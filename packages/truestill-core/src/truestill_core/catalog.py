"""Persistent record of every file the pipeline has processed.

A single SQLite file (stdlib ``sqlite3``, no server, no extra setup). It exists so runs
are **idempotent and resumable**: a file processed and uploaded once is recognised on the
next run and neither re-hashed for a decision nor re-uploaded. It also feeds the dedup
index, so exact/perceptual matches are found against the whole history, not just the
current run.

One row per processed source file, keyed by SHA-256.
"""

from __future__ import annotations

import contextlib
import os
import sqlite3
from collections import Counter
from collections.abc import Callable, Collection, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType
from typing import Self, cast

from truestill_core import catalog_backup
from truestill_core.catalog_busy import CatalogUnwritableError
from truestill_core.models import CaptureContext, DateSource


@dataclass(frozen=True, slots=True)
class DriveHolding:
    """One drive and how much of a queried content set it physically holds.

    See :meth:`Catalog.drives_holding`. ``files`` counts distinct CONTENT, so two source files
    with the same bytes count once - the drive holds one copy of them.
    """

    drive_uuid: str
    label: str
    files: int


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
    date_tag      TEXT,
    -- (kk): read during categorisation and the event jump-cut, and until v17 discarded.
    -- Coordinates are signed decimal degrees; NULL means the file carries no location, and
    -- 0.0 means the equator or the prime meridian, which is a real answer.
    camera_make   TEXT,
    camera_model  TEXT,
    lens_model    TEXT,
    gps_latitude  REAL,
    gps_longitude REAL
);
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
    -- When we LOOKED for this copy on a drive that identified itself, and it was not there.
    -- NULL means "not known to be absent", which is the ordinary state and is NOT a claim that
    -- the copy is present -- that claim needs last_verified. `(abg)`.
    --
    -- The row survives, deliberately. It is the record that content was once written here, and
    -- it is the only clue left to what happened; deleting it would answer "where did my 2,269
    -- files go?" with silence. Absence is remembered, never acted on.
    missing_at    TEXT,
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

-- ⚠ **AN INTENT LOG, NOT A LOG OF COMPLETED MOVES**, and the distinction is the whole of
-- `(agk)`. The row is written BEFORE the rename, because a journal that records only finished
-- work cannot cover the window in which the work happens - measured at 25% of crashes, with a
-- real photograph left displaced and `undo-organize` reporting success.
--
-- ⚠ `outcome` IS NULL UNTIL THE OPERATION ANSWERS, AND NULL MEANS **UNKNOWN** - NEVER
-- "DIDN'T HAPPEN". A crash between the rename and the write-back leaves NULL over a file that
-- did move, so any reader treating NULL as "no move" would reintroduce the defect one layer up.
-- Only the disk settles it; `undo.plan_undo` is where that reconciliation lives.
--
-- `size` is the free half of identity: it can REJECT a mismatch without reading the file, and
-- can never confirm one. `undo` hashes to confirm. `(agk)` Ruling 2.
CREATE TABLE IF NOT EXISTS inplace_moves (
    run_id       TEXT NOT NULL,
    sha256       TEXT NOT NULL,
    old_relative TEXT NOT NULL,
    new_relative TEXT NOT NULL,
    recorded_at  TEXT NOT NULL,   -- when the INTENT was written, not when a file moved
    outcome      TEXT,            -- NULL = unknown | 'renamed' | 'copied'
    size         INTEGER,
    PRIMARY KEY (run_id, old_relative)
);
CREATE INDEX IF NOT EXISTS idx_inplace_moves_run ON inplace_moves (run_id);

-- A multi-day trip: identity IS the row, never a membership hash. Unlike events.signature
-- (a hash of member SHA-256s), a trip is user-adjustable and grows on re-ingest -- an edge
-- trim or an added day must not orphan its name. See trip-grouping-research.md §6.
-- One row per drive, recording a copy-mode organize that has STARTED. `(aem)`.
--
-- Written before the first byte and closed after the last, exactly as `inplace_runs` is - but
-- for the mechanism that had no journal at all: a plain copy. Three run-shaped tables existed
-- and all three attached to something else (layout migration, source deletion, rename
-- relocation), so a `kill -9` at 340 of 4,105 files left a catalog that was internally
-- consistent and therefore serene - indistinguishable from a finished 340-file library.
--
-- ⚠ `intended_total` IS WHAT THE DRIVE WILL HOLD WHEN THE RUN COMPLETES, not what this run will
-- write, and the difference is what makes an interruption legible across a restart:
--
--       first run                writes 4,105   drive will hold 4,105
--       restart after a kill     writes 3,765   drive will hold 4,105
--
-- The write count gives two denominators that cannot be compared; the target gives one.
--
-- ⚠ AND "INTERRUPTED" IS DERIVED FROM IT, never read from `completed_at`: a run is unfinished
-- when the drive holds FEWER copies than it intended. So a crash between the last file and the
-- close reads as complete, which is correct - the close is an optimisation, not a correctness
-- requirement. `migrate` is immune to its own identical window the same way, by reporting
-- pending journal rows rather than a status flag.
--
-- Keyed on drive_uuid, superseding on start, on `start_migration_run`'s bound: exactly one
-- run's worth per drive and always the newest, so growth is bounded without a timer and an
-- open row cannot outlive the next run against that drive.
CREATE TABLE IF NOT EXISTS organize_runs (
    drive_uuid     TEXT PRIMARY KEY,
    run_id         TEXT NOT NULL,
    started_at     TEXT NOT NULL,
    intended_total INTEGER NOT NULL,
    completed_at   TEXT
);

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
CURRENT_SCHEMA_VERSION = 21


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
    _run_script(
        conn,
        """
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY, name TEXT NOT NULL, slug TEXT NOT NULL,
            start_date TEXT, file_count INTEGER, signature TEXT NOT NULL UNIQUE
        );
        CREATE TABLE IF NOT EXISTS skipped_clusters (
            signature TEXT PRIMARY KEY, skipped_at TEXT NOT NULL
        );
        """,
    )


