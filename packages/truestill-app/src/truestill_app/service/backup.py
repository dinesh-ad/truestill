"""Backup: the panel over `truestill_core.backup`. `(ahf)` stage 1.

⚠ **THE ENGINE MOVED TO CORE ON 2026-08-25.** What is left here is the transport: the two payload
`TypedDict`s a screen renders, the drive registration and gate that precede a run, and the
assembly of a `BackupRunSummary` from what the engine returns. Backup was one of three mutating
runs that existed only in the app, and `truestill-cli` cannot import this package
(`IMPLEMENTATION_STANDARDS.md` §2).

**Measured before anything moved**: of nineteen top-level symbols, **fourteen touched no app name
at all**. Those are core now. The five that did are `backup_preview`, `backup_run`,
`BackupPreviewOk`, `BackupPreviewErr` and `_nothing_copied`, and they are here - the same
core-computes/app-wraps line `drive.drive_identity` and `(ahd)` already draw.

⚠ **`attach_drive` stayed, and that is a sequencing choice rather than a ruling about where it
belongs.** It is called at setup and never inside the copy loop, so the engine never needed it.
Its correct home is core - it uses exactly one app-side name and that name is a re-export of a
core one - and `(ahf)` records that as stage 2's first move rather than smuggling it in here.
"""

from __future__ import annotations

import shutil
import threading
from pathlib import Path
from typing import Literal, NotRequired, TypedDict

from truestill_core.backup import (
    _FREE_SPACE_MARGIN,
    UNREAD_FOLDERS_REASON,
    UNREAD_FOLDERS_TITLE,
    BackupPair,
    MissingCopy,
    _blocked_message,
    _files_missing_on_target,
    copy_to_drive,
)
from truestill_core.catalog_session import open_catalog
from truestill_core.drive import read_marker
from truestill_core.progress import ProgressCallback

from truestill_app.jobs import JobTarget
from truestill_app.service.drive_support import not_a_drive
from truestill_app.service.drives import attach_drive
from truestill_app.service.media_support import media_breakdown


class BackupPreviewErr(TypedDict):
    ok: Literal[False]
    error: str


# ``from`` is a reserved word; functional form keeps the JSON key exact.
BackupPreviewOk = TypedDict(
    "BackupPreviewOk",
    {
        "ok": Literal[True],
        "from": str,
        "to": str,
        "will_register": list[str],
        #: How many already-organized copies the run will read end to end to establish this
        #: drive's own hashes. Stated before the run because attach is no longer instant: a
        #: full read of a library is minutes to hours, and a progress bar that appears without
        #: warning reads as a hang. Zero on an already-attached drive, which is the usual case.
        "will_read": int,
        "count": int,
        "photos": int,
        "videos": int,
        "audio": int,
        "bytes": int,
        "free": int,
        "enough": bool,
        #: Folders the attach could not open, each named with the drive it is on. `(abm)`
        #: ⚠ **This is what makes the counts above conditional.** A file under one of these never
        #: got a `file_copies` row, so it was never a candidate to copy and *"every photo on X is
        #: already on Y"* is false about it. Named rather than counted - the walk never went
        #: inside (`IMPLEMENTATION_STANDARDS.md` §9).
        "unreadable_dirs": list[str],
        #: Files on either drive whose bytes could not be read, so they could not be identified.
        #: Counted, because unlike a folder these were seen.
        "unreadable": int,
        #: The banner's heading and body, both from `truestill_core.backup`. Empty when there is
        #: nothing to say. `app.js` renders text it was handed and words nothing itself (`(ahc)`),
        #: which is why the title is a payload key rather than a string in the markup.
        "unread_title": str,
        "unread_reason": str,
    },
)


