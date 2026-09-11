"""Recover: the panel over `truestill_core.recover`. Restore stage 3.

⚠ **THE ENGINE IS CORE'S AND NOTHING HERE COPIES A FILE.** What lives in this module is the
transport: the payload a screen renders, the drive resolution that precedes a run, and the
assembly of a summary from what the engine returns - the same core-computes/app-wraps line
`service/backup.py` draws over `copy_to_drive`.

⚠ **AND NO SENTENCE IS RETYPED HERE.** `recover.NOTHING_IS_LOST`, `DRIVE_IS_READ_ONLY`,
`SKIP_REASONS` and `NEVER_WALKED` are core constants, shipped as payload keys, because the
terminal and the drive card must reassure a frightened user in identical words. `app.js` renders
text it was handed and words nothing itself.

**Why the preview is a JOB and backup's is not.** `plan_recovery` stats the whole library -
measured at **85% of 896 ms** over 40,000 files on local ext4, so seconds on USB or a network
mount. The recorded complaint about Time Machine's restore is that window: *a minute with no
indication anything is happening*. A plain POST would reproduce it exactly, so this one gets the
run block eight other mounts already share.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Literal, NotRequired, TypedDict

from truestill_core.drive import read_marker
from truestill_core.progress import ProgressCallback
from truestill_core.recover import (
    DRIVE_IS_READ_ONLY,
    NEVER_WALKED,
    NOTHING_IS_LOST,
    SKIP_REASONS,
    RecoverPair,
    Skipped,
    plan_recovery,
    recover_into_library,
)

from truestill_app.jobs import JobTarget
from truestill_app.service.drive_support import not_a_drive
from truestill_app.service.media_support import media_breakdown

#: ⚠ **Re-exported so `server.py` never imports core**, which `test_app_core_import_boundary`
#: enforces: an app module outside `service/` must reach core through this layer. The values are
#: core's and are not restated here - `home()` substitutes them into the markup so the
#: reassurance is on screen before the user touches a field.
RECOVER_NOTHING_IS_LOST = NOTHING_IS_LOST
RECOVER_DRIVE_IS_READ_ONLY = DRIVE_IS_READ_ONLY


class RecoverPreviewErr(TypedDict):
    ok: Literal[False]
    error: str


class RecoverPreviewOk(TypedDict):
    ok: Literal[True]
    drive: str
    library: str
    count: int
    photos: int
    videos: int
    audio: int
    bytes: int
    #: ⚠ False when `file_copies` holds nothing for this drive - **nobody walked it**, which is
    #: not the same as it being empty. The worst wrong answer in the product is reporting
    #: "nothing to bring back" about a drive holding a whole library.
    drive_walked: bool
    #: Core's sentence for that state, empty when it does not apply. The screen renders it.
    never_walked: str
    #: The two reassurances, always present, always from core.
    nothing_is_lost: str
    drive_is_read_only: str


class RecoverRunSummary(TypedDict):
    copied: int
    drive: str
    library: str
    photos: int
    videos: int
    audio: int
    bytes_copied: int
    #: Files deliberately not copied, by reason - ``{reason sentence: count}``. **Skips are not
    #: failures**, and the split is what stops a user hunting a defect that is not there.
    skipped: dict[str, int]
    failed: int
    #: Whether the run left nothing undone. `jobs.py` reads it for the terminal status. A skip
    #: does NOT make a run unclean: leaving a file alone is the rule working.
    finished_clean: bool
    nothing_is_lost: str
    elapsed_seconds: NotRequired[float]


def _pair_or_error(drive: Path, library: Path) -> RecoverPair | str:
    """Resolve both sides, or the sentence to show instead. **Refuses; never registers.**

    `_cmd_recover`'s rule and for its reason: registering is a distinct act with its own ghost
    guard, and a read-then-write command that mints a drive id as a side effect is how a ghost
    drive is created. Unlike `backup_preview`, nothing here can be *offered* registration -
    there is nothing to recover from a folder truestill has never recorded.
    """
    if not drive.is_dir():
        return "That drive folder was not found. Is it plugged in and mounted?"
    if not library.is_dir():
        return "That library folder was not found. Check the path, then pick an existing folder."
    drive_marker, library_marker = read_marker(drive), read_marker(library)
    if drive_marker is None or library_marker is None:
        missing = drive if drive_marker is None else library
        return str(not_a_drive(missing, Path()))
    if drive_marker.uuid == library_marker.uuid:
        return "That is the same drive twice. Pick the drive you want to bring photos back from."
    return RecoverPair(
        drive=drive, drive_marker=drive_marker, library=library, library_marker=library_marker
    )


def recover_preview(
    drive: Path, library: Path, db: Path
) -> JobTarget[RecoverPreviewOk | RecoverPreviewErr]:
    """Build a job that answers what this drive is carrying. **Writes nothing.**

    A job rather than a request because the answer costs a walk of the library - see the module
    note. The refusal cases are returned as a payload rather than raised, so a screen renders a
    sentence instead of an error card.
    """

    def target_job(
        progress: ProgressCallback,
        cancel: threading.Event,  # noqa: ARG001 - the shape `JobTarget` requires; see below
    ) -> RecoverPreviewOk | RecoverPreviewErr:
        # ⚠ **Accepted and unused, and that is honest rather than sloppy.** The gap computation
        # is one blocking call inside the reused engine, so there is no loop to check a flag
        # between - a `cancel` this function consulted would stop nothing. Threading one through
        # would mean reimplementing the comparison, which is the second implementation of the
        # product's most safety-critical set difference. Named in the UI instead: the run block
        # for a preview offers no Cancel, because offering one that cannot work is worse.
        pair = _pair_or_error(drive, library)
        if isinstance(pair, str):
            return RecoverPreviewErr(ok=False, error=pair)
        plan = plan_recovery(pair, db, progress=progress)
        breakdown = media_breakdown([row.relative for row in plan.gaps])
        return RecoverPreviewOk(
            ok=True,
            drive=plan.drive_label,
            library=plan.library_label,
            count=plan.count,
            photos=breakdown["photos"],
            videos=breakdown["videos"],
            audio=breakdown["audio"],
            bytes=plan.bytes_needed,
            drive_walked=plan.drive_walked,
            never_walked="" if plan.drive_walked else NEVER_WALKED,
            nothing_is_lost=NOTHING_IS_LOST,
            drive_is_read_only=DRIVE_IS_READ_ONLY,
        )

    return target_job


def recover_run(drive: Path, library: Path, db: Path) -> JobTarget[RecoverRunSummary]:
    """Build a job that copies the gap into the library. **Adds only; deletes nothing.**"""

    def target_job(progress: ProgressCallback, cancel: threading.Event) -> RecoverRunSummary:
        pair = _pair_or_error(drive, library)
        if isinstance(pair, str):
            # A sentence for a person, not a type error: `jobs.py` ships `str(exc)` to the
            # browser as the terminal event's message.
            raise ValueError(pair)  # noqa: TRY004 - the payload is prose, never a type
        outcome = recover_into_library(pair, db, progress=progress, cancel=cancel)
        breakdown = media_breakdown(outcome.copied_names)
        return {
            "copied": outcome.copied,
            "drive": pair.drive_marker.label,
            "library": pair.library_marker.label,
            "photos": breakdown["photos"],
            "videos": breakdown["videos"],
            "audio": breakdown["audio"],
            "bytes_copied": outcome.bytes_copied,
            "skipped": _skips(outcome.skipped),
            "failed": len(outcome.failures),
            # ⚠ **A SKIP DOES NOT MAKE A RUN UNCLEAN**, and that is the whole split. Leaving a
            # file alone because something is already at its path is the never-overwrite rule
            # working; reporting it as unfinished would teach a user to distrust the one
            # behaviour that makes this safe. Only a failure - work truestill should have
            # managed and did not - marks the run.
            "finished_clean": not outcome.failures,
            "nothing_is_lost": NOTHING_IS_LOST,
        }

    return target_job


def _skips(skipped: list[tuple[str, Skipped]]) -> dict[str, int]:
    """Skips grouped by core's sentence for them, so the screen adds no wording of its own."""
    counts: dict[str, int] = {}
    for _relative, reason in skipped:
        sentence = SKIP_REASONS[reason]
        counts[sentence] = counts.get(sentence, 0) + 1
    return counts
