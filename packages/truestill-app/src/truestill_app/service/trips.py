"""Trips and events: review cards, propose, merge/split, apply names."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from pathlib import Path
from typing import Any, Literal, NotRequired, TypedDict

from truestill_core.catalog import Catalog
from truestill_core.categorize import build_rules
from truestill_core.dedup import DedupIndex
from truestill_core.drive import read_marker
from truestill_core.event_review import EventDecision, commit_catalog
from truestill_core.events import EventCandidate, EventSettings, split_candidate
from truestill_core.exif import read_metadata
from truestill_core.hash_cache import HashCache
from truestill_core.hashing import DEFAULT_PHASH_THRESHOLD
from truestill_core.layout_settings import resolve_scheme
from truestill_core.models import Resolution
from truestill_core.organizer import discover, heavy_days_for_organize, plan, resolve
from truestill_core.trip_review import (
    ReviewCard,
    TripDecision,
    TripMergeError,
    assemble_trip_review,
    collapsed_event_cards,
    commit_trips,
    decline_message,
    is_small_event,
    merge_review_cards,
    order_review_cards,
    split_trip,
)

from truestill_app.service.drive_support import DriveUnavailablePayload, drive_unavailable


def plan_resolve(source: Path, db: Path) -> tuple[list[Resolution], dict[Path, dict[str, Any]]]:
    """Plan + dedup a source (no writes), returning resolutions and metadata for clustering.

    Cached like every other reader (audit F18). Note this helper is **not on a user path** -
    ``server.py`` never calls it and its only caller is ``test_events_http``; the cache is here
    so the file cannot be read later as "the one reader that deliberately does not cache", which
    is exactly the ambiguity F18 was made of. Its dead-ish status is tracked separately as F22.
    """
    files = discover(source)
    if not files:
        return [], {}
    with HashCache.beside(db) as cache:
        metadata = read_metadata(files, cache=cache)
    with Catalog(db) as catalog:
        scheme = resolve_scheme(catalog)
        rules = build_rules()
        heavy = heavy_days_for_organize(catalog, files, metadata, rules)
        decisions = plan(files, metadata, rules, scheme=scheme, heavy_days=heavy)
        index = DedupIndex.from_catalog_rows(catalog.seed_rows(), DEFAULT_PHASH_THRESHOLD)
        resolutions = resolve(decisions, index, catalog_sizes=catalog.known_sizes())
    return resolutions, metadata


class ReviewDayPayload(TypedDict):
    date: str
    count: int


class ReviewCardPayload(TypedDict):
    kind: Literal["trip", "event"]
    start: str
    end: str
    count: int
    active_days: int
    days: list[ReviewDayPayload]
    location: list[float] | None
    collapsed: bool


class CollapsedEventSummaryPayload(TypedDict):
    count: int
    min_photos: int
    max_photos: int
    start: str
    end: str


class ReviewCardsPayload(TypedDict):
    session: str
    cards: list[ReviewCardPayload]
    collapsed: CollapsedEventSummaryPayload | None


class ProposedReviewCardsPayload(ReviewCardsPayload):
    ok: Literal[True]
    label: str
    declines: list[str]
    #: The proposal-size floor this run filtered with, so a screen with NO cards can say which
    #: number it fell short of. It rides the proposal and not :class:`ReviewCardsPayload`, because
    #: propose is the only path that can render an empty review: split and merge rearrange cards
    #: that already exist and cannot reduce them to none.
    min_files: int


def _event_location(cluster: EventCandidate) -> list[float] | None:
    centroid = cluster.gps_centroid()
    return list(centroid) if centroid else None


def review_card_json(card: ReviewCard, min_files: int) -> ReviewCardPayload:
    """Serialise one assembled review card (Stage 2d, 13.3b) - a multi-day trip or a standalone
    day-event - for the review UI. ``kind`` ("trip" | "event") is the label the screen shows;
    serialisation does not alter either card's persisted identity.
    """
    if card.trip is not None:
        return {
            "kind": card.kind,
            "start": card.trip.start_date.isoformat(),
            "end": card.trip.end_date.isoformat(),
            "count": card.count,
            "active_days": len(card.trip.days),
            "days": [
                {"date": day.isoformat(), "count": count}
                for day, count in sorted(card.trip.days.items())
            ],
            "location": None,
            "collapsed": False,
        }
    assert card.event is not None
    return {
        "kind": card.kind,
        "start": card.event.start.isoformat(),
        "end": card.event.end.isoformat(),
        "count": card.count,
        "active_days": 1,
        "days": [],
        "location": _event_location(card.event),
        "collapsed": is_small_event(card, min_files),
    }


def collapsed_event_summary(
    cards: Sequence[ReviewCard], min_files: int
) -> CollapsedEventSummaryPayload | None:
    """Summarise every hidden event so expanding is optional, not required for confidence."""
    collapsed = collapsed_event_cards(cards, min_files)
    if not collapsed:
        return None
    counts = [card.count for card in collapsed]
    return {
        "count": len(collapsed),
        "min_photos": min(counts),
        "max_photos": max(counts),
        "start": min(card.start for card in collapsed).isoformat(),
        "end": max(card.end for card in collapsed).isoformat(),
    }


def review_cards_payload(
    session: str, cards: Sequence[ReviewCard], min_files: int
) -> ReviewCardsPayload:
    return {
        "session": session,
        "cards": [review_card_json(card, min_files) for card in cards],
        "collapsed": collapsed_event_summary(cards, min_files),
    }


def proposed_review_cards_payload(
    session: str,
    cards: Sequence[ReviewCard],
    min_files: int,
    label: str,
    declines: list[str],
) -> ProposedReviewCardsPayload:
    return {
        **review_cards_payload(session, cards, min_files),
        "ok": True,
        "label": label,
        "declines": declines,
        "min_files": min_files,
    }


class InvalidEventProposalPayload(TypedDict):
    ok: Literal[False]
    error: str


# Same shape as the connected-drive soft-refuse (drive_support.DriveUnavailablePayload).
EventProposalDriveErrorPayload = DriveUnavailablePayload


class EventProposalSuccessPayload(TypedDict):
    ok: Literal[True]
    uuid: str
    label: str
    cards: list[ReviewCard]
    day_totals: dict[date, int]
    min_files: int
    declines: list[str]


def invalid_event_proposal_payload(error: str) -> InvalidEventProposalPayload:
    return {"ok": False, "error": error}


def propose_events(
    path: Path, db: Path
) -> EventProposalSuccessPayload | EventProposalDriveErrorPayload:
    """Assemble trips and standalone day-events from an already-organized connected drive.

    Stage 2d, 13.3b's inversion: a genuine multi-day run assembles into ONE card; a standalone
    active day still renders as its own (unchanged) day-event card. Returns the drive uuid + the
    assembled review cards (the caller keeps them, and ``day_totals``, in a session for
    merge/split/name), or an error when the path is not a connected truestill drive.

    A decline is named and explained (§3f), never folded into silence: each carries the exact
    message detection's own ruling requires.
    """
    marker = read_marker(path)
    if marker is None:
        return drive_unavailable(path)
    with Catalog(db) as catalog:
        settings = EventSettings.from_catalog(catalog)
        review = assemble_trip_review(
            catalog,
            marker.uuid,
            min_files=settings.min_files,
        )
    return {
        "ok": True,
        "uuid": marker.uuid,
        "label": marker.label,
        "cards": review.cards,
        "day_totals": review.day_totals,
        "min_files": settings.min_files,
        "declines": [decline_message(decline) for decline in review.declines],
    }


class MergeReviewCardsResult(TypedDict):
    """Outcome of :func:`merge_event_review_cards` - either new cards or a refusal message."""

    cards: NotRequired[list[ReviewCard]]
    error: NotRequired[str]


def merge_event_review_cards(
    cards: list[ReviewCard],
    day_totals: dict[date, int],
    indices: list[int],
) -> MergeReviewCardsResult:
    """Combine selected review cards into one trip, or refuse with the §3e/§3f message.

    Domain work for the Trips screen's Merge control - lives in service so ``server.py`` stays
    a transport shim (§2 sole-bridge rule; audit F7).
    """
    chosen = [cards[i] for i in indices]
    rest = [card for j, card in enumerate(cards) if j not in set(indices)]
    try:
        merged = merge_review_cards(chosen, day_totals)
    except TripMergeError as exc:
        return {"error": str(exc)}
    return {"cards": order_review_cards([ReviewCard(trip=merged), *rest])}


def split_event_review_card(
    cards: list[ReviewCard],
    index: int,
    *,
    at: int | None = None,
    after_day: str | None = None,
) -> list[ReviewCard]:
    """Split one review card into two and re-order the session list.

    An event splits by file count; a trip splits at a day boundary. Domain work for the Trips
    screen's Split control (§2; audit F7).
    """
    card = cards[index]
    if card.event is not None:
        if at is None:
            message = "event split requires at"
            raise ValueError(message)
        first_event, second_event = split_candidate(card.event, at)
        new_cards = [ReviewCard(event=first_event), ReviewCard(event=second_event)]
    else:
        if after_day is None:
            message = "trip split requires after_day"
            raise ValueError(message)
        assert card.trip is not None
        first_trip, second_trip = split_trip(card.trip, date.fromisoformat(after_day))
        new_cards = [ReviewCard(trip=first_trip), ReviewCard(trip=second_trip)]
    return order_review_cards([*cards[:index], *new_cards, *cards[index + 1 :]])


class NamedEventSelection(TypedDict):
    event_id: int
    name: str
    start: str
    end: str


class NamedTripSelection(TypedDict):
    trip_id: int
    name: str
    start: str
    end: str


class ApplyReviewNamesResult(TypedDict):
    events: int
    trips: int
    named_events: list[NamedEventSelection]
    named_trips: list[NamedTripSelection]


def apply_event_review_names(
    db: Path,
    cards: list[ReviewCard],
    names: list[str | None],
) -> ApplyReviewNamesResult:
    """Persist named trips and events to the catalog (Save names). No files move.

    Domain work for the Trips screen's apply step - catalog writes belong in service, not the
    HTTP layer (§2; audit F7).
    """
    with Catalog(db) as catalog:
        event_decisions = [
            EventDecision(card.event, name)
            for card, name in zip(cards, names, strict=True)
            if card.event is not None
        ]
        named_events_count = commit_catalog(catalog, event_decisions)

        trip_decisions = [
            TripDecision(card.trip, name)
            for card, name in zip(cards, names, strict=True)
            if card.trip is not None
        ]
        named_trips_count = commit_trips(catalog, trip_decisions)

        named_events: list[NamedEventSelection] = []
        for card, name in zip(cards, names, strict=True):
            if card.event is None or not name or not name.strip():
                continue
            existing = catalog.event_by_signature(card.event.signature)
            if existing is None:
                continue
            named_events.append(
                {
                    "event_id": int(existing["id"]),
                    "name": str(existing["name"]),
                    "start": card.event.start.isoformat(),
                    "end": card.event.end.isoformat(),
                }
            )
        named_trips: list[NamedTripSelection] = []
        for card, name in zip(cards, names, strict=True):
            if card.trip is None or not name or not name.strip():
                continue
            first_day = min(card.trip.days)
            trip_id = catalog.trip_for_day(first_day.isoformat())
            if trip_id is None:
                continue
            named_trips.append(
                {
                    "trip_id": trip_id,
                    "name": name.strip(),
                    "start": first_day.isoformat(),
                    "end": max(card.trip.days).isoformat(),
                }
            )
    return {
        "events": named_events_count,
        "trips": named_trips_count,
        "named_events": named_events,
        "named_trips": named_trips,
    }
