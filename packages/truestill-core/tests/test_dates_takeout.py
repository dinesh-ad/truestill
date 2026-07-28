"""Takeout tiers in the dating evidence chain: priority, tz, prefer flag, fallback."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from truestill_core.dates import resolve_capture_datetime
from truestill_core.models import DateSource
from truestill_core.takeout import TakeoutSidecar

_UTC_TAKEN = datetime(2023, 8, 15, 14, 25, 36, tzinfo=UTC)


def _sidecar(
    *, taken: datetime | None = _UTC_TAKEN, created: datetime | None = None
) -> TakeoutSidecar:
    return TakeoutSidecar(taken_at=taken, created_at=created, gps=None)


def test_exif_wins_by_default() -> None:
    when, source, _ = resolve_capture_datetime(
        Path("p.jpg"), {"DateTimeOriginal": "2020:01:01 09:00:00"}, takeout=_sidecar()
    )
    assert source is DateSource.EXIF
    assert when == datetime(2020, 1, 1, 9, 0, 0)


def test_takeout_used_when_no_exif() -> None:
    when, source, _ = resolve_capture_datetime(Path("p.jpg"), {}, takeout=_sidecar())
    assert source is DateSource.TAKEOUT
    assert when == datetime(2023, 8, 15, 14, 25, 36)  # UTC treated as wall clock


def test_tz_offset_applied_once() -> None:
    when, source, _ = resolve_capture_datetime(
        Path("p.jpg"), {}, takeout=_sidecar(), tz_offset=timedelta(hours=5, minutes=30)
    )
    assert source is DateSource.TAKEOUT
    assert when == datetime(2023, 8, 15, 19, 55, 36)  # +05:30 once, no double-convert


def test_prefer_takeout_flips_priority_over_exif() -> None:
    when, source, _ = resolve_capture_datetime(
        Path("p.jpg"),
        {"DateTimeOriginal": "2020:01:01 09:00:00"},  # wrong embedded date
        takeout=_sidecar(),
        prefer_takeout=True,
    )
    assert source is DateSource.TAKEOUT
    assert when == datetime(2023, 8, 15, 14, 25, 36)


def test_creation_time_fallback_when_no_taken_time() -> None:
    upload = datetime(2023, 9, 1, 10, 0, 0, tzinfo=UTC)
    when, source, _ = resolve_capture_datetime(
        Path("p.jpg"), {}, takeout=_sidecar(taken=None, created=upload)
    )
    assert source is DateSource.TAKEOUT_UPLOAD  # approximate, honestly labelled
    assert when == datetime(2023, 9, 1, 10, 0, 0)


def test_insane_exif_year_falls_through_to_takeout() -> None:
    _, source, _ = resolve_capture_datetime(
        Path("p.jpg"), {"DateTimeOriginal": "1872:01:01 00:00:00"}, takeout=_sidecar()
    )
    assert source is DateSource.TAKEOUT  # reset-clock EXIF is not trusted


def test_filename_below_takeout_upload() -> None:
    _, source, _ = resolve_capture_datetime(Path("IMG_20250804_120000.jpg"), {}, takeout=None)
    assert source is DateSource.FILENAME
