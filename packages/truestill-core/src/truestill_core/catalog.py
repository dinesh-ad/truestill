"""Persistent record of every file the pipeline has processed.

A single SQLite file (stdlib ``sqlite3``, no server, no extra setup). It exists so runs
are **idempotent and resumable**: a file processed and uploaded once is recognised on the
next run and neither re-hashed for a decision nor re-uploaded. It also feeds the dedup
index, so exact/perceptual matches are found against the whole history, not just the
current run.

One row per processed source file, keyed by SHA-256.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable, Collection, Iterator, Sequence
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType
from typing import Self

from truestill_core.models import DateSource

# Current catalog schema, created whole for a fresh database. Its version is
# CURRENT_SCHEMA_VERSION; older databases are brought up to it by _MIGRATIONS.
#
# ============================================================================================
# STANDING RULE, before adding ANY column to `files`:
#
#   Ask whether the fact is true of the CONTENT, or true of a COPY ON A DRIVE.
#
# `files` is keyed by sha256. Every column on it is shared by every copy of that content, on
# every drive, forever. A fact that can differ between two copies of the same photo does not
# belong here - it belongs on `file_copies`, which is keyed by (sha256, drive_uuid).
#
# This has been got wrong three times, and each was expensive in a different way:
#
#   * `files.copy_sha256` - the post-write hash of "the" copy. Attach wrote it onto a per-drive
#     row, so a Takeout-baked copy would have been verified against a pre-bake hash and reported
#     as CORRUPTION on a file truestill itself rewrote. (The column now has a legitimate
#     per-content role - see `_add_drive_tables` - but using it as a per-drive value was the bug.)
#   * `files.relative` - where "the" copy lives. migrate-layout rewrites `file_copies.relative`
#     and nothing updates this one, so on the real library 0 of 2,300 of these paths still
#     existed and re-attach reported 2,300 files absent from a drive holding 2,269 of them.
#   * `date_confirmations.baked_at` - whether "the" copy has the confirmed date in its bytes.
#     Baking one drive would have marked the confirmation handled and the backup drive's copy
#     would never have been written, and never offered again. Now `file_copies.date_baked_at`.
#
# **Knowing the pattern did not prevent the third one**, which was written one commit after the
# second was documented. That is why the rule is here, at the schema, rather than in a research
# doc or in anyone's memory: this is the last place a person looks before adding a column, and
# the three instances were each caught by a *different* mechanism - an attach measurement, a
# reader sweep, and a reporting obligation. None of them was caught by remembering.
#
# The third one is also an argument for the never-silent rule (`IMPLEMENTATION_STANDARDS.md`
# §9) beyond its usual one: the obligation to report *which drives are still behind* is what
# surfaced it. Being required to tell the truth per drive forced the question "per drive
# according to what?", and the answer was a column that could not answer it. **An honesty
# requirement found a data-model bug** - honest reporting is not only how a user learns what
# happened, it is a design constraint that makes some wrong models impossible to write down.
# ============================================================================================
_SCHEMA = """
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
    uploaded_at   TEXT,
    date_source   TEXT,
    date_tag      TEXT
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

-- One row per (content, drive): where each piece of content physically lives, and the hash of
-- THAT copy (a baked Takeout copy is not byte-identical to the source, and two copies written
-- at different times need not match each other -- so the hash is per-copy, not per-content).
CREATE TABLE IF NOT EXISTS file_copies (
    sha256        TEXT NOT NULL,
    drive_uuid    TEXT NOT NULL,
    relative      TEXT NOT NULL,
    copy_sha256   TEXT,
    size          INTEGER,
    copied_at     TEXT,
    last_verified TEXT,
    -- When a confirmed date was written into THIS drive's copy, NULL until it is. Per
    -- (content, drive) like copy_sha256 above, because that is exactly what a bake changes:
    -- baking the photo on one drive says nothing about the copy on another.
    date_baked_at TEXT,
    PRIMARY KEY (sha256, drive_uuid)
);
CREATE INDEX IF NOT EXISTS idx_file_copies_drive ON file_copies (drive_uuid);

-- Per-catalog key/value settings. First use: the destination layout template (which folder
-- structure this library is organized into), so a re-organization can diff against it.
CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- In-flight layout-migration moves, one row per copy being relocated. A row exists from the
-- moment a move is planned until its old location is removed; its presence after a crash is
-- what lets `migrate-layout` resume -- old_relative is retained so an orphaned old copy can be
-- cleaned even after file_copies has been updated to new_relative.
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

-- One row per migration run, so a finished run can be found and reversed as a unit.
CREATE TABLE IF NOT EXISTS migration_runs (
    run_id       TEXT PRIMARY KEY,
    drive_uuid   TEXT NOT NULL,
    started_at   TEXT NOT NULL,
    completed_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_migration_runs_drive ON migration_runs (drive_uuid);

-- Audit/resume journal for `truestill reclaim`: one row per source deletion, written just before
-- the delete and cleared just after. A row surviving a crash names a source that was verified-
-- redundant and about to be freed -- an audit trail, since reclaim never deletes an unverified
-- source. `freed_bytes` records the space each delete reclaimed.
CREATE TABLE IF NOT EXISTS reclaim_journal (
    source_path TEXT PRIMARY KEY,
    sha256      TEXT NOT NULL,
    freed_bytes INTEGER,
    reclaimed_at TEXT
);

-- Reversible journal for rename-based relocation (in-place organize). Unlike reclaim_journal,
-- which records what was *destroyed*, this records where each file *moved* -- the difference
-- between an audit trail and an undo. Paths are stored relative to the two roots in the run
-- header, not absolutely, so a drive that remounts elsewhere is still undoable.
--
-- The journal attaches to the MECHANISM, not to a flag: any rename-based relocation is
-- recorded, whether the user asked for --in-place or got the same-filesystem optimization
-- under a plain --move. Two users who performed the identical operation get identical undo
-- rights regardless of how they spelled it.
CREATE TABLE IF NOT EXISTS inplace_runs (
    run_id       TEXT PRIMARY KEY,
    source_root  TEXT NOT NULL,
    dest_root    TEXT NOT NULL,
    drive_uuid   TEXT,
    started_at   TEXT NOT NULL,
    completed_at TEXT,
    status       TEXT NOT NULL   -- in_progress | completed | undone
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

-- A multi-day trip: identity IS the row, never a membership hash. Unlike events.signature
-- (a hash of member SHA-256s), a trip is user-adjustable and grows on re-ingest -- an edge
-- trim or an added day must not orphan its name. See trip-grouping-research.md §6.
CREATE TABLE IF NOT EXISTS trips (
    id         INTEGER PRIMARY KEY,
    name       TEXT    NOT NULL,
    slug       TEXT    NOT NULL,
    start_date TEXT    NOT NULL,
    end_date   TEXT    NOT NULL
);

-- One row per day claimed by a trip. `day` as the PRIMARY KEY makes "a day belongs to at most
-- one trip" unviolatable rather than merely intended, and is the name-once lookup: a candidate
-- day already present here is already claimed.
CREATE TABLE IF NOT EXISTS trip_days (
    day     TEXT PRIMARY KEY,
    trip_id INTEGER NOT NULL REFERENCES trips(id)
);
CREATE TABLE IF NOT EXISTS date_confirmations (
    sha256       TEXT PRIMARY KEY,
    captured_at  TEXT NOT NULL,
    confirmed_at TEXT NOT NULL,
    confirmed_by TEXT
);
"""

#: Bump whenever the schema changes, and add a matching entry to _MIGRATIONS.
CURRENT_SCHEMA_VERSION = 16


class CatalogVersionError(RuntimeError):
    """The catalog on disk was written by a newer truestill than this one understands."""


def _column_names(conn: sqlite3.Connection) -> set[str]:
    return {row["name"] for row in conn.execute("PRAGMA table_info(files)")}


def _columns_of(conn: sqlite3.Connection, table: str) -> set[str]:
    """Column names of any table. `_column_names` answers only for ``files``, and a migration
    that reused it against another table would silently test the wrong one."""
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}


def _add_size_column(conn: sqlite3.Connection) -> None:
    """v1 -> v2: add the ``size`` column used by the scan's size pre-filter."""
    if "size" not in _column_names(conn):
        conn.execute("ALTER TABLE files ADD COLUMN size INTEGER")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_files_size ON files (size)")


def _add_original_name_column(conn: sqlite3.Connection) -> None:
    """v2 -> v3: record the original filename alongside the renamed destination copy."""
    if "original_name" not in _column_names(conn):
        conn.execute("ALTER TABLE files ADD COLUMN original_name TEXT")


def _add_event_tables(conn: sqlite3.Connection) -> None:
    """v3 -> v4: event membership + remembered skips for the event layer."""
    if "event_id" not in _column_names(conn):
        conn.execute("ALTER TABLE files ADD COLUMN event_id INTEGER")
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY, name TEXT NOT NULL, slug TEXT NOT NULL,
            start_date TEXT, file_count INTEGER, signature TEXT NOT NULL UNIQUE
        );
        CREATE TABLE IF NOT EXISTS skipped_clusters (
            signature TEXT PRIMARY KEY, skipped_at TEXT NOT NULL
        );
        """
    )


def _add_takeout_tables(conn: sqlite3.Connection) -> None:
    """v4 -> v5: post-write copy hash + album membership for Takeout ingestion."""
    if "copy_sha256" not in _column_names(conn):
        conn.execute("ALTER TABLE files ADD COLUMN copy_sha256 TEXT")
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS albums (
            id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE
        );
        CREATE TABLE IF NOT EXISTS file_albums (
            file_id INTEGER NOT NULL, album_id INTEGER NOT NULL,
            PRIMARY KEY (file_id, album_id)
        );
        """
    )


