"""Organizing a folder that contains folders already organized.

The real shape: `A` contains `B`, `C` and `D`; `D` contains `E`. The user organizes `E`, then
`B`, then `A` - which contains everything they already did. That path had no test at all.

Three things are asserted separately, because they can disagree and the third is the one that
was missing: what lands ON DISK, what the CATALOG holds, and what the run SAYS.

Fixtures rather than the working area, so this passes on any machine. Photos are noise rather
than solid colour: a flat image dHashes to all zeros and every fixture becomes a near-duplicate
of every other, which would swallow the exact-duplicate counts this file exists to check.
"""

from __future__ import annotations

import random
import shutil
import threading
from pathlib import Path
from typing import Any

import pytest
from PIL import Image
from truestill_app.service import organize_preview, organize_run
from truestill_core.catalog import Catalog
from truestill_core.duplicate_explain import origin_phrase
from truestill_core.models import DuplicateOrigin

pytestmark = pytest.mark.skipif(shutil.which("exiftool") is None, reason="exiftool not installed")


def _jpeg(path: Path, seed: int) -> None:
    rng = random.Random(seed)
    image = Image.new("RGB", (64, 64))
    image.putdata(
        [(rng.randrange(256), rng.randrange(256), rng.randrange(256)) for _ in range(4096)]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, "JPEG", quality=95)


def _tree(root: Path) -> dict[str, list[Path]]:
    """A/ with B, C and D; D/ holds E. Every photo distinct."""
    made: dict[str, list[Path]] = {}
    layout = {"B": (10, 2), "C": (20, 2), "D": (30, 1), "D/E": (40, 3)}
    for rel, (seed, count) in layout.items():
        paths = []
        for i in range(count):
            p = root / "A" / rel / f"IMG_{seed + i:04d}.jpg"
            _jpeg(p, seed + i)
            paths.append(p)
        made[rel] = paths
    return made


def _run(source: Path, destination: Path, db: Path, *, mode: str = "copy") -> Any:
    target = organize_run(source, destination, db, mode=mode)
    return target(lambda _p: None, threading.Event())


def _files_under(root: Path) -> set[str]:
    """Source-relative paths in POSIX form, never `str(Path)` (ENGINEERING_STANDARD 4).

    `str(Path)` renders `D\\E\\IMG_0040.jpg` on Windows, so the separator reached the `"D/E"`
    comparison below and the lane failed against correct behaviour - the three originals really
    were still there. The comparison was wrong, not the product.
    """
    return {p.relative_to(root).as_posix() for p in root.rglob("*.jpg")}


# --------------------------------------------------------------------------- copy mode


def test_copy_mode_organizes_each_photo_once_across_overlapping_runs(tmp_path: Path) -> None:
    """E, then B, then A. A contains both, so the third run must add only C and D."""
    src, dest, db = tmp_path / "src", tmp_path / "dest", tmp_path / "c.sqlite"
    made = _tree(src)

    _run(src / "A" / "D" / "E", dest, db)
    _run(src / "A" / "B", dest, db)
    third = _run(src / "A", dest, db)

    # ON DISK: eight source photos, eight organized copies. Nothing is copied twice.
    assert len(_files_under(dest)) == 8, sorted(_files_under(dest))

    # WHAT IT SAYS: the third run organized only what the first two had not.
    assert third["organized"] == 3, third
    assert third["duplicates"] == 5, third

    # IN THE CATALOG: one row per file, keyed on content.
    with Catalog(db) as catalog:
        assert catalog.count() == 8
    assert len(made["D/E"]) + len(made["B"]) == 5


def test_the_catalog_holds_one_row_per_file_not_one_per_source_path(tmp_path: Path) -> None:
    """`files.sha256` is UNIQUE and the insert is `ON CONFLICT(sha256) DO UPDATE`.

    A second reach at the same bytes must not create a second row, or custody counts, verify
    and status would each count one photo twice.
    """
    src, dest, db = tmp_path / "src", tmp_path / "dest", tmp_path / "c.sqlite"
    _tree(src)
    _run(src / "A" / "D" / "E", dest, db)
    _run(src / "A", dest, db)

    with Catalog(db) as catalog:
        rows = catalog.seed_rows()
        shas = [sha for _path, sha, _p in rows]
    assert len(shas) == len(set(shas)), "the same content is recorded twice"
    assert len(shas) == 8


