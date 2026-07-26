"""Date resolution: metadata first, filename second, never filesystem mtime."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
from truestill_core import dates, exif
from truestill_core.dates import date_from_filename, parse_exif_datetime, resolve_capture_datetime
from truestill_core.models import DateSource
from truestill_core.organizer import build_destination


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("2026:07:21 00:14:27", datetime(2026, 7, 21, 0, 14, 27)),
        ("2026:07:21 00:14:27.753+02:00", datetime(2026, 7, 21, 0, 14, 27)),
        ("2025:08:04 11:16:38Z", datetime(2025, 8, 4, 11, 16, 38)),
    ],
)
def test_parse_exif_datetime(raw: str, expected: datetime) -> None:
    assert parse_exif_datetime(raw) == expected


@pytest.mark.parametrize("raw", ["0000:00:00 00:00:00", "", None, "not a date"])
def test_parse_exif_datetime_rejects_junk(raw: str | None) -> None:
    assert parse_exif_datetime(raw) is None


@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        ("IMG-20250804-WA0020.jpg", datetime(2025, 8, 4)),
        ("photo_2024-01-15_12-30-45.jpg", datetime(2024, 1, 15)),
        ("photo_1@29-10-2021_09-30-00.jpg", datetime(2021, 10, 29)),
        ("Screenshot_20260721_001427.png", datetime(2026, 7, 21)),
    ],
)
def test_date_from_filename(filename: str, expected: datetime) -> None:
    assert date_from_filename(filename) == expected


@pytest.mark.parametrize("filename", ["holiday.jpg", "IMG-20259999-WA0001.jpg", "1234.jpg"])
def test_date_from_filename_rejects_invalid(filename: str) -> None:
    assert date_from_filename(filename) is None


def test_metadata_beats_filename() -> None:
    when, source, tag = resolve_capture_datetime(
        Path("IMG-20250804-WA0020.mp4"),
        {"CreateDate": "2025:08:04 11:16:38"},
    )
    assert when == datetime(2025, 8, 4, 11, 16, 38)
    assert source is DateSource.EXIF
    assert tag == "CreateDate"


def test_quicktime_creationdate_beats_utc_container_tags() -> None:
    # iPhone video, shot 2023-08-20 01:30 local (UTC+05:30). The QuickTime container tags are
    # stored in UTC (2023-08-19 20:00), so filing by them would name the wrong day; CreationDate
    # carries the true local moment with its offset and must win.
    when, source, tag = resolve_capture_datetime(
        Path("IMG_1234.mov"),
        {
            "CreationDate": "2023:08:20 01:30:00+05:30",
            "CreateDate": "2023:08:19 20:00:00",
            "MediaCreateDate": "2023:08:19 20:00:00",
            "TrackCreateDate": "2023:08:19 20:00:00",
        },
    )
    # Offset dropped exactly once -> the local wall-clock, not the UTC 08-19 nor a re-shifted time.
    assert when == datetime(2023, 8, 20, 1, 30, 0)
    assert source is DateSource.EXIF
    assert tag == "CreationDate"


def test_quicktime_creationdate_shifts_the_month_folder() -> None:
    # The <Label>/YYYY/MM folder only moves when the UTC->local shift crosses a month (or year)
    # edge: here the UTC container tag says July, the local CreationDate says August.
    when, _, tag = resolve_capture_datetime(
        Path("IMG_9.mov"),
        {"CreationDate": "2023:08:01 01:30:00+05:30", "CreateDate": "2023:07:31 20:00:00"},
    )
    assert when == datetime(2023, 8, 1, 1, 30, 0)
    assert tag == "CreationDate"
    placed = build_destination(Path("/dest"), "Camera", when, "IMG_9.mov")
    assert placed == Path("/dest/Camera/2023/08/IMG_9.mov")  # 2023/07 under the old behaviour


def test_creationdate_wiring_is_requested_and_ranked() -> None:
    # The fix is inert unless exiftool is asked for the tag and the resolver ranks it ahead of
    # the UTC container family. Guard both, dependency-free.
    assert "CreationDate" in exif.REQUESTED_TAGS
    tags = dates.DATE_TAGS
    assert tags.index("CreationDate") < tags.index("CreateDate")


def test_container_createdate_still_used_when_no_creationdate() -> None:
    # Non-Apple videos (no CreationDate) must be unaffected: the container tag is still used.
    when, source, tag = resolve_capture_datetime(
        Path("clip.mp4"), {"CreateDate": "2025:08:04 11:16:38"}
    )
    assert when == datetime(2025, 8, 4, 11, 16, 38)
    assert source is DateSource.EXIF
    assert tag == "CreateDate"


def test_filename_used_when_metadata_absent() -> None:
    when, source, tag = resolve_capture_datetime(Path("IMG-20250804-WA0020.mp4"), {})
    assert when == datetime(2025, 8, 4)
    assert source is DateSource.FILENAME
    assert tag is None


def test_no_evidence_is_not_guessed() -> None:
    when, source, _ = resolve_capture_datetime(Path("mystery.jpg"), {})
    assert when is None
    assert source is DateSource.NONE


def test_destination_layout() -> None:
    root = Path("/dest")
    dated = build_destination(root, "WhatsApp", datetime(2025, 8, 4), "a.mp4")
    assert dated == root / "WhatsApp" / "2025" / "08" / "a.mp4"

    undated = build_destination(root, "Camera", None, "b.jpg")
    assert undated == root / "Camera" / "Undated" / "b.jpg"
