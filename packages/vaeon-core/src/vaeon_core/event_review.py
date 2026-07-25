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
from typing import Any

from vaeon_core.catalog import Catalog
from vaeon_core.events import EventCandidate, EventItem, cluster_camera, slugify
from vaeon_core.hashing import sha256_file
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


def run_event_stage(
    resolutions: list[Resolution],
    metadata: dict[Any, dict[str, Any]],
    catalog: Catalog,
    *,
    apply: bool,
    prompt: Prompt | None = None,
) -> EventStageOutcome:
    """Cluster Camera files and, when ``apply``, resolve names (catalog memory, then ``prompt``).

    In preview (``apply=False``) the clusters are returned but nothing is named or written and
    the resolutions are unchanged. In apply mode a missing/empty prompt answer skips a cluster.
    """
    items = gather_camera_items(resolutions, metadata)
    clusters = cluster_camera(items)

    if not clusters or not apply:
        return EventStageOutcome(resolutions, {}, clusters)

    ask = prompt or (lambda _cluster: None)
    skipped = catalog.skipped_signatures()
    assignments: dict[str, tuple[Any, str]] = {}
    event_ids: dict[str, int] = {}

    for cluster in clusters:
        signature = cluster.signature
        existing = catalog.event_by_signature(signature)
        if existing is not None:
            slug, event_id = existing["slug"], int(existing["id"])
        elif signature in skipped:
            continue
        else:
            name = ask(cluster)
            if not name or not name.strip():
                catalog.record_skip(signature)
                continue
            slug = slugify(name)
            event_id = catalog.record_event(
                name=name.strip(),
                slug=slug,
                start_date=cluster.start.isoformat(),
                file_count=cluster.count,
                signature=signature,
            )
        for item in cluster.items:
            assignments[item.key] = (cluster.start, slug)
            event_ids[item.key] = event_id

    return EventStageOutcome(apply_events(resolutions, assignments), event_ids, clusters)
