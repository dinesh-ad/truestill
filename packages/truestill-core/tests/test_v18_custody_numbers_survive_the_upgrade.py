"""Upgrading a v18 catalog to v19 changes no custody number. `(abg)` Stage 2.

**This is the only honest definition of a safe migration here.** v19 adds `file_copies.missing_at`
and four custody queries learned to exclude rows that carry it - so the risk the column introduces
is not a lost row or a failed `ALTER`, which `test_migration_safety.py` already covers for every
migration. It is that a user upgrades and the sentence on their screen changes, with nothing
having happened to their files.

It cannot, and the reason is worth stating rather than trusting: the column is NULL on every
existing row, and NULL means *not known to be absent*. A value only ever arrives from an
observation - a verify run on a drive that identified itself. An upgrade observes nothing.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from truestill_core.catalog import CURRENT_SCHEMA_VERSION, Catalog

DRIVES = (("D0", "The Memory Cabinet"), ("D1", "Output"))


def _custody_answers(catalog: Catalog) -> dict[str, Any]:
    """Every number a custody sentence is written against, in one place."""
    floor = catalog.custody_floor()
    return {
        "single_copy": catalog.single_copy_count(),
        "at_risk": [r["original_name"] for r in catalog.single_copy_shas()],
        "no_copy": floor["no_copy"],
        "one_copy": floor["one_copy"],
        "held": floor["held"],
        "held_floor": floor["held_floor"],
        "floor": floor["floor"],
        "holding": [(h.label, h.files) for h in catalog.drives_holding(["sha0", "sha1", "sha2"])],
        "drives": [
            (d["label"], d["file_count"], d["missing_count"]) for d in catalog.list_drives()
        ],
    }


def _seed(db: Path) -> None:
    """Three files: one on both drives, one on `Output` only, one with no copy at all.

    The third is there because `custody_floor` reads `files` and not `file_copies`, so a fixture
    without it would leave `no_copy` at zero and prove nothing about the most exposed state.
    """
    with Catalog(db) as catalog:
        for uuid, label in DRIVES:
            catalog.upsert_drive(uuid=uuid, label=label)
        for index in range(3):
            catalog.record_uploaded(
                source_path=f"/src/{index}.jpg",
                original_name=f"{index}.jpg",
                sha256=f"sha{index}",
                copy_sha256=f"sha{index}",
                perceptual=None,
                size=10,
                captured_at=None,
                category="Camera",
                relative=f"Camera/{index}.jpg",
                drive_uuid="D1" if index < 2 else None,
            )
        catalog.record_copy(
            sha256="sha0", drive_uuid="D0", relative="Camera/0.jpg", copy_sha256="sha0", size=10
        )


def _downgrade_to_v18(db: Path) -> None:
    """Make this catalog genuinely v18: no `missing_at`, and `user_version` to match.

    Dropping the column rather than building v18's DDL by hand, so the fixture cannot drift from
    the schema the migration will actually meet.
    """
    conn = sqlite3.connect(db)
    try:
        conn.execute("ALTER TABLE file_copies DROP COLUMN missing_at")
        conn.execute("PRAGMA user_version = 18")
        conn.commit()
    finally:
        conn.close()


def test_a_v18_catalog_answers_every_custody_question_identically_after_upgrading(
    tmp_path: Path,
) -> None:
    db = tmp_path / "c.sqlite"
    _seed(db)
    with Catalog(db) as catalog:
        after_v19 = _custody_answers(catalog)

    _downgrade_to_v18(db)
    with Catalog(db) as catalog:  # opening runs the migration
        assert catalog.schema_version == CURRENT_SCHEMA_VERSION
        upgraded = _custody_answers(catalog)

    assert upgraded == after_v19, "the upgrade changed a number a user reads"
    assert after_v19["drives"] == [("Output", 2, 0), ("The Memory Cabinet", 1, 0)], (
        "the fixture is not the shape this test assumes"
    )
    assert after_v19["no_copy"] == 1, "the file with no copy at all is not in the fixture"


def test_the_upgraded_column_is_null_everywhere_rather_than_defaulted(tmp_path: Path) -> None:
    """NULL is *not known to be absent*; it is not a claim of presence and not a zero.

    A migration that backfilled anything here would be asserting an observation nobody made,
    which is the failure the whole entry is about.
    """
    db = tmp_path / "c.sqlite"
    _seed(db)
    _downgrade_to_v18(db)

    with Catalog(db) as catalog:
        rows = catalog.copies_on_drive("D1")
        assert rows, "the fixture lost its copies in the downgrade"

    conn = sqlite3.connect(db)
    try:
        values = [r[0] for r in conn.execute("SELECT missing_at FROM file_copies")]
    finally:
        conn.close()
    assert values, "the fixture has no copy rows, so this asserts nothing"
    assert all(v is None for v in values), f"the migration invented an observation: {values}"
