"""What a move left behind: the folders it emptied, and the files it did not take.

Different job from :mod:`truestill_app.service.clean_empty` (preview/apply on a given
emptied list). This module only *detects* leftovers after a move/in-place run.

The two halves are here together because they are one answer and must agree on screen: a
folder that still holds skipped files is counted by the second and refused by the first
(`plan_cleanup` drops it as ``OCCUPIED``). Splitting them across modules is how the offer
would end up tidying around files nothing mentions.
"""

from __future__ import annotations

from pathlib import Path
from typing import TypedDict

from truestill_core.cleanup import emptied_directories, plan_cleanup
from truestill_core.left_behind import files_left_in_source
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


class LeftInSourceFolder(TypedDict):
    """One folder and how many of the user's files are still in it.

    ``folder`` is relative to the source root, and empty for the root itself - the surfaces
    word that case rather than inventing a name for it.
    """

    folder: str
    files: int


class LeftInSource(TypedDict):
    """Files a move did not take, for the completion card.

    Reason counts use `duplicate_explain`'s vocabulary, because they lead to opposite next
    actions: *already in your library* means the source copy is redundant, *earlier in this
    batch* says nothing about the library at all.
    """

    total: int
    already_in_library: int
    within_this_batch: int
    unclassified: int
    folders: list[LeftInSourceFolder]
    #: Before the cap, so a truncated list can never imply it is the whole story.
    folders_total: int


def left_in_source_from_results(
    results: list[ActionResult], source_root: Path
) -> LeftInSource | None:
    """The payload shape of :func:`truestill_core.left_behind.files_left_in_source`.

    Move and in-place only; the caller gates on the mode, exactly as the offer above does.
    """
    left = files_left_in_source(results, source_root)
    if left is None:
        return None
    return {
        "total": left.total,
        "already_in_library": left.already_in_library,
        "within_this_batch": left.within_this_batch,
        "unclassified": left.unclassified,
        "folders": [{"folder": f.folder, "files": f.files} for f in left.folders],
        "folders_total": left.folders_total,
    }


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
