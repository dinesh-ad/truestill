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
JOBS = ROOT / "packages/truestill-app/src/truestill_app/jobs.py"
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
MEASURED_ROUTES = 52  # 50 on 2026-08-25; re-measured 2026-09-02 (P191)
MEASURED_RESOLVED = 49  # 47 on 2026-08-25


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


def _spans(tree: ast.Module) -> list[tuple[int, int, str]]:
    return [
        (fn.lineno, fn.end_lineno or fn.lineno, fn.name)
        for fn in ast.walk(tree)
        if isinstance(fn, ast.FunctionDef | ast.AsyncFunctionDef)
    ]


def _literal_frames(path: Path = JOBS) -> dict[str, int]:
    """``"<function>: <what>" -> line``, for every frame that reaches the stream with no name.

    ⚠ **Stage B (P195): 4a's census read `JSONResponse(<dict literal>)` in `server.py` and
    nothing else, so the three SSE frames and one hand-written byte string were untyped AND
    unlisted - a hole with no note beside it.** Four shapes escape a queue-reading census: a
    dict literal handed straight to ``.put(...)`` or ``json.dumps(...)``, a dict literal
    assigned to an UNannotated name (an annotated one is typed by its annotation), and a bytes
    literal carrying ``data:``, which is a frame written by hand.
    """
    tree = _module(path)
    spans = _spans(tree)
    found: dict[str, int] = {}

    def record(node: ast.expr | ast.stmt, what: str) -> None:
        inner = [n for lo, hi, n in spans if lo <= node.lineno <= hi]
        found[f"{inner[-1] if inner else '?'}: {what}"] = node.lineno

    def keys(literal: ast.Dict) -> str:
        return ",".join(sorted(ast.unparse(k).strip("'\"") for k in literal.keys if k is not None))

    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and node.args and isinstance(node.args[0], ast.Dict):
            attr = getattr(node.func, "attr", "")
            if attr in ("put", "dumps"):
                record(node, f"{attr}({{{keys(node.args[0])}}})")
        elif isinstance(node, ast.Assign) and isinstance(node.value, ast.Dict):
            record(node, f"{ast.unparse(node.targets[0])} = {{{keys(node.value)}}}")
        elif (
            isinstance(node, ast.Constant)
            and isinstance(node.value, bytes)
            and b"data:" in node.value
        ):
            record(node, "hand-written bytes frame")
    return found


def _typeddict_names() -> set[str]:
    """Every TypedDict declared in the app, INCLUDING those that inherit another - the base test
    `"TypedDict" in base` misses `OrganizeDoneSummary(CompletionBase)` and two more."""
    classes: dict[str, list[str]] = {}
    for path in [*sorted(SERVICE.glob("*.py")), JOBS]:
        for node in ast.walk(_module(path)):
            if isinstance(node, ast.ClassDef):
                classes[node.name] = [ast.unparse(b) for b in node.bases]
    names = {n for n, bases in classes.items() if any("TypedDict" in b for b in bases)}
    while True:
        more = {
            n for n, bases in classes.items() if n not in names and any(b in names for b in bases)
        }
        if not more:
            return names
        names |= more


def _job_summary_types() -> dict[str, list[str]]:
    """``factory -> the members of its JobTarget[T]``: what `DoneFrame.summary` can be, derived
    from the thirteen annotations rather than listed a second time. `(ahn)` stage B."""
    out: dict[str, list[str]] = {}
    for name, returns in _declared_return_types().items():
        for text in returns:
            for member in _union_members(text):
                if member.startswith("JobTarget[") and member.endswith("]"):
                    out[name] = _union_members(member[len("JobTarget[") : -1])
    return out


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
    undeclared = sorted(
        (set(_literal_payloads()) | set(_literal_frames())) - UNTYPED_LITERAL.keys()
    )

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


# ------------------------------------------------------- `(ahn)` stage 4b: what REACHES a JSONResponse

#: The pool helper: `run_in_threadpool(F, ...)` answers with whatever `F` answers with.
_POOL = "run_in_threadpool"
#: Response classes that carry no JSON payload; a route returning one is not a payload route.
_NOT_JSON = ("HTMLResponse", "StreamingResponse", "PlainTextResponse", "Response")


def _is_service(f: ast.expr) -> bool:
    return (
        isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) and f.value.id == "service"
    )


