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

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Final

from truestill_core.catalog import Catalog
from truestill_core.drive import path_is_usable_dir
from truestill_core.hashing import sha256_file
from truestill_core.progress import Phase, Progress, ProgressCallback


class UndoSkip(StrEnum):
    """Why one file could not be put back."""

    MOVED_AWAY = "moved_away"  # not at the path the run left it -- moved or deleted since
    ORIGIN_OCCUPIED = "origin_occupied"  # something else now sits where it came from
    FAILED = "failed"  # the rename itself failed (permissions, read-only mount, ...)
    #: What is at the path is not what the row describes. `(agk)` Ruling 2: since the journal
    #: became an INTENT log, a row can name a rename that never happened - and the path it names
    #: may since have been taken, legitimately, by a different file. Position is not identity.
    NOT_THE_SAME_FILE = "not_the_same_file"
    #: The row records a fallback COPY rather than a rename. The copy path removed the source
    #: only after re-hashing the destination, so it needs no undo row and this one describes
    #: nothing to reverse.
    WAS_A_COPY = "was_a_copy"
    #: Identity could not be established, so nothing is moved. Never a silent pass.
    UNREADABLE = "unreadable"
    #: The intent was recorded and the rename never happened - the file is still where it
    #: started. ⚠ **NOT A FAILURE**: there is nothing to put back. It exists because an intent
    #: log can say "unknown", and the disk can then answer.
    NEVER_MOVED = "never_moved"


class SkipClass(StrEnum):
    """What a skip means for the two decisions that hang off it. `(agk)` follow-up.

    ⚠ **THE DISCRIMINATOR IS NOT "IS THIS A FAILURE". It is: can re-running undo do any more?**
    `run_undo` keeps a partial reversal open precisely so *"a second `undo` finishes the job"*
    once the user has resolved what blocked it. A run held open on something that can never clear
    is a promise the product cannot keep - `still_armed` stays true forever and every later undo
    restores nothing.

    Three classes, two behaviours, and the third exists because a **record** has to tell them
    apart even where the exit code does not: *"something else is there now"* and *"we could not
    do it"* are different facts about the drive, and `(afa)` is what happens when several facts
    share one word.
    """

    #: Nothing was outstanding and nothing ever will be. Does not hold the run open, does not
    #: spend the exit code. A second undo cannot change these.
    NOTHING_TO_DO = "nothing_to_do"
    #: The world moved under the run. The user can act - reconnect the drive, clear the path -
    #: and re-run, so the run stays open and the exit code says so.
    RESOLVABLE = "resolvable"
    #: Attempted and could not be done. Holds the run open for the same reason, and is reported
    #: differently because it is our failure to perform rather than the drive having changed.
    COULD_NOT = "could_not"


#: ⚠ **Exhaustive, and `test_every_skip_reason_is_classified` is what keeps it so.** Nothing type
#: checks a mapping, so a new `UndoSkip` member would otherwise fall through to whatever default
#: `classify` has - deciding both the exit code and whether the run closes by omission.
_CLASS_OF: Final[dict[UndoSkip, SkipClass]] = {
    UndoSkip.NEVER_MOVED: SkipClass.NOTHING_TO_DO,
    UndoSkip.WAS_A_COPY: SkipClass.NOTHING_TO_DO,
    UndoSkip.MOVED_AWAY: SkipClass.RESOLVABLE,
    UndoSkip.ORIGIN_OCCUPIED: SkipClass.RESOLVABLE,
    UndoSkip.NOT_THE_SAME_FILE: SkipClass.RESOLVABLE,
    UndoSkip.FAILED: SkipClass.COULD_NOT,
    UndoSkip.UNREADABLE: SkipClass.COULD_NOT,
}


def classify(reason: UndoSkip) -> SkipClass | None:
    """What this skip means, or ``None`` if nobody has said - which is a defect, not a default."""
    return _CLASS_OF.get(reason)


def outstanding(skipped: Sequence[UndoSkipped]) -> list[UndoSkipped]:
    """The skips that represent work left to do. **One definition, two callers.**

    The exit code and the close condition are two readings of one question, and the CLI derived
    its own answer inline until `(agk)`'s regressions were fixed. Two copies of a rule is how the
    copies disagree - here it would mean a run that closes while the command reports failure.

    ⚠ **An unclassified reason counts as outstanding.** Unknown must mean "needs a human", never
    "nothing to do": the safe direction is the one that keeps the run re-runnable.
    """
    return [item for item in skipped if classify(item.reason) is not SkipClass.NOTHING_TO_DO]


