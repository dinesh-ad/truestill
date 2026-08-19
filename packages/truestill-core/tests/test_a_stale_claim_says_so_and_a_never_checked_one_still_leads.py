"""Staleness gains a consequence, tiered per drive and reported at the claim. `(abg)` Stage 3.

**The defect.** The claim became datable (Stage 1) and then dated (Stage 2); it never became
*conditional*. A library last checked in April read exactly like one checked this morning - the
count and the date, and no consequence whatever. `abg.md:172-207`: *"what is left is that
staleness does nothing."*

**Why the tier is computed PER DRIVE and reported at the claim.** `checked_at` is
`min(checked) if checked and not never else None`, so **one never-checked drive removes the date
for every other drive**. That is Stage 1's rule and it is right - no single date is true of the
whole claim - but it means whole-claim tiering can never fire on a library that has one unchecked
place. Measured on the maintainer's own catalog, which is exactly that shape::

    Morrowkeep           files=  395   last_verified=None
    Output               files= 2269   last_verified=2026-07-28
    The Memory Cabinet   files= 2269   last_verified=2026-07-28
    checked_at = None    never_checked = ('Morrowkeep',)

So `dated_at` is added beside `checked_at` rather than replacing it: the oldest date among the
drives that HAVE one, which an unchecked drive does not blank. Two true statements - *"Morrowkeep
has never been checked"* and *"the oldest dated place was checked 34 days ago"* - instead of one
that hides both.

⚠ **The absolute date is never replaced by the relative one.** `abg.md:280` and both renderers
record *"a date that only gets older cannot mislead"*, and a bare "34 days ago" is not such a
value. What legitimately changes with time is the **tier**; the date stays beside it.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from truestill_core.drive import (
    CUSTODY_SOFTENS_AFTER_DAYS,
    CUSTODY_STALE_AFTER_DAYS,
    CustodyTier,
    custody_freshness,
)

#: A fixed clock, so a tier is never a function of when the suite happened to run. Every fixture
#: here dates its drives RELATIVE to this - a hardcoded past date would cross 30 days by calendar
#: and turn a green suite red with no commit behind it.
NOW = datetime(2026, 8, 19, 12, 0, tzinfo=UTC)


class _Settings:
    """The one-method `_SettingsReader` protocol `custody_freshness` needs for naming."""

    def get_setting(self, key: str) -> str | None:  # noqa: ARG002 - the protocol's shape
        return None


def _days_ago(days: int) -> str:
    return (NOW - timedelta(days=days)).isoformat()


def _drive(uuid: str, label: str, *, verified: str | None) -> dict[str, object]:
    return {"uuid": uuid, "label": label, "last_verified": verified}


def _freshness(*drives: dict[str, object]):
    rows = list(drives)
    return custody_freshness(_Settings(), rows, rows, now=NOW)


def test_a_never_checked_place_no_longer_hides_how_old_the_others_are() -> None:
    """⚠ THE REGRESSION, AND THE SHAPE OF THE REAL CATALOG.

    One never-checked drive plus two dated ones past the softening threshold. Today's code can
    express only half of this: `checked_at` is None, so the two 34-day-old drives are invisible
    and the claim says nothing about them at all.
    """
    got = _freshness(
        _drive("M", "Morrowkeep", verified=None),
        _drive("O", "Output", verified=_days_ago(34)),
        _drive("C", "The Memory Cabinet", verified=_days_ago(20)),
    )

    # Stage 1's rule, deliberately unchanged: no single date is true of the whole claim.
    assert got.checked_at is None
    assert got.never_checked == ("Morrowkeep",)

    # ...and the part that did not exist: the dated drives still get to be reported.
    assert got.dated_at is not None, (
        "a never-checked drive still blanks the date for every other drive, so the tiers can "
        "never fire on a library shaped like the maintainer's own"
    )
    assert got.dated_days == 34, "the tier must follow the OLDEST dated drive, not the newest"
    assert got.tier is CustodyTier.SOFTENING


def test_the_tier_follows_the_oldest_dated_drive_not_an_average_or_the_newest() -> None:
    """*"Two drives 34 days old"* is false when one is 34 and the other 20. The claim names the
    oldest, because a claim is only as fresh as its weakest leg - the same rule `checked_at`
    already follows, applied to the drives that have a date."""
    got = _freshness(
        _drive("A", "A", verified=_days_ago(120)),
        _drive("B", "B", verified=_days_ago(1)),
    )

    assert got.dated_days == 120
    assert got.tier is CustodyTier.STALE
    # And with no never-checked drive, `checked_at` and `dated_at` agree exactly.
    assert got.checked_at == got.dated_at


@pytest.mark.parametrize(
    ("days", "tier"),
    [
        (0, CustodyTier.FRESH),
        (CUSTODY_SOFTENS_AFTER_DAYS - 1, CustodyTier.FRESH),
        (CUSTODY_SOFTENS_AFTER_DAYS, CustodyTier.SOFTENING),
        (CUSTODY_STALE_AFTER_DAYS - 1, CustodyTier.SOFTENING),
        (CUSTODY_STALE_AFTER_DAYS, CustodyTier.STALE),
        (400, CustodyTier.STALE),
    ],
)
def test_each_threshold_bites_on_its_own_day(days: int, tier: CustodyTier) -> None:
    """Both boundaries, from both sides. A `>=` quietly weakened to `>` moves the consequence by a
    day in a way no round-number fixture would notice."""
    got = _freshness(_drive("A", "A", verified=_days_ago(days)))

    assert got.tier is tier, f"{days} days read as {got.tier}, expected {tier}"
    assert got.dated_days == days


def test_a_library_with_nothing_dated_is_fresh_rather_than_stale() -> None:
    """An honest zero. Nothing has been checked, so there is no age to have exceeded - the
    never-checked state carries that claim, and it is a different one."""
    got = _freshness(_drive("M", "Morrowkeep", verified=None))

    assert got.dated_at is None
    assert got.dated_days is None
    assert got.tier is CustodyTier.FRESH, (
        "an undated library was called stale, which reads as 'checked long ago' about a place "
        "nothing has ever looked at"
    )


def test_a_drive_holding_nothing_still_neither_supplies_nor_withholds_the_age() -> None:
    """The filtering rule Stage 1 established, extended to the new field rather than forgotten.

    `holding` is the caller's filter; a registered drive with no copies is not one of the places
    the claim is about. It must not be able to drag `dated_at` backwards either.
    """
    holding = [_drive("A", "A", verified=_days_ago(5))]
    registered = [*holding, _drive("SPARE", "Spare, never used", verified=_days_ago(300))]

    got = custody_freshness(_Settings(), holding, registered, now=NOW)

    assert got.dated_days == 5
    assert got.tier is CustodyTier.FRESH


def test_the_fresh_case_is_byte_identical_to_what_shipped_before() -> None:
    """The cry-wolf half. A library checked last week must read exactly as it did yesterday -
    a consequence that fires on a healthy library is the nagging this entry exists to avoid."""
    got = _freshness(
        _drive("A", "A", verified=_days_ago(3)),
        _drive("B", "B", verified=_days_ago(9)),
    )

    assert got.tier is CustodyTier.FRESH
    assert got.never_checked == ()
    assert got.checked_at == got.dated_at