def test_a_skipped_duplicate_does_not_repoint_the_source_path(tmp_path: Path) -> None:
    """`record_uploaded` runs only after a successful write, and a duplicate never writes.

    So the recorded source stays where the run that actually organized it found the file.
    """
    src, dest, db = tmp_path / "src", tmp_path / "dest", tmp_path / "c.sqlite"
    _tree(src)
    _run(src / "A" / "D" / "E", dest, db)
    with Catalog(db) as catalog:
        before = {sha: path for path, sha, _p in catalog.seed_rows()}

    _run(src / "A", dest, db)
    with Catalog(db) as catalog:
        after = {sha: path for path, sha, _p in catalog.seed_rows()}

    for sha, path in before.items():
        assert after[sha] == path, f"{sha[:8]} was repointed from {path} to {after[sha]}"


# --------------------------------------------------------------------------- the preview


def test_the_preview_calls_the_overlap_already_in_your_library(tmp_path: Path) -> None:
    """The origin split must land these as CATALOG, not RUN.

    "Earlier in this batch" would be a plain falsehood about a file a previous run organized,
    and it is the difference between "you already did this" and "you selected it twice".
    """
    src, dest, db = tmp_path / "src", tmp_path / "dest", tmp_path / "c.sqlite"
    _tree(src)
    _run(src / "A" / "D" / "E", dest, db)
    _run(src / "A" / "B", dest, db)

    preview = organize_preview(src / "A", dest, db)
    matches = preview["exact_dup_matches"]
    assert matches["total"] == 5, preview
    assert matches["already_in_library"] == 5, matches
    assert matches["within_this_batch"] == 0, matches
    # The payload carries the PHRASE a user reads, not the enum - `explain_duplicate` renders
    # it through `origin_phrase`. Asserting the words is what pins the sentence on screen.
    phrase = origin_phrase(DuplicateOrigin.CATALOG)
    assert phrase == "already in your library"
    assert all(s["origin"] == phrase for s in matches["shown"]), matches["shown"]


def test_the_preview_does_not_count_the_overlap_as_new(tmp_path: Path) -> None:
    """`new_unique` is what the run will write. Counting five known files there would promise
    work that is not going to happen.

    **`new_unique == 3` is true of THIS material, not in general.** These fixtures are noise, so
    no two look alike. Run the same sequence on eight real photos from one event and it reads
    `new_unique 2, near_dup 1` - still three organized, because a near-duplicate is kept and
    organized too, and still summing to eight. Measured on 2026-08-06; the wording that makes
    that pair misleading on screen is `BACKLOG.md` **(abl)**. What this test pins is that the
    five known files are not among them.
    """
    src, dest, db = tmp_path / "src", tmp_path / "dest", tmp_path / "c.sqlite"
    _tree(src)
    _run(src / "A" / "D" / "E", dest, db)
    _run(src / "A" / "B", dest, db)

    preview = organize_preview(src / "A", dest, db)
    assert preview["files"] == 8
    assert preview["exact_dup"] == 5, preview
    # The claim that survives a change of material: whatever the new/look-alike split, none of
    # the five is counted as work the run will do.
    assert preview["new_unique"] + preview["near_dup"] == 3, preview
    assert preview["new_unique"] == 3, preview


# --------------------------------------------------------------------------- move mode


def test_move_mode_leaves_the_already_organized_originals_where_they_are(tmp_path: Path) -> None:
    """THE BEHAVIOUR THIS COMMIT EXISTS FOR.

    The duplicate check runs BEFORE the move, so a file already in the library is skipped and
    its original is never deleted. That is correct - deleting originals for files this run did
    not move would be far worse - and the user is not told.
    """
    src, dest, db = tmp_path / "src", tmp_path / "dest", tmp_path / "c.sqlite"
    _tree(src)
    _run(src / "A" / "D" / "E", dest, db)  # copy first, so the originals still exist

    before = _files_under(src / "A")
    result = _run(src / "A", dest, db, mode="move")
    after = _files_under(src / "A")

    assert result["duplicates"] == 3, result
    # The three E photos are still sitting in the source the user asked to empty.
    assert len(after) == 3, sorted(after)
    assert all("D/E" in p for p in after), sorted(after)
    assert before - after, "nothing moved at all - the fixture is not exercising move mode"


# ------------------------------------------------------------------ two destinations


