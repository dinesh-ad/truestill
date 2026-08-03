"""Destination-copy filename convention and its exact-stamp suppression rule."""

from __future__ import annotations

from datetime import datetime

import pytest
from truestill_core.naming import dated_filename


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


# --- re-organizing an organized copy: our own prefix is replaced, never stacked ----------

_WHEN = datetime(2014, 8, 15, 14, 30, 22)


@pytest.mark.parametrize(
    ("label", "first_pass_time_known", "second_pass_time_known", "expected"),
    [
        ("time -> time", True, True, "20140815_143022_IMG_0001.jpg"),
        ("date -> date", False, False, "20140815_IMG_0001.jpg"),
        ("time -> date", True, False, "20140815_143022_IMG_0001.jpg"),
        ("date -> time", False, True, "20140815_143022_IMG_0001.jpg"),
    ],
)
def test_a_second_pass_never_stacks_a_second_date(
    label: str, first_pass_time_known: bool, second_pass_time_known: bool, expected: str
) -> None:
    """All four precision directions, because only one of them was ever exercised.

    ``date -> time`` is the real one: a file organized from a filename or Takeout date gets a
    date-only name, and organizing it again once EXIF is readable used to produce
    ``20140815_143022_20140815_IMG_0001.jpg``. The other three already held.
    """
    once = dated_filename("IMG_0001.jpg", _WHEN, time_known=first_pass_time_known)
    twice = dated_filename(once, _WHEN, time_known=second_pass_time_known)
    assert twice == expected, label
    assert dated_filename(twice, _WHEN, time_known=second_pass_time_known) == twice


def test_a_date_only_prefix_is_upgraded_in_place_when_the_time_becomes_known() -> None:
    """The replacement half stated on its own: the date survives and gains its time."""
    assert dated_filename("20140815_IMG_0001.jpg", _WHEN, time_known=True) == (
        "20140815_143022_IMG_0001.jpg"
    )


def test_a_leading_date_that_disagrees_with_the_evidence_is_never_overwritten() -> None:
    """Cry-wolf, and the reason the rule checks the date rather than only the shape.

    ``20140815_wedding.jpg`` may be the user's own name, and if the metadata says a *different*
    day we have no standing to delete theirs. Only a leading stamp for the **same** date is
    ours to replace; anything else is prefixed exactly as before.
    """
    other_day = datetime(2013, 1, 1, 12, 0, 0)
    assert dated_filename("20140815_wedding.jpg", other_day, time_known=True) == (
        "20130101_120000_20140815_wedding.jpg"
    )


@pytest.mark.parametrize(
    ("name", "when", "expected"),
    [
        (
            "VID-20250804-WA0020.mp4",
            datetime(2025, 8, 4, 11, 16, 38),
            "20250804_111638_VID-20250804-WA0020.mp4",
        ),
        (
            "IMG_20140815_143000.jpg",
            datetime(2014, 8, 15, 14, 30, 22),
            "20140815_143022_IMG_20140815_143000.jpg",
        ),
        (
            "Screenshot_20260721_000515_EDF & MOI.jpg",
            datetime(2026, 7, 21, 0, 5, 16),
            "20260721_000516_Screenshot_20260721_000515_EDF & MOI.jpg",
        ),
    ],
)
def test_a_vendor_name_that_merely_contains_a_date_still_gets_its_stamp(
    name: str, when: datetime, expected: str
) -> None:
    """The look-alikes, and the reason the rule is anchored rather than a substring search.

    WhatsApp, Android and screenshot names all embed a date somewhere in the middle -- most of
    a real library. Matching a date-only stamp *anywhere* would suppress the prefix for all of
    them and silently drop the time we do know. Only a stamp at the **start** is one we wrote.
    """
    assert dated_filename(name, when, time_known=True) == expected
