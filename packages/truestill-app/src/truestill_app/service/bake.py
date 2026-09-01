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

⚠ **THE ENGINE MOVED TO `truestill_core.bake` ON 2026-08-25** (`(ahd)` step 1). What is left here
is the **panel**: the transport shapes a screen renders and the mapping onto
`DriveUnavailablePayload`. The write loop, the vocabulary both surfaces must agree on and every
predicate live in core, because `truestill-cli` cannot import this package
(`IMPLEMENTATION_STANDARDS.md` §2) and bake was the one mutating run with no CLI.

⚠ **`bake_run`, `bake_preview` and `bake_preconditions` did NOT move, and the reason is the
line.** All three return `DriveUnavailablePayload`, which carries `suggested_root` and
`can_register` - a button on a screen. Moving them whole would have put an app affordance in core.
So the seam is the one `drive.drive_identity` already uses: **core computes and returns a core
value, and this module wraps it into the payload.** These three keep their exact return shapes.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Final, Literal, NotRequired, TypedDict

from truestill_core.bake import (
    CHECKS_PER_FILE,
    CONFIRM_WORD,
    IRREVERSIBLE_NOTE,
    VIDEO_EXCLUSION_REASON,
    BakeDriveLine,
    BakeOutcome,
    DriveAwaiting,
    bake_confirmed_dates,
    bake_plan,
    completeness_line,
    migration_unfinished,
    migration_unfinished_message,
    unconfirmed_reason,
)
from truestill_core.catalog_session import open_catalog
from truestill_core.drive import read_marker
from truestill_core.progress import ProgressCallback

from truestill_app.jobs import JobTarget
from truestill_app.service.drive_support import (
    DriveUnavailablePayload,
    drive_unavailable,
)

#: Re-exported so the screens and their tests keep one import site while the engine lives in core.
__all__ = [
    "CHECKS_PER_FILE",
    "CONFIRM_WORD",
    "IRREVERSIBLE_NOTE",
    "NOT_CONFIRMED",
    "VIDEO_EXCLUSION_REASON",
    "BakeDriveLine",
    "BakePreview",
    "BakeRefusal",
    "BakeSummary",
    "DriveAwaiting",
    "bake_preconditions",
    "bake_preview",
    "bake_run",
    "completeness_line",
    "migration_unfinished",
    "migration_unfinished_message",
]

NOT_CONFIRMED: Final = "NotConfirmed"


class BakeRefusal(TypedDict):
    """A refusal the UI can render as-is. Same shape as every other soft failure."""

    ok: Literal[False]
    error: str
    code: Literal["MigrationUnfinished", "NotConfirmed"]
    drive_label: str


def bake_preconditions(path: Path, db: Path) -> BakeRefusal | DriveUnavailablePayload | None:
    """``None`` when a bake may proceed, else the refusal to show. Reads only.

    Called once before the run *and again before each file* - see :data:`CHECKS_PER_FILE` and
    the module docstring for what that does and does not buy.
    """
    marker = read_marker(path)
    if marker is None:
        return drive_unavailable(path, db)
    with open_catalog(db) as catalog:
        if migration_unfinished(catalog, marker.uuid):
            return {
                "ok": False,
                "error": migration_unfinished_message(marker.label),
                "code": "MigrationUnfinished",
                "drive_label": marker.label,
            }
    return None


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
    #: Whether the run left the library clean - read by `jobs.py` for the terminal status.
    #: `(aiq)`.
    finished_clean: bool
    #: The copy named by the catalog is not on the drive.
    absent: int
    #: Stopped because a migration started on this drive mid-run.
    refused: NotRequired[str]
    elapsed_seconds: NotRequired[float]


def bake_run(
    path: Path, db: Path, *, confirmation: str
) -> JobTarget[BakeSummary] | DriveUnavailablePayload | BakeRefusal:
    """Build a job that writes confirmed dates into this drive's copies.

    ⚠ **`confirmation` IS CHECKED HERE, NOT AT THE ROUTE** (`(ahe)`), and the word it is checked
    against lives in `truestill_core.bake` so a CLI checks the same one. The route is one caller;
    a guard on the caller is the shape `(afu)` punished. **No default**, the ruling
    `MigrationStop.kind` and `jobs.start`'s `mutating` already carry - and `(ahd)`'s move must not
    hand back the default the guard was installed to refuse.

    The refusal happens **before the target is built**, so a request with no word never becomes a
    job. Moving the check inside the loop would return a `job_id` and then fail.
    """
    unconfirmed_why = unconfirmed_reason(confirmation)
    if unconfirmed_why is not None:
        unconfirmed: BakeRefusal = {
            "ok": False,
            "error": unconfirmed_why,
            "code": NOT_CONFIRMED,
            # ⚠ Empty on purpose: nothing is wrong with the drive, and naming one here would make
            # a caller's mistake read as a fault of the user's hardware.
            "drive_label": "",
        }
        return unconfirmed
    refusal = bake_preconditions(path, db)
    if refusal is not None:
        return refusal
    marker = read_marker(path)
    if marker is None:  # pragma: no cover - bake_preconditions already answered this
        return drive_unavailable(path, db)

    def target(progress: ProgressCallback, cancel: threading.Event) -> BakeSummary:
        """The panel half: run the engine, then shape what it returns for a screen."""
        outcome: BakeOutcome = bake_confirmed_dates(
            path, db, marker, confirmation=confirmation, progress=progress, cancel=cancel
        )
        summary: BakeSummary = {
            "drive_label": outcome.drive_label,
            "baked": outcome.baked,
            "awaiting": outcome.awaiting,
            "completeness": outcome.completeness,
            "videos_skipped": outcome.videos_skipped,
            "videos_reason": VIDEO_EXCLUSION_REASON,
            "failed": outcome.failed,
            # `(aiq)`. A bake that could not write some dates left the library short of what
            # was asked for, which is the CLI exit-1 state.
            "finished_clean": not outcome.failed,
            "absent": outcome.absent,
        }
        if outcome.refused is not None:
            summary["refused"] = outcome.refused
        return summary

    return target


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
        return drive_unavailable(path, db)

    plan = bake_plan(path, db, marker)
    return {
        "ok": True,
        "drive_label": plan.drive_label,
        "will_write": plan.will_write,
        "videos_skipped": plan.videos_skipped,
        "videos_reason": VIDEO_EXCLUSION_REASON,
        "absent": plan.absent,
        "elsewhere": plan.elsewhere,
        "confirm_word": CONFIRM_WORD,
        "irreversible": IRREVERSIBLE_NOTE,
    }
