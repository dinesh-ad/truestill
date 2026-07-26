"""Event-review orchestration (pure, no I/O beyond the catalog it is given).

Clusters Camera files, resolves each cluster's name from catalog memory first (a previously
named event, or a remembered skip) and otherwise an injected ``prompt`` callback, and applies
the named events. It prints nothing and reads no stdin -- the CLI and the web UI each supply
their own prompt and their own display. This is what lets any front-end drive event review
without importing another front-end.

Naming is the one thing only a human can do; everything else is the machine's.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from vaeon_core.catalog import Catalog
from vaeon_core.events import EventCandidate, EventItem, cluster_camera, slugify
from vaeon_core.hashing import sha256_file
from vaeon_core.layout import DEFAULT_TEMPLATE, LayoutTemplate
from vaeon_core.models import Resolution
from vaeon_core.organizer import apply_events

#: A prompt returns the user's chosen name for a cluster, or None to skip it.
Prompt = Callable[[EventCandidate], str | None]


@dataclass(frozen=True, slots=True)
class EventStageOutcome:
    """Result of the event stage: possibly-rewritten resolutions, event ids, and the proposals."""

    resolutions: list[Resolution]
    event_ids: dict[str, int]
    clusters: list[EventCandidate] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class EventDecision:
    """One reviewed cluster and its verdict: a name to keep it, or ``None`` to skip it.

    The cluster may be an original proposal, or one the caller reshaped with
    :func:`vaeon_core.events.merge_candidates` / ``split_candidate`` before deciding.
    """

    cluster: EventCandidate
    name: str | None  # None -> skip


def _gps(meta: dict[str, Any]) -> tuple[float, float] | None:
    lat, lon = meta.get("GPSLatitude"), meta.get("GPSLongitude")
    if isinstance(lat, int | float) and isinstance(lon, int | float):
        return (float(lat), float(lon))
    return None


def gather_camera_items(
    resolutions: list[Resolution], metadata: dict[Any, dict[str, Any]]
) -> list[EventItem]:
    """Build clustering inputs from Camera files that will be uploaded and carry a date.

    Camera membership is the device rule firing (so per-device labels count too), not a literal
    "Camera" string. SHA-256 is computed here for any unique-size file the scan skipped, since a
    cluster's identity is the hash of its members' SHA-256s.
    """
    items: list[EventItem] = []
    for resolution in resolutions:
        decision = resolution.decision
        if not resolution.should_upload or decision.category.rule != "device":
            continue
        if decision.captured_at is None:
            continue
        sha = resolution.hashes.sha256 or sha256_file(decision.source)
        items.append(
            EventItem(
                key=str(decision.source),
                captured_at=decision.captured_at,
                sha256=sha,
                gps=_gps(metadata.get(decision.source, {})),
            )
        )
    return items


def propose(
    resolutions: list[Resolution], metadata: dict[Any, dict[str, Any]]
) -> list[EventCandidate]:
    """Return the proposed Camera event clusters (the data a UI presents for review)."""
    return cluster_camera(gather_camera_items(resolutions, metadata))


def commit(
    resolutions: list[Resolution],
    decisions: list[EventDecision],
    catalog: Catalog,
    *,
    template: LayoutTemplate = DEFAULT_TEMPLATE,
) -> EventStageOutcome:
    """Apply reviewed decisions: name (record event), skip (remember), or reuse a known event.

    Decisions may cover reshaped (merged/split) clusters -- identity is each cluster's member
    signature, so a previously-named or previously-skipped cluster is honoured without re-asking.
    """
    skipped = catalog.skipped_signatures()
    assignments: dict[str, tuple[Any, str]] = {}
    event_ids: dict[str, int] = {}

    for decision in decisions:
        cluster = decision.cluster
        signature = cluster.signature
        existing = catalog.event_by_signature(signature)
        if existing is not None:
            slug, event_id = existing["slug"], int(existing["id"])
        elif decision.name and decision.name.strip():
            slug = slugify(decision.name)
            event_id = catalog.record_event(
                name=decision.name.strip(),
                slug=slug,
                start_date=cluster.start.isoformat(),
                file_count=cluster.count,
                signature=signature,
            )
        else:
            if signature not in skipped:
                catalog.record_skip(signature)
            continue
        for item in cluster.items:
            assignments[item.key] = (cluster.start, slug)
            event_ids[item.key] = event_id

    return EventStageOutcome(
        apply_events(resolutions, assignments, template=template),
        event_ids,
        [d.cluster for d in decisions],
    )


def _parse_dt(value: Any) -> datetime:
    return datetime.fromisoformat(str(value))


def propose_from_catalog(catalog: Catalog, drive_uuid: str) -> list[EventCandidate]:
    """Propose trips from an *already-organized* drive's dated camera copies (no source re-read).

    This is the web UI's "review trips in place" path: it clusters what the catalog already knows,
    so naming trips operates on the organized library rather than a fresh import.
    """
    items = [
        EventItem(
            key=str(row["sha256"]),
            captured_at=_parse_dt(row["captured_at"]),
            sha256=str(row["sha256"]),
        )
        for row in catalog.camera_copies_for_events(drive_uuid)
    ]
    return cluster_camera(items)


def commit_catalog(catalog: Catalog, decisions: list[EventDecision]) -> int:
    """Persist reviewed trip names against the catalog: record each event and link its files.

    Linking ``files.event_id`` is what lets a subsequent migration place each file under its event
    folder. Returns the number of events named (skips are remembered, not counted).
    """
    skipped = catalog.skipped_signatures()
    named = 0
    for decision in decisions:
        cluster = decision.cluster
        signature = cluster.signature
        existing = catalog.event_by_signature(signature)
        if existing is not None:
            event_id = int(existing["id"])
        elif decision.name and decision.name.strip():
            event_id = catalog.record_event(
                name=decision.name.strip(),
                slug=slugify(decision.name),
                start_date=cluster.start.isoformat(),
                file_count=cluster.count,
                signature=signature,
            )
        else:
            if signature not in skipped:
                catalog.record_skip(signature)
            continue
        catalog.set_event_id([item.sha256 for item in cluster.items], event_id)
        named += 1
    return named


def run_event_stage(
    resolutions: list[Resolution],
    metadata: dict[Any, dict[str, Any]],
    catalog: Catalog,
    *,
    apply: bool,
    prompt: Prompt | None = None,
    template: LayoutTemplate = DEFAULT_TEMPLATE,
) -> EventStageOutcome:
    """Name/skip convenience over :func:`propose` + :func:`commit` (the CLI's flow).

    In preview (``apply=False``) the clusters are returned but nothing is named or written. In
    apply mode each not-yet-decided cluster is put to ``prompt`` (a missing/empty answer skips).
    A UI wanting merge/split calls ``propose`` + ``commit`` directly instead.
    """
    clusters = propose(resolutions, metadata)
    if not clusters or not apply:
        return EventStageOutcome(resolutions, {}, clusters)

    ask = prompt or (lambda _cluster: None)
    skipped = catalog.skipped_signatures()
    decisions: list[EventDecision] = []
    for cluster in clusters:
        if catalog.event_by_signature(cluster.signature) is not None:
            decisions.append(EventDecision(cluster, name=None))  # commit reuses via signature
        elif cluster.signature in skipped:
            continue  # remembered skip -> leave flat, don't re-ask
        else:
            decisions.append(EventDecision(cluster, name=ask(cluster)))
    return commit(resolutions, decisions, catalog, template=template)
