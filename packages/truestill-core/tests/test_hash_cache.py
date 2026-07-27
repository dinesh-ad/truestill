"""The hash cache: it must save work, and it must never change an answer.

Every test here is one of the two questions. The cache is allowed to be wrong about whether a
file needs hashing -- being wrong just costs time -- but it is never allowed to be wrong about
what a file hashed to.
"""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime
from pathlib import Path

import pytest
from truestill_core import scan
from truestill_core.dates import resolve_capture_datetime
from truestill_core.hash_cache import HashCache, cache_path_for
from truestill_core.scan import compute_hashes


@pytest.fixture
def counted(monkeypatch: pytest.MonkeyPatch) -> dict[str, int]:
    """Count real hashing work, so "was it re-hashed?" is answered by evidence."""
    counts = {"sha": 0, "perceptual": 0}
    real_sha, real_perceptual = scan.sha256_file, scan.perceptual_hash

    def sha(path: Path) -> str:
        counts["sha"] += 1
        return real_sha(path)

    def perceptual(path: Path) -> str | None:
        counts["perceptual"] += 1
        return real_perceptual(path)

    monkeypatch.setattr(scan, "sha256_file", sha)
    monkeypatch.setattr(scan, "perceptual_hash", perceptual)
    return counts


def _files(root: Path, n: int = 4, *, same_size: bool = True) -> list[Path]:
    """Identical-size files by default, so the size pre-filter demands SHA-256 for all."""
    root.mkdir(parents=True, exist_ok=True)
    made = []
    for i in range(n):
        p = root / f"f{i}.bin"
        p.write_bytes(f"content-{i}".encode() if same_size else b"x" * (10 + i))
        made.append(p)
    return made


def test_an_unchanged_file_is_not_re_hashed(tmp_path: Path, counted: dict[str, int]) -> None:
    """The whole point, proved by counter rather than by stopwatch."""
    files = _files(tmp_path / "src")
    db = tmp_path / "c.sqlite"

    with HashCache.beside(db) as cache:
        first = compute_hashes(files, cache=cache)
    assert counted["sha"] == len(files)
    assert counted["perceptual"] == len(files)

    counted["sha"] = counted["perceptual"] = 0
    with HashCache.beside(db) as cache:
        second = compute_hashes(files, cache=cache)

    assert counted == {"sha": 0, "perceptual": 0}  # nothing was read again
    assert second == first  # and the answers are identical


def test_a_touched_file_is_re_hashed(tmp_path: Path, counted: dict[str, int]) -> None:
    """mtime moving is enough on its own -- content can change without changing size."""
    files = _files(tmp_path / "src")
    db = tmp_path / "c.sqlite"
    with HashCache.beside(db) as cache:
        compute_hashes(files, cache=cache)

    counted["sha"] = counted["perceptual"] = 0
    stat = files[0].stat()
    os.utime(files[0], ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000_000))
    with HashCache.beside(db) as cache:
        compute_hashes(files, cache=cache)

    assert counted["perceptual"] == 1  # exactly the touched one


def test_a_resized_file_is_re_hashed(tmp_path: Path, counted: dict[str, int]) -> None:
    """And size moving is enough on its own, even if mtime is put back."""
    files = _files(tmp_path / "src")
    db = tmp_path / "c.sqlite"
    with HashCache.beside(db) as cache:
        compute_hashes(files, cache=cache)

    stat = files[0].stat()
    files[0].write_bytes(b"a-different-length-entirely")
    os.utime(files[0], ns=(stat.st_atime_ns, stat.st_mtime_ns))  # mtime restored, size changed

    counted["sha"] = counted["perceptual"] = 0
    with HashCache.beside(db) as cache:
        compute_hashes(files, cache=cache)

    assert counted["perceptual"] == 1


def test_a_corrupt_cache_falls_back_to_hashing_everything(
    tmp_path: Path, counted: dict[str, int]
) -> None:
    """A cache that cannot be read is a cache that misses -- never an error, never a wrong hash."""
    files = _files(tmp_path / "src")
    db = tmp_path / "c.sqlite"
    with HashCache.beside(db) as cache:
        expected = compute_hashes(files, cache=cache)

    cache_path_for(db).write_bytes(b"this is not a database, it is a pile of bytes")

    counted["sha"] = counted["perceptual"] = 0
    with HashCache.beside(db) as cache:
        assert cache.enabled is False  # it noticed, and disabled itself
        actual = compute_hashes(files, cache=cache)

    assert actual == expected  # same answers
    assert counted["perceptual"] == len(files)  # arrived at the honest way


