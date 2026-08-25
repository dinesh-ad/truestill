"""The Analyze facts, and the two things about them that are easy to get wrong.

These were computed only for a **finished run**, inside the app's `_completion`, so a preview
could not report them at all. Moving them to core is the "one home" rule: the CLI preview and
the app run now answer from the same code, and `test_insights_match_the_run_summary` asserts
the move did not quietly change an answer.

The two traps:

* **Near-duplicate bytes are not savings.** Truestill *keeps* near-duplicates by design, so
  counting their bytes as reclaimable would be the first dishonest number in this product. Only
  exact duplicates are reclaimable, and the two are separate fields with separate names.
* **Undated files must not vanish from a year histogram.** A file with no capture date belongs
  to no year, and silently dropping it makes the histogram disagree with the file count.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
from truestill_core.categorize import CategoryMatch, Confidence
from truestill_core.insights import (
    capture_span,
    capture_years,
    duplicate_bytes,
    largest_files,
)
from truestill_core.models import (
    DateSource,
    Decision,
    DuplicateKind,
    DuplicateMatch,
    FileHashes,
    Resolution,
    RuleName,
)


def _resolution(
    name: str,
    *,
    when: datetime | None = None,
    exact: bool = False,
    near: bool = False,
) -> Resolution:
    match = DuplicateMatch(
        kind=DuplicateKind.EXACT if exact else DuplicateKind.PERCEPTUAL,
        matched_path=f"/library/{name}",
        origin="catalog",
        distance=None if exact else 3,
    )
    decision = Decision(
        source=Path(f"/src/{name}"),
        category=CategoryMatch(
            label="Camera", reason="t", confidence=Confidence.MEDIUM, rule=RuleName.DEVICE
        ),
        captured_at=when,
        date_source=DateSource.EXIF if when else DateSource.NONE,
        date_tag=None,
        relative=Path(f"Camera/{name}"),
    )
    return Resolution(
        decision=decision,
        hashes=FileHashes(sha256=f"sha-{name}", perceptual=None),
        exact_duplicate=match if exact else None,
        near_duplicate=match if near else None,
    )


# --- duplicate bytes: exact are reclaimable, near-duplicates are not ------------------------


def test_only_exact_duplicates_count_as_reclaimable() -> None:
    """The ruling, pinned on the numbers AND on which field they land in.

    A near-duplicate is kept, so its bytes are never freed by organizing. Reporting them as
    savings would promise space that no operation will return.
    """
    resolutions = [
        _resolution("a.jpg", exact=True),
        _resolution("b.jpg", exact=True),
        _resolution("c.jpg", near=True),
        _resolution("d.jpg"),
    ]
    sizes = {Path("/src/a.jpg"): 100, Path("/src/b.jpg"): 200, Path("/src/c.jpg"): 400}

    counted = duplicate_bytes(resolutions, sizes)

    assert counted.exact_bytes == 300
    assert counted.exact_files == 2
    assert counted.near_bytes == 400
    assert counted.near_files == 1
    assert counted.reclaimable_bytes == 300, "reclaimable must exclude near-duplicates"


def test_a_library_of_only_near_duplicates_reclaims_nothing() -> None:
    """Cry-wolf: the field must read zero rather than borrowing the near-dup total."""
    counted = duplicate_bytes([_resolution("c.jpg", near=True)], {Path("/src/c.jpg"): 999})
    assert counted.reclaimable_bytes == 0
    assert counted.near_bytes == 999


def test_a_file_with_no_recorded_size_contributes_nothing_rather_than_raising() -> None:
    """A source that vanished between the scan and the sizing is a real, ordinary case."""
    counted = duplicate_bytes([_resolution("gone.jpg", exact=True)], {})
    assert counted.exact_bytes == 0
    assert counted.exact_files == 1, "the file is still counted; only its bytes are unknown"


# --- the capture span ------------------------------------------------------------------------


def test_the_span_is_the_oldest_and_newest_dated_file() -> None:
    resolutions = [
        _resolution("a.jpg", when=datetime(2011, 3, 2, 9, 0)),
        _resolution("b.jpg", when=datetime(2019, 7, 14, 18, 30)),
        _resolution("c.jpg", when=datetime(2015, 1, 1)),
    ]
    span = capture_span(resolutions)
    assert span is not None
    assert span.oldest == datetime(2011, 3, 2, 9, 0)
    assert span.newest == datetime(2019, 7, 14, 18, 30)


def test_an_undated_library_has_no_span_rather_than_a_placeholder_year() -> None:
    """`None`, never a made-up range. Inventing one is the "computed for effect" defect."""
    assert capture_span([_resolution("a.jpg"), _resolution("b.jpg")]) is None


# --- the year histogram -----------------------------------------------------------------------


def test_years_are_counted_and_undated_files_are_kept_visible() -> None:
    """The histogram must reconcile with the file count, so undated gets its own number."""
    resolutions = [
        _resolution("a.jpg", when=datetime(2014, 5, 1)),
        _resolution("b.jpg", when=datetime(2014, 9, 9)),
        _resolution("c.jpg", when=datetime(2019, 1, 1)),
        _resolution("d.jpg"),
        _resolution("e.jpg"),
    ]
    years = capture_years(resolutions)

    assert years.by_year == {2014: 2, 2019: 1}
    assert years.undated == 2
    assert sum(years.by_year.values()) + years.undated == len(resolutions)


def test_the_years_are_ordered_oldest_first() -> None:
    """A timeline read out of order is harder to read than a table."""
    resolutions = [
        _resolution("c.jpg", when=datetime(2019, 1, 1)),
        _resolution("a.jpg", when=datetime(2004, 1, 1)),
        _resolution("b.jpg", when=datetime(2011, 1, 1)),
    ]
    assert list(capture_years(resolutions).by_year) == [2004, 2011, 2019]


def test_a_gap_year_is_not_invented() -> None:
    """Only years with files appear. A zero row for 2005-2010 is noise, not information."""
    resolutions = [
        _resolution("a.jpg", when=datetime(2004, 1, 1)),
        _resolution("b.jpg", when=datetime(2011, 1, 1)),
    ]
    assert list(capture_years(resolutions).by_year) == [2004, 2011]


# --- largest files, bounded both ways ----------------------------------------------------------


def test_the_largest_files_are_capped_but_the_total_is_exact() -> None:
    """The extension-census lesson applied: cap the enumeration, never the count."""
    sizes = {Path(f"/src/f{i}.jpg"): i * 10 for i in range(1, 60)}
    listed = largest_files(sizes, limit=5)

    assert listed.total == 59
    assert len(listed.shown) == 5
    assert [entry.size for entry in listed.shown] == [590, 580, 570, 560, 550]


def test_a_short_list_is_shown_whole(tmp_path: Path) -> None:
    """Cry-wolf: a library smaller than the cap must not grow an elision."""
    sizes = {tmp_path / "a.jpg": 10, tmp_path / "b.jpg": 20}
    listed = largest_files(sizes, limit=5)
    assert listed.total == 2
    assert len(listed.shown) == 2


def test_ties_break_by_name_so_the_same_library_renders_identically() -> None:
    """Cross-platform stability: equal sizes must not depend on dict or walk order."""
    sizes = {Path("/src/b.jpg"): 100, Path("/src/a.jpg"): 100, Path("/src/c.jpg"): 100}
    assert [entry.path.name for entry in largest_files(sizes, limit=3).shown] == [
        "a.jpg",
        "b.jpg",
        "c.jpg",
    ]


@pytest.mark.parametrize("limit", [0, -1])
def test_a_nonsense_limit_shows_nothing_and_still_counts_everything(limit: int) -> None:
    """Total and enumeration are independent; a bad cap must not corrupt the count."""
    listed = largest_files({Path("/src/a.jpg"): 1, Path("/src/b.jpg"): 2}, limit=limit)
    assert listed.total == 2
    assert listed.shown == ()
