"""Preconditions for baking a confirmed date into the copies on a drive (step 4, condition 3).

**What this module is, today.** The precondition half of the bake: it refuses to start, and
refuses to continue, while a migration is unfinished on the same drive. The write itself lands
in the commits after this one (O1, O2, preview-then-typed-confirm). The refusal is separated on
purpose - it is the condition that had to be settled *before* anything writes to a user's drive.

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

from pathlib import Path
from typing import Literal, TypedDict

from truestill_core.catalog import Catalog
from truestill_core.drive import read_marker

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