def test_a_cache_from_another_schema_is_rebuilt_not_misread(tmp_path: Path) -> None:
    """Derived data is rebuilt on a version it does not recognise, never migrated."""
    db = tmp_path / "c.sqlite"
    files = _files(tmp_path / "src")
    with HashCache.beside(db) as cache:
        compute_hashes(files, cache=cache)

    conn = sqlite3.connect(cache_path_for(db))
    conn.execute("PRAGMA user_version = 999")
    conn.commit()
    conn.close()

    with HashCache.beside(db) as cache:
        assert cache.enabled is True
        assert cache.get(files[0], files[0].stat().st_size, 0, need_sha=False) is None


def test_cached_and_uncached_runs_agree(tmp_path: Path) -> None:
    """The property that matters most: the cache is invisible in the output."""
    files = _files(tmp_path / "src", 6)
    db = tmp_path / "c.sqlite"

    uncached = compute_hashes(files)
    with HashCache.beside(db) as cache:
        compute_hashes(files, cache=cache)  # populate
    with HashCache.beside(db) as cache:
        cached = compute_hashes(files, cache=cache)  # serve

    assert cached == uncached


def test_a_row_without_a_sha_is_not_served_to_a_run_that_needs_one(tmp_path: Path) -> None:
    """The subtle one.

    A unique-size file is cached with ``sha256=None`` because the pre-filter skipped it. If a
    later run has a size collision -- so that file *does* need a SHA-256 -- serving the old row
    would hand back a null hash and quietly break exact dedup.
    """
    src = tmp_path / "src"
    src.mkdir()
    lonely = src / "unique.bin"
    lonely.write_bytes(b"only-one-of-this-size")
    db = tmp_path / "c.sqlite"

    with HashCache.beside(db) as cache:
        first = compute_hashes([lonely], cache=cache)
    assert first[lonely].sha256 is None  # pre-filter skipped it, correctly

    twin = src / "twin.bin"
    twin.write_bytes(b"only-one-of-this-siza")  # same length -> now a collision

    with HashCache.beside(db) as cache:
        second = compute_hashes([lonely, twin], cache=cache)

    assert second[lonely].sha256 is not None  # re-hashed rather than served a None
    assert second[twin].sha256 is not None


def test_cleanup_actually_runs(tmp_path: Path) -> None:
    """PixSort defined `cleanup_stale_entries()` and never called it, so rows accumulated
    forever. Pruning here is part of every run, not a method someone must remember."""
    files = _files(tmp_path / "src", 3)
    db = tmp_path / "c.sqlite"
    with HashCache.beside(db) as cache:
        compute_hashes(files, cache=cache)

    gone = files[0]
    gone.unlink()

    with HashCache.beside(db) as cache:
        compute_hashes(files[1:], cache=cache)  # a run that does not mention the deleted file

    with HashCache.beside(db) as cache:
        assert cache.get(gone, 0, 0, need_sha=False) is None
        assert str(gone) not in cache._rows


def test_the_cache_lives_beside_the_catalog_not_inside_it(tmp_path: Path) -> None:
    """Machine-local, path-keyed, disposable data stays out of the custody record."""
    db = tmp_path / "reports" / "catalog.sqlite"
    files = _files(tmp_path / "src", 2)

    with HashCache.beside(db) as cache:
        compute_hashes(files, cache=cache)

    assert cache_path_for(db).name == "catalog.cache.sqlite"
    assert cache_path_for(db).exists()
    assert not db.exists()  # the cache never creates or touches the catalog itself


def test_mtime_never_reaches_dating(tmp_path: Path) -> None:
    """The invariant the cache gets closest to breaking.

    The cache reads mtime; dating must still refuse to. A file whose mtime says one thing and
    whose EXIF says another is placed by the EXIF, cache or no cache.
    """
    photo = tmp_path / "p.jpg"
    photo.write_bytes(b"pretend-jpeg")
    os.utime(photo, (0, 0))  # mtime: 1970

    when, source, _ = resolve_capture_datetime(photo, {"DateTimeOriginal": "2021:06:15 10:30:00"})

    assert when == datetime(2021, 6, 15, 10, 30)
    assert source.value == "exif"
