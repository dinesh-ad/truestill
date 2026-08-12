"""Sentinel dates and camera-default dates -- the two tiers, pinned at their real values.

Tier A (hard sentinels) must reject **independently of the sanity window**. That independence
is the whole point of these tests: before the two-tier split, the window was the only thing
rejecting 1904/1970, so lowering its floor to honour genuine scanned-archive dates would have
silently re-admitted them. If someone changes ``_MIN_SANE_YEAR`` again, these fail.

Tier B (suspect camera defaults) must **accept and flag**, never reject: a photo really can be
taken on 2000-01-01, and guessing it away would be exactly the kind of silent data loss the
project forbids.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from truestill_core import dates
from truestill_core.dates import is_suspect_default, resolve_capture_datetime
from truestill_core.models import DateSource
from truestill_core.takeout import TakeoutSidecar

# --- Tier A: hard sentinels ------------------------------------------------------------

_SENTINELS = ["1904:01:01 00:00:00", "1970:01:01 00:00:00"]


@pytest.mark.parametrize("raw", _SENTINELS)
def test_hard_sentinel_is_refused_and_reported(raw: str) -> None:
    """The file had a date, it was an epoch zero, and the report says so."""
    when, source, _ = resolve_capture_datetime(Path("clip.mov"), {"CreateDate": raw})
    assert when is None  # -> Undated/, never filed under 1904 or 1970
    assert source is DateSource.REJECTED_SENTINEL  # not NONE: a date was found and refused


@pytest.mark.parametrize("raw", _SENTINELS)
def test_sentinel_rejection_does_not_depend_on_the_sanity_window(
    raw: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The regression guard: widen the window to admit everything, sentinels still reject.

    This is what makes the floor safe to lower. Deleting this test re-opens the trap.
    """
    monkeypatch.setattr(dates, "_MIN_SANE_YEAR", 1)
    monkeypatch.setattr(dates, "_MAX_SANE_YEAR", 9999)
    _, source, _ = resolve_capture_datetime(Path("clip.mov"), {"CreateDate": raw})
    assert source is DateSource.REJECTED_SENTINEL


def test_sentinel_falls_through_to_a_real_later_tier() -> None:
    """A refused sentinel must not poison a file that another tier can date correctly."""
    when, source, _ = resolve_capture_datetime(
        Path("IMG_20250804_120000.jpg"), {"CreateDate": "1904:01:01 00:00:00"}
    )
    assert source is DateSource.FILENAME
    assert when == datetime(2025, 8, 4)


def test_sentinel_in_a_takeout_sidecar_is_refused_too() -> None:
    """Tier A is a property of the value, not of the field that carried it."""
    sidecar = TakeoutSidecar(taken_at=datetime(1970, 1, 1, tzinfo=UTC), created_at=None, gps=None)
    _, source, _ = resolve_capture_datetime(
        Path("p.jpg"), {}, takeout=sidecar, tz_offset=timedelta(0)
    )
    assert source is DateSource.REJECTED_SENTINEL


def test_a_truly_dateless_file_is_still_plain_none() -> None:
    """No date at all is NONE -- REJECTED_SENTINEL must mean something more specific."""
    _, source, _ = resolve_capture_datetime(Path("mystery.jpg"), {})
    assert source is DateSource.NONE


# --- The lowered floor: genuine early photographs -------------------------------------


@pytest.mark.parametrize(
    "raw",
    ["1900:01:01 12:00:00", "1952:06:14 09:30:00", "1985:07:04 18:22:10", "1989:12:31 23:59:59"],
)
def test_pre_1990_dates_are_now_honoured(raw: str) -> None:
    """Scanned negatives and slides carry real early dates; they used to land in Undated/."""
    when, source, tag = resolve_capture_datetime(Path("scan.jpg"), {"DateTimeOriginal": raw})
    assert source is DateSource.EXIF
    assert tag == "DateTimeOriginal"
    assert when is not None
    assert when.year < 1990


def test_absurdly_early_dates_still_fall_through() -> None:
    """The floor moved, it did not disappear -- an 1872 clock is still garbage.

    The refusal itself is unchanged; only its **name** is. This asserted ``NONE`` because that was
    the only word available, which is precisely the silence `REJECTED_EARLY` was added to end: a
    date was found and refused, and the report used to say the file never had one.
    """
    when, source, _ = resolve_capture_datetime(
        Path("p.jpg"), {"DateTimeOriginal": "1872:01:01 00:00:00"}
    )
    assert when is None
    assert source is DateSource.REJECTED_EARLY


# --- Tier B: suspect camera defaults ---------------------------------------------------


