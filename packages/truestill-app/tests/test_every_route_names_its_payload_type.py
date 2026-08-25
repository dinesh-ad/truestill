"""Every route names the payload type it returns. `(ahn)` stage 2

`(ahn)` measured that **50 routes are annotated `-> JSONResponse` and nothing declares which
payload each returns**, which is why `(ahl)`'s census had to work at key-name granularity and could
not see a collided field. This is the join: derived on one side, declared on the other.

⚠ **IT RESOLVES A DECLARATION, IT DOES NOT MATCH A CALL SHAPE, and that is the whole design.**
Measured before writing it: the 50 handlers reach their service function through **39 distinct
return-expression spellings** - direct calls, `run_in_threadpool(service.X, ...)`,
`run_in_threadpool(_start_drive_job, await run_in_threadpool(service.X, ...))`, a local assigned
earlier and returned by name, and two local helpers. A resolver keyed on any one of those would
have the hole `(agu)` shipped and P77 repaired, **and this file's own author walked into it once**:
the P86 census matched `_start_drive_job(` and silently missed the eleven sites that reach it
through `run_in_threadpool`. So :func:`_service_names` looks for the **reference** to
``service.X`` anywhere in the handler, following local helpers, and never asks how it is called.

⚠ **WHAT THIS PROVES**: every route names at least one *declared* payload type, or is listed below
with a reason. A new route that names none fails.

⚠ **WHAT IT CANNOT PROVE, and the distinction matters more than the guard**: that the named type is
what the handler actually returns. A handler that resolves to `BackupPreviewOk` and returns
`JSONResponse({"error": ...})` from one branch passes here. **That is mypy's job once the
annotations exist** - which is stage 4, not this - and until then the branches that build a dict
literal are enumerated in :data:`UNTYPED_LITERAL` rather than left to look covered.

⚠ **WHICH BLINDNESS THIS CLOSES, because `(ahl)` has two and they are not the same.**
`PROJECT_STATUS.md`'s condition 3 is blind in two ways:

* **a name collision** - `BakeSummary.absent` reads as live because `BakePreview.absent` is
  rendered. ❌ **NOT closed here.** `BakeSummary` is a **job** payload, delivered on the SSE stream,
  and no route returns it. `(ahn)` stage 1 gave it a type; only a payload-granular census over
  *both* channels unhides it, and that is stage 3.
* **no route-to-payload join** - ✅ **this closes it**, for the HTTP channel only.

Claiming otherwise would make the census believe it had payload granularity everywhere. It has it
for routes.

**Cost, declared rather than suppressed** (`ENGINEERING_STANDARD.md` §4): one `ast.parse` of
`server.py`, one of each module under `service/`, then a walk per handler with local helpers
followed to a depth bound. Linear in the source, well under a second.
"""

from __future__ import annotations

import ast
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SERVER = ROOT / "packages/truestill-app/src/truestill_app/server.py"
SERVICE = ROOT / "packages/truestill-app/src/truestill_app/service"

#: Routes that return no JSON payload at all. ⚠ **A ceiling, not a list to append to** - see
#: `test_the_declarations_cannot_grow`. Each says what it returns instead.
NOT_A_JSON_PAYLOAD: dict[str, str] = {
    "/": "serves `index.html` as an `HTMLResponse`. A page, not a payload",
    "/api/jobs/{job_id}/events": (
        "an SSE stream of `bytes`. Each frame carries a JOB payload, which `(ahn)` stage 1 typed "
        "at the producer and which no route returns"
    ),
    "/api/jobs/{job_id}/cancel": "a bare 202/404 `Response` with no body at all",
}

#: Places a JSON payload is built from a **dict literal**, so no type describes it.
#:
#: ⚠ **EMPTY SINCE 2026-08-25, AND THE CEILING FELL WITH IT.** It held **seven** when this guard
#: was written, each row naming its remedy rather than its excuse; `(ahn)` stage 4a typed six and
#: **deleted** the seventh - `events_propose` was re-implementing `invalid_event_proposal_payload`
#: two lines below calling it, so a type would have frozen a duplicate rather than fixed one.
#:
#: ⚠ **A ceiling left at seven would be a hole with a note beside it**: the table could refill to
#: its old size and nothing would say so. `test_the_declarations_cannot_grow_and_the_derived_side_is_real`
#: now requires it to be **empty**, so the next literal payload fails on arrival. That is the
#: point of a debt table shrinking - the number is the evidence, and it has to be checked.
UNTYPED_LITERAL: dict[str, str] = {}

