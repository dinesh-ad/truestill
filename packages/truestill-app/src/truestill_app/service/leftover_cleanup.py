"""Post-run leftover empty-folder detection for Organize and Migration.

Different job from :mod:`truestill_app.service.clean_empty` (preview/apply on a given
emptied list). This module only *detects* leftovers after a move/in-place run.
"""

from __future__ import annotations

from pathlib import Path
from typing import TypedDict

from truestill_core.cleanup import emptied_directories, plan_cleanup
from truestill_core.models import ActionResult, ActionStatus


class LeftoverEmptyFolders(TypedDict):
    """Empty-folder cleanup offer after move/in-place organize or migration apply.

    Shared by organize_run and migration_apply (the genuinely shared shape;
    completion itself is organize-only).
    """

    source_root: str
    emptied: list[str]
    count: int
    folders: list[str]


def cleanup_summary_from_results(
    results: list[ActionResult], source_root: Path
) -> LeftoverEmptyFolders | None:
    """Empty-folder leftovers after move/in-place organize, for completion messaging."""
    moved_sources = [
        row.resolution.decision.source
        for row in results
        if row.status in {ActionStatus.MOVED, ActionStatus.MOVED_IN_PLACE}
    ]
    if not moved_sources:
        return None
    old_paths: list[str] = []
    for source in moved_sources:
        try:
            old_paths.append(source.relative_to(source_root).as_posix())
        except ValueError:
            continue
    if not old_paths:
        return None
    return cleanup_summary_from_old_paths(source_root, old_paths)


def cleanup_summary_from_old_paths(
    source_root: Path, old_paths: list[str]
) -> LeftoverEmptyFolders | None:
    emptied = emptied_directories(old_paths)
    plan = plan_cleanup(source_root, emptied)
    leftovers = [candidate.relative for candidate in plan.removable]
    if not leftovers:
        return None
    return {
        "source_root": str(source_root),
        "emptied": emptied,
        "count": len(leftovers),
        "folders": leftovers,
    }
