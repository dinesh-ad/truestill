"""Opening a catalog can upgrade it in place, and until `(akz)` nothing said so. `(akz)`

**The defect, and the research that shaped the fix rather than the fix shaping itself.**

BoxLite shipped this exact shape: *"a newer component migrates that database forward in place,
and from that moment every older component stops working... no warning before the migration
happens."* Truestill does the same thing - `Catalog.__init__` calls `_migrate` unconditionally, so
there is no read-only open anywhere and `truestill where` upgrades a library.

⚠ **THE NAIVE FIX IS WORSE AND IS REFUSED.** FreeBSD's pkg migrates only on read-write opens, and
every read-only command then fails on an old schema with *"no such table"*, leaving the upgrade
path *"permanently wedged"*. OneUptime's rule is the one Truestill already follows: *"use
user_version as an explicit application contract and ship immutable sequential migrations... fail
closed on unknown schemas"* - which is `catalog._refuse_if_newer`. **Forward-migrate-on-open
stays. The defect was the silence.**

⚠ **AND THE MIGRATION IS NOT DONE BY THE COMMAND.** `_dispatch` calls `inspect_catalog` for every
subcommand carrying `--db`, and that opens a real `Catalog` to count files and drives - so **the
startup banner is what upgrades the file**, one line before any handler runs. That is why the fact
rides on `CatalogStartupInfo` and not on a reporter at the command's own open: a reporter there
would always find `None`, which was written, measured, and deleted the same day.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from truestill_core.catalog import CURRENT_SCHEMA_VERSION, Catalog, SchemaUpgrade
from truestill_core.catalog_backup import BackupOutcome
from truestill_core.catalog_startup import (
    CatalogOpening,
    format_startup_lines,
    inspect_catalog,
    schema_upgrade_notice,
)

BEHIND = CURRENT_SCHEMA_VERSION - 1


def _wind_back(path: Path, version: int) -> Path:
    """Set ``path``'s schema version, so the next open must run the chain.

    ⚠ **Called LAST, after any content this test needs.** Adding a drive means opening the
    catalog, and opening it migrates - which is the whole subject of this file. The first draft
    seeded a drive after winding back and measured a catalog that was already current.
    """
    conn = sqlite3.connect(str(path))
    conn.execute(f"PRAGMA user_version = {version}")
    conn.commit()
    conn.close()
    return path


def _catalog_at(path: Path, version: int) -> Path:
    """A real catalog wound back to ``version``."""
    with Catalog(path):
        pass
    return _wind_back(path, version)


# ------------------------------------------------------------------ the fact, where it is made


def test_a_catalog_that_migrates_records_where_it_came_from(tmp_path: Path) -> None:
    """`previous` is the number an older build would still accept, and only this open knows it.

    After the chain runs, `PRAGMA user_version` says `CURRENT_SCHEMA_VERSION` and nothing can
    recover the old value - which is why the record is made inside `_migrate` rather than asked
    for afterwards by a surface.
    """
    db = _catalog_at(tmp_path / "catalog.sqlite", BEHIND)

    with Catalog(db) as catalog:
        assert catalog.schema_upgrade == SchemaUpgrade(BEHIND, CURRENT_SCHEMA_VERSION)
        assert catalog.schema_version == CURRENT_SCHEMA_VERSION


def test_an_ordinary_open_records_nothing(tmp_path: Path) -> None:
    """The cry-wolf half, and it is the case that happens on every open but the first.

    Without this, a `schema_upgrade` set unconditionally would satisfy every assertion above
    while announcing an upgrade to every user on every command for ever.
    """
    db = tmp_path / "catalog.sqlite"
    with Catalog(db) as first:
        assert first.schema_upgrade is None, "a FRESH catalog was not migrated from anything"
    with Catalog(db) as second:
        assert second.schema_upgrade is None, "an already-current catalog reported an upgrade"


def test_the_first_thing_that_opens_the_catalog_is_what_carries_the_fact(tmp_path: Path) -> None:
    """⚠ **`inspect_catalog` migrates, and that is the finding this file is built around.**

    The banner is not a passive reading: it opens a `Catalog` to count files and drives. A
    `Catalog` opened afterwards is the second opener and has nothing to report, so a guard that
    asserted on the second would pass against total silence.
    """
    db = _catalog_at(tmp_path / "catalog.sqlite", BEHIND)

    info = inspect_catalog(db, explicit_db=True)

    assert info.opening.upgrade == SchemaUpgrade(BEHIND, CURRENT_SCHEMA_VERSION)
    with Catalog(db) as after:
        assert after.schema_upgrade is None, "the banner did not migrate; this guard is misplaced"


# --------------------------------------------------------------------------------- the wording


def test_the_notice_names_both_versions_and_what_it_costs() -> None:
    """Both halves, and the second is the one a user can act on.

    BoxLite's remedy asks for *"the previous and new versions"*; naming them alone still leaves a
    person to work out what changed for them. What changed is that `_refuse_if_newer` will turn an
    older build away, and that refusal is the next message they meet.
    """
    said = schema_upgrade_notice(CatalogOpening(SchemaUpgrade(23, 24)))

    assert "23" in said
    assert "24" in said
    assert "older" in said.lower()
    assert "refuse" in said.lower()


def test_the_notice_names_the_copy_that_is_the_way_back() -> None:
    """The remedy in the same breath as the cost - the copy is the only route to `previous`."""
    copy = Path("/data/Truestill/catalog.pre-upgrade.sqlite")
    said = schema_upgrade_notice(
        CatalogOpening(SchemaUpgrade(23, 24), BackupOutcome(taken=True, path=copy))
    )

    assert str(copy) in said


def test_a_failed_copy_is_said_as_the_loss_it_is() -> None:
    """⚠ **Not softened into the success wording.** An upgrade with no copy has no way back, and
    a sentence that named a path which does not exist would be worse than one that named none."""
    said = schema_upgrade_notice(
        CatalogOpening(
            SchemaUpgrade(23, 24), BackupOutcome(taken=False, error="no space left on device")
        )
    )

    assert "no space left on device" in said
    assert "no way back" in said
    assert "kept at" not in said


def test_nothing_is_said_when_nothing_was_migrated() -> None:
    """Empty, so a surface may render it unconditionally and stay silent."""
    assert schema_upgrade_notice(CatalogOpening()) == ""


# ------------------------------------------------------------- the surface that renders it


def test_the_startup_lines_carry_the_upgrade(tmp_path: Path) -> None:
    """Both surfaces print `format_startup_lines`, so one change reaches both. §9."""
    db = _catalog_at(tmp_path / "catalog.sqlite", BEHIND)

    lines = format_startup_lines(inspect_catalog(db, explicit_db=True))

    assert any("upgraded from version" in line for line in lines), lines
    assert lines[0].startswith("Catalog:"), "the upgrade was said before the path it refers to"


def test_the_startup_lines_say_nothing_extra_on_an_ordinary_open(tmp_path: Path) -> None:
    """The cry-wolf half at the surface, not only at the fact."""
    db = tmp_path / "catalog.sqlite"
    with Catalog(db):
        pass

    lines = format_startup_lines(inspect_catalog(db, explicit_db=True))

    assert not any("upgraded" in line for line in lines), lines


@pytest.mark.parametrize("drives", [0, 1])
def test_every_presence_that_opened_the_catalog_carries_the_upgrade(
    tmp_path: Path, drives: int
) -> None:
    """⚠ **Four return paths follow that open and the first fix filled in one of them.**

    `inspect_catalog` returns READY, EMPTY_WITH_DRIVES or EMPTY after migrating, and a wound-back
    EMPTY catalog reported nothing at all until this was parametrized - found by running the real
    command rather than by reading the diff.
    """
    db = tmp_path / "catalog.sqlite"
    with Catalog(db) as catalog:
        if drives:
            catalog.upsert_drive(uuid="uuid-1", label="Backup")
    _wind_back(db, BEHIND)

    info = inspect_catalog(db, explicit_db=True)

    assert info.opening.upgrade is not None, f"presence {info.presence} dropped the upgrade"


# ⚠ **ONE MUTATION SURVIVES THIS FILE AND IS NAMED RATHER THAN PAPERED OVER.**
#
# Replacing `if version < CURRENT_SCHEMA_VERSION:` with `if True:` at the record site makes an
# open that migrated nothing claim an upgrade - "from version 24 to 24". Nothing here can see it,
# and a defensive guard in `schema_upgrade_notice` was written to catch it and then deleted,
# because it could not: `_migrate`'s fast path returns first on every catalog a single process
# can construct, so the line is only reached with `previous == current` through `(afv)`'s race
# between two concurrent openers - which measured four of six taking a pointless full copy.
#
# The precedent for deleting it is in this codebase already, in `catalog_session.open_catalog`:
# *"a defensive `mark_clean()` here was written and then deleted, because a mutation that removed
# it killed no test - it could not."* An untested guard against an untestable state is a comfort,
# not a check, and this note is the honest version of it.
