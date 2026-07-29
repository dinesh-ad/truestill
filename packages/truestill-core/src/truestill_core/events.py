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

Only clusters worth naming are proposed (enough files, spanning enough time); everything else
stays in the active scheme's un-evented timeline folder. A cluster's identity is the hash of its
sorted member SHA-256s, so a skip or a name is remembered across runs and re-proposed only if
the membership actually changes.
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

#: How far above the local baseline (in natural-log seconds) a gap must sit to be a boundary.
#:
#: ⚠ **This test no longer decides alone, and the reason is worth reading before changing it.**
#: On its own it is *relative to local density*, which inverts at both extremes: on a 654-photo
#: day the median gap is 7 seconds, so a 7-minute pause became a "boundary" and the day
#: shattered; in a sparse multi-year tail the median gap is 109 days, so nothing ever split and
#: 11 photos spanning 5.6 years became one "event". :data:`MIN_BOUNDARY_GAP_S` and
#: :data:`MAX_WITHIN_EVENT_GAP_S` bound it at each end.
#:
#: **Correction to the original tuning note**, which claimed 4.0 "keeps a multi-day trip whole".
#: That was true only of the synthetic fixtures it was tuned on, which have uniform intra-event
#: spacing -- the one condition under which a purely relative threshold behaves. It is false on
#: real data, and it is doubly false now: every overnight gap exceeds
#: :data:`MIN_BOUNDARY_GAP_S`, so **segmentation produces within-day clusters only**. Multi-day
#: trips are grouped explicitly, above this layer, rather than being hoped for here.
DEFAULT_SENSITIVITY = 4.0

#: A gap must be at least this long to be a boundary, however unusual it looks locally. A pause
#: shorter than a coffee break is not the end of an event. Swept against the real 2,238-file
#: library: with no floor a day breaks into 6-12 fragments; at 30 min still 6-7; at 60 min two
#: or three recognisable outings; at 90 min distinct morning and evening outings merge.
MIN_BOUNDARY_GAP_S = 60 * 60

#: A gap this long always ends an event, whatever the local baseline says. This is what stops
#: sparse data fusing -- it is the cap that removed the 5.6-year cluster. Deliberately on the
#: **gap**, never on a segment's span: capping span would chop a genuine two-week trip, whose
#: internal gaps are only hours. 48h lets an event survive one quiet day (travel, weather)
#: without splitting. Measured: floor alone still yields a 49,068-hour cluster; floor plus cap
#: caps the longest at 11.8h.
MAX_WITHIN_EVENT_GAP_S = 48 * 60 * 60
#: Half-width of the local-baseline window, in gaps.
DEFAULT_WINDOW = 10
#: A cluster is only proposed if it has at least this many files.
#:
#: This is the only size filter. A duration floor used to sit beside it and was removed: it made
#: a 45-minute birthday with 60 photos unofferable at any sensitivity, while doing nothing the
#: file count does not already do. `min_files` is the useful half.
DEFAULT_MIN_FILES = 8
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
    min_boundary_gap_s: float = MIN_BOUNDARY_GAP_S,
    max_within_event_gap_s: float = MAX_WITHIN_EVENT_GAP_S,
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
    for i, gap in enumerate(gaps):
        # Absolute cap first: a gap this long ends an event whatever the local baseline says.
        if gap > max_within_event_gap_s:
            boundaries.add(i)
            continue
        # Then the relative test, floored so a locally-unusual but short pause is not a break.
        if gap >= min_boundary_gap_s and _boundary_after(i, log_gaps, window, sensitivity):
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
