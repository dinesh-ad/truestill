"""The payload contract's components, from the TypedDicts the wire reaches. `(ahn)` stage C.

⚠ **DO NOT EMIT FROM THE INVENTORY.** This module takes ROOTS - the TypedDicts the route
resolver and the stream census say the server actually sends - and emits the closure of those and
nothing else. There is deliberately no function here that enumerates every TypedDict in the tree.
Measured 2026-09-02 (P193): emitting from the inventory put **seven dataclasses**
(`ReviewCard`, `TripProposal`, `EventItem`, ...) and `EventProposalSuccessPayload` into the spec,
describing nothing the server sends - they are internal session objects whose wire shape is
`ReviewCardsPayload`. Whoever extends this file meets the rule here or repeats that.

**msgspec is a schema emitter here, not a model layer.** `packages/truestill-app/pyproject.toml`
refuses Pydantic *for our models*; this defines no model, validates nothing, and runs at build
time only. It is in the root `[dependency-groups] dev` and the app never imports it.

**What msgspec cannot express, and what is done about each** - the rebuild pass, `_lower`:

* `Literal[True]` / `Literal[False]`, the project's discriminator tag: msgspec's schema generator
  refuses a boolean literal (*"Literal may only contain None/integers/strings"*). Lowered to
  `Annotated[bool, Meta(extra_json_schema={"const": ...})]`, which emits the same `const`.
* `NotRequired` under `from __future__ import annotations` on 3.14: a TypedDict's own
  `__optional_keys__` is EMPTY, so msgspec would mark every optional field required and say
  nothing. Every TypedDict is rebuilt from `get_type_hints(include_extras=True)`, where the
  wrapper is visible; the guard checks the result against the AST.
* a bare `object` field: refused by msgspec as a custom type. Allowed at exactly one field,
  :data:`OBJECT_FIELDS`, lowered to `Any` (an empty schema) - `DoneFrame.summary`, whose union
  stage D emits as a `oneOf` from the factories' annotations. Anywhere else it is a refusal.
* a dataclass reached through a field: **refused**, by name. A dataclass is never a wire shape
  here; meeting one means a root is an internal object, not a payload.
* a union of two TypedDicts inside a field: msgspec refuses it (*"may not contain more than one
  TypedDict"*). None exists today; if one appears it is refused with the field named, and the
  route-level unions are stage D's `oneOf`, never msgspec's.
"""

from __future__ import annotations

import dataclasses
import types
import typing
from collections.abc import Iterable
from typing import Annotated, Any, Literal, NotRequired, Required, get_args, get_origin

import msgspec
from msgspec import Meta

#: Where `$ref`s point - OpenAPI 3.1's component path rather than msgspec's `$defs`.
REF_TEMPLATE = "#/components/schemas/{name}"

#: The one place a field may be `object`: `DoneFrame.summary`, whose real type is the union of
#: the job factories' `T`, discharged at `JobManager.start` and re-derived by stage D.
OBJECT_FIELDS: frozenset[tuple[str, str]] = frozenset({("DoneFrame", "summary")})


class RefusedError(ValueError):
    """A type the contract cannot express, named with the field it sits on."""

    def __init__(self, owner: str, field: str, reason: str) -> None:
        super().__init__(f"{owner}.{field}: {reason}")


def _rebuilt(td: type, memo: dict[type, type]) -> type:
    """`td` rebuilt with every annotation lowered, so msgspec sees what the source says."""
    if td in memo:
        return memo[td]
    fields: dict[str, object] = {}
    for name, hint in typing.get_type_hints(td, include_extras=True).items():
        fields[name] = _lower(hint, memo, owner=td.__name__, field=name)
    # Functional-syntax construction is the only way to build a TypedDict from data; mypy has no
    # static view of it and says so.
    new = typing.TypedDict(td.__name__, fields, total=td.__total__)  # type: ignore[misc]
    new.__doc__ = ""
    memo[td] = new
    return new