#: Measured 2026-08-25. Floors sit just under the derived figures - `(agu)`'s floor read `>= 12`
#: against a real 16 and could never fire - and the declarations get **ceilings** instead, because
#: a declaration of known debt must never be somewhere new debt can be added quietly.
MEASURED_ROUTES = 50
MEASURED_RESOLVED = 47


def _module(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"))


def _functions(tree: ast.Module) -> dict[str, ast.FunctionDef | ast.AsyncFunctionDef]:
    return {
        n.name: n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef)
    }


def _routes(tree: ast.Module) -> list[tuple[str, str]]:
    """``(path, handler name)`` for every `Route(...)` the server declares."""
    return [
        (ast.unparse(n.args[0]).strip("'\""), ast.unparse(n.args[1]))
        for n in ast.walk(tree)
        if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "Route" and len(n.args) > 1
    ]


def _service_names(
    fn: ast.FunctionDef | ast.AsyncFunctionDef,
    helpers: dict[str, ast.FunctionDef | ast.AsyncFunctionDef],
    seen: frozenset[str] = frozenset(),
) -> set[str]:
    """Every ``service.X`` **named** anywhere in `fn`, following local helpers.

    ⚠ **An `ast.Attribute` on the name `service`, not a call.** That is what makes it blind to how
    the function is invoked - awaited, threadpooled, assigned to a local first, or handed to
    `_start_drive_job` - and it is the repair P77 made to `_declared()` applied before the same
    hole could open here.
    """
    found: set[str] = set()
    for node in ast.walk(fn):
        if (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == "service"
        ):
            found.add(node.attr)
        if isinstance(node, ast.Call):
            name = getattr(node.func, "id", None)
            if name in helpers and name not in seen and name != fn.name:
                found |= _service_names(helpers[name], helpers, seen | {name})
    return found


def _declared_return_types() -> dict[str, set[str]]:
    """``service function name -> the return annotations it is declared with.``"""
    annotations: dict[str, set[str]] = defaultdict(set)
    for path in sorted(SERVICE.glob("*.py")):
        for node in ast.walk(_module(path)):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.returns:
                annotations[node.name].add(ast.unparse(node.returns))
    return annotations


def _resolution() -> tuple[dict[str, set[str]], list[str]]:
    """``({route: payload types}, [routes that name none])``."""
    tree = _module(SERVER)
    helpers = _functions(tree)
    typed = _declared_return_types()
    resolved: dict[str, set[str]] = {}
    bare: list[str] = []
    for path, handler in _routes(tree):
        fn = helpers.get(handler)
        names = _service_names(fn, helpers) if fn is not None else set()
        types = {t for name in names for t in typed.get(name, set())}
        if types:
            resolved[path] = types
        else:
            bare.append(path)
    return resolved, bare


def _literal_payloads() -> dict[str, int]:
    """``"<function>: <sorted keys>" -> line``, for every `JSONResponse(<dict literal>)`.

    ⚠ **Helpers included, not only route handlers.** Two of the seven live in
    `_catalog_busy_refusal` and `expired_session`, and the biggest is `_start_drive_job`'s - a
    census of handlers alone would have found five of seven and looked complete.
    """
    tree = _module(SERVER)
    spans = [
        (fn.lineno, fn.end_lineno or fn.lineno, fn.name)
        for fn in ast.walk(tree)
        if isinstance(fn, ast.FunctionDef | ast.AsyncFunctionDef)
    ]
    found: dict[str, int] = {}
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and getattr(node.func, "id", "") == "JSONResponse"
            and node.args
            and isinstance(node.args[0], ast.Dict)
        ):
            inner = [n for lo, hi, n in spans if lo <= node.lineno <= hi]
            # ⚠ A `None` key is `{**spread}`, which has no name to record. Marked rather than
            # dropped: a literal that splices another dict is still a literal, and silently
            # reporting a partial key set would make two different payloads share one row.
            named = sorted(ast.unparse(k).strip("'\"") for k in node.args[0].keys if k is not None)
            if any(k is None for k in node.args[0].keys):
                named.append("**spread")
            found[f"{inner[-1] if inner else '?'}: {','.join(named)}"] = node.lineno
    return found


