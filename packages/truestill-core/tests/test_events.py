"""Event clustering: temporal-gap detection, GPS reinforcement, and placement."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from truestill_core.events import (
    EventItem,
    cluster_camera,
    event_dirname,
    haversine_km,
    merge_candidates,
    slugify,
    split_candidate,
)

# Naive datetimes are the domain (EXIF wall-clock).


def _items(
    base: datetime, offsets_s: list[float], *, gps: tuple[float, float] | None = None
) -> list[EventItem]:
    items = []
    for i, off in enumerate(offsets_s):
        when = base + timedelta(seconds=off)
        items.append(EventItem(key=f"/p{i}", captured_at=when, sha256=f"sha{i:04d}", gps=gps))
    return items


def _burst(base: datetime, n: int, *, gps: tuple[float, float] | None = None) -> list[EventItem]:
    """n photos, ~30s apart (spanning > 2h for n>=8 only if spacing large enough)."""
    return _items(base, [i * 1200 for i in range(n)], gps=gps)  # 20 min apart -> spans hours


def test_single_burst_is_one_event() -> None:
    items = _burst(datetime(2026, 6, 14, 9, 0, 0), 12)  # 12 photos over ~3.6h
    clusters = cluster_camera(items)
    assert len(clusters) == 1
    assert clusters[0].count == 12


def test_two_events_separated_by_a_large_gap() -> None:
    day1 = _burst(datetime(2026, 6, 14, 9, 0, 0), 10)
    day2 = _burst(datetime(2026, 6, 20, 9, 0, 0), 10)  # 6 days later
    clusters = cluster_camera(day1 + day2)
    assert len(clusters) == 2
    assert all(c.count == 10 for c in clusters)


def _trip_day(base: datetime, n: int = 15, gap_min: int = 30) -> list[datetime]:
    return [base + timedelta(minutes=gap_min * i) for i in range(n)]


def test_multi_day_trip_stays_one_event() -> None:
    """A 3-day trip with overnight gaps is a single event, not three per-day fragments."""
    times = (
        _trip_day(datetime(2026, 6, 14, 9))
        + _trip_day(datetime(2026, 6, 15, 9))
        + _trip_day(datetime(2026, 6, 16, 9))
    )
    items = [
        EventItem(key=f"/t{i}", captured_at=t, sha256=f"t{i:04d}") for i, t in enumerate(times)
    ]
    clusters = cluster_camera(items)
    assert len(clusters) == 1
    assert clusters[0].count == 45


def test_sub_threshold_group_is_not_proposed() -> None:
    items = _burst(datetime(2026, 6, 14, 9, 0, 0), 5)  # only 5 files -> below min_files
    assert cluster_camera(items) == []


def test_a_short_but_real_event_is_proposed() -> None:
    """The inverse of the filter this replaces: brevity is not evidence of unimportance.

    A duration floor used to reject this. A 45-minute birthday with 60 photos is a real event,
    and was unofferable at any sensitivity; `min_files` is the size filter that does useful work.
    """
    items = _items(datetime(2026, 6, 14, 9, 0, 0), [i * 60 for i in range(10)])  # 10 files, 9 min
    proposed = cluster_camera(items)
    assert len(proposed) == 1
    assert proposed[0].count == 10


def test_gps_jump_reinforces_a_boundary() -> None:
    """Two same-day bursts with no big time gap, but a large location jump between them."""
    home = (12.9716, 77.5946)  # Bangalore
    away = (15.2993, 74.1240)  # Goa, ~460 km
    first = [
        EventItem(
            key=f"/a{i}",
            captured_at=datetime(2026, 6, 14, 9, 0) + timedelta(minutes=20 * i),
            sha256=f"a{i}",
            gps=home,
        )
        for i in range(9)
    ]
    # continues right after in time, but far away
    last_t = first[-1].captured_at + timedelta(minutes=20)
    second = [
        EventItem(
            key=f"/b{i}", captured_at=last_t + timedelta(minutes=20 * i), sha256=f"b{i}", gps=away
        )
        for i in range(9)
    ]
    clusters = cluster_camera(first + second, gps_jump_km=50.0)
    assert len(clusters) == 2


def test_signature_is_stable_and_membership_sensitive() -> None:
    base = datetime(2026, 6, 14, 9, 0, 0)
    a = cluster_camera(_burst(base, 10))[0]
    b = cluster_camera(_burst(base, 10))[0]
    assert a.signature == b.signature  # same members -> same signature
    c = cluster_camera(_burst(base, 11))[0]
    assert c.signature != a.signature  # one more member -> re-proposed


def test_haversine_known_distance() -> None:
    # Bangalore -> Goa is roughly 460 km; allow a wide tolerance.
    assert 400 < haversine_km((12.9716, 77.5946), (15.2993, 74.1240)) < 520


def test_slugify() -> None:
    assert slugify("Goa Trip!") == "goa-trip"
    assert slugify("  Jack's  Wedding  ") == "jack-s-wedding"
    assert slugify("2026 Reunion") == "2026-reunion"
    assert len(slugify("x" * 100)) <= 48


def test_event_dirname_is_date_prefixed() -> None:
    assert event_dirname(datetime(2026, 6, 14, 9, 0, 0), "goa-trip") == "20260614_goa-trip"


def test_merge_candidates_unions_and_sorts() -> None:
    a = cluster_camera(_burst(datetime(2026, 6, 14, 9, 0, 0), 10))[0]
    b = cluster_camera(_burst(datetime(2026, 6, 20, 9, 0, 0), 10))[0]
    merged = merge_candidates([a, b])
    assert merged.count == 20
    times = [it.captured_at for it in merged.items]
    assert times == sorted(times)  # re-sorted across both


def test_split_candidate_partitions_in_order() -> None:
    cluster = cluster_camera(_burst(datetime(2026, 6, 14, 9, 0, 0), 10))[0]
    first, second = split_candidate(cluster, 4)
    assert (first.count, second.count) == (4, 6)
    assert first.items[-1].captured_at <= second.items[0].captured_at


def test_split_out_of_range_raises() -> None:
    cluster = cluster_camera(_burst(datetime(2026, 6, 14, 9, 0, 0), 10))[0]
    with pytest.raises(ValueError, match="out of range"):
        split_candidate(cluster, 0)


# --- regression: density profiles taken from the real library ------------------------------
#
# The previous rule passed every synthetic fixture while being inverted on real data, because
# the fixtures had uniform intra-event spacing -- the one condition under which a purely
# relative threshold behaves. These fixtures reproduce the DENSITY PROFILES that broke it:
# a burst-shot day (median gap ~7-10s over 15-20 hours) and a sparse multi-year tail (median
# gap ~109 days). They assert shape, not counts, so they survive tuning.


def _dense_day(day: datetime, count: int, *, seconds_apart: int = 8) -> list[EventItem]:
    """A burst-shot day with the real thing's density VARIATION, not a metronome.

    Uniform spacing is exactly what let the old rule pass every synthetic fixture: with no
    locally-unusual gap there is nothing for a relative threshold to cut on. Real burst days
    pause every so often -- changing lens, walking to the next place -- and those few-minute
    pauses are what the old rule mistook for boundaries. Every twentieth frame is a 10-minute
    one -- chosen because against an 8-second median it clears the old relative threshold
    (ln 600 - ln 8 = 4.3 > 4.0) and so genuinely reproduces the shattering, while sitting well
    under the 60-minute floor that now prevents it.
    """
    offsets, t = [], 0
    for i in range(count):
        offsets.append(t)
        t += 10 * 60 if i and i % 20 == 0 else seconds_apart
    return _items(day, offsets)


def test_a_burst_shot_day_is_not_shattered_into_fragments() -> None:
    """The failure that shipped: a 7-second median gap made a 7-minute pause a 'boundary'.

    The day broke into a dozen pieces, almost all of which then died to a duration filter, so a
    654-photo day produced no proposal at all.
    """
    items = _dense_day(datetime(2014, 8, 17, 6, 30), 650)

    proposed = cluster_camera(items)

    assert len(proposed) == 1, f"a steadily-shot day should be one event, got {len(proposed)}"
    assert proposed[0].count == 650


def test_a_sparse_multi_year_tail_is_never_one_event() -> None:
    """The other half of the inversion: where the median gap is months, nothing ever split.

    11 photos spanning 5.6 years were proposed as a single 'event'. The absolute cap is what
    makes that impossible, and it is asserted on the span rather than on a count so it cannot
    pass by accident.
    """
    base = datetime(2018, 8, 19, 12, 0)
    items = _items(base, [i * 109 * 86400 for i in range(11)])  # ~109 days apart, as measured

    proposed = cluster_camera(items)

    for candidate in proposed:
        span_days = (
            candidate.items[-1].captured_at - candidate.items[0].captured_at
        ).total_seconds() / 86400
        assert span_days <= 2, f"a {span_days:.0f}-day span is not one event"


def test_a_pause_shorter_than_the_floor_never_splits_a_day() -> None:
    """The floor, stated as behaviour: a coffee break is not the end of an event."""
    morning = _dense_day(datetime(2014, 8, 15, 9, 0), 300)
    after_a_short_pause = _items(datetime(2014, 8, 15, 10, 20), [i * 8 for i in range(300)])

    proposed = cluster_camera([*morning, *after_a_short_pause])

    assert len(proposed) == 1  # a 20-minute pause is inside the day, not a boundary


def test_an_overnight_gap_always_splits() -> None:
    """The accepted consequence: segmentation now yields WITHIN-DAY clusters only.

    Every overnight gap exceeds the floor, so multi-day trips are no longer discovered here.
    That is deliberate -- they are grouped explicitly, above this layer -- and it is pinned so
    the behaviour is a decision rather than a surprise.
    """
    day_one = _dense_day(datetime(2014, 8, 15, 9, 0), 100)
    day_two = _dense_day(datetime(2014, 8, 16, 9, 0), 100)

    proposed = cluster_camera([*day_one, *day_two])

    assert len(proposed) == 2
    assert {c.items[0].captured_at.date().day for c in proposed} == {15, 16}
