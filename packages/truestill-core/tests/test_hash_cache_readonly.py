"""A read-only hash cache: takes hits, writes nothing, and cannot write even if asked.

**Why this exists.** Analyze wants tier 2a (exact duplicates) without tier 2b (look-alikes),
which means hashing SHA-256 and skipping the perceptual hash. Writing that to the cache would
be a silent disaster: `perceptual TEXT` is nullable and has **one representation for two
meanings** -- "not an image" and "not computed" -- and `HashCache.get` has a `need_sha`
parameter precisely because `sha256` has the same ambiguity, with **no `need_perceptual`
counterpart**. A row written by such a run would come back as a hit on the next organize
preview, near-duplicate detection would silently vanish for those files, and nothing would say
so. That breaks `(r)`'s invariant 3: *the cache can only ever cost extra work, never produce a
wrong answer.*

Reading is safe; only writing poisons. So the read-only mode keeps every benefit and removes
the hazard entirely.

**Structural, not policy.** The connection is opened `mode=ro`, so SQLite itself refuses every
write. A boolean the writer merely agrees to honour would be one refactor from being ignored;
`test_the_connection_itself_refuses_a_write` is what makes that difference checkable.
"""

from __future__ import annotations

import contextlib
import sqlite3
from pathlib import Path

import pytest
from truestill_core.hash_cache import HashCache
from truestill_core.models import FileHashes

_HASHES = FileHashes(sha256="a" * 64, perceptual="ffff0000ffff0000")


def _seed(cache_path: Path, target: Path) -> None:
    """Write one real row with a writable cache, so the read-only one has something to find."""
    target.write_bytes(b"x" * 10)
    stat = target.stat()
    with HashCache(cache_path) as cache:
        cache.put(target, stat.st_size, stat.st_mtime_ns, _HASHES, perceptual_computed=True)


def _read(cache: HashCache, target: Path) -> FileHashes | None:
    stat = target.stat()
    return cache.get(target, stat.st_size, stat.st_mtime_ns, need_sha=True)


# --- reading still works, which is the entire point ------------------------------------------


def test_a_read_only_cache_returns_the_hits_a_writable_one_recorded(tmp_path: Path) -> None:
    target = tmp_path / "IMG_0001.jpg"
    cache_path = tmp_path / "catalog.cache.sqlite"
    _seed(cache_path, target)

    with HashCache(cache_path, writable=False) as cache:
        assert cache.enabled
        assert _read(cache, target) == _HASHES


def test_metadata_hits_are_returned_too(tmp_path: Path) -> None:
    """The metadata half of the cache is read the same way and must not be left behind."""
    target = tmp_path / "IMG_0001.jpg"
    target.write_bytes(b"x" * 10)
    stat = target.stat()
    cache_path = tmp_path / "catalog.cache.sqlite"
    with HashCache(cache_path) as cache:
        cache.put_metadata(target, stat.st_size, stat.st_mtime_ns, "fp1", {"Model": "Pixel"})

    with HashCache(cache_path, writable=False) as cache:
        assert cache.get_metadata(target, stat.st_size, stat.st_mtime_ns, "fp1") == {
            "Model": "Pixel"
        }


# --- and writing does not happen ---------------------------------------------------------------


def test_a_put_through_a_read_only_cache_reaches_the_file_never(tmp_path: Path) -> None:
    """Asserted by reopening WRITABLE and looking, not by trusting the write path's own report."""
    target = tmp_path / "IMG_0001.jpg"
    cache_path = tmp_path / "catalog.cache.sqlite"
    _seed(cache_path, target)
    other = tmp_path / "IMG_0002.jpg"
    other.write_bytes(b"y" * 20)
    stat = other.stat()

    with HashCache(cache_path, writable=False) as cache:
        cache.put(other, stat.st_size, stat.st_mtime_ns, _HASHES, perceptual_computed=True)

    with HashCache(cache_path) as cache:
        assert _read(cache, other) is None, "a read-only cache wrote a row"


