"""A filename whose date and time run together is still a date. `date-resolver-corpus-measurement`.

**The tier this file covers never fires on the maintainer's library**, because 2,271 of its 2,275
files carry EXIF. That is exactly why it is tested here rather than trusted to a real run: the
only libraries it matters to are the ones nobody here has.

The shape counts quoted below are from that library used as a *labelled set* - every EXIF-dated
file is an example whose answer is known, and the question is what the filename tier would have
returned had the EXIF been absent.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
from truestill_core.dates import resolve_capture_datetime
from truestill_core.models import DateSource

#: Pinned so a passing suite cannot depend on the day it runs.
NOW = datetime(2026, 8, 12, 12, 0, 0)


def resolve(name: str) -> tuple[datetime | None, DateSource]:
    """The real chain with **no embedded metadata**, so tier 4 is the only tier that can answer."""
    value, source, _tag = resolve_capture_datetime(Path(name), {}, now=NOW)
    return value, source


@pytest.mark.parametrize(
    ("name", "day", "origin"),
    [
        ("2014815120755.jpg", "2014-08-15", "unpadded month; 614 files in the reference library"),
        ("2014815120755_1.jpg", "2014-08-15", "the same, duplicate suffix; 29 more"),
        ("20131115120755.jpg", "2013-11-15", "padded, 14 digits"),
        ("ch01_20130704123045.mp4", "2013-07-04", "CCTV/NVR channel export"),
        ("DJI_20230715120000_0001_D.JPG", "2023-07-15", "DJI, timestamped firmware"),
        ("00100dPORTRAIT_00100_BURST20190413181239_COVER.jpg", "2019-04-13", "Google Camera burst"),
        ("00000IMG_00000_BURST20190413181239_COVER.jpg", "2019-04-13", "Google Camera burst"),
    ],
)
def test_a_run_that_is_entirely_a_timestamp_is_read(name: str, day: str, origin: str) -> None:
    value, source = resolve(name)
    assert value is not None, f"{origin}: sent to Undated with the day in its name"
    assert value.date().isoformat() == day, origin
    assert source is DateSource.FILENAME, origin


def test_the_two_repairs_are_both_needed_and_neither_alone_is_enough() -> None:
    """THE LINE SOMEONE WILL GET WRONG, pinned as behaviour rather than as a comment.

    `2014815120755` fails `_COMPACT_DATE` twice over - the trailing time defeats its ``(?!\\d)``
    fence, and the one-digit month defeats ``(0[1-9]|1[0-2])``. **Either repair on its own
    recovers 0 of the 614 real files of this shape.**

    The two assertions separate the halves, and they do it the way a mutation would find:

    * The **14-digit** name has a padded month, so it needs only the fence half. Removing the
      unpadded widths leaves this passing.
    * The **13-digit** name needs the unpadded widths as well. Removing them fails only this one,
      which is the whole point - a half-repair looks like progress on the first assertion while
      recovering nothing that was actually measured.
    """
    fence_half, _ = resolve("20131115120755.jpg")
    assert fence_half is not None, "the digit fence was not relaxed at all"

    both_halves, _ = resolve("2014815120755.jpg")
    assert both_halves is not None, (
        "the shape this change exists for - 614 files, and the ONLY assertion that fails when "
        "the unpadded month/day widths are dropped. Recovering nothing is what a half-repair "
        "measures, and it is why the analysis then looks wrong"
    )


@pytest.mark.parametrize(
    ("name", "why"),
    [
        ("2014121120755.jpg", "reads as both 2014-01-21 and 2014-12-01"),
        ("2014112120755.jpg", "reads as both 2014-01-12 and 2014-11-02"),
    ],
)
def test_two_valid_readings_refuse_rather_than_pick_one(name: str, why: str) -> None:
    """Undated is an honest gap; a coin-flip month is a day that never happened (§1)."""
    value, source = resolve(name)
    assert value is None, f"{why} - the resolver guessed instead of refusing"
    assert source is DateSource.NONE


@pytest.mark.parametrize(
    ("name", "why"),
    [
        ("1381677_10201988507291619_751802045_n.jpg", "a Facebook id, 17 digits"),
        ("1615708931234.jpg", "a bare epoch-ms name today: year 1615, below the floor"),
        ("received_1234567890123456.jpeg", "a Messenger download"),
        ("Snapchat-1234567890.jpg", "a Snapchat save"),
        ("DSC_0142.JPG", "a Nikon serial"),
        ("P1010142.JPG", "a Panasonic serial"),
        ("R0012345.JPG", "a Ricoh serial"),
        ("GX010142.MP4", "a GoPro serial"),
        ("scan_0001.jpg", "a scanner default"),
        ("20130704999999.jpg", "a real day with an impossible clock - not a timestamp"),
        ("19620814093000.jpg", "before any device wrote this convention (_RUN_MIN_YEAR)"),
    ],
)
def test_the_correctly_silent_stay_silent(name: str, why: str) -> None:
    """THE CRY-WOLF HALF. 43.9% of the reference library is correctly silent and must remain so.

    A wider tier 4 pays for itself only if it does not start inventing days for serial numbers.
    """
    value, source = resolve(name)
    assert value is None, f"{why} - a serial or id was read as a date"
    assert source is DateSource.NONE


def test_a_run_timestamp_still_loses_to_embedded_metadata() -> None:
    """Tier order is unchanged: this is a fourth *filename* pattern, not a fourth tier."""
    value, source, tag = resolve_capture_datetime(
        Path("2014815120755.jpg"), {"DateTimeOriginal": "2013:07:04 12:30:45"}, now=NOW
    )
    assert value is not None
    assert value.date().isoformat() == "2013-07-04"
    assert source is DateSource.EXIF
    assert tag == "DateTimeOriginal"


def test_a_messenger_name_is_still_refused_before_this_pattern_is_reached() -> None:
    """The refusal must not be reachable around: a WeChat epoch name has 13 digits too."""
    for name in ("mmexport1988406000000.jpg", "FB_IMG_1988406000000.jpg"):
        value, source = resolve(name)
        assert value is None, f"{name} took a date from a messenger's send stamp"
        assert source is DateSource.NONE