def test_every_route_names_a_payload_type() -> None:
    """**The join.** Loop the DERIVED routes; assert into the DECLARATION.

    `ENGINEERING_STANDARD.md`'s seventy-second member. Iterating the table instead would pass
    perfectly against an emptied one - `test_the_declarations_cannot_grow` proves this one does not.
    """
    resolved, bare = _resolution()
    undeclared = sorted(set(bare) - NOT_A_JSON_PAYLOAD.keys())

    assert not undeclared, (
        "these routes name no service function, so nothing declares what they return:\n"
        + "\n".join(f"  {route}" for route in undeclared)
        + "\n\nEither the handler should call a typed service function, or add it to "
        "`NOT_A_JSON_PAYLOAD` WITH what it returns instead."
    )
    assert resolved, "no route resolved at all; the resolver is looking at the wrong tree"


def test_no_new_payload_is_built_from_a_dict_literal() -> None:
    """A literal has no type, so a route that builds one is outside the join even when it resolves.

    ⚠ **This is the half `test_every_route_names_a_payload_type` cannot see.** A handler that names
    a typed service function AND returns a literal from one branch passes that test and is still
    undeclared here.
    """
    undeclared = sorted(set(_literal_payloads()) - UNTYPED_LITERAL.keys())

    assert not undeclared, (
        "these JSON payloads are built from a dict literal and nothing names their type:\n"
        + "\n".join(f"  {site}" for site in undeclared)
        + "\n\nGive it a TypedDict. Every row already in `UNTYPED_LITERAL` is typeable too - the "
        "table records debt with its remedy, and is not somewhere to add more."
    )


def test_a_declaration_that_stopped_being_needed_is_removed() -> None:
    """⚠ **CRY-WOLF HALF, both tables.** A declaration that outlives its reason is how a table of
    known holes becomes a table of things somebody once wrote down."""
    resolved, _bare = _resolution()
    stale_routes = sorted(NOT_A_JSON_PAYLOAD.keys() & resolved.keys())
    stale_literals = sorted(UNTYPED_LITERAL.keys() - _literal_payloads().keys())

    assert not stale_routes, f"these now resolve and should leave the table: {stale_routes}"
    assert not stale_literals, (
        f"these literals are gone - delete the row, it is the good direction: {stale_literals}"
    )


def test_the_declarations_cannot_grow_and_the_derived_side_is_real() -> None:
    """Anti-vacuity in both directions, from the MEASURED counts.

    **Floors** on the derived side, just under measured: a resolver pointed at a moved file or
    reading one call shape returns a smaller inventory and every assertion above passes on it.
    **Ceilings** on the declarations, because a table of known debt is exactly where new debt is
    easiest to add quietly - and both tables are meant to shrink.
    """
    resolved, bare = _resolution()

    assert len(_routes(_module(SERVER))) >= MEASURED_ROUTES - 5
    assert len(resolved) >= MEASURED_RESOLVED - 5, f"only {len(resolved)} routes resolved"
    assert len(NOT_A_JSON_PAYLOAD) <= 3, "a fourth route that returns no payload needs a ruling"
    assert not UNTYPED_LITERAL, (
        "the literal debt table refilled. It reached zero on 2026-08-25 and the ceiling fell "
        "with it - type the payload instead of listing it"
    )
    assert len(bare) == len(NOT_A_JSON_PAYLOAD), "the unresolvable set and its table disagree"


def test_the_resolver_ignores_how_the_service_function_is_called() -> None:
    """⚠ **`(agu)`'s defect refused in advance, and P86's own census walked into it.**

    Four spellings, one of which (`run_in_threadpool(_start_drive_job, ...)`) is the one that
    census missed. Driven against source written here, so the proof does not depend on `server.py`
    continuing to contain every shape.
    """
    module = ast.parse(
        "def h1(r):\n    return JSONResponse(service.direct(db))\n"
        "def h2(r):\n    return JSONResponse(await run_in_threadpool(service.pooled, db))\n"
        "def h3(r):\n    t = service.assigned(db)\n    return JSONResponse(t)\n"
        "def helper(x):\n    return service.viaHelper(x)\n"
        "def h4(r):\n    return helper(1)\n"
    )
    helpers = _functions(module)

    assert _service_names(helpers["h1"], helpers) == {"direct"}
    assert _service_names(helpers["h2"], helpers) == {"pooled"}, "the threadpool shape was missed"
    assert _service_names(helpers["h3"], helpers) == {"assigned"}, "a local binding was missed"
    assert _service_names(helpers["h4"], helpers) == {"viaHelper"}, (
        "a local helper was not followed"
    )
