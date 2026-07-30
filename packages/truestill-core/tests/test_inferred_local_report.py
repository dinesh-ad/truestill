"""Never-silent report for videos shifted from UTC CreateDate."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from truestill_core.models import (
    CategoryMatch,
    Confidence,
    DateSource,
    Decision,
    FileHashes,
    InferredLocalShift,
    Resolution,
    format_inferred_local_shift_line,
    inferred_local_shifts,
)


def _resolution(
    name: str,
    *,
    source: DateSource,
    captured_at: datetime | None,
    date_tag: str | None,
    inferred_from: datetime | None = None,
) -> Resolution:
    decision = Decision(
        source=Path(name),
        category=CategoryMatch("Saved", "test", Confidence.HIGH, "test"),
        captured_at=captured_at,
        date_source=source,
        date_tag=date_tag,
        relative=Path(name),
        inferred_from=inferred_from,
    )
    return Resolution(
        decision=decision,
        hashes=FileHashes(sha256="a" * 64, perceptual=None),
        exact_duplicate=None,
        near_duplicate=None,
    )


def test_format_line_names_file_and_offset() -> None:
    shift = InferredLocalShift(
        name="VID_20140817_102145.mp4",
        before=datetime(2014, 8, 17, 4, 54, 24),
        after=datetime(2014, 8, 17, 10, 21, 45),
        offset=timedelta(hours=5, minutes=30),
        evidence="filename",
    )
    assert (
        format_inferred_local_shift_line(shift)
        == "VID_20140817_102145.mp4  04:54:24 -> 10:21:45  (+05:30, filename)"
    )


def test_inferred_local_shifts_lists_converted_videos_only() -> None:
    shifted = _resolution(
        "VID_20140817_102145.mp4",
        source=DateSource.INFERRED_LOCAL,
        captured_at=datetime(2014, 8, 17, 10, 21, 45),
        date_tag="CreateDate|filename:VID_|+05:30",
        inferred_from=datetime(2014, 8, 17, 4, 54, 24),
    )
    # not_proven_utc stays EXIF - must not appear as a problem or a shift.
    fallthrough = _resolution(
        "clip.mp4",
        source=DateSource.EXIF,
        captured_at=datetime(2025, 8, 4, 11, 16, 38),
        date_tag="CreateDate|not_proven_utc",
    )
    plain = _resolution(
        "photo.jpg",
        source=DateSource.EXIF,
        captured_at=datetime(2014, 8, 17, 14, 28, 39),
        date_tag="DateTimeOriginal",
    )

    shifts = inferred_local_shifts([shifted, fallthrough, plain])
    assert len(shifts) == 1
    assert shifts[0].name == "VID_20140817_102145.mp4"
    assert shifts[0].evidence == "filename"
    assert format_inferred_local_shift_line(shifts[0]).endswith("(+05:30, filename)")