@pytest.mark.parametrize(
    "raw",
    ["2000:01:01 00:00:00", "1999:12:31 00:00:00", "1980:01:01 00:00:00"],
)
def test_camera_default_is_accepted_and_flagged(raw: str) -> None:
    """Accepted -- these can be real -- but counted so the user can review."""
    when, source, _ = resolve_capture_datetime(Path("DSC0001.jpg"), {"DateTimeOriginal": raw})
    assert source is DateSource.EXIF  # never rejected
    assert when is not None
    assert is_suspect_default(when, source) is True


def test_a_real_photo_on_a_reset_day_is_not_flagged() -> None:
    """Exact midnight is the discriminator: a millennium photo at 14:32 is just a photo."""
    when, source, _ = resolve_capture_datetime(
        Path("party.jpg"), {"DateTimeOriginal": "2000:01:01 14:32:07"}
    )
    assert source is DateSource.EXIF
    assert when == datetime(2000, 1, 1, 14, 32, 7)
    assert is_suspect_default(when, source) is False


def test_filename_dates_are_never_flagged_as_camera_defaults() -> None:
    """The false-positive guard.

    ``date_from_filename`` returns **midnight by construction**, so applying the exact-midnight
    test to it would flag every legitimately filename-dated file on a reset day.
    """
    when, source, _ = resolve_capture_datetime(Path("photo_2000-01-01_backup.jpg"), {})
    assert source is DateSource.FILENAME
    assert when == datetime(2000, 1, 1)
    assert is_suspect_default(when, source) is False


def test_an_ordinary_date_is_not_flagged() -> None:
    when, source, _ = resolve_capture_datetime(
        Path("p.jpg"), {"DateTimeOriginal": "2019:05:02 00:00:00"}
    )
    assert is_suspect_default(when, source) is False  # midnight, but not a reset day


def test_a_date_below_the_sanity_floor_is_a_refusal_not_a_silence() -> None:
    """`1899:12:31` was found, refused, and reported as ``NONE`` - "this file had no date".

    That is the exact silence `REJECTED_SENTINEL` and `REJECTED_FUTURE` exist to prevent. It
    survived because the *ceiling* happened to be guarded by the future check and nobody asked
    about the floor (`date-resolver-corpus-measurement.md` §4.3).
    """
    when, source, _ = resolve_capture_datetime(
        Path("p.jpg"), {"DateTimeOriginal": "1899:12:31 23:59:59"}
    )
    assert when is None
    assert source is DateSource.REJECTED_EARLY


def test_the_floor_itself_is_still_a_real_date() -> None:
    """CRY-WOLF HALF. 1900 is the floor *because* scanned negatives carry genuine early dates."""
    when, source, _ = resolve_capture_datetime(
        Path("p.jpg"), {"DateTimeOriginal": "1900:01:01 00:00:00"}
    )
    assert when == datetime(1900, 1, 1)
    assert source is DateSource.EXIF


def test_a_refused_floor_still_lets_a_later_tag_win() -> None:
    """A refusal is a fall-through, not a verdict on the file."""
    when, source, tag = resolve_capture_datetime(
        Path("p.jpg"),
        {"DateTimeOriginal": "1899:12:31 23:59:59", "CreateDate": "2013:07:04 12:30:45"},
    )
    assert when == datetime(2013, 7, 4, 12, 30, 45)
    assert source is DateSource.EXIF
    assert tag == "CreateDate"


def test_a_sentinel_outranks_an_early_date_so_named_refusals_keep_their_name() -> None:
    """Precedence is future > sentinel > early, so no case that already had an answer changes."""
    when, source, _ = resolve_capture_datetime(
        Path("p.jpg"),
        {"DateTimeOriginal": "1904:01:01 00:00:00", "CreateDate": "1899:12:31 23:59:59"},
    )
    assert when is None
    assert source is DateSource.REJECTED_SENTINEL


def test_a_terminating_nul_does_not_cost_the_file_its_date() -> None:
    """EXIF's 20th byte is a NUL, and ``str.strip()`` does not remove it - it is not whitespace."""
    when, source, _ = resolve_capture_datetime(
        Path("p.jpg"), {"DateTimeOriginal": "2013:07:04 12:30:45\x00"}
    )
    assert when == datetime(2013, 7, 4, 12, 30, 45)
    assert source is DateSource.EXIF


def test_an_embedded_nul_is_still_refused() -> None:
    """Edges only, deliberately: splicing a NUL out of the middle invents a string nobody wrote."""
    when, source, _ = resolve_capture_datetime(
        Path("p.jpg"), {"DateTimeOriginal": "2013:07:04\x0012:30:45"}
    )
    assert when is None
    assert source is DateSource.NONE
