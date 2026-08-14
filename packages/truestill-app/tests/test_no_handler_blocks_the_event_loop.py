"""No route handler does synchronous work on the event loop.

**The defect this closes, measured 2026-08-14.** Every handler the page calls on load was
`async def` doing synchronous work - a catalog open, a directory listing - directly on the loop.
Starlette runs `async def` endpoints *on the loop*; only plain `def` endpoints get a threadpool.
So one slow filesystem call did not just make that one request slow, it stopped the server.

Measured with a 2 s synchronous sleep injected into a single handler:

| | |
|---|---|
| page load (`wait_until="load"`) | **4085 ms** |
| event-loop lag, max | **3995 ms** |
| the bundled fonts arrived at | **4077 ms** |

The fonts are static files with no relationship to the handler that slept. They were four seconds
late because the loop was blocked, and they are what `load` waits for. That is the whole failure:
**a slow handler stalls static asset serving and every other request behind it.**

It reached us as two WebKit timeouts in CI, and only WebKit because engines differ in when they
fetch fonts - WebKit issues them after the API calls, Chromium before. Nine WebKit tests were
inside 3 s of the 15 s ceiling; two crossed it. Raising the timeout was refused deliberately: it
would have made CI green and left a user on a slow disk with an app that hangs on open.

**The reasoning was already in this repo, applied to one route.** `server.thumb` is wrapped in
`run_in_threadpool` with the comment that 23 ms of CPU-bound decode on the loop *"would stall
every other request behind each tile - which on a fifty-tile grid is the whole page"*. A directory
listing on a network mount is the same shape, and `PERFORMANCE.md` §5.2 already measured an
encrypted cloud mount dominating CPU by 3.6x to 36x.

**The rule, checkable rather than remembered:** a handler may call `service.*` only where it is not
on the loop - either the handler is `def`, or the call goes through `run_in_threadpool`.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

SERVER = Path(__file__).resolve().parents[1] / "src/truestill_app/server.py"


def _routed_handlers(tree: ast.Module) -> set[str]:
    """Names passed to `Route(...)`, so the check covers endpoints and nothing else.

    Derived from the route table rather than from a naming convention: a helper that happens to
    look like a handler is not one, and a handler that stops looking like one is still routed.
    """
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "Route":
            for arg in node.args[1:2]:
                if isinstance(arg, ast.Name):
                    names.add(arg.id)
    return names


def _local_functions(tree: ast.Module) -> dict[str, ast.FunctionDef | ast.AsyncFunctionDef]:
    return {
        n.name: n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def _blocking_locals(tree: ast.Module) -> set[str]:
    """Functions in this module that reach `service.*` synchronously, followed transitively.

    ⚠ **The first version of this guard looked only inside handler bodies, and missed the worst
    case in the file.** `_start_drive_job` is a helper, so nothing flagged it - and it calls
    `service.drive_ref_for`, which reads a drive marker off disk. Sixteen handlers called it, so
    every job start did filesystem I/O on the event loop while the guard reported clean. A rule
    that stops at one level answers "does this function block" when the question is "does calling
    it block".
    """
    local = _local_functions(tree)
    blocking: set[str] = set()
    changed = True
    while changed:  # fixpoint: a caller of a blocker is a blocker
        changed = False
        for name, fn in local.items():
            if name in blocking:
                continue
            for call in _unpooled_calls(fn, blocking):
                del call
                blocking.add(name)
                changed = True
                break
    return blocking


def _unpooled_calls(
    fn: ast.FunctionDef | ast.AsyncFunctionDef, blocking_locals: set[str]
) -> list[str]:
    """Calls in ``fn`` that reach blocking work without going through a threadpool."""
    wrapped: set[int] = set()
    for node in ast.walk(fn):
        if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "run_in_threadpool":
            for arg in node.args:
                wrapped.add(id(arg))
    found = []
    for node in ast.walk(fn):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        # `run_in_threadpool(f, a, b)` passes the FUNCTION, never a call - so a Call node
        # reaching here is being invoked directly.
        if isinstance(func, ast.Attribute) and getattr(func.value, "id", None) == "service":
            if id(func) not in wrapped:
                found.append(f"service.{func.attr} (line {node.lineno})")
        elif (
            isinstance(func, ast.Name)
            and func.id in blocking_locals
            and func.id != fn.name
            and id(func) not in wrapped
        ):
            found.append(f"{func.id}() (line {node.lineno})")
    return found


def _blocking_calls(fn: ast.AsyncFunctionDef, blocking_locals: set[str]) -> list[str]:
    return _unpooled_calls(fn, blocking_locals)


def _async_handlers() -> dict[str, ast.AsyncFunctionDef]:
    tree = ast.parse(SERVER.read_text())
    routed = _routed_handlers(tree)
    return {
        n.name: n
        for n in ast.walk(tree)
        if isinstance(n, ast.AsyncFunctionDef) and n.name in routed
    }


def test_the_route_table_was_actually_parsed() -> None:
    """Cry-wolf guard. An AST walk that matched nothing would make every assertion below
    vacuously true - the empty-set-reads-as-success trap this repo keeps finding."""
    routed = _routed_handlers(ast.parse(SERVER.read_text()))
    assert len(routed) > 30, f"only {len(routed)} routed handlers parsed; the walk is broken"


@pytest.mark.parametrize("name", sorted(_async_handlers()))
def test_an_async_handler_does_no_synchronous_service_work(name: str) -> None:
    """THE GUARD. Parametrized per handler so a failure names the one that regressed.

    An `async def` handler runs ON the event loop. A plain `def` handler is dispatched to a
    threadpool by Starlette itself, which is why converting is the fix rather than a workaround:
    it is the framework's own mechanism, not one bolted on.
    """
    tree = ast.parse(SERVER.read_text())
    offenders = _blocking_calls(_async_handlers()[name], _blocking_locals(tree))
    assert not offenders, (
        f"`{name}` is `async def` and calls {offenders} directly, so that work runs on the event "
        "loop and stalls every other request - including static assets. Either drop `async` (a "
        "`def` endpoint is pooled by Starlette) or route the call through `run_in_threadpool`."
    )