class _Scope:
    """What a name means inside one handler: its declared annotation, or the type of what was
    assigned to it, resolved lazily and in source order."""

    def __init__(
        self,
        handler: ast.FunctionDef | ast.AsyncFunctionDef,
        helpers: dict[str, ast.FunctionDef | ast.AsyncFunctionDef],
        typed: dict[str, set[str]],
        bound: dict[str, str] | None = None,
    ) -> None:
        self.helpers, self.typed = helpers, typed
        self.declared: dict[str, str] = {
            a.arg: ast.unparse(a.annotation)
            for a in handler.args.args + handler.args.kwonlyargs
            if a.annotation is not None
        }
        # A helper's parameter means what the CALLER passed, not its own annotation: stage A.
        self.declared.update(bound or {})
        self.raw: dict[str, ast.expr] = {}
        self.resolving: set[str] = set()
        self.body = _own_statements(handler)
        for node in self.body:
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                self.declared[node.target.id] = ast.unparse(node.annotation)
            elif (
                isinstance(node, ast.Assign)
                and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
            ):
                self.raw[node.targets[0].id] = node.value

    def of_callable(self, f: ast.expr) -> str:
        # `partial(service.X, ...)` is the callable `service.X` with arguments filled in; the
        # pool runs it and the response is still what `service.X` declares. Stage A.
        if isinstance(f, ast.Call) and getattr(f.func, "id", None) == "partial" and f.args:
            return self.of_callable(f.args[0])
        if _is_service(f):
            assert isinstance(f, ast.Attribute)
            return " | ".join(sorted(self.typed.get(f.attr, {f"?service.{f.attr}"})))
        name = getattr(f, "id", None)
        return f"HELPER:{name}" if name in self.helpers else f"?callable:{ast.unparse(f)[:40]}"

    def of_name(self, name: str) -> str:
        if name in self.declared:
            return self.declared[name]
        if name in self.raw and name not in self.resolving:
            self.resolving.add(name)
            try:
                return self.of(self.raw[name])
            finally:
                self.resolving.discard(name)
        return f"?local:{name}"

    def of_call(self, call: ast.Call) -> str:
        f = call.func
        name = getattr(f, "id", None)
        if name == _POOL and call.args:
            return self.of_callable(call.args[0])
        if _is_service(f):
            return self.of_callable(f)
        if name == "dict" and call.args:
            return self.of(call.args[0])
        if name in self.helpers:
            return f"HELPER:{name}"
        return f"?{ast.unparse(call)[:40]}"

    def binding(self, text: str, args: list[ast.expr]) -> dict[str, str]:
        """What a followed helper's first positional parameter is, from this call's argument.

        `_start_drive_job(started, ...)` receives the factory's return, and its own annotation
        (`JobTarget[object] | Mapping[str, object]`) is deliberately wide. The caller's argument
        is the precise type, minus every `JobTarget[...]` member - a job target is run, never
        sent, which was stage 2's whole lesson. An empty remainder means the refusal arm is
        unreachable from this caller and is recorded as :data:`_NEVER`.
        """
        if not text.startswith("HELPER:") or not args:
            return {}
        params = self.helpers[text.removeprefix("HELPER:")].args.args
        if not params:
            return {}
        kept = [m for m in _union_members(self.of(args[0])) if not m.startswith("JobTarget[")]
        return {params[0].arg: " | ".join(kept) or _NEVER}

    def of(self, expr: ast.expr) -> str:
        if isinstance(expr, ast.Await):
            return self.of(expr.value)
        if isinstance(expr, ast.Name):
            return self.of_name(expr.id)
        if isinstance(expr, ast.Dict):
            return "dict literal"
        if isinstance(expr, ast.Call):
            return self.of_call(expr)
        return f"?{ast.unparse(expr)[:40]}"


#: A response arm proved unreachable from its caller: `dict(target)` when every member the
#: caller passes is a `JobTarget[...]`. Dropped from a route's set, never written into a row.
_NEVER = "never"


def _union_members(text: str) -> list[str]:
    """`A | B[C | D] | E` -> `["A", "B[C | D]", "E"]` - a split that respects brackets, because
    `JobTarget[CompletionBase | OrganizeDoneSummary]` is one member, not two."""
    members, depth, start = [], 0, 0
    for i, ch in enumerate(text):
        depth += ch == "["
        depth -= ch == "]"
        if depth == 0 and text.startswith(" | ", i):
            members.append(text[start:i])
            start = i + 3
    members.append(text[start:])
    return [m for m in members if m]


