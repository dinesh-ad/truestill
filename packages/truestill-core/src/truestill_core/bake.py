"""Writing a human-confirmed date into the copies on a drive. `(ahd)` step 1.

**Why this is in core.** `PROJECT_STATUS.md` §1b: the engine finishes first and every behaviour
lives where both front-ends can reach it. Until 2026-08-25 the whole bake lived in
`truestill_app.service.bake`, so it was the one mutating run with **no CLI** - and
`truestill-cli` cannot import `truestill_app` (`IMPLEMENTATION_STANDARDS.md` §2). Same reason
`drive.drive_path_hint` and `drive.drive_identity` already give for sitting here.

⚠ **THE THREE FUNCTIONS NAMED IN `(ahd)` COULD NOT MOVE INTACT, and that is a finding rather than
a shortcut.** `bake_run`, `bake_preview` and `bake_preconditions` return `DriveUnavailablePayload`
- a **UI correction payload** carrying `suggested_root` and `can_register`, which is a button on a
screen. Moving them whole would have dragged an app affordance into core, which is the direction
`IMPLEMENTATION_STANDARDS.md` §2 forbids and which nothing structurally prevents once it is
imported. So the line is drawn where `drive_identity` draws it: **core computes and returns a core
value; the app wraps it into its payload.**

**What lives here** - everything a CLI would need, and the test is exactly that question:

* the vocabulary both surfaces must agree on - :data:`CONFIRM_WORD`, :data:`IRREVERSIBLE_NOTE`,
  :data:`VIDEO_EXCLUSION_REASON`, :func:`migration_unfinished_message`, :func:`completeness_line`.
  A sentence spelled twice in two packages is the drift `MIGRATE_CARD_NAME` already cost once;
* the predicates - :func:`is_video`, :func:`migration_unfinished`, :func:`unconfirmed_reason`;
* **the irreversible write loop itself**, :func:`bake_confirmed_dates`.

**What stays in `truestill_app.service.bake`**: `BakeRefusal`, `BakeSummary`, `BakePreview` and
the mapping onto `DriveUnavailablePayload` - transport shapes a CLI has no use for.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Final, TypedDict

from truestill_core.catalog import Catalog
from truestill_core.catalog_session import open_catalog
from truestill_core.drive import DriveMarker
from truestill_core.exif import build_metadata_args, write_metadata_batch
from truestill_core.hashing import sha256_file
from truestill_core.organizer import VIDEO_EXTENSIONS
from truestill_core.progress import Phase, Progress, ProgressCallback

#: The guard runs before **every** file, not once per run. Read by
#: `test_the_toctou_gap_is_narrowed_not_closed`, so the narrowing is pinned rather than promised.
CHECKS_PER_FILE = True

#: The word a user types to authorise the write. Distinct from every other confirm word in the
#: product (`undo`, `clean`, `move`, `delete`, `delete forever`) because the actions are
#: different and a muscle-memory word typed on the wrong screen is not a confirmation.
CONFIRM_WORD: Final = "set dates"


def unconfirmed_reason(confirmation: str) -> str | None:
    """Why this run may not proceed, or ``None`` when the word matches. `(ahe)`

    ⚠ **The caller passes it; nothing here defaults it.** `(ahe)` fixed a bake that could be
    started with no confirmation at all because the typed word never left the browser, and the
    guard that fix installed is `bake_run`'s **defaultless** parameter. Moving the check into core
    must not hand back the default the move was meant to generalise: a CLI that could omit the
    argument is the same hole in a second surface.
    """
    if confirmation == CONFIRM_WORD:
        return None
    return f"This run was not confirmed. It needs the words {CONFIRM_WORD!r}."


#: Why a confirmed video keeps its catalog date but is not written to.
VIDEO_EXCLUSION_REASON = (
    "Videos keep the date you set, but truestill does not write it into the video file yet. "
    "The date is safe in your library and survives reorganizing; only the file's own internal "
    "date is left alone, because writing video files needs testing against real camera "
    "footage first."
)


IRREVERSIBLE_NOTE = (
    "This changes the date stored inside each photo file. The date it had before is not kept, "
    "so this cannot be undone from inside truestill."
)


def is_video(relative: str) -> bool:
    """Whether this copy is one of the containers the bake leaves alone."""
    return Path(relative).suffix.lower() in VIDEO_EXTENSIONS


def migration_unfinished(catalog: Catalog, drive_uuid: str) -> bool:
    """Whether a migration on this drive is journalled and not yet completed.

    ``pending_migration`` returns rows with ``completed_at IS NULL`` only. Completed rows stay
    in the table as the record undo reverses from, so keying on *presence* would refuse a bake
    on every drive that had ever been migrated. This keys on the pending **state**.

    Reading the journal is what makes the check work across processes: the app's own job lock is
    in memory (`(vv)`), and a check that only sees its own process is not a check.
    """
    return bool(catalog.pending_migration(drive_uuid))


def migration_unfinished_message(drive_label: str) -> str:
    """Why the bake will not start, and the two things that resolve it.

    Both ways out are named because they are genuinely different choices: finishing applies the
    move the journal is holding, undoing puts it back. Telling someone only that a migration is
    "in progress" leaves them to guess which, on the drive holding their photos.

    **The word is "migration" because that is what this app already calls it** - the undo
    affordance on Trips and Settings reads *"Undo the last migration"*, so the second way out
    names the button the user is being sent to. "Reorganize" would have been plainer in the
    abstract and wrong here: it is this UI's word for in-place organize, a *different*
    operation with a different undo, which is the exact confusion `(pp)` was raised about.
    """
    return (
        f"{drive_label} has an unfinished migration. Writing dates into the photos now could "
        f"make that migration fail partway and report damage on a file truestill itself "
        f"rewrote. Finish the migration, or undo it, and then set the dates."
    )


class DriveAwaiting(TypedDict):
    """A drive that still holds the old date inside its copies. O2's partial-by-nature fact."""

    label: str
    files: int


