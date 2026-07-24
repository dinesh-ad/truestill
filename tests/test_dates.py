"""Date resolution: metadata first, filename second, never filesystem mtime."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from vaeon.dates import date_from_filename, parse_exif_datetime, resolve_capture_datetime
from vaeon.models import DateSource
from vaeon.organizer import build_destination


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
