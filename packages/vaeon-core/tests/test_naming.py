"""Destination-copy filename convention and its exact-stamp suppression rule."""

from __future__ import annotations

from datetime import datetime

from vaeon_core.naming import dated_filename


def test_full_datetime_prefix_when_time_known() -> None:
    when = datetime(2025, 8, 4, 11, 16, 38)
    assert dated_filename("IMG_1234.jpg", when, time_known=True) == "20250804_111638_IMG_1234.jpg"


def test_date_only_prefix_when_time_unknown() -> None:
    when = datetime(2024, 1, 15)
    assert dated_filename("holiday.jpg", when, time_known=False) == "20240115_holiday.jpg"


def test_no_date_keeps_original_name() -> None:
    assert dated_filename("mystery.jpg", None, time_known=False) == "mystery.jpg"


def test_disabled_keeps_original_name() -> None:
    when = datetime(2025, 8, 4, 11, 16, 38)
    assert dated_filename("IMG_1234.jpg", when, time_known=True, enabled=False) == "IMG_1234.jpg"


# --- suppression rule: prefix suppressed iff the EXACT stamp already appears -----------


def test_screenshot_exact_stamp_is_suppressed() -> None:
    """Real case: Android screenshot whose EXIF matches the embedded timestamp exactly."""
    name = "Screenshot_20260720_235232_EDF & MOI.jpg"
    when = datetime(2026, 7, 20, 23, 52, 32)  # EXIF DateTimeOriginal == filename stamp
    assert dated_filename(name, when, time_known=True) == name  # not double-dated


def test_screenshot_one_second_mismatch_is_still_prefixed() -> None:
    """Real case: EXIF says :16 but the filename says :15 -> derived date is authoritative."""
    name = "Screenshot_20260721_000515_EDF & MOI.jpg"
    when = datetime(2026, 7, 21, 0, 5, 16)  # differs from filename by one second
    assert dated_filename(name, when, time_known=True) == f"20260721_000516_{name}"


def test_whatsapp_date_only_in_name_still_gets_full_stamp() -> None:
    """Real case: name carries the date (20250804) but not the time -> full stamp prepended."""
    name = "VID-20250804-WA0020.mp4"
    when = datetime(2025, 8, 4, 11, 16, 38)  # container CreateDate has the time
    assert dated_filename(name, when, time_known=True) == f"20250804_111638_{name}"


def test_rerun_does_not_stack_a_second_prefix() -> None:
    """A genuine re-run derives the same stamp, finds it present, and adds nothing."""
    when = datetime(2025, 8, 4, 11, 16, 38)
    once = dated_filename("IMG_1234.jpg", when, time_known=True)
    twice = dated_filename(once, when, time_known=True)
    assert twice == once == "20250804_111638_IMG_1234.jpg"


def test_date_only_stamp_present_is_suppressed() -> None:
    when = datetime(2024, 1, 15)
    assert dated_filename("20240115_holiday.jpg", when, time_known=False) == "20240115_holiday.jpg"


def test_original_name_is_preserved_inside_prefixed_result() -> None:
    when = datetime(2025, 8, 4, 11, 16, 38)
    result = dated_filename("random.jpg", when, time_known=True)
    assert result.endswith("random.jpg")
    assert result.startswith("20250804_111638_")
