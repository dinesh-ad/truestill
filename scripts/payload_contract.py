"""The payload contract's derivations: what every route, frame and job summary sends. `(ahn)`

**Everything here is read from the source, never listed.** Stage A's resolver names the types
that reach a `JSONResponse` from each handler, with the status code and the method of each arm;
stage B's census names the frames `jobs.py` writes; the thirteen factories' `JobTarget[T]`
annotations name the summaries; the `exception_handlers` registration names the refusal every
route can carry. `scripts/emit_openapi.py` emits from these and from nothing else, and the tests
under `packages/truestill-app/tests/` assert into them.

Lived in `test_every_route_names_its_payload_type.py` until stage D (2026-09-03), when the
emitter needed it and a script importing a test would have been backwards.
"""

from __future__ import annotations

import ast
import importlib
import pkgutil
import typing
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "packages/truestill-app/src/truestill_app/server.py"
JOBS = ROOT / "packages/truestill-app/src/truestill_app/jobs.py"
SERVICE = ROOT / "packages/truestill-app/src/truestill_app/service"


def module(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"))


def functions(tree: ast.Module) -> dict[str, ast.FunctionDef | ast.AsyncFunctionDef]:
    return {
        n.name: n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef)
    }


def routes(tree: ast.Module) -> list[tuple[str, str]]:
    """``(path, handler name)`` for every `Route(...)` the server declares."""
    return [(path, handler) for path, handler, _ in routes_with_methods(tree)]


def routes_with_methods(tree: ast.Module) -> list[tuple[str, str, list[str]]]:
    """``(path, handler name, methods)``; Starlette's default when none is declared is ``GET``."""
    out: list[tuple[str, str, list[str]]] = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "Route" and len(n.args) > 1:
            methods = ["GET"]
            for kw in n.keywords:
                if kw.arg == "methods" and isinstance(kw.value, ast.List):
                    methods = [ast.unparse(e).strip("'\"") for e in kw.value.elts]
            out.append((ast.unparse(n.args[0]).strip("'\""), ast.unparse(n.args[1]), methods))
    return out


def declared_return_types() -> dict[str, set[str]]:
    """``service function name -> the return annotations it is declared with.``"""
    annotations: dict[str, set[str]] = defaultdict(set)
    for path in sorted(SERVICE.glob("*.py")):
        for node in ast.walk(module(path)):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.returns:
                annotations[node.name].add(ast.unparse(node.returns))
    return annotations


def typeddict_names() -> set[str]:
    """Every TypedDict declared in the app, INCLUDING those that inherit another - the base test
    `"TypedDict" in base` misses `OrganizeDoneSummary(CompletionBase)` and two more."""
    classes: dict[str, list[str]] = {}
    for path in [*sorted(SERVICE.glob("*.py")), JOBS]:
        for node in ast.walk(module(path)):
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


def job_summary_types() -> dict[str, list[str]]:
    """``factory -> the members of its JobTarget[T]``: what `DoneFrame.summary` can be, derived
    from the thirteen annotations rather than listed a second time. `(ahn)` stage B."""
    out: dict[str, list[str]] = {}
    for name, returns in declared_return_types().items():
        for text in returns:
            for member in union_members(text):
                if member.startswith("JobTarget[") and member.endswith("]"):
                    out[name] = union_members(member[len("JobTarget[") : -1])
    return out


POOL = "run_in_threadpool"
#: Response classes that carry no JSON payload; a route returning one is not a payload route.
NOT_JSON = ("HTMLResponse", "StreamingResponse", "PlainTextResponse", "Response")


def is_service(f: ast.expr) -> bool:
    return (
        isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) and f.value.id == "service"
    )


class Scope:
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
        self.body = own_statements(handler)
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
        if is_service(f):
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
        if name == POOL and call.args:
            return self.of_callable(call.args[0])
        if is_service(f):
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
        unreachable from this caller and is recorded as :data:`NEVER`.
        """
        if not text.startswith("HELPER:") or not args:
            return {}
        params = self.helpers[text.removeprefix("HELPER:")].args.args
        if not params:
            return {}
        kept = [m for m in union_members(self.of(args[0])) if not m.startswith("JobTarget[")]
        return {params[0].arg: " | ".join(kept) or NEVER}

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
NEVER = "never"


def union_members(text: str) -> list[str]:
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


def own_statements(node: ast.AST) -> list[ast.AST]:
    """Every node inside `node` except those inside a nested function - a nested function is its
    own scope, and its returns are not this handler's."""
    out: list[ast.AST] = []
    for child in ast.iter_child_nodes(node):
        if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda):
            continue
        out.append(child)
        out.extend(own_statements(child))
    return out


