"""Event clustering: temporal-gap detection, GPS reinforcement, and placement."""

from __future__ import annotations

from datetime import datetime, timedelta

from vaeon_core.events import (
    EventItem,
    cluster_camera,
    event_dirname,
    haversine_km,
    slugify,
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


def test_short_group_below_min_duration_is_not_proposed() -> None:
    items = _items(datetime(2026, 6, 14, 9, 0, 0), [i * 60 for i in range(10)])  # 10 files, 9 min
    assert cluster_camera(items) == []


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
