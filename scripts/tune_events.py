"""Sensitivity tuning aid for the event clusterer (not a test).

Run: uv run python scripts/tune_events.py

Builds representative synthetic timelines and prints how many clusters each sensitivity
yields, so the DEFAULT_SENSITIVITY in vaeon_core.events can be chosen from evidence rather
than guessed. The default (4.0) is the lowest value where a multi-day trip stays whole
while genuinely separate events still split.
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "packages/vaeon-core/src"))

from vaeon_core.events import EventItem, cluster_camera


def _day(base: datetime, n: int = 15, gap_min: int = 30) -> list[datetime]:
    return [base + timedelta(minutes=gap_min * i) for i in range(n)]


def _items(times: list[datetime]) -> list[EventItem]:
    return [EventItem(key=f"/p{i}", captured_at=t, sha256=f"s{i:04d}") for i, t in enumerate(times)]


def main() -> None:
    trip = (
        _day(datetime(2026, 6, 14, 9))
        + _day(datetime(2026, 6, 15, 9))
        + _day(datetime(2026, 6, 16, 9))
    )
    trip_plus = trip + _day(datetime(2026, 6, 25, 9), n=12, gap_min=20)
    two = _day(datetime(2026, 6, 14, 9), n=10, gap_min=20) + _day(
        datetime(2026, 6, 20, 9), n=10, gap_min=20
    )
    burst = _day(datetime(2026, 6, 14, 9), n=12, gap_min=20)

    print(f"{'sens':>5} {'trip=1':>8} {'trip+wed=2':>11} {'6d-apart=2':>11} {'burst=1':>8}")
    for s in (2.0, 3.0, 3.5, 4.0, 4.5, 5.0):
        row = [
            len(cluster_camera(_items(trip), sensitivity=s)),
            len(cluster_camera(_items(trip_plus), sensitivity=s)),
            len(cluster_camera(_items(two), sensitivity=s)),
            len(cluster_camera(_items(burst), sensitivity=s)),
        ]
        print(f"{s:>5} {row[0]:>8} {row[1]:>11} {row[2]:>11} {row[3]:>8}")


if __name__ == "__main__":
    main()
