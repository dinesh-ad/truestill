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
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType
from typing import Self

# Current catalog schema, created whole for a fresh database. Its version is
# CURRENT_SCHEMA_VERSION; older databases are brought up to it by _MIGRATIONS.
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
    PRIMARY KEY (sha256, drive_uuid)
);

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
"""

#: Bump whenever the schema changes, and add a matching entry to _MIGRATIONS.
CURRENT_SCHEMA_VERSION = 9


class CatalogVersionError(RuntimeError):
    """The catalog on disk was written by a newer truestill than this one understands."""


def _column_names(conn: sqlite3.Connection) -> set[str]:
    return {row["name"] for row in conn.execute("PRAGMA table_info(files)")}


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

    ``files.copy_sha256`` is retained but deprecated: it is a per-content field, whereas a
    copy's integrity hash belongs to the copy. New copies record their hash in ``file_copies``;
    pre-v6 ``files`` rows are not backfilled (they predate drive identity), and their
    ``copy_sha256`` remains readable for any legacy path.
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


#: Ordered migrations: ``(target_version, fn)``. Each is idempotent and lifts a database
#: from ``target_version - 1`` to ``target_version``. Append; never rewrite history.
_MIGRATIONS: tuple[tuple[int, Callable[[sqlite3.Connection], None]], ...] = (
    (2, _add_size_column),
    (3, _add_original_name_column),
    (4, _add_event_tables),
    (5, _add_takeout_tables),
    (6, _add_drive_tables),
    (7, _add_settings_table),
    (8, _add_migration_journal),
    (9, _add_reclaim_journal),
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

        Joins ``file_copies`` to ``files`` (category, captured_at) and any named event (slug,
        start), so a migration can recompute each copy's destination without re-reading the file.
        """
        return list(
            self._conn.execute(
                """
                SELECT fc.sha256, fc.relative, fc.copy_sha256, f.category, f.captured_at,
                       e.slug AS event_slug, e.start_date AS event_start
                FROM file_copies fc
                JOIN files f ON f.sha256 = fc.sha256
                LEFT JOIN events e ON e.id = f.event_id
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

    def record_migration_moves(self, moves: list[tuple[str, str, str, str, str | None]]) -> None:
        """Journal planned moves ``(sha256, drive_uuid, old, new, copy_sha256)`` before touching disk."""
        with self._tx() as conn:
            conn.executemany(
                """
                INSERT INTO migration_journal
                    (sha256, drive_uuid, old_relative, new_relative, copy_sha256)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(sha256, drive_uuid) DO UPDATE SET
                    old_relative = excluded.old_relative, new_relative = excluded.new_relative,
                    copy_sha256 = excluded.copy_sha256
                """,
                moves,
            )

    def pending_migration(self, drive_uuid: str) -> list[sqlite3.Row]:
        """Journalled moves for a drive left over from an interrupted run."""
        return list(
            self._conn.execute(
                "SELECT sha256, drive_uuid, old_relative, new_relative, copy_sha256 "
                "FROM migration_journal WHERE drive_uuid = ?",
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

    def clear_migration_move(self, sha256: str, drive_uuid: str) -> None:
        """Drop a journal row once its move (including old-copy removal) is complete."""
        with self._tx() as conn:
            conn.execute(
                "DELETE FROM migration_journal WHERE sha256 = ? AND drive_uuid = ?",
                (sha256, drive_uuid),
            )

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

    def find_by_sha256(self, sha256: str) -> sqlite3.Row | None:
        cursor = self._conn.execute("SELECT * FROM files WHERE sha256 = ?", (sha256,))
        row: sqlite3.Row | None = cursor.fetchone()
        return row

    def count(self) -> int:
        return int(self._conn.execute("SELECT COUNT(*) FROM files").fetchone()[0])

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

    def drive_by_label(self, label: str) -> sqlite3.Row | None:
        cursor = self._conn.execute("SELECT * FROM drives WHERE label = ?", (label,))
        row: sqlite3.Row | None = cursor.fetchone()
        return row

    def copies_on_drive(self, drive_uuid: str) -> list[sqlite3.Row]:
        """Every recorded copy on a drive: ``sha256, relative, copy_sha256, size``."""
        return list(
            self._conn.execute(
                "SELECT sha256, relative, copy_sha256, size FROM file_copies WHERE drive_uuid = ?",
                (drive_uuid,),
            )
        )

    def find_copies(self, term: str) -> list[sqlite3.Row]:
        """For ``where``: copies whose original name, relative path or source path match ``term``."""
        like = f"%{term}%"
        return list(
            self._conn.execute(
                """
                SELECT f.original_name, f.source_path, fc.relative, fc.last_verified,
                       d.label AS drive_label, d.uuid AS drive_uuid
                FROM file_copies fc
                JOIN files f ON f.sha256 = fc.sha256
                JOIN drives d ON d.uuid = fc.drive_uuid
                WHERE f.original_name LIKE ? OR fc.relative LIKE ? OR f.source_path LIKE ?
                ORDER BY f.original_name, d.label
                """,
                (like, like, like),
            )
        )

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

    def event_by_signature(self, signature: str) -> sqlite3.Row | None:
        """A previously-named event with this cluster signature, if any."""
        cursor = self._conn.execute("SELECT * FROM events WHERE signature = ?", (signature,))
        row: sqlite3.Row | None = cursor.fetchone()
        return row

    def skipped_signatures(self) -> frozenset[str]:
        """Cluster signatures the user chose to skip on a previous run."""
        cursor = self._conn.execute("SELECT signature FROM skipped_clusters")
        return frozenset(row["signature"] for row in cursor)

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
    ) -> int:
        """Insert (or refresh) a row marking a file as processed and uploaded; return its id.

        ``sha256`` is the source (pre-write) content hash and the dedup identity;
        ``copy_sha256`` is the organized copy's hash after any Takeout metadata write (equal to
        ``sha256`` for the byte-identical normal pipeline). When ``drive_uuid`` is given, the copy
        is also recorded in ``file_copies`` (per-content-per-drive), the authoritative location
        record. ``files.copy_sha256``/``relative`` are retained but deprecated. Album membership
        is linked many-to-many. Idempotent on ``sha256``.
        """
        now = _now()
        with self._tx() as conn:
            conn.execute(
                """
                INSERT INTO files (
                    source_path, original_name, sha256, copy_sha256, perceptual, size,
                    captured_at, category, relative, event_id, upload_status, processed_at,
                    uploaded_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'uploaded', ?, ?)
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
                    uploaded_at   = excluded.uploaded_at
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
                ),
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