def test_the_same_photo_copied_to_x_is_not_moved_to_y(tmp_path: Path) -> None:
    """Two runs, two intentions, one photo: copy into X, then move A into Y.

    The index is seeded from the whole catalog rather than from what is at this destination, so
    Y never receives the file and the original stays in the source.
    """
    src = tmp_path / "src"
    x, y, db = tmp_path / "X", tmp_path / "Y", tmp_path / "c.sqlite"
    _tree(src)

    _run(src / "A" / "D" / "E", x, db)
    result = _run(src / "A", y, db, mode="move")

    assert len(_files_under(x)) == 3, sorted(_files_under(x))
    # Y gets only what X never had.
    assert len(_files_under(y)) == 5, sorted(_files_under(y))
    assert result["duplicates"] == 3, result
    # And the originals of the three are still in the source.
    assert len(_files_under(src / "A" / "D" / "E")) == 3


# ------------------------------------------------- the leftover-empty-folder offer


def test_the_move_result_names_the_folder_the_leftovers_are_in(tmp_path: Path) -> None:
    """The other half of the offer above: what is still there, not just what is now empty.

    The engine has always known this - a DUPLICATE result carries the source path it declined
    to move - and the payload dropped it, so the screen could only ever have said nothing.
    """
    src, dest, db = tmp_path / "src", tmp_path / "dest", tmp_path / "c.sqlite"
    _tree(src)
    _run(src / "A" / "D" / "E", dest, db)
    result = _run(src / "A", dest, db, mode="move")

    left = result["left_in_source"]
    assert left["total"] == 3, left
    assert left["already_in_library"] == 3, left
    assert [(f["folder"], f["files"]) for f in left["folders"]] == [("D/E", 3)]


def test_the_leftovers_and_the_cleanup_offer_agree(tmp_path: Path) -> None:
    """Two halves of one answer, and they must not contradict each other on screen.

    A folder that still holds files is offered for removal by neither.
    """
    src, dest, db = tmp_path / "src", tmp_path / "dest", tmp_path / "c.sqlite"
    _tree(src)
    _run(src / "A" / "D" / "E", dest, db)
    result = _run(src / "A", dest, db, mode="move")

    occupied = {f["folder"] for f in result["left_in_source"]["folders"]}
    offered = set(result.get("leftover_empty_folders", {}).get("folders", []))
    assert not (occupied & offered), f"a folder is both empty and occupied: {occupied & offered}"


def test_copy_mode_says_nothing_about_files_it_never_intended_to_take(tmp_path: Path) -> None:
    """CRY-WOLF HALF, and the answer to "does copy mode have the same silence".

    It does not. A copy leaves every original where it is - that is what the mode is called -
    so there is nothing a user did not already ask for, and a note after every copy run would
    be noise rather than news.
    """
    src, dest, db = tmp_path / "src", tmp_path / "dest", tmp_path / "c.sqlite"
    _tree(src)
    _run(src / "A" / "D" / "E", dest, db)
    result = _run(src / "A", dest, db)

    assert result["duplicates"] == 3, result
    assert "left_in_source" not in result, result["left_in_source"]


def test_a_move_that_left_nothing_behind_says_nothing(tmp_path: Path) -> None:
    """The second cry-wolf half: a clean move must not gain a note about leftovers."""
    src, dest, db = tmp_path / "src", tmp_path / "dest", tmp_path / "c.sqlite"
    _tree(src)
    result = _run(src / "A", dest, db, mode="move")

    assert result["duplicates"] == 0, result
    assert "left_in_source" not in result, result["left_in_source"]


def test_the_cleanup_offer_never_names_a_folder_that_still_holds_files(tmp_path: Path) -> None:
    """CHECKED because it would be a second lie on top of the first.

    After a move the run offers to remove folders it emptied. If it offered `D/E` - which still
    holds the three skipped originals - it would be telling the user the folder is empty while
    their photos sit in it. `plan_cleanup` classifies each folder by inspecting it and drops
    anything `OCCUPIED`, so the offer is honest; this pins that rather than trusting it.
    """
    src, dest, db = tmp_path / "src", tmp_path / "dest", tmp_path / "c.sqlite"
    _tree(src)
    _run(src / "A" / "D" / "E", dest, db)
    result = _run(src / "A", dest, db, mode="move")

    leftovers = result.get("leftover_empty_folders")
    if leftovers is None:
        pytest.skip("no cleanup offer was made for this run shape")

    named = set(leftovers["folders"])
    assert "D/E" not in named, f"offered to remove a folder that still holds files: {named}"
    assert "D" not in named, f"offered to remove D, whose child E still holds files: {named}"
    for folder in named:
        assert not list((src / "A" / folder).rglob("*.jpg")), (
            f"{folder} was offered as empty but still contains photos"
        )
