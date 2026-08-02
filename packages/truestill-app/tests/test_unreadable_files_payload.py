"""The organize preview payload names the source files that could not be read.

`BACKLOG.md` ``(aac)``. The CLI has a printed block; this is the same fact on the app's side of
the boundary, in the ``{total, shown}`` shape `_duplicate_report` established so that a
truncated list can never read as a complete one.

The reason strings are asserted as **words a user reads**, not enum values, because that is what
§9 governs and what would actually be wrong on screen.
"""

from __future__ import annotations

from pathlib import Path

from truestill_app.service.organize import UNREADABLE_SAMPLE_LIMIT, _unreadable_files
from truestill_core.categorize import CategoryMatch, Confidence
from truestill_core.models import (
    DateSource,
    Decision,
    FileHashes,
    Resolution,
    UnreadableReason,
)


def _resolution(name: str, reason: UnreadableReason | None) -> Resolution:
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
        hashes=FileHashes(sha256=None, perceptual=None, unreadable=reason),
        exact_duplicate=None,
        near_duplicate=None,
    )


def test_the_payload_names_each_unreadable_file_with_a_human_reason() -> None:
    """Named, not merely counted (§9), and the path travels so the UI can show which file."""
    report = _unreadable_files(
        [
            _resolution("DSC_0042.jpg", UnreadableReason.PERMISSION),
            _resolution("IMG_1180.heic", UnreadableReason.IO_ERROR),
            _resolution("gone.mp4", UnreadableReason.MISSING),
            _resolution("fine.jpg", None),
        ]
    )

    assert report["total"] == 3, "a readable file must not be counted as a failure"
    assert [s["name"] for s in report["shown"]] == ["DSC_0042.jpg", "IMG_1180.heic", "gone.mp4"]
    assert [s["reason"] for s in report["shown"]] == [
        "permission denied",
        "input/output error",
        "disappeared during the scan",
    ], "three reasons because they are three different next actions for the user"
    assert report["shown"][0]["path"] == str(Path("/src/DSC_0042.jpg"))


def test_an_ordinary_preview_carries_an_empty_report_not_a_missing_key() -> None:
    """Cry-wolf half. The key is always present so the UI never has to guess what absence means."""
    report = _unreadable_files([_resolution("a.jpg", None), _resolution("b.jpg", None)])

    assert report == {"total": 0, "shown": []}


def test_truncation_states_the_total_it_was_taken_from() -> None:
    """A short list that does not admit it is short reads as the whole story. It is not."""
    over = UNREADABLE_SAMPLE_LIMIT + 7
    report = _unreadable_files(
        [_resolution(f"p{i:04d}.jpg", UnreadableReason.PERMISSION) for i in range(over)]
    )

    assert report["total"] == over, "the total is never truncated - only the list is"
    assert len(report["shown"]) == UNREADABLE_SAMPLE_LIMIT
