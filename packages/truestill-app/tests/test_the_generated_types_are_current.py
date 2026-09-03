"""`api.d.ts` is regenerated from `openapi.json` here, whole, and any difference is red. `(ahn)` stage E

**The gain over a header hash, and why the emitter is Python** (P199): a hash in the header
catches a stale spec and not a hand edit that leaves the header alone. Regenerating the whole
file catches both, and it can run in every lane because `scripts/emit_api_types.py` needs no
Node - the TypeScript 7 package ships no compiler API, so `openapi-typescript` cannot run in
this tree at all.

**The emitter is accepted against the field's tool, not against intent**: the frozen pair under
`fixtures/contract-oracle/` is `openapi-typescript` 7.13.0's rendering of the spec of
2026-09-03, and the emitter must reproduce it byte for byte below the header.

**The two probes P198 ran under `tsc`**, kept here without Node: the generated union names the
field the island's payload has (`organized`) and not the one `app.js` adds on the way
(`cancelled`); and `main.tsx` imports the generated type where the cast was.

**Cost, declared rather than suppressed** (`ENGINEERING_STANDARD.md` §4): one JSON parse and one
string render, milliseconds, in `make check`.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))

import emit_api_types

ORACLE = Path(__file__).resolve().parent / "fixtures/contract-oracle"
MAIN_TSX = emit_api_types.ROOT / "packages/truestill-app/frontend/src/main.tsx"


def _below_header(text: str) -> str:
    """Everything after the first `/** ... */` block - the oracle's and the emitter's differ."""
    return text.split("*/\n", 1)[1].lstrip("\n")


def test_the_committed_types_equal_what_the_spec_renders() -> None:
    committed = emit_api_types.TYPES.read_text(encoding="utf-8")
    assert committed == emit_api_types.generate(), (
        f"{emit_api_types.TYPES.name} differs from what {emit_api_types.SPEC.name} renders - a hand "
        "edit, or a spec change without regeneration. Run: "
        "uv run python scripts/emit_api_types.py --write"
    )
    digest = re.search(r"Spec sha256: ([0-9a-f]{64})", committed)
    assert digest is not None, "the header carries no spec hash"


def test_the_emitter_reproduces_the_oracle_byte_for_byte() -> None:
    spec = json.loads((ORACLE / "openapi.json").read_text(encoding="utf-8"))
    oracle = _below_header((ORACLE / "api.d.ts").read_text(encoding="utf-8"))
    mine = emit_api_types.body(spec)
    assert mine == oracle, "the emitter and openapi-typescript 7.13.0 disagree on the frozen spec"
    assert len(oracle.splitlines()) >= 3700, (
        "the oracle shrank; the fixture is not the 3,793-line record"
    )


def test_a_construct_the_oracle_never_saw_is_refused_not_guessed() -> None:
    for schema in (
        {"allOf": [{"type": "string"}]},
        {"prefixItems": [{"type": "number"}]},
        {"type": ["string", "null"]},
    ):
        with pytest.raises(emit_api_types.UnrenderableError):
            emit_api_types.type_of(schema, 0, "probe")


def test_the_islands_payload_type_names_what_the_wire_carries() -> None:
    """P198's probes, without a compiler: `organized` is a field, `cancelled` is not, anywhere."""
    types = emit_api_types.TYPES.read_text(encoding="utf-8")
    for name in ("OrganizeDoneSummary", "CompletionBase"):
        block = types.split(f"        {name}: {{", 1)[1].split("\n        };", 1)[0]
        assert "organized: number;" in block, f"{name} lost `organized`"
    assert "cancelled" not in types, (
        "`cancelled` entered the contract; app.js adds it, the wire never sends it"
    )
    main = MAIN_TSX.read_text(encoding="utf-8")
    assert "type OrganizeSummary = Record<string, unknown>" not in main, "the cast is back"
    assert "type OrganizeSummary =\n  | components" in main, (
        "the alias no longer names the generated type"
    )
    assert 'components["schemas"]["OrganizeDoneSummary"]' in main
    assert 'import type { components } from "./generated/api";' in main


def test_the_digest_is_a_fact_about_the_spec_not_about_git(tmp_path: Path) -> None:
    """The Windows lane checks the spec out with CRLF; the rendered file must not change."""
    crlf = tmp_path / "openapi.json"
    crlf.write_bytes(
        emit_api_types.SPEC.read_text(encoding="utf-8").replace("\n", "\r\n").encode("utf-8")
    )
    assert crlf.read_bytes() != emit_api_types.SPEC.read_bytes(), (
        "the CRLF copy is not a different file"
    )
    assert emit_api_types.generate(crlf) == emit_api_types.generate()
