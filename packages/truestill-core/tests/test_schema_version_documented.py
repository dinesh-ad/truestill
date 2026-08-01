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

import truestill_core.catalog
from truestill_core.catalog import _MIGRATIONS, CURRENT_SCHEMA_VERSION

_CONTRACT = Path(__file__).resolve().parents[3] / "docs" / "IMPLEMENTATION_STANDARDS.md"

#: Read from the imported module rather than a relative path, so the guard is aimed at the
#: catalog the tests actually load (§4 - a guard targets the module that owns the name).
_CATALOG_SOURCE = Path(truestill_core.catalog.__file__)

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


#: How far after a version token to look for the subject it introduces. **Measured, not
#: guessed, and deliberately not load-bearing:** every value from 20 to 70 gives exactly one
#: defining mention for each of v2..v16 against the real ledger, so the discriminators are the
#: possessive and the sentence break below, not this number.
_SUBJECT_WINDOW = 40


def _defining_mentions(version: int, ledger: str) -> int:
    """How often `v{version}` **introduces** an entry, rather than merely naming one.

    Presence was the first rule and it was too weak: `v16` appears three times in the ledger
    and `v12` twice, because an entry's own reasoning goes on to discuss the version it just
    described. Deleting a real entry therefore left its commentary behind to answer for it -
    the "ledger drifts quietly" failure this module's docstring claims to guard, unguarded.

    An entry names its subject in backticks (``v15 `date_confirmations` ``); commentary does
    not. Two shapes are excluded, and both are real text from this ledger rather than invented
    ones: a possessive (``v16's flag is on ...``) and a version with no subject after it at all
    (``caught before v16 shipped.``). A backtick reached only after a sentence break belongs to
    the next sentence, not to this version.

    Deliberately tolerant of the entries that describe before they name - ``v4 event tables
    (`events` + ...)`` - because three real entries are written that way and a rule that
    demanded an immediately-adjacent backtick would fail on correct text (§4: a guard that
    fires on ordinary prose is one someone switches off).
    """
    found = 0
    for match in re.finditer(rf"\bv{version}\b", ledger):
        tail = ledger[match.end() : match.end() + _SUBJECT_WINDOW]
        if tail.startswith("'"):
            continue  # possessive: the entry is discussing itself, not opening
        tick = tail.find("`")
        if tick == -1:
            continue  # no subject named
        if ". " in tail[:tick]:
            continue  # that backtick opens the next sentence
        found += 1
    return found


def _versions_missing_from_the_ledger() -> list[int]:
    ledger = _ledger_block()
    return [version for version, _fn in _MIGRATIONS if _defining_mentions(version, ledger) == 0]


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


def test_every_migration_is_defined_once_in_the_ledger_not_merely_mentioned() -> None:
    """The measured half of the defining-token rule, and its anti-vacuity.

    Exactly one defining mention per version. More than one would mean the rule is counting
    commentary again and a deletion could hide behind it; zero is the missing-entry case the
    test above reports. Against the ledger as written this is 1 for every v2..v16, while bare
    presence counts 3 for `v16` and 2 for `v12`.
    """
    ledger = _ledger_block()
    assert ledger, "the ledger did not resolve"

    counts = {version: _defining_mentions(version, ledger) for version, _fn in _MIGRATIONS}
    assert all(count == 1 for count in counts.values()), (
        "a version is defined more or less than once in §3's ledger: "
        + ", ".join(f"v{v}={c}" for v, c in sorted(counts.items()) if c != 1)
    )


def test_commentary_alone_does_not_define_a_ledger_entry() -> None:
    """Driven directly against the two commentary shapes this ledger actually contains.

    Both strings below are real text. If a later simplification returns the check to bare
    presence, these go red rather than the weakness quietly returning.
    """
    assert _defining_mentions(16, "v16 `file_copies.date_baked_at` (whether a date reached) ") == 1

    # Possessive, and a subject named right after it - the shape that fooled bare presence.
    assert (
        _defining_mentions(16, "**v16's flag is on `file_copies`, not on `date_confirmations`") == 0
    )
    # No subject at all.
    assert _defining_mentions(16, "caught before v16 shipped.") == 0
    # A backtick that opens the next sentence is not this version's subject.
    assert _defining_mentions(9, "v9 was skipped. `reclaim_journal` came later") == 0


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


#: §3's table-inventory bullet, located by its heading rather than a line number.
_INVENTORY_HEAD = "- **Table inventory"