def _lower(tp: Any, memo: dict[type, type], *, owner: str, field: str) -> Any:  # noqa: PLR0911 - one branch per type family, each named in the module docstring
    """One annotation, lowered for msgspec, or :class:`RefusedError` naming the field."""
    origin, args = get_origin(tp), get_args(tp)
    if typing.is_typeddict(tp):
        return _rebuilt(tp, memo)
    if dataclasses.is_dataclass(tp):
        shape = getattr(tp, "__name__", repr(tp))
        raise RefusedError(owner, field, f"{shape} is a dataclass, not a wire shape")
    if tp is object:
        if (owner, field) in OBJECT_FIELDS:
            return Any
        raise RefusedError(owner, field, "a bare `object` says nothing; give it a type")
    if origin is Literal:
        if args and all(isinstance(v, bool) for v in args):
            if len(args) == 1:
                return Annotated[bool, Meta(extra_json_schema={"const": args[0]})]
            return bool
        return tp
    if origin in (NotRequired, Required):
        return origin[_lower(args[0], memo, owner=owner, field=field)]
    if origin is Annotated:
        return Annotated[(_lower(args[0], memo, owner=owner, field=field), *args[1:])]
    if origin in (typing.Union, types.UnionType):
        members = [_lower(a, memo, owner=owner, field=field) for a in args]
        if sum(typing.is_typeddict(m) for m in members) > 1:
            raise RefusedError(
                owner, field, "a union of two TypedDicts inside a field; msgspec cannot express it"
            )
        return typing.Union[tuple(members)]  # noqa: UP007 - built from a tuple, not spelled
    if origin is not None and args:
        return origin[tuple(_lower(a, memo, owner=owner, field=field) for a in args)]
    return tp


def components(roots: Iterable[type]) -> dict[str, dict[str, Any]]:
    """`name -> JSON Schema` for every TypedDict reachable from `roots`, and nothing else.

    `roots` come from the caller - the route resolver's closure and the frames the stream writes.
    They are never the inventory; see the module docstring.
    """
    memo: dict[type, type] = {}
    rebuilt = [_rebuilt(root, memo) for root in roots]
    _, schemas = msgspec.json.schema_components(rebuilt, ref_template=REF_TEMPLATE)
    return dict(sorted(schemas.items()))


def empty_schemas(schemas: dict[str, dict[str, Any]]) -> list[str]:
    """Every `name.field` whose schema is `{}` - says-anything - so the caller can refuse all but
    :data:`OBJECT_FIELDS`."""
    return [
        f"{name}.{field}"
        for name, schema in schemas.items()
        for field, sub in schema.get("properties", {}).items()
        if sub == {}
    ]


# --- the document: the join, stage D -------------------------------------------------------

import argparse
import json
import sys
import tomllib

import payload_contract as pc

#: Where the committed spec lives. Regenerate with `uv run python scripts/emit_openapi.py --write`;
#: `--check` (the default) exits 1 when the tree and the file disagree, and
#: `test_the_committed_spec_is_current.py` asserts the same in `make check`.
SPEC = pc.ROOT / "packages/truestill-app/openapi.json"
EVENTS_ROUTE = "/api/jobs/{job_id}/events"
#: Non-JSON response classes and what they put on the wire; `Response` carries no body worth a
#: content type, and `StreamingResponse` is the event stream, handled by name.
NON_JSON_CONTENT = {"HTMLResponse": "text/html", "PlainTextResponse": "text/plain"}


def ref(name: str) -> dict[str, str]:
    return {"$ref": REF_TEMPLATE.format(name=name)}


def tag_of(names: list[str], schemas: dict[str, dict[str, Any]]) -> tuple[str, str] | None:
    """A property every member carries with a single fixed value, distinct per member -
    ``(property, "string" | "boolean")`` - or ``None`` when the union has no such property.

    OpenAPI's `discriminator` requires a STRING property, so a boolean tag (`ok: true/false`) is
    reported but not emitted as one; TypeScript narrows on a boolean literal without it.
    """
    if len(names) < 2:
        return None
    shared = set.intersection(*(set(schemas[n].get("required", [])) for n in names))
    for prop in sorted(shared):
        values: list[object] = []
        for n in names:
            sub = schemas[n]["properties"][prop]
            if "const" in sub:
                values.append(sub["const"])
            elif isinstance(sub.get("enum"), list) and len(sub["enum"]) == 1:
                values.append(sub["enum"][0])
            else:
                break
        else:
            if len(set(map(repr, values))) == len(values):
                kind = "boolean" if all(isinstance(v, bool) for v in values) else "string"
                return prop, kind
    return None


