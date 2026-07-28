"""Trip detection: grouping consecutive active days into multi-day trips.

Pure detection only -- Stage 2b of `trip-grouping-research.md`. No schema, no `trips`/`trip_days`
tables, no layout template, no file placement, no migration; those are Stages 2c-2e.

A **sibling module to `events.py`, not an addition to it.** `events.py`'s own docstring scopes it
to within-day clustering, and by construction every overnight gap in the tuned thresholds exceeds
`MIN_BOUNDARY_GAP_S` -- a cluster never spans midnight on real data (see its `DEFAULT_SENSITIVITY`
docstring). A trip is a second, explicit layer above that: a named span of *days*, built from
which calendar days produced a cluster at all, never from loosening the within-day rule.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from itertools import pairwise

from truestill_core.events import EventCandidate, EventItem

#: A run of fewer than this many active days is a day event, not a trip.
_MIN_TRIP_DAYS = 2

#: Default cap on a trip's total span, in calendar days. Chosen on principle -- long enough for
#: any real holiday, short enough that a habitual daily shooter never trips it -- rather than
#: fitted: the real library's longest active-day run is 4 days, so this default is unvalidated by
#: measurement. See `trip-grouping-research.md` §3f.
DEFAULT_MAX_SPAN_DAYS = 30

#: Default tolerance for a photoless day inside an otherwise-active run -- a single dead day (a
#: travel day, a rained-out day) does not end a trip. Chosen on principle and literature
#: consensus (trip-mining prior art bridges small gaps to keep a multi-day trip whole); also
#: unvalidated here, since the one real multi-day run in this library has no interior gap to
#: measure against. See `trip-grouping-research.md`'s "Built" note.
DEFAULT_MAX_GAP_DAYS = 1


class TripDeclineReason(StrEnum):
    """Why a candidate run was not proposed as a trip. Today, exactly one reason exists."""

    MAX_SPAN = "max_span"


@dataclass(frozen=True, slots=True)
class TripProposal:
    """A candidate trip: a consecutive run of active days, with per-day photo counts.

    ``days`` holds only the *active* days in ``[start_date, end_date]``. A bridged interior day
    with zero photos (see ``max_gap_days`` on `detect_trips`) sits inside the span but has **no
    entry** here -- that absence is the signal a renderer uses to know a day was bridged, not
    dated. Each count is every photo taken that day (cluster members and stragglers together,
    never just the cluster sum) -- see `trip-grouping-research.md` §2's day-claim rule.
    """

    start_date: date
    end_date: date
    days: Mapping[date, int]


@dataclass(frozen=True, slots=True)
class TripDecline:
    """A candidate run considered and not proposed, and why.

    Carries no human-readable message -- composing one (naming the run length and the setting
    that governs it, per `trip-grouping-research.md` §3f) is a rendering concern for the stage
    that displays proposals, not a detection concern.
    """

    start_date: date
    end_date: date
    day_count: int
    reason: TripDeclineReason


@dataclass(frozen=True, slots=True)
class TripDetectionResult:
    """Everything `detect_trips` found: proposals to offer, and runs it declined to propose."""

    proposals: list[TripProposal]
    declines: list[TripDecline]


def _split_at_year_boundary(run: Sequence[date]) -> list[list[date]]:
    """Break a sorted run of active days at every calendar-year change.

    Structural, not optional (`IMPLEMENTATION_STANDARDS.md` R2: nothing is filed outside its own
    year). Groups consecutive same-year days together, so a run spanning more than two years (not
    reachable under any sane ``max_span_days``, but not assumed away either) splits correctly into
    one piece per year rather than just two.
    """
    pieces: list[list[date]] = []
    current: list[date] = []
    for day in run:
        if current and day.year != current[-1].year:
            pieces.append(current)
            current = []
        current.append(day)
    if current:
        pieces.append(current)
    return pieces


def detect_trips(
    all_items: Sequence[EventItem],
    clusters: Sequence[EventCandidate],
    *,
    max_span_days: int = DEFAULT_MAX_SPAN_DAYS,
    max_gap_days: int = DEFAULT_MAX_GAP_DAYS,
) -> TripDetectionResult:
    """Group consecutive active days into candidate trips. Pure -- no I/O, nothing re-read.

    An **active day** is a calendar date that produced at least one entry in ``clusters`` (the
    Stage 1 rule) -- never a date with photos alone. That is what stops a two-day, two-photo run
    of stragglers from ever proposing a trip: see `trip-grouping-research.md` §4.

    ``all_items`` supplies the *count* for each active day -- every photo taken that day, cluster
    members and stragglers together -- and only that. It is never consulted for gating: a day
    with entries in ``all_items`` but no cluster in ``clusters`` cannot start, join, or bridge a
    run. (``clusters`` alone cannot supply this count: `cluster_camera` silently drops any segment
    under ``min_files``, so the members of an under-threshold segment are not recoverable from its
    output. ``all_items`` is the same population the clusters were built from, held by the caller
    before it calls `cluster_camera` -- see `event_review.gather_camera_items` and
    `event_review.propose_from_catalog`.)

    A run of active days bridges a gap of up to ``max_gap_days`` calendar days with zero photos; a
    bridged day sits inside the trip's span but has no entry in `TripProposal.days`. A run
    crossing a year boundary is always split into one piece per year before anything else is
    evaluated, including the span cap, so a trip is never fabricated across a boundary that does
    not move. **A known, narrow consequence**: a two-day active run that straddles exactly one
    year boundary (e.g. Dec 31 + Jan 1, with nothing else nearby) splits into two one-day pieces
    and yields neither a proposal nor a decline -- the faithful composition of "always split at
    the year" and "a single day is never a trip", not a bug in either rule alone.

    A surviving run whose active-day span exceeds ``max_span_days`` is declined, not split and not
    trimmed: inventing a boundary the data does not contain is the same error as a fabricated
    date. A run of a single active day is never a trip and produces neither a proposal nor a
    decline; it is left for the day-event layer.

    **Edge case flagged, not solved here**: a cluster is assumed to fall entirely within one
    calendar day, per `events.py`'s stated (empirical, not structurally enforced) invariant. A
    cluster whose members straddle midnight without a qualifying gap -- possible in principle,
    unobserved on the real library -- contributes only its first member's date as active; the rest
    of its span is not separately accounted for. Not exercised by any fixture here.

    Complexity: **O(N) to total ``all_items`` by date** (unavoidable -- it is the only source of
    the straggler count) **+ O(D log D) to sort the distinct active-day set + O(D)** for the run
    scan, the year split and the span check, where ``D`` is the number of active days and
    ``N = len(all_items)``. Neither sequence is walked more than once; there is no pass nested
    inside another.
    """
    active_days: set[date] = {cluster.start.date() for cluster in clusters}
    if not active_days:
        return TripDetectionResult(proposals=[], declines=[])

    day_counts: dict[date, int] = {}
    for item in all_items:
        day = item.captured_at.date()
        if day in active_days:
            day_counts[day] = day_counts.get(day, 0) + 1

    ordered_days = sorted(active_days)

    runs: list[list[date]] = []
    current_run = [ordered_days[0]]
    for previous, day in pairwise(ordered_days):
        dead_days = (day - previous).days - 1
        if dead_days <= max_gap_days:
            current_run.append(day)
        else:
            runs.append(current_run)
            current_run = [day]
    runs.append(current_run)

    proposals: list[TripProposal] = []
    declines: list[TripDecline] = []

    for run in runs:
        if len(run) < _MIN_TRIP_DAYS:
            continue
        for piece in _split_at_year_boundary(run):
            if len(piece) < _MIN_TRIP_DAYS:
                continue
            start, end = piece[0], piece[-1]
            span_days = (end - start).days + 1
            if span_days > max_span_days:
                declines.append(
                    TripDecline(
                        start_date=start,
                        end_date=end,
                        day_count=len(piece),
                        reason=TripDeclineReason.MAX_SPAN,
                    )
                )
                continue
            proposals.append(
                TripProposal(
                    start_date=start,
                    end_date=end,
                    days={day: day_counts[day] for day in piece},
                )
            )

    return TripDetectionResult(proposals=proposals, declines=declines)
