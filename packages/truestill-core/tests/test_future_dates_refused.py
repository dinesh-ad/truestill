"""A capture date after now is impossible evidence, so it is refused and the chain falls through.

**Found on the real 32,628-file library**, which reported a range of `2002-07-17 to 2051-03-01`:
two files claimed a capture date 25 years ahead and Truestill filed them by it, stretching the
library's stated span by three decades and placing them under a `2051/` folder.

**There was no future check anywhere in the date chain.** What existed was a plausibility band,
`_MIN_SANE_YEAR = 1900` to `_MAX_SANE_YEAR = 2100` -- and 2051 sits comfortably inside it. The
band was also applied only inside `_embedded_datetime`, so it never reached the Takeout or
filename tiers at all.

**Refuse and fall through; never guess.** No library can recover a value someone overwrote, so
the honest response is to reject impossible evidence and continue down the tier ladder. If
nothing survives the file is `Undated/` -- and it is *reported*, because "your file claims 2051"
usually means a wrong device clock or edited metadata, which is worth knowing.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest
from truestill_core.dates import FUTURE_TOLERANCE, resolve_capture_datetime
from truestill_core.models import DateSource

_NOW = datetime(2026, 8, 3, 12, 0, 0)


def _resolve(metadata: dict[str, str], name: str = "photo.jpg", **kwargs: object):
    return resolve_capture_datetime(Path(name), metadata, now=_NOW, **kwargs)  # type: ignore[arg-type]


# --- the defect ---------------------------------------------------------------------------------


def test_a_date_25_years_ahead_is_refused() -> None:
    """The real case, verbatim: `2051-03-01` must not become this file's capture date."""
    when, source, _tag = _resolve({"DateTimeOriginal": "2051:03:01 10:00:00"})

    assert when is None
    assert source is DateSource.REJECTED_FUTURE


def test_the_refusal_reaches_every_tier_not_only_exif() -> None:
    """The old band lived inside `_embedded_datetime`; a filename date never met it.

    A file named `20510301_...` is exactly the shape that slipped past, so the check has to
    sit in the tier loop where the sentinel check already is.
    """
    when, source, _tag = _resolve({}, name="20510301_120000_IMG.jpg")

    assert when is None
    assert source is DateSource.REJECTED_FUTURE


# --- falling through, which is the ruling --------------------------------------------------------


def test_a_lower_tier_still_wins_when_the_top_one_is_impossible() -> None:
    """Refuse and continue -- not refuse and give up. The next real date is the answer."""
    when, source, _tag = _resolve(
        {"DateTimeOriginal": "2051:03:01 10:00:00"}, name="20140815_120000_IMG.jpg"
    )

    assert when == datetime(2014, 8, 15, 0, 0, 0)  # a filename carries a date, not a time
    assert source is DateSource.FILENAME


def test_a_second_embedded_tag_is_tried_before_giving_up() -> None:
    """Fall-through within the embedded tier, which `_embedded_datetime` already did."""
    when, source, _tag = _resolve(
        {"DateTimeOriginal": "2051:03:01 10:00:00", "CreateDate": "2014:08:15 09:30:00"}
    )

    assert when == datetime(2014, 8, 15, 9, 30, 0)
    assert source is DateSource.EXIF


def test_nothing_survives_means_undated_and_it_says_why() -> None:
    """`REJECTED_FUTURE`, never a bare `NONE` -- the difference is the whole disclosure."""
    when, source, _tag = _resolve({"DateTimeOriginal": "2051:03:01 10:00:00"})

    assert when is None
    assert source is not DateSource.NONE
    assert source is DateSource.REJECTED_FUTURE


def test_a_file_with_no_date_at_all_is_still_plain_undated() -> None:
    """Cry-wolf: a file that never had a date must not be reported as having a refused one."""
    when, source, _tag = _resolve({})

    assert when is None
    assert source is DateSource.NONE


def test_an_epoch_sentinel_keeps_its_own_reason() -> None:
    """The two refusals mean different things and must not collapse into one bucket.

    A placeholder date says the device never set its clock; a future date says the clock is
    wrong or the metadata was edited. Different causes, different remedies, different words.
    """
    when, source, _tag = _resolve({"DateTimeOriginal": "1970:01:01 00:00:00"})

    assert when is None
    assert source is DateSource.REJECTED_SENTINEL


