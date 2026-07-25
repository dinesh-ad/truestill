"""CLI adapter for event review: terminal prompt + display over the pure core orchestrator.

The orchestration lives in :mod:`vaeon_core.event_review`; this module only adds the CLI's
interaction surface (a stdin prompt and printed proposals). ``album_prompt`` builds a
non-interactive prompt for ``ingest --map-albums``.
"""

from __future__ import annotations

import sys
from collections import Counter
from typing import Any

from vaeon_core.catalog import Catalog
from vaeon_core.event_review import Prompt
from vaeon_core.event_review import run_event_stage as _core_run_event_stage
from vaeon_core.events import EventCandidate
from vaeon_core.models import Resolution

__all__ = ["Prompt", "album_prompt", "run_event_stage"]


def _describe(cluster: EventCandidate) -> str:
    span = f"{cluster.start:%Y-%m-%d %H:%M} -> {cluster.end:%Y-%m-%d %H:%M}"
    centroid = cluster.gps_centroid()
    where = f"  ~({centroid[0]:.3f}, {centroid[1]:.3f})" if centroid else ""
    return f"{cluster.count} files  {span}{where}"


def album_prompt(album_of: dict[str, str]) -> Prompt:
    """A non-interactive prompt that names a cluster after its members' majority album."""

    def prompt(cluster: EventCandidate) -> str | None:
        names = [album_of[item.key] for item in cluster.items if item.key in album_of]
        if not names:
            return None
        return Counter(names).most_common(1)[0][0]

    return prompt


def _stdin_prompt(cluster: EventCandidate) -> str | None:
    """Ask on the terminal. Empty input (or no TTY) means skip."""
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
    """Run the core event stage, printing proposals for the CLI. Returns (resolutions, event_ids)."""
    outcome = _core_run_event_stage(
        resolutions, metadata, catalog, apply=apply, prompt=prompt or _stdin_prompt
    )
    if not outcome.clusters:
        print("\nEvents: no clusters proposed (need enough Camera photos close in time).")
    elif not apply:
        print(f"\nEvents: {len(outcome.clusters)} cluster(s) proposed (dry run -- not naming):")
        for cluster in outcome.clusters:
            print(f"  - {_describe(cluster)}")
    return outcome.resolutions, outcome.event_ids