def _own_statements(node: ast.AST) -> list[ast.AST]:
    """Every node inside `node` except those inside a nested function - a nested function is its
    own scope, and its returns are not this handler's."""
    out: list[ast.AST] = []
    for child in ast.iter_child_nodes(node):
        if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda):
            continue
        out.append(child)
        out.extend(_own_statements(child))
    return out


def _returned(node: ast.Return, scope: _Scope) -> tuple[str, dict[str, str]]:
    """What one `return` sends: the argument of `JSONResponse(...)`, a helper to follow (with
    what its first parameter is bound to), a non-JSON response class, or an unresolved
    expression kept under `?`."""
    assert node.value is not None
    value = node.value.value if isinstance(node.value, ast.Await) else node.value
    if isinstance(value, ast.Call):
        name = getattr(value.func, "id", None)
        if name == "JSONResponse" and value.args:
            return scope.of(value.args[0]), {}
        if name in _NOT_JSON:
            return f"not JSON:{name}", {}
        if name == _POOL and value.args:
            text = scope.of_callable(value.args[0])
            return text, scope.binding(text, value.args[1:])
        if name in scope.helpers:
            return f"HELPER:{name}", scope.binding(f"HELPER:{name}", value.args)
    return f"?{ast.unparse(node.value)[:40]}", {}


def _response_types(
    handler: ast.FunctionDef | ast.AsyncFunctionDef,
    helpers: dict[str, ast.FunctionDef | ast.AsyncFunctionDef],
    typed: dict[str, set[str]],
    seen: frozenset[str] = frozenset(),
    bound: dict[str, str] | None = None,
) -> set[str]:
    """The types of every expression that reaches ``JSONResponse(...)`` from this handler.

    **The rule, written down (P191):** the response is the first positional argument of every
    `JSONResponse(...)` reachable from the handler, and a helper the handler returns through -
    `_start_drive_job`, directly or via `run_in_threadpool` - contributes every one of ITS
    responses. That is what stage 2's resolver does not do: it names every `service.X` the
    handler *refers to*, so a job route resolved to `JobTarget[BackupRunSummary]`, the factory's
    callable type, which no route ever sends.

    **Stage A (P193) closed the two gaps P191 left open, without branch analysis.** A narrowed
    value is bound to an annotated local in `server.py` (`busy: DriveBusyPayload = result`), so
    the name IS the arm; and a followed helper's first parameter reads as the caller's argument
    minus its `JobTarget[...]` members, so `dict(target)` names the refusal payloads this route
    can actually send. Every unresolved expression is kept under `?`, never dropped - an
    unresolved response must show up in the derivation, not vanish from it.
    """
    scope = _Scope(handler, helpers, typed, bound)
    types: set[str] = set()
    for node in scope.body:
        if not isinstance(node, ast.Return) or node.value is None:
            continue
        text, binding = _returned(node, scope)
        if not text.startswith("HELPER:"):
            types.add(text)
            continue
        name = text.removeprefix("HELPER:")
        if name in seen or name == handler.name:
            types.add(f"?recursive:{name}")
        else:
            types |= _response_types(helpers[name], helpers, typed, seen | {name}, binding)
    return types - {_NEVER}


def _response_resolution() -> dict[str, set[str]]:
    """``route -> the types that reach its JSONResponse``, the stage-4b derivation."""
    tree = _module(SERVER)
    helpers = _functions(tree)
    typed = _declared_return_types()
    return {
        path: _response_types(helpers[handler], helpers, typed)
        for path, handler in _routes(tree)
        if handler in helpers
    }


#: Re-derived 2026-09-02 (P193, stage A): 52 routes, MEASURED_MULTI_TYPE_RESPONSES resolve to more
#: than one type-string (40 when a `X | Y` string is counted by member), and the job envelope is
#: now named PER ROUTE - `JobStarted`, `DriveBusyPayload`,
#: and each refusal payload the route's own factory can return - instead of a shared
#: `Mapping[str, object]`. Zero unresolved. Floors, never ceilings; the count is read from
#: `test_the_response_derivation_is_real`. No declaration row is written from it yet: stage D
#: emits from it (`(ahn)`).
MEASURED_RESPONSE_ROUTES = 52
MEASURED_MULTI_TYPE_RESPONSES = 29