# --- the boundary, in both directions ------------------------------------------------------------


def test_a_photo_taken_moments_ago_is_never_refused() -> None:
    """The cry-wolf half that matters most: today's photo must survive."""
    when, source, _tag = _resolve(
        {"DateTimeOriginal": (_NOW - timedelta(minutes=1)).strftime("%Y:%m:%d %H:%M:%S")}
    )

    assert when is not None
    assert source is DateSource.EXIF


@pytest.mark.parametrize(
    ("label", "offset"),
    [
        ("an hour ahead - a camera clock drifting", timedelta(hours=1)),
        ("just inside the tolerance", FUTURE_TOLERANCE - timedelta(minutes=1)),
    ],
)
def test_a_small_amount_ahead_is_tolerated(label: str, offset: timedelta) -> None:
    """Clock skew is ordinary: a camera minutes ahead, or a timestamp read as UTC.

    Rejecting those would send correctly-dated photos to `Undated/`, which is a worse and far
    more common failure than accepting a date a few hours out.
    """
    when, source, _tag = _resolve(
        {"DateTimeOriginal": (_NOW + offset).strftime("%Y:%m:%d %H:%M:%S")}
    )

    assert when is not None, label
    assert source is DateSource.EXIF, label


def test_just_past_the_tolerance_is_refused() -> None:
    """The other side of the same boundary, so the tolerance is pinned rather than assumed."""
    when, source, _tag = _resolve(
        {
            "DateTimeOriginal": (_NOW + FUTURE_TOLERANCE + timedelta(minutes=1)).strftime(
                "%Y:%m:%d %H:%M:%S"
            )
        }
    )

    assert when is None
    assert source is DateSource.REJECTED_FUTURE


def test_the_clock_is_injected_so_the_suite_is_not_time_of_day_dependent() -> None:
    """`now` is a parameter. A test that read the real clock would pass or fail by the hour."""
    ahead = datetime(2030, 1, 1, 0, 0, 0)
    accepted, source, _tag = resolve_capture_datetime(
        Path("p.jpg"), {"DateTimeOriginal": "2029:06:01 10:00:00"}, now=ahead
    )
    assert accepted == datetime(2029, 6, 1, 10, 0, 0)
    assert source is DateSource.EXIF

    refused, refused_source, _ = resolve_capture_datetime(
        Path("p.jpg"), {"DateTimeOriginal": "2029:06:01 10:00:00"}, now=_NOW
    )
    assert refused is None
    assert refused_source is DateSource.REJECTED_FUTURE


#: The widest gap possible between where a photo was taken and where it is imported. UTC+14
#: (Kiritimati) to UTC-12 (Baker Island) is **26 hours**, so a photo taken moments ago on one
#: side can carry a local wall clock 26 hours ahead of the importing computer's.
_MAX_TIMEZONE_SPREAD = timedelta(hours=26)


def test_a_photo_from_the_far_side_of_the_dateline_is_not_refused() -> None:
    """**Measured, not reasoned** (P41): a photo taken in Kiritimati and imported on a UTC-12
    machine went to `Undated/` as `rejected_future`, while the same file imported on UTC+14 or
    UTC+05:30 landed correctly. The gap is 26 hours and the tolerance was one day.

    This is the Adobe shape - a folder decided by the importing computer's clock rather than by
    the photo - and it is the only place the machine's timezone reaches a placement decision.

    Asserted in ABSOLUTE hours rather than against `FUTURE_TOLERANCE`, deliberately. The
    neighbouring boundary tests are written relative to the constant, so they hold at any value
    and cannot catch the constant being too small. This one states the requirement the world
    imposes, so trimming the tolerance back under 26 hours fails here.
    """
    when, source, _tag = _resolve(
        {
            "DateTimeOriginal": (_NOW + _MAX_TIMEZONE_SPREAD).strftime("%Y:%m:%d %H:%M:%S"),
        }
    )

    assert when is not None, "a fresh photo from UTC+14 imported on UTC-12 must still be dated"
    assert source is DateSource.EXIF


def test_a_wrong_device_clock_is_still_refused() -> None:
    """The other side, so widening the tolerance does not quietly retire the case it was written
    for: the real library reporting a range ending in 2051."""
    when, source, _tag = _resolve({"DateTimeOriginal": "2051:03:01 09:00:00"})

    assert when is None
    assert source is DateSource.REJECTED_FUTURE