def _add_drive_tables(conn: sqlite3.Connection) -> None:
    """v5 -> v6: drive identity + per-(content, drive) copy locations.

    Copy *locations* and their integrity hashes belong to ``file_copies``, per (content, drive).
    That is what this migration established, and it stands.

    **``files.copy_sha256`` was deprecated here, and is NOT any more (2026-07-31). Do not
    re-deprecate it from the old reasoning.** The old reasoning was right about what it is and
    wrong about what it is *for*. It is per-content data, so using it as a **per-drive** value -
    which `attach_drive` once did, copying it onto a ``file_copies`` row - was always incorrect,
    and that misuse is gone.

    What it is now is the **durable per-content record of what the organized copy hashed to
    after any metadata bake**, and content-matching attach depends on it. ``record_uploaded``
    writes the baked digest to both this column and ``file_copies``; on a **re-attach**, the
    per-drive rows are gone *by definition*, so this is the only surviving evidence that a
    Takeout-baked copy hashes to something other than ``files.sha256``. Drop it and those copies
    become unrecognisable exactly when the catalog most needs to rebuild - proved by deleting
    the ``files.copy_sha256`` branch of :meth:`Catalog.attachable_hashes`, which fails
    ``test_a_baked_copy_is_recognised_by_the_hash_it_actually_has``.

    Pre-v6 ``files`` rows are not backfilled (they predate drive identity); their
    ``copy_sha256`` is NULL and reads as "no recorded hash", which `verify` reports as
    UNVERIFIABLE rather than guessing.

    **``files.relative`` is the one that stayed deprecated**, and it is still here for a stated
    reason rather than as debt. Nothing locates a file by it any more (that misuse ended when
    attach began matching on content), and it no longer answers "was this organized?" - three
    queries that asked ``WHERE relative IS NOT NULL`` now ask ``upload_status = 'uploaded'``,
    which is the question they meant. It remains only as a **name fallback** where
    ``original_name`` is NULL - ``media_names``, the format breakdown, ``stats_undated_samples``
    - and those feed the custody strip's photo/video/audio counts. A fallback that never fires
    costs nothing; removing one that turns out to fire costs a blank column on screen. It is
    therefore not dropped, and there is no migration for it.
    """
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS drives (
            uuid TEXT PRIMARY KEY, label TEXT NOT NULL, first_seen TEXT, last_seen TEXT,
            last_verified TEXT, notes TEXT
        );
        CREATE TABLE IF NOT EXISTS file_copies (
            sha256 TEXT NOT NULL, drive_uuid TEXT NOT NULL, relative TEXT NOT NULL,
            copy_sha256 TEXT, size INTEGER, copied_at TEXT, last_verified TEXT,
            -- When a confirmed date was written into THIS drive's copy. Per (content, drive)
            -- like copy_sha256 beside it, because that is what a bake changes.
            date_baked_at TEXT,
            PRIMARY KEY (sha256, drive_uuid)
        );
        CREATE INDEX IF NOT EXISTS idx_file_copies_drive ON file_copies (drive_uuid);
        """
    )


def _add_settings_table(conn: sqlite3.Connection) -> None:
    """v6 -> v7: a per-catalog key/value settings store (first use: the layout template)."""
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY, value TEXT NOT NULL
        );
        """
    )


def _add_reversible_migrations(conn: sqlite3.Connection) -> None:
    """v10 -> v11: a migration becomes reversible, not merely resumable.

    The journal previously deleted each row the moment its move completed, which made it a
    *resume* record that erased itself on success -- so a finished migration had nothing left to
    reverse from. Rows now carry the run that made them and the moment they completed, and they
    survive as the reversal record until a later run of the same drive supersedes them.

    Column adds are gated on ``PRAGMA table_info`` so a concurrent opener that already applied
    the full current ``_SCHEMA`` (which includes ``run_id`` / ``completed_at``) cannot collide
    with this step when ``user_version`` was still below 11.
    """
    journal_cols = {row["name"] for row in conn.execute("PRAGMA table_info(migration_journal)")}
    if "run_id" not in journal_cols:
        conn.execute("ALTER TABLE migration_journal ADD COLUMN run_id TEXT")
    if "completed_at" not in journal_cols:
        conn.execute("ALTER TABLE migration_journal ADD COLUMN completed_at TEXT")
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS migration_runs (
            run_id       TEXT PRIMARY KEY,
            drive_uuid   TEXT NOT NULL,
            started_at   TEXT NOT NULL,
            completed_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_migration_runs_drive ON migration_runs (drive_uuid);
        """
    )


def _add_migration_journal(conn: sqlite3.Connection) -> None:
    """v7 -> v8: a journal of in-flight layout-migration moves (for crash-safe resume)."""
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS migration_journal (
            sha256 TEXT NOT NULL, drive_uuid TEXT NOT NULL, old_relative TEXT NOT NULL,
            new_relative TEXT NOT NULL, copy_sha256 TEXT,
            PRIMARY KEY (sha256, drive_uuid)
        );
        """
    )


def _add_reclaim_journal(conn: sqlite3.Connection) -> None:
    """v8 -> v9: an audit/resume journal for `truestill reclaim` source deletions."""
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS reclaim_journal (
            source_path TEXT PRIMARY KEY, sha256 TEXT NOT NULL,
            freed_bytes INTEGER, reclaimed_at TEXT
        );
        """
    )


def _add_inplace_journal(conn: sqlite3.Connection) -> None:
    """v9 -> v10: a reversible journal for rename-based relocation (in-place organize)."""
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS inplace_runs (
            run_id TEXT PRIMARY KEY, source_root TEXT NOT NULL, dest_root TEXT NOT NULL,
            drive_uuid TEXT, started_at TEXT NOT NULL, completed_at TEXT, status TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS inplace_moves (
            run_id TEXT NOT NULL, sha256 TEXT NOT NULL, old_relative TEXT NOT NULL,
            new_relative TEXT NOT NULL, moved_at TEXT NOT NULL,
            PRIMARY KEY (run_id, old_relative)
        );
        CREATE INDEX IF NOT EXISTS idx_inplace_moves_run ON inplace_moves (run_id);
        """
    )


#: Ordered migrations: ``(target_version, fn)``. Each is idempotent and lifts a database
#: from ``target_version - 1`` to ``target_version``. Append; never rewrite history.
def _add_date_tag_column(conn: sqlite3.Connection) -> None:
    """v13 -> v14: the evidence behind the tier, not just the tier.

    ``date_source`` says *which kind* of evidence won; this says *which piece*. For EXIF it is
    the winning tag name (``DateTimeOriginal``, ``CreateDate``); for ``INFERRED_LOCAL`` it is the
    pipe-encoded container tag, corroborating rung and offset that
    :func:`truestill_core.date_provenance.format_inferred_date_tag` produced.

    Together they answer the question a user actually asks - "why this date?" - which is what the
    honesty view shows and what the rescue flow (ii) hangs its action off. NULL for the tiers that
    have no tag (filename, undated) and for rows written before v14, on the same reasoning as
    ``date_source``: not recorded is not a guess.
    """
    if "date_tag" not in _column_names(conn):
        conn.execute("ALTER TABLE files ADD COLUMN date_tag TEXT")


