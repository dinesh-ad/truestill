"""Remember what a file hashed to (and what exiftool last returned for it).

Measured on a 2,275-file library of 12 MP photos (~11.6 MB each), hashing is **79%** of the
cost of a preview -- 18.7s of 23.7s -- and within that, the perceptual hash dominates: a full
Pillow decode at ~69.8 ms per file against ~8.5 ms for SHA-256. The size pre-filter already
spares SHA-256 for ~94% of realistic-size files, but the perceptual hash runs for *every*
image, every time. So this caches **both**, and caching only SHA-256 would have recovered
about 5% of the wait rather than nearly all of it.

The 2026-07-29 cold-preview profile (`docs/preview-performance-profile.md`) then showed
**exiftool is 74% of wall on a cloud FUSE mount**. The same sidecar also caches the requested
metadata tags, keyed identically (path + size + ``mtime_ns``). One layer, not a second store.

**It is never inside the catalog, and since `(aae)` it is not in the catalog's directory
either** - `app_paths.cache_path_for` puts it in the cache counterpart of wherever the catalog
lives, which for a default install is the OS cache directory. Rows are keyed by absolute path,
which is **machine-specific** -- and `IMPLEMENTATION_STANDARDS.md` §3.1 already establishes that
identity is never a path, which is why drive mount points are hints rather than catalog columns.
The same reasoning applies here: throwaway, machine-local, high-churn rows have no business
sharing a file, or a backup and retention policy, with the record of which drive holds the only
copy of someone's photos. Delete this file and nothing is lost but time.

**It can only ever save work for hashes.** A hash hit requires size *and* mtime_ns to match
exactly; anything else means hashing from scratch. There is no path on which a cached hash
decides an outcome.

**Metadata is different: a stale row can change where a photo lands.** Size+mtime invalidation
matches PhotoPrism's rule and is honest when the file bytes or timestamps change. Known limit:
some tools edit tags **without** bumping mtime (documented case: IMatch). Callers that must be
sure therefore pass ``force=True`` to :func:`truestill_core.exif.read_metadata`, and **verify /
reclaim never use this cache** - they re-read bytes on disk by design.

**mtime is read here for change detection only.** It never reaches dating; that chain
(`dates.resolve_capture_datetime`) does not consult the filesystem at all, and this module does
not change that.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from types import TracebackType
from typing import Any, Self

from truestill_core.app_paths import cache_path_for as _cache_path_for
from truestill_core.models import FileHashes

#: Bumped when the row shape changes. A cache is derived data, so a version it does not
#: recognise is dropped and rebuilt rather than migrated -- there is nothing here worth
#: preserving that a re-read cannot reproduce.
#:
#: v1: hashes only. v2: adds ``tags_fp`` + ``metadata_json`` for the exiftool read cache.
SCHEMA_VERSION = 2

#: How many absent files to prune per run. Bounded so cleanup cannot degrade into an
#: O(whole-cache) stat storm on a library that is mostly untouched -- the point is that it
#: runs *every time* rather than being defined and never called, which is the mistake the
#: PixSort audit recorded.
PRUNE_LIMIT = 2_000

_SCHEMA = """
CREATE TABLE IF NOT EXISTS hash_cache (
    path          TEXT PRIMARY KEY,
    size          INTEGER NOT NULL,
    mtime_ns      INTEGER NOT NULL,
    sha256        TEXT,
    perceptual    TEXT,
    tags_fp       TEXT,
    metadata_json TEXT
);
"""

# Row: size, mtime_ns, sha256, perceptual, tags_fp, metadata_json
_Row = tuple[int, int, str | None, str | None, str | None, str | None]


def cache_path_for(catalog: Path) -> Path:
    """The cache belonging to ``catalog``. Delegates to `app_paths`, which owns the rule.

    Kept as a re-export so the eleven ``HashCache.beside(db)`` call sites and their tests do not
    each need to know it - one home for "where does the cache go", per the companion rule.
    """
    return _cache_path_for(catalog)


def tags_fingerprint(requested: tuple[str, ...], numeric: tuple[str, ...] = ()) -> str:
    """Stable short digest of the tag set a metadata row was written for.

    If ``REQUESTED_TAGS`` (or the numeric GPS set) grows or shrinks, every cached metadata
    row misses rather than partially answering a question it was not asked.
    """
    payload = "\0".join((*requested, "#", *numeric)).encode()
    return hashlib.sha256(payload).hexdigest()[:16]


class HashCache:
    """A path→hashes (and path→metadata) cache that degrades to doing nothing rather than harm.

    Every failure mode -- unreadable file, corrupt database, unknown schema -- leaves an
    instance that reports misses and swallows writes, so callers never branch on whether the
    cache is working. The only observable difference is how long the run takes.
    """

    def __init__(self, path: Path | None, *, writable: bool = True) -> None:
        """Open the sidecar. ``writable=False`` takes hits and can never write one.

        **Read-only exists for a specific hazard, not for tidiness.** A caller that computes
        only *some* of a file's hashes -- Analyze's tier 2a wants SHA-256 without the
        perceptual hash -- must not record that, because ``perceptual`` is nullable and carries
        **two meanings in one value**: "not an image" and "not computed". :meth:`get` takes
        ``need_sha`` precisely because ``sha256`` has that ambiguity, and there is no
        ``need_perceptual`` counterpart. Such a row would return as a hit and silently delete
        near-duplicate detection for those files. Reading is safe; only writing poisons.

        **Enforced by SQLite, not by agreement.** The connection is opened ``mode=ro``, so a
        write raises rather than relying on every future caller to remember. A missing file
        simply fails to open, which the class already treats as a cache that misses -- and
        crucially it is **not created**, so a read-only session leaves no trace at all.
        """
        self._conn: sqlite3.Connection | None = None
        self._rows: dict[str, _Row] = {}
        self._pending: dict[str, _Row] = {}
        self._seen: set[str] = set()
        self._writable = writable
        if path is None:
            return
        try:
            conn = self._connect(path, writable=writable)
            # One bulk read rather than a query per file: 21 ms for 20,000 rows, measured,
            # against ~10 us x N for individual lookups.
            self._rows = {
                str(row[0]): (
                    int(row[1]),
                    int(row[2]),
                    row[3],
                    row[4],
                    row[5],
                    row[6],
                )
                for row in conn.execute(
                    "SELECT path, size, mtime_ns, sha256, perceptual, tags_fp, metadata_json "
                    "FROM hash_cache"
                )
            }
            self._conn = conn
        except (sqlite3.Error, OSError, ValueError):
            # A cache that cannot be read is simply a cache that misses.
            self._conn = None
            self._rows = {}

    @staticmethod
    def _connect(path: Path, *, writable: bool) -> sqlite3.Connection:
        """The connection, prepared for its mode. Raises for anything unusable.

        Read-only never creates the file, never creates its parent, and never repairs a schema
        it does not recognise -- an unknown version is refused rather than migrated, because
        migrating is a write.
        """
        if not writable:
            conn = sqlite3.connect(f"{path.absolute().as_uri()}?mode=ro", uri=True)
            if conn.execute("PRAGMA user_version").fetchone()[0] != SCHEMA_VERSION:
                conn.close()
                message = "read-only hash cache is at an unrecognised schema version"
                raise sqlite3.DatabaseError(message)
            return conn
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(path)
        if conn.execute("PRAGMA user_version").fetchone()[0] != SCHEMA_VERSION:
            conn.executescript("DROP TABLE IF EXISTS hash_cache;")
            conn.executescript(_SCHEMA)
            conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
            conn.commit()
        conn.executescript(_SCHEMA)
        return conn

    @classmethod
    def beside(cls, catalog: Path | None) -> Self:
        """Open the sidecar for ``catalog``, or a disabled cache when there is no catalog."""
        return cls(cache_path_for(catalog) if catalog is not None else None)

    @property
    def enabled(self) -> bool:
        return self._conn is not None

    def _base_row(self, key: str, size: int, mtime_ns: int) -> _Row:
        """Pending or stored row when size+mtime still match; else a blank row for this key."""
        prev = self._pending.get(key) or self._rows.get(key)
        if prev is not None and prev[0] == size and prev[1] == mtime_ns:
            return prev
        return (size, mtime_ns, None, None, None, None)

    def get(self, path: Path, size: int, mtime_ns: int, *, need_sha: bool) -> FileHashes | None:
        """The recorded hashes for a file that has not changed, else ``None``.

        ``need_sha`` is part of the question, not an afterthought: a row written when the size
        pre-filter skipped SHA-256 carries ``sha256=None``, which is a perfectly good answer
        for a run that still does not need it and an insufficient one for a run that does.
        Treating that as a hit would quietly hand back a null hash and break exact dedup.
        """
        key = str(path)
        self._seen.add(key)
        row = self._rows.get(key)
        if row is None:
            return None
        cached_size, cached_mtime, sha, perceptual, _tags_fp, _meta = row
        if cached_size != size or cached_mtime != mtime_ns:
            return None
        if need_sha and sha is None:
            return None
        return FileHashes(sha256=sha, perceptual=perceptual)

    def put(self, path: Path, size: int, mtime_ns: int, hashes: FileHashes) -> None:
        if not self._writable:
            return
        key = str(path)
        self._seen.add(key)
        base = self._base_row(key, size, mtime_ns)
        self._pending[key] = (
            size,
            mtime_ns,
            hashes.sha256,
            hashes.perceptual,
            base[4],
            base[5],
        )

    def get_metadata(
        self, path: Path, size: int, mtime_ns: int, tags_fp: str
    ) -> dict[str, Any] | None:
        """Cached exiftool tags when size, mtime, and tag-set fingerprint all match."""
        key = str(path)
        self._seen.add(key)
        row = self._rows.get(key)
        if row is None:
            return None
        cached_size, cached_mtime, _sha, _ph, cached_fp, raw = row
        if cached_size != size or cached_mtime != mtime_ns:
            return None
        if cached_fp != tags_fp or raw is None:
            return None
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return None
        return data if isinstance(data, dict) else None

    def put_metadata(
        self, path: Path, size: int, mtime_ns: int, tags_fp: str, metadata: dict[str, Any]
    ) -> None:
        if not self._writable:
            return
        key = str(path)
        self._seen.add(key)
        base = self._base_row(key, size, mtime_ns)
        self._pending[key] = (
            size,
            mtime_ns,
            base[2],
            base[3],
            tags_fp,
            json.dumps(metadata, separators=(",", ":"), sort_keys=True),
        )

    def commit(self) -> None:
        """Write what this run learned, and prune what it can prove is gone.

        Cleanup is here, in the path every run takes, rather than in a method somebody has to
        remember to call.
        """
        if self._conn is None or not self._writable:
            # Pruning lives here too, and pruning is a write. A read-only session must decide
            # nothing about rows it did not put there.
            return
        try:
            if self._pending:
                self._conn.executemany(
                    "INSERT INTO hash_cache "
                    "(path, size, mtime_ns, sha256, perceptual, tags_fp, metadata_json) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT(path) DO UPDATE SET "
                    "size=excluded.size, mtime_ns=excluded.mtime_ns, "
                    "sha256=excluded.sha256, perceptual=excluded.perceptual, "
                    "tags_fp=excluded.tags_fp, metadata_json=excluded.metadata_json",
                    [(k, *v) for k, v in self._pending.items()],
                )
                self._pending.clear()
            self._prune()
            self._conn.commit()
        except sqlite3.Error:
            self._conn = None  # a cache that cannot be written is a cache that misses

    def _prune(self) -> None:
        """Drop rows whose file is gone. Bounded, and never checks a path this run just used."""
        if self._conn is None:
            return
        stale = [
            key
            for key in list(self._rows)[:PRUNE_LIMIT]
            if key not in self._seen and not Path(key).exists()
        ]
        if stale:
            self._conn.executemany("DELETE FROM hash_cache WHERE path = ?", [(k,) for k in stale])
            for key in stale:
                self._rows.pop(key, None)

    def close(self) -> None:
        if self._conn is not None:
            self.commit()
            if self._conn is not None:
                self._conn.close()
            self._conn = None

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()
