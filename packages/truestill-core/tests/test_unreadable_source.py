"""An unreadable source FOLDER is named, and its contents admitted to be unknown ((aac)).

**The asymmetry this closes.** `verify` reports an unreadable copy as its own outcome
(`CopyStatus.UNREADABLE`, counted and named). Organize said nothing at all about a source
subtree it could not list: `rglob` swallows the permission error by design, so `scan_source`
returned as though the folder did not exist. Files that are really there were never seen, never
counted, and never mentioned - a §9 violation on the busiest path in the product.

**Three points, and only one of them is this.** Measured before building:

* *unreadable at copy time* - already correct: `execute` catches ``OSError`` and records
  `ActionStatus.FAILED` with the message, counted and named.
* *unreadable at hash time* - degraded but recovered: `_hash_one` returns ``(path, None, None)``,
  and `organizer.py`'s ``hashes.sha256 or sha256_file(...)`` re-hashes at upload, raises, and
  lands as FAILED. No silent success.
* *unreadable folder at scan time* - **nothing.** That is this file.

**A folder is not a file, and the report must not pretend otherwise.** An unreadable file is a
named loss - truestill knows which file. An unreadable folder is an **unknown quantity**: the
count of what is inside is exactly what could not be read. Saying "3 files could not be read"
about a folder truestill could not open would be inventing the number that is missing.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from PIL import Image
from truestill_core.organizer import scan_source

#: ⚠ **PER-TEST, NOT MODULE-WIDE, AND THE DIFFERENCE HID A DEFECT.** `(ais)`
#:
#: Three of the six tests here `chmod` a folder to `0o000`; the other three - the ordinary scan,
#: the partitioning walk and the ordering contract - need nothing from POSIX at all. As a
#: `pytestmark` this exempted all six from the Windows lane, and
#: `test_the_media_list_is_deterministically_ordered` sat there comparing
#: `str(p.relative_to(src))` against `"sub/a.jpg"` - **a live separator bug the one lane that
#: could see it was never allowed to run.** A skip written for one test's need is not free: it
#: is a hole the size of the file.
_NEEDS_POSIX_PERMISSIONS = pytest.mark.skipif(
    sys.platform == "win32" or os.geteuid() == 0,
    reason="needs POSIX permissions and a non-root user",
)


def _jpeg(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (32, 32), "red").save(path)


@_NEEDS_POSIX_PERMISSIONS
def test_an_unreadable_folder_is_named(tmp_path: Path) -> None:
    """The defect: this subtree used to vanish from the scan entirely."""
    src = tmp_path / "src"
    _jpeg(src / "keep.jpg")
    _jpeg(src / "locked" / "hidden.jpg")
    (src / "locked").chmod(0o000)
    try:
        scan = scan_source(src)
    finally:
        (src / "locked").chmod(0o755)

    assert [p.name for p in scan.unreadable_dirs] == ["locked"]


@_NEEDS_POSIX_PERMISSIONS
def test_the_readable_files_beside_it_are_still_found(tmp_path: Path) -> None:
    """One unreadable folder must not cost the rest of the run - the never-abort rule."""
    src = tmp_path / "src"
    _jpeg(src / "keep.jpg")
    _jpeg(src / "locked" / "hidden.jpg")
    (src / "locked").chmod(0o000)
    try:
        scan = scan_source(src)
    finally:
        (src / "locked").chmod(0o755)

    assert [p.name for p in scan.media] == ["keep.jpg"]


def test_an_ordinary_scan_reports_nothing_new(tmp_path: Path) -> None:
    """Cry-wolf half, and it matters more than usual: this is the busiest walk in the product.

    A spurious line on every ordinary run gets the whole feature switched off in someone's head,
    taking its real coverage with it.
    """
    src = tmp_path / "src"
    _jpeg(src / "a.jpg")
    _jpeg(src / "sub" / "b.jpg")

    scan = scan_source(src)

    assert scan.unreadable_dirs == []
    assert sorted(p.name for p in scan.media) == ["a.jpg", "b.jpg"]


@_NEEDS_POSIX_PERMISSIONS
def test_an_unreadable_file_is_not_reported_as_an_unreadable_folder(tmp_path: Path) -> None:
    """The distinction the report turns on. A file truestill cannot read is a *named loss* and is
    already handled downstream as FAILED; it must not be reported here as an unknown quantity."""
    src = tmp_path / "src"
    _jpeg(src / "locked.jpg")
    (src / "locked.jpg").chmod(0o000)
    try:
        scan = scan_source(src)
    finally:
        (src / "locked.jpg").chmod(0o644)

    assert scan.unreadable_dirs == []
    assert [p.name for p in scan.media] == ["locked.jpg"], "the file is still offered to the run"


def test_the_walk_still_partitions_everything_else_the_same(tmp_path: Path) -> None:
    """Regression: swapping rglob for Path.walk must not change what lands in each bucket."""
    src = tmp_path / "src"
    _jpeg(src / "photo.jpg")
    (src / "notes.txt").write_text("x", encoding="utf-8")
    (src / "thing.xyz").write_text("x", encoding="utf-8")
    (src / "photo.jpg_original").write_text("x", encoding="utf-8")
    _jpeg(src / ".hidden" / "skip.jpg")
    (src / ".dotfile.jpg").write_text("x", encoding="utf-8")

    scan = scan_source(src)

    assert [p.name for p in scan.media] == ["photo.jpg"]
    assert [p.name for p in scan.documents] == ["notes.txt"]
    assert [p.name for p in scan.unrecognized] == ["thing.xyz"]
    assert [p.name for p in scan.exiftool_backups] == ["photo.jpg_original"]


def test_the_media_list_is_deterministically_ordered(tmp_path: Path) -> None:
    """`rglob` was globally sorted; `Path.walk` yields per directory. Order is part of the
    contract - the organize report and every golden test read it."""
    src = tmp_path / "src"
    for name in ("c.jpg", "a.jpg", "b.jpg"):
        _jpeg(src / name)
    _jpeg(src / "sub" / "a.jpg")

    scan = scan_source(src)

    assert [p.relative_to(src).as_posix() for p in scan.media] == [
        "a.jpg",
        "b.jpg",
        "c.jpg",
        "sub/a.jpg",
    ]