def backup_preview(source: Path, target: Path, db: Path) -> BackupPreviewOk | BackupPreviewErr:
    """Preview copying the library from one connected drive to another (writes nothing).

    Reports how many files (and bytes) are missing on the target, and whether the target has room
    -- a disk-full part-way through is the failure this whole feature exists to prevent.
    """
    if not source.is_dir():
        return {
            "ok": False,
            "error": "The From folder was not found. Check the path, then pick an existing folder.",
        }
    if not target.is_dir():
        return {
            "ok": False,
            "error": "The To folder was not found. Check the path, then pick or create a folder.",
        }
    if source.resolve() == target.resolve():
        return {
            "ok": False,
            "error": "From and To point to the same folder. Pick a different destination drive.",
        }
    # Preview writes nothing, so an unregistered folder is *reported* as one that will be
    # registered rather than rejected -- the run does the registering.
    src = attach_drive(source, db, write=False)
    tgt = attach_drive(target, db, write=False)
    # Refused before anything else is computed: a folder that already holds a known library
    # must not be registered a second time, or truestill would count one copy of the user's
    # photos as two and say so on the very screen that promises redundancy ((aap)).
    for side, attachment in (("From", src), ("To", tgt)):
        if attachment.blocked_by is not None:
            return {"ok": False, "error": _blocked_message(side, attachment.blocked_by)}
    src_marker, tgt_marker = read_marker(source), read_marker(target)
    if src_marker is not None and tgt_marker is not None and src_marker.uuid == tgt_marker.uuid:
        return {
            "ok": False,
            "error": "From and To are the same drive. Pick a different backup drive.",
        }
    with open_catalog(db) as catalog:
        missing = (
            _files_missing_on_target(catalog, src_marker.uuid, tgt_marker.uuid)
            if src_marker is not None and tgt_marker is not None
            else [MissingCopy.from_row(r) for r in catalog.organized_files()]
        )
    need = sum(int(r.size or 0) for r in missing)
    free = shutil.disk_usage(target).free
    breakdown = media_breakdown([r.relative for r in missing])
    # ⚠ `(abm)`: both sides, because either can carry a folder the walk could not open, and each
    # entry names its own drive so one list stays readable. Held by `src`/`tgt` since the attach
    # above and discarded until now, which is the whole of that entry.
    unreadable_dirs = [
        f"{attachment.label}: {folder}"
        for attachment in (src, tgt)
        for folder in attachment.unreadable_dirs
    ]
    unreadable = src.unreadable + tgt.unreadable
    return {
        "ok": True,
        "from": src.label,
        "to": tgt.label,
        "will_register": [d.label for d in (src, tgt) if d.registered],
        "will_read": src.linked + tgt.linked,
        "count": len(missing),
        "photos": breakdown["photos"],
        "videos": breakdown["videos"],
        "audio": breakdown["audio"],
        "bytes": need,
        "free": free,
        "enough": free >= need * _FREE_SPACE_MARGIN,
        "unreadable_dirs": unreadable_dirs,
        "unreadable": unreadable,
        "unread_title": UNREAD_FOLDERS_TITLE if (unreadable_dirs or unreadable) else "",
        "unread_reason": UNREAD_FOLDERS_REASON if (unreadable_dirs or unreadable) else "",
    }


class BackupRunSummary(TypedDict):
    copied: int
    to: str
    photos: int
    videos: int
    audio: int
    bytes_copied: int
    #: Files this run could not copy. `ENGINEERING_STANDARD.md` §4 Errors: one bad file does not
    #: abort the batch, so it is counted and named rather than ending the run. `(afw)` Stage 4.
    failed: int
    #: ⚠ **`bool`, and it was `Literal[True]` until 2026-08-23** - the type itself asserted the
    #: claim, so mypy would have rejected the honest value. That is worth more than the flag: an
    #: invariant baked into a type is one nothing can report a violation of.
    verified: bool
    target_path: str
    elapsed_seconds: NotRequired[float]


def _nothing_copied(label: str, target: Path) -> BackupRunSummary:
    """The summary for a run that stopped before copying anything. Still ``verified``: nothing
    was written, so nothing went unchecked."""
    return {
        "copied": 0,
        "failed": 0,
        "to": label,
        "photos": 0,
        "videos": 0,
        "audio": 0,
        "bytes_copied": 0,
        "verified": True,
        "target_path": str(target),
    }


def backup_run(source: Path, target: Path, db: Path) -> JobTarget[BackupRunSummary]:
    """Build a job that copies the library to another drive: verify-after-write, record each copy."""

    def target_job(progress: ProgressCallback, cancel: threading.Event) -> BackupRunSummary:
        if not source.is_dir() or not target.is_dir():
            message = "both the 'from' and 'to' folders must exist."
            raise ValueError(message)
        # Register whatever is not yet a drive, and attach a library organized before its
        # folder was registered. Without this the app rejects the very library it just built.
        # Attach reads every copy it links to establish that drive's own hashes, so it takes
        # the job's progress and cancel: on an unattached library this is the long part of the
        # run, and it must be visible and stoppable rather than a silent wait before copying.
        attach_drive(source, db, write=True, progress=progress, cancel=cancel)
        attach_drive(target, db, write=True, progress=progress, cancel=cancel)
        src_marker, tgt_marker = read_marker(source), read_marker(target)
        if src_marker is None or tgt_marker is None:
            raise not_a_drive(source if src_marker is None else target, db)
        if cancel.is_set():
            # Stopped during attach. What was hashed is recorded and the next run resumes from
            # there. Returning here rather than falling through means a cancelled run cannot be
            # answered with "not enough space" - a true statement about a run nobody asked to
            # continue, and a confusing one to be handed after pressing stop.
            return _nothing_copied(tgt_marker.label, target)
        outcome = copy_to_drive(
            BackupPair(
                source=source,
                source_marker=src_marker,
                target=target,
                target_marker=tgt_marker,
            ),
            db,
            progress=progress,
            cancel=cancel,
        )
        copied, copied_names = outcome.copied, outcome.copied_names
        copied_bytes, failures = outcome.bytes_copied, outcome.failures
        breakdown = media_breakdown(copied_names)
        return {
            "copied": copied,
            "to": tgt_marker.label,
            "photos": breakdown["photos"],
            "videos": breakdown["videos"],
            "audio": breakdown["audio"],
            "bytes_copied": copied_bytes,
            "failed": len(failures),
            # ⚠ **DERIVED, never asserted** (`(afw)` Stage 4). This was the literal `True`, and
            # the comment justifying it said *"a copy that failed that check aborts the run"* -
            # which stopped being true the moment one bad file stopped aborting. A custody
            # product cannot ship a record claiming verification it did not perform: that is
            # BackInTime #1587's shape, where per-file failures reported only through an exit
            # code left users believing the backup was fine.
            "verified": not failures,
            "target_path": str(target),
        }

    return target_job
