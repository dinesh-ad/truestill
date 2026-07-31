"""The rescue action: a person tells truestill when a photo was taken (step 5, part 2).

This is the first surface where a user changes what truestill *believes* about their photos, and
it is what makes everything since step 1 reachable - `confirm_date` shipped in step 3 with zero
routes and zero CLI commands, so until now nobody could perform a rescue at all.

**Two decisions this file pins, both of which look arbitrary without their reason.**

*The assumed time is 12:00, not 00:00.* Placement never uses time - `layout._DATE_TOKENS` is
years, months and days - but **event clustering does**: `events.py` measures gaps between
``captured_at`` values in hours and seconds. Confirming 400 scanned prints at midnight would
collapse them into one enormous 00:00 event. Midday is the least-wrong point in a day, keeps a
day's files together rather than on a boundary, and avoids looking like the dead-clock midnight
values `dates.is_suspect_default` exists to flag.

*A precision the model cannot represent is refused, not rounded.* ``captured_at`` is a
``datetime``; there is no year-only or month-only form. Accepting "1985" and storing
1985-01-01 would present a guess as an exact date **recorded as human-confirmed** - the most
trusted tier in the system - which is precisely the lie this program was built to remove. The
refusal is deliberate and says so where the user meets it. The archivist with "summer 1985" is a
real unserved user; that is a backlog item, not a silent rounding.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
from truestill_app.service.date_rescue import ASSUMED_TIME, confirm_file_date
from truestill_core.catalog import Catalog
from truestill_core.models import DateSource

SHA = "sha-000"


def _library(db: Path) -> None:
    with Catalog(db) as catalog:
        catalog.record_uploaded(
            source_path="/src/a.jpg",
            original_name="a.jpg",
            sha256=SHA,
            copy_sha256=SHA,
            perceptual=None,
            size=10,
            captured_at="2014-08-16T10:46:26",
            category="Camera",
            relative="Camera/2014/a.jpg",
            date_source=DateSource.FILENAME.value,
        )


def _row(db: Path) -> dict:
    with Catalog(db) as catalog:
        row = catalog.find_by_sha256(SHA)
        assert row is not None
        return {"captured_at": row["captured_at"], "date_source": row["date_source"]}


# --- the action ------------------------------------------------------------------------------


def test_confirming_a_date_changes_what_the_library_believes(tmp_path: Path) -> None:
    """The point of the whole program, finally reachable from outside the catalog API."""
    db = tmp_path / "c.sqlite"
    _library(db)

    result = confirm_file_date(db, sha256=SHA, date_text="2011-03-04")

    assert result["ok"] is True
    assert _row(db)["date_source"] == DateSource.HUMAN_CONFIRMED.value
    assert _row(db)["captured_at"].startswith("2011-03-04")


def test_the_durable_record_is_written_too(tmp_path: Path) -> None:
    """`files` can be deleted by undo-organize; `date_confirmations` is what survives it."""
    db = tmp_path / "c.sqlite"
    _library(db)

    confirm_file_date(db, sha256=SHA, date_text="2011-03-04")

    with Catalog(db) as catalog:
        assert catalog.confirmed_date(SHA).startswith("2011-03-04")


def test_an_unknown_file_is_refused_not_silently_ignored(tmp_path: Path) -> None:
    """§9: a no-op that reports success is how a user believes a correction was saved."""
    db = tmp_path / "c.sqlite"
    _library(db)

    result = confirm_file_date(db, sha256="not-in-the-catalog", date_text="2011-03-04")

    assert result["ok"] is False
    assert "no longer" in result["error"].lower() or "not" in result["error"].lower()


# --- the assumed time ------------------------------------------------------------------------


def test_a_date_without_a_time_is_stored_at_midday(tmp_path: Path) -> None:
    """Not midnight. See the module docstring - event clustering measures gaps in hours."""
    db = tmp_path / "c.sqlite"
    _library(db)

    confirm_file_date(db, sha256=SHA, date_text="2011-03-04")

    assert _row(db)["captured_at"] == datetime(2011, 3, 4, 12, 0, 0).isoformat()
    assert ASSUMED_TIME.hour == 12


def test_a_supplied_time_is_used_exactly(tmp_path: Path) -> None:
    """The default is a default, not a policy: someone who knows the time keeps it."""
    db = tmp_path / "c.sqlite"
    _library(db)

    confirm_file_date(db, sha256=SHA, date_text="2011-03-04", time_text="09:15")

    assert _row(db)["captured_at"] == datetime(2011, 3, 4, 9, 15, 0).isoformat()


def test_midnight_is_allowed_when_the_user_actually_types_it(tmp_path: Path) -> None:
    """Cry-wolf half: what is refused is imprecision, never a particular time of day.

    A photo genuinely taken at midnight is a real photo, and `is_suspect_default` does not flag
    a human-confirmed date anyway - it gates on the clock-derived tiers.
    """
    db = tmp_path / "c.sqlite"
    _library(db)

    result = confirm_file_date(db, sha256=SHA, date_text="2011-03-04", time_text="00:00")

    assert result["ok"] is True
    assert _row(db)["captured_at"] == datetime(2011, 3, 4, 0, 0, 0).isoformat()


# --- refusing a precision the model cannot hold ------------------------------------------------


@pytest.mark.parametrize("imprecise", ["1985", "1985-07", "summer 1985", "07/1985"])
def test_a_partial_date_is_refused_rather_than_rounded(tmp_path: Path, imprecise: str) -> None:
    """ "1985" silently becoming 1985-01-01, recorded as human-confirmed, is the lie to avoid."""
    db = tmp_path / "c.sqlite"
    _library(db)

    result = confirm_file_date(db, sha256=SHA, date_text=imprecise)

    assert result["ok"] is False
    assert _row(db)["date_source"] == DateSource.FILENAME.value, "the library was changed anyway"


def test_the_refusal_says_it_is_deliberate_and_what_is_supported(tmp_path: Path) -> None:
    """A user meeting this must learn it is a decision, not a parser that failed to try."""
    db = tmp_path / "c.sqlite"
    _library(db)

    error = confirm_file_date(db, sha256=SHA, date_text="1985")["error"].lower()

    assert "full date" in error, "the supported form is not named"
    assert "guess" in error or "exact" in error, "the reason for refusing is not given"


def test_the_refusal_does_not_use_backend_vocabulary(tmp_path: Path) -> None:
    """(ccc): the message is for someone holding a scanned print, not a parser author."""
    db = tmp_path / "c.sqlite"
    _library(db)

    error = confirm_file_date(db, sha256=SHA, date_text="1985")["error"].lower()

    for jargon in ("iso", "datetime", "parse", "precision", "captured_at", "sha"):
        assert jargon not in error, f"backend vocabulary reached the user: {jargon!r}"


def test_a_malformed_date_is_refused(tmp_path: Path) -> None:
    db = tmp_path / "c.sqlite"
    _library(db)

    assert confirm_file_date(db, sha256=SHA, date_text="not a date")["ok"] is False


def test_a_bad_time_is_refused_without_changing_anything(tmp_path: Path) -> None:
    """A partial write here would leave a date the user never chose."""
    db = tmp_path / "c.sqlite"
    _library(db)

    result = confirm_file_date(db, sha256=SHA, date_text="2011-03-04", time_text="25:99")

    assert result["ok"] is False
    assert _row(db)["captured_at"] == "2014-08-16T10:46:26"
