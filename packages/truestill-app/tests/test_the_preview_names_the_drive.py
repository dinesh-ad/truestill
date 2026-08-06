"""The preview says WHICH library the matched files are already in.

Until now it could not. `matched_path` is `files.source_path` - where content was first read
from, never repointed - so every path a preview showed for a duplicate named the user's old
folder. Any surface offering to act on "your library" was therefore guessing, and Stage 1's
two-destination case makes the guess wrong: copy into X, later preview against Y, and every
match lives on X while the box on screen says Y.

Reach is carried rather than resolved away, because `DriveReach` is three-valued and both folds
lie: a drive that is not plugged in is not a drive that is gone.
"""

from __future__ import annotations

import random
import shutil
import threading
from pathlib import Path
from typing import Any

import pytest
from PIL import Image
from truestill_app.service import backup_run, organize_preview, organize_run
from truestill_core.catalog import Catalog

pytestmark = pytest.mark.skipif(shutil.which("exiftool") is None, reason="exiftool not installed")


def _jpeg(path: Path, seed: int) -> None:
    rng = random.Random(seed)
    image = Image.new("RGB", (64, 64))
    image.putdata(
        [(rng.randrange(256), rng.randrange(256), rng.randrange(256)) for _ in range(4096)]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, "JPEG", quality=95)


def _source(root: Path, seeds: range) -> Path:
    for i in seeds:
        _jpeg(root / f"IMG_{i:04d}.jpg", i)
    return root


def _run(source: Path, destination: Path, db: Path, *, mode: str = "copy") -> Any:
    return organize_run(source, destination, db, mode=mode)(lambda _p: None, threading.Event())


def test_the_preview_names_the_drive_the_matches_are_on(tmp_path: Path) -> None:
    src, dest, db = tmp_path / "src", tmp_path / "MyLibrary", tmp_path / "c.sqlite"
    _source(src, range(4))
    _run(src, dest, db)

    preview = organize_preview(src, dest, db)
    where = preview["matched_drives"]

    assert where["total"] == 4, where
    assert [(d["label"], d["files"]) for d in where["drives"]] == [("MyLibrary", 4)]
    assert where["unplaced"] == 0, where


def test_the_named_drive_is_where_the_files_are_not_where_the_box_says(tmp_path: Path) -> None:
    """THE CASE THIS COMMIT EXISTS FOR - Stage 1's two destinations.

    Copied into X, then previewed against Y. Y holds nothing; the honest answer is X, and a
    surface reading the destination field would have said Y.
    """
    src, x, y, db = tmp_path / "src", tmp_path / "X", tmp_path / "Y", tmp_path / "c.sqlite"
    _source(src, range(4))
    _run(src, x, db)

    preview = organize_preview(src, y, db)
    labels = [d["label"] for d in preview["matched_drives"]["drives"]]

    assert labels == ["X"], f"the preview named {labels}, not the drive the files are on"


def test_matches_spread_across_two_drives_name_both(tmp_path: Path) -> None:
    """Never pick the first and call it the answer: both are true and they differ.

    A BACKUP is how content genuinely reaches a second drive - organizing the same folder into
    another destination does not, because the second run skips it as a duplicate, which is what
    `test_overlapping_organize_runs.py` pins. So the fixture backs X up to Y.
    """
    src, x, y, db = tmp_path / "src", tmp_path / "X", tmp_path / "Y", tmp_path / "c.sqlite"
    _source(src, range(4))
    _run(src, x, db)
    y.mkdir()
    backup_run(x, y, db)(lambda _p: None, threading.Event())

    preview = organize_preview(src, tmp_path / "Z", db)
    where = preview["matched_drives"]

    assert {d["label"] for d in where["drives"]} == {"X", "Y"}, where
    assert [d["files"] for d in where["drives"]] == [4, 4], where
    assert where["total"] == 4, "content on two drives was counted twice"


def test_a_connected_drive_carries_its_path_and_an_absent_one_does_not(tmp_path: Path) -> None:
    """`reach` is three-valued and stays that way. A path is offered only when it is real."""
    src, dest, db = tmp_path / "src", tmp_path / "MyLibrary", tmp_path / "c.sqlite"
    _source(src, range(3))
    _run(src, dest, db)

    connected = organize_preview(src, dest, db)["matched_drives"]["drives"][0]
    assert connected["reach"] == "connected"
    assert connected["path"] == str(dest)

    # Unplug it: the folder and its marker are gone, the catalog rows are not.
    shutil.rmtree(dest)
    offline = organize_preview(src, tmp_path / "elsewhere", db)["matched_drives"]["drives"][0]
    assert offline["reach"] == "offline", offline
    assert offline["path"] is None, "an offline drive was handed a path to act on"
    assert offline["label"] == "MyLibrary", "the drive stopped being named when it was unplugged"


def test_a_batch_twin_is_not_looked_up_at_all(tmp_path: Path) -> None:
    """Only catalog matches have a drive. A twin found earlier in this same batch is not in the
    library yet, and counting it would attribute a file to a drive that does not hold it."""
    src, dest, db = tmp_path / "src", tmp_path / "MyLibrary", tmp_path / "c.sqlite"
    _source(src, range(2))
    shutil.copy2(src / "IMG_0000.jpg", src / "copy-of-0000.jpg")

    preview = organize_preview(src, dest, db)

    assert preview["exact_dup_matches"]["within_this_batch"] == 1, preview["exact_dup_matches"]
    assert preview["matched_drives"]["total"] == 0, preview["matched_drives"]
    assert preview["matched_drives"]["drives"] == []


def test_a_preview_with_no_matches_carries_no_drives(tmp_path: Path) -> None:
    """CRY-WOLF HALF. Nothing matched, so there is no library to name."""
    src, dest, db = tmp_path / "src", tmp_path / "MyLibrary", tmp_path / "c.sqlite"
    _source(src, range(3))

    where = organize_preview(src, dest, db)["matched_drives"]

    assert where["total"] == 0
    assert where["drives"] == []
    assert where["unplaced"] == 0


def test_a_match_with_no_copy_row_is_counted_as_unplaced_rather_than_dropped(
    tmp_path: Path,
) -> None:
    """The orphan state `test_organize_registers_the_destination.py` exists for: a `files` row
    with no `file_copies` row. It is a real match with no drive, and silence about it would make
    the parts stop summing to the whole."""
    src, dest, db = tmp_path / "src", tmp_path / "MyLibrary", tmp_path / "c.sqlite"
    _source(src, range(3))
    _run(src, dest, db)
    with Catalog(db) as catalog:
        # Reaching past the public surface on purpose: there is no method that produces this
        # state, because nothing is supposed to produce it. The orphan is a defect a CLI
        # organize used to leave, and the payload has to be honest about meeting one.
        catalog._conn.execute("DELETE FROM file_copies")
        catalog._conn.commit()

    where = organize_preview(src, dest, db)["matched_drives"]

    assert where["total"] == 3, where
    assert where["unplaced"] == 3, where
    assert where["drives"] == [], where
    assert where["unplaced"] + sum(d["files"] for d in where["drives"]) == where["total"]
