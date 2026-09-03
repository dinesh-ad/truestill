"""The contract's components are the closure of what the wire reaches, derived and pinned. `(ahn)` stage C

**Roots are derived, never listed.** Three sources, each already mechanical: the route resolver's
closure (`payload_contract.response_resolution`, stage A), the frames `jobs.py` binds to an annotated local and
writes to the stream (stage B), and the job summaries the thirteen factories declare
(`payload_contract.job_summary_types`). The emitter, `scripts/emit_openapi.py`, takes those roots and nothing
else; its own docstring carries the rule and this file proves it bites - a root that is an
internal session object is REFUSED, by the dataclass it reaches.

**The count is derived here, and this is where the floor lives.** `(ahn)` carried *117
TypedDicts* until P193, stale three ways; now :data:`MEASURED_COMPONENTS` is read from
`test_the_count_is_derived_and_pinned` and sits just under the derivation.

**Cost, declared rather than suppressed** (`ENGINEERING_STANDARD.md` §4): one import of the app's
service modules, one AST pass over them for `NotRequired`, and one msgspec emission - well under a
second, in `make check`. msgspec is imported here and by the emitter only: a build-time dependency,
never the app's.
"""

from __future__ import annotations

import ast
import dataclasses
import functools
import sys
import typing
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))

import emit_openapi
import payload_contract as pc

ROOT = Path(__file__).resolve().parents[3]
JOBS = ROOT / "packages/truestill-app/src/truestill_app/jobs.py"
CORE_BAKE = ROOT / "packages/truestill-core/src/truestill_core/bake.py"

#: Derived 2026-09-03 (P196): the closure the wire reaches. A floor just under it; the inventory
#: (every TypedDict by import) is larger, and the gap is the point.
MEASURED_COMPONENTS = 128


@functools.cache
def _components() -> dict[str, dict[str, typing.Any]]:
    return emit_openapi.components(pc.roots())


def _not_required_fields() -> set[tuple[str, str]]:
    """Every `(TypedDict, field)` declared `NotRequired`, read from the AST - the runtime view is
    empty under deferred annotations, which is the defect the rebuild pass exists for."""
    out: set[tuple[str, str]] = set()
    for path in [*sorted(pc.SERVICE.glob("*.py")), JOBS, CORE_BAKE]:
        for node in ast.walk(pc.module(path)):
            if isinstance(node, ast.ClassDef):
                for st in node.body:
                    if isinstance(st, ast.AnnAssign) and "NotRequired" in ast.unparse(
                        st.annotation
                    ):
                        out.add((node.name, ast.unparse(st.target)))
    return out


def test_the_count_is_derived_and_pinned() -> None:
    """The number `(ahn)` stopped carrying, produced here and floored just under."""
    schemas = _components()
    inventory = pc.inventory()
    print(
        f"components: {len(schemas)} | inventory: {len(inventory)} | roots: {len(pc.root_names())}"
    )
    assert len(schemas) >= MEASURED_COMPONENTS - 5, f"components fell to {len(schemas)}"
    assert len(pc.root_names()) >= 40, (
        "the roots collapsed; a derivation is looking at the wrong tree"
    )
    assert set(schemas) < set(inventory) | {"DriveAwaiting", "BakeDriveLine"}, (
        "the closure is not a strict subset of the inventory - is something emitting from it?"
    )


def test_the_inventory_is_not_emitted() -> None:
    """The rule in the emitter's own text, proved: an internal session object is refused by the
    dataclass it reaches, and neither it nor the dataclass is in the output."""
    schemas = _components()
    for name in (
        "EventProposalSuccessPayload",
        "MergeReviewCardsResult",
        "ReviewCard",
        "TripProposal",
    ):
        assert name not in schemas, f"{name} describes nothing the server sends"
    inventory = pc.inventory()
    with pytest.raises(emit_openapi.RefusedError, match="ReviewCard is a dataclass"):
        emit_openapi.components([inventory["EventProposalSuccessPayload"]])
    assert not any(dataclasses.is_dataclass(t) for t in pc.roots())


def test_what_msgspec_cannot_express_is_lowered_or_refused() -> None:
    schemas = _components()
    # NotRequired: read from the AST, never from `__optional_keys__`, and never emitted required.
    wrong = sorted(
        f"{td}.{field}"
        for td, field in _not_required_fields()
        if td in schemas and field in schemas[td].get("required", [])
    )
    assert not wrong, f"NotRequired fields emitted as required: {wrong}"
    assert sum(1 for td, _ in _not_required_fields() if td in schemas) >= 15, (
        "the NotRequired census is too small to prove anything"
    )
    # The boolean tag survives as a const.
    consts = [
        f"{name}.{field}"
        for name, schema in schemas.items()
        for field, sub in schema.get("properties", {}).items()
        if "const" in sub
    ]
    assert len(consts) >= 30, f"only {len(consts)} boolean tags survived: {consts}"
    assert schemas["DriveBusyPayload"]["properties"]["ok"] == {"type": "boolean", "const": False}
    # `object` is allowed at exactly one field, and it is the one stage D fills.
    assert emit_openapi.empty_schemas(schemas) == ["DoneFrame.summary"]


def test_the_inheriting_typeddicts_are_found_and_flattened() -> None:
    """`_declared`'s `"TypedDict" in base` test misses these three; import does not, and msgspec
    flattens the parent's keys into the child."""
    schemas = _components()
    child, parent = schemas["OrganizeDoneSummary"], schemas["CompletionBase"]
    assert set(parent["properties"]) < set(child["properties"])
    assert "FsCreateOk" in schemas
    assert set(schemas["FsValidateResolved"]["properties"]) < set(
        schemas["FsCreateOk"]["properties"]
    )


def test_the_frames_and_the_envelope_are_components() -> None:
    """Stage B's four frames appear although no route returns them, and stage A's envelope
    members appear because routes do."""
    schemas = _components()
    assert pc.frame_roots() == {"ProgressFrame", "DoneFrame", "ErrorFrame", "UnknownJobFrame"}
    assert pc.frame_roots() <= set(schemas)
    assert {"JobStarted", "DriveBusyPayload", "DriveUnavailablePayload", "BakeRefusal"} <= set(
        schemas
    )
    assert schemas["ProgressFrame"]["properties"]["type"] == {"enum": ["progress"]}
    # The one response no route returns and every route can carry: the exception handler's.
    assert pc.exception_handler_roots() == {"CatalogBusyPayload"}
    assert "CatalogBusyPayload" in schemas


def test_every_ref_resolves_inside_the_components() -> None:
    schemas = _components()
    refs: set[str] = set()

    def walk(obj: object) -> None:
        if isinstance(obj, dict):
            if "$ref" in obj:
                refs.add(str(obj["$ref"]))
            for v in obj.values():
                walk(v)
        elif isinstance(obj, list):
            for v in obj:
                walk(v)

    walk(schemas)
    prefix = emit_openapi.REF_TEMPLATE.split("{")[0]
    dangling = sorted(
        r for r in refs if not r.startswith(prefix) or r[len(prefix) :] not in schemas
    )
    assert refs, "no $ref at all; nesting vanished"
    assert not dangling, dangling
