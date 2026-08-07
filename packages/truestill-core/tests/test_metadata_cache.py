"""Metadata half of HashCache: warm preview must not re-invoke exiftool."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

import pytest
import truestill_core.exif as exif_mod
from truestill_core.exif import _NUMERIC_TAGS, REQUESTED_TAGS, read_metadata
from truestill_core.hash_cache import HashCache, tags_fingerprint
from truestill_core.models import FileHashes


@pytest.fixture
def counted_exif(monkeypatch: pytest.MonkeyPatch) -> dict[str, int]:
    """Count real exiftool subprocess invocations."""
    counts = {"runs": 0}
    real = subprocess.run

    def wrapped(*args: Any, **kwargs: Any) -> Any:
        cmd = args[0] if args else kwargs.get("args")
        if isinstance(cmd, (list, tuple)) and cmd and "exiftool" in str(cmd[0]):
            counts["runs"] += 1
        return real(*args, **kwargs)

    monkeypatch.setattr(subprocess, "run", wrapped)
    monkeypatch.setattr(exif_mod.binaries, "run", wrapped)
    return counts


def _photo(path: Path, payload: bytes = b"fake-jpeg") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return path


@pytest.mark.skipif(__import__("shutil").which("exiftool") is None, reason="exiftool not installed")
def test_warm_second_read_makes_zero_exiftool_calls(
    tmp_path: Path, counted_exif: dict[str, int]
) -> None:
    files = [_photo(tmp_path / "a.jpg"), _photo(tmp_path / "b.jpg", b"other")]
    db = tmp_path / "c.sqlite"

    with HashCache.beside(db) as cache:
        first = read_metadata(files, cache=cache)
    assert counted_exif["runs"] >= 1
    assert len(first) == 2

    counted_exif["runs"] = 0
    with HashCache.beside(db) as cache:
        second = read_metadata(files, cache=cache)

    assert counted_exif["runs"] == 0  # the whole point
    assert second == first


@pytest.mark.skipif(__import__("shutil").which("exiftool") is None, reason="exiftool not installed")
def test_changed_mtime_invalidates_metadata(tmp_path: Path, counted_exif: dict[str, int]) -> None:
    photo = _photo(tmp_path / "a.jpg")
    db = tmp_path / "c.sqlite"
    with HashCache.beside(db) as cache:
        read_metadata([photo], cache=cache)

    counted_exif["runs"] = 0
    stat = photo.stat()
    os.utime(photo, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000_000))
    with HashCache.beside(db) as cache:
        read_metadata([photo], cache=cache)
    assert counted_exif["runs"] == 1


@pytest.mark.skipif(__import__("shutil").which("exiftool") is None, reason="exiftool not installed")
def test_changed_size_invalidates_metadata(tmp_path: Path, counted_exif: dict[str, int]) -> None:
    photo = _photo(tmp_path / "a.jpg")
    db = tmp_path / "c.sqlite"
    with HashCache.beside(db) as cache:
        read_metadata([photo], cache=cache)

    counted_exif["runs"] = 0
    stat = photo.stat()
    photo.write_bytes(b"a-different-length-payload")
    os.utime(photo, ns=(stat.st_atime_ns, stat.st_mtime_ns))
    with HashCache.beside(db) as cache:
        read_metadata([photo], cache=cache)
    assert counted_exif["runs"] == 1


@pytest.mark.skipif(__import__("shutil").which("exiftool") is None, reason="exiftool not installed")
def test_force_bypasses_metadata_cache(tmp_path: Path, counted_exif: dict[str, int]) -> None:
    photo = _photo(tmp_path / "a.jpg")
    db = tmp_path / "c.sqlite"
    with HashCache.beside(db) as cache:
        read_metadata([photo], cache=cache)

    counted_exif["runs"] = 0
    with HashCache.beside(db) as cache:
        read_metadata([photo], cache=cache, force=True)
    assert counted_exif["runs"] == 1


@pytest.mark.skipif(__import__("shutil").which("exiftool") is None, reason="exiftool not installed")
def test_expanded_requested_tags_invalidates_metadata(
    tmp_path: Path, counted_exif: dict[str, int], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A row written for an older tag set must miss, not partially answer."""
    photo = _photo(tmp_path / "a.jpg")
    db = tmp_path / "c.sqlite"
    with HashCache.beside(db) as cache:
        read_metadata([photo], cache=cache)

    counted_exif["runs"] = 0
    monkeypatch.setattr(
        exif_mod,
        "REQUESTED_TAGS",
        (*REQUESTED_TAGS, "LensSerialNumber"),
    )
    with HashCache.beside(db) as cache:
        read_metadata([photo], cache=cache)
    assert counted_exif["runs"] == 1


def test_tags_fingerprint_changes_when_the_set_grows() -> None:
    base = tags_fingerprint(REQUESTED_TAGS, _NUMERIC_TAGS)
    grown = tags_fingerprint((*REQUESTED_TAGS, "NewTag"), _NUMERIC_TAGS)
    assert base != grown


def test_hash_put_preserves_cached_metadata(tmp_path: Path) -> None:
    """Hashing and metadata share one row; writing hashes must not wipe tags."""
    photo = _photo(tmp_path / "a.jpg")
    db = tmp_path / "c.sqlite"
    st = photo.stat()
    with HashCache.beside(db) as cache:
        cache.put_metadata(
            photo,
            st.st_size,
            st.st_mtime_ns,
            "fp1",
            {"DateTimeOriginal": "2020:01:01 00:00:00"},
        )
        cache.put(
            photo,
            st.st_size,
            st.st_mtime_ns,
            FileHashes(sha256="abc", perceptual=None),
            # A full pass that found no image, not a pass that skipped one.
            perceptual_computed=True,
        )

    with HashCache.beside(db) as cache:
        meta = cache.get_metadata(photo, st.st_size, st.st_mtime_ns, "fp1")
        hashes = cache.get(photo, st.st_size, st.st_mtime_ns, need_sha=True)
    assert meta == {"DateTimeOriginal": "2020:01:01 00:00:00"}
    assert hashes is not None
    assert hashes.sha256 == "abc"


def test_mutation_warm_hit_fails_if_cache_is_ignored(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If read_metadata stopped consulting the cache, the zero-call guard must fail."""
    photo = _photo(tmp_path / "a.jpg")
    db = tmp_path / "c.sqlite"
    st = photo.stat()
    with HashCache.beside(db) as cache:
        cache.put_metadata(
            photo,
            st.st_size,
            st.st_mtime_ns,
            tags_fingerprint(REQUESTED_TAGS, _NUMERIC_TAGS),
            {"Make": "Canon"},
        )

    calls = {"n": 0}

    def boom(*_a: object, **_k: object) -> Any:
        calls["n"] += 1
        raise RuntimeError

    monkeypatch.setattr(exif_mod.binaries, "run", boom)
    with HashCache.beside(db) as cache:
        out = read_metadata([photo], cache=cache)
    assert out[photo]["Make"] == "Canon"
    assert calls["n"] == 0
