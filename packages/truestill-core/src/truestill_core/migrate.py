"""Re-place an already-organized drive's copies under a new layout template.

The dangerous operation of this whole feature. It obeys three invariants:

* **Copy-only.** It moves *destination copies* recorded in ``file_copies``; source files are
  never touched. A move is a copy-then-remove at the destination, so a byte-identical copy's
  ``copy_sha256`` stays valid and ``verify`` keeps passing.
* **One connected drive at a time.** It relocates only the drive it is handed; other drives'
  copies are left untouched and reported as pending until each is reconnected.
* **Crash-safe and resumable.** Every move is journalled before any file is touched, and each
  move runs copy -> verify -> update-catalog -> remove-old in that order. A run interrupted at
  any point is recovered by replaying the journal on the next invocation.

Per move, the catalog's recorded ``relative`` is the state indicator: it flips from the old to
the new path in a single transaction *after* the new copy is written and verified, and the
journal row (which retains the old path) is cleared only *after* the old copy is removed -- so a
crash between those steps leaves a recoverable orphan, never a lost or unrecorded file.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import PurePosixPath

from truestill_core.catalog import Catalog
from truestill_core.destinations.base import Destination, DestinationError
from truestill_core.layout import PATH_LENGTH_WARN, LayoutTemplate, RenderContext
from truestill_core.progress import Phase, Progress, ProgressCallback


@dataclass(frozen=True)
class Move:
    """One copy to relocate, from ``old_relative`` to ``new_relative`` on a drive."""

    sha256: str
    old_relative: str
    new_relative: str
    copy_sha256: str | None


@dataclass(frozen=True)
class MigrationPlan:
    """The relocations a template change implies for one drive (pure; nothing is moved)."""

    drive_uuid: str
    moves: list[Move]
    unchanged: int
    warnings: list[str]


@dataclass(frozen=True)
class MigrationOutcome:
    """The result of planning (and possibly applying) a migration for one drive."""

    plan: MigrationPlan
    resumed: int  # moves recovered from a prior interrupted run
    migrated: int  # moves applied this run (0 in preview)
    applied: bool


def _parse_dt(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def plan_migration(catalog: Catalog, drive_uuid: str, template: LayoutTemplate) -> MigrationPlan:
    """Compute the ``old -> new`` relocations ``template`` implies for a drive's copies. Pure."""
    moves: list[Move] = []
    unchanged = 0
    warnings: list[str] = []
    targets: dict[str, str] = {}  # lower(new) -> new, to spot case-insensitive collisions

    for row in catalog.copies_for_migration(drive_uuid):
        current = str(row["relative"])
        filename = PurePosixPath(current).name
        event = None
        if row["event_slug"] and row["event_start"]:
            event = (_parse_dt(row["event_start"]), row["event_slug"])
        directory = template.render(
            RenderContext(
                category=str(row["category"]),
                captured_at=_parse_dt(row["captured_at"]),
                event=event,  # type: ignore[arg-type]  # start parsed to datetime above
            )
        )
        new_relative = (directory / filename).as_posix()
        if new_relative == current:
            unchanged += 1
            continue

        key = new_relative.lower()
        if key in targets:
            warnings.append(f"two files would land at the same path: {new_relative}")
        targets[key] = new_relative
        if len(new_relative) > PATH_LENGTH_WARN:
            warnings.append(f"{new_relative} is near the Windows 260-char limit")
        moves.append(Move(str(row["sha256"]), current, new_relative, row["copy_sha256"]))

    return MigrationPlan(drive_uuid=drive_uuid, moves=moves, unchanged=unchanged, warnings=warnings)


def _matches(destination: Destination, relative: str, expected_sha: str | None) -> bool:
    """Whether a stored copy exists and (if we know its hash) verifies."""
    if not destination.exists(relative):
        return False
    if not expected_sha:
        return True  # legacy copy with no recorded hash: existence is the best we can check
    try:
        return destination.checksum(relative) == expected_sha
    except DestinationError:
        return False


def _apply_move(catalog: Catalog, destination: Destination, drive_uuid: str, move: Move) -> None:
    """Advance one move to completion from whatever state it is in (idempotent)."""
    current = catalog.copy_relative(move.sha256, drive_uuid)
    if current is None:  # copy no longer tracked; nothing to do but forget the journal row
        catalog.clear_migration_move(move.sha256, drive_uuid)
        return

    if current == move.new_relative:  # catalog already flipped; only the old orphan may remain
        if move.old_relative != move.new_relative:
            destination.remove(move.old_relative)
        catalog.clear_migration_move(move.sha256, drive_uuid)
        return

    # Catalog still points at the old path: write and verify the new copy first.
    if not _matches(destination, move.new_relative, move.copy_sha256):
        destination.relocate(move.old_relative, move.new_relative)
    if not _matches(destination, move.new_relative, move.copy_sha256):
        message = f"verification failed after relocating to {move.new_relative}"
        raise DestinationError(message)

    catalog.relocate_copy(move.sha256, drive_uuid, move.new_relative)  # the atomic flip
    if move.old_relative != move.new_relative:
        destination.remove(move.old_relative)
    catalog.clear_migration_move(move.sha256, drive_uuid)


def resume_migration(catalog: Catalog, destination: Destination, drive_uuid: str) -> int:
    """Replay any journalled moves left by an interrupted run. Returns how many were recovered."""
    pending = catalog.pending_migration(drive_uuid)
    for row in pending:
        move = Move(
            sha256=str(row["sha256"]),
            old_relative=str(row["old_relative"]),
            new_relative=str(row["new_relative"]),
            copy_sha256=row["copy_sha256"],
        )
        _apply_move(catalog, destination, drive_uuid, move)
    return len(pending)


def run_migration(
    catalog: Catalog,
    destination: Destination,
    drive_uuid: str,
    template: LayoutTemplate,
    *,
    apply: bool,
    progress: ProgressCallback | None = None,
    cancel: threading.Event | None = None,
) -> MigrationOutcome:
    """Resume any interrupted run, plan the relocations, and (if ``apply``) carry them out.

    ``progress`` is called ``(done, total)`` per move; ``cancel`` stops the run early (moves
    already completed stay -- the run is resumable). A cancelled run's remaining journal rows are
    picked up by the next invocation.
    """
    resumed = resume_migration(catalog, destination, drive_uuid) if apply else 0
    plan = plan_migration(catalog, drive_uuid, template)
    if not apply:
        return MigrationOutcome(plan=plan, resumed=0, migrated=0, applied=False)

    catalog.record_migration_moves(
        [(m.sha256, drive_uuid, m.old_relative, m.new_relative, m.copy_sha256) for m in plan.moves]
    )
    migrated = 0
    total = len(plan.moves)
    for move in plan.moves:
        if cancel is not None and cancel.is_set():
            break
        _apply_move(catalog, destination, drive_uuid, move)
        migrated += 1
        if progress is not None:
            progress(Progress(migrated, total, Phase.MOVING, PurePosixPath(move.new_relative).name))
    return MigrationOutcome(plan=plan, resumed=resumed, migrated=migrated, applied=True)
