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
