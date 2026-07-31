"""Trip persistence: schema v12 (`trips`/`trip_days`) and its CRUD, per `trip-grouping-research.md` §6.

A separate file from `test_catalog.py` rather than an addition to it: this is one cohesive unit
(one migration, one down-migration, one small CRUD surface) that reads better held together than
interleaved with the rest of the catalog's tests.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from truestill_core.catalog import (
    CURRENT_SCHEMA_VERSION,
    Catalog,
    _add_trip_tables,
    downgrade_v12_to_v11,
)

# --- schema shape ------------------------------------------------------------------------

#: Genuine v11, frozen at the moment v12 was added -- hand-transcribed, like `_make_v1_catalog`
#: and `_make_v6_catalog` in test_catalog.py, rather than derived from the module under test.
#: Deriving it from `catalog._SCHEMA` would make this test unable to catch a bug in `_SCHEMA`
#: itself; a frozen, independent copy is what actually proves the down-migration's target.
_V11_FULL_SCHEMA = """
CREATE TABLE IF NOT EXISTS files (
    id            INTEGER PRIMARY KEY,
    source_path   TEXT    NOT NULL,
    original_name TEXT,
    sha256        TEXT    NOT NULL UNIQUE,
    copy_sha256   TEXT,
    perceptual    TEXT,
    size          INTEGER,
    captured_at   TEXT,
    category      TEXT    NOT NULL,
    relative      TEXT    NOT NULL,
    event_id      INTEGER,
    upload_status TEXT    NOT NULL,
    processed_at  TEXT    NOT NULL,
    uploaded_at   TEXT
);
CREATE INDEX IF NOT EXISTS idx_files_sha256 ON files (sha256);
CREATE INDEX IF NOT EXISTS idx_files_perceptual ON files (perceptual);
CREATE INDEX IF NOT EXISTS idx_files_size ON files (size);

