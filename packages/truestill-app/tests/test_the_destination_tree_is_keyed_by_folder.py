"""The preview's destination tree is keyed by the folder a file lands in, never by its category.

⚠ **This class of mistake has already been made once here, and a test did not catch it - running
the product did.** `_represent`, the grid's sampler, was first written against
`decision.category.label` - Camera, Saved, WhatsApp - where it needed `decision.relative.parent`,
the folder the layout template builds. On a real 165-file run the category gave **3** groups and
the folder gave **18**, and the sampler looked right in every unit test until the numbers were
printed.

`destination_tree` is the same data reached by the same wrong turning, and the two are counted
four lines apart in `_summarize` off the same `Decision`. So the disagreement is built into the
fixture: every file below is one category and they land in four folders. A fixture where the two
agree cannot tell them apart, which is how the sampler's version shipped.
"""

from __future__ import annotations

from pathlib import Path

from truestill_app.service.organize import _summarize
from truestill_core.categorize import CategoryMatch, Confidence
from truestill_core.models import (
    DateSource,
    Decision,
    DuplicateKind,
    DuplicateMatch,
    FileHashes,
    Resolution,
)


def _resolution(category: str, relative: str, *, exact: bool = False) -> Resolution:
    name = Path(relative).name
    return Resolution(
        decision=Decision(
            source=Path("/src") / name,
            category=CategoryMatch(
                label=category, reason="t", confidence=Confidence.HIGH, rule="device"
            ),
            captured_at=None,
            date_source=DateSource.NONE,
            date_tag=None,
            relative=Path(relative),
        ),
        hashes=FileHashes(sha256=f"{abs(hash(relative)):064x}"[:64], perceptual=None),
        exact_duplicate=(
            DuplicateMatch(kind=DuplicateKind.EXACT, matched_path="/lib/twin.jpg", origin="run")
            if exact
            else None
        ),
        near_duplicate=None,
    )


#: One category, four destination folders. Keyed by category this run has ONE entry.
RUN = [
    _resolution("Camera", "2010/2010-04/2010-04 - Everyday/a.jpg"),
    _resolution("Camera", "2010/2010-04/2010-04 - Everyday/b.jpg"),
    _resolution("Camera", "2014/2014-08/2014-08-17 - Everyday/c.jpg"),
    _resolution("Camera", "Saved/2012/2012-01/d.jpg"),
    _resolution("Camera", "Undated/e.jpg"),
]


def _tree(resolutions: list[Resolution]) -> dict[str, int]:
    return dict(_summarize(resolutions)["destination_tree"])


def test_the_tree_is_keyed_by_destination_folder_not_by_category() -> None:
    """The headline. Five files of one category landing in four folders give four keys."""
    assert _tree(RUN) == {
        "2010/2010-04/2010-04 - Everyday": 2,
        "2014/2014-08/2014-08-17 - Everyday": 1,
        "Saved/2012/2012-01": 1,
        "Undated": 1,
    }


def test_keying_by_category_would_have_collapsed_this_run_to_one_entry() -> None:
    """The differential, so the guard is measured rather than asserted.

    Without it the test above passes against any grouping that happens to yield four keys. This
    states what the wrong key gives on the same input - and `folders`, which really is keyed by
    category, is right there in the payload to say it.
    """
    summary = _summarize(RUN)

    assert summary["folders"] == {"Camera": 5}, "the fixture no longer separates the two keys"
    assert len(summary["destination_tree"]) == 4, "the tree collapsed onto the category"


def test_the_tree_is_sorted_by_path() -> None:
    """A tree is read in order. `most_common`, which `folders` uses, would put 2014 above 2010."""
    tree = _tree(RUN)

    assert list(tree) == sorted(tree), f"the tree is not in path order: {list(tree)}"


def test_the_tree_counts_only_what_the_run_will_organize() -> None:
    """It is built from the organized bucket, so it cannot promise a folder for a skipped file."""
    duplicate = _resolution("Camera", "2011/2011-11/2011-11 - Everyday/dup.jpg", exact=True)

    tree = _tree([*RUN, duplicate])

    assert "2011/2011-11/2011-11 - Everyday" not in tree, (
        f"a duplicate that will not be copied claimed a destination folder: {tree}"
    )


def test_a_run_with_nothing_to_organize_has_an_empty_tree() -> None:
    """The cry-wolf half: an empty tree is a real answer, and must not be a missing key."""
    assert _tree([]) == {}