def _add_takeout_tables(conn: sqlite3.Connection) -> None:
    """v4 -> v5: post-write copy hash + album membership for Takeout ingestion."""
    if "copy_sha256" not in _column_names(conn):
        conn.execute("ALTER TABLE files ADD COLUMN copy_sha256 TEXT")
    _run_script(
        conn,
        """
        CREATE TABLE IF NOT EXISTS albums (
            id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE
        );
        CREATE TABLE IF NOT EXISTS file_albums (
            file_id INTEGER NOT NULL, album_id INTEGER NOT NULL,
            PRIMARY KEY (file_id, album_id)
        );
        """,
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
    _run_script(
        conn,
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
        """,
    )


def _add_settings_table(conn: sqlite3.Connection) -> None:
    """v6 -> v7: a per-catalog key/value settings store (first use: the layout template)."""
    _run_script(
        conn,
        """
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY, value TEXT NOT NULL
        );
        """,
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
    _run_script(
        conn,
        """
        CREATE TABLE IF NOT EXISTS migration_runs (
            run_id       TEXT PRIMARY KEY,
            drive_uuid   TEXT NOT NULL,
            started_at   TEXT NOT NULL,
            completed_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_migration_runs_drive ON migration_runs (drive_uuid);
        """,
    )


def _add_migration_journal(conn: sqlite3.Connection) -> None:
    """v7 -> v8: a journal of in-flight layout-migration moves (for crash-safe resume)."""
    _run_script(
        conn,
        """
        CREATE TABLE IF NOT EXISTS migration_journal (
            sha256 TEXT NOT NULL, drive_uuid TEXT NOT NULL, old_relative TEXT NOT NULL,
            new_relative TEXT NOT NULL, copy_sha256 TEXT,
            PRIMARY KEY (sha256, drive_uuid)
        );
        """,
    )


def _add_reclaim_journal(conn: sqlite3.Connection) -> None:
    """v8 -> v9: an audit/resume journal for `truestill reclaim` source deletions."""
    _run_script(
        conn,
        """
        CREATE TABLE IF NOT EXISTS reclaim_journal (
            source_path TEXT PRIMARY KEY, sha256 TEXT NOT NULL,
            freed_bytes INTEGER, reclaimed_at TEXT
        );
        """,
    )


def _add_inplace_journal(conn: sqlite3.Connection) -> None:
    """v9 -> v10: a reversible journal for rename-based relocation (in-place organize)."""
    _run_script(
        conn,
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
        """,
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
    _run_script(
        conn,
        """
        CREATE TABLE IF NOT EXISTS date_confirmations (
            sha256       TEXT PRIMARY KEY,
            captured_at  TEXT NOT NULL,
            confirmed_at TEXT NOT NULL,
            confirmed_by TEXT
        );
        """,
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
    _run_script(
        conn,
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
        """,
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
    _run_script(
        conn,
        """
        DROP TABLE IF EXISTS trip_days;
        DROP TABLE IF EXISTS trips;
        """,
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


def _add_capture_columns(conn: sqlite3.Connection) -> None:
    """v16 -> v17: keep the camera and the coordinates instead of reading them and dropping them.

    `(kk)` and the camera half were one defect: `Make`/`Model`/`LensModel` decide the Camera
    category and `GPSLatitude`/`GPSLongitude` feed the event jump-cut, and every one of them was
    discarded once used. All five were already being requested from exiftool, so this is a
    column rather than a pass - the tag fingerprint is unchanged and no cached metadata is
    invalidated.

    **No backfill.** A row written before v17 keeps NULLs; recovering the values means re-reading
    the file, which is a decision of its own and not something a schema migration should do
    quietly. Five nullable columns, no defaults, no index - an index waits for a query that
    needs one.
    """
    existing = _columns_of(conn, "files")
    for column, kind in (
        ("camera_make", "TEXT"),
        ("camera_model", "TEXT"),
        ("lens_model", "TEXT"),
        ("gps_latitude", "REAL"),
        ("gps_longitude", "REAL"),
    ):
        if column not in existing:
            conn.execute(f"ALTER TABLE files ADD COLUMN {column} {kind}")


def _drop_redundant_sha256_index(conn: sqlite3.Connection) -> None:
    """v17 -> v18: drop `idx_files_sha256`, which duplicated a constraint SQLite already indexes.

    `files.sha256` is `NOT NULL UNIQUE`, so SQLite maintains `sqlite_autoindex_files_1` over
    exactly that column. The explicit index was a second B-tree on the same key: **196 KB of the
    file and one more write on every insert**, for nothing a query needed.

    **Measured on two clean copies rather than by dropping it in place**, which is what makes the
    claim safe. Every query touching `files.sha256` was planned with the index and without it -
    point lookups, both `UPDATE ... WHERE sha256`, the migration and event joins, the
    `library_status` count and the dedup seed. Three chose the explicit index and all three moved
    to the autoindex; `library_status`, the only full scan among them, measured **0.844 ms with
    and 0.848 ms without**.

    *An in-place drop-and-remeasure first suggested a 1.7x slowdown. It was the freed pages, not
    the plan: on VACUUMed copies the two are indistinguishable. The fair comparison is two clean
    databases, never one database before and after.*
    """
    conn.execute("DROP INDEX IF EXISTS idx_files_sha256")


def _add_copy_missing_at(conn: sqlite3.Connection) -> None:
    """v18 -> v19: remember that we looked for a copy and it was not there. `(abg)`.

    Verify has always computed this and thrown it away - `mark_copy_verified` fires only on
    success, so the catalog could record that a copy is fine and had no way to record that it is
    gone. Every count then read a `file_copies` row as a true statement about now, when it is a
    true statement about the moment it was written.

    **Additive and NULL on every existing row**, which is what makes the upgrade honest: a v18
    catalog answers every custody question with the same numbers after this migration as before,
    because nothing has looked yet. The column only ever gains a value from an observation.
    """
    columns = _columns_of(conn, "file_copies")
    if not columns:  # see `_add_copy_date_baked_at` - a missing TABLE is not this step's to report
        return
    if "missing_at" not in columns:
        conn.execute("ALTER TABLE file_copies ADD COLUMN missing_at TEXT")


def _refuse_if_newer(version: int) -> None:
    """A catalog from a newer Truestill is refused rather than risked."""
    if version > CURRENT_SCHEMA_VERSION:
        message = (
            f"catalog schema is version {version} but this truestill understands only "
            f"{CURRENT_SCHEMA_VERSION}; upgrade truestill to open it"
        )
        raise CatalogVersionError(message)


def _split_schema(script: str) -> tuple[str, ...]:
    """``_SCHEMA`` as individual statements, split by SQLite's own parser.

    Needed because the fresh-catalog path runs inside a transaction now, and `executescript`
    cannot: Python documents it as issuing an implicit COMMIT first, which would release the
    very lock `_migrate` took.

    **Split with `sqlite3.complete_statement` rather than on `;`.** `_SCHEMA` carries `--`
    comments between its statements, so a naive split hands SQLite fragments and mis-counts
    them - it reports 24 where there are 21. The parser that will execute the statements is
    the only honest authority on where they end.
    """
    statements: list[str] = []
    buffer = ""
    for line in script.splitlines(keepends=True):
        buffer += line
        if sqlite3.complete_statement(buffer):
            statements.append(buffer)
            buffer = ""
    if buffer.strip():  # pragma: no cover - a trailing fragment means _SCHEMA is malformed
        message = f"_SCHEMA ends with an incomplete statement: {buffer.strip()[:80]!r}"
        raise ValueError(message)
    return tuple(statements)


#: Computed once at import, O(len(_SCHEMA)) and never again.
_SCHEMA_STATEMENTS = _split_schema(_SCHEMA)


def _run_script(conn: sqlite3.Connection, script: str) -> None:
    """A multi-statement migration script, run **inside** the caller's transaction. `(adl)`.

    `executescript` cannot be used from a migration: Python documents it as issuing an implicit
    `COMMIT` first, so a step that opened a transaction and then called it would silently commit
    everything done so far and run the rest unprotected - the wrapper would look correct and roll
    back nothing. Ten steps were written that way.

    **Split by `_split_schema`, never on `;`.** The migration scripts happen to split identically
    either way today - eighteen statements against eighteen - but that is luck, not a property:
    one of them already carries `--` comments, and they simply contain no semicolon. `_SCHEMA` is
    the standing proof the coincidence does not hold in general, at 24 against 21.
    """
    for statement in _split_schema(script):
        conn.execute(statement)


#: "Has this catalog been built at all". One home, because `_migrate` asks it twice on purpose -
#: once on the unlocked fast path and once under the write lock - and two copies of the question
#: is how the two reads quietly stop being the same question.
_FILES_TABLE = "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'files'"


def _apply_step(
    conn: sqlite3.Connection, target: int, migrate: Callable[[sqlite3.Connection], None]
) -> None:
    """Run one migration and stamp its version, **atomically**. `(adl)`.

    **The stamp is inside the transaction, and that is the whole fix.** `PRAGMA user_version` is
    itself transactional - rolled back it returns to the old value together with the DDL beside
    it - so *"the migration ran but the version stayed old"* stops being a state this code can
    produce. Before this, the step and its stamp were two separate autocommits with a real gap
    between them, and a failure in that gap left a schema that had moved and a version that had
    not, which nothing downstream can reason about.

    ⚠ **The explicit `BEGIN` is not decoration.** Under ``LEGACY_TRANSACTION_CONTROL`` Python opens
    an implicit transaction before **DML only**; DDL autocommits, and `rollback()` after a bare
    `ALTER TABLE` does nothing at all. Measured both ways. That is why the chain behaved as it did,
    and why :meth:`Catalog._tx` cannot be used here - it never issues a `BEGIN`, and it would also
    set ``_dirty``, which `catalog_session` reads as *"a decision may have changed"* and would fire
    a decisions-save to every reachable drive on every upgrade open.

    **Per step, not per chain.** One step's hold is ~3.5 ms against ~60 ms for the whole chain, and
    per-step closes the same defect. What it deliberately does not close is a stop **between**
    steps - there the schema and the stamp agree, so the catalog is at version N with schema N and
    the next open resumes at N+1, which is ordinary rather than damaged.

    ⚠ **`BEGIN IMMEDIATE`, and a deferred `BEGIN` was tried first and is WRONG.** Several steps
    *read* before they write - `PRAGMA table_info`, the column guard - so a deferred transaction
    starts on a SHARED lock, and SQLite **cannot upgrade SHARED to RESERVED while another
    connection holds one: it returns `SQLITE_BUSY` immediately and does not honour
    `busy_timeout`.** Measured: six concurrent openers of a behind catalog turned 6 of 90 opens
    into `database is locked` under `BEGIN`, and none under `BEGIN IMMEDIATE`. The repo already
    knew this - `test_two_openers_build_the_schema_once` records that *"one writer bought by
    making the other fail is not the fix"* - and a deferred begin here reintroduces exactly that.
    """
    conn.execute("BEGIN IMMEDIATE")
    try:
        # ⚠ **THE STAMP MUST NOT MOVE THE VERSION BACKWARDS, AND THIS READ IS WHAT STOPS IT.**
        # `(afv)`. The chain's `version` is read once, before the loop, and is a plain local: two
        # openers of a behind catalog can therefore both enter with `version = 3` while a third
        # completes the whole chain in between. The loser then stamped `user_version = 4` over a
        # file already at 20 - **a version that moves backwards on disk**, so the file claims a
        # schema older than it has and the next open re-runs migrations against columns that
        # already exist. Measured with an independent connection sampling the file:
        # `20 -> 5`, `20 -> 19`, `20 -> 4`.
        #
        # ⚠ **This is `(adl)`'s, not `(ady)`'s.** `(adl)` made each step atomic and left the stamp
        # non-idempotent under concurrency; `(ady)`'s copy only widened the window. Measured over
        # 40 rounds of six concurrent openers: **7/40 before `(ady)`, 28/40 after** - amplifier,
        # not cause.
        #
        # The re-read costs nothing: `BEGIN IMMEDIATE` above already holds RESERVED, so this is a
        # read inside a lock this function was taking anyway, and it is the same
        # re-read-under-the-lock shape `_migrate`'s fast path already uses.
        if int(conn.execute("PRAGMA user_version").fetchone()[0]) >= target:
            # Already applied by another opener. `migrate` is idempotent, so running it would be
            # harmless and pointless; the stamp would not be.
            conn.commit()
            return
        migrate(conn)
        conn.execute(f"PRAGMA user_version = {target}")
        conn.commit()
    except BaseException:
        # `BaseException` for the reason `__init__` gives: a Ctrl-C mid-migration must still leave
        # the file clean. Suppressed because a failing rollback must not replace the real error.
        with contextlib.suppress(Exception):
            conn.rollback()
        raise


def _add_organize_runs(conn: sqlite3.Connection) -> None:
    """v19 -> v20: a run record for copy-mode organize, so an interruption is legible. `(aem)`.

    See the table's own comment in `_SCHEMA` for why `intended_total` is the drive's target
    holdings rather than the run's write count, and why "interrupted" is derived from it rather
    than read from `completed_at`.
    """
    _run_script(
        conn,
        """
        CREATE TABLE IF NOT EXISTS organize_runs (
            drive_uuid     TEXT PRIMARY KEY,
            run_id         TEXT NOT NULL,
            started_at     TEXT NOT NULL,
            intended_total INTEGER NOT NULL,
            completed_at   TEXT
        );
        """,
    )


def _make_the_inplace_journal_an_intent_log(conn: sqlite3.Connection) -> None:
    """v20 -> v21: the in-place journal records intent, not completed moves. `(agk)`

    ⚠ **`moved_at` is RENAMED rather than reused**, and that is the point of the migration. A
    column called `moved_at` on a row that may describe a rename which never happened is the
    reader asserting what it no longer knows - the exact failure Ruling 1 exists to prevent.

    ⚠ **EXISTING ROWS ARE LEFT UNKNOWN, AND THE FIRST DRAFT BACKFILLED THEM.** Every old row was
    written *after* a completed rename, so `'renamed'` would have been true - and
    `test_migration_safety.py`'s backfill guard refused it, correctly: DDL autocommits and DML
    does not, so a crash between them commits the column, rolls back the data, and the retry
    **skips** the backfill because the column already exists. The partial state becomes permanent
    and silent.

    Leaving them NULL is not a concession, it is the better rule: **the journal never asserts an
    outcome it did not observe**, including for rows predating the field. Unknown costs a hash on
    undo and nothing else, because unknown means *ask the disk* - which `undo.plan_undo` does for
    every row anyway. A `DEFAULT 'renamed'` was rejected for the opposite reason: it would make
    any future insert that omits the column claim a rename happened, which is the one direction
    this entry exists to prevent.

    ⚠ **`ADD COLUMN` is not `DEFAULT`-free by accident either** - `size` stays NULL for old rows,
    which costs only the free pre-filter. `undo` still hashes, so identity is unaffected.
    """
    columns = _columns_of(conn, "inplace_moves")
    if not columns:
        # No table, nothing to alter. `PRAGMA table_info` answers empty rather than raising for a
        # missing table, so this is the same guard the statements below use and not a special
        # case - a chain replayed onto a file that never reached v10 must complete, not die here.
        return
    # Guarded per statement, not per migration: `_MIGRATIONS` is replayed from whatever version
    # the file is on, and a half-applied step must be completable rather than fatal. `RENAME
    # COLUMN` in particular cannot be re-run - it raises on the second pass, where `ADD COLUMN`
    # merely duplicates.
    if "moved_at" in columns:
        conn.execute("ALTER TABLE inplace_moves RENAME COLUMN moved_at TO recorded_at")
    if "outcome" not in columns:
        conn.execute("ALTER TABLE inplace_moves ADD COLUMN outcome TEXT")
    if "size" not in columns:
        conn.execute("ALTER TABLE inplace_moves ADD COLUMN size INTEGER")


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
    (17, _add_capture_columns),
    (18, _drop_redundant_sha256_index),
    (19, _add_copy_missing_at),
    (20, _add_organize_runs),
    (21, _make_the_inplace_journal_an_intent_log),
)


#: Where the planner's statistics were last refreshed, as `files.id`'s high-water mark. Machine-
#: local: it describes THIS file's planner, so it is excluded from the decisions document by the
#: `catalog.` prefix - restored onto another machine it would describe a database that is not
#: there.
ANALYZED_AT_KEY = "catalog.analyzed_at_row"

#: New `files` rows before the statistics are refreshed again. Generous on purpose: `ANALYZE`
#: measured 1.8 ms on the real 2,695-file catalog and 17 ms against a 172,480-row table, so the
#: cost of running it slightly too often is far below the cost of a planner guessing at joins.
ANALYZE_GROWTH_ROWS = 1000


def _now() -> str:
    return datetime.now(UTC).isoformat()


#: Mirrors `decisions._EXCLUDED_SETTING_PREFIXES`. Duplicated rather than imported because
#: `decisions` takes a catalog and importing it here would close a cycle; the pair is pinned by
#: `test_local_settings_match_the_document_exclusions`, so they cannot drift.
_LOCAL_SETTING_PREFIXES = ("path_hint.", "decisions.", "catalog.")


class Catalog:
    """Thin, typed wrapper over the SQLite state file. Use as a context manager."""

    def __init__(self, path: Path) -> None:
        self.path = path
        #: The copy taken before the migration chain ran, or ``None`` when no chain ran - a
        #: fresh catalog and an already-current one both leave this ``None``, and those are two
        #: different reasons for the same absence rather than a failure. Core prints nothing
        #: (`IMPLEMENTATION_STANDARDS` §2); a surface reads this and decides. `(ady)`
        self.pre_migration_backup: catalog_backup.BackupOutcome | None = None
        if path != Path(":memory:"):
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                # Before SQLite is ever asked, so no `sqlite3.Error` exists to carry this to the
                # surfaces. Reported as the condition it is rather than as a stack. `(aen)`
                raise CatalogUnwritableError(exc, path.parent) from exc
        # PINNED, NOT ADOPTED. `LEGACY_TRANSACTION_CONTROL` is what an unqualified `connect`
        # gives today, so this changes no behaviour - it is here because Python's documentation
        # says the `autocommit` default becomes `False` in a future release. Inheriting it means
        # a Python upgrade silently changes when every catalog write commits, with no line of
        # ours changing. Adopting the new semantics is a separate, deliberate decision that has
        # to consider the whole write path; this only stops it happening by accident.
        #
        # The `type: ignore` is a typeshed gap, not a smell: the stub declares
        # `autocommit: bool`, while the documented sentinel for "keep the old behaviour" is
        # `sqlite3.LEGACY_TRANSACTION_CONTROL`, which is the int -1. Runtime accepts it; the
        # annotation is narrower than the API. Deleting the ignore breaks the build; deleting
        # the argument silently un-pins the transaction model.
        self._dirty = False
        self._conn = sqlite3.connect(
            str(path),
            autocommit=sqlite3.LEGACY_TRANSACTION_CONTROL,  # type: ignore[call-overload]
        )
        # Everything after the connect is guarded, because `with Catalog(...)` cannot help
        # here: `__init__` raises, so the object is never returned, `__enter__` is never
        # reached, and `__exit__` never runs. `_migrate` refusing a newer catalog is a
        # documented, ordinary path - it left the handle open on every occurrence.
        try:
            self._conn.row_factory = sqlite3.Row
            # Off by default per SQLite connection (not persisted in the file). trip_days.trip_id
            # is the first declared foreign key in this schema; without this, the REFERENCES
            # clause is decorative and a bogus trip_id would insert silently.
            self._conn.execute("PRAGMA foreign_keys = ON")
            self._migrate()
            self._conn.commit()
        except BaseException:
            # `suppress`, so a failing close can never replace the exception being handled:
            # "this catalog is from a newer Truestill" must not surface as an unrelated sqlite
            # error from the cleanup. BaseException so a Ctrl-C mid-migration still closes.
            with contextlib.suppress(Exception):
                self._conn.close()
            raise

    def _migrate(self) -> None:
        """Bring the database schema to CURRENT_SCHEMA_VERSION via PRAGMA user_version.

        A fresh database gets the whole current schema in one step. An existing one is
        lifted through the ordered migrations. A database from a *newer* truestill is refused
        rather than risked.

        **The version read and the table check happen under the write lock, and that is the
        point.** They used to be two unsynchronised reads followed by a write - a textbook
        check-then-act - and with two openers on one fresh catalog it produced both observed
        failures at once. Measured in CI run 31810809571: **2170 schema writes from 7696
        opens**, so nearly every concurrent opener rebuilt the schema another had just built,
        and one such writer held the file for **20260 ms** while the rest expired against
        `sqlite3.connect`'s 5 s timeout. The `duplicate column` errors are the same race read
        the other way - an opener that read `version = 0`, then found `files` already created
        by the winner, and ran all 18 migrations against a schema that was already current.

        `BEGIN IMMEDIATE` takes RESERVED before the first read, so no other process can write
        between the check and the act. Cross-process by construction: an in-process lock would
        not have covered the CLI, and `(adh)` test (d) records that launching twice already
        gives two sidecars with no single-instance guard.

        ⚠ **The migration chain deliberately runs OUTSIDE that transaction**, and it is not a
        choice so much as a constraint that was measured: **10** of the 18 migrations call
        `executescript`, which Python documents as issuing an implicit COMMIT first - re-verified
        2026-08-18 on Python 3.13.13 / SQLite 3.50.4, `in_transaction` goes False and the lock is
        gone. Wrapping the chain would have silently released the lock at the first migration
        while looking correct.
        ~~and `_drop_redundant_sha256_index` runs `VACUUM`, which SQLite refuses inside a
        transaction outright.~~ ⚠ **STRUCK 2026-08-18: THAT IS NOT TRUE OF THIS CODE.** `VACUUM`
        appears in this module only inside docstrings; no migration executes it, and v18 is a
        single `DROP INDEX IF EXISTS`. Two further corrections in the same breath, because they
        change what is possible rather than only what is accurate: the count was **12**, and
        `executescript` is a **`sqlite3` module** behaviour rather than a database constraint -
        **DDL itself is fully transactional in SQLite** (verified: `ALTER TABLE` inside `BEGIN
        IMMEDIATE` keeps `in_transaction`, and `rollback()` removes a created table). So the
        chain *could* be wrapped by splitting those 10 into per-statement `execute` calls, at the
        price of holding the write lock for a whole migration. `BACKLOG.md` `(adl)` carries the
        routes and the measured failure rate; **nothing here is a recommendation.**
        So the chain keeps today's autocommit-per-statement behaviour exactly: a failure
        part-way still leaves the schema half-lifted with `user_version` unchanged. **That is
        unchanged, not fixed** - see `BACKLOG.md`. ~~What the transaction does fix is that the
        chain can no longer be entered on a catalog that is already current.~~
        ⚠ **NARROWED 2026-08-18 BY MEASUREMENT, `(adl)`: only if the STAMP has already happened,
        and the stamp is outside the lock too.** An opener that takes the lock after another has
        committed but before it has written the new `user_version` reads the OLD version and runs
        the same migration again. Measured on a catalog one version behind, 150 trials: at six
        openers, **20 ran a migration more than once**. Nothing has ever failed for it because the
        chain's migrations happen to be idempotent - which is luck holding, not a design.

        Cost, since `(adu)`: an already-current catalog does **two reads and no transaction**;
        anything else pays those two reads and then the full path below. The fresh path executes
        the same 21 statements as before, now individually rather than as one script.
        """
        conn = self._conn
        # THE FAST PATH, AND IT CAN ONLY EVER DECIDE TO SKIP. `(adu)`.
        #
        # **Why this is not the check-then-act that §5.4 replaced, which is the whole
        # distinction.** The defect was reading the version and then *acting* on what an unlocked
        # read said. Nothing here acts: the only conclusion this block can reach is "the schema is
        # already current, there is nothing to do, return". Every path that writes falls through
        # to `BEGIN IMMEDIATE` below and **re-reads the version and the table under the lock**,
        # which is where the decision is made. A fast path that acts on this read instead of
        # falling through IS the old defect, and
        # `test_two_openers_build_the_schema_once` catches it - proven by mutation in both
        # directions before this landed.
        #
        # **Why it is worth having**, measured 2026-08-18 on ext4 with a 256x fsync control
        # (`PERFORMANCE.md` §5.6): the lock protects exactly one state - two openers both
        # building a fresh schema - and that happens **once per catalog** in the life of a
        # library. Removing `BEGIN IMMEDIATE` is caught immediately on a fresh catalog and
        # survives entirely on a migrated one, which writes nothing at all: `total_changes` 0,
        # file byte-identical, no journal. Every open after the first was paying for a state that
        # cannot recur, and at twelve concurrent opens that cost p99 **181.9 ms against 3.93 ms**.
        #
        # ⚠ **It is a TRADE, not a free win.** Uncontended it is slightly *slower* -
        # **0.575 -> 0.670 ms**, the one extra read - and that is recorded rather than buried. It
        # buys a contention tail with a fixed sub-millisecond cost.
        #
        # `_refuse_if_newer` runs here too: a catalog from a newer Truestill must be refused
        # before anything opens a transaction against it, not after.
        version = int(conn.execute("PRAGMA user_version").fetchone()[0])
        _refuse_if_newer(version)
        if version == CURRENT_SCHEMA_VERSION and conn.execute(_FILES_TABLE).fetchone() is not None:
            return
        # RESERVED before the first read. Waiters block here for at most `busy_timeout`, and
        # the whole decision below is invisible to them until it commits.
        conn.execute("BEGIN IMMEDIATE")
        try:
            # RE-READ UNDER THE LOCK, never reused from the fast path above. This is the line
            # that makes the fast path a skip rather than a decision.
            version = int(conn.execute("PRAGMA user_version").fetchone()[0])
            _refuse_if_newer(version)
            fresh = conn.execute(_FILES_TABLE).fetchone() is None
            if fresh:
                for statement in _SCHEMA_STATEMENTS:
                    conn.execute(statement)
                conn.execute(f"PRAGMA user_version = {CURRENT_SCHEMA_VERSION}")
            conn.commit()
        except BaseException:
            # Rollback before re-raising: `__init__`'s handler closes the connection, and a
            # connection closed mid-transaction leaves the journal for the next opener to
            # recover. Suppressed because a failing rollback must not replace the real error.
            with contextlib.suppress(Exception):
                conn.rollback()
            raise

        if fresh:
            return

        # ⚠ **THE COPY GOES HERE, AND "HERE" IS LOAD-BEARING - see `catalog_backup`.** Two things
        # about this position are measured rather than chosen:
        #
        # 1. **After the `BEGIN IMMEDIATE` above has COMMITTED.** `Connection.backup` hangs
        #    forever - not raises - when its source connection is inside a write transaction.
        #    Moving this call up into that block would replace a startup with a process that
        #    sleeps until it is killed. `in_transaction` is False here, and a test pins it.
        # 2. **Only when there is a chain to run**, which is `version < CURRENT_SCHEMA_VERSION`
        #    and NOT merely "not fresh". ⚠ The `fresh` guard above catches a brand-new catalog
        #    and misses an **already-current** one that fell through the fast path: that read is
        #    outside the lock, so an opener can see a behind version there, re-read the current
        #    one under the lock, and arrive here with nothing whatever to do. Measured on six
        #    concurrent openers, **four of six** took a full copy and applied **zero** steps.
        #    `(afv)`
        #
        # ⚠ **That was not only waste.** Each of those copies put a page-by-page read of the
        # catalog in the path of the openers that *were* migrating, which is what took `(adl)`'s
        # backward-stamp defect from 7/40 rounds to 28/40. Removing them removes most of the
        # amplification as well as most of the work. **The stamp was the defect and is fixed in
        # `_apply_step`; this is the amplifier.**
        #
        # It never raises: a catalog whose safety copy could not be taken must still open, so the
        # outcome is reported rather than thrown. `(ady)`
        if version < CURRENT_SCHEMA_VERSION:
            self.pre_migration_backup = catalog_backup.copy_before_migration(conn, self.path)

        for target, migrate in _MIGRATIONS:
            if version < target:
                _apply_step(conn, target, migrate)

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

    def set_local_setting(self, key: str, value: str) -> None:
        """Persist a **machine-local** setting without marking the catalog dirty. `(afc)`

        ⚠ **`dirty` means "a decision may have changed", and for these keys it provably has not.**
        `catalog_session` fires `save_decisions_to_reachable_drives` on a dirty close, and
        `decisions._EXCLUDED_SETTING_PREFIXES` filters exactly these prefixes **out of the
        document**. So a `path_hint.` write through :meth:`set_setting` writes an *identical*
        document to every reachable drive - and turns any read-only command that records where it
        found a drive into one that writes to the user's disk. `catalog.py`'s schema-upgrade
        docstring already names this hazard for its own case.

        ⚠ **It REFUSES a key that is not excluded**, which is what keeps it from becoming a quiet
        way to skip the sync for a real decision. The guard is the point; without it this is a
        footgun with a reassuring name.
        """
        if not key.startswith(_LOCAL_SETTING_PREFIXES):
            message = (
                f"{key!r} is not a machine-local setting. set_local_setting skips the decisions "
                f"sync, which is only safe for keys the document excludes."
            )
            raise ValueError(message)
        was_dirty = self._dirty
        self.set_setting(key, value)
        self._dirty = was_dirty

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
                SELECT fc.sha256, fc.relative, fc.copy_sha256, fc.size, f.category,
                       f.captured_at,
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

        **The coordinates are part of the clustering input, not decoration.** `cluster_camera`
        cuts an event boundary on a GPS jump, and omitting them here is what made this path
        disagree with a fresh import over the same photos - the jump-cut simply could not fire.
        """
        return list(
            self._conn.execute(
                """
                SELECT fc.sha256, f.captured_at, f.gps_latitude, f.gps_longitude
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

        ⚠ **Both journals, and this read `migration_journal` alone until 2026-08-22.** A layout
        migration writes there; `organize --in-place` writes `inplace_moves` instead - so the
        folders an in-place run emptied were invisible to `clean-empty` and to the offer printed
        after the run, while the run's own banner promised *"Empty folders left behind are
        reported"*. Measured: 161 `inplace_moves` rows, an empty folder on disk, and *"no
        migration leftovers recorded"*. `(afi)`

        ⚠ **The equal-roots condition is a SAFETY one, not a tidiness one.** `Relocation`
        is built for plain ``--move`` as well (`cli.py`, deliberately, so both spellings earn the
        same undo rights), and `old_relative` is relative to the **source root** - which for
        ``--move`` is the folder the user was importing FROM, not this drive. Without that clause
        a folder emptied under `~/Downloads` would be offered for removal at the same relative
        path on the destination drive, which is precisely the drive-sweep the paragraph above
        forbids. Only a true in-place run has ``source_root == dest_root``.

        **A read, not a merge.** The two journals stay separate because `inplace_runs` /
        `inplace_moves` are what `undo-organize` reverses, and `(yy)` already recorded that
        rewriting undo records is its own decision. Nothing here writes.
        """
        paths = [
            str(row["old_relative"])
            for row in self._conn.execute(
                "SELECT old_relative FROM migration_journal "
                "WHERE drive_uuid = ? AND completed_at IS NOT NULL",
                (drive_uuid,),
            )
        ]
        paths.extend(
            str(row["old_relative"])
            for row in self._conn.execute(
                "SELECT m.old_relative, r.source_root, r.dest_root FROM inplace_moves m "
                "JOIN inplace_runs r ON r.run_id = m.run_id "
                "WHERE r.drive_uuid = ? AND r.completed_at IS NOT NULL",
                (drive_uuid,),
            )
            # ⚠ Compared in Python rather than in the SQL, because the roots are stored as the
            # strings the user typed. `os.path.normpath` settles a trailing slash, a `./` and a
            # doubled separator without touching the filesystem; a pair that is absolute on one
            # side and relative on the other cannot be settled at all without the cwd of a run
            # that has already finished, and falls to "not in place" -- which under-reports
            # rather than offering a folder on the wrong root.
            if os.path.normpath(row["source_root"]) == os.path.normpath(row["dest_root"])
        )
        return paths

    def start_organize_run(self, *, drive_uuid: str, run_id: str, intended_total: int) -> None:
        """Open a copy-mode organize run, superseding any prior one for this drive. `(aem)`.

        **Written before the first byte**, the way `start_inplace_run` is - *"so a crash leaves a
        record"*. That is the whole point: after the process dies the intended total cannot be
        reconstructed, because the restart's own intended total correctly excludes what already
        landed.

        ``intended_total`` is **what the drive will hold when this run completes**, not what the
        run will write. See the table comment in `_SCHEMA`.
        """
        with self._tx() as conn:
            conn.execute("DELETE FROM organize_runs WHERE drive_uuid = ?", (drive_uuid,))
            conn.execute(
                "INSERT INTO organize_runs (drive_uuid, run_id, started_at, intended_total) "
                "VALUES (?, ?, ?, ?)",
                (drive_uuid, run_id, _now(), intended_total),
            )

    def finish_organize_run(self, drive_uuid: str) -> None:
        """Close the run for a drive. **An optimisation, never a correctness requirement.**

        A crash between the last file and this call leaves `completed_at` NULL on a run that
        actually finished; :meth:`unfinished_organize_run` derives the answer from what the drive
        holds instead, so that case reads as complete.
        """
        with self._tx() as conn:
            conn.execute(
                "UPDATE organize_runs SET completed_at = ? WHERE drive_uuid = ? "
                "AND completed_at IS NULL",
                (_now(), drive_uuid),
            )

    def unfinished_organize_run(self, drive_uuid: str) -> sqlite3.Row | None:
        """The open run for a drive whose files did not all arrive, or ``None``. `(aem)`.

        ⚠ **DERIVED, NOT READ FROM `completed_at`.** A run is unfinished when the drive holds
        FEWER copies than the run intended it to hold - so a lost close reads as complete, which
        is correct, and a genuinely interrupted run reads as interrupted even if some later
        process closed its row. `migrate` is immune to the same window in the same way, by
        reporting pending journal rows rather than a status.

        Returns the run row plus ``achieved``, so a caller can say *"340 of 4,105"* without a
        second query.
        """
        row = self._conn.execute(
            """
            SELECT r.drive_uuid, r.run_id, r.started_at, r.intended_total, r.completed_at,
                   (SELECT COUNT(*) FROM file_copies fc WHERE fc.drive_uuid = r.drive_uuid)
                       AS achieved
            FROM organize_runs r
            WHERE r.drive_uuid = ?
            """,
            (drive_uuid,),
        ).fetchone()
        if row is None or row["completed_at"] is not None:
            # ⚠ A CLOSED RUN IS FINISHED, WHATEVER THE DRIVE HOLDS NOW, and this branch is not
            # redundant with the one below. Without it a run that completed correctly begins
            # claiming it was interrupted the moment any file is deleted afterwards - `achieved`
            # falls below `intended_total` for a reason that has nothing to do with the run.
            # Found by mutation: replacing the derivation with this flag alone survived every
            # test, which said the two conditions were not both being exercised.
            return None
        if int(row["achieved"]) >= int(row["intended_total"]):
            # Everything the run intended is here, so it finished even though its close was
            # lost - the crash between the last file and the close. Deriving this rather than
            # trusting `completed_at` is what makes the close an optimisation.
            return None
        return cast("sqlite3.Row", row)

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
                "SELECT sha256, drive_uuid, old_relative, new_relative, copy_sha256, run_id, completed_at FROM migration_journal "
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

    def record_inplace_intent(
        self,
        *,
        run_id: str,
        sha256: str,
        old_relative: str,
        new_relative: str,
        size: int | None,
    ) -> None:
        """Journal a rename **about to be attempted**. Written BEFORE the file moves. `(agk)`

        ⚠ **The ordering is the guarantee, and reversing it is the defect.** Written afterwards,
        as it was until `(agk)`, the rename itself is covered by nothing: a crash in the window
        leaves the file moved with no way back. Measured on real photographs - 2 of 8 kills, and
        `undo-organize` then reported success while the file stayed where the run had put it.

        Written first, the worst case is a row describing a rename that never happened, and that
        is recoverable by construction: `undo.plan_undo` reconciles against the **disk**, so such
        a row is skipped rather than acted on. A failure here means no rename is attempted, so
        there is nothing to undo - which is the point of doing it in this order.
        """
        with self._tx() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO inplace_moves (run_id, sha256, old_relative, "
                "new_relative, recorded_at, outcome, size) VALUES (?, ?, ?, ?, ?, NULL, ?)",
                (run_id, sha256, old_relative, new_relative, _now(), size),
            )

    def record_inplace_outcome(self, *, run_id: str, old_relative: str, outcome: str) -> None:
        """Say what the attempt became: ``'renamed'`` or ``'copied'``. `(agk)`

        ⚠ **This is bookkeeping, not the guarantee.** Losing it costs a count its precision and
        nothing else, because the row it updates already exists and `undo` never trusts this
        field - it reconciles against the disk either way. That asymmetry is deliberate: the
        write that must not be lost happens before the rename, and this one may be.
        """
        with self._tx() as conn:
            conn.execute(
                "UPDATE inplace_moves SET outcome = ? WHERE run_id = ? AND old_relative = ?",
                (outcome, run_id, old_relative),
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
        """Every recorded relocation run, newest first, with what its journal actually says.

        ⚠ **Three counts, not one, since `(agk)`.** The single `moves` column asserted that every
        row was a completed move, which an intent log cannot promise. `intended` is how many
        renames the run set out to make, `renamed` how many are confirmed, and `unknown` how many
        have no outcome recorded - **which means the disk has not been asked, never that nothing
        happened.** A caller that wants the truth about an `unknown` row reconciles, as
        `undo.plan_undo` does; a caller that only reports says "intended".
        """
        return list(
            self._conn.execute(
                """
                SELECT r.run_id, r.source_root, r.dest_root, r.drive_uuid, r.started_at,
                       r.completed_at, r.status,
                       (SELECT COUNT(*) FROM inplace_moves m WHERE m.run_id = r.run_id)
                           AS intended,
                       (SELECT COUNT(*) FROM inplace_moves m
                         WHERE m.run_id = r.run_id AND m.outcome = 'renamed') AS renamed,
                       (SELECT COUNT(*) FROM inplace_moves m
                         WHERE m.run_id = r.run_id AND m.outcome IS NULL) AS unknown
                FROM inplace_runs r
                ORDER BY r.started_at DESC
                """
            )
        )

    def inplace_run(self, run_id: str) -> sqlite3.Row | None:
        """One run's header, or ``None`` if there is no such run."""
        cursor = self._conn.execute(
            "SELECT run_id, source_root, dest_root, drive_uuid, started_at, completed_at, status FROM inplace_runs WHERE run_id = ?",
            (run_id,),
        )
        row: sqlite3.Row | None = cursor.fetchone()
        return row

    def latest_undoable_run(self) -> sqlite3.Row | None:
        """The most recent run that has not already been undone."""
        cursor = self._conn.execute(
            "SELECT run_id, source_root, dest_root, drive_uuid, started_at, completed_at, status FROM inplace_runs "
            "WHERE status != 'undone' ORDER BY started_at DESC LIMIT 1"
        )
        row: sqlite3.Row | None = cursor.fetchone()
        return row

    def inplace_moves(self, run_id: str) -> list[sqlite3.Row]:
        """A run's moves in the order they happened; undo walks this reversed."""
        return list(
            self._conn.execute(
                "SELECT sha256, old_relative, new_relative, outcome, size FROM inplace_moves "
                "WHERE run_id = ? ORDER BY recorded_at, old_relative",
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
        the newest human answer is the answer.

        **A new answer also un-bakes every copy**, and this is not housekeeping. Step 4 skips a
        copy whose ``file_copies.date_baked_at`` is set, so without clearing it the sequence
        confirm -> bake -> change your mind leaves the second answer durable in the catalog and
        **unable to ever reach the files**: every copy still looks baked, is never offered again,
        and the photo keeps a date its owner has explicitly replaced. Silent, and exactly the
        class of failure O4 exists for. The invariant is now sayable: ``date_baked_at`` is
        non-NULL only while the bytes carry the *current* confirmed date.

        **O(1)**, three indexed writes in one transaction.
        """
        with self._tx() as conn:
            conn.execute(
                "INSERT INTO date_confirmations (sha256, captured_at, confirmed_at, confirmed_by)"
                " VALUES (?, ?, ?, ?) ON CONFLICT(sha256) DO UPDATE SET"
                " captured_at = excluded.captured_at, confirmed_at = excluded.confirmed_at,"
                " confirmed_by = excluded.confirmed_by",
                (sha256, captured_at, _now(), confirmed_by),
            )
            conn.execute("UPDATE file_copies SET date_baked_at = NULL WHERE sha256 = ?", (sha256,))
            conn.execute(
                "UPDATE files SET captured_at = ?, date_source = ?, date_tag = NULL"
                " WHERE sha256 = ?",
                (captured_at, DateSource.HUMAN_CONFIRMED.value, sha256),
            )

    def copy_is_baked(self, sha256: str) -> bool:
        """Whether any copy of this content currently carries a confirmed date in its bytes.

        Used to word the outcome card truthfully: after a bake the file does not say its
        *original* evidence date any more, it says whatever was last written into it.
        **O(1)** on the primary key.
        """
        row = self._conn.execute(
            "SELECT 1 FROM file_copies WHERE sha256 = ? AND date_baked_at IS NOT NULL LIMIT 1",
            (sha256,),
        ).fetchone()
        return row is not None

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
        # After the commit, never before: a rolled-back transaction changed nothing and must not
        # look as though it did.
        self._dirty = True

    @property
    def dirty(self) -> bool:
        """Whether **any** write has been committed since this catalog was opened or marked clean.

        **Any write, not "a decision" - and that is deliberate.** Telling the two apart would mean
        maintaining a list of which methods count, and the day someone adds a decision table and
        forgets the list, the drive copy goes quiet with nothing saying so. Every write in this
        class goes through one :meth:`_tx`, so this cannot drift; a list would.

        Interpreting it is the caller's job. `catalog_session.open_catalog` reads it as "this unit
        of work may have changed a decision, so refresh the drives".
        """
        return self._dirty

    def mark_clean(self) -> None:
        """Forget the writes seen so far. Called after the drive copies have been refreshed.

        Without it the refresh's own bookkeeping write - it records outcomes through this same
        catalog - would leave the catalog looking dirty and fire a second, identical save. That is
        harmless today and a loop the day the fire point moves.
        """
        self._dirty = False

    # -- reads ---------------------------------------------------------------------

    def seed_rows(self) -> list[tuple[str, str, str | None]]:
        """Return ``(source_path, sha256, perceptual)`` for every known file.

        This is exactly the shape :meth:`DedupIndex.from_catalog_rows` consumes.
        """
        cursor = self._conn.execute("SELECT source_path, sha256, perceptual FROM files")
        return [(row["source_path"], row["sha256"], row["perceptual"]) for row in cursor]

    def repoint_sources(self, moves: Sequence[tuple[str, str]]) -> int:
        """Rewrite ``files.source_path`` for ``(sha256, new_path)`` pairs. Returns rows changed.

        One transaction: a repoint half-applied would leave a library split across two roots
        with nothing recording which rows moved. `sha256` is the key because it is the column
        with a UNIQUE constraint and the one thing a moved file keeps.
        """
        if not moves:
            return 0
        with self._conn as conn:
            cursor = conn.executemany(
                "UPDATE files SET source_path = ? WHERE sha256 = ?",
                [(new_path, sha) for sha, new_path in moves],
            )
            return int(cursor.rowcount or 0)

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
        cursor = self._conn.execute(
            "SELECT id, source_path, original_name, sha256, copy_sha256, perceptual, size, captured_at, category, relative, event_id, upload_status, processed_at, uploaded_at, date_source, date_tag, camera_make, camera_model, lens_model, gps_latitude, gps_longitude FROM files WHERE sha256 = ?",
            (sha256,),
        )
        row: sqlite3.Row | None = cursor.fetchone()
        return row

    def count(self) -> int:
        return int(self._conn.execute("SELECT COUNT(*) FROM files").fetchone()[0])

    def total_content_bytes(self) -> int:
        """How big the library is: DISTINCT content, never the sum over drives.

        `library_status` summed `file_copies.size` across every drive, so a backed-up library
        reported twice its size and the panel disagreed with Stats about the same photos. A
        second copy is custody - which is what `places` and `single_copy` beside it are for -
        not volume.

        Same aggregate `stats_summary` already reports as `total_size`, so the two surfaces
        read one number by construction rather than by agreement.
        """
        return int(self._conn.execute("SELECT COALESCE(SUM(size), 0) FROM files").fetchone()[0])

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

    def files_in_date_tier(
        self, date_source: str | None, *, limit: int
    ) -> tuple[list[sqlite3.Row], int]:
        """One page of the files in a provenance tier, and the tier's full size.

        Returns ``sha256, original_name, relative, captured_at, date_tag`` per row - **the
        sha256 is the point**: `confirm_date` is keyed on it, so a list without it can describe
        a file but cannot name it to the action that would fix it.

        ``date_source`` of ``None`` selects the *not recorded* group, which is a real tier and
        the commonest one on any library organized before schema v13 - it must not be the one
        group a user cannot open.

        The count is a separate query rather than ``len(rows)`` so a truncated page can still
        say what it was taken from (F46). **Complexity: O(page)** on an indexed scan, plus one
        counting scan of the tier.
        """
        where = "date_source IS NULL" if date_source is None else "date_source = ?"
        params: tuple[str, ...] = () if date_source is None else (date_source,)
        total = int(
            self._conn.execute(f"SELECT COUNT(*) FROM files WHERE {where}", params).fetchone()[0]
        )
        rows = list(
            self._conn.execute(
                f"SELECT sha256, original_name, relative, captured_at, date_tag "
                f"FROM files WHERE {where} ORDER BY processed_at DESC LIMIT ?",
                (*params, limit),
            )
        )
        return rows, total

    def stats_undated_samples(self, *, limit: int = 12) -> list[sqlite3.Row]:
        """A small, actionable sample of undated files for the UI."""
        return list(
            self._conn.execute(
                """
                SELECT sha256, original_name, source_path, relative
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
        """Known drives with their copy counts and total bytes (largest label set aside).

        **This list REPORTS HISTORY, so it gains a number rather than losing one** - the opposite
        rule to the custody counts below, and deliberately. ``file_count`` still counts every
        recorded copy including ones a check did not find, and ``missing_count`` names the
        shortfall, so a drive reads *"2,269 recorded, 2,269 not found on 11 Aug"*. Filtering here
        instead would drop it to ``0`` and destroy the only clue to what happened. `(abg)`.
        """
        return list(
            self._conn.execute(
                """
                SELECT d.uuid, d.label, d.first_seen, d.last_seen, d.last_verified, d.notes, COUNT(fc.sha256) AS file_count,
                       COALESCE(SUM(fc.size), 0) AS total_size,
                       COUNT(fc.missing_at) AS missing_count,
                       MAX(fc.missing_at) AS missing_at,
                       -- Copies a check has CONFIRMED. This is what separates the two meanings
                       -- of a NULL `last_verified`: "nothing has ever run" (zero) from "a check
                       -- ran and could not confirm everything" (non-zero). `missing_count` alone
                       -- cannot do it - a copy can be unconfirmed without being missing, when it
                       -- was unreadable or the run was cancelled before reaching it. `(aej)`.
                       SUM(fc.last_verified IS NOT NULL) AS confirmed_count
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

    #: How many hashes go into one ``IN (...)``. SQLite refuses more bound parameters than
    #: ``SQLITE_MAX_VARIABLE_NUMBER``, which is 999 on builds predating 3.32 and 32,766 after -
    #: and the caller here is a preview over a whole folder, so 40,000 is an ordinary size.
    #: 900 clears the older limit rather than probing for the newer one; the cost of a smaller
    #: chunk is more index seeks in the same order, not more work per hash.
    _SHA_CHUNK = 900

    def drives_holding(self, shas: Sequence[str]) -> list[DriveHolding]:
        """Which drives physically hold this content: ``drive_uuid, label, files``, biggest first.

        *Hold*, present tense: a copy looked for and not found is excluded, on
        :meth:`single_copy_shas`'s reasoning.

        **`file_copies` is the only table that knows.** `files.source_path` is where content was
        first read from and is deliberately never repointed, so it names a user's old folder
        rather than their library; `file_copies`, keyed by ``(sha256, drive_uuid)``, is where a
        copy actually sits. A surface that wants to act on "your library" has to ask this.

        Content on two drives yields **two rows**, on purpose. Collapsing to one would answer the
        two-destination case - copied into X, later compared against Y - with a confident wrong
        drive, which is worse than the honest pair.

        A hash with no copy row contributes to nothing here; the caller counts those as unplaced
        rather than having one invented for them.

        **Complexity: O(m log n)** index seeks for *m* distinct hashes over an *n*-row table -
        ``PRIMARY KEY (sha256, drive_uuid)`` leads with ``sha256``, so its automatic index already
        serves this and **no new index is added**. Pinned by
        ``test_the_lookup_uses_an_index_rather_than_scanning_every_copy``, because a later schema
        change that reordered that key would turn this into a table scan per preview with nothing
        to notice it.
        """
        unique = list(dict.fromkeys(shas))  # one seek per CONTENT, not per matched file
        if not unique:
            return []
        counts: Counter[str] = Counter()
        labels: dict[str, str] = {}
        for start in range(0, len(unique), self._SHA_CHUNK):
            chunk = unique[start : start + self._SHA_CHUNK]
            for row in self._conn.execute(self._drives_holding_sql(chunk), chunk):
                counts[row["drive_uuid"]] += int(row["files"])
                labels[row["drive_uuid"]] = row["label"]
        ordered = sorted(counts.items(), key=lambda item: (-item[1], labels[item[0]]))
        # A typed record rather than a `sqlite3.Row` like its neighbours, and deliberately: the
        # counts are summed ACROSS chunks, so no single statement produced this and pretending
        # otherwise would invite someone to add a column to the SQL and expect it here.
        return [DriveHolding(uuid, labels[uuid], count) for uuid, count in ordered]

    @staticmethod
    def _drives_holding_sql(chunk: Sequence[str]) -> str:
        placeholders = ",".join("?" for _ in chunk)
        return f"""
            SELECT fc.drive_uuid AS drive_uuid, d.label AS label, COUNT(*) AS files
            FROM file_copies fc
            JOIN drives d ON d.uuid = fc.drive_uuid
            WHERE fc.sha256 IN ({placeholders}) AND fc.missing_at IS NULL
            GROUP BY fc.drive_uuid
        """

    def placed_shas(self, shas: Sequence[str]) -> set[str]:
        """Which of these hashes have a copy row at all, on any drive.

        The complement is the orphan state: a `files` row with no `file_copies` row, which a CLI
        organize left behind until `test_organize_registers_the_destination.py`. A caller that
        subtracted `drives_holding`'s counts from its input would get this wrong the moment
        content sits on two drives, so it is asked rather than derived.

        **Complexity:** the same index seek as :meth:`drives_holding`, chunked the same way.
        """
        unique = list(dict.fromkeys(shas))
        found: set[str] = set()
        for start in range(0, len(unique), self._SHA_CHUNK):
            chunk = unique[start : start + self._SHA_CHUNK]
            placeholders = ",".join("?" for _ in chunk)
            found.update(
                row["sha256"]
                for row in self._conn.execute(
                    f"SELECT DISTINCT sha256 FROM file_copies WHERE sha256 IN ({placeholders})",
                    chunk,
                )
            )
        return found

    def explain_drives_holding(self, shas: Sequence[str]) -> list[sqlite3.Row]:
        """The query plan for :meth:`drives_holding`, so a test can assert it is not a scan."""
        chunk = list(dict.fromkeys(shas))[: self._SHA_CHUNK]
        return list(
            self._conn.execute(f"EXPLAIN QUERY PLAN {self._drives_holding_sql(chunk)}", chunk)
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
        """For ``status``: content that exists on exactly one drive (a single point of loss).

        **A copy looked for and not found is not a place.** This sentence is a promise about now,
        so it excludes ``missing_at`` rows - see :meth:`list_drives` for why the drive list does
        the opposite. `(abg)`.
        """
        return list(
            self._conn.execute(
                """
                SELECT fc.sha256, f.original_name, d.label AS drive_label
                FROM file_copies fc
                JOIN files f ON f.sha256 = fc.sha256
                JOIN drives d ON d.uuid = fc.drive_uuid
                WHERE fc.missing_at IS NULL AND fc.sha256 IN (
                    SELECT sha256 FROM file_copies WHERE missing_at IS NULL
                    GROUP BY sha256 HAVING COUNT(*) = 1
                )
                ORDER BY f.original_name
                """
            )
        )

    def single_copy_count(self) -> int:
        """How many files exist on exactly one drive -- the number, without the names.

        Excludes copies known absent, on :meth:`single_copy_shas`'s reasoning.

        Was calling :meth:`single_copy_shas`, which joins to two tables and sorts every at-risk
        row by name so it can throw all of it away. Measured at 100k files that was 425 ms per
        refresh against 27 ms here. Same question, asked directly.

        **Corrected 2026-08-05.** This used to say "the custody strip refreshes on every screen
        and only ever renders this count". Both halves were false: the strip does not refresh on
        a screen switch (`showScreen` does not call it), and it never rendered this count at all
        - it rendered a per-drive number instead. The strip now uses :meth:`custody_floor`,
        which this method cannot replace: reading ``FROM file_copies`` makes a file with no copy
        row invisible here.

        Equivalent to ``len(single_copy_shas())``: both count sha256 values with exactly one
        row in ``file_copies``, and `test_single_copy_count_matches_the_listing` holds them
        together so the cheap answer cannot drift from the detailed one.
        """
        cursor = self._conn.execute(
            "SELECT COUNT(*) FROM (SELECT sha256 FROM file_copies "
            "WHERE missing_at IS NULL GROUP BY sha256 HAVING COUNT(*) = 1)"
        )
        return int(cursor.fetchone()[0])

    def custody_floor(self) -> sqlite3.Row:
        """Per-FILE redundancy: how many copies the *weakest* file has, and how many are exposed.

        The ``LEFT JOIN`` excludes copies known absent, so a file whose only copy was looked for
        and not found lands in ``no_copy`` - the most exposed state, which is where it belongs.
        :meth:`single_copy_shas` carries the reasoning; :meth:`list_drives` carries the opposite
        rule for the surface that reports history.

        The custody strip makes a per-file claim in English - "in only one place" - so it has to
        be answered with a per-file number. `single_copy_count` cannot do it alone: it reads
        ``FROM file_copies``, so a `files` row with **no** copy row at all is invisible to it and
        counts as neither safe nor at risk. That file is the most exposed thing in the library.

        ``floor`` is the minimum copy count across every file, so it can never over-promise: one
        unprotected file holds the whole library's floor down, which is the point of a
        risk-first reading.

        ``held`` and ``held_floor`` answer the same question over files that have **at least
        one** copy. The strip needs both: a file with no copy at all is reported on the Stats
        screen rather than in the rail, so it must not drag the rail's floor to zero and leave it
        with nothing to say - but it must also not be papered over, which is why a library that
        has any keeps the *count* wording ("N files in M places") instead of the universal
        ("every file in M places"). A universal that silently excludes rows is the same defect
        this method was written to remove, one level down.

        Complexity: **O(n)** over `files` LEFT JOINed to `file_copies`, grouped once - the same
        shape as :meth:`single_copy_count`, one query rather than three.
        """
        cursor = self._conn.execute(
            """
            WITH per_file AS (
                SELECT f.sha256 AS sha, COUNT(fc.sha256) AS copies
                FROM files f
                LEFT JOIN file_copies fc
                       ON fc.sha256 = f.sha256 AND fc.missing_at IS NULL
                GROUP BY f.sha256
            )
            SELECT
                COALESCE(SUM(CASE WHEN copies = 0 THEN 1 ELSE 0 END), 0) AS no_copy,
                COALESCE(SUM(CASE WHEN copies = 1 THEN 1 ELSE 0 END), 0) AS one_copy,
                COALESCE(MIN(copies), 0) AS floor,
                COALESCE(SUM(CASE WHEN copies > 0 THEN 1 ELSE 0 END), 0) AS held,
                COALESCE(MIN(CASE WHEN copies > 0 THEN copies END), 0) AS held_floor
            FROM per_file
            """
        )
        row: sqlite3.Row = cursor.fetchone()
        return row

    def event_by_signature(self, signature: str) -> sqlite3.Row | None:
        """A previously-named event with this cluster signature, if any."""
        cursor = self._conn.execute(
            "SELECT id, name, slug, start_date, file_count, signature FROM events WHERE signature = ?",
            (signature,),
        )
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

    def source_hints_for_drive(self, drive_uuid: str) -> list[sqlite3.Row]:
        """Where each of a drive's dated Camera copies was first read from. **O(rows).**

        The input a folder-name suggestion is derived from, deliberately SEPARATE from
        `camera_copies_for_events` rather than a widening of it. That query decides what
        CLUSTERS; carrying `source_path` on it would let a display concern change the grouping it
        is only supposed to describe.

        The two share a filter - same drive, Camera, dated - and that is load-bearing rather than
        incidental: a hint for a file no cluster holds could never be shown, and a cluster member
        with no hint would silently drop out of the denominator and strengthen every majority.
        `test_it_matches_the_clustering_population_exactly` is what keeps them in step.

        A row whose ``source_path`` is NULL is still returned, for the same reason: missing
        evidence weakens a claim rather than being quietly excluded from it.
        """
        return list(
            self._conn.execute(
                """
                SELECT fc.sha256, f.source_path, f.captured_at
                FROM file_copies fc
                JOIN files f ON f.sha256 = fc.sha256
                WHERE fc.drive_uuid = ? AND f.category = 'Camera' AND f.captured_at IS NOT NULL
                """,
                (drive_uuid,),
            )
        )

    def named_event_signatures(self) -> dict[str, str]:
        """``{event signature: that event's name}`` for every named event. **O(named events).**

        Keyed by SIGNATURE because that is what event identity IS - a SHA-256 over the sorted
        member SHA-256s (`events.signature`, the UNIQUE key `event_by_signature` looks up). A
        cluster whose membership changed hashes differently and correctly misses: it is a new
        object that merely overlaps a named one, not that event.
        """
        return {
            str(row["signature"]): str(row["name"])
            for row in self._conn.execute("SELECT signature, name FROM events")
        }

    def named_trip_days(self) -> dict[str, str]:
        """``{claimed day: that trip's name}`` for every day any trip holds. **O(claimed days).**

        Keyed by DAY rather than by trip id because the review screen has to answer "is the trip
        this card describes already named?" for a card that carries no trip id - a proposal is
        recomputed from clusters every visit and knows only its days. A day is claimed by at most
        one trip (`trip_days.day` is the primary key), so the mapping cannot be ambiguous.
        """
        return {
            str(row["day"]): str(row["name"])
            for row in self._conn.execute(
                "SELECT td.day AS day, t.name AS name"
                " FROM trip_days td JOIN trips t ON t.id = td.trip_id"
            )
        }

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

    # --- decision snapshot -------------------------------------------------------------
    # Reads for `decisions.py`, which carries the choices a rescan cannot recompute onto a drive.
    # Column-by-column, never `SELECT *`: a column added later must not reach a user's drive by
    # default, and that is a privacy guarantee rather than a style preference.

    def drive_row(self, uuid: str) -> sqlite3.Row | None:
        """A drive's own record, or ``None``. **O(1)** on the primary key.

        ``last_seen`` is here for `(adx)`: it is the only record of WHEN a drive was previously
        seen, and `upsert_drive` refreshes it - so anything that wants to report the previous
        sighting has to read it **before** that call, not after. Existing callers use named access
        and are unaffected by the extra column.
        """
        cursor = self._conn.execute(
            "SELECT uuid, label, notes, last_seen FROM drives WHERE uuid = ?", (uuid,)
        )
        row: sqlite3.Row | None = cursor.fetchone()
        return row

    def all_settings(self) -> dict[str, str]:
        """Every stored setting. Callers publishing these must filter them first."""
        return {
            str(r["key"]): str(r["value"])
            for r in self._conn.execute("SELECT key, value FROM settings")
        }

    def refresh_statistics_if_stale(self) -> bool:
        """Run `ANALYZE` when the library has grown enough to make the old statistics wrong.

        **Never on open**, which would charge `status` and `where` for something they cannot use.
        Called when a unit of work that WROTE finishes - see `catalog_session.open_catalog` - so
        the check itself costs one `max(id)` (`O(1)` on the primary key) and one settings read,
        and only on a command that changed something.

        `ANALYZE` had never run at all before 2026-08-09: there was no `sqlite_stat1`, so every
        join was planned on guesses. Measured on the real catalog, Find went 4.59 ms -> 2.15 ms.
        """
        high_water = self._conn.execute("SELECT COALESCE(MAX(id), 0) FROM files").fetchone()[0]
        last = self.get_setting(ANALYZED_AT_KEY)
        if last is not None and int(high_water) - int(last) < ANALYZE_GROWTH_ROWS:
            return False
        with self._tx() as conn:
            conn.execute("ANALYZE")
        self.set_setting(ANALYZED_AT_KEY, str(int(high_water)))
        return True

    def registered_drives(self) -> list[sqlite3.Row]:
        """Every drive's identity and label. **No join** - `O(drives)`.

        `list_drives` counts copies and sums their bytes over `file_copies`, which is right for a
        listing and wrong for a decisions write that fires after ordinary commands: it would make
        a 1.3 KB backup pay for an aggregate over every copy on every drive.
        """
        return list(self._conn.execute("SELECT uuid, label, notes FROM drives ORDER BY label"))

    def all_trips(self) -> list[sqlite3.Row]:
        """Every trip, id included -- the id is how a caller joins `all_trip_days` back to it.

        The id is local to this catalog and must not leave it; `decisions.gather_decisions`
        resolves the days with it and writes the DAYS, never the id.
        """
        return list(
            self._conn.execute("SELECT id, name, slug, start_date, end_date FROM trips ORDER BY id")
        )

    def all_trip_days(self) -> dict[str, int]:
        return {
            str(r["day"]): int(r["trip_id"])
            for r in self._conn.execute("SELECT day, trip_id FROM trip_days ORDER BY day")
        }

    def all_events(self) -> list[sqlite3.Row]:
        return list(
            self._conn.execute("SELECT name, slug, start_date, signature FROM events ORDER BY id")
        )

    def all_date_confirmations(self) -> list[sqlite3.Row]:
        return list(
            self._conn.execute(
                "SELECT sha256, captured_at, confirmed_at, confirmed_by"
                " FROM date_confirmations ORDER BY sha256"
            )
        )

    def date_confirmation_for(self, sha256: str) -> sqlite3.Row | None:
        """The confirmation this catalog already holds for content, or ``None``. **O(1)**."""
        cursor = self._conn.execute(
            "SELECT captured_at, confirmed_at FROM date_confirmations WHERE sha256 = ?", (sha256,)
        )
        row: sqlite3.Row | None = cursor.fetchone()
        return row

    def all_album_names(self) -> list[str]:
        return [str(r["name"]) for r in self._conn.execute("SELECT name FROM albums ORDER BY id")]

    def knows_content(self, sha256: str) -> bool:
        """Whether this catalog has a `files` row for this content. **O(1)**."""
        return (
            self._conn.execute("SELECT 1 FROM files WHERE sha256 = ?", (sha256,)).fetchone()
            is not None
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

    def refresh_drive_verified(self, uuid: str) -> None:
        """Re-derive the drive's ``last_verified`` from its copies: the OLDEST, or NULL.

        **Derived rather than stamped, and that is the whole of `(abg)` Stage 2.** This used to
        be ``set_drive_verified(uuid, when)``, called unconditionally at the end of every verify
        run - so a run whose own summary said ``missing: 2269`` dated the drive *now*, and a run
        cancelled at the first file did the same. Stage 1 had just carried this date to the
        sentence a person reads, which meant the reassuring claim got **fresher** on evidence
        that contradicted it.

        The rule is :func:`~truestill_core.drive.custody_freshness`'s, one level down: a claim is
        only as fresh as its weakest leg. ``MIN`` over the copies, and ``NULL`` the moment any of
        them has never been confirmed - which covers *missing*, *unreadable*, *unverifiable* and
        *not reached before the user cancelled* without having to enumerate them. Nothing here
        takes a timestamp from the caller, so it is **structurally** incapable of over-claiming
        rather than correct only while every call site remembers to check.

        A drive with no copies keeps ``NULL``: there is nothing to have confirmed.
        """
        with self._tx() as conn:
            conn.execute(
                """
                UPDATE drives SET last_verified = (
                    SELECT CASE WHEN COUNT(*) = COUNT(fc.last_verified)
                                THEN MIN(fc.last_verified) END
                    FROM file_copies fc WHERE fc.drive_uuid = drives.uuid
                )
                WHERE uuid = ?
                """,
                (uuid,),
            )

    def mark_copy_missing(self, *, sha256: str, drive_uuid: str, when: str) -> None:
        """Remember that we looked for this copy on a drive that was there, and it was not.

        Clears ``last_verified`` in the same statement: a copy cannot simultaneously be confirmed
        present and known absent, and leaving the old date would let :meth:`refresh_drive_verified`
        keep dating a claim off a confirmation the next check disproved.

        **THE CLEAR MATTERS MORE THAN THE SET, AND IS THE EASIER ONE TO LOSE.** Both ways back -
        :meth:`mark_copy_verified` and :meth:`record_copy` - blank this column, and neither may be
        simplified away. Mutation testing found both unguarded, which is what a corrective state
        tested only for how it is *set* looks like from the inside. **A stuck ``missing_at`` is
        worse than the defect it was added for, because that defect at least corrected itself
        when the news turned good:** a user who restores a drive and re-checks it would see their
        files still reported as living in one place, with nothing they could do about it.

        **The row is never deleted.** It is the record that content was once written here, and
        the only clue left to what happened - see the column comment in ``_SCHEMA``.
        """
        with self._tx() as conn:
            conn.execute(
                "UPDATE file_copies SET missing_at = ?, last_verified = NULL "
                "WHERE sha256 = ? AND drive_uuid = ?",
                (when, sha256, drive_uuid),
            )

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
                    size = excluded.size, copied_at = excluded.copied_at,
                    -- A re-copy re-establishes the place, so a remembered absence is spent.
                    -- Without this, restoring a drive by copying into it would leave every
                    -- restored file uncounted until the user thought to run a verify. `(abg)`.
                    missing_at = NULL
                """,
                (sha256, drive_uuid, relative, copy_sha256, size, _now()),
            )

    def mark_copy_verified(self, *, sha256: str, drive_uuid: str, when: str) -> None:
        """Confirm a copy is present with the bytes we recorded, clearing any remembered absence.

        The clear is the same statement on purpose: a copy that just hashed correctly is not
        absent, and a stale ``missing_at`` would keep it out of every custody count while
        ``last_verified`` said it was fine. One observation, one row, no window between them.
        """
        with self._tx() as conn:
            conn.execute(
                "UPDATE file_copies SET last_verified = ?, missing_at = NULL "
                "WHERE sha256 = ? AND drive_uuid = ?",
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
        capture: CaptureContext | None = None,
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
        # Bound once so the INSERT reads the same whether or not a caller supplied one: an empty
        # context is five NULLs, which is exactly what "we were not told" means here.
        shot = capture if capture is not None else CaptureContext()
        now = _now()
        with self._tx() as conn:
            conn.execute(
                """
                INSERT INTO files (
                    source_path, original_name, sha256, copy_sha256, perceptual, size,
                    captured_at, category, relative, event_id, upload_status, processed_at,
                    uploaded_at, date_source, date_tag,
                    camera_make, camera_model, lens_model, gps_latitude, gps_longitude
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'uploaded', ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    date_tag      = excluded.date_tag,
                    camera_make   = excluded.camera_make,
                    camera_model  = excluded.camera_model,
                    lens_model    = excluded.lens_model,
                    gps_latitude  = excluded.gps_latitude,
                    gps_longitude = excluded.gps_longitude
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
                    shot.camera_make,
                    shot.camera_model,
                    shot.lens_model,
                    shot.gps_latitude,
                    shot.gps_longitude,
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
