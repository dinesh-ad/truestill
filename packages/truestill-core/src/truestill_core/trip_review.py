"""Trip-review orchestration: the detection-to-persistence join (Stage 2d, sub-stage 13.1).

Mirrors ``event_review.py``'s already-organized-drive path one layer up:
:func:`propose_trips_from_catalog` clusters what the catalog already knows and runs
:func:`truestill_core.trips.detect_trips` (Stage 2b, pure) over it; :func:`commit_trips` persists
reviewed decisions through the Stage 2c CRUD (``create_trip`` / ``update_trip_days`` /
``trip_for_day``). Catalog-only: no layout, no ``Placement``, no rendering, no file relocation --
see ``docs/trip-grouping-research.md`` §13.1.

Naming is the one thing only a human can do (``event_review.py``'s own words); this module never
invents or derives one. A :class:`TripDecision` carries whatever name a reviewer gave, or ``None``
to decline -- exactly :class:`truestill_core.event_review.EventDecision`'s shape, one layer up.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import Final, Literal

from truestill_core.catalog import Catalog
from truestill_core.events import (
    DEFAULT_MIN_FILES,
    EventCandidate,
    EventItem,
    cluster_camera,
    slugify,
)
from truestill_core.trips import (
    DEFAULT_MAX_GAP_DAYS,
    DEFAULT_MAX_SPAN_DAYS,
    TripDecline,
    TripDetectionResult,
    TripProposal,
    detect_trips,
)

#: The same floor `trips._MIN_TRIP_DAYS` uses for detection, restated here for the display
#: label: a trip manually split down to one day is still labelled "event" (`ReviewCard.kind`),
#: exactly as detection itself never proposes a 1-day trip from scratch.
_MIN_TRIP_DAYS_FOR_LABEL = 2
#: "Small" means threshold-adjacent: below the first doubling of the configured inclusion floor
#: (`count < 2 * min_files`; detected events already meet the floor, while a manual split may
#: create a smaller half). Unlike a fixed photo count, this scales with the user's chosen
#: sensitivity without hiding the 23-photo secondary-survey claim discussed in Stage 3. Only
#: standalone event candidates are eligible; trips never are.
_SMALL_EVENT_FACTOR: Final[int] = 2


def _parse_dt(value: object) -> datetime:
    return datetime.fromisoformat(str(value))


def _camera_items(catalog: Catalog, drive_uuid: str) -> list[EventItem]:
    """The dated Camera copies on a drive, as clustering input. Shared by every proposer here."""
    return [
        EventItem(
            key=str(row["sha256"]),
            captured_at=_parse_dt(row["captured_at"]),
            sha256=str(row["sha256"]),
        )
        for row in catalog.camera_copies_for_events(drive_uuid)
    ]


def propose_trips_from_catalog(
    catalog: Catalog,
    drive_uuid: str,
    *,
    min_files: int = DEFAULT_MIN_FILES,
    max_span_days: int = DEFAULT_MAX_SPAN_DAYS,
    max_gap_days: int = DEFAULT_MAX_GAP_DAYS,
) -> TripDetectionResult:
    """Propose trips from an already-organized drive's dated camera copies (no source re-read).

    Mirrors :func:`truestill_core.event_review.propose_from_catalog`: the same catalog rows
    (:meth:`Catalog.camera_copies_for_events`), the same Stage-1 clusters
    (:func:`truestill_core.events.cluster_camera`), one layer up. Declines travel with the
    proposals in the returned :class:`TripDetectionResult` -- a caller decides what to show for
    them; this function never drops or explains them itself.

    Pure with respect to the catalog: reads rows, writes nothing.
    """
    items = _camera_items(catalog, drive_uuid)
    clusters = cluster_camera(items, min_files=min_files)
    return detect_trips(items, clusters, max_span_days=max_span_days, max_gap_days=max_gap_days)


@dataclass(frozen=True, slots=True)
class ReviewCard:
    """One assembled review card (Stage 2d, 13.3b): a multi-day TRIP or a standalone-day EVENT.

    Exactly one of ``trip``/``event`` is set. A standalone day keeps its **original**
    cluster-only membership -- never the whole day's total, stragglers included -- so backlog
    ``(ll)``'s day-event identity (a signature over member SHA-256s) is untouched by this stage;
    only a genuine multi-day trip claims a whole day (§2). ``kind`` is a **display label**, not
    the persistence mechanism: it reads by day count, because a trip manually split all the way
    down to one day (see :func:`split_trip`) is still a `TripProposal` under the hood -- confirmed
    through :func:`truestill_core.trip_review.commit_trips` like any other trip -- even though it
    is *labelled* "event" for the same reason detection never proposes a 1-day trip.
    """

    trip: TripProposal | None = None
    event: EventCandidate | None = None

    def __post_init__(self) -> None:
        if (self.trip is None) == (self.event is None):
            message = "a review card must carry exactly one of trip or event"
            raise ValueError(message)

    @property
    def kind(self) -> Literal["trip", "event"]:
        is_multi_day = self.trip is not None and len(self.trip.days) >= _MIN_TRIP_DAYS_FOR_LABEL
        return "trip" if is_multi_day else "event"

    @property
    def start(self) -> date:
        return self.trip.start_date if self.trip is not None else self.event.start.date()  # type: ignore[union-attr]

    @property
    def end(self) -> date:
        return self.trip.end_date if self.trip is not None else self.event.end.date()  # type: ignore[union-attr]

    @property
    def count(self) -> int:
        if self.trip is not None:
            return sum(self.trip.days.values())
        assert self.event is not None
        return self.event.count


def small_event_limit(min_files: int) -> int:
    """Exclusive upper bound for threshold-adjacent event groups (one doubling of the floor)."""
    return min_files * _SMALL_EVENT_FACTOR


def is_small_event(card: ReviewCard, min_files: int) -> bool:
    """Whether this standalone event belongs behind the one summary disclosure."""
    return card.event is not None and card.count < small_event_limit(min_files)


def order_review_cards(cards: Sequence[ReviewCard]) -> list[ReviewCard]:
    """Return proposals largest-first; sorting card count is the only ordering work."""
    return sorted(cards, key=lambda card: card.count, reverse=True)


def collapsed_event_cards(cards: Sequence[ReviewCard], min_files: int) -> list[ReviewCard]:
    """The exact floor-near standalone events hidden by default; trips are ineligible."""
    return [card for card in cards if is_small_event(card, min_files)]


@dataclass(frozen=True, slots=True)
class TripReview:
    """Everything :func:`assemble_trip_review` found: cards to show, declines to explain."""

    cards: list[ReviewCard]
    declines: list[TripDecline]
    day_totals: dict[date, int]


def assemble_trip_review(
    catalog: Catalog,
    drive_uuid: str,
    *,
    min_files: int = DEFAULT_MIN_FILES,
    max_span_days: int = DEFAULT_MAX_SPAN_DAYS,
    max_gap_days: int = DEFAULT_MAX_GAP_DAYS,
) -> TripReview:
    """The 13.3b inversion: a genuine multi-day run assembles into ONE card; a standalone active
    day still renders as its own (unchanged) day-event card.

    Before this, every Stage-1 cluster rendered as its own card regardless of whether it was
    part of a longer run, and a user reassembled a trip by hand with a merge checkbox -
    reassembling what `detect_trips` already knows. Here, detection runs first and its
    multi-day proposals are rendered whole; only the clusters *outside* every proposal's claimed
    days still render individually, exactly as they always did.

    One pass over one query feeds both `detect_trips` (2b, unchanged) and the standalone-day
    clusters, so this costs no extra I/O over calling `propose_trips_from_catalog` alone.
    """
    items = _camera_items(catalog, drive_uuid)
    clusters = cluster_camera(items, min_files=min_files)
    result = detect_trips(items, clusters, max_span_days=max_span_days, max_gap_days=max_gap_days)
    claimed_days = {day for trip in result.proposals for day in trip.days}
    cards = [ReviewCard(trip=trip) for trip in result.proposals]
    cards.extend(
        ReviewCard(event=cluster)
        for cluster in clusters
        if cluster.start.date() not in claimed_days
    )
    cards = order_review_cards(cards)
    day_totals: dict[date, int] = {}
    for item in items:
        day = item.captured_at.date()
        day_totals[day] = day_totals.get(day, 0) + 1
    return TripReview(cards=cards, declines=result.declines, day_totals=day_totals)


class TripMergeError(ValueError):
    """A manual merge would violate a locked layout rule (§3e year boundary, §3f max span)."""


def merge_review_cards(
    cards: Sequence[ReviewCard],
    day_totals: Mapping[date, int],
    *,
    max_span_days: int = DEFAULT_MAX_SPAN_DAYS,
) -> TripProposal:
    """Combine two or more reviewed cards the detector did **not** join into one trip, or refuse.

    The secondary control (§10/13.3b): split is the primary adjustment (breaking a wrongly-joined
    run), merge is for the gap case - two runs a few days apart the user considers one trip.

    Once any of these days joins a multi-day trip, every photo taken on it belongs to the trip
    (§2) - so each day's contribution is always its **full** total (``day_totals``), never a
    solo event's partial cluster count. This is why a merge can change what a standalone day
    *means* even though it does not touch a single file.

    Refuses rather than silently producing an un-renderable or over-cap trip - the two locked
    rules a manual merge must obey exactly like detection does:

    - **§3e, year boundary**: `_split_at_year_boundary` guarantees no *detected* proposal ever
      crosses a year, because the layout has no way to express a trip folder spanning two year
      parents. A manual merge could otherwise defeat that guarantee, so it is checked again here.
    - **§3f, max span**: merging past `max_span_days` is declined, in the same words detection's
      own decline message uses, never silently split or truncated.
    """
    claimed: dict[date, int] = {}
    for card in cards:
        if card.trip is not None:
            for day, count in card.trip.days.items():
                claimed[day] = day_totals.get(day, count)
        else:
            assert card.event is not None
            day = card.event.start.date()
            claimed[day] = day_totals.get(day, card.event.count)

    start, end = min(claimed), max(claimed)
    if start.year != end.year:
        message = (
            f"These runs span {start.year} and {end.year} - a trip cannot cross a year boundary "
            "(trip-grouping-research.md §3e). Confirm them as separate trips instead."
        )
        raise TripMergeError(message)

    span = (end - start).days + 1
    if span > max_span_days:
        message = (
            f"{span} consecutive days of photos ({start.isoformat()} to {end.isoformat()}) - too "
            f"long to propose as one trip. Raise trips.max_span_days (currently {max_span_days}) "
            "if this really was one trip."
        )
        raise TripMergeError(message)

    return TripProposal(start_date=start, end_date=end, days=claimed)


def decline_message(decline: TripDecline, *, max_span_days: int = DEFAULT_MAX_SPAN_DAYS) -> str:
    """The §3f message, composed here rather than in detection: name the run length and the
    setting that governs it, never fold a decline into silence.

    `TripDecline` deliberately carries no message of its own (§12: "composing one is a
    rendering concern for the stage that displays proposals, not a detection concern") - this
    is that stage.
    """
    return (
        f"{decline.day_count} consecutive days of photos ({decline.start_date.isoformat()} to "
        f"{decline.end_date.isoformat()}) - too long to propose as one trip. Raise "
        f"trips.max_span_days (currently {max_span_days}) if this really was one trip."
    )


def split_trip(proposal: TripProposal, after_day: date) -> tuple[TripProposal, TripProposal]:
    """Split a trip into two at a day boundary - the direct inverse of :func:`merge_review_cards`.

    ``after_day`` must be one of the trip's own claimed days, and not its last. A 2-day trip (the
    smallest a proposal can be) splits into two 1-day pieces - each still a `TripProposal`, even
    though a day that small is *labelled* "event" (:attr:`ReviewCard.kind`) and detection itself
    never proposes one from scratch (`trips._MIN_TRIP_DAYS`). That is a deliberate, narrow
    difference between what detection proposes and what a manual split may produce, not an
    oversight - flagged here rather than reconciled, since building a bridge back to a genuine
    cluster-based `EventCandidate` would need member items this function was never given.
    """
    ordered = sorted(proposal.days)
    too_short = len(ordered) < _MIN_TRIP_DAYS_FOR_LABEL
    if too_short or after_day not in ordered or after_day == ordered[-1]:
        message = f"{after_day.isoformat()} is not a valid split point for this trip"
        raise ValueError(message)
    idx = ordered.index(after_day)
    first_days = {d: proposal.days[d] for d in ordered[: idx + 1]}
    second_days = {d: proposal.days[d] for d in ordered[idx + 1 :]}
    return (
        TripProposal(start_date=min(first_days), end_date=max(first_days), days=first_days),
        TripProposal(start_date=min(second_days), end_date=max(second_days), days=second_days),
    )


@dataclass(frozen=True, slots=True)
class TripDecision:
    """One reviewed trip proposal and its verdict: a name to confirm it, or ``None`` to decline.

    ``confirmed_days`` narrows or extends the proposed run per the "proposal is the run; the
    edges belong to the user" rule (``trip-grouping-research.md`` §5) -- ``None`` uses the full
    proposed run (``proposal.days``) unchanged.
    """

    proposal: TripProposal
    name: str | None
    confirmed_days: Sequence[date] | None = None


def commit_trips(catalog: Catalog, decisions: Sequence[TripDecision]) -> int:
    """Persist reviewed trip decisions. Returns how many trips were newly named.

    **Name-once, by day** (``trip-grouping-research.md`` §6): a day :meth:`Catalog.trip_for_day`
    already reports claimed is never re-created and never re-asked.

    - **No day in this decision is claimed yet:** a brand-new trip. A ``name`` creates it
      (:meth:`Catalog.create_trip`); an empty or missing ``name`` is a decline and persists
      nothing.
    - **Every day in this decision is already claimed by the SAME trip:** membership is refreshed
      via :meth:`Catalog.update_trip_days` -- idempotent when the confirmed days match what is
      already stored (a pure re-ask: a re-run over unchanged clusters, or a re-run after
      ingesting one more photo into an already-active day), an edge adjustment when they differ.
      ``update_trip_days`` never touches the trip's id, name or slug, so re-ingesting a day
      already claimed by a named trip can never re-create it or orphan its name -- and any
      ``name`` this decision carries is ignored, exactly as a remembered day-event ignores a
      re-prompt (``event_review.commit_catalog``).
    - **Mixed** (some days already claimed, by one or more OTHER trips, alongside unclaimed
      days): not reachable by any fixture here. Flagged, not solved -- persists nothing for that
      decision rather than guessing which trip it belongs to.

    Complexity: ``O(days)`` per decision for the name-once lookups (one indexed
    ``trip_for_day`` read per day), plus ``O(days)`` for whichever of ``create_trip`` /
    ``update_trip_days`` fires -- both are already ``O(days)`` per Stage 2c. No table scan.
    """
    named = 0
    for decision in decisions:
        days = (
            sorted(decision.confirmed_days)
            if decision.confirmed_days is not None
            else sorted(decision.proposal.days)
        )
        if not days:
            continue

        claims = {catalog.trip_for_day(d.isoformat()) for d in days}
        if claims == {None}:
            if not decision.name or not decision.name.strip():
                continue  # declined: nothing to persist
            name = decision.name.strip()
            catalog.create_trip(
                name=name,
                slug=slugify(name),
                start_date=days[0].isoformat(),
                end_date=days[-1].isoformat(),
                days=[d.isoformat() for d in days],
            )
            named += 1
        elif len(claims) == 1 and None not in claims:
            (existing_id,) = claims
            assert existing_id is not None  # excluded by the `None not in claims` check above
            catalog.update_trip_days(existing_id, [d.isoformat() for d in days])
        else:
            continue  # mixed claims: out of scope for this stage, see docstring
    return named
