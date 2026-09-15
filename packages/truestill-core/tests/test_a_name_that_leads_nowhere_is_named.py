"""A path that resolves to nothing lands in a bucket instead of vanishing. `(akw)`

⚠ **THREE FILES WERE IN NO BUCKET AT ALL.** `scan_source` calls `path.is_file()`, which FOLLOWS
a symlink, so a dangling link and a symlink loop both answer False and hit a bare ``continue``:
not media, not a document, not unrecognized, not hidden, not an unreadable folder.

Measured on a deliberately hostile corpus: **287 paths existed, 282 media + 4 unrecognized + 1
hidden = 287 were accounted for, and three were never mentioned anywhere.** The arithmetic was
internally consistent and the report was incomplete, which is the worse of the two failures -
a count that does not add up invites a second look, and one that does invites none.

**Named, never counted as media**: the bytes are not there to organize. This is the same rule
``unreadable_dirs`` and ``hidden_dirs`` already follow - report the place, invent no number for
what is behind it.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from truestill_core.organizer import BROKEN_LINK_LABEL, scan_source, skipped_extension_counts


def _corpus(root: Path) -> None:
    (root / "real.jpg").write_bytes(b"\xff\xd8\xffreal")
    (root / "dangling.jpg").symlink_to(root / "gone.jpg")
    (root / "loop_a").symlink_to(root / "loop_b")
    (root / "loop_b").symlink_to(root / "loop_a")
    (root / "works.jpg").symlink_to(root / "real.jpg")


def test_a_dangling_link_and_a_loop_are_both_named(tmp_path: Path) -> None:
    """The three that used to disappear. A loop is two links, and both are reported: each is a
    name a user can see in their own folder, so each is a name the report must account for."""
    _corpus(tmp_path)

    scan = scan_source(tmp_path)

    assert sorted(p.name for p in scan.broken_links) == ["dangling.jpg", "loop_a", "loop_b"]


_POSIX_ONLY = pytest.mark.skipif(
    sys.platform == "win32",
    reason="os.mkfifo does not exist on Windows; a named pipe has no equivalent here",
)


@_POSIX_ONLY
def test_something_that_is_not_a_link_is_not_called_a_broken_one(tmp_path: Path) -> None:
    """⚠ **THE LABEL MUST STAY TRUE OF WHAT IT NAMES.** A FIFO is not a regular file either, so
    it reaches the same branch - but it does not *lead nowhere*: it leads somewhere that is not a
    photograph. Reporting it under this row would be the wrong sentence about the right file,
    which is the class of defect this entry exists to remove rather than relocate.

    Found by mutation: widening the test to ``if True`` swept every non-file into the bucket and
    no assertion noticed, because the corpus above contains only symlinks.
    """
    os.mkfifo(tmp_path / "a_pipe")
    (tmp_path / "real.jpg").write_bytes(b"\xff\xd8\xffreal")

    scan = scan_source(tmp_path)

    assert [p.name for p in scan.broken_links] == []
    assert [p.name for p in scan.media] == ["real.jpg"]


def test_a_working_link_is_still_media_and_not_a_broken_one(tmp_path: Path) -> None:
    """⚠ **The cry-wolf half, and it is the one that matters**: `is_file()` follows a link, so a
    symlink pointing at a real photograph is a real photograph and must keep being organized.
    A guard that swept every symlink into the new bucket would 'fix' this by losing files."""
    _corpus(tmp_path)

    scan = scan_source(tmp_path)

    assert sorted(p.name for p in scan.media) == ["real.jpg", "works.jpg"]
    assert "works.jpg" not in {p.name for p in scan.broken_links}


def test_every_path_in_the_folder_is_accounted_for_somewhere(tmp_path: Path) -> None:
    """**The property the defect broke**, asserted as arithmetic rather than as a list: what the
    scan reports must add up to what is in the folder. This is what would have caught it."""
    _corpus(tmp_path)

    scan = scan_source(tmp_path)
    accounted = (
        len(scan.media)
        + len(scan.documents)
        + len(scan.unrecognized)
        + len(scan.hidden)
        + len(scan.markers)
        + len(scan.exiftool_backups)
        + len(scan.broken_links)
    )

    assert accounted == len(list(tmp_path.iterdir()))


def test_the_shared_census_carries_them_so_every_surface_shows_them(tmp_path: Path) -> None:
    """`skipped_extension_counts` is the one home all three surfaces render - `(aer)` is the
    record of a group that existed and which one renderer never showed. Counted by NAME, like
    `hidden`: an extension census of a broken link reports the extension of a file that is not
    there."""
    _corpus(tmp_path)

    groups = skipped_extension_counts(scan_source(tmp_path))

    assert groups[BROKEN_LINK_LABEL] == {"dangling.jpg": 1, "loop_a": 1, "loop_b": 1}


def test_an_ordinary_folder_grows_no_row_for_links_it_does_not_have(tmp_path: Path) -> None:
    """A group with nothing in it is absent, not zero - never-silent is about what happened."""
    (tmp_path / "only.jpg").write_bytes(b"\xff\xd8\xffx")

    groups = skipped_extension_counts(scan_source(tmp_path))

    assert groups[BROKEN_LINK_LABEL] == {}