def statuses(call: ast.Call) -> list[int]:
    """The HTTP status(es) a response call carries: `status_code=` as a constant, or both arms
    of `a if cond else b`; 200 when it says nothing."""
    for kw in call.keywords:
        if kw.arg != "status_code":
            continue
        if isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, int):
            return [kw.value.value]
        if isinstance(kw.value, ast.IfExp):
            arms = [kw.value.body, kw.value.orelse]
            if all(isinstance(a, ast.Constant) and isinstance(a.value, int) for a in arms):
                return [
                    a.value
                    for a in arms
                    if isinstance(a, ast.Constant) and isinstance(a.value, int)
                ]
    return [200]


def returned(node: ast.Return, scope: Scope) -> tuple[str, dict[str, str], list[int]]:
    """What one `return` sends: the argument of `JSONResponse(...)`, a helper to follow (with
    what its first parameter is bound to), a non-JSON response class, or an unresolved
    expression kept under `?` - and the status code(s) it goes out with."""
    assert node.value is not None
    value = node.value.value if isinstance(node.value, ast.Await) else node.value
    if isinstance(value, ast.Call):
        name = getattr(value.func, "id", None)
        if name == "JSONResponse" and value.args:
            return scope.of(value.args[0]), {}, statuses(value)
        if name in NOT_JSON:
            return f"not JSON:{name}", {}, statuses(value)
        if name == POOL and value.args:
            text = scope.of_callable(value.args[0])
            return text, scope.binding(text, value.args[1:]), [200]
        if name in scope.helpers:
            return f"HELPER:{name}", scope.binding(f"HELPER:{name}", value.args), [200]
    return f"?{ast.unparse(node.value)[:40]}", {}, [200]


@dataclass(frozen=True)
class Arm:
    """One thing a handler can send: a type, the status it goes out with, and the method it is
    reachable under (``None`` when every method of the route reaches it)."""

    status: int
    method: str | None
    type: str


def tagged_blocks(body: list[ast.AST]) -> list[tuple[str, ast.If]]:
    """Every ``if request.method == "M":`` in `body`, with its `M`."""
    out: list[tuple[str, ast.If]] = []
    for node in body:
        if not (isinstance(node, ast.If) and isinstance(node.test, ast.Compare)):
            continue
        test = node.test
        if ast.unparse(test.left) != "request.method" or len(test.comparators) != 1:
            continue
        tag = test.comparators[0]
        if isinstance(tag, ast.Constant) and isinstance(tag.value, str):
            out.append((tag.value, node))
    return out


def returns_in(nodes: Iterable[ast.AST]) -> list[ast.Return]:
    return [n for st in nodes for n in [st, *own_statements(st)] if isinstance(n, ast.Return)]


def reaches(
    handler: ast.FunctionDef | ast.AsyncFunctionDef, methods: tuple[str, ...]
) -> dict[int, tuple[str | None, ...]]:
    """``id(return node) -> the methods that reach it``, from the handler's own shape.

    The six two-method routes all branch on ``if request.method == "M":`` (checked 2026-09-03),
    and three lexical facts decide what a return can be reached by - none of them is branch
    narrowing of a value:

    * a return INSIDE that block belongs to `M`;
    * a return outside it belongs to the route's other methods - and to `M` as well when the
      block does not end in a return (`event_settings` assigns and falls through), or when the
      return sits in an `except` clause whose `try` wraps the block (`everyday_day_settings`);
    * with no declared methods (the root derivation), every return reads as method-less.
    """
    body = own_statements(handler)
    tagged = tagged_blocks(body)
    out: dict[int, tuple[str | None, ...]] = {}
    if not tagged or not methods:
        return out
    inside = {id(r): m for m, node in tagged for r in returns_in(node.body)}
    fall_through = {
        m for m, node in tagged if not isinstance(node.body[-1], ast.Return | ast.Raise)
    }
    rescued: dict[int, set[str]] = {}
    for m, node in tagged:
        for try_ in body:
            if isinstance(try_, ast.Try) and any(n is node for n in own_statements(try_)):
                for r in returns_in(try_.handlers):
                    rescued.setdefault(id(r), set()).add(m)
    named = {m for m, _ in tagged}
    for ret in returns_in(body):
        if id(ret) in inside:
            out[id(ret)] = (inside[id(ret)],)
        else:
            also = fall_through | rescued.get(id(ret), set())
            out[id(ret)] = tuple(m for m in methods if m not in named or m in also)
    return out


