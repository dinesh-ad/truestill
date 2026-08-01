"""The binding contract must state the schema version and the migrations the code actually has.

**The drift this closes.** `IMPLEMENTATION_STANDARDS.md` §3 is the *binding* contract - `CLAUDE.md`
says it wins on any conflict with another doc or with a code comment - and it had fallen two
versions behind. It read `CURRENT_SCHEMA_VERSION = 15` while `catalog.py` was on **16**, and its
migration ledger enumerated v2 to v11, then v14, v13, v12, **never reaching v15 or v16**. A reader
resolving a conflict in the document's favour would have been resolving it toward a schema that
has not existed since v15 shipped.

**Why two halves, and why the second is the one that matters.** The version line is a single
number and drifts loudly. The ledger drifts *quietly*: v15 was missing while the version line was
still only one behind, so a version-only check would have passed over it. The ledger is also the
half a reader actually uses - it is where "what does v11 mean" is answered - so a gap there is a
question the contract silently cannot answer.

**Measured scope** (`ENGINEERING_STANDARD.md` §4 - a guard is scoped against the real file, not
against a plausible one). Against the contract as it stood before this test landed:

=========================================  ===================
tree state                                 half 2 reports
=========================================  ===================
before the fix (contract at v15, ledger)   **v15, v16 missing**
after the fix                              **nothing missing**
=========================================  ===================

Half 1 was red for the same reason at the same moment: 15 != 16.

**Shape.** `test_dependency_floors.py` established the pattern in this package - reach
`parents[3]` for a repo-root file, compare it against what the code declares, and carry
anti-vacuity guards on both sides so a parser that silently matches nothing cannot report green.
This is the same rule applied to the schema instead of the dependency floors, and it is the
industry-standard shape for a documented constant (Rust's `version-sync` asserts a document
contains the current version by regex; scikit-learn's `assert_docstring_consistency` does the
same for prose).

`_MIGRATIONS` is imported despite the leading underscore for the same reason `test_organizer.py`
imports `_STATUS_LABELS`: it *is* the subject under test, and reading it through a public facade
would put a second thing between the guard and the thing it guards (§4 - a guard must be aimed at
what it guards).
"""

from __future__ import annotations

import re
from pathlib import Path

from truestill_core.catalog import _MIGRATIONS, CURRENT_SCHEMA_VERSION

_CONTRACT = Path(__file__).resolve().parents[3] / "docs" / "IMPLEMENTATION_STANDARDS.md"

#: The §3 sentence that names the version. One occurrence is expected; see the anti-vacuity
#: assertion, which is the whole reason this is `findall` rather than `search`.
_DOCUMENTED_VERSION = re.compile(r"CURRENT_SCHEMA_VERSION = (\d+)")

#: §3's ledger bullet, located by its own heading rather than by line number, which drifts.
_LEDGER_HEAD = "- **Migration ledger:**"

#: Markdown bullets at the section's top level. The ledger ends where the next one begins.
_TOP_LEVEL_BULLET = "- **"


def _contract_text() -> str:
    return _CONTRACT.read_text(encoding="utf-8")


def _ledger_block() -> str:
    """§3's migration-ledger bullet, from its heading to the next top-level bullet."""
    lines = _contract_text().splitlines()
    starts = [i for i, line in enumerate(lines) if line.startswith(_LEDGER_HEAD)]
    if len(starts) != 1:
        return ""  # not located; the anti-vacuity assertion below turns this into a failure
    start = starts[0]
    end = next(
        (i for i in range(start + 1, len(lines)) if lines[i].startswith(_TOP_LEVEL_BULLET)),
        len(lines),
    )
    return "\n".join(lines[start:end])


def _versions_missing_from_the_ledger() -> list[int]:
    ledger = _ledger_block()
    return [version for version, _fn in _MIGRATIONS if not re.search(rf"\bv{version}\b", ledger)]


def test_the_contract_states_the_schema_version_the_code_is_on() -> None:
    """Half 1: §3's version line equals the constant."""
    documented = _DOCUMENTED_VERSION.findall(_contract_text())

    # Anti-vacuity, and the reason for `findall`: a doc edit that reworded or dropped the
    # sentence would leave `search` returning None and a laxer assertion passing on nothing.
    assert len(documented) == 1, (
        f"expected exactly one `CURRENT_SCHEMA_VERSION = N` in {_CONTRACT.name}, "
        f"found {len(documented)}: {documented}. The guard reads that sentence; if it moved or "
        "was reworded, this check is no longer looking at anything."
    )

    assert int(documented[0]) == CURRENT_SCHEMA_VERSION, (
        f"{_CONTRACT.name} §3 says the schema is at v{documented[0]}; the code is at "
        f"v{CURRENT_SCHEMA_VERSION}. The contract wins on conflict, so a stale number here is "
        "worse than no number - update §3 in the same commit as the migration."
    )


def test_every_migration_appears_in_the_contract_ledger() -> None:
    """Half 2: every entry in `_MIGRATIONS` is described in §3's ledger."""
    assert _MIGRATIONS, "no migrations found; this guard would be vacuous"

    ledger = _ledger_block()
    assert ledger, (
        f"could not locate exactly one {_LEDGER_HEAD!r} bullet in {_CONTRACT.name}. Without it "
        "every version below would read as missing, or as present in an empty string - either "
        "way the result would be noise rather than a finding."
    )

    missing = _versions_missing_from_the_ledger()
    assert not missing, (
        "§3's migration ledger does not describe "
        + ", ".join(f"v{version}" for version in missing)
        + ".\n\nA ledger that stops short is the quiet half of this drift: the version line is "
        "one number and is noticed, while a missing ledger entry just leaves a question the "
        "contract cannot answer. Add the entry - with what it adds and why - in the same commit "
        "as the migration."
    )


def test_the_ledger_check_discriminates() -> None:
    """The guard aimed at itself: the token search must find what is there and miss what is not.

    A `v{n}` search is one word boundary away from answering `v1` with `v11`, which would make
    the check report success for an entry nobody wrote. Driven directly rather than asserted
    about, so a regex that stopped discriminating fails here rather than silently passing above.
    """
    ledger = _ledger_block()

    assert re.search(r"\bv12\b", ledger), "a version the ledger really describes reads as absent"
    assert not re.search(r"\bv99\b", ledger), "a version nobody wrote reads as present"
    # `v1` is the base schema, not a migration: `_MIGRATIONS` starts at 2. It must not be
    # satisfied by `v11`/`v12`/`v13`, which is what an unbounded search would do.
    assert not re.search(r"\bv1\b", ledger), "the word boundary is not holding; v11 answered v1"


def test_the_ledger_check_does_not_demand_more_than_the_code_has() -> None:
    """Cry-wolf half (§4): the guard asks for exactly the migrations that exist, and no others.

    Without this, a check could quietly widen - demanding a `v17` the code has never shipped -
    and the first person to hit the false failure would delete the guard rather than the demand.
    """
    demanded = {version for version, _fn in _MIGRATIONS}
    assert demanded == set(range(2, CURRENT_SCHEMA_VERSION + 1)), (
        "the migration list is not the contiguous v2..current range this guard assumes; "
        f"demanded {sorted(demanded)} against v2..v{CURRENT_SCHEMA_VERSION}"
    )
    assert CURRENT_SCHEMA_VERSION + 1 not in demanded
