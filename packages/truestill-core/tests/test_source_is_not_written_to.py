"""Organizing a pure copy writes nothing at all to the source, not even its timestamps.

**What was there.** `_upload_copy` snapshotted the source's atime and mtime, and afterwards put
both back with `os.utime` whenever either had moved, "so a copy does not invalidate the
path+size+mtime hash-cache key".

**Why that was wrong in two directions, both measured.**

* Reading a file advances **atime** and never **mtime** (measured on ext4/relatime: atime moved,
  mtime did not). So the restore fired on essentially every file of every run - and atime is not
  in the cache key at all. The key is path + size + ``mtime_ns`` (`hash_cache`). Restoring atime
  could not protect the thing the comment named.
* If **mtime** genuinely differs, nothing truestill did caused it: `copy2` reads the source and
  writes the destination. It means the file changed underneath the run - and stamping the old
  mtime back would make a *stale* cache row look valid, so the next run would serve a hash for
  content that no longer matches. The restore was actively harmful in the only case where its
  condition could honestly be true.

**Why it matters more than one syscall.** The source is usually the user's camera card. FAT32
and exFAT have no journal, so every metadata write to it is an unjournalled directory-entry
update. Doing that once per file, per run, for no benefit is not a tidy no-op.
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

import pytest
from truestill_core.categorize import CategoryMatch, Confidence
from truestill_core.destinations import LocalDestination
from truestill_core.models import DateSource, Decision, FileHashes, Resolution
from truestill_core.organizer import execute

WHEN = datetime(2024, 6, 17, 9, 30)
CAT = CategoryMatch(label="Camera", reason="t", confidence=Confidence.MEDIUM, rule="device")
#: Three days back, so a relatime mount really does update atime on the read.
STALE = datetime(2020, 1, 2, 3, 4, 5).timestamp()


def _resolution(source: Path) -> Resolution:
    return Resolution(
        decision=Decision(
            source=source,
            category=CAT,
            captured_at=WHEN,
            date_source=DateSource.EXIF,
            date_tag="EXIF:DateTimeOriginal",
            relative=Path(f"Camera/2024/06/{source.name}"),
        ),
        hashes=FileHashes(sha256="0" * 64, perceptual=None),
        exact_duplicate=None,
        near_duplicate=None,
    )


def _aged_photo(directory: Path, name: str = "IMG_0001.jpg") -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_bytes(b"\xff\xd8" + b"x" * 500)
    os.utime(path, (STALE, STALE))
    return path


def test_organizing_leaves_the_source_timestamps_exactly_as_found(tmp_path: Path) -> None:
    """The mtime the hash cache keys on is untouched - by not being written, not by being
    written back."""
    source = _aged_photo(tmp_path / "src")
    before = source.stat()

    execute([_resolution(source)], LocalDestination(tmp_path / "dest"), apply=True)

    after = source.stat()
    assert after.st_mtime_ns == before.st_mtime_ns
    assert after.st_size == before.st_size


def test_the_source_is_never_utimed_during_a_pure_copy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Asserted on the *call*, not on the resulting mtime. Writing the same value back leaves a
    byte-identical stat and would pass the test above while still writing to the card - guard
    rule 4: assert the promise, not what happens to survive it.

    Patched on `os.utime` itself, which is the reference `organizer` calls through (it does a
    plain ``import os``), rather than on a name the module does not use - guard rule 3.
    """
    source = _aged_photo(tmp_path / "src")
    stamped: list[Path] = []
    real_utime = os.utime

    def watched(path: object, *args: object, **kwargs: object) -> None:
        stamped.append(Path(str(path)))
        real_utime(path, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(os, "utime", watched)

    execute([_resolution(source)], LocalDestination(tmp_path / "dest"), apply=True)

    assert source not in stamped, f"the source was written to: {stamped}"


def test_a_source_that_really_changed_keeps_its_new_mtime(tmp_path: Path) -> None:
    """The case the old restore got backwards.

    Nothing truestill does moves the source's mtime, so a difference means the file changed
    underneath the run. Stamping the old value back would make a stale cache row - keyed on
    path+size+mtime - look valid, and the next run would serve a hash for content that no longer
    matches. The new mtime must survive so the cache invalidates itself.
    """
    source = _aged_photo(tmp_path / "src")

    class _TouchingDestination(LocalDestination):
        """Stands in for anything that modifies the source mid-run: another process, a sync
        client, the user. The mechanism does not matter; the outcome under test does."""

        def upload(self, local: Path, relative_path: str) -> None:
            super().upload(local, relative_path)
            local.write_bytes(local.read_bytes() + b"changed")

    execute([_resolution(source)], _TouchingDestination(tmp_path / "dest"), apply=True)

    assert source.stat().st_mtime_ns != int(STALE * 1_000_000_000), (
        "an external modification was stamped back to its old mtime, hiding it from the cache"
    )


def test_the_destination_copy_still_gets_its_capture_date(tmp_path: Path) -> None:
    """The cry-wolf direction: only the *source* write went away. Stamping the destination is
    the whole point of `set_timestamps` and must be untouched."""
    source = _aged_photo(tmp_path / "src")
    destination = tmp_path / "dest"

    execute([_resolution(source)], LocalDestination(destination), apply=True)

    copy = destination / "Camera/2024/06/IMG_0001.jpg"
    assert copy.stat().st_mtime == WHEN.timestamp()
