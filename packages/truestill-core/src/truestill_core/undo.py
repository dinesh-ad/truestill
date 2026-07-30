"""Reverse a rename-based relocation run, putting every file back where it was.

This exists because in-place organize is used precisely by people who have **no second copy**
-- a pendrive or external drive that *is* the library. A rename cannot lose bytes, so what is
at risk is not the data but the *arrangement*: a run that categorized badly has rearranged
someone's only copy. Undo is that feature's real safety story, which is why it ships with it
rather than after it.

Three rules, each the mirror of one the forward path obeys:

* **Undo never overwrites either.** A file whose original location is occupied again is
  reported and skipped, never restored on top of whatever is there now.
* **Undo is previewed first.** ``plan_undo`` touches nothing; ``run_undo(apply=True)`` is the
  only writing path, exactly as ``organizer.execute`` is for the forward direction.
* **Undo is honest about partial success.** Files moved or deleted since the run cannot be
  restored; they are counted and named rather than quietly skipped.

Moves are reversed in the opposite order to how they happened, so a chain that freed a path
for a later file unwinds without colliding with itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from truestill_core.catalog import Catalog
from truestill_core.drive import path_is_usable_dir
from truestill_core.progress import Phase, Progress, ProgressCallback


class UndoSkip(StrEnum):
    """Why one file could not be put back."""

    MOVED_AWAY = "moved_away"  # not at the path the run left it -- moved or deleted since
    ORIGIN_OCCUPIED = "origin_occupied"  # something else now sits where it came from
    FAILED = "failed"  # the rename itself failed (permissions, read-only mount, ...)


@dataclass(frozen=True, slots=True)
class UndoStep:
    """One file to put back: from ``current`` (where the run left it) to ``original``."""

    sha256: str
    current: Path
    original: Path


@dataclass(frozen=True, slots=True)
class UndoSkipped:
    step: UndoStep
    reason: UndoSkip
    detail: str = ""


@dataclass(frozen=True, slots=True)
class UndoPlan:
    """What reversing a run would do. Pure -- nothing is moved."""

    run_id: str
    source_root: Path
    dest_root: Path
    drive_uuid: str | None
    status: str
    steps: list[UndoStep]
    skipped: list[UndoSkipped]

    @property
    def restorable(self) -> int:
        return len(self.steps)


@dataclass(frozen=True, slots=True)
class UndoOutcome:
    plan: UndoPlan
    restored: int
    skipped: list[UndoSkipped]
    applied: bool


class UndoError(RuntimeError):
    """The requested run cannot be undone (unknown id, or already undone)."""


def _resolve_run(catalog: Catalog, run_id: str | None) -> tuple[str, Path, Path, str | None, str]:
    row = catalog.inplace_run(run_id) if run_id is not None else catalog.latest_undoable_run()
    if row is None:
        message = (
            f"no relocation run with id {run_id!r}"
            if run_id is not None
            else "no relocation run to undo -- nothing has been organized in place"
        )
        raise UndoError(message)
    if str(row["status"]) == "undone":
        message = f"run {row['run_id']} has already been undone"
        raise UndoError(message)
    return (
        str(row["run_id"]),
        Path(str(row["source_root"])),
        Path(str(row["dest_root"])),
        row["drive_uuid"],
        str(row["status"]),
    )


def plan_undo(
    catalog: Catalog,
    run_id: str | None = None,
    *,
    source_root: Path | None = None,
    dest_root: Path | None = None,
) -> UndoPlan:
    """Work out how to reverse a run. Reads the filesystem; writes nothing.

    ``source_root`` / ``dest_root`` override what the run recorded, for a drive that has since
    remounted somewhere else -- the journal stores relative paths precisely so this works.

    If a stored (or overridden) root is unreachable, raises :class:`UndoError` naming the path
    and the override flags - never a silent plan of all-MOVED_AWAY skips.
    """
    rid, recorded_source, recorded_dest, drive_uuid, status = _resolve_run(catalog, run_id)
    src_root = source_root or recorded_source
    dst_root = dest_root or recorded_dest

    problems: list[str] = []
    if not path_is_usable_dir(src_root):
        if source_root is None:
            problems.append(
                f"stored source root is unreachable: {recorded_source} "
                "(pass --source-root PATH to the current location)"
            )
        else:
            problems.append(f"source root is unreachable: {src_root}")
    if not path_is_usable_dir(dst_root):
        if dest_root is None:
            problems.append(
                f"stored dest root is unreachable: {recorded_dest} "
                "(pass --dest-root PATH to the current location)"
            )
        else:
            problems.append(f"dest root is unreachable: {dst_root}")
    if problems:
        raise UndoError("; ".join(problems))

    steps: list[UndoStep] = []
    skipped: list[UndoSkipped] = []
    # Reversed: a move that freed a path for a later one must unwind after it.
    for row in reversed(catalog.inplace_moves(rid)):
        step = UndoStep(
            sha256=str(row["sha256"]),
            current=dst_root / str(row["new_relative"]),
            original=src_root / str(row["old_relative"]),
        )
        if not step.current.is_file():
            skipped.append(
                UndoSkipped(step, UndoSkip.MOVED_AWAY, "no longer at the path this run left it")
            )
            continue
        if step.original.exists():
            skipped.append(
                UndoSkipped(step, UndoSkip.ORIGIN_OCCUPIED, "something else is there now")
            )
            continue
        steps.append(step)

    return UndoPlan(
        run_id=rid,
        source_root=src_root,
        dest_root=dst_root,
        drive_uuid=drive_uuid,
        status=status,
        steps=steps,
        skipped=skipped,
    )


def run_undo(
    catalog: Catalog,
    plan: UndoPlan,
    *,
    apply: bool = False,
    progress: ProgressCallback | None = None,
) -> UndoOutcome:
    """Put each file back, then forget the copies the run recorded.

    Dry run by default. Catalog state is corrected per file *after* its rename succeeds, so an
    interruption leaves the catalog describing exactly the files that actually moved back.
    """
    if not apply:
        return UndoOutcome(plan=plan, restored=0, skipped=plan.skipped, applied=False)

    restored = 0
    skipped = list(plan.skipped)
    total = len(plan.steps)
    for done, step in enumerate(plan.steps, start=1):
        # Re-check immediately before moving: the preview may be minutes old, and the
        # never-overwrite rule has to hold at the moment of the write, not at planning time.
        if not step.current.is_file():
            skipped.append(UndoSkipped(step, UndoSkip.MOVED_AWAY, "disappeared before undo"))
            continue
        if step.original.exists():
            skipped.append(UndoSkipped(step, UndoSkip.ORIGIN_OCCUPIED, "occupied before undo"))
            continue
        try:
            step.original.parent.mkdir(parents=True, exist_ok=True)
            step.current.rename(step.original)
        except OSError as exc:
            skipped.append(UndoSkipped(step, UndoSkip.FAILED, str(exc)))
            continue

        # Drops this drive's copy record, and the file row with it when no copy remains --
        # otherwise the content still looks organized and a re-organize would skip every
        # restored file as an exact duplicate.
        catalog.forget_organized(step.sha256, plan.drive_uuid)
        restored += 1
        if progress is not None:
            progress(Progress(done, total, Phase.RESTORING, step.original.name))

    # Only a *complete* reversal closes the run. Leaving a partial one open is deliberate: its
    # remaining journal rows are still valid, so once the user resolves whatever blocked them
    # (an occupied path, a disconnected drive) a second `undo` finishes the job. Files already
    # restored are simply skipped as MOVED_AWAY on that second pass, so retrying is safe.
    if not skipped:
        catalog.finish_inplace_run(plan.run_id, status="undone")
    return UndoOutcome(plan=plan, restored=restored, skipped=skipped, applied=True)
