"""Interactive event review: propose Camera clusters, let the user name or skip each.

Naming is the one thing only a human can do; everything else is the machine's. The prompt
is injectable so tests drive it without a TTY. Merge/split are intentionally out of scope
for the CLI (deferred to the desktop UI); v1 is name-or-skip.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from typing import Any

from vaeon_core.catalog import Catalog
from vaeon_core.events import EventCandidate, EventItem, cluster_camera, slugify
from vaeon_core.hashing import sha256_file
from vaeon_core.models import Resolution
from vaeon_core.organizer import apply_events

#: A prompt returns the user's chosen name, or None to skip the cluster.
Prompt = Callable[[EventCandidate], str | None]


def _gps(meta: dict[str, Any]) -> tuple[float, float] | None:
    lat, lon = meta.get("GPSLatitude"), meta.get("GPSLongitude")
    if isinstance(lat, int | float) and isinstance(lon, int | float):
        return (float(lat), float(lon))
    return None


def camera_items(
    resolutions: list[Resolution], metadata: dict[Any, dict[str, Any]]
) -> list[EventItem]:
    """Build clustering inputs from Camera files that will be uploaded and carry a date.

    Camera membership is the device rule firing (so per-device labels count too), not a
    literal "Camera" string. SHA-256 is computed here for any unique-size file the scan
    skipped, since a cluster's identity is the hash of its members' SHA-256s.
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


def _describe(cluster: EventCandidate) -> str:
    span = f"{cluster.start:%Y-%m-%d %H:%M} -> {cluster.end:%Y-%m-%d %H:%M}"
    centroid = cluster.gps_centroid()
    where = f"  ~({centroid[0]:.3f}, {centroid[1]:.3f})" if centroid else ""
    return f"{cluster.count} files  {span}{where}"


def _stdin_prompt(cluster: EventCandidate) -> str | None:
    """Default prompt: ask on the terminal. Empty input (or no TTY) means skip."""
    if not sys.stdin or not sys.stdin.isatty():
        return None
    print(f"\n  Event? {_describe(cluster)}")
    answer = input("  name (Enter to skip): ").strip()
    return answer or None


def run_event_stage(
    resolutions: list[Resolution],
    metadata: dict[Any, dict[str, Any]],
    catalog: Catalog,
    *,
    apply: bool,
    prompt: Prompt | None = None,
) -> tuple[list[Resolution], dict[str, int]]:
    """Cluster Camera files, resolve names (catalog memory first, then prompt), apply them.

    Returns the (possibly rewritten) resolutions and a map of source path -> event id for
    the executor to record. In dry-run (``apply=False``) clusters are displayed but nothing
    is asked or written, and paths are left unchanged.
    """
    items = camera_items(resolutions, metadata)
    clusters = cluster_camera(items)

    if not clusters:
        print("\nEvents: no clusters proposed (need enough Camera photos close in time).")
        return resolutions, {}

    if not apply:
        print(f"\nEvents: {len(clusters)} cluster(s) proposed (dry run -- not naming):")
        for cluster in clusters:
            print(f"  - {_describe(cluster)}")
        return resolutions, {}

    ask = prompt or _stdin_prompt
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

    return apply_events(resolutions, assignments), event_ids