CREATE TABLE IF NOT EXISTS albums (
    id   INTEGER PRIMARY KEY,
    name TEXT    NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS file_albums (
    file_id  INTEGER NOT NULL,
    album_id INTEGER NOT NULL,
    PRIMARY KEY (file_id, album_id)
);

CREATE TABLE IF NOT EXISTS events (
    id         INTEGER PRIMARY KEY,
    name       TEXT    NOT NULL,
    slug       TEXT    NOT NULL,
    start_date TEXT,
    file_count INTEGER,
    signature  TEXT    NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS skipped_clusters (
    signature  TEXT PRIMARY KEY,
    skipped_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS drives (
    uuid          TEXT PRIMARY KEY,
    label         TEXT NOT NULL,
    first_seen    TEXT,
    last_seen     TEXT,
    last_verified TEXT,
    notes         TEXT
);

CREATE TABLE IF NOT EXISTS file_copies (
    sha256        TEXT NOT NULL,
    drive_uuid    TEXT NOT NULL,
    relative      TEXT NOT NULL,
    copy_sha256   TEXT,
    size          INTEGER,
    copied_at     TEXT,
    last_verified TEXT,
    PRIMARY KEY (sha256, drive_uuid)
);
CREATE INDEX IF NOT EXISTS idx_file_copies_drive ON file_copies (drive_uuid);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS migration_journal (
    sha256       TEXT NOT NULL,
    drive_uuid   TEXT NOT NULL,
    old_relative TEXT NOT NULL,
    new_relative TEXT NOT NULL,
    copy_sha256  TEXT,
    run_id       TEXT,
    completed_at TEXT,
    PRIMARY KEY (sha256, drive_uuid)
);

CREATE TABLE IF NOT EXISTS migration_runs (
    run_id       TEXT PRIMARY KEY,
    drive_uuid   TEXT NOT NULL,
    started_at   TEXT NOT NULL,
    completed_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_migration_runs_drive ON migration_runs (drive_uuid);

CREATE TABLE IF NOT EXISTS reclaim_journal (
    source_path TEXT PRIMARY KEY,
    sha256      TEXT NOT NULL,
    freed_bytes INTEGER,
    reclaimed_at TEXT
);

CREATE TABLE IF NOT EXISTS inplace_runs (
    run_id       TEXT PRIMARY KEY,
    source_root  TEXT NOT NULL,
    dest_root    TEXT NOT NULL,
    drive_uuid   TEXT,
    started_at   TEXT NOT NULL,
    completed_at TEXT,
    status       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS inplace_moves (
    run_id       TEXT NOT NULL,
    sha256       TEXT NOT NULL,
    old_relative TEXT NOT NULL,
    new_relative TEXT NOT NULL,
    moved_at     TEXT NOT NULL,
    PRIMARY KEY (run_id, old_relative)
);
CREATE INDEX IF NOT EXISTS idx_inplace_moves_run ON inplace_moves (run_id);
"""


def _make_v11_reference_catalog(path: Path) -> None:
    """A genuine, complete v11 catalog, built independently of the module under test."""
    conn = sqlite3.connect(str(path))
    conn.executescript(_V11_FULL_SCHEMA)
    conn.execute("PRAGMA user_version = 11")
    conn.commit()
    conn.close()


def _make_minimal_v11_catalog(path: Path) -> None:
    """A pre-v12 catalog with only `files` + version 11, matching `_make_v6_catalog`'s style.

    `_add_trip_tables` only creates `trips`/`trip_days`, which do not depend on any other table
    -- so a minimal stand-in is enough to prove the *up* migration runs, without needing the
    full historical chain that `_V11_FULL_SCHEMA` exists to provide for the *down* proof.
    """
    conn = sqlite3.connect(str(path))
    conn.executescript(
        """
        CREATE TABLE files (
            id INTEGER PRIMARY KEY, source_path TEXT NOT NULL, sha256 TEXT NOT NULL UNIQUE,
            category TEXT NOT NULL, relative TEXT NOT NULL, upload_status TEXT NOT NULL,
            processed_at TEXT NOT NULL
        );
        PRAGMA user_version = 11;
        """
    )
    conn.commit()
    conn.close()


def _schema_fingerprint(conn: sqlite3.Connection) -> tuple[object, ...]:
    """A structural snapshot: every table's columns, every index, and the schema version.

    Compared instead of raw DDL text so the proof is immune to incidental whitespace and catches
    exactly what "byte-equivalent" means here: no table left over, none missing, no column added
    or dropped.
    """
    tables = {
        row["name"]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
        )
    }
    columns = {
        table: tuple(
            sorted(
                (col["name"], col["type"], col["notnull"], col["pk"])
                for col in conn.execute(f"PRAGMA table_info({table})")
            )
        )
        for table in tables
    }
    indexes = {
        row["name"]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'index' AND name NOT LIKE 'sqlite_%'"
        )
    }
    version = int(conn.execute("PRAGMA user_version").fetchone()[0])
    return (frozenset(tables), tuple(sorted(columns.items())), frozenset(indexes), version)


def test_the_v11_reference_predates_the_current_schema() -> None:
    """Verified, not trusted: confirms the premise every other test in this file depends on.

    Asserts the *relationship* rather than a literal. The old form pinned ``== 12`` and had to
    be edited by every later migration, which makes the edit routine - and a premise check that
    is routinely edited stops being checked.
    """
    assert CURRENT_SCHEMA_VERSION > 11, "the v11 reference below must predate the live schema"


def test_v11_catalog_migrates_up_to_v12_with_trip_tables(tmp_path: Path) -> None:
    db = tmp_path / "v11.sqlite"
    _make_minimal_v11_catalog(db)

    with Catalog(db) as catalog:
        assert catalog.schema_version == CURRENT_SCHEMA_VERSION
        # Both new tables exist and are queryable (proves the migration, not just the version bump).
        assert catalog.trip_for_day("2014-08-14") is None
        trip_id = catalog.create_trip(
            name="Wayanad",
            slug="wayanad",
            start_date="2014-08-14",
            end_date="2014-08-17",
            days=["2014-08-14"],
        )
        assert catalog.trip_for_day("2014-08-14") == trip_id


def test_v12_downgrades_to_v11_byte_equivalent(tmp_path: Path) -> None:
    """Up then down: round-trips clean, and `down` leaves the schema byte-equivalent to v11."""
    reference_db = tmp_path / "reference.sqlite"
    _make_v11_reference_catalog(reference_db)
    reference_conn = sqlite3.connect(str(reference_db))
    reference_conn.row_factory = sqlite3.Row

    # Built as a genuine v12 rather than "a fresh catalog, which happens to be v12" - that
    # equivalence held only while 12 was the newest version, and quietly stopped being true at
    # v13. `downgrade_v12_to_v11` is scoped to v12 by name, so it must be handed one.
    live_db = tmp_path / "live.sqlite"
    _make_v11_reference_catalog(live_db)
    live_setup = sqlite3.connect(str(live_db))
    _add_trip_tables(live_setup)
    live_setup.execute("PRAGMA user_version = 12")
    live_setup.commit()
    assert int(live_setup.execute("PRAGMA user_version").fetchone()[0]) == 12
    downgrade_v12_to_v11(live_setup)
    live_setup.commit()
    live_setup.close()

    live_conn = sqlite3.connect(str(live_db))
    live_conn.row_factory = sqlite3.Row

    assert _schema_fingerprint(live_conn) == _schema_fingerprint(reference_conn)
    assert int(live_conn.execute("PRAGMA user_version").fetchone()[0]) == 11


def test_trip_days_primary_key_rejects_a_second_trip_claiming_the_same_day(tmp_path: Path) -> None:
    with Catalog(tmp_path / "c.sqlite") as catalog:
        catalog.create_trip(
            name="Wayanad",
            slug="wayanad",
            start_date="2014-08-15",
            end_date="2014-08-17",
            days=["2014-08-15", "2014-08-16", "2014-08-17"],
        )
        with pytest.raises(sqlite3.IntegrityError):
            catalog.create_trip(
                name="Duplicate",
                slug="duplicate",
                start_date="2014-08-16",
                end_date="2014-08-16",
                days=["2014-08-16"],  # already claimed above
            )


def test_edge_adjust_keeps_trip_id_and_name_stable(tmp_path: Path) -> None:
    """The direct §6 regression: an edge trim must not re-create the trip under a new identity.

    A decoy trip is created *after* the one under test, giving it a higher id. Plain
    ``INTEGER PRIMARY KEY`` (no ``AUTOINCREMENT``) assigns the next rowid as ``max(existing) + 1``
    at insert time, not from a monotonic counter -- so a delete-then-reinsert bug on the trip
    under test would land back on the *same* id by coincidence if it were the only or the
    highest-numbered row in the table. The decoy's higher id forces a genuine reinsert to land on
    a *different*, higher id, so this only passes if the row was truly never deleted. Confirmed by
    mutation testing before trusting it -- see the report.
    """
    with Catalog(tmp_path / "c.sqlite") as catalog:
        trip_id = catalog.create_trip(
            name="Wayanad",
            slug="wayanad",
            start_date="2014-08-14",
            end_date="2014-08-17",
            days=["2014-08-14", "2014-08-15", "2014-08-16", "2014-08-17"],
        )
        catalog.create_trip(
            name="Decoy",
            slug="decoy",
            start_date="2013-09-15",
            end_date="2013-09-16",
            days=["2013-09-15", "2013-09-16"],
        )

        catalog.update_trip_days(trip_id, ["2014-08-15", "2014-08-16", "2014-08-17"])  # trim Aug 14

        row = catalog._conn.execute(
            "SELECT id, name, start_date, end_date FROM trips WHERE id = ?", (trip_id,)
        ).fetchone()
        assert row["id"] == trip_id  # same identity, not a new row
        assert row["name"] == "Wayanad"  # name survived the edit untouched
        assert row["start_date"] == "2014-08-15"  # the row's own span was refreshed
        assert row["end_date"] == "2014-08-17"
        assert catalog.trip_for_day("2014-08-14") is None  # trimmed day released
        assert catalog.trip_for_day("2014-08-15") == trip_id  # remaining days still claimed


def test_trip_days_foreign_key_requires_a_real_trip(tmp_path: Path) -> None:
    with Catalog(tmp_path / "c.sqlite") as catalog, pytest.raises(sqlite3.IntegrityError):
        catalog._conn.execute(
            "INSERT INTO trip_days (day, trip_id) VALUES (?, ?)", ("2099-01-01", 999)
        )
