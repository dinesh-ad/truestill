"""Preconditions for baking a confirmed date into the copies on a drive (step 4, condition 3).

**What this module does.** Writes a confirmed date into the copies on a connected drive, and
refuses - before the run and again before every file - while a migration is unfinished on that
drive. The refusal was built first, on purpose: it is the condition that had to be settled
before anything wrote to a user's drive at all.

**O1, the obligation this feature turns on: the recorded hash is read back from the file ON THE
DRIVE, after the write, and lands in the same transaction as the bake record**
(`Catalog.record_bake`). Never from a staged copy, and never from what exiftool reported. A
staged copy is not the file `verify` will re-read, and exiftool's "1 image files updated" says a
write was accepted, not what the bytes now hash to. On a network mount a destination can also
become visible before it has settled, which is the third way a hash taken anywhere but from the
final file can be a confident lie. Get this wrong and `verify` tells a user their photo is
damaged when truestill rewrote it - the worst failure this feature has.

**Videos are excluded from the bake, and the exclusion is stated, not silent.** A video whose
date is confirmed keeps its catalog record - step 3's durability, which works and is untouched -
and simply does not get written. The reason is on the record below.

**The window it closes.** `run_migration` snapshots each copy's ``copy_sha256`` at plan time into
``migration_journal`` and verifies relocated files against that snapshot, never a fresh read. A
bake rewrites the bytes and updates ``file_copies.copy_sha256`` in the same transaction (O1),
which makes the snapshot stale. `_apply_move` then relocates the file and mismatches, raising
``verification failed after relocating``. The file survives - `relocate` copies rather than
renames - but the migration stalls permanently (a resume repeats the same comparison), an orphan
copy is left at the new path, and the user is shown the word "verification" about a file
truestill itself rewrote.

**Why a check here rather than a lock.** The app's per-drive job lock already covers app-vs-app
completely: every job route goes through ``server._start_drive_job``, which keys on
``uuid:<marker uuid>``. It is process-local **by design** (`BACKLOG.md` **(vv)**), so a CLI
``migrate-layout`` beside an app bake is not serialized at all. The journal, unlike the lock,
lives in the shared catalog and every process can read it.

**This narrows the race; it does not close it.** Between a check and the write that follows it,
another process can still journal a migration. Re-checking before *every file* reduces the
exposure from the length of a run to the gap around a single write, which is the best a check
can do. Closing it needs a cross-process on-disk lock (flock on the drive marker or the
catalog); that is **(vv)**'s design, it is a different piece of work, and it must not be
smuggled in here.
"""

from __future__ import annotations

import threading
from datetime import datetime
from pathlib import Path
from typing import Literal, NotRequired, TypedDict

from truestill_core.catalog import Catalog
from truestill_core.drive import read_marker
from truestill_core.exif import build_metadata_args, write_metadata_batch
from truestill_core.hashing import sha256_file
from truestill_core.organizer import VIDEO_EXTENSIONS
from truestill_core.progress import Phase, Progress, ProgressCallback

from truestill_app.jobs import JobTarget
from truestill_app.service.drive_support import DriveUnavailablePayload, drive_unavailable

#: The guard runs before **every** file, not once per run. Read by
#: `test_the_toctou_gap_is_narrowed_not_closed`, so the narrowing is pinned rather than promised.
CHECKS_PER_FILE = True


class BakeRefusal(TypedDict):
    """A refusal the UI can render as-is. Same shape as every other soft failure."""

    ok: Literal[False]
    error: str
    code: Literal["MigrationUnfinished"]
    drive_label: str


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


def migration_unfinished(catalog: Catalog, drive_uuid: str) -> bool:
    """Whether a migration on this drive is journalled and not yet completed.

    ``pending_migration`` returns rows with ``completed_at IS NULL`` only. Completed rows stay
    in the table as the record undo reverses from, so keying on *presence* would refuse a bake
    on every drive that had ever been migrated. This keys on the pending **state**.

    Reading the journal is what makes the check work across processes: the app's own job lock is
    in memory (`(vv)`), and a check that only sees its own process is not a check.
    """
    return bool(catalog.pending_migration(drive_uuid))


def bake_preconditions(path: Path, db: Path) -> BakeRefusal | DriveUnavailablePayload | None:
    """``None`` when a bake may proceed, else the refusal to show. Reads only.

    Called once before the run *and again before each file* - see :data:`CHECKS_PER_FILE` and
    the module docstring for what that does and does not buy.
    """
    marker = read_marker(path)
    if marker is None:
        return drive_unavailable(path)
    with Catalog(db) as catalog:
        if migration_unfinished(catalog, marker.uuid):
            return {
                "ok": False,
                "error": migration_unfinished_message(marker.label),
                "code": "MigrationUnfinished",
                "drive_label": marker.label,
            }
    return None