def schema_for(names: list[str], schemas: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """One `$ref`, or a `oneOf` of them with a `discriminator` when a string tag exists.

    ⚠ **`oneOf`, never `anyOf`, and every arm of a status in ONE schema.** Two responses on the
    same status and content type overwrite each other silently (oaswrap#44); the union is the
    only shape that keeps every arm, and `anyOf` degrades to a loose type in generators.
    """
    if len(names) == 1:
        return ref(names[0])
    out: dict[str, Any] = {"oneOf": [ref(n) for n in names]}
    tag = tag_of(names, schemas)
    if tag is not None and tag[1] == "string":
        prop = tag[0]
        mapping = {}
        for n in names:
            sub = schemas[n]["properties"][prop]
            mapping[str(sub["const"] if "const" in sub else sub["enum"][0])] = ref(n)["$ref"]
        out["discriminator"] = {"propertyName": prop, "mapping": mapping}
    return out


def responses_for(
    arms: set[pc.Arm],
    method: str,
    extra: set[pc.Arm],
    schemas: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """The `responses` object of one operation: every arm this method reaches, grouped by status,
    each status's JSON arms as one schema, plus the arms every route carries (`extra`)."""
    mine = {a for a in arms if a.method in (None, method)} | extra
    out: dict[str, dict[str, Any]] = {}
    for status in sorted({a.status for a in mine}):
        at = [a for a in mine if a.status == status]
        json_names = sorted(
            {m for a in at if not a.type.startswith("not JSON") for m in pc.union_members(a.type)}
        )
        plain = sorted(
            {a.type.removeprefix("not JSON:") for a in at if a.type.startswith("not JSON")}
        )
        content: dict[str, Any] = {}
        if json_names:
            content["application/json"] = {"schema": schema_for(json_names, schemas)}
        for cls in plain:
            if cls in NON_JSON_CONTENT:
                content[NON_JSON_CONTENT[cls]] = {"schema": {"type": "string"}}
        described = json_names + [f"{cls} (no JSON body)" for cls in plain]
        response: dict[str, Any] = {"description": " | ".join(described)}
        if content:
            response["content"] = content
        out[str(status)] = response
    return out


def path_parameters(path: str) -> list[dict[str, Any]]:
    return [
        {"name": name, "in": "path", "required": True, "schema": {"type": "string"}}
        for name in (
            seg[1:-1] for seg in path.split("/") if seg.startswith("{") and seg.endswith("}")
        )
    ]


def document() -> dict[str, Any]:
    """The whole OpenAPI 3.1 document, from the derivations and the components - deterministic:
    key order sorted at dump time, nothing dated, no path outside the routes'."""
    tree = pc.module(pc.SERVER)
    helpers = pc.functions(tree)
    typed = pc.declared_return_types()
    schemas = components(pc.roots())
    # Q1273 - `DoneFrame.summary` is the union of the factories' `T`, derived, never listed.
    summaries = sorted({m for ms in pc.job_summary_types().values() for m in ms})
    schemas["DoneFrame"]["properties"]["summary"] = schema_for(summaries, schemas)
    # The refusal every route can carry, from `exception_handlers={...}`: its own status, on every operation.
    carried = {
        pc.Arm(arm.status, None, arm.type)
        for name in pc.exception_handler_names(tree)
        if name in helpers
        for arm in pc.response_arms(helpers[name], helpers, typed)
    }
    paths: dict[str, dict[str, Any]] = {}
    for path, handler, methods in pc.routes_with_methods(tree):
        arms = pc.response_arms(helpers[handler], helpers, typed, pc.Follow(methods=tuple(methods)))
        item: dict[str, Any] = {}
        for method in methods:
            operation: dict[str, Any] = {
                "operationId": handler if len(methods) == 1 else f"{handler}_{method.lower()}",
                "responses": responses_for(arms, method, carried, schemas),
            }
            if path == EVENTS_ROUTE:
                # SSE is not native in 3.1 (`itemSchema` is 3.2): the 3.1 shape is the
                # per-event schema under `text/event-stream`, which Schemathesis reads.
                frames = sorted(pc.frame_roots())
                operation["responses"]["200"] = {
                    "description": "one frame per event: " + " | ".join(frames),
                    "content": {"text/event-stream": {"schema": schema_for(frames, schemas)}},
                }
            if parameters := path_parameters(path):
                operation["parameters"] = parameters
            item[method.lower()] = operation
        paths[path] = item
    version = tomllib.loads(
        (pc.ROOT / "packages/truestill-app/pyproject.toml").read_text(encoding="utf-8")
    )["project"]["version"]
    return {
        "openapi": "3.1.0",
        "info": {"title": "Truestill app", "version": version},
        "paths": paths,
        "components": {"schemas": schemas},
    }


def render() -> str:
    """The committed bytes: sorted keys, two-space indent, one trailing newline."""
    return json.dumps(document(), indent=2, sort_keys=True) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument(
        "--write", action="store_true", help=f"write {SPEC.relative_to(pc.ROOT).as_posix()}"
    )
    args = parser.parse_args(argv)
    text = render()
    if args.write:
        SPEC.write_text(text, encoding="utf-8")
        print(f"wrote {SPEC.relative_to(pc.ROOT).as_posix()}")
        return 0
    if SPEC.exists() and SPEC.read_text(encoding="utf-8") == text:
        print(f"{SPEC.relative_to(pc.ROOT).as_posix()} is current")
        return 0
    print(
        f"{SPEC.relative_to(pc.ROOT).as_posix()} is stale; run: uv run python scripts/emit_openapi.py --write"
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