@dataclass(frozen=True, slots=True)
class UndoStep:
    """One file to put back: from ``current`` (where the run left it) to ``original``."""

    sha256: str
    current: Path
    original: Path
    #: The size recorded with the intent, when there was one. The **free** half of identity: it
    #: can reject a mismatch without opening the file and can never confirm one, so a match
    #: still costs a hash. NULL for rows written before `(agk)`.
    size: int | None = None
    #: ``'renamed'`` / ``'copied'`` / ``None``. ⚠ **``None`` is UNKNOWN, never "did not
    #: happen"** - a crash between the rename and the write-back leaves it, over a file that
    #: really did move. Only the disk settles it, which is what the checks below do.
    outcome: str | None = None


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
            size=row["size"],
            outcome=row["outcome"],
        )
        verdict = _why_not(step)
        if verdict is not None:
            skipped.append(verdict)
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


def _why_not(step: UndoStep) -> UndoSkipped | None:
    """Why this row cannot be reversed, or ``None`` if it can. `(agk)`

    ⚠ **THE JOURNAL IS AN INTENT LOG, SO NOTHING HERE MAY TRUST THE ROW.** Every question is
    answered by looking at the disk. A row with no outcome is **unknown**, not "did not happen":
    a crash between the rename and the write-back leaves exactly that over a file that moved, and
    treating it as nothing-to-do would put the `(agk)` defect back one layer up.

    **Order matters and is cheapest-first**: position, then size, then the hash. Size can only
    ever *reject* - two files of one length are routine - so a match still costs a read.
    """
    if step.outcome == "copied":
        # Not a rename at all. `organizer._move_source` verified the destination copy before
        # removing the source, so the file is accounted for and this row describes no move.
        return UndoSkipped(step, UndoSkip.WAS_A_COPY, "this file was copied, not renamed")
    if not step.current.is_file():
        if step.outcome is None and step.original.is_file():
            # ⚠ **The "unknown" outcome, settled by the disk.** Nothing is at the new path and
            # the file is still at the old one, so the rename never happened - which an intent
            # log can express and a completed-moves log could not. Reporting this as *"no longer
            # at the path this run left it"* would be false: the run never left it anywhere.
            return UndoSkipped(
                step, UndoSkip.NEVER_MOVED, "was never moved; it is still where it started"
            )
        return UndoSkipped(step, UndoSkip.MOVED_AWAY, "no longer at the path this run left it")
    if step.original.exists():
        return UndoSkipped(step, UndoSkip.ORIGIN_OCCUPIED, "something else is there now")
    return _identity_check(step)


def _identity_check(step: UndoStep) -> UndoSkipped | None:
    """Is the file at ``current`` the one this row describes? `(agk)` Ruling 2.

    ⚠ **`organizer._move_source` already re-hashes before it unlinks a source**, and this is the
    same product performing the same user action - so undo checking only *position* would be a
    second divergence on top of the ordering one `(agk)` exists to close. The user is reversing a
    destructive act on files that may be their only copy; this is where a read is worth paying
    for.

    ⚠ **Unreadable is a REFUSAL, not a pass.** Failing open here would move a file whose identity
    could not be established, which is the one outcome undo must never produce.
    """
    try:
        actual = step.current.stat().st_size
    except OSError as exc:
        return UndoSkipped(step, UndoSkip.UNREADABLE, f"could not be read to confirm it: {exc}")
    if step.size is not None and actual != step.size:
        # Free rejection: a different length is a different file, and no hash is needed to say so.
        return UndoSkipped(
            step,
            UndoSkip.NOT_THE_SAME_FILE,
            f"a different file is at this path now ({actual} bytes, not {step.size})",
        )
    try:
        digest = sha256_file(step.current)
    except OSError as exc:
        return UndoSkipped(step, UndoSkip.UNREADABLE, f"could not be read to confirm it: {exc}")
    if digest != step.sha256:
        return UndoSkipped(step, UndoSkip.NOT_THE_SAME_FILE, "a different file is at this path now")
    return None


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
        # ⚠ **The SAME predicate as the plan, identity included** (`(agk)`). Re-checking only
        # position here would mean the hash was a planning-time opinion about a file that can
        # change afterwards - and the window is exactly the one this re-check exists for.
        verdict = _why_not(step)
        if verdict is not None:
            skipped.append(verdict)
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
    # ⚠ **`outstanding`, not `skipped`.** A run held open on something a second undo can never
    # resolve leaves `still_armed` true forever, on the one path where a wrong state costs most.
    if not outstanding(skipped):
        catalog.finish_inplace_run(plan.run_id, status="undone")
    return UndoOutcome(plan=plan, restored=restored, skipped=skipped, applied=True)
