"""What a successful run prints today, measured rather than described. `(afm)`

**This file pins behaviour that is about to change, deliberately.** `(afm)` splits `_print_report`
into the two documents it currently is - a decision sheet read before typing a word, and a listing
scrolled past after the fact. A volume change with nothing to measure it against is a change
described in a commit message and nowhere else, so the numbers go in first, in their own commit.

**The four gaps this closes, counted before it was written:**

* the `unique`/`near`/`exact` listing had **no test at all**. Two files call `_print_report`
  (`test_duplicate_origin_is_named.py`, `test_summary_tally_is_disjoint.py`) and both assert
  **tally lines and duplicate origins** - counts in headers, never the listing under them.
* `_print_skipped_undated` had **zero references anywhere** in any suite.
* `organizer.py`'s `FOLDER_PREVIEW` cap on `uncompared_photos` was untested.
* ⚠ **no suite asserted output VOLUME at all** - no `len(out.splitlines())` assertion existed
  anywhere in this repo. That is the measurement `(afm)` is about, and it was the one nobody had.

**Slope, not size, is what these assert.** A test that pins *"100 files print 711 lines"* fails the
next time a field is added to an entry, which is a formatting change and nobody's defect. The
durable fact is that the cost is **per entry and has no ceiling**: two measurements at different
sizes give the slope, and a slope above zero for a block with no cap is the whole finding.
"""

from __future__ import annotations

import io
from contextlib import redirect_stdout
from pathlib import Path

import pytest
from truestill_cli.cli import _print_report, _print_skipped_undated, _print_uncompared
from truestill_core.categorize import CategoryMatch, Confidence
from truestill_core.models import (
    DateSource,
    Decision,
    DuplicateKind,
    DuplicateMatch,
    FileHashes,
    Resolution,
)
from truestill_core.organizer import FOLDER_PREVIEW, uncompared_photos


def _resolution(name: str, *, exact: bool = False, undecodable: bool = False) -> Resolution:
    decision = Decision(
        source=Path("/src") / name,
        category=CategoryMatch(
            label="Camera", reason="t", confidence=Confidence.HIGH, rule="device"
        ),
        captured_at=None,
        date_source=DateSource.NONE,
        date_tag=None,
        relative=Path("Camera/Undated") / name,
    )
    return Resolution(
        decision=decision,
        hashes=FileHashes(
            sha256="a" * 64,
            perceptual=None,
            unreadable=None,
            perceptual_computed=undecodable,
        ),
        exact_duplicate=(
            DuplicateMatch(kind=DuplicateKind.EXACT, matched_path="/lib/twin.jpg", origin="library")
            if exact
            else None
        ),
        near_duplicate=None,
    )


def _lines(render: object) -> int:
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        render()  # type: ignore[operator]
    return len(buffer.getvalue().splitlines())


def _slope(render: object, small: int, large: int) -> float:
    """Lines added per extra file. Zero for a capped block, positive for an unbounded one."""
    return (_lines(lambda: render(large)) - _lines(lambda: render(small))) / (large - small)  # type: ignore[operator]


def test_the_unique_listing_has_no_ceiling() -> None:
    """Every new file costs the terminal a fixed number of lines, for as many files as there are.

    ⚠ **The load-bearing measurement of `(afm)`.** Seven lines per entry, measured here, against a
    real library of 15,082 unique files is **105,585 lines** for this one block - which is what a
    person gets today for typing `organize --apply` on a library that is not small.
    """

    def render(n: int) -> None:
        _print_report([_resolution(f"p{i}.jpg") for i in range(n)], "DRIVE")

    assert _slope(render, 10, 110) > 0, "the unique listing must be shown to be uncapped"
    per_entry = _slope(render, 10, 110)
    assert per_entry == pytest.approx(7.0), (
        f"each unique entry costs {per_entry} lines; if the entry's format changed on purpose, "
        "update this number - if it changed by accident, this is the regression"
    )


def test_the_exact_duplicate_listing_has_no_ceiling() -> None:
    """The skipped files scale too, and they are the ones nobody acts on."""

    def render(n: int) -> None:
        _print_report([_resolution(f"d{i}.jpg", exact=True) for i in range(n)], "DRIVE")

    assert _slope(render, 10, 110) > 0, "the exact-duplicate listing must be shown to be uncapped"


def test_every_undated_file_is_named_with_no_ceiling() -> None:
    """`--skip-undated` names each file it left behind. One line each, forever.

    Its docstring promises *"Never silent"*, and until this test nothing anywhere held it to that.
    """

    def render(n: int) -> None:
        _print_skipped_undated([_resolution(f"u{i}.jpg") for i in range(n)], True)

    assert _slope(render, 10, 110) == pytest.approx(1.0), "one line per undated file"
    assert _lines(lambda: render(10)) > 0, "the block must appear at all when files were skipped"


def test_the_undated_block_is_silent_without_the_flag() -> None:
    """No flag, no block - the gate `(afm)` must not disturb."""
    assert _lines(lambda: _print_skipped_undated([_resolution("u.jpg")], False)) == 0


def test_the_uncompared_sample_is_capped_at_the_source() -> None:
    """`uncompared_photos` hands the CLI a bounded sample and an exact total. `organizer.py`

    ⚠ **The one site of the five that already got this right**, and it is the shape `(afm)` copies:
    the cap lives where the data is built, and `total` carries the truth the sample cannot.
    """
    many = [_resolution(f"c{i}.jpg", undecodable=True) for i in range(FOLDER_PREVIEW + 25)]
    uncompared = uncompared_photos(many)
    assert uncompared is not None
    assert uncompared.total == FOLDER_PREVIEW + 25, "the count is exact and uncapped"
    assert len(uncompared.files) == FOLDER_PREVIEW, "the sample is bounded"


def test_the_uncompared_block_costs_the_same_at_any_size() -> None:
    """The rendered block does not grow, because the cap is upstream of it. Slope zero."""

    def render(n: int) -> None:
        _print_uncompared([_resolution(f"c{i}.jpg", undecodable=True) for i in range(n)])

    assert _slope(render, FOLDER_PREVIEW + 5, FOLDER_PREVIEW + 500) == 0.0, (
        "a capped block must cost the same for 25 files as for 520"
    )
