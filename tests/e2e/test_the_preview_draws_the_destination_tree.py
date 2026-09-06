"""The preview says what the library will LOOK LIKE, not only how many files it found.

**The question the screen could not answer.** "Check for duplicates" reported counts, a promise
sentence and a row of category chips - Camera, Saved, WhatsApp - and nothing that said where the
photographs would be afterwards. `destination_tree` carries that: how many files land in each
folder the run will create.

⚠ **The tree and the chips are DIFFERENT DATA and this file holds them apart.** `folders` is keyed
by category and `destination_tree` by destination folder; on a real 165-file run the first gave 3
groups and the second 18. The fixture below is built so a renderer that reached for the wrong one
fails here rather than looking plausible - the two disagree in count, in name and in nesting.
`packages/truestill-app/tests/test_the_destination_tree_is_keyed_by_folder.py` guards the payload
half; this guards the drawing.
"""

from __future__ import annotations

from typing import Any

from playwright.sync_api import Page, expect

TREE = "[data-testid='org-tree']"
GROUP = "[data-testid='org-tree-group']"

#: Keyed by DESTINATION FOLDER. Four top-level names, six leaves, and one - `Undated` - with no
#: second segment at all, which is the Undated tile reached without a special case.
DESTINATION_TREE: dict[str, int] = {
    "2010/2010-04/2010-04 - Everyday": 12,
    "2010/2010-11/2010-11 - Everyday": 3,
    "2014/2014-08/2014-08-17 - Sailing": 40,
    "2014/2014-08/2014-08 - Everyday": 7,
    "Saved/2012/2012-01": 5,
    "Undated": 2,
}

#: Keyed by CATEGORY. Deliberately unlike the tree: one name, one entry, a different total.
FOLDERS: dict[str, int] = {"Camera": 69}


def _preview(ui: Page, **overrides: Any) -> None:
    """Put the island in its `preview` state through the props seam.

    The same entry point `test_the_grid_is_the_result.py` uses. A real dedup pass cannot be made
    to produce the folder shape above on demand, and driving one would test the scanner.
    """
    summary: dict[str, Any] = {
        "files": 69,
        "photos": 69,
        "videos": 0,
        "audio": 0,
        "by_format": {},
        "new_unique": 69,
        "near_dup": 0,
        "exact_dup": 0,
        "exact_dup_matches": None,
        "near_dup_matches": None,
        "will_organize": 69,
        "undated": 2,
        "sentinel_rejected": 0,
        "future_rejected": 0,
        "suspect_default": 0,
        "inferred_local_shifts": [],
        "folders": FOLDERS,
        "destination_tree": DESTINATION_TREE,
        "mode": "copy",
    }
    summary.update(overrides)
    view = {
        "skippingUndated": False,
        "already": {"kind": "none"},
        "destinationLabel": "TruestillLibrary",
        "copiesAgain": False,
    }
    ui.evaluate(
        "([s, v]) => { window.organizeResult.set({ kind: 'preview', preview: s, view: v }); }",
        [summary, view],
    )
    expect(ui.locator("#org-result .card.result")).to_be_visible()


def test_the_tree_draws_one_tile_per_top_level_folder(ui: Page) -> None:
    """Four destination folders, four tiles, each carrying the total of everything beneath it."""
    _preview(ui)

    expect(ui.locator(TREE)).to_be_visible()
    expect(ui.locator(GROUP)).to_have_count(4)
    for name, total in [("2010", 15), ("2014", 47), ("Saved", 5), ("Undated", 2)]:
        tile = ui.locator(f"{GROUP}[data-folder='{name}']")
        expect(tile).to_have_count(1)
        expect(tile.locator(".tree-group-head .num")).to_have_text(str(total))


def test_the_months_are_listed_beneath_their_year(ui: Page) -> None:
    """The second path segment, summed. `2014-08` holds two leaf folders and reads as one month."""
    year = ui.locator(f"{GROUP}[data-folder='2014']")
    _preview(ui)

    expect(year.locator(".tree-child")).to_have_count(1)
    expect(year.locator(".tree-child[data-child='2014-08'] .num")).to_have_text("47")
    expect(ui.locator(f"{GROUP}[data-folder='2010'] .tree-child")).to_have_count(2)


def test_the_undated_tile_has_nothing_beneath_it(ui: Page) -> None:
    """A one-segment key is a folder with no children, not a folder with an empty child."""
    _preview(ui)

    undated = ui.locator(f"{GROUP}[data-folder='Undated']")
    expect(undated).to_be_visible()
    expect(undated.locator(".tree-children")).to_have_count(0)


def test_the_tree_is_not_the_category_chips(ui: Page) -> None:
    """The differential. Drawing `folders` here would give one tile called Camera.

    This is the mistake `_represent` actually made, one layer down, and it looked correct until
    someone printed the numbers.
    """
    _preview(ui)

    names = ui.locator(GROUP).evaluate_all("els => els.map(e => e.dataset.folder)")
    assert "Camera" not in names, f"the tree drew the CATEGORY chips: {names}"
    assert names == ["2010", "2014", "Saved", "Undated"], names
    # And the chips are still drawn, from their own field, so this is a separation rather than a
    # replacement.
    expect(ui.locator("#org-result .chips .chip")).to_have_count(1)


def test_the_heading_names_the_destination(ui: Page) -> None:
    """The heading needs the folder's OWN name - "the destination" is not an answer."""
    _preview(ui)

    expect(ui.locator("[data-testid='org-tree-heading']")).to_have_text(
        "TruestillLibrary after this run"
    )


def test_a_preview_with_no_destination_tree_draws_no_tree(ui: Page) -> None:
    """The cry-wolf half: an empty tree is silence, not an empty heading over nothing."""
    _preview(ui, destination_tree={})

    expect(ui.locator(TREE)).to_have_count(0)
    expect(ui.locator("#org-result .card.result")).to_be_visible()