#: Why a confirmed video keeps its catalog date but is not written to.
#:
#: **Measured null result, 2026-07-31 (CI run 30640215762).** truestill's video metadata write
#: was verified on **Ubuntu, macOS and Windows**: the write is confirmed, the bytes change, the
#: container stays readable and returns the tag, no ``_original`` sidecar appears, and the source
#: of a copy is untouched. **No atom-rewrite difference, no ``-overwrite_original`` divergence,
#: no copy-only violation on any platform.**
#:
#: So the exclusion does **not** rest on "Windows may differ" - that was the fear, it was
#: measured, and it is false. It rests on the narrower and still-true fact that this path had
#: **no test at all** until the run above, and one green run over a 1.5 KB synthetic container is
#: not the same evidence as real camera files with MakerNotes whose offsets exiftool must
#: relocate. Whoever lifts this needs *that* corpus, not another platform matrix.
VIDEO_EXCLUSION_REASON = (
    "Videos keep the date you set, but truestill does not write it into the video file yet. "
    "The date is safe in your library and survives reorganizing; only the file's own internal "
    "date is left alone, because writing video files needs testing against real camera "
    "footage first."
)


class BakeSummary(TypedDict):
    """What a bake actually did. Every outcome counted separately (§9)."""

    drive_label: str
    baked: int
    #: Confirmed, catalog record intact, file deliberately not written. Named, never silent.
    videos_skipped: int
    videos_reason: str
    #: Present but the write was not confirmed by exiftool: reported, never assumed fine.
    failed: int
    #: The copy named by the catalog is not on the drive.
    absent: int
    #: Stopped because a migration started on this drive mid-run.
    refused: NotRequired[str]
    elapsed_seconds: NotRequired[float]


def _is_video(relative: str) -> bool:
    return Path(relative).suffix.lower() in VIDEO_EXTENSIONS


def bake_run(path: Path, db: Path) -> JobTarget | DriveUnavailablePayload | BakeRefusal:
    """Build a job that writes confirmed dates into this drive's copies.

    One file at a time on purpose: each write is followed by its own read-back and its own
    single-transaction record, so an interruption leaves every finished file correct and every
    unfinished one untouched. Batching the writes would be faster and would make a crash
    mid-batch ambiguous about which files had been rewritten.
    """
    refusal = bake_preconditions(path, db)
    if refusal is not None:
        return refusal
    marker = read_marker(path)
    if marker is None:  # pragma: no cover - bake_preconditions already answered this
        return drive_unavailable(path)

    def target(progress: ProgressCallback, cancel: threading.Event) -> BakeSummary:
        summary: BakeSummary = {
            "drive_label": marker.label,
            "baked": 0,
            "videos_skipped": 0,
            "videos_reason": VIDEO_EXCLUSION_REASON,
            "failed": 0,
            "absent": 0,
        }
        with Catalog(db) as catalog:
            pending = catalog.confirmations_to_bake(marker.uuid)
            total = len(pending)
            for index, row in enumerate(pending, start=1):
                if cancel.is_set():
                    break
                # Re-checked per file: another process can journal a migration at any moment,
                # and this is the narrowest window a check can achieve (see the module docstring).
                if migration_unfinished(catalog, marker.uuid):
                    summary["refused"] = migration_unfinished_message(marker.label)
                    break
                relative = str(row["relative"])
                if _is_video(relative):
                    summary["videos_skipped"] += 1
                    continue
                target_file = path / relative
                if not target_file.is_file():
                    summary["absent"] += 1
                    continue
                args = build_metadata_args(
                    taken_at_local=datetime.fromisoformat(str(row["captured_at"]))
                )
                verdicts = write_metadata_batch([(target_file, args)])
                if not verdicts.get(target_file, False):
                    # Unconfirmed is failed, never assumed fine: the same rule the Takeout bake
                    # already applies. The catalog hash is left alone, so verify keeps checking
                    # against what is really recorded for this copy.
                    summary["failed"] += 1
                    continue
                # O1: read back from the file ON THE DRIVE, after the write - never the staged
                # copy, never exiftool's report - then record it with the bake in one transaction.
                catalog.record_bake(
                    str(row["sha256"]), marker.uuid, copy_sha256=sha256_file(target_file)
                )
                summary["baked"] += 1
                if progress is not None:
                    progress(Progress(index, total, Phase.ORGANIZING, target_file.name))
        return summary

    return target
