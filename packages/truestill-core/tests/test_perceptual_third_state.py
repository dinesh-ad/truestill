"""The cache can say "nobody looked" as well as "not an image".

**One ambiguity, two live defects.** `perceptual` was nullable and carried both meanings, and
`get` had no way to tell them apart, so any row written by a pass that did not hash the pixels
came back as a **hit** carrying `perceptual=None` - which every reader took as *not an image*.

* `attach_drive` wrote SHA-only rows. Closed by opening its cache read-only.
* `read_metadata` writes a row for a path nothing has hashed, and `_cmd_organize` closes that
  cache before `_run_pipeline` opens a fresh one - so the metadata-only rows became hits within
  a single command. **A guard cannot fix this one**: `read_metadata` genuinely does not know
  whether anybody hashed the file, so there is nothing for it to assert.

Measured on a real 2,239-row cache: **2,221 image rows with no perceptual hash**, and an
organize preview reporting `look-alikes: 0` as though it had looked.

The column removes the need for the invariant rather than restating it.
"""

from __future__ import annotations

from pathlib import Path

from truestill_core.hash_cache import HashCache
from truestill_core.models import FileHashes


def _cache(tmp_path: Path) -> HashCache:
    return HashCache(tmp_path / "hashes.cache.sqlite")


def test_a_metadata_only_row_misses_a_run_that_needs_the_perceptual_hash(tmp_path: Path) -> None:
    """THE DEFECT. Before the column this returned a hit and the file was never hashed."""
    target = tmp_path / "photo.jpg"
    target.write_bytes(b"\xff\xd8" + b"x" * 500)
    stat = target.stat()

    with _cache(tmp_path) as cache:
        cache.put_metadata(target, stat.st_size, stat.st_mtime_ns, "tags-v1", {"Make": "HTC"})

    with _cache(tmp_path) as cache:
        assert cache.get(target, stat.st_size, stat.st_mtime_ns, need_sha=False) is not None, (
            "a SHA-only reader should still take this row - it asks nothing about pixels"
        )
        assert (
            cache.get(target, stat.st_size, stat.st_mtime_ns, need_sha=False, need_perceptual=True)
            is None
        ), "a run that needs a perceptual hash took a row nobody perceptually hashed"


def test_the_metadata_itself_still_hits(tmp_path: Path) -> None:
    """The cry-wolf half. Metadata caching is ~74% of a cold preview and must be untouched."""
    target = tmp_path / "photo.jpg"
    target.write_bytes(b"\xff\xd8" + b"x" * 500)
    stat = target.stat()

    with _cache(tmp_path) as cache:
        cache.put_metadata(target, stat.st_size, stat.st_mtime_ns, "tags-v1", {"Make": "HTC"})
    with _cache(tmp_path) as cache:
        assert cache.get_metadata(target, stat.st_size, stat.st_mtime_ns, "tags-v1") == {
            "Make": "HTC"
        }


def test_a_computed_null_is_a_real_answer_and_still_hits(tmp_path: Path) -> None:
    """A video IS perceptually hashless, and re-deciding that every run is the cost to avoid."""
    target = tmp_path / "clip.mp4"
    target.write_bytes(b"\0" * 500)
    stat = target.stat()

    with _cache(tmp_path) as cache:
        cache.put(
            target,
            stat.st_size,
            stat.st_mtime_ns,
            FileHashes("a" * 64, None),
            perceptual_computed=True,
        )
    with _cache(tmp_path) as cache:
        hit = cache.get(target, stat.st_size, stat.st_mtime_ns, need_sha=True, need_perceptual=True)
    assert hit is not None, "a computed 'not an image' must be usable, or videos re-decode forever"
    assert hit.perceptual is None
    assert hit.perceptual_computed is True


def test_a_sha_only_pass_never_downgrades_a_row_that_already_knows(tmp_path: Path) -> None:
    """Attach writes SHA over a row a full run hashed; that answer must survive."""
    target = tmp_path / "photo.jpg"
    target.write_bytes(b"\xff\xd8" + b"y" * 500)
    stat = target.stat()

    with _cache(tmp_path) as cache:
        cache.put(
            target,
            stat.st_size,
            stat.st_mtime_ns,
            FileHashes(None, "phash"),
            perceptual_computed=True,
        )
        cache.put(
            target,
            stat.st_size,
            stat.st_mtime_ns,
            FileHashes("a" * 64, "phash"),
            perceptual_computed=False,
        )
    with _cache(tmp_path) as cache:
        hit = cache.get(target, stat.st_size, stat.st_mtime_ns, need_sha=True, need_perceptual=True)
    assert hit is not None, "a SHA-only write erased a perceptual answer the cache already had"
    assert hit.perceptual == "phash"


def test_a_changed_file_misses_whatever_was_recorded(tmp_path: Path) -> None:
    """Unchanged from before: size+mtime still govern, and the new column does not bypass them."""
    target = tmp_path / "photo.jpg"
    target.write_bytes(b"\xff\xd8" + b"z" * 500)
    stat = target.stat()
    with _cache(tmp_path) as cache:
        cache.put(
            target,
            stat.st_size,
            stat.st_mtime_ns,
            FileHashes("a" * 64, "p"),
            perceptual_computed=True,
        )
    with _cache(tmp_path) as cache:
        assert cache.get(target, stat.st_size + 1, stat.st_mtime_ns, need_sha=True) is None
