"""`files.sha256` is indexed once, by the constraint, not twice.

`NOT NULL UNIQUE` means SQLite maintains `sqlite_autoindex_files_1` over that column already. The
explicit `idx_files_sha256` was a second B-tree on the same key - 196 KB and an extra write per
insert - and every query that chose it moves to the autoindex with no measurable change.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from truestill_core.catalog import CURRENT_SCHEMA_VERSION, Catalog


def _indexes_on_files(catalog: Catalog) -> set[str]:
    return {
        str(r["name"])
        for r in catalog._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='files'"
        )
    }


def test_a_fresh_catalog_does_not_create_the_duplicate(tmp_path: Path) -> None:
    with Catalog(tmp_path / "c.sqlite") as catalog:
        assert "idx_files_sha256" not in _indexes_on_files(catalog)
        assert "sqlite_autoindex_files_1" in _indexes_on_files(catalog), (
            "the UNIQUE constraint's own index is gone; sha256 lookups would be a table scan"
        )


def test_an_existing_catalog_has_it_removed_by_the_migration(tmp_path: Path) -> None:
    """The half a fresh-catalog test cannot see: every user's file already carries the index."""
    db = tmp_path / "old.sqlite"
    with Catalog(db):
        pass
    raw = sqlite3.connect(db)
    raw.execute("CREATE INDEX IF NOT EXISTS idx_files_sha256 ON files (sha256)")
    raw.execute("PRAGMA user_version = 17")
    raw.commit()
    raw.close()

    with Catalog(db) as migrated:
        assert "idx_files_sha256" not in _indexes_on_files(migrated)
        assert migrated.schema_version == CURRENT_SCHEMA_VERSION


def test_a_sha256_lookup_still_uses_an_index(tmp_path: Path) -> None:
    """CRY-WOLF HALF. Dropping the wrong index would turn every content lookup - the operation
    this whole product is built on - into a table scan, and a test that only asserts absence
    would call that a success."""
    with Catalog(tmp_path / "c.sqlite") as catalog:
        plan = " ".join(
            str(r[3])
            for r in catalog._conn.execute(
                "EXPLAIN QUERY PLAN SELECT * FROM files WHERE sha256 = ?", ("x",)
            )
        )

    assert "SEARCH" in plan, f"sha256 lookups are no longer indexed: {plan}"
    assert "INDEX" in plan, f"sha256 lookups are no longer indexed: {plan}"
    assert "SCAN" not in plan