def test_metadata_writes_are_suppressed_as_well(tmp_path: Path) -> None:
    target = tmp_path / "IMG_0001.jpg"
    target.write_bytes(b"x" * 10)
    stat = target.stat()
    cache_path = tmp_path / "catalog.cache.sqlite"
    _seed(cache_path, tmp_path / "seed.jpg")

    with HashCache(cache_path, writable=False) as cache:
        cache.put_metadata(target, stat.st_size, stat.st_mtime_ns, "fp1", {"Model": "Pixel"})

    with HashCache(cache_path) as cache:
        assert cache.get_metadata(target, stat.st_size, stat.st_mtime_ns, "fp1") is None


def test_pruning_does_not_run(tmp_path: Path) -> None:
    """Pruning is a write, and a read-only session must not perform one.

    It matters beyond tidiness: an Analyze over folder A must not decide anything about rows
    belonging to folder B, and the safest way to guarantee that is to delete nothing at all.
    """
    gone = tmp_path / "deleted.jpg"
    cache_path = tmp_path / "catalog.cache.sqlite"
    _seed(cache_path, gone)
    gone.unlink()

    with HashCache(cache_path, writable=False) as cache:
        assert cache.enabled

    with contextlib.closing(sqlite3.connect(cache_path)) as probe:
        rows = probe.execute("SELECT COUNT(*) FROM hash_cache").fetchone()[0]
    assert rows == 1, "the read-only session pruned a row"


def test_the_connection_itself_refuses_a_write(tmp_path: Path) -> None:
    """Structural, not policy: SQLite refuses, so a future caller cannot opt back in.

    If this ever fails, read-only has become a convention the code merely agrees to follow,
    and the poisoning hazard is one forgotten branch away from returning.
    """
    target = tmp_path / "IMG_0001.jpg"
    cache_path = tmp_path / "catalog.cache.sqlite"
    _seed(cache_path, target)

    with HashCache(cache_path, writable=False) as cache:
        conn = cache._conn
        assert conn is not None
        with pytest.raises(sqlite3.OperationalError):
            conn.execute("DELETE FROM hash_cache")


# --- the missing-file case ----------------------------------------------------------------------


def test_a_missing_cache_file_is_not_created(tmp_path: Path) -> None:
    """ "Writes nothing" has to include the file itself, or the promise is already broken."""
    cache_path = tmp_path / "nowhere" / "catalog.cache.sqlite"

    with HashCache(cache_path, writable=False) as cache:
        assert not cache.enabled, "a read-only cache must not create its own database"

    assert not cache_path.exists()
    assert not cache_path.parent.exists(), "not even the parent directory"


def test_a_disabled_read_only_cache_simply_misses(tmp_path: Path) -> None:
    """Degrades to doing nothing rather than harm - the class's existing promise, kept."""
    target = tmp_path / "IMG_0001.jpg"
    target.write_bytes(b"x" * 10)

    with HashCache(tmp_path / "absent.sqlite", writable=False) as cache:
        assert _read(cache, target) is None


# --- cry-wolf: the writable cache is untouched ----------------------------------------------


def test_the_writable_cache_still_writes(tmp_path: Path) -> None:
    """The default must be unchanged; this whole change is opt-in."""
    target = tmp_path / "IMG_0001.jpg"
    cache_path = tmp_path / "catalog.cache.sqlite"
    _seed(cache_path, target)

    with HashCache(cache_path) as cache:
        assert _read(cache, target) == _HASHES


def test_the_writable_cache_still_prunes(tmp_path: Path) -> None:
    """Cry-wolf for the prune suppression: `(r)` invariant 5 requires pruning to actually run."""
    gone = tmp_path / "deleted.jpg"
    cache_path = tmp_path / "catalog.cache.sqlite"
    _seed(cache_path, gone)
    gone.unlink()

    with HashCache(cache_path):
        pass

    with contextlib.closing(sqlite3.connect(cache_path)) as probe:
        assert probe.execute("SELECT COUNT(*) FROM hash_cache").fetchone()[0] == 0
