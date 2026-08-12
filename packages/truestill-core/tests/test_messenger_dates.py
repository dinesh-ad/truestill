"""Messenger filenames carry a *delivery* date, not a capture date.

R1: no trustworthy capture date means `Undated/`. The subtlety is that messenger names and
screenshot names share the same `YYYYMMDD` pattern and mean different things, so the refusal is
scoped to the convention, never to the pattern.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
from truestill_core.dates import resolve_capture_datetime
from truestill_core.models import DateSource


@pytest.mark.parametrize(
    "name",
    [
        "IMG-20250804-WA0020.jpg",  # WhatsApp
        "VID-20250804-WA0021.mp4",
        "photo_2024-01-15_12-30-45.jpg",  # Telegram mobile
        "photo_1@29-10-2021_09-30-00.jpg",  # Telegram Desktop
        "signal-2024-01-15-120000.jpg",  # Signal
    ],
)
def test_a_messenger_filename_date_never_places_a_file(name: str) -> None:
    """Forward a 2015 photo today and the name says today. Undated beats confidently wrong."""
    when, source, _ = resolve_capture_datetime(Path(name), {})
    assert when is None
    assert source is DateSource.NONE


def test_a_screenshot_filename_date_is_still_trusted() -> None:
    """The discriminator: a screenshot's filename stamp IS its capture moment."""
    when, source, _ = resolve_capture_datetime(Path("Screenshot_20260721_001427.png"), {})
    assert when == datetime(2026, 7, 21)
    assert source is DateSource.FILENAME


def test_embedded_metadata_still_wins_on_a_messenger_file() -> None:
    """Refusing the filename must not refuse the file: real EXIF still dates it."""
    when, source, _ = resolve_capture_datetime(
        Path("IMG-20250804-WA0020.jpg"), {"DateTimeOriginal": "2015:06:15 10:30:00"}
    )
    assert when == datetime(2015, 6, 15, 10, 30)
    assert source is DateSource.EXIF


@pytest.mark.parametrize(
    "name",
    [
        "WhatsApp Image 2022-07-14 at 18.48.47.jpeg",  # Desktop / Web save
        "WhatsApp Video 2022-07-14 at 18.48.47.mp4",
        "WhatsApp Image 2022-07-14 at 18.48.47 (1).jpeg",  # duplicate suffix
        "PHOTO-2022-07-14-18-48-47.jpg",  # iOS share-to-Files
        "VIDEO-2022-07-14-18-48-47.mp4",
    ],
)
def test_whatsapps_other_three_conventions_are_refused_too(name: str) -> None:
    """WhatsApp writes four naming conventions and `NAME_PATTERNS` listed one.

    The ruling was never wrong - the list it delegates to was short - so these names were read as
    CAPTURE dates while `IMG-...-WA...` was refused: the same app, the same send stamp, opposite
    answers (`date-resolver-corpus-measurement.md` §3.1).
    """
    when, source, _ = resolve_capture_datetime(Path(name), {})
    assert when is None, f"{name} was filed under the day WhatsApp delivered it"
    assert source is DateSource.NONE


@pytest.mark.parametrize(
    ("name", "day", "why"),
    [
        ("IMG-20130704-00001.jpg", datetime(2013, 7, 4), "BlackBerry camera, not a messenger"),
        ("PHOTO-2022-07-14.jpg", datetime(2022, 7, 14), "no time tail - not the iOS convention"),
        ("Screenshot 2024-01-15 at 10.30.45.png", datetime(2024, 1, 15), "a macOS screenshot"),
    ],
)
def test_the_widened_list_does_not_swallow_capture_names(
    name: str, day: datetime, why: str
) -> None:
    """CRY-WOLF HALF, and the reason `PHOTO-`/`VIDEO-` carries a full datetime tail.

    A bare `PHOTO-` prefix would have claimed the second name here and cost it a real date. The
    tail is what keeps the least specific entry in the table narrow enough to earn its place.
    """
    when, source, _ = resolve_capture_datetime(Path(name), {})
    assert when == day, why
    assert source is DateSource.FILENAME