def _add_date_confirmations(conn: sqlite3.Connection) -> None:
    """v14 -> v15: human date confirmations, in their **own table** keyed on content.

    Deliberately not a column on ``files``. ``forget_organized`` deletes the ``files`` row when
    an undo removes the last copy - correct, because that table is the dedup index and a row
    left behind makes restored content look organized. But a confirmation is not a record of
    *organization*, it is the user's own contribution about *content*, and it must outlive every
    operation that rearranges where that content lives. A column would have been deleted by the
    first `undo-organize`, which is exactly the failure (ii) exists to prevent.

    Keyed on ``sha256`` for the same reason (z) hash-keys its manifest: content identity survives
    rename, migrate, re-layout and in-place organize; a path does not.
    """
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS date_confirmations (
            sha256       TEXT PRIMARY KEY,
            captured_at  TEXT NOT NULL,
            confirmed_at TEXT NOT NULL,
            confirmed_by TEXT
        );
        """
    )


def _add_date_source_column(conn: sqlite3.Connection) -> None:
    """v12 -> v13: persist which tier a file's capture date came from.

    The resolver has always produced this (:class:`~truestill_core.models.DateSource`) and the
    write path has always discarded it; `date-layering-gap-check.md` §5 recorded that gap, and
    items (n) and (ii) both need it durable.

    **Existing rows stay NULL, deliberately.** A library organized before this shipped has no
    retrievable provenance - the evidence chain ran against files that may since have moved -
    so NULL means "not recorded", which is a different and more honest answer than any value
    this migration could invent. The honesty view must not be confidently wrong about exactly
    the files it cannot check.
    """
    if "date_source" not in _column_names(conn):
        conn.execute("ALTER TABLE files ADD COLUMN date_source TEXT")


def _add_trip_tables(conn: sqlite3.Connection) -> None:
    """v11 -> v12: multi-day trips, identified by row -- never by membership hash.

    See the ``trips``/``trip_days`` comment in ``_SCHEMA`` for why; this function exists only so
    an *existing* v11 catalog gets the same two tables a fresh one is born with.
    """
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS trips (
            id         INTEGER PRIMARY KEY,
            name       TEXT    NOT NULL,
            slug       TEXT    NOT NULL,
            start_date TEXT    NOT NULL,
            end_date   TEXT    NOT NULL
        );
        CREATE TABLE IF NOT EXISTS trip_days (
            day     TEXT PRIMARY KEY,
            trip_id INTEGER NOT NULL REFERENCES trips(id)
        );
        """
    )


def downgrade_v12_to_v11(conn: sqlite3.Connection) -> None:
    """Reverse `_add_trip_tables` in place, leaving a byte-for-byte v11 catalog.

    **The first schema-level down-migration in this codebase.** Every prior migration
    (`_MIGRATIONS`) is forward-only; nothing before v12 needed reversing at the schema level
    ("reversible", for the layout migration feature, means an *undoable file move* recorded in
    `migration_journal`/`migration_runs` -- a data-level undo, not a DDL one). This is safe to
    add here specifically because v12 only *adds* two self-contained tables and alters nothing
    that v11 already had; dropping them and resetting the version is therefore exact, not an
    approximation.

    **Testing/rollback only.** No CLI path calls this, and nothing in `Catalog` wires it in --
    a fresh clone always migrates forward via `_migrate`. It exists to prove the v12 migration is
    safely reversible, per the standing rule that a migration must be shown undoable, not merely
    claimed to be.
    """
    conn.executescript(
        """
        DROP TABLE IF EXISTS trip_days;
        DROP TABLE IF EXISTS trips;
        """
    )
    conn.execute("PRAGMA user_version = 11")


def _add_copy_date_baked_at(conn: sqlite3.Connection) -> None:
    """v15 -> v16: record, **per drive**, whether a confirmed date reached that copy's bytes.

    Step 3 made a confirmation durable in the catalog; step 4 writes it into the files. Those
    are different states and a user is entitled to know which one a photo is in - a date only
    truestill knows is not the same promise as a date any other tool will read.

    **It belongs on ``file_copies``, not on ``date_confirmations``.** A confirmation is per
    *content*; a bake changes *one drive's copy*. Putting the flag on the confirmation would
    mean baking the photo on the laptop marked it done for the backup drive as well, which then
    never gets written and never reappears in `confirmations_to_bake` - the same per-content /
    per-drive confusion that produced the ``copy_sha256`` and ``relative`` findings, made a
    third time. Caught before v16 was ever pushed; no database carries the earlier shape.
    """
    columns = _columns_of(conn, "file_copies")
    if not columns:
        # No such table. `_SCHEMA` runs only for a brand-new database, so on an existing one a
        # migration sees whatever is actually there - and a catalog at v15 without `file_copies`
        # is malformed in a way v16 cannot repair and should not diagnose. Skipping keeps the
        # failure where it belongs (the first query that needs the table) instead of reporting a
        # missing *column* on a missing *table*.
        return
    if "date_baked_at" not in columns:
        conn.execute("ALTER TABLE file_copies ADD COLUMN date_baked_at TEXT")


_MIGRATIONS: tuple[tuple[int, Callable[[sqlite3.Connection], None]], ...] = (
    (2, _add_size_column),
    (3, _add_original_name_column),
    (4, _add_event_tables),
    (5, _add_takeout_tables),
    (6, _add_drive_tables),
    (7, _add_settings_table),
    (8, _add_migration_journal),
    (9, _add_reclaim_journal),
    (10, _add_inplace_journal),
    (11, _add_reversible_migrations),
    (12, _add_trip_tables),
    (13, _add_date_source_column),
    (14, _add_date_tag_column),
    (15, _add_date_confirmations),
    (16, _add_copy_date_baked_at),
)


def _now() -> str:
    return datetime.now(UTC).isoformat()


