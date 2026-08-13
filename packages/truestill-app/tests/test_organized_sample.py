"""What a finished organize hands the result grid.

The run summary carried seventeen counts and **no per-file identity at all**, so a grid of the
photos it had just organized was not expressible from the payload. This adds the one thing that
was missing - content ids - under the same bargain every other truncating list in this file
obeys: name a capped sample, and state the total it was taken from.
"""

from __future__ import annotations

from pathlib import Path

from truestill_app.service.organize import GRID_SAMPLE_LIMIT, _completion
from truestill_core.models import (
    ActionResult,
    ActionStatus,
    CategoryMatch,
    Confidence,
    DateSource,
    Decision,
    FileHashes,
    Resolution,
)


def _result(
    name: str, *, sha: str | None, status: ActionStatus = ActionStatus.UPLOADED
) -> ActionResult:
    decision = Decision(
        source=Path("/src") / name,
        category=CategoryMatch(
            label="Camera", reason="t", confidence=Confidence.HIGH, rule="device"
        ),
        captured_at=None,
        date_source=DateSource.EXIF,
        date_tag=None,
        relative=Path("Camera/2014") / name,
    )
    return ActionResult(
        resolution=Resolution(
            decision=decision,
            hashes=FileHashes(sha256=sha, perceptual=None, perceptual_computed=True),
            exact_duplicate=None,
            near_duplicate=None,
        ),
        status=status,
        final_relative=decision.relative,
        # `sha256` on the RESULT, not on the resolution: `execute` establishes it for a
        # unique-size file the scan never hashed, which is the case the grid was losing.
        sha256=sha,
    )


def test_every_organized_photo_is_addressable_by_content(tmp_path: Path) -> None:
    results = [_result(f"a{i}.jpg", sha=f"{i:064x}") for i in range(3)]
    sample = _completion(results, tmp_path)["organized_sample"]

    assert sample["total"] == 3
    assert [t["sha256"] for t in sample["shown"]] == [f"{i:064x}" for i in range(3)]
    assert [t["name"] for t in sample["shown"]] == ["a0.jpg", "a1.jpg", "a2.jpg"]


def test_videos_and_audio_are_counted_elsewhere_and_never_promised_a_tile(tmp_path: Path) -> None:
    """A run of videos organizes real work and has nothing to show. `total` counts PHOTOS, so
    the grid never says "and 40 more" over a space that could not have held them."""
    results = [
        _result("a.jpg", sha="a" * 64),
        _result("b.mp4", sha="b" * 64),
        _result("c.m4a", sha="c" * 64),
    ]
    summary = _completion(results, tmp_path)

    assert summary["organized_sample"]["total"] == 1
    assert [t["name"] for t in summary["organized_sample"]["shown"]] == ["a.jpg"]
    # The tally above the grid still reports all three, which is where they belong.
    assert (summary["videos"], summary["audio"]) == (1, 1)


def test_a_skipped_duplicate_is_not_in_the_grid(tmp_path: Path) -> None:
    """The grid shows what the run PUT somewhere. A skipped duplicate went nowhere."""
    results = [
        _result("kept.jpg", sha="a" * 64),
        _result("dupe.jpg", sha="b" * 64, status=ActionStatus.DUPLICATE),
    ]
    sample = _completion(results, tmp_path)["organized_sample"]

    assert sample["total"] == 1
    assert [t["name"] for t in sample["shown"]] == ["kept.jpg"]


def test_a_photo_with_no_content_hash_is_left_out_of_both_numbers(tmp_path: Path) -> None:
    """A result with no established content id cannot be addressed. A tile built from `None`
    would be a 400 per photo, and counting it in `total` would make "and N more" promise tiles
    that cannot exist. Rare now that `execute` carries the id it computes, but reachable: a
    FAILED outcome never gets one."""
    results = [_result("has.jpg", sha="a" * 64), _result("none.jpg", sha=None)]
    sample = _completion(results, tmp_path)["organized_sample"]

    assert sample["total"] == 1, "an unaddressable photo was counted as showable"
    assert [t["name"] for t in sample["shown"]] == ["has.jpg"]


def test_truncation_says_so(tmp_path: Path) -> None:
    """The rule `DuplicateReport` and `UnreadableReport` already obey: cap the list, never the
    count. A grid that quietly showed 48 of 200 would read as "this is what you organized"."""
    count = GRID_SAMPLE_LIMIT + 25
    results = [_result(f"a{i}.jpg", sha=f"{i:064x}") for i in range(count)]
    sample = _completion(results, tmp_path)["organized_sample"]

    assert sample["total"] == count
    assert len(sample["shown"]) == GRID_SAMPLE_LIMIT


def test_a_run_that_organized_no_photos_still_answers(tmp_path: Path) -> None:
    """Absent keys are how a renderer learns to write `payload.x || {}` everywhere. The key is
    always present; it is the CONTENT that is empty."""
    sample = _completion([], tmp_path)["organized_sample"]

    assert sample == {"total": 0, "shown": []}
