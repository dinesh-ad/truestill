"""Trip detection: grouping consecutive active days into multi-day trips (Stage 2b, pure)."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from truestill_core.events import EventCandidate, EventItem
from truestill_core.trips import TripDeclineReason, detect_trips

# Naive datetimes are the domain (EXIF wall-clock), matching test_events.py.


def _candidate_on(day: date, n: int, *, hour: int = 10) -> EventCandidate:
    """A synthetic n-item cluster on `day`. Only `.start.date()` is read by `detect_trips`."""
    items = tuple(
        EventItem(
            key=f"c-{day}-{hour}-{i}",
            captured_at=datetime(day.year, day.month, day.day, hour, 0, 0) + timedelta(seconds=i),
            sha256=f"c{day:%Y%m%d}{hour:02d}{i:05d}",
        )
        for i in range(n)
    )
    return EventCandidate(items=items)


def _items_on(day: date, n: int) -> list[EventItem]:
    """n synthetic dated items on `day`, for the all-photos-that-day population."""
    return [
        EventItem(
            key=f"a-{day}-{i}",
            captured_at=datetime(day.year, day.month, day.day, 0, 0, 0) + timedelta(seconds=i),
            sha256=f"a{day:%Y%m%d}{i:05d}",
        )
        for i in range(n)
    ]


def test_the_real_wayanad_run_is_one_full_proposal_no_trim() -> None:
    """Acceptance fixture: real cluster shape and real day counts from `trip-grouping-research.md`.

    Dinesh confirmed the Aug 14 evening (19:46-21:22, n=23) was the drive up to Wayanad, so the
    proposal must equal ground truth -- the whole Aug 14-17 run, no edge trimmed.
    """
    clusters = [
        _candidate_on(date(2014, 8, 14), 23, hour=19),
        _candidate_on(date(2014, 8, 14), 8, hour=22),
        _candidate_on(date(2014, 8, 15), 618, hour=7),
        _candidate_on(date(2014, 8, 15), 13, hour=20),
        _candidate_on(date(2014, 8, 16), 565, hour=9),
        _candidate_on(date(2014, 8, 16), 157, hour=16),
        _candidate_on(date(2014, 8, 17), 594, hour=6),
        _candidate_on(date(2014, 8, 17), 42, hour=18),
        _candidate_on(date(2014, 8, 17), 15, hour=21),
    ]
    all_items = (
        _items_on(date(2014, 8, 14), 31)
        + _items_on(date(2014, 8, 15), 635)
        + _items_on(date(2014, 8, 16), 737)
        + _items_on(date(2014, 8, 17), 654)
    )

    result = detect_trips(all_items, clusters)

    assert result.declines == []
    assert len(result.proposals) == 1
    trip = result.proposals[0]
    assert trip.start_date == date(2014, 8, 14)
    assert trip.end_date == date(2014, 8, 17)
    assert dict(trip.days) == {
        date(2014, 8, 14): 31,
        date(2014, 8, 15): 635,
        date(2014, 8, 16): 737,
        date(2014, 8, 17): 654,
    }


def test_a_run_crossing_the_year_boundary_splits_into_two_proposals() -> None:
    """R2: nothing is filed outside its own year, so this is two trips, never one."""
    days = [
        date(2016, 12, 28),
        date(2016, 12, 29),
        date(2016, 12, 30),
        date(2017, 1, 1),
        date(2017, 1, 2),
    ]
    clusters = [_candidate_on(d, 10) for d in days]
    all_items = [item for d in days for item in _items_on(d, 10)]

    result = detect_trips(all_items, clusters)  # Dec 31 bridged by the default max_gap_days=1

    assert result.declines == []
    assert len(result.proposals) == 2
    tail, head = sorted(result.proposals, key=lambda p: p.start_date)
    assert (tail.start_date, tail.end_date) == (date(2016, 12, 28), date(2016, 12, 30))
    assert (head.start_date, head.end_date) == (date(2017, 1, 1), date(2017, 1, 2))
    assert set(tail.days) == {date(2016, 12, 28), date(2016, 12, 29), date(2016, 12, 30)}
    assert set(head.days) == {date(2017, 1, 1), date(2017, 1, 2)}


def test_two_quiet_days_below_min_files_never_propose() -> None:
    """Candidacy is gated on clusters, never on any-photo days -- research §4's load-bearing rule.

    Two days with one photo each are below `min_files`, so `cluster_camera` never proposes a
    cluster for either: they never become active days at all, regardless of what `all_items` says.
    """
    quiet_day_one, quiet_day_two = date(2023, 8, 20), date(2023, 8, 21)
    all_items = _items_on(quiet_day_one, 1) + _items_on(quiet_day_two, 1)

    result = detect_trips(all_items, clusters=[])

    assert result.proposals == []
    assert result.declines == []


def test_a_forty_day_run_declines_rather_than_splits() -> None:
    """Past the cap, decline outright -- a split would fabricate a boundary the data lacks."""
    days = [date(2018, 6, 3) + timedelta(days=i) for i in range(40)]
    clusters = [_candidate_on(d, 10) for d in days]
    all_items = [item for d in days for item in _items_on(d, 10)]

    result = detect_trips(all_items, clusters)

    assert result.proposals == []
    assert len(result.declines) == 1
    decline = result.declines[0]
    assert decline.start_date == days[0]
    assert decline.end_date == days[-1]
    assert decline.day_count == 40
    assert decline.reason is TripDeclineReason.MAX_SPAN


def test_a_bridged_interior_day_stays_inside_the_span_but_absent_from_days() -> None:
    """A photoless day one gap wide bridges; it is inside [start, end] but has no `days` entry."""
    active_start = date(2019, 5, 10)
    day_one, day_two, dead_day, day_four, day_five = (
        active_start + timedelta(days=i) for i in range(5)
    )
    clusters = [_candidate_on(day_one, 10), _candidate_on(day_two, 10)]
    clusters += [_candidate_on(day_four, 10), _candidate_on(day_five, 10)]
    all_items = _items_on(day_one, 10) + _items_on(day_two, 10)
    all_items += _items_on(day_four, 10) + _items_on(day_five, 10)

    result = detect_trips(all_items, clusters)  # default max_gap_days=1 bridges the dead day

    assert result.declines == []
    assert len(result.proposals) == 1
    trip = result.proposals[0]
    assert trip.start_date == day_one
    assert trip.end_date == day_five
    assert dead_day not in trip.days
    assert dict(trip.days) == {day_one: 10, day_two: 10, day_four: 10, day_five: 10}
