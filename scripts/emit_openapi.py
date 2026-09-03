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
