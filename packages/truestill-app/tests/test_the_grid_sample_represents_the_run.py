"""The 48 tiles represent the run, not its first afternoon.

⚠ **The defect this replaces, and the comment that defended it.** `organized_sample` was
`photos[:48]` under a note saying any other ordering "would be a judgement about which of a user's
photos matter". True - and equally true of first-seen, which is not a neutral choice but the
walk's own accident. A run spanning eight years showed one afternoon, because the first 48 files a
walk meets are 48 neighbours from one folder.

The rule is deliberately preference-free: one photo per destination folder first, then an even
stride across the rest. Nothing is ranked by date, size, shape or name; a folder is the run's own
grouping and a stride is the absence of a preference.

`GRID_SAMPLE_LIMIT` is untouched. This is about WHICH 48.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from truestill_app.service.organize import GRID_SAMPLE_LIMIT, _represent


def _photo(folder: str, index: int) -> MagicMock:
    """An `ActionResult` stand-in carrying only what the selection reads: its folder label."""
    r = MagicMock()
    # `relative` is the DESTINATION path the layout template built, so its parent is the folder
    # the file lands in - which is what the run has many of. `category.label` is not: on a real
    # 165-file run it gave three groups where the destination gave seven.
    r.resolution.decision.relative = Path(folder) / f"IMG_{index:04d}.jpg"
    r.resolution.decision.category.label = folder
    return r


def _run(folders: dict[str, int]) -> list[MagicMock]:
    """Photos in run order: every file of one folder, then the next - a walk's own shape."""
    out: list[MagicMock] = []
    for folder, count in folders.items():
        out.extend(_photo(folder, i) for i in range(count))
    return out


def _folders(chosen: list[MagicMock]) -> list[str]:
    return [str(c.resolution.decision.relative.parent) for c in chosen]


def test_a_run_that_fits_is_returned_whole_and_in_order() -> None:
    """Under the limit nothing is selected at all - the cheap path stays cheap."""
    photos = _run({"2019": 10, "2020": 12})

    assert _represent(photos, GRID_SAMPLE_LIMIT) == photos


def test_every_destination_folder_reaches_the_grid() -> None:
    """The headline property. Eight years, 400 photos, and all eight are on screen."""
    photos = _run({str(year): 50 for year in range(2012, 2020)})

    chosen = _represent(photos, GRID_SAMPLE_LIMIT)

    assert len(chosen) == GRID_SAMPLE_LIMIT
    assert sorted(set(_folders(chosen))) == [str(y) for y in range(2012, 2020)]


def test_the_old_rule_would_have_shown_one_folder() -> None:
    """The differential, so the fix is measured rather than asserted.

    Without this the test above passes against any selection that happens to spread - including
    one that spread by accident. This states what the previous rule produced on the same input.
    """
    photos = _run({str(year): 50 for year in range(2012, 2020)})

    old = photos[:GRID_SAMPLE_LIMIT]

    assert set(_folders(old)) == {"2012"}, (
        "the first-48 rule no longer clusters, so this test has no subject"
    )
    assert len(set(_folders(_represent(photos, GRID_SAMPLE_LIMIT)))) == 8


def test_more_folders_than_tiles_takes_the_first_ones_met() -> None:
    """With 60 folders and 48 tiles the grid cannot show them all, and says so by taking them in
    run order rather than choosing between them."""
    photos = _run({f"f{i:02d}": 3 for i in range(60)})

    chosen = _represent(photos, GRID_SAMPLE_LIMIT)

    assert len(chosen) == GRID_SAMPLE_LIMIT
    assert _folders(chosen) == [f"f{i:02d}" for i in range(GRID_SAMPLE_LIMIT)]


def test_the_remainder_is_spread_rather_than_clustered() -> None:
    """Two folders, 300 photos: the filler must not all come from the first half.

    The stride is the half of the rule that stops the grid being folder one plus 46 of its
    neighbours, which is the original defect wearing a different hat.
    """
    photos = _run({"A": 150, "B": 150})

    chosen = _represent(photos, GRID_SAMPLE_LIMIT)
    positions = [photos.index(c) for c in chosen]

    assert len(chosen) == GRID_SAMPLE_LIMIT
    assert max(positions) > 250, f"nothing from the end of the run was taken: {positions[-5:]}"
    assert len([p for p in positions if p >= 150]) > 15, "the second folder is barely represented"


def test_the_output_stays_in_run_order() -> None:
    """The selection chooses; it does not reorder. A shuffled grid would read as a gallery."""
    photos = _run({"A": 40, "B": 40, "C": 40})

    chosen = _represent(photos, GRID_SAMPLE_LIMIT)
    positions = [photos.index(c) for c in chosen]

    assert positions == sorted(positions), "the grid was reordered, not just sampled"


def test_no_photo_is_drawn_twice() -> None:
    """The two passes could collide on a folder's first photo; they must not double-count it."""
    photos = _run({"A": 5, "B": 100})

    chosen = _represent(photos, GRID_SAMPLE_LIMIT)

    assert len(chosen) == len({id(c) for c in chosen}) == GRID_SAMPLE_LIMIT