def test_the_response_derivation_is_real() -> None:
    """Anti-vacuity for the stage-4b resolver, and the place its numbers are read from.

    The job envelope must show its arms on every job-start route (`JobStarted`,
    `DriveBusyPayload`, the refusal Mapping), a plain route must resolve to its service's
    declared return, and the unresolved set must stay small and named - a resolver that answered
    `?` for everything would still "resolve" 52 routes.
    """
    resolution = _response_resolution()
    assert len(resolution) >= MEASURED_RESPONSE_ROUTES - 5, f"only {len(resolution)} routes"
    job_start = [p for p, t in resolution.items() if any("JobStarted" in x for x in t)]
    assert len(job_start) >= 15, f"only {len(job_start)} job-start routes show the envelope"
    for path in job_start:
        joined = " ".join(resolution[path])
        assert "DriveBusyPayload" in joined, f"{path} lacks the busy arm"
        # Stage A: the two shapes P191 said a row must never encode.
        assert "Mapping[str, object]" not in joined, f"{path} still carries the wide parameter"
        assert "str | DriveBusyPayload" not in joined, f"{path} still carries the unnarrowed local"
        assert "JobTarget[" not in joined, f"{path} names a job target as a response"
    # The refusal arm is the caller's, per route: none for backup, two for the bake.
    assert resolution["/api/backup/run"] == {"JobStarted", "DriveBusyPayload"}
    bake = " ".join(resolution["/api/dates/bake/run"])
    assert "BakeRefusal" in bake, bake
    assert "DriveUnavailablePayload" in bake, bake
    assert resolution["/api/library/stats"] == {"LibraryStats"}
    multi = sum(1 for t in resolution.values() if len(t) > 1)
    assert multi >= MEASURED_MULTI_TYPE_RESPONSES - 5, f"multi-type routes fell to {multi}"
    unresolved = {
        p: sorted(x for x in t if x.startswith("?"))
        for p, t in resolution.items()
        if any(x.startswith("?") for x in t)
    }
    assert not unresolved, f"unresolved responses: {unresolved}"


#: The thirteen `JobTarget[T]` factories on 2026-09-03; a floor just under it.
MEASURED_JOB_FACTORIES = 13


def test_the_frame_census_sees_what_escapes_a_queue(tmp_path: Path) -> None:
    """Driven against source written here: the three unnamed shapes are found, the annotated
    local - the remedy - is not. ⚠ On `jobs.py` as committed before stage B this census
    reported four; on the tree it reports none, and that is the whole proof of stage B."""
    probe = tmp_path / "probe.py"
    probe.write_text(
        "def run(q):\n"
        "    q.put({'type': 'progress', 'done': 1})\n"
        "    terminal = {'type': 'done'}\n"
        "    frame: DoneFrame = {'type': 'done'}\n"
        "    q.put(frame)\n"
        "def stream():\n"
        "    yield b'event: error\\ndata: {}\\n\\n'\n",
        encoding="utf-8",
    )
    found = _literal_frames(probe)
    assert set(found) == {
        "run: put({done,type})",
        "run: terminal = {type}",
        "stream: hand-written bytes frame",
    }, found
    assert not _literal_frames(), "a frame reached the stream without a name; give it a TypedDict"


def test_done_frame_summary_is_derived_not_listed() -> None:
    """`DoneFrame.summary` is `object` in code and the union of the factories' `T` here - one
    definition, read from the annotations stage A made the resolver read. A hand-written
    `JobSummary` alias would be the second definition this refuses."""
    factories = _job_summary_types()
    assert len(factories) >= MEASURED_JOB_FACTORIES - 2, f"only {len(factories)} factories"
    members = {m for ms in factories.values() for m in ms}
    assert len(members) >= 12, f"only {len(members)} summary types: {sorted(members)}"
    declared = _typeddict_names()
    assert members <= declared, f"not TypedDicts: {sorted(members - declared)}"
    done = next(
        n for n in ast.walk(_module(JOBS)) if isinstance(n, ast.ClassDef) and n.name == "DoneFrame"
    )
    summary = [
        ast.unparse(st.annotation)
        for st in done.body
        if isinstance(st, ast.AnnAssign) and ast.unparse(st.target) == "summary"
    ]
    assert summary == ["object"], (
        f"DoneFrame.summary is {summary}; the union is derived, not listed"
    )
