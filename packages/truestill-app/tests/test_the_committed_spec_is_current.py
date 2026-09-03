"""`openapi.json` is committed, and `make check` is red the moment the tree disagrees with it. `(ahn)` stage D

**The airbyte pattern** (`airbytehq/airbyte-python-cdk#751`): the spec is generated from the
code, committed beside it, and CI fails when the committed file is stale - so a TypedDict edit
that was not committed with its spec is caught here, in Python, with no Node on the machine.
`scripts/emit_openapi.py --write` regenerates it.

**What else is asserted, each into the derivation rather than into a table:**

* every arm the resolver derives for a route is in the document under its status and method -
  the same-status collision (oaswrap#44: *"the second silently overwrites the first"*) cannot lose
  one, because every status's JSON arms are ONE `oneOf`;
* `DoneFrame.summary` is the `oneOf` of the factories' summaries, derived (Q1273);
* the event stream is `text/event-stream` with the four frames as one `oneOf` (Q1270);
* the emitter is deterministic: two renders agree, nothing dated, no absolute path;
* the discriminator census (Q1268) is printed and pinned: which unions carry a string tag, a
  boolean tag, or none.

**Cost, declared rather than suppressed** (`ENGINEERING_STANDARD.md` §4): one emission (imports
the app, walks `server.py` once, msgspec over the closure), well under a second, in `make check`.
"""

from __future__ import annotations

import functools
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))

import emit_openapi
import payload_contract as pc

#: Derived 2026-09-03 (P197): operations whose 200 is a union. A floor just under it.
MEASURED_UNION_OPERATIONS = 38


@functools.cache
def _document() -> dict[str, object]:
    return emit_openapi.document()


def _refs(schema: object) -> set[str]:
    if isinstance(schema, dict):
        if "$ref" in schema:
            return {str(schema["$ref"]).rsplit("/", 1)[1]}
        return set().union(*(_refs(v) for v in schema.values()))
    if isinstance(schema, list):
        return set().union(*(_refs(v) for v in schema))
    return set()


def test_the_committed_spec_equals_what_the_tree_emits() -> None:
    committed = emit_openapi.SPEC.read_text(encoding="utf-8")
    assert committed == emit_openapi.render(), (
        f"{emit_openapi.SPEC.name} is stale against the tree. Run: "
        "uv run python scripts/emit_openapi.py --write - and commit the spec with the change."
    )


def test_the_emitter_is_deterministic() -> None:
    first, second = emit_openapi.render(), emit_openapi.render()
    assert first == second, "two renders of the same tree differ"
    assert str(pc.ROOT) not in first, "an absolute path leaked into the spec"
    for word in ("generated", "timestamp", "date-time"):
        assert word not in first, f"{word!r} in the spec: something dated is being emitted"
    assert first.endswith("}\n")


def test_no_route_loses_an_arm_to_the_same_status() -> None:
    """Loop the DERIVED arms; assert into the document. oaswrap#44's bug, refused."""
    doc = _document()
    paths = doc["paths"]
    assert isinstance(paths, dict)
    tree = pc.module(pc.SERVER)
    helpers, typed = pc.functions(tree), pc.declared_return_types()
    checked = 0
    for path, handler, methods in pc.routes_with_methods(tree):
        for arm in pc.response_arms(
            helpers[handler], helpers, typed, pc.Follow(methods=tuple(methods))
        ):
            if arm.type.startswith("not JSON") or path == emit_openapi.EVENTS_ROUTE:
                continue
            for method in methods:
                if arm.method not in (None, method):
                    continue
                response = paths[path][method.lower()]["responses"][str(arm.status)]
                present = _refs(response["content"]["application/json"]["schema"])
                for member in pc.union_members(arm.type):
                    assert member in present, f"{method} {path} {arm.status} lost {member}"
                    checked += 1
    assert checked >= 100, (
        f"only {checked} arms checked; the derivation is looking at the wrong tree"
    )
    text = json.dumps(doc)
    assert '"anyOf"' not in json.dumps(doc["paths"]), "a response uses anyOf; oneOf is the ruling"
    unions = sum(
        1
        for p in paths.values()
        for op in p.values()
        if "oneOf" in json.dumps(op["responses"].get("200", {}))
    )
    assert unions >= MEASURED_UNION_OPERATIONS - 3, f"union operations fell to {unions}"
    print(f"union operations on 200: {unions} | arms checked: {checked} | bytes: {len(text)}")


def test_done_frame_summary_is_the_derived_union() -> None:
    doc = _document()
    schemas = doc["components"]["schemas"]  # type: ignore[index]
    summary = schemas["DoneFrame"]["properties"]["summary"]
    derived = {m for ms in pc.job_summary_types().values() for m in ms}
    assert _refs(summary) == derived, sorted(_refs(summary) ^ derived)
    assert len(derived) >= 12
    assert not emit_openapi.empty_schemas(schemas), "an empty schema survived into the document"


def test_the_event_stream_is_one_union_of_the_frames() -> None:
    doc = _document()
    op = doc["paths"][emit_openapi.EVENTS_ROUTE]["get"]  # type: ignore[index]
    content = op["responses"]["200"]["content"]
    assert list(content) == ["text/event-stream"], content.keys()
    assert _refs(content["text/event-stream"]["schema"]) == pc.frame_roots()
    assert len(pc.frame_roots()) == 4
    # Every route carries the exception handler's refusal at its own status.
    assert doc["paths"]["/api/library/stats"]["get"]["responses"]["503"]["content"][
        "application/json"
    ]["schema"] == {  # type: ignore[index]
        "$ref": "#/components/schemas/CatalogBusyPayload"
    }


def test_which_unions_can_be_discriminated_is_derived_and_said() -> None:
    """Q1268. A discriminator needs a fixed-value property in EVERY member; the job envelope's
    `JobStarted` is `{"job_id"}` and has none, so the envelope is a bare `oneOf` and this test
    says so rather than letting it be discovered."""
    doc = _document()
    schemas = doc["components"]["schemas"]  # type: ignore[index]
    census: dict[str, list[str]] = {"string": [], "boolean": [], "none": []}
    seen: set[tuple[str, ...]] = set()
    for path, item in doc["paths"].items():  # type: ignore[union-attr]
        for op in item.values():
            for status, response in op["responses"].items():
                for body in response.get("content", {}).values():
                    schema = body["schema"]
                    if "oneOf" not in schema:
                        continue
                    members = tuple(sorted(_refs(schema)))
                    if members in seen:
                        continue
                    seen.add(members)
                    tag = emit_openapi.tag_of(list(members), schemas)
                    census[tag[1] if tag else "none"].append(
                        f"{path} {status}: {' | '.join(members)}" + (f" [{tag[0]}]" if tag else "")
                    )
                    assert ("discriminator" in schema) == (
                        tag is not None and tag[1] == "string"
                    ), path
    for kind, rows in census.items():
        print(f"{kind}: {len(rows)}")
        for row in rows:
            print("   ", row)
    envelope = tuple(sorted({"DriveBusyPayload", "JobStarted"}))
    assert envelope in seen
    assert emit_openapi.tag_of(list(envelope), schemas) is None, (
        "JobStarted grew a tag; re-rule Q1268"
    )
    assert census["none"], "every union discriminable - the envelope should not be"
