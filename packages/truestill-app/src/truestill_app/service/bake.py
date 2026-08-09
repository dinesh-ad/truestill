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

**O2: a bake is partial by nature, and must never read as complete.** ``copy_sha256`` is per
drive, so writing a date into the copy on one drive says nothing about the copy on another. A
confirmation can therefore be *in the bytes* on one drive and *catalog-only* on the next, and
those are different promises: the first survives leaving truestill entirely, the second survives
only inside it. The summary names the drives still waiting rather than counting them, because
"2 other drives" tells a user there is work left and "Backup 2019 and The Memory Cabinet" tells
them which two to plug in. **Nothing picks the rest up on its own** - there is no background
sweep, and a bake writes to user files, so it stays an explicit act. The report says so.

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

**Why a check here rather than a lock.** The app's per-drive job lock covers everything *inside
one app process*: every job route goes through ``server._start_drive_job``, which keys on
``uuid:<marker uuid>``. It is process-local **by design** (`BACKLOG.md` **(vv)**), so a CLI
``migrate-layout`` beside an app bake is not serialized at all -- and neither is a **second app
process**, which starts happily on an ephemeral port with its own ``JobManager`` (corrected
2026-08-03; this file previously said app-vs-app was covered "completely"). The journal, unlike
the lock, lives in the shared catalog and every process can read it.

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
from truestill_core.catalog_session import open_catalog
from truestill_core.drive import DriveReach, drive_reach, read_marker
from truestill_core.exif import build_metadata_args, write_metadata_batch
from truestill_core.hashing import sha256_file
from truestill_core.organizer import VIDEO_EXTENSIONS
from truestill_core.progress import Phase, Progress, ProgressCallback

from truestill_app.jobs import JobTarget
from truestill_app.service.drive_support import (
    DriveUnavailablePayload,
    drive_path_hint,
    drive_unavailable,
)

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
    with open_catalog(db) as catalog:
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


class DriveAwaiting(TypedDict):
    """A drive whose copies still hold the old date in their bytes."""

    label: str
    files: int


class BakeSummary(TypedDict):
    """What a bake actually did. Every outcome counted separately (§9)."""

    drive_label: str
    baked: int
    #: Other drives with copies still unbaked - **named**, not counted (O2).
    awaiting: list[DriveAwaiting]
    #: One sentence saying whether this finished the job or only part of it. Never omitted:
    #: a report that lists successes and stays quiet about the rest reads as completion.
    completeness: str
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
            "awaiting": [],
            "completeness": "",
            "videos_skipped": 0,
            "videos_reason": VIDEO_EXCLUSION_REASON,
            "failed": 0,
            "absent": 0,
        }
        with open_catalog(db) as catalog:
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
                target_file = path / relative
                # Every item ticks, including the ones nothing is written for. Progress that
                # only advances on success stalls on a run of skips and reads as a hang - the
                # (oo) finding, which is about hidden *work* rather than hidden errors.
                if progress is not None:
                    progress(Progress(index, total, Phase.ORGANIZING, target_file.name))
                if _is_video(relative):
                    summary["videos_skipped"] += 1
                    continue
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
            summary["awaiting"] = [
                {"label": str(r["label"]), "files": int(r["files"])}
                for r in catalog.drives_awaiting_bake(marker.uuid)
            ]
        summary["completeness"] = completeness_line(
            marker.label, summary["baked"], summary["awaiting"]
        )
        return summary

    return target


#: The word a user types to authorise the write. Distinct from every other confirm word in the
#: product (`undo`, `clean`, `move`, `delete`, `delete forever`) because the actions are
#: different and a muscle-memory word typed on the wrong screen is not a confirmation.
CONFIRM_WORD = "set dates"

#: Stated in the preview because it is the part a user cannot infer. `-overwrite_original`
#: (`exif._WRITE_FLAGS`) means exiftool replaces the file's metadata in place and keeps no
#: sidecar, so **the date the file used to carry is gone** once this runs. The catalog keeps the
#: provenance of the new date; it does not keep the old embedded one. `(bbb)` recovery is the
#: item that would offer to preserve it, and it is not built.
IRREVERSIBLE_NOTE = (
    "This changes the date stored inside each photo file. The date it had before is not kept, "
    "so this cannot be undone from inside truestill."
)


class BakeDriveLine(TypedDict):
    """One drive in the plan, and whether this run will actually reach it."""

    label: str
    files: int
    #: True when the drive's remembered location is reachable **right now**. A hint, never
    #: identity (§3.1) - it answers "can you plug this in without hunting for it", nothing more.
    connected: bool


class BakePreview(TypedDict):
    """What a bake would do, computed and displayed. Writes nothing."""

    ok: Literal[True]
    drive_label: str
    #: Files on the selected drive that would be written.
    will_write: int
    #: Confirmed videos on this drive: shown as excluded, with the reason. Never omitted - a
    #: file missing from a plan is the same defect class as a silently truncated list.
    videos_skipped: int
    videos_reason: str
    #: Confirmed copies this drive should hold that are not on it.
    absent: int
    #: Every other drive with copies that would keep the old date inside them.
    elsewhere: list[BakeDriveLine]
    confirm_word: str
    irreversible: str


def _reachable(catalog: Catalog, drive_uuid: str) -> bool:
    """Whether a drive's remembered path is live and still carries that drive's marker.

    Reads the hint **without clearing it**: `take_live_path_hint` deletes a dead hint, which is
    correct on a screen load and would be a *write* here. A preview writes nothing, including
    settings it thinks are stale.
    """
    hint = catalog.get_setting(drive_path_hint(drive_uuid))
    return drive_reach(hint, drive_uuid) is DriveReach.CONNECTED


def bake_preview(path: Path, db: Path) -> BakePreview | BakeRefusal | DriveUnavailablePayload:
    """Compute the plan for a bake. **Writes nothing** - see `test_bake_preview_purity`.

    Everything the user needs to decide is here and not after: how many files on this drive
    would be written, which confirmed videos are excluded and why, which other drives would keep
    the old date inside them and whether they are currently reachable, and that the change
    cannot be undone.
    """
    refusal = bake_preconditions(path, db)
    if refusal is not None:
        return refusal
    marker = read_marker(path)
    if marker is None:  # pragma: no cover - bake_preconditions already answered this
        return drive_unavailable(path)

    will_write = videos = absent = 0
    with open_catalog(db) as catalog:
        for row in catalog.confirmations_to_bake(marker.uuid):
            relative = str(row["relative"])
            if _is_video(relative):
                videos += 1
            elif not (path / relative).is_file():
                absent += 1
            else:
                will_write += 1
        elsewhere: list[BakeDriveLine] = [
            {
                "label": str(r["label"]),
                "files": int(r["files"]),
                "connected": _reachable(catalog, str(r["uuid"])),
            }
            for r in catalog.drives_awaiting_bake(marker.uuid)
        ]
    return {
        "ok": True,
        "drive_label": marker.label,
        "will_write": will_write,
        "videos_skipped": videos,
        "videos_reason": VIDEO_EXCLUSION_REASON,
        "absent": absent,
        "elsewhere": elsewhere,
        "confirm_word": CONFIRM_WORD,
        "irreversible": IRREVERSIBLE_NOTE,
    }
