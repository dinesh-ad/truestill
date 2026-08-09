"""Trips and events: review cards, propose, merge/split, apply names."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path, PurePosixPath
from typing import Any, Literal, NotRequired, TypedDict

from truestill_core.catalog_session import open_catalog
from truestill_core.categorize import build_rules
from truestill_core.dedup import DedupIndex
from truestill_core.drive import read_marker
from truestill_core.event_review import EventDecision, commit_catalog
from truestill_core.events import EventCandidate, EventSettings, split_candidate
from truestill_core.exif import read_metadata
from truestill_core.folder_hint import suggest_name
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
    with open_catalog(db) as catalog:
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


#: Below this many cards, "a name in most cards" cannot mean anything: with one card every
#: ancestor is in 100% of them. See `_suggestion_roots`.
_MIN_CARDS_FOR_ROOTS = 3

#: Share of a proposal's cards a name must appear in to be treated as library plumbing.
_ROOT_SHARE = 0.8


class ReviewCardPayload(TypedDict):
    kind: Literal["trip", "event"]
    #: The name this trip ALREADY has in the CATALOG, or None when it has none yet. Deliberately
    #: NOT ``name``: the browser already uses ``card.name`` as its own store for whatever the user
    #: has typed (`app.js` `syncEvNamesFromDom`, carried across merge/split by
    #: `takeEvNamesByKey`), so putting a catalog name there would make it indistinguishable from
    #: something the user wrote. A proposal is
    #: recomputed from clusters on every visit and `assemble_trip_review` never consults
    #: `trip_for_day`, so an already-named trip is re-offered like any other card; without this
    #: the screen could not tell the two apart and showed an empty box for a question
    #: `commit_trips` will not accept an answer to.
    existing_name: str | None
    #: A name PROPOSED from the folders this card's members came from, or None. Its own field:
    #: `name` is the browser's store for what the user typed and `existing_name` is what the
    #: catalog already holds. Three meanings, three fields - collapsing any two makes a
    #: suggestion indistinguishable from an answer.
    suggested_name: str | None
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


@dataclass(frozen=True, slots=True)
class ExistingNames:
    """What the catalog has already named, in the two shapes identity takes.

    One object rather than two loose maps threaded side by side: they are read together, from one
    catalog, about one review, and a third would otherwise be added as a third parameter.

    The two are keyed differently because the two identities ARE different, and that is the whole
    design decision here rather than an implementation detail. A trip is identified by the days it
    claims (`trip_days.day` is a primary key), so it survives its membership changing. An event is
    identified by its membership itself (`events.signature`, a hash over member SHA-256s), so a
    cluster that gained or lost a photo is a NEW event that merely overlaps a named one - and must
    still be offered a name, or every cluster that ever grew would fall silent.
    """

    trips_by_day: Mapping[str, str]
    events_by_signature: Mapping[str, str]


@dataclass(frozen=True, slots=True)
class SourceHints:
    """Where a drive's clustered files came from, in the two shapes a card needs to be read.

    A trip card carries no member identities - `TripProposal` holds day COUNTS - so its members
    are derived by date from the days it claims (the day-claim rule, `trip-grouping-research.md`
    §2). An event card reads its own `items`. Both end at the same per-file ancestor chains.
    """

    chain_by_sha: Mapping[str, tuple[str, ...]]
    shas_by_day: Mapping[str, tuple[str, ...]]

    @classmethod
    def of(cls, rows: Sequence[Any]) -> SourceHints:
        chains: dict[str, tuple[str, ...]] = {}
        by_day: dict[str, list[str]] = {}
        for row in rows:
            sha = str(row["sha256"])
            # `files.source_path` is TEXT NOT NULL, so the degenerate value is "" rather than
            # NULL. Either way the member keeps its place in the denominator with an empty
            # chain: missing evidence weakens a claim, it does not leave the count.
            parent = PurePosixPath(str(row["source_path"] or "")).parent
            chains[sha] = tuple(part for part in reversed(parent.parts) if part != "/")
            by_day.setdefault(str(row["captured_at"])[:10], []).append(sha)
        return cls(chains, {day: tuple(shas) for day, shas in by_day.items()})

    def chains_for(self, card: ReviewCard) -> list[tuple[str, ...]]:
        if card.trip is not None:
            shas = [
                sha for day in card.trip.days for sha in self.shas_by_day.get(day.isoformat(), ())
            ]
        else:
            shas = [item.sha256 for item in card.event.items] if card.event else []
        return [self.chain_by_sha.get(sha, ()) for sha in shas]


def suggested_card_name(
    card: ReviewCard, hints: SourceHints | None, names: ExistingNames | None, roots: frozenset[str]
) -> str | None:
    """A name to propose for this card, or ``None``.

    Gated on the card having no name yet: proposing one for something already named would offer a
    confident answer to a question `commit_catalog` discards. Never raises - a suggestion sits
    behind a naming screen and may not block it.
    """
    if hints is None or existing_card_name(card, names) is not None:
        return None
    return suggest_name(hints.chains_for(card), year=card.start.year, roots=roots)


def _suggestion_roots(cards: Sequence[ReviewCard], hints: SourceHints | None) -> frozenset[str]:
    """Names present in >= 80% of this proposal's cards - library plumbing, never an event.

    Only computed at three cards or more: with one card every ancestor is in 100% of them, which
    would silence everything. Below that the junk list carries it alone, and the depth cap keeps
    the climb short.
    """
    if hints is None or len(cards) < _MIN_CARDS_FOR_ROOTS:
        return frozenset()
    seen: Counter[str] = Counter()
    for card in cards:
        for name in {part for chain in hints.chains_for(card) for part in chain}:
            seen[name] += 1
    return frozenset(name for name, held in seen.items() if held >= len(cards) * _ROOT_SHARE)


def existing_card_name(card: ReviewCard, names: ExistingNames | None) -> str | None:
    """The name the catalog already holds for this exact card, if any.

    A trip is looked up by its first claimed DAY, not by a position in the card list: merge and
    split reorder cards, and an index-keyed lookup would start naming the wrong one.
    """
    if names is None:
        return None
    if card.trip is not None:
        return names.trips_by_day.get(min(card.trip.days).isoformat())
    return names.events_by_signature.get(card.event.signature) if card.event else None


def review_card_json(
    card: ReviewCard,
    min_files: int,
    names: ExistingNames | None = None,
    suggested: str | None = None,
) -> ReviewCardPayload:
    """Serialise one assembled review card (Stage 2d, 13.3b) - a multi-day trip or a standalone
    day-event - for the review UI. ``kind`` ("trip" | "event") is the label the screen shows;
    serialisation does not alter either card's persisted identity.
    """
    if card.trip is not None:
        return {
            "kind": card.kind,
            "existing_name": existing_card_name(card, names),
            "suggested_name": suggested,
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
        "existing_name": existing_card_name(card, names),
        "suggested_name": suggested,
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
    session: str,
    cards: Sequence[ReviewCard],
    min_files: int,
    names: ExistingNames | None = None,
    hints: SourceHints | None = None,
) -> ReviewCardsPayload:
    roots = _suggestion_roots(cards, hints)
    return {
        "session": session,
        "cards": [
            review_card_json(card, min_files, names, suggested_card_name(card, hints, names, roots))
            for card in cards
        ],
        "collapsed": collapsed_event_summary(cards, min_files),
    }


def proposed_review_cards_payload(
    session: str, proposal: EventProposalSuccessPayload
) -> ProposedReviewCardsPayload:
    """Serialise a whole proposal for the screen.

    Takes the proposal object rather than its fields one by one. The caller used to pass five
    values drawn from TWO sources - three off the session it had just built, two off the proposal
    - which is five chances for them to disagree about the same review, and one argument short of
    a lint rule that exists precisely to stop a sixth being added quietly.
    """
    return {
        **review_cards_payload(
            session,
            proposal["cards"],
            proposal["min_files"],
            proposal["existing_names"],
            proposal["source_hints"],
        ),
        "ok": True,
        "label": proposal["label"],
        "declines": proposal["declines"],
        "min_files": proposal["min_files"],
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
    #: What the catalog has already named - see `ReviewCardPayload.existing_name`. Read once with
    #: the proposal so merge and split, which rebuild cards without touching the catalog, keep
    #: answering the question consistently.
    existing_names: ExistingNames
    #: Where each clustered file came from, read once with the proposal - see `SourceHints`.
    source_hints: SourceHints


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
    with open_catalog(db) as catalog:
        settings = EventSettings.from_catalog(catalog)
        review = assemble_trip_review(
            catalog,
            marker.uuid,
            min_files=settings.min_files,
        )
        hints = SourceHints.of(catalog.source_hints_for_drive(marker.uuid))
        existing = ExistingNames(
            trips_by_day=catalog.named_trip_days(),
            events_by_signature=catalog.named_event_signatures(),
        )
    return {
        "ok": True,
        "uuid": marker.uuid,
        "label": marker.label,
        "cards": review.cards,
        "day_totals": review.day_totals,
        "min_files": settings.min_files,
        "declines": [decline_message(decline) for decline in review.declines],
        "existing_names": existing,
        "source_hints": hints,
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
    with open_catalog(db) as catalog:
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