def response_types(
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
    follow = Follow(seen, bound or {}, None)
    return {arm.type for arm in response_arms(handler, helpers, typed, follow)}


@dataclass(frozen=True)
class Follow:
    """How a helper was reached: the helpers already on the path, what its first parameter is
    bound to, and the method of the return that reached it."""

    seen: frozenset[str] = frozenset()
    bound: dict[str, str] | None = None
    method: str | None = None
    #: The route's declared methods. With them, a return outside every `if request.method ==`
    #: block belongs to the methods no block names - the other half of :func:`method_of_returns`.
    methods: tuple[str, ...] = ()


def response_arms(
    handler: ast.FunctionDef | ast.AsyncFunctionDef,
    helpers: dict[str, ast.FunctionDef | ast.AsyncFunctionDef],
    typed: dict[str, set[str]],
    follow: Follow | None = None,
) -> set[Arm]:
    """Every :class:`Arm` reachable from this handler - :func:`response_types` with the status
    and the method kept. A followed helper's arms inherit the method of the return that reached
    it. Stage D."""
    follow = follow or Follow()
    scope = Scope(handler, helpers, typed, follow.bound)
    by_return = reaches(handler, follow.methods)
    arms: set[Arm] = set()
    for node in scope.body:
        if not isinstance(node, ast.Return) or node.value is None:
            continue
        text, binding, codes = returned(node, scope)
        reaches_ = by_return.get(id(node), (follow.method,))
        if not text.startswith("HELPER:"):
            arms |= {Arm(code, reach, text) for code in codes for reach in reaches_}
            continue
        name = text.removeprefix("HELPER:")
        for reach in reaches_:
            if name in follow.seen or name == handler.name:
                arms.add(Arm(200, reach, f"?recursive:{name}"))
            else:
                deeper = Follow(follow.seen | {name}, binding, reach)
                arms |= response_arms(helpers[name], helpers, typed, deeper)
    return {arm for arm in arms if arm.type != NEVER}


def response_resolution() -> dict[str, set[str]]:
    """``route -> the types that reach its JSONResponse``, the stage-4b derivation."""
    tree = module(SERVER)
    helpers = functions(tree)
    typed = declared_return_types()
    return {
        path: response_types(helpers[handler], helpers, typed)
        for path, handler in routes(tree)
        if handler in helpers
    }


def modules() -> list[str]:
    service = importlib.import_module("truestill_app.service")
    return [
        "truestill_app.jobs",
        *(f"truestill_app.service.{m.name}" for m in pkgutil.iter_modules(service.__path__)),
    ]


def inventory() -> dict[str, type]:
    """Every TypedDict the app declares, by import - which is what sees the inheriting ones."""
    found: dict[str, type] = {}
    for name in modules():
        module = importlib.import_module(name)
        for attr, obj in vars(module).items():
            if typing.is_typeddict(obj) and obj.__module__ == name:
                assert attr not in found, f"two TypedDicts named {attr}"
                found[attr] = obj
    return found


def frame_roots() -> set[str]:
    """The TypedDicts `jobs.py` binds to an annotated local inside a function: what it writes."""
    declared = {n.name for n in ast.walk(module(JOBS)) if isinstance(n, ast.ClassDef)}
    return {
        ast.unparse(node.annotation)
        for fn in ast.walk(module(JOBS))
        if isinstance(fn, ast.FunctionDef)
        for node in ast.walk(fn)
        if isinstance(node, ast.AnnAssign) and ast.unparse(node.annotation) in declared
    }


def exception_handler_names(tree: ast.Module) -> set[str]:
    """The handler names registered under `exception_handlers={...}` in `create_app`."""
    return {
        ast.unparse(value)
        for node in ast.walk(tree)
        if isinstance(node, ast.keyword)
        and node.arg == "exception_handlers"
        and isinstance(node.value, ast.Dict)
        for value in node.value.values
    }


def exception_handler_roots() -> set[str]:
    """What the handlers in `exception_handlers={...}` send - a response every route can carry
    that no route walk reaches. Found by the derivation, 2026-09-03: `CatalogBusyPayload`."""
    tree = module(SERVER)
    helpers = functions(tree)
    typed = declared_return_types()
    return {
        member
        for name in exception_handler_names(tree)
        if name in helpers
        for text in response_types(helpers[name], helpers, typed)
        for member in union_members(text)
    }


def root_names() -> set[str]:
    responses = {
        member
        for types in response_resolution().values()
        for text in types
        if not text.startswith("not JSON")
        for member in union_members(text)
    }
    summaries = {m for ms in job_summary_types().values() for m in ms}
    return responses | summaries | frame_roots() | exception_handler_roots()


def roots() -> list[type]:
    """The TypedDict classes behind :func:`root_names`, in name order - the emitter's input."""
    declared = inventory()
    missing = sorted(n for n in root_names() if n not in declared)
    if missing:
        msg = f"roots the inventory cannot resolve: {missing}"
        raise LookupError(msg)
    return [declared[n] for n in sorted(root_names())]