class Catalog:
    """Thin, typed wrapper over the SQLite state file. Use as a context manager."""

    def __init__(self, path: Path) -> None:
        self.path = path
        if path != Path(":memory:"):
            path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(path))
        self._conn.row_factory = sqlite3.Row
        # Off by default per SQLite connection (not persisted in the file). trip_days.trip_id
        # is the first declared foreign key in this schema; without this, the REFERENCES clause
        # is decorative and a bogus trip_id would insert silently.
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._migrate()
        self._conn.commit()

    def _migrate(self) -> None:
        """Bring the database schema to CURRENT_SCHEMA_VERSION via PRAGMA user_version.

        A fresh database gets the whole current schema in one step. An existing one is
        lifted through the ordered migrations. A database from a *newer* truestill is refused
        rather than risked.
        """
        conn = self._conn
        version = int(conn.execute("PRAGMA user_version").fetchone()[0])

        if version > CURRENT_SCHEMA_VERSION:
            message = (
                f"catalog schema is version {version} but this truestill understands only "
                f"{CURRENT_SCHEMA_VERSION}; upgrade truestill to open it"
            )
            raise CatalogVersionError(message)

        table_exists = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'files'"
        ).fetchone()

        if table_exists is None:
            conn.executescript(_SCHEMA)
            conn.execute(f"PRAGMA user_version = {CURRENT_SCHEMA_VERSION}")
            return

        for target, migrate in _MIGRATIONS:
            if version < target:
                migrate(conn)
                conn.execute(f"PRAGMA user_version = {target}")

    @property
    def schema_version(self) -> int:
        return int(self._conn.execute("PRAGMA user_version").fetchone()[0])

    def get_setting(self, key: str) -> str | None:
        """Return a stored setting's value, or ``None`` if it was never set."""
        row = self._conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return None if row is None else str(row["value"])

    def set_setting(self, key: str, value: str) -> None:
        """Persist a setting, replacing any prior value for ``key``."""
        with self._tx() as conn:
            conn.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )

    # -- layout migration ----------------------------------------------------------------

    def copies_for_migration(self, drive_uuid: str) -> list[sqlite3.Row]:
        """Every copy on a drive with the fields needed to re-render its path under a template.

        Joins ``file_copies`` to ``files`` (category, captured_at, original_name), any named
        event (slug, start, **name**), and any confirmed trip whose day claims this file's own
        capture date (id, slug, the trip's own start, **name**) -- a day-keyed join against
        ``trip_days.day`` (its primary key), the same join `trip_for_day` uses, so a migration can
        recompute each copy's destination without re-reading the file. Both names are what make a
        readable folder possible on the migration path -- `slugify` is lossy, so neither can be
        rebuilt from its slug alone.
        """
        return list(
            self._conn.execute(
                """
                SELECT fc.sha256, fc.relative, fc.copy_sha256, f.category, f.captured_at,
                       f.original_name,
                       e.slug AS event_slug, e.start_date AS event_start, e.name AS event_name,
                       t.id AS trip_id, t.slug AS trip_slug, t.start_date AS trip_start,
                       t.name AS trip_name
                FROM file_copies fc
                JOIN files f ON f.sha256 = fc.sha256
                LEFT JOIN events e ON e.id = f.event_id
                LEFT JOIN trip_days td ON td.day = date(f.captured_at)
                LEFT JOIN trips t ON t.id = td.trip_id
                WHERE fc.drive_uuid = ?
                """,
                (drive_uuid,),
            )
        )

    def copy_relative(self, sha256: str, drive_uuid: str) -> str | None:
        """The relative path the catalog currently records for one copy, or ``None``."""
        row = self._conn.execute(
            "SELECT relative FROM file_copies WHERE sha256 = ? AND drive_uuid = ?",
            (sha256, drive_uuid),
        ).fetchone()
        return None if row is None else str(row["relative"])

    def camera_copies_for_events(self, drive_uuid: str) -> list[sqlite3.Row]:
        """Dated camera copies on a drive -- the clustering input for reviewing trips in place.

        Only the device rule's default ``Camera`` label is proposed as trips (by-device layouts
        are a follow-on); undated files carry no time to cluster on and are excluded.
        """
        return list(
            self._conn.execute(
                """
                SELECT fc.sha256, f.captured_at
                FROM file_copies fc
                JOIN files f ON f.sha256 = fc.sha256
                WHERE fc.drive_uuid = ? AND f.category = 'Camera' AND f.captured_at IS NOT NULL
                """,
                (drive_uuid,),
            )
        )

    def record_migration_moves(
        self, moves: list[tuple[str, str, str, str, str | None, str]]
    ) -> None:
        """Journal planned moves ``(sha256, drive, old, new, copy_sha256, run_id)`` before disk."""
        with self._tx() as conn:
            conn.executemany(
                """
                INSERT INTO migration_journal
                    (sha256, drive_uuid, old_relative, new_relative, copy_sha256, run_id)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(sha256, drive_uuid) DO UPDATE SET
                    old_relative = excluded.old_relative, new_relative = excluded.new_relative,
                    copy_sha256 = excluded.copy_sha256, run_id = excluded.run_id,
                    completed_at = NULL
                """,
                moves,
            )

    def pending_migration(self, drive_uuid: str) -> list[sqlite3.Row]:
        """Journalled moves for a drive that have **not** completed - an interrupted run.

        Completed rows stay in the table as the reversal record, so "pending" is now a state
        rather than mere presence: only rows without a ``completed_at`` are replayed forward.
        """
        return list(
            self._conn.execute(
                "SELECT sha256, drive_uuid, old_relative, new_relative, copy_sha256 "
                "FROM migration_journal WHERE drive_uuid = ? AND completed_at IS NULL",
                (drive_uuid,),
            )
        )

    def relocate_copy(self, sha256: str, drive_uuid: str, new_relative: str) -> None:
        """Point a copy at its new relative path (the authoritative location update)."""
        with self._tx() as conn:
            conn.execute(
                "UPDATE file_copies SET relative = ? WHERE sha256 = ? AND drive_uuid = ?",
                (new_relative, sha256, drive_uuid),
            )

    def complete_migration_move(self, sha256: str, drive_uuid: str) -> None:
        """Mark a move done. **The row is kept** -- it is the record undo reverses from.

        This used to delete the row, which made the journal a resume record that erased itself
        on success: a finished migration had nothing left to reverse. The row now survives until
        a later run of the same drive supersedes it, or undo consumes it.
        """
        with self._tx() as conn:
            conn.execute(
                "UPDATE migration_journal SET completed_at = ? WHERE sha256 = ? AND drive_uuid = ?",
                (_now(), sha256, drive_uuid),
            )

    def forget_migration_move(self, sha256: str, drive_uuid: str) -> None:
        """Drop a journal row once undo has put its file back -- the record is spent."""
        with self._tx() as conn:
            conn.execute(
                "DELETE FROM migration_journal WHERE sha256 = ? AND drive_uuid = ?",
                (sha256, drive_uuid),
            )

    def migrated_old_paths(self, drive_uuid: str) -> list[str]:
        """The paths a completed migration moved files OUT of - the cleanup's entire scope.

        Read from the journal rather than the filesystem on purpose: it is the only record of
        which folders truestill emptied, and cleaning anything else would be sweeping a user's
        drive for directories the tool never touched.
        """
        return [
            str(row["old_relative"])
            for row in self._conn.execute(
                "SELECT old_relative FROM migration_journal "
                "WHERE drive_uuid = ? AND completed_at IS NOT NULL",
                (drive_uuid,),
            )
        ]

    def start_migration_run(self, run_id: str, drive_uuid: str) -> None:
        """Open a run, superseding the previous one's journal for this drive.

        Superseding here rather than on a timer is what bounds growth: exactly one run's worth of
        reversal record exists per drive, and it is always the newest one -- so the only record
        that can be dropped is one a newer migration has already made meaningless.
        """
        with self._tx() as conn:
            conn.execute("DELETE FROM migration_journal WHERE drive_uuid = ?", (drive_uuid,))
            conn.execute("DELETE FROM migration_runs WHERE drive_uuid = ?", (drive_uuid,))
            conn.execute(
                "INSERT INTO migration_runs (run_id, drive_uuid, started_at) VALUES (?, ?, ?)",
                (run_id, drive_uuid, _now()),
            )

    def finish_migration_run(self, run_id: str) -> None:
        with self._tx() as conn:
            conn.execute(
                "UPDATE migration_runs SET completed_at = ? WHERE run_id = ?", (_now(), run_id)
            )

    def reversible_migration(self, drive_uuid: str) -> tuple[str, list[sqlite3.Row]] | None:
        """The newest run for a drive and its completed moves, newest move first.

        Reverse order matters: undo walks moves backwards so that a path freed by one reversal is
        available to the next, exactly as the forward run built them up.
        """
        run = self._conn.execute(
            "SELECT run_id FROM migration_runs WHERE drive_uuid = ? "
            "ORDER BY started_at DESC LIMIT 1",
            (drive_uuid,),
        ).fetchone()
        if run is None:
            return None
        rows = list(
            self._conn.execute(
                "SELECT * FROM migration_journal "
                "WHERE drive_uuid = ? AND completed_at IS NOT NULL "
                "ORDER BY completed_at DESC, rowid DESC",
                (drive_uuid,),
            )
        )
        return (str(run["run_id"]), rows) if rows else None

    # -- reclaim (space-safe source deletion) --------------------------------------------

    def reclaim_candidates(self, drive_uuid: str) -> list[sqlite3.Row]:
        """Source files whose content has a copy on ``drive_uuid``, for reclaim evaluation.

        Returns ``source_path, sha256, size, relative, copy_sha256`` (the copy on this drive, to
        re-verify) and ``copy_count`` (total copies of this content across all drives, for the
        min-copies redundancy check). The caller re-hashes the copy and confirms the source still
        exists before deleting anything.
        """
        return list(
            self._conn.execute(
                """
                SELECT f.source_path, f.sha256, f.size,
                       fc.relative, fc.copy_sha256,
                       (SELECT COUNT(*) FROM file_copies WHERE sha256 = f.sha256) AS copy_count
                FROM files f
                JOIN file_copies fc ON fc.sha256 = f.sha256 AND fc.drive_uuid = ?
                """,
                (drive_uuid,),
            )
        )

    def record_reclaim(self, source_path: str, sha256: str, freed_bytes: int) -> None:
        """Journal an imminent source deletion (written just before the unlink)."""
        with self._tx() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO reclaim_journal (source_path, sha256, freed_bytes, "
                "reclaimed_at) VALUES (?, ?, ?, ?)",
                (source_path, sha256, freed_bytes, _now()),
            )

    def clear_reclaim(self, source_path: str) -> None:
        """Clear a reclaim journal row once the source has been deleted."""
        with self._tx() as conn:
            conn.execute("DELETE FROM reclaim_journal WHERE source_path = ?", (source_path,))

    def pending_reclaim(self) -> list[sqlite3.Row]:
        """Reclaim journal rows left by an interrupted run (audit / resume)."""
        return list(
            self._conn.execute("SELECT source_path, sha256, freed_bytes FROM reclaim_journal")
        )

    # -- in-place relocation journal (undo) -----------------------------------------------

    def start_inplace_run(
        self, *, run_id: str, source_root: str, dest_root: str, drive_uuid: str | None
    ) -> None:
        """Open a relocation run. Written before the first rename, so a crash leaves a record."""
        with self._tx() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO inplace_runs (run_id, source_root, dest_root, "
                "drive_uuid, started_at, completed_at, status) VALUES (?, ?, ?, ?, ?, NULL, ?)",
                (run_id, source_root, dest_root, drive_uuid, _now(), "in_progress"),
            )

    def record_inplace_move(
        self, *, run_id: str, sha256: str, old_relative: str, new_relative: str
    ) -> None:
        """Journal one completed rename. Written immediately after the file has moved."""
        with self._tx() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO inplace_moves (run_id, sha256, old_relative, "
                "new_relative, moved_at) VALUES (?, ?, ?, ?, ?)",
                (run_id, sha256, old_relative, new_relative, _now()),
            )

    def finish_inplace_run(self, run_id: str, *, status: str = "completed") -> None:
        """Close a run. An interrupted run keeps ``in_progress`` and is still undoable."""
        with self._tx() as conn:
            conn.execute(
                "UPDATE inplace_runs SET status = ?, completed_at = ? WHERE run_id = ?",
                (status, _now(), run_id),
            )

    def discard_inplace_run(self, run_id: str) -> None:
        """Remove a run that moved nothing, so `undo-organize` never offers an empty run."""
        with self._tx() as conn:
            conn.execute("DELETE FROM inplace_moves WHERE run_id = ?", (run_id,))
            conn.execute("DELETE FROM inplace_runs WHERE run_id = ?", (run_id,))

    def inplace_runs(self) -> list[sqlite3.Row]:
        """Every recorded relocation run, newest first, with its move count."""
        return list(
            self._conn.execute(
                """
                SELECT r.run_id, r.source_root, r.dest_root, r.drive_uuid, r.started_at,
                       r.completed_at, r.status,
                       (SELECT COUNT(*) FROM inplace_moves m WHERE m.run_id = r.run_id) AS moves
                FROM inplace_runs r
                ORDER BY r.started_at DESC
                """
            )
        )

    def inplace_run(self, run_id: str) -> sqlite3.Row | None:
        """One run's header, or ``None`` if there is no such run."""
        cursor = self._conn.execute("SELECT * FROM inplace_runs WHERE run_id = ?", (run_id,))
        row: sqlite3.Row | None = cursor.fetchone()
        return row

    def latest_undoable_run(self) -> sqlite3.Row | None:
        """The most recent run that has not already been undone."""
        cursor = self._conn.execute(
            "SELECT * FROM inplace_runs WHERE status != 'undone' ORDER BY started_at DESC LIMIT 1"
        )
        row: sqlite3.Row | None = cursor.fetchone()
        return row

    def inplace_moves(self, run_id: str) -> list[sqlite3.Row]:
        """A run's moves in the order they happened; undo walks this reversed."""
        return list(
            self._conn.execute(
                "SELECT sha256, old_relative, new_relative FROM inplace_moves "
                "WHERE run_id = ? ORDER BY moved_at, old_relative",
                (run_id,),
            )
        )

    def confirm_date(
        self, sha256: str, captured_at: str, *, confirmed_by: str | None = None
    ) -> None:
        """Record a human-confirmed capture date for content, and apply it to its file row.

        Two writes, one transaction, and the pairing is the point. The confirmation table is the
        durable record - it survives an undo that deletes the ``files`` row. The ``files`` update
        is what makes every catalog-driven re-render (migrate-layout, a preset change) place the
        file by the confirmed date instead of the evidence it was originally filed under, which
        is (ii)'s actual requirement: a rescue that a later whole-disk operation reverts has not
        happened.

        Re-confirming the same content overwrites: a person is allowed to change their mind, and
        the newest human answer is the answer. **O(1)**, two indexed writes.
        """
        with self._tx() as conn:
            conn.execute(
                "INSERT INTO date_confirmations (sha256, captured_at, confirmed_at, confirmed_by)"
                " VALUES (?, ?, ?, ?) ON CONFLICT(sha256) DO UPDATE SET"
                " captured_at = excluded.captured_at, confirmed_at = excluded.confirmed_at,"
                " confirmed_by = excluded.confirmed_by",
                (sha256, captured_at, _now(), confirmed_by),
            )
            conn.execute(
                "UPDATE files SET captured_at = ?, date_source = ?, date_tag = NULL"
                " WHERE sha256 = ?",
                (captured_at, DateSource.HUMAN_CONFIRMED.value, sha256),
            )

    def confirmations_to_bake(self, drive_uuid: str) -> list[sqlite3.Row]:
        """Confirmed dates whose copy is on this drive and is not yet written into the bytes.

        Returns ``sha256, captured_at, relative``. Driven by **this drive's**
        ``file_copies.date_baked_at IS NULL``, so a re-run picks up exactly what is left on
        *this* drive - which is also what makes the bake resumable, and what makes a second
        drive's copies still pending after the first drive has been done.

        **Complexity: O(confirmations on this drive)**, one indexed join. No I/O.
        """
        return list(
            self._conn.execute(
                """
                SELECT dc.sha256, dc.captured_at, fc.relative
                FROM date_confirmations dc
                JOIN file_copies fc ON fc.sha256 = dc.sha256
                WHERE fc.drive_uuid = ? AND fc.date_baked_at IS NULL
                ORDER BY fc.relative
                """,
                (drive_uuid,),
            )
        )

    def drives_awaiting_bake(self, exclude_drive_uuid: str) -> list[sqlite3.Row]:
        """Other drives holding copies whose confirmed date is not yet in their bytes.

        Returns ``label, files`` per drive, so a report can **name** them rather than counting
        them - the same courtesy `migrate` and `reclaim` already extend when they cannot reach a
        drive. "3 other drives" tells a user there is work left; "Backup 2019 and The Memory
        Cabinet" tells them which two to plug in.

        **Complexity: O(unbaked copies)**, one indexed join and a group-by. No I/O.
        """
        return list(
            self._conn.execute(
                """
                SELECT d.uuid AS uuid, d.label AS label, COUNT(*) AS files
                FROM date_confirmations dc
                JOIN file_copies fc ON fc.sha256 = dc.sha256
                JOIN drives d ON d.uuid = fc.drive_uuid
                WHERE fc.drive_uuid != ? AND fc.date_baked_at IS NULL
                GROUP BY d.uuid, d.label
                ORDER BY d.label
                """,
                (exclude_drive_uuid,),
            )
        )

    def record_bake(self, sha256: str, drive_uuid: str, *, copy_sha256: str) -> None:
        """**O1: the new copy hash and the bake record land in ONE transaction.**

        This is the obligation the whole feature turns on. If the bytes are rewritten and the
        recorded hash is not updated with them, `verify` compares the new file against the old
        digest and tells the user their photo is damaged - **a tool reporting corruption on a
        file it rewrote itself**, which destroys the trust `verify` exists to build. Splitting
        these into two statements would leave a crash between them doing exactly that.

        ``copy_sha256`` must be read back from the file **on the drive** after the write, never
        from a staged copy and never from what exiftool reported - see `service.bake`.
        """
        with self._tx() as conn:
            conn.execute(
                "UPDATE file_copies SET copy_sha256 = ?, date_baked_at = ? "
                "WHERE sha256 = ? AND drive_uuid = ?",
                (copy_sha256, _now(), sha256, drive_uuid),
            )

    def confirmed_date(self, sha256: str) -> str | None:
        """The human-confirmed capture date for content, or ``None``. **O(1)** on the key."""
        row = self._conn.execute(
            "SELECT captured_at FROM date_confirmations WHERE sha256 = ?", (sha256,)
        ).fetchone()
        return str(row["captured_at"]) if row is not None else None

    def forget_organized(self, sha256: str, drive_uuid: str | None) -> None:
        """Forget that content was organized: drop this drive's copy, and the file row with it
        when no copy remains anywhere.

        The second half is what keeps an undo honest. ``files`` is the dedup index, so a row
        left behind after its only copy moved back would make the content still look organized
        -- and a re-organize would skip every restored file as an exact duplicate. That is an
        undo which quietly leaves the library un-organizable, which is worse than no undo.

        ``drive_uuid`` is ``None`` when the destination was not an identified drive; there is
        then no copy row to drop and the file row goes on the same "nothing holds it" test.
        """
        with self._tx() as conn:
            if drive_uuid is not None:
                conn.execute(
                    "DELETE FROM file_copies WHERE sha256 = ? AND drive_uuid = ?",
                    (sha256, drive_uuid),
                )
            remaining = conn.execute(
                "SELECT COUNT(*) FROM file_copies WHERE sha256 = ?", (sha256,)
            ).fetchone()[0]
            if not remaining:
                conn.execute("DELETE FROM files WHERE sha256 = ?", (sha256,))

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        self._conn.close()

    @contextmanager
    def _tx(self) -> Iterator[sqlite3.Connection]:
        try:
            yield self._conn
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise

    # -- reads ---------------------------------------------------------------------

    def seed_rows(self) -> list[tuple[str, str, str | None]]:
        """Return ``(source_path, sha256, perceptual)`` for every known file.

        This is exactly the shape :meth:`DedupIndex.from_catalog_rows` consumes.
        """
        cursor = self._conn.execute("SELECT source_path, sha256, perceptual FROM files")
        return [(row["source_path"], row["sha256"], row["perceptual"]) for row in cursor]

    def organized_files(self) -> list[sqlite3.Row]:
        """Every organized file with the relative path it was written to.

        Used to attach an already-organized library to a drive that was registered after the
        fact: the rows say where each copy *should* be, and the caller confirms it is really
        there before recording it.
        """
        return list(
            self._conn.execute(
                "SELECT sha256, copy_sha256, size, relative FROM files "
                "WHERE upload_status = 'uploaded'"
            )
        )

    def attachable_hashes(self) -> list[sqlite3.Row]:
        """``(hash, sha256)`` for every digest a copy of an organized file can present on disk.

        Used to attach a drive by reading it rather than by trusting a remembered path. A
        copy is **not** always byte-identical to its source: the Takeout bake rewrites metadata,
        so that copy hashes to its own ``copy_sha256`` and would be unrecognisable if only
        ``files.sha256`` were matched. Every recorded copy digest is therefore an accepted
        identity for the same content.

        **Complexity: O(n)** over files plus copies, one scan each, no I/O.
        """
        return list(
            self._conn.execute(
                """
                SELECT sha256 AS hash, sha256 FROM files WHERE upload_status = 'uploaded'
                UNION
                SELECT copy_sha256 AS hash, sha256 FROM files WHERE copy_sha256 IS NOT NULL
                UNION
                SELECT copy_sha256 AS hash, sha256 FROM file_copies WHERE copy_sha256 IS NOT NULL
                """
            )
        )

    def organized_sizes(self) -> dict[str, int | None]:
        """``{sha256: size}`` for organized files, so attach can report a scale before reading."""
        return {
            str(row["sha256"]): row["size"]
            for row in self._conn.execute(
                "SELECT sha256, size FROM files WHERE upload_status = 'uploaded'"
            )
        }

    def find_by_sha256(self, sha256: str) -> sqlite3.Row | None:
        cursor = self._conn.execute("SELECT * FROM files WHERE sha256 = ?", (sha256,))
        row: sqlite3.Row | None = cursor.fetchone()
        return row

    def count(self) -> int:
        return int(self._conn.execute("SELECT COUNT(*) FROM files").fetchone()[0])

    def stats_summary(self) -> sqlite3.Row:
        """Library-level custody and completeness totals from aggregate SQL only.

        Complexity: O(n) over ``files`` and ``file_copies`` once each, with grouped aggregates.
        No per-file Python loops.
        """
        row: sqlite3.Row | None = self._conn.execute(
            """
            WITH copy_rollup AS (
                SELECT
                    sha256,
                    COUNT(*) AS copies,
                    MAX(CASE WHEN last_verified IS NOT NULL THEN 1 ELSE 0 END) AS any_verified
                FROM file_copies
                GROUP BY sha256
            )
            SELECT
                COUNT(*) AS total_files,
                COALESCE(SUM(size), 0) AS total_size,
                COALESCE(SUM(CASE WHEN captured_at IS NULL THEN 1 ELSE 0 END), 0) AS undated_files,
                COALESCE(SUM(CASE WHEN captured_at IS NOT NULL AND category = 'Camera' THEN 1 ELSE 0 END), 0) AS timeline_files,
                COALESCE(SUM(CASE WHEN captured_at IS NULL OR category != 'Camera' THEN 1 ELSE 0 END), 0) AS side_bin_files,
                MIN(captured_at) AS oldest_capture,
                MAX(captured_at) AS newest_capture,
                COALESCE(SUM(CASE WHEN COALESCE(cr.copies, 0) >= 2 THEN 1 ELSE 0 END), 0) AS files_on_two_plus_drives,
                COALESCE(SUM(CASE WHEN COALESCE(cr.copies, 0) = 1 THEN 1 ELSE 0 END), 0) AS files_on_one_drive,
                COALESCE(SUM(CASE WHEN COALESCE(cr.copies, 0) = 0 THEN 1 ELSE 0 END), 0) AS files_on_zero_drives,
                COALESCE(SUM(CASE WHEN COALESCE(cr.any_verified, 0) = 0 THEN 1 ELSE 0 END), 0) AS never_verified_files
            FROM files f
            LEFT JOIN copy_rollup cr ON cr.sha256 = f.sha256
            """
        ).fetchone()
        if row is None:
            message = "stats summary query returned no row"
            raise RuntimeError(message)
        return row

    def stats_date_provenance(self) -> list[sqlite3.Row]:
        """Counts per (date_source, date_tag). **O(n)** single grouped scan; reads no files.

        NULL ``date_source`` is returned as its own group rather than filtered out: on a library
        organized before v13 it is every row, so hiding it would make the view claim a confident
        breakdown of nothing.
        """
        return list(
            self._conn.execute(
                "SELECT date_source, date_tag, COUNT(*) AS files FROM files "
                "GROUP BY date_source, date_tag ORDER BY files DESC"
            )
        )

    def stats_by_year(self) -> list[sqlite3.Row]:
        """Captured-file counts by year from SQL grouping.

        Complexity: O(n) grouped by ``substr(captured_at, 1, 4)``.
        """
        return list(
            self._conn.execute(
                """
                SELECT substr(captured_at, 1, 4) AS year, COUNT(*) AS count
                FROM files
                WHERE captured_at IS NOT NULL
                GROUP BY year
                ORDER BY year
                """
            )
        )

    def stats_near_duplicate_flagged_count(self) -> int:
        """How many catalog files are in a perceptual-hash collision group.

        This is a cheap, indexed proxy for "near-duplicates flagged": ``idx_files_perceptual``
        powers the grouping and no image bytes are read.
        """
        row = self._conn.execute(
            """
            SELECT COALESCE(SUM(group_count), 0) AS total
            FROM (
                SELECT COUNT(*) AS group_count
                FROM files
                WHERE perceptual IS NOT NULL
                GROUP BY perceptual
                HAVING COUNT(*) > 1
            )
            """
        ).fetchone()
        return int(row["total"] if row is not None else 0)

    def stats_undated_samples(self, *, limit: int = 12) -> list[sqlite3.Row]:
        """A small, actionable sample of undated files for the UI."""
        return list(
            self._conn.execute(
                """
                SELECT original_name, source_path, relative
                FROM files
                WHERE captured_at IS NULL
                ORDER BY processed_at DESC
                LIMIT ?
                """,
                (limit,),
            )
        )

    def stats_counts_by_format(self, extensions: Collection[str]) -> dict[str, int]:
        """How many catalog files match each media extension (one aggregate SQL pass).

        ``extensions`` is the caller's media set (e.g. ``MEDIA_EXTENSIONS``); Catalog does not
        own the taxonomy. Empty / blank names are ignored. Ordered by count desc, then ext.
        """
        normalized = sorted({ext.lstrip(".").lower() for ext in extensions if ext.strip()})
        case_parts: list[str] = []
        params: list[str] = []
        for ext in normalized:
            case_parts.append("WHEN name LIKE ? THEN ?")
            params.extend([f"%.{ext}", ext])
        row_sql = "\n".join(case_parts) if case_parts else "ELSE ''"
        sql = f"""
            WITH named AS (
                SELECT lower(COALESCE(original_name, relative, source_path, '')) AS name
                FROM files
            )
            SELECT ext, COUNT(*) AS count
            FROM (
                SELECT CASE
                    {row_sql}
                    ELSE ''
                END AS ext
                FROM named
            )
            WHERE ext != ''
            GROUP BY ext
            ORDER BY count DESC, ext
        """
        rows = self._conn.execute(sql, params).fetchall()
        return {str(row["ext"]): int(row["count"]) for row in rows}

    def stats_zero_drive_samples(self, *, limit: int = 12) -> list[str]:
        """Display names of files that have no ``file_copies`` row (nowhere on a drive)."""
        rows = self._conn.execute(
            """
            SELECT COALESCE(original_name, sha256) AS name
            FROM files f
            WHERE NOT EXISTS (
                SELECT 1 FROM file_copies fc WHERE fc.sha256 = f.sha256
            )
            ORDER BY processed_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [str(row["name"]) for row in rows]

    def clear_setting(self, key: str) -> None:
        """Remove a setting, so "absent" and "explicitly empty" never diverge.

        Switching between layouts must be able to *unset* the evented-timeline override, not
        just overwrite it -- a stale override left behind would keep sending events somewhere
        the newly-chosen preset does not put them.
        """
        with self._tx() as conn:
            conn.execute("DELETE FROM settings WHERE key = ?", (key,))

    def has_placed_files(self) -> bool:
        """Whether this catalog has ever actually *placed* a file on disk.

        The signal is a `files` row with ``upload_status = 'uploaded'``, because
        :meth:`record_uploaded` is the only path that inserts one and it is reached only under
        ``apply=True``. Deliberately **not** "the catalog has rows": a scan, a preview or an
        event-review session writes `events`, `skipped_clusters`, `settings` and `drives`
        without a single file being written, and such a library has no layout worth protecting.

        Nor is `file_copies` the signal, despite being the authoritative location record -
        organizing into a plain folder that carries no drive marker places files without
        recording a copy row, so a non-empty `files` table is the wider and correct test.
        """
        return (
            self._conn.execute(
                "SELECT 1 FROM files WHERE upload_status = 'uploaded' LIMIT 1"
            ).fetchone()
            is not None
        )

    def media_names(self) -> list[str]:
        """Every file's name (original if known, else its stored path) for format classification."""
        cursor = self._conn.execute("SELECT COALESCE(original_name, relative) AS n FROM files")
        return [str(row["n"]) for row in cursor]

    def copy_names_by_drive(self) -> list[sqlite3.Row]:
        """``(drive_uuid, relative)`` for every recorded copy, to split per-drive counts by format."""
        return list(self._conn.execute("SELECT drive_uuid, relative FROM file_copies"))

    def known_sizes(self) -> frozenset[int]:
        """Byte sizes of all catalogued files, for the scan's size pre-filter.

        A new file whose size matches a catalogued one must be SHA-256'd so cross-run exact
        duplicates are still caught; a size absent here and unique in-scan can skip hashing.
        """
        cursor = self._conn.execute("SELECT DISTINCT size FROM files WHERE size IS NOT NULL")
        return frozenset(int(row["size"]) for row in cursor)

    # -- drives & copies (reads) ---------------------------------------------------

    def list_drives(self) -> list[sqlite3.Row]:
        """Known drives with their copy counts and total bytes (largest label set aside)."""
        return list(
            self._conn.execute(
                """
                SELECT d.*, COUNT(fc.sha256) AS file_count, COALESCE(SUM(fc.size), 0) AS total_size
                FROM drives d
                LEFT JOIN file_copies fc ON fc.drive_uuid = d.uuid
                GROUP BY d.uuid
                ORDER BY d.label
                """
            )
        )

    def copies_on_drive(self, drive_uuid: str) -> list[sqlite3.Row]:
        """Every recorded copy on a drive: ``sha256, relative, copy_sha256, size``."""
        return list(
            self._conn.execute(
                "SELECT sha256, relative, copy_sha256, size FROM file_copies WHERE drive_uuid = ?",
                (drive_uuid,),
            )
        )

    #: Rows per page of search results. Chosen to be scannable rather than exhaustive: at a
    #: glance a person is looking for *one* file, and a page longer than a screenful is scrolled
    #: past rather than read. Mainstream file managers and photo tools settle in the 25-100 band
    #: (Explorer and Finder paginate by viewport; Immich and PhotoPrism default to grids of this
    #: order), and 50 sits mid-band: two or three scrolls at a typical window height, and small
    #: enough that the count line beneath it stays meaningful.
    FIND_PAGE_SIZE = 50

    def count_copies(self, term: str) -> int:
        """How many copies match ``term``, for the page count. One indexed scan, no rows built."""
        like = f"%{term}%"
        row = self._conn.execute(
            """
            SELECT COUNT(*)
            FROM file_copies fc
            JOIN files f ON f.sha256 = fc.sha256
            JOIN drives d ON d.uuid = fc.drive_uuid
            WHERE f.original_name LIKE ? OR fc.relative LIKE ? OR f.source_path LIKE ?
            """,
            (like, like, like),
        ).fetchone()
        return int(row[0])

    def find_copies_query(
        self, term: str, *, limit: int | None = None, offset: int = 0
    ) -> tuple[str, list[object]]:
        """SQL + params for :meth:`find_copies`.

        Exposed so the paging guard can ``EXPLAIN`` the statement that actually ships, not a
        retyped twin that could drift (audit F11).
        """
        like = f"%{term}%"
        sql = """
            SELECT f.original_name, f.source_path, fc.relative, fc.last_verified,
                   d.label AS drive_label, d.uuid AS drive_uuid
            FROM file_copies fc
            JOIN files f ON f.sha256 = fc.sha256
            JOIN drives d ON d.uuid = fc.drive_uuid
            WHERE f.original_name LIKE ? OR fc.relative LIKE ? OR f.source_path LIKE ?
            ORDER BY f.original_name, d.label
        """
        params: list[object] = [like, like, like]
        if limit is not None:
            sql += " LIMIT ? OFFSET ?"
            params += [limit, offset]
        return sql, params

    def find_copies(
        self, term: str, *, limit: int | None = None, offset: int = 0
    ) -> list[sqlite3.Row]:
        """For ``where``: copies whose original name, relative path or source path match ``term``.

        **Paged in SQL, not in Python.** ``LIMIT``/``OFFSET`` go to SQLite so a page costs one
        page of rows; fetching everything and slicing would build the whole result set in memory
        on every keystroke, which is the shape that only hurts once a library is large. ``limit``
        of ``None`` keeps the unpaged behaviour for callers that genuinely want every row.
        """
        sql, params = self.find_copies_query(term, limit=limit, offset=offset)
        return list(self._conn.execute(sql, params))

    def single_copy_shas(self) -> list[sqlite3.Row]:
        """For ``status``: content that exists on exactly one drive (a single point of loss)."""
        return list(
            self._conn.execute(
                """
                SELECT fc.sha256, f.original_name, d.label AS drive_label
                FROM file_copies fc
                JOIN files f ON f.sha256 = fc.sha256
                JOIN drives d ON d.uuid = fc.drive_uuid
                WHERE fc.sha256 IN (SELECT sha256 FROM file_copies GROUP BY sha256 HAVING COUNT(*) = 1)
                ORDER BY f.original_name
                """
            )
        )

    def single_copy_count(self) -> int:
        """How many files exist on exactly one drive -- the number, without the names.

        The custody strip refreshes on every screen and only ever renders this count, but was
        calling :meth:`single_copy_shas`, which joins to two tables and sorts every at-risk row
        by name so it can throw all of it away. Measured at 100k files that was 425 ms per
        refresh against 27 ms here. Same question, asked directly.

        Equivalent to ``len(single_copy_shas())``: both count sha256 values with exactly one
        row in ``file_copies``, and `test_single_copy_count_matches_the_listing` holds them
        together so the cheap answer cannot drift from the detailed one.
        """
        cursor = self._conn.execute(
            "SELECT COUNT(*) FROM "
            "(SELECT sha256 FROM file_copies GROUP BY sha256 HAVING COUNT(*) = 1)"
        )
        return int(cursor.fetchone()[0])

    def event_by_signature(self, signature: str) -> sqlite3.Row | None:
        """A previously-named event with this cluster signature, if any."""
        cursor = self._conn.execute("SELECT * FROM events WHERE signature = ?", (signature,))
        row: sqlite3.Row | None = cursor.fetchone()
        return row

    def sample_relative_for_event(self, event_id: int, drive_uuid: str) -> str | None:
        """One copy's current relative path for a named event, on a drive.

        Any one file suffices: every file sharing an event id renders under the same event
        folder, so the caller takes this row's *parent* directory as the trip's real folder --
        it is only ever asked for right after a migration has placed the files there, so the
        path is current, not stale. Returns `None` when the event has no copy on this drive
        (nothing to show). One indexed lookup, `O(1)`.
        """
        row = self._conn.execute(
            """
            SELECT fc.relative FROM file_copies fc
            JOIN files f ON f.sha256 = fc.sha256
            WHERE f.event_id = ? AND fc.drive_uuid = ?
            LIMIT 1
            """,
            (event_id, drive_uuid),
        ).fetchone()
        return str(row["relative"]) if row is not None else None

    def sample_relative_for_trip(self, trip_id: int, drive_uuid: str) -> str | None:
        """One copy's current relative path for a confirmed trip, on a drive.

        Mirrors :meth:`sample_relative_for_event`, day-keyed instead of event-keyed: every file
        whose capture day the trip claims renders under the same trip header (§2's day-claim
        rule), so any one suffices. Returns `None` when the trip has no copy on this drive. One
        indexed join, `O(1)` (``trip_days.day`` is the primary key).
        """
        row = self._conn.execute(
            """
            SELECT fc.relative FROM file_copies fc
            JOIN files f ON f.sha256 = fc.sha256
            JOIN trip_days td ON td.day = date(f.captured_at)
            WHERE td.trip_id = ? AND fc.drive_uuid = ?
            LIMIT 1
            """,
            (trip_id, drive_uuid),
        ).fetchone()
        return str(row["relative"]) if row is not None else None

    def skipped_signatures(self) -> frozenset[str]:
        """Cluster signatures the user chose to skip on a previous run."""
        cursor = self._conn.execute("SELECT signature FROM skipped_clusters")
        return frozenset(row["signature"] for row in cursor)

    def trip_for_day(self, day: str) -> int | None:
        """The trip a day is already claimed by, if any -- the name-once lookup.

        One indexed lookup on `trip_days.day`'s primary key, O(1). A day present here is
        claimed regardless of which trip; the caller (a later stage) decides what silence means.
        """
        row = self._conn.execute("SELECT trip_id FROM trip_days WHERE day = ?", (day,)).fetchone()
        return int(row["trip_id"]) if row is not None else None

    def unevented_timeline_captured_ats(self) -> list[str]:
        """ISO capture timestamps for Everyday density counting (Camera, no event, no trip day).

        One SQL pass. Callers feed the strings (or parsed datetimes) into
        :func:`truestill_core.layout.count_capture_days` together with the current run's
        un-evented members. ``category = 'Camera'`` matches the default device-rule label;
        ``--by-device`` libraries that rename the timeline label are a follow-up.
        """
        rows = self._conn.execute(
            """
            SELECT f.captured_at
            FROM files f
            LEFT JOIN trip_days td ON td.day = date(f.captured_at)
            WHERE f.captured_at IS NOT NULL
              AND f.event_id IS NULL
              AND td.day IS NULL
              AND f.category = 'Camera'
            """
        ).fetchall()
        return [str(row["captured_at"]) for row in rows]

    # -- writes --------------------------------------------------------------------

    def record_event(
        self, *, name: str, slug: str, start_date: str, file_count: int, signature: str
    ) -> int:
        """Record a named event (idempotent on signature) and return its id."""
        with self._tx() as conn:
            conn.execute(
                """
                INSERT INTO events (name, slug, start_date, file_count, signature)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(signature) DO UPDATE SET
                    name = excluded.name, slug = excluded.slug,
                    start_date = excluded.start_date, file_count = excluded.file_count
                """,
                (name, slug, start_date, file_count, signature),
            )
        row = self._conn.execute(
            "SELECT id FROM events WHERE signature = ?", (signature,)
        ).fetchone()
        return int(row["id"])

    def set_event_id(self, shas: list[str], event_id: int) -> None:
        """Link each content hash to a named event, so a migration places it under the event folder."""
        if not shas:
            return
        placeholders = ",".join("?" for _ in shas)
        with self._tx() as conn:
            conn.execute(
                f"UPDATE files SET event_id = ? WHERE sha256 IN ({placeholders})",
                (event_id, *shas),
            )

    def create_trip(
        self, *, name: str, slug: str, start_date: str, end_date: str, days: Sequence[str]
    ) -> int:
        """Insert a new trip and its claimed days in one transaction. Returns the new trip's id.

        Identity is the row -- never a membership hash. Unlike `events.signature` (a hash of
        member SHA-256s, which moves the moment membership changes), a trip's id is stable across
        every edge adjustment and every re-ingest; `update_trip_days` is how membership changes,
        and it never touches this id. See `trip-grouping-research.md` §6.

        Does not check `trip_for_day` itself -- name-once is the caller's decision to make before
        calling this, not a rule this method enforces. `trip_days.day`'s primary key still refuses
        a day already claimed by another trip outright, so a caller that skips the check fails
        loudly (`sqlite3.IntegrityError`) rather than silently double-booking a day.
        """
        if not days:
            message = "a trip must claim at least one day"
            raise ValueError(message)
        with self._tx() as conn:
            cursor = conn.execute(
                "INSERT INTO trips (name, slug, start_date, end_date) VALUES (?, ?, ?, ?)",
                (name, slug, start_date, end_date),
            )
            new_id = cursor.lastrowid
            if new_id is None:
                message = "insert into trips did not return a rowid"
                raise RuntimeError(message)
            conn.executemany(
                "INSERT INTO trip_days (day, trip_id) VALUES (?, ?)",
                [(day, new_id) for day in days],
            )
        return int(new_id)

    def update_trip_days(self, trip_id: int, days: Sequence[str]) -> None:
        """Replace a trip's claimed days -- an edge adjustment, never a new identity.

        `trip_id`, `name` and `slug` are untouched; only membership changes, which is the whole
        point (§6: an edge trim or an added day must not orphan the name). `start_date`/
        `end_date` on the `trips` row are refreshed to the new membership's min/max so the row
        never claims a span it no longer covers -- left stale, they would silently lie about
        what the trip currently spans.
        """
        if not days:
            message = "a trip must claim at least one day"
            raise ValueError(message)
        ordered = sorted(days)
        with self._tx() as conn:
            conn.execute("DELETE FROM trip_days WHERE trip_id = ?", (trip_id,))
            conn.executemany(
                "INSERT INTO trip_days (day, trip_id) VALUES (?, ?)",
                [(day, trip_id) for day in ordered],
            )
            conn.execute(
                "UPDATE trips SET start_date = ?, end_date = ? WHERE id = ?",
                (ordered[0], ordered[-1], trip_id),
            )

    def record_skip(self, signature: str) -> None:
        """Remember that the user skipped this cluster, so it is not re-proposed unchanged."""
        with self._tx() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO skipped_clusters (signature, skipped_at) VALUES (?, ?)",
                (signature, _now()),
            )

    def upsert_drive(self, *, uuid: str, label: str) -> None:
        """Record a drive (idempotent on uuid), setting first_seen once and refreshing last_seen."""
        now = _now()
        with self._tx() as conn:
            conn.execute(
                """
                INSERT INTO drives (uuid, label, first_seen, last_seen)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(uuid) DO UPDATE SET label = excluded.label, last_seen = excluded.last_seen
                """,
                (uuid, label, now, now),
            )

    def set_drive_verified(self, uuid: str, when: str) -> None:
        """Roll up the drive-level last_verified convenience timestamp."""
        with self._tx() as conn:
            conn.execute("UPDATE drives SET last_verified = ? WHERE uuid = ?", (when, uuid))

    def record_copy(
        self,
        *,
        sha256: str,
        drive_uuid: str,
        relative: str,
        copy_sha256: str | None,
        size: int | None,
    ) -> None:
        """Record (idempotent on (sha256, drive_uuid)) that a copy lives on a drive."""
        with self._tx() as conn:
            conn.execute(
                """
                INSERT INTO file_copies (sha256, drive_uuid, relative, copy_sha256, size, copied_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(sha256, drive_uuid) DO UPDATE SET
                    relative = excluded.relative, copy_sha256 = excluded.copy_sha256,
                    size = excluded.size, copied_at = excluded.copied_at
                """,
                (sha256, drive_uuid, relative, copy_sha256, size, _now()),
            )

    def mark_copy_verified(self, *, sha256: str, drive_uuid: str, when: str) -> None:
        with self._tx() as conn:
            conn.execute(
                "UPDATE file_copies SET last_verified = ? WHERE sha256 = ? AND drive_uuid = ?",
                (when, sha256, drive_uuid),
            )

    def record_uploaded(
        self,
        *,
        source_path: str,
        original_name: str,
        sha256: str,
        copy_sha256: str | None = None,
        perceptual: str | None,
        size: int | None,
        captured_at: str | None,
        category: str,
        relative: str,
        event_id: int | None = None,
        albums: Sequence[str] = (),
        drive_uuid: str | None = None,
        date_source: str | None = None,
        date_tag: str | None = None,
    ) -> int:
        """Insert (or refresh) a row marking a file as processed and uploaded; return its id.

        ``sha256`` is the source (pre-write) content hash and the dedup identity;
        ``copy_sha256`` is the organized copy's hash after any Takeout metadata write (equal to
        ``sha256`` for the byte-identical normal pipeline). When ``drive_uuid`` is given, the copy
        is also recorded in ``file_copies`` (per-content-per-drive), the authoritative location
        record. Writing ``copy_sha256`` to **both** places is deliberate and load-bearing: the
        per-drive row is the authoritative one, and the ``files`` row is what survives a lost
        drive row so a baked copy can still be recognised on re-attach (see
        :func:`_add_drive_tables`). ``files.relative`` remains a name fallback only, never a
        location. Album membership is linked many-to-many. Idempotent on ``sha256``.
        """
        now = _now()
        with self._tx() as conn:
            conn.execute(
                """
                INSERT INTO files (
                    source_path, original_name, sha256, copy_sha256, perceptual, size,
                    captured_at, category, relative, event_id, upload_status, processed_at,
                    uploaded_at, date_source, date_tag
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'uploaded', ?, ?, ?, ?)
                ON CONFLICT(sha256) DO UPDATE SET
                    source_path   = excluded.source_path,
                    original_name = excluded.original_name,
                    copy_sha256   = excluded.copy_sha256,
                    perceptual    = excluded.perceptual,
                    size          = excluded.size,
                    captured_at   = excluded.captured_at,
                    category      = excluded.category,
                    relative      = excluded.relative,
                    event_id      = excluded.event_id,
                    upload_status = 'uploaded',
                    uploaded_at   = excluded.uploaded_at,
                    date_source   = excluded.date_source,
                    date_tag      = excluded.date_tag
                """,
                (
                    source_path,
                    original_name,
                    sha256,
                    copy_sha256,
                    perceptual,
                    size,
                    captured_at,
                    category,
                    relative,
                    event_id,
                    now,
                    now,
                    date_source,
                    date_tag,
                ),
            )
            # A human confirmation outranks machine derivation permanently, so an ordinary
            # re-run must not quietly undo one. `record_uploaded` upserts and refreshes
            # date_source, which is right for every other row and exactly wrong for a confirmed
            # one - measured: without this, a re-ingest reverted a confirmed 2011 date to the
            # 2014 filename evidence, and the next migrate-layout would have re-rendered the
            # file back. Same transaction, one indexed lookup on the primary key.
            conn.execute(
                "UPDATE files SET captured_at = ("
                "  SELECT captured_at FROM date_confirmations WHERE sha256 = files.sha256"
                "), date_source = ?, date_tag = NULL"
                " WHERE sha256 = ?"
                " AND EXISTS (SELECT 1 FROM date_confirmations WHERE sha256 = ?)",
                (DateSource.HUMAN_CONFIRMED.value, sha256, sha256),
            )
            row = conn.execute("SELECT id FROM files WHERE sha256 = ?", (sha256,)).fetchone()
            file_id = int(row["id"])
            for album in albums:
                conn.execute("INSERT OR IGNORE INTO albums (name) VALUES (?)", (album,))
                album_row = conn.execute(
                    "SELECT id FROM albums WHERE name = ?", (album,)
                ).fetchone()
                conn.execute(
                    "INSERT OR IGNORE INTO file_albums (file_id, album_id) VALUES (?, ?)",
                    (file_id, int(album_row["id"])),
                )
            if drive_uuid is not None:
                conn.execute(
                    """
                    INSERT INTO file_copies (sha256, drive_uuid, relative, copy_sha256, size, copied_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(sha256, drive_uuid) DO UPDATE SET
                        relative = excluded.relative, copy_sha256 = excluded.copy_sha256,
                        size = excluded.size, copied_at = excluded.copied_at
                    """,
                    (sha256, drive_uuid, relative, copy_sha256, size, now),
                )
        return file_id
