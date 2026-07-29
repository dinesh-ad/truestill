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

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime

from truestill_core.catalog import Catalog
from truestill_core.events import EventItem, cluster_camera, slugify
from truestill_core.trips import (
    DEFAULT_MAX_GAP_DAYS,
    DEFAULT_MAX_SPAN_DAYS,
    TripDetectionResult,
    TripProposal,
    detect_trips,
)


def _parse_dt(value: object) -> datetime:
    return datetime.fromisoformat(str(value))


def propose_trips_from_catalog(
    catalog: Catalog,
    drive_uuid: str,
    *,
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
    items = [
        EventItem(
            key=str(row["sha256"]),
            captured_at=_parse_dt(row["captured_at"]),
            sha256=str(row["sha256"]),
        )
        for row in catalog.camera_copies_for_events(drive_uuid)
    ]
    clusters = cluster_camera(items)
    return detect_trips(items, clusters, max_span_days=max_span_days, max_gap_days=max_gap_days)


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
