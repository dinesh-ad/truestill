"""Mutation guards for the video UTC ladder safety bounds.

Each test monkeypatches one load-bearing check so the corresponding production assertion
would fail - proving the guard can fail against the defect (ENGINEERING_STANDARD §4).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest
from truestill_core import video_utc
from truestill_core.categorize import is_messenger_filename
from truestill_core.dates import resolve_capture_datetime
from truestill_core.models import DateSource
from truestill_core.video_utc import (
    FILENAME_OFFSET_EPSILON,
    candidate_filename_offsets,
    device_filename_local,
    unique_filename_offset,
)

_ANDROID = {
    "CreateDate": "2014:08:17 04:54:24",
    "Duration": "0:02:38",
    "MIMEType": "video/mp4",
}
_CREATE = datetime(2014, 8, 17, 4, 54, 24)
_FILENAME = datetime(2014, 8, 17, 10, 21, 45)
_DURATION = timedelta(minutes=2, seconds=38)
_IST = timedelta(hours=5, minutes=30)


def test_production_unique_match_refuses_wide_epsilon() -> None:
    assert unique_filename_offset(_CREATE, _FILENAME, _DURATION) == _IST
    assert (
        unique_filename_offset(_CREATE, _FILENAME, _DURATION, epsilon=timedelta(minutes=35)) is None
    )


def test_mutation_dropping_unique_check_accepts_ambiguity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Widen-epsilon scenario: without unique-match, a second offset is accepted."""

    def without_unique(
        create_utc: datetime,
        filename_local: datetime,
        duration: timedelta | None,
        *,
        epsilon: timedelta = FILENAME_OFFSET_EPSILON,
    ) -> timedelta | None:
        eps = epsilon.total_seconds()
        for offset in candidate_filename_offsets():
            local_end = create_utc + offset
            if abs((local_end - filename_local).total_seconds()) <= eps:
                return offset
            if (
                duration is not None
                and abs((local_end - filename_local - duration).total_seconds()) <= eps
            ):
                return offset
        return None

    monkeypatch.setattr(video_utc, "unique_filename_offset", without_unique)
    # Production refuses; mutated matcher returns the first of several hits.
    assert (
        video_utc.unique_filename_offset(
            _CREATE, _FILENAME, _DURATION, epsilon=timedelta(minutes=35)
        )
        is not None
    )


def test_mutation_dropping_duration_breaks_android(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without the duration term, CreateDate is ~5h27m from filename - not on the grid."""

    def no_duration(
        create_utc: datetime,
        filename_local: datetime,
        _duration: timedelta | None,
        *,
        epsilon: timedelta = FILENAME_OFFSET_EPSILON,
    ) -> timedelta | None:
        return unique_filename_offset(create_utc, filename_local, None, epsilon=epsilon)

    monkeypatch.setattr(video_utc, "unique_filename_offset", no_duration)
    when, source, _ = resolve_capture_datetime(Path("VID_20140817_102145.mp4"), _ANDROID)
    assert when == _CREATE
    assert source is DateSource.EXIF


def test_mutation_hour_grid_breaks_ist(monkeypatch: pytest.MonkeyPatch) -> None:
    """A 60-minute grid cannot express +05:30, so the Android IST case must not convert."""
    monkeypatch.setattr(video_utc, "FILENAME_OFFSET_STEP", timedelta(hours=1))
    when, source, _ = resolve_capture_datetime(Path("VID_20140817_102145.mp4"), _ANDROID)
    assert when == _CREATE
    assert source is DateSource.EXIF
    assert _IST not in video_utc.candidate_filename_offsets()


def test_mutation_dropping_messenger_refusal_leaks_wa_offset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A ``-WA`` name that also embeds ``VID_YYYYMMDD_HHMMSS`` converts if refusal is dropped.

    Native ``VID-20140817-WA0001.mp4`` has no HHMMSS; the dangerous form is a WA delivery
    stamp wrapping (or followed by) a device-local time. Production refuses the whole name.
    """
    # WhatsApp pattern is prefix-anchored without ``$``, so a trailing device stamp still matches.
    name = "VID-20140817-WA0001_VID_20140817_102145.mp4"
    assert is_messenger_filename(name)
    assert device_filename_local(name) is None

    def leaky(stem: str) -> tuple[datetime, str] | None:
        match = video_utc._DEVICE_LOCAL_TIME.search(stem)
        if match is None:
            return None
        ymd, hms = match.group("ymd"), match.group("hms")
        when = datetime.strptime(f"{ymd}{hms}", "%Y%m%d%H%M%S")  # noqa: DTZ007
        return when, f"filename:{match.group('prefix').upper()}_"

    monkeypatch.setattr(video_utc, "device_filename_local", leaky)
    when, source, tag = resolve_capture_datetime(Path(name), _ANDROID)
    assert when == _FILENAME
    assert source is DateSource.INFERRED_LOCAL
    assert tag is not None
    assert "+05:30" in tag


def test_canon_mvi_2550_unaffected_by_filename_ladder() -> None:
    """Canon pin survives even when Android-like metadata is also present."""
    when, source, tag = resolve_capture_datetime(
        Path("MVI_2550.MOV"),
        {
            "DateTimeOriginal": "2014:08:17 14:28:39",
            "CreateDate": "2014:08:17 07:58:39",
            "TimeZone": "+06:30",
            "Duration": "1.46 s",
            "MIMEType": "video/quicktime",
            # Decoy: must not override DTO.
            "GPSDateStamp": "2014:08:17",
            "GPSTimeStamp": "07:58:39",
        },
    )
    assert when == datetime(2014, 8, 17, 14, 28, 39)
    assert source is DateSource.EXIF
    assert tag == "DateTimeOriginal"
