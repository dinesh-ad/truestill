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
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType
from typing import Self

_SCHEMA = """
CREATE TABLE IF NOT EXISTS files (
    id            INTEGER PRIMARY KEY,
    source_path   TEXT    NOT NULL,
    sha256        TEXT    NOT NULL UNIQUE,
    perceptual    TEXT,
    size          INTEGER,
    captured_at   TEXT,
    category      TEXT    NOT NULL,
    relative      TEXT    NOT NULL,
    upload_status TEXT    NOT NULL,
    processed_at  TEXT    NOT NULL,
    uploaded_at   TEXT
);
CREATE INDEX IF NOT EXISTS idx_files_sha256 ON files (sha256);
CREATE INDEX IF NOT EXISTS idx_files_perceptual ON files (perceptual);
CREATE INDEX IF NOT EXISTS idx_files_size ON files (size);
"""

#: Columns added after the initial release, applied to pre-existing catalogs on open.
_MIGRATIONS = (("size", "ALTER TABLE files ADD COLUMN size INTEGER"),)


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
        self._conn.executescript(_SCHEMA)
        self._migrate()
        self._conn.commit()

    def _migrate(self) -> None:
        """Add columns introduced after a catalog was first created."""
        existing = {row["name"] for row in self._conn.execute("PRAGMA table_info(files)")}
        for column, ddl in _MIGRATIONS:
            if column not in existing:
                self._conn.execute(ddl)

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

    def known_sizes(self) -> frozenset[int]:
        """Byte sizes of all catalogued files, for the scan's size pre-filter.

        A new file whose size matches a catalogued one must be SHA-256'd so cross-run exact
        duplicates are still caught; a size absent here and unique in-scan can skip hashing.
        """
        cursor = self._conn.execute("SELECT DISTINCT size FROM files WHERE size IS NOT NULL")
        return frozenset(int(row["size"]) for row in cursor)

    # -- writes --------------------------------------------------------------------

    def record_uploaded(
        self,
        *,
        source_path: str,
        sha256: str,
        perceptual: str | None,
        size: int | None,
        captured_at: str | None,
        category: str,
        relative: str,
    ) -> None:
        """Insert (or refresh) a row marking a file as processed and uploaded.

        Idempotent on ``sha256``: re-recording the same content updates the existing row
        rather than raising, so a partially-completed run can be re-run safely.
        """
        now = _now()
        with self._tx() as conn:
            conn.execute(
                """
                INSERT INTO files (
                    source_path, sha256, perceptual, size, captured_at,
                    category, relative, upload_status, processed_at, uploaded_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'uploaded', ?, ?)
                ON CONFLICT(sha256) DO UPDATE SET
                    source_path   = excluded.source_path,
                    perceptual    = excluded.perceptual,
                    size          = excluded.size,
                    captured_at   = excluded.captured_at,
                    category      = excluded.category,
                    relative      = excluded.relative,
                    upload_status = 'uploaded',
                    uploaded_at   = excluded.uploaded_at
                """,
                (source_path, sha256, perceptual, size, captured_at, category, relative, now, now),
            )