#: `CREATE TABLE [IF NOT EXISTS] name`, tolerating the optional quoting SQLite accepts. Applied
#: to `catalog.py` only - see `_documented_tables` for why the cache sidecar is out of scope.
_CREATE_TABLE = re.compile(
    r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[\"'`\[]?([A-Za-z_][A-Za-z0-9_]*)",
    re.IGNORECASE,
)

#: A backticked token inside the inventory bullet.
_BACKTICKED = re.compile(r"`([^`]+)`")


def _created_tables() -> set[str]:
    """Every table `catalog.py` creates, from `_SCHEMA` and from the migrations alike.

    Names are lowercased, which is how SQLite compares them, and the set is a union: a table
    appears both in `_SCHEMA` (for a fresh database) and in the migration that introduced it
    (for an existing one), and both spellings must be the same name.
    """
    source = _CATALOG_SOURCE.read_text(encoding="utf-8")
    return {name.lower() for name in _CREATE_TABLE.findall(source)}


def _documented_tables() -> set[str]:
    """The table names §3's inventory bullet lists.

    Backticked tokens **without a dot**. The bullet's closing sentence names the columns that
    v13, v14 and v16 add (`files.date_source`, `file_copies.date_baked_at`), and a column is not
    a table; the dot is what separates them, and it is the document's own notation rather than a
    convention invented here.

    **Scope: the catalog, not the cache.** `hash_cache.py` creates a `hash_cache` table, and it
    is deliberately absent from §3 because it lives in a *different database* - §8 states the
    sidecar sits beside the catalog, never inside it, and is disposable where the catalog is
    not. So this reads `catalog.py` alone. Widening it to the whole tree would demand a row in
    the catalog's data contract for a file that contract does not govern.
    """
    lines = _contract_text().splitlines()
    starts = [i for i, line in enumerate(lines) if line.startswith(_INVENTORY_HEAD)]
    if len(starts) != 1:
        return set()  # not located; the anti-vacuity assertion turns this into a failure
    start = starts[0]
    end = next(
        (i for i in range(start + 1, len(lines)) if lines[i].startswith(_TOP_LEVEL_BULLET)),
        len(lines),
    )
    block = "\n".join(lines[start:end])
    return {token.lower() for token in _BACKTICKED.findall(block) if "." not in token}


def test_the_contract_lists_the_tables_the_catalog_actually_creates() -> None:
    """§3's inventory equals the `CREATE TABLE` set, in both directions.

    Unlike the dependency inventory (§7), equality is right here: §3's list claims to *be* the
    catalog's table set, and there is no legitimate reason for it to name a table the code does
    not create or to omit one it does. `date_confirmations` had fallen out of it - named in the
    prose beneath, absent from the list above - which is exactly the drift this closes.

    **One future exception, recorded rather than pre-handled.** SQLite cannot drop or retype a
    column in place; the supported route is create-a-new-table, copy, drop, rename. The first
    migration that needs it will create a **scratch table** that exists for three statements and
    must *not* appear in §3. When this test goes red for that reason it is a **STOP and rule**,
    not a document to force into alignment - the honest fixes are to name the scratch table by a
    convention this reader skips, or to say in §3 why it is excluded. Deliberately not built
    now: no such migration exists, and a rule written for a shape nobody has produced would be
    guessing at the shape.
    """
    created = _created_tables()
    documented = _documented_tables()

    assert created, f"no CREATE TABLE found in {_CATALOG_SOURCE.name}; the reader is wrong"
    assert documented, (
        f"could not locate exactly one {_INVENTORY_HEAD!r} bullet in {_CONTRACT.name}, or it "
        "listed nothing - either way this check would compare against an empty set and pass "
        "for the wrong reason."
    )

    assert created == documented, (
        "§3's table inventory and the catalog disagree.\n"
        f"  created but not listed: {sorted(created - documented) or 'none'}\n"
        f"  listed but not created: {sorted(documented - created) or 'none'}\n\n"
        "The inventory is the contract's answer to 'what is in the catalog'. Update it in the "
        "same commit as the migration."
    )


def test_the_table_reader_separates_a_column_from_a_table() -> None:
    """Aimed at the reader: the dot rule must keep columns out and let table names through.

    Without it the inventory's closing sentence would contribute `files.date_source` and
    `file_copies.date_baked_at` as tables, and the equality above would fail for a reason that
    has nothing to do with the schema.
    """
    documented = _documented_tables()

    assert "files" in documented
    assert "date_confirmations" in documented, "the v15 table is the one that fell out before"
    assert not any("." in name for name in documented), "a column leaked in as a table"
    assert "hash_cache" not in documented, "the cache sidecar is not part of the catalog contract"


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
