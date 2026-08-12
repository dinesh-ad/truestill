"""Embedded date values the wild really contains, beyond the one EXIF spells. `(add)`.

Every string here was read off a real file in `metadata-extractor-images` or `exif-samples`
(1,077 tag readings, 60 refused). The split between the two halves is a **ruling**, not a
limitation of effort, and each half states its own reason:

* **Recovered** - numeric, year-first, no locale and no ambiguity. The day is not in question.
* **Refused** - either ambiguous (`12/29/93` is the US-vs-EU wrong-answer class) or
  locale-dependent (`Tue Dec 14` needs `%a`/`%b`, which read the running machine's `LC_TIME`).
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
from truestill_core.dates import parse_exif_datetime, resolve_capture_datetime
from truestill_core.models import DateSource

RECOVERED = [
    ("20020904", datetime(2002, 9, 4), "date-only compact, 4 readings"),
    ("20030701", datetime(2003, 7, 1), "date-only compact"),
    ("2011-03-15T10:14:46-04:00", datetime(2011, 3, 15, 10, 14, 46), "ISO 8601"),
    ("2008.07.10  15:16:55", datetime(2008, 7, 10, 15, 16, 55), "dots, and a double space"),
    ("2019:04:24 22:24:00+02:00 DST", datetime(2019, 4, 24, 22, 24), "a trailing DST marker"),
    ("2011:06:14 15:47+02:00", datetime(2011, 6, 14, 15, 47), "minute precision, no seconds"),
    ("2020:01:05 15:04Z", datetime(2020, 1, 5, 15, 4), "minute precision, Zulu"),
    ("2013:07:04", datetime(2013, 7, 4), "date only, EXIF separators"),
    ("2013/07/04 12:30:45", datetime(2013, 7, 4, 12, 30, 45), "slashes, but year first"),
]

REFUSED_AMBIGUOUS = ["12/29/93 13:52:11", "12/5/95 10:44 PM", "2/5/14", "12/09/14", "02-Aug-99"]
REFUSED_LOCALE = [
    "Tue Dec 14 09:54:11 2004",
    "Tue Dec  2 12:06:48 2008",
    "Sun May 27 09:09:46 2007",
    "Monday, September 11, 2000, 2:45:40 PM",
]
REFUSED_CORRUPT = [
    "0000:00:00 00:00:00",
    "    :  :     :  :",
    "200Ô-04-07T19:06:16-07:00",
    "40096:09:19 03:52:44",
    "Test Year",
    "2013:07:04 25:00:00",
    "2013:02:30 12:00:00",
    "",
    "   ",
]


@pytest.mark.parametrize(("raw", "expected", "why"), RECOVERED)
def test_an_unambiguous_numeric_form_is_recovered(raw: str, expected: datetime, why: str) -> None:
    assert parse_exif_datetime(raw) == expected, why


@pytest.mark.parametrize("raw", REFUSED_AMBIGUOUS)
def test_an_ambiguous_form_is_refused_because_a_wrong_day_is_worse_than_none(raw: str) -> None:
    """`12/29/93` cannot be read without choosing US or EU, and choosing is the wrong-answer
    class `date-resolver-corpus-measurement.md` §3.2 exists to avoid. §1: dates are never guessed.
    """
    assert parse_exif_datetime(raw) is None


@pytest.mark.parametrize("raw", REFUSED_LOCALE)
def test_a_month_name_form_is_refused_because_it_would_read_the_machines_locale(raw: str) -> None:
    """`%a`/`%b` resolve against `LC_TIME`, so these parse on an English machine and fail on a
    French one - the same file landing in a different folder depending on the computer, which is
    the failure this project exists not to have. Five readings of 1,077 do not buy an English
    month table.
    """
    assert parse_exif_datetime(raw) is None


@pytest.mark.parametrize("raw", REFUSED_CORRUPT)
def test_the_refusals_that_were_already_working_still_refuse(raw: str) -> None:
    """CRY-WOLF HALF. A wider parser must not start blessing unset fields or corrupt bytes."""
    assert parse_exif_datetime(raw) is None


def test_a_recovered_value_still_loses_to_a_better_tag() -> None:
    """Tier order untouched: `DateTimeOriginal` wins even when only `CreateDate` needed the new
    parser, and vice versa - a widened parser is not a widened tier."""
    when, source, tag = resolve_capture_datetime(
        Path("p.jpg"), {"DateTimeOriginal": "20020904", "CreateDate": "2013:07:04 12:30:45"}
    )
    assert when == datetime(2002, 9, 4)
    assert source is DateSource.EXIF
    assert tag == "DateTimeOriginal"


def test_a_recovered_value_is_still_subject_to_the_sentinel_and_window_rules() -> None:
    """The new forms enter the same chain, not beside it."""
    assert parse_exif_datetime("19700101") == datetime(1970, 1, 1)  # parses...
    when, source, _ = resolve_capture_datetime(Path("p.jpg"), {"DateTimeOriginal": "19700101"})
    assert when is None, "an epoch zero reached the timeline through the new parser"
    assert source is DateSource.REJECTED_SENTINEL


@pytest.mark.parametrize("raw", ["2002094", "200294", "2002090412", "20020904123", "2013070"])
def test_a_digit_run_that_is_not_exactly_eight_is_not_a_compact_date(raw: str) -> None:
    """The compact form must be **exactly eight digits or nothing**, and this is what pins it.

    Found by mutation: making the separators optional so one pattern could serve both forms lets
    a seven-digit run split as `2002` + `09` + `4`, which invents a reading of a number that is
    not a date. The source comment asserted this; nothing tested it, so the mutant survived.
    """
    assert parse_exif_datetime(raw) is None
