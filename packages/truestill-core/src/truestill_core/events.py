"""Event detection for Camera photos (opt-in, review-based).

Camera files are clustered into *events* by capture time so a human can name a trip or an
occasion. The machine only proposes boundaries; naming is always human (no algorithm knows
it was "Jack's wedding").

Method -- adaptive temporal-gap clustering, the technique photo apps use:

* Sort by capture time; take the gap between consecutive photos.
* Work in log space, so a 2-second burst at a wedding and hour-long lulls on a trip are
  comparable with one sensitivity knob rather than a fixed hour threshold.
* A boundary sits where a gap's log greatly exceeds the *local* baseline (the median of a
  window of surrounding gaps) -- i.e. this gap is unusual for right here, not globally.
* A large GPS jump between neighbours is additional boundary evidence; absent GPS changes
  nothing.

Only clusters worth naming are proposed (enough files, spanning enough time); everything
else stays flat in ``<Label>/YYYY/MM/``. A cluster's identity is the hash of its sorted
member SHA-256s, so a skip or a name is remembered across runs and re-proposed only if the
membership actually changes.
"""

from __future__ import annotations

import hashlib
import math
import re
import statistics
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

# --- tunables (defaults chosen empirically; see scripts/tune_events.py) ----------------

#: How far above the local baseline (in natural-log seconds) a gap must sit to be a
#: boundary. Tuned on synthetic scenarios (scripts/tune_events.py): 4.0 is the lowest value
#: that keeps a multi-day trip whole (overnight gaps do not split it) while still splitting
#: genuinely separate events days apart. Lower values fragment trips into per-day pieces.
DEFAULT_SENSITIVITY = 4.0
#: Half-width of the local-baseline window, in gaps.
DEFAULT_WINDOW = 10
#: A cluster is only proposed if it has at least this many files ...
DEFAULT_MIN_FILES = 8
#: ... spanning at least this long.
DEFAULT_MIN_DURATION_S = 2 * 3600
#: A neighbour-to-neighbour GPS jump beyond this many km reinforces a boundary. Kept large
#: so movement *within* an outing does not shatter it; only real relocations count.
DEFAULT_GPS_JUMP_KM = 50.0

GeoPoint = tuple[float, float]


@dataclass(frozen=True, slots=True)
class EventItem:
    """One Camera file's inputs to clustering. ``key`` is an opaque stable identity."""

    key: str
    captured_at: datetime
    sha256: str
    gps: GeoPoint | None = None


@dataclass(frozen=True, slots=True)
class EventCandidate:
    """A proposed event: its members, in capture order."""

    items: tuple[EventItem, ...]

    @property
    def start(self) -> datetime:
        return self.items[0].captured_at

    @property
    def end(self) -> datetime:
        return self.items[-1].captured_at

    @property
    def count(self) -> int:
        return len(self.items)

    @property
    def signature(self) -> str:
        """Stable identity: SHA-256 over the sorted member SHA-256s."""
        joined = "\n".join(sorted(item.sha256 for item in self.items))
        return hashlib.sha256(joined.encode("utf-8")).hexdigest()

    def gps_centroid(self) -> GeoPoint | None:
        points = [item.gps for item in self.items if item.gps is not None]
        if not points:
            return None
        return (
            statistics.fmean(p[0] for p in points),
            statistics.fmean(p[1] for p in points),
        )


def haversine_km(a: GeoPoint, b: GeoPoint) -> float:
    """Great-circle distance between two ``(lat, lon)`` points, in kilometres."""
    radius = 6371.0088
    lat1, lon1, lat2, lon2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(h))


def _boundary_after(index: int, log_gaps: list[float], window: int, sensitivity: float) -> bool:
    lo = max(0, index - window)
    hi = min(len(log_gaps), index + window + 1)
    neighbours = [log_gaps[j] for j in range(lo, hi) if j != index]
    if not neighbours:
        return False
    return log_gaps[index] - statistics.median(neighbours) > sensitivity


def cluster_camera(
    items: Sequence[EventItem],
    *,
    sensitivity: float = DEFAULT_SENSITIVITY,
    window: int = DEFAULT_WINDOW,
    min_files: int = DEFAULT_MIN_FILES,
    min_duration_s: float = DEFAULT_MIN_DURATION_S,
    gps_jump_km: float = DEFAULT_GPS_JUMP_KM,
) -> list[EventCandidate]:
    """Return proposed events, largest-first. Items need not be pre-sorted."""
    ordered = sorted(items, key=lambda it: it.captured_at)
    if len(ordered) < min_files:
        return []

    gaps = [
        (ordered[i + 1].captured_at - ordered[i].captured_at).total_seconds()
        for i in range(len(ordered) - 1)
    ]
    log_gaps = [math.log1p(max(0.0, g)) for g in gaps]

    boundaries: set[int] = set()
    for i in range(len(gaps)):
        if _boundary_after(i, log_gaps, window, sensitivity):
            boundaries.add(i)
        here, nxt = ordered[i].gps, ordered[i + 1].gps
        if here is not None and nxt is not None and haversine_km(here, nxt) > gps_jump_km:
            boundaries.add(i)

    candidates: list[EventCandidate] = []
    segment_start = 0
    for i in range(len(ordered)):
        is_last = i == len(ordered) - 1
        if is_last or i in boundaries:
            segment = ordered[segment_start : i + 1]
            segment_start = i + 1
            if len(segment) >= min_files:
                span = (segment[-1].captured_at - segment[0].captured_at).total_seconds()
                if span >= min_duration_s:
                    candidates.append(EventCandidate(items=tuple(segment)))

    candidates.sort(key=lambda c: c.count, reverse=True)
    return candidates


# --- naming / placement ----------------------------------------------------------------

_SLUG_STRIP = re.compile(r"[^a-z0-9]+")
_MAX_SLUG_LEN = 48


def slugify(name: str) -> str:
    """Turn a human event name into a filesystem-safe slug (``Goa Trip!`` -> ``goa-trip``)."""
    slug = _SLUG_STRIP.sub("-", name.strip().casefold()).strip("-")
    return slug[:_MAX_SLUG_LEN].strip("-")


def event_dirname(start: datetime, slug: str) -> str:
    """Event folder name, date-prefixed so folders sort chronologically: ``YYYYMMDD_slug``."""
    return f"{start:%Y%m%d}_{slug}"


# --- interactive reshaping (merge / split), used by the review UI --------------------


def merge_candidates(candidates: Sequence[EventCandidate]) -> EventCandidate:
    """Combine several proposed clusters into one (members unioned, re-sorted by time)."""
    items = sorted(
        (item for candidate in candidates for item in candidate.items),
        key=lambda item: item.captured_at,
    )
    return EventCandidate(items=tuple(items))


def split_candidate(candidate: EventCandidate, index: int) -> tuple[EventCandidate, EventCandidate]:
    """Split a cluster into two at ``index`` (1 <= index < count), preserving capture order."""
    if not 1 <= index < candidate.count:
        message = f"split index {index} out of range for a {candidate.count}-file cluster"
        raise ValueError(message)
    ordered = sorted(candidate.items, key=lambda item: item.captured_at)
    return EventCandidate(items=tuple(ordered[:index])), EventCandidate(
        items=tuple(ordered[index:])
    )