def completeness_line(drive_label: str, baked: int, awaiting: list[DriveAwaiting]) -> str:
    """Whether this finished the job, in one sentence, naming what is left.

    **A partial bake must not read as a completed one.** Listing what succeeded and saying
    nothing about the rest is how a user concludes their whole library is done - so the
    unfinished half is stated in the same breath as the finished one, with the drives named and
    what to do about them, because nothing picks them up on its own.
    """
    written = f"{baked} {'file' if baked == 1 else 'files'}"
    if not awaiting:
        return (
            f"Done. The dates are written into {written} on {drive_label}, and every other copy "
            f"truestill knows about already has them."
        )
    names = [
        f"{d['label']} ({d['files']} {'file' if d['files'] == 1 else 'files'})" for d in awaiting
    ]
    listed = names[0] if len(names) == 1 else ", ".join(names[:-1]) + f" and {names[-1]}"
    return (
        f"Partly done. The dates are now in {written} on {drive_label}. Copies on {listed} "
        f"still have the old date inside them - the corrected date is safe in your library "
        f"either way, but to put it into those files, connect each drive and set the dates again."
    )


@dataclass(frozen=True, slots=True)
class BakeOutcome:
    """What one bake did. **A core value, not a payload** - the app shapes it for a screen.

    `refused` is the mid-run stop: another process journalled a migration while this was running.
    """

    drive_label: str
    baked: int
    failed: int
    absent: int
    videos_skipped: int
    awaiting: list[DriveAwaiting]
    completeness: str
    refused: str | None


def bake_confirmed_dates(
    root: Path,
    db: Path,
    marker: DriveMarker,
    *,
    progress: ProgressCallback | None,
    cancel: threading.Event,
) -> BakeOutcome:
    """Write every confirmed date into this drive's copies, one file at a time.

    **One file at a time on purpose:** each write is followed by its own read-back and its own
    single-transaction record, so an interruption leaves every finished file correct and every
    unfinished one untouched. Batching would be faster and would make a crash mid-batch ambiguous
    about which files had been rewritten.

    ⚠ **This is the only path in the product that runs `-overwrite_original` and keeps no
    sidecar.** The date a file carried before is gone once it returns.
    """
    drive_uuid, drive_label = marker.uuid, marker.label
    baked = failed = absent = videos_skipped = 0
    refused: str | None = None
    with open_catalog(db) as catalog:
        pending = catalog.confirmations_to_bake(drive_uuid)
        total = len(pending)
        for index, row in enumerate(pending, start=1):
            if cancel.is_set():
                break
            # Re-checked per file: another process can journal a migration at any moment, and
            # this is the narrowest window a check can achieve (see :data:`CHECKS_PER_FILE`).
            if migration_unfinished(catalog, drive_uuid):
                refused = migration_unfinished_message(drive_label)
                break
            relative = str(row["relative"])
            target_file = root / relative
            # Every item ticks, including the ones nothing is written for. Progress that only
            # advances on success stalls on a run of skips and reads as a hang - the (oo)
            # finding, which is about hidden *work* rather than hidden errors.
            if progress is not None:
                progress(Progress(index, total, Phase.ORGANIZING, target_file.name))
            if is_video(relative):
                videos_skipped += 1
                continue
            if not target_file.is_file():
                absent += 1
                continue
            args = build_metadata_args(
                taken_at_local=datetime.fromisoformat(str(row["captured_at"]))
            )
            # ⚠ **THE INTENT, BEFORE THE IRREVERSIBLE STEP** (`(agv)`, `(agk)`'s shape). From here
            # until `record_bake`, the recorded `copy_sha256` describes bytes that are about to
            # stop existing - and a crash in that window used to leave `verify` reporting
            # MISMATCH, a tool reporting corruption on a file it rewrote itself. The mark is what
            # lets a reader say *unknown* instead of *corrupt*.
            catalog.begin_bake(str(row["sha256"]), drive_uuid)
            verdicts = write_metadata_batch([(target_file, args)])
            if not verdicts.get(target_file, False):
                # Unconfirmed is failed, never assumed fine: the same rule the Takeout bake
                # applies. The catalog hash is left alone, so verify keeps checking against what
                # is really recorded for this copy.
                # ⚠ **And the mark comes back off**: exiftool declining leaves the file untouched,
                # so this copy is still exactly what the catalog says it is. A refusal is not an
                # interruption, and holding the mark would trade a false alarm for a false silence.
                catalog.abandon_bake(str(row["sha256"]), drive_uuid)
                failed += 1
                continue
            # O1: read back from the file ON THE DRIVE, after the write - never the staged copy,
            # never exiftool's report - then record it with the bake in one transaction.
            catalog.record_bake(
                str(row["sha256"]), drive_uuid, copy_sha256=sha256_file(target_file)
            )
            baked += 1
        awaiting: list[DriveAwaiting] = [
            {"label": str(r["label"]), "files": int(r["files"])}
            for r in catalog.drives_awaiting_bake(drive_uuid)
        ]
    return BakeOutcome(
        drive_label=drive_label,
        baked=baked,
        failed=failed,
        absent=absent,
        videos_skipped=videos_skipped,
        awaiting=awaiting,
        completeness=completeness_line(drive_label, baked, awaiting),
        refused=refused,
    )
