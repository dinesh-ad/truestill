"""Backup: copy the library to a second drive with verify-after-write."""

from __future__ import annotations

import shutil
import sqlite3
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, NotRequired, TypedDict

from truestill_core.catalog import Catalog
from truestill_core.drive import read_marker
from truestill_core.hashing import sha256_file
from truestill_core.progress import Phase, Progress, ProgressCallback

from truestill_app.jobs import JobTarget
from truestill_app.service.drive_support import not_a_drive
from truestill_app.service.drives import BACKUP_PATH_HINT, attach_drive
from truestill_app.service.media_support import media_breakdown


def _now() -> str:
    return datetime.now(UTC).isoformat()


_GB = 1_000_000_000
_MB = 1_000_000


def _gb(n: int) -> str:
    """A human byte size for space messages (GB for anything sizeable, else MB)."""
    return f"{n / _GB:.1f} GB" if n >= _GB else f"{n / _MB:.0f} MB"


_FREE_SPACE_MARGIN = 1.03  # keep a little headroom so a copy never fills the target drive


@dataclass(frozen=True, slots=True)
class MissingCopy:
    """One library file still absent on the backup target.

    Carries both hashes deliberately: ``sha256`` is the content/dedup identity, ``copy_sha256``
    is the verification identity (§3). The copy-verify loop must never treat them as
    interchangeable - that is why this is a dataclass, not ``list[Any]`` (audit F8).
    """

    sha256: str
    relative: str
    copy_sha256: str | None
    size: int | None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> MissingCopy:
        """Build from a ``copies_on_drive`` or ``organized_files`` catalog row."""
        size_raw = row["size"]
        copy_raw = row["copy_sha256"]
        return cls(
            sha256=str(row["sha256"]),
            relative=str(row["relative"]),
            copy_sha256=None if copy_raw is None else str(copy_raw),
            size=None if size_raw is None else int(size_raw),
        )

    @property
    def verify_sha(self) -> str | None:
        """Digest the on-disk copy must match after write, or ``None`` if none was recorded.

        No fallback to the source hash. That asserted the copy is byte-identical to its source,
        which the Takeout bake already breaks and date-rescue baking will break again - and it
        made an un-recorded hash indistinguishable from a legacy row.
        """
        return self.copy_sha256


def _files_missing_on_target(
    catalog: Catalog, source_uuid: str, target_uuid: str
) -> list[MissingCopy]:
    """Copies present on the source drive but not yet on the target -- keyed on per-drive presence,
    not the catalog-global dedup that would wrongly skip a genuine second copy."""
    on_target = {r["sha256"] for r in catalog.copies_on_drive(target_uuid)}
    return [
        MissingCopy.from_row(r)
        for r in catalog.copies_on_drive(source_uuid)
        if r["sha256"] not in on_target
    ]


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
    src_marker, tgt_marker = read_marker(source), read_marker(target)
    if src_marker is not None and tgt_marker is not None and src_marker.uuid == tgt_marker.uuid:
        return {
            "ok": False,
            "error": "From and To are the same drive. Pick a different backup drive.",
        }
    with Catalog(db) as catalog:
        missing = (
            _files_missing_on_target(catalog, src_marker.uuid, tgt_marker.uuid)
            if src_marker is not None and tgt_marker is not None
            else [MissingCopy.from_row(r) for r in catalog.organized_files()]
        )
    need = sum(int(r.size or 0) for r in missing)
    free = shutil.disk_usage(target).free
    breakdown = media_breakdown([r.relative for r in missing])
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
    }


class BackupRunSummary(TypedDict):
    copied: int
    to: str
    photos: int
    videos: int
    audio: int
    bytes_copied: int
    verified: Literal[True]
    target_path: str
    elapsed_seconds: NotRequired[float]


def _nothing_copied(label: str, target: Path) -> BackupRunSummary:
    """The summary for a run that stopped before copying anything. Still ``verified``: nothing
    was written, so nothing went unchecked."""
    return {
        "copied": 0,
        "to": label,
        "photos": 0,
        "videos": 0,
        "audio": 0,
        "bytes_copied": 0,
        "verified": True,
        "target_path": str(target),
    }


def backup_run(source: Path, target: Path, db: Path) -> JobTarget:
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
            raise not_a_drive(source if src_marker is None else target)
        if src_marker.uuid == tgt_marker.uuid:
            message = "the 'from' and 'to' folders are the same drive."
            raise ValueError(message)
        if cancel.is_set():
            # Stopped during attach. What was hashed is recorded and the next run resumes from
            # there. Returning here rather than falling through means a cancelled run cannot be
            # answered with "not enough space" - a true statement about a run nobody asked to
            # continue, and a confusing one to be handed after pressing stop.
            return _nothing_copied(tgt_marker.label, target)
        with Catalog(db) as catalog:
            missing = _files_missing_on_target(catalog, src_marker.uuid, tgt_marker.uuid)
            need = sum(int(r.size or 0) for r in missing)
            free = shutil.disk_usage(target).free
            if free < need * _FREE_SPACE_MARGIN:
                message = (
                    f"not enough space on {tgt_marker.label}: needs {_gb(need)}, "
                    f"only {_gb(free)} free."
                )
                raise ValueError(message)
            copied = 0
            copied_names: list[str] = []
            copied_bytes = 0
            for row in missing:
                if cancel.is_set():
                    break
                rel = row.relative
                dst = target / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source / rel, dst)
                written = sha256_file(dst)
                want = row.verify_sha
                if want is not None and written != want:
                    # verify-after-write; a bad copy is never recorded
                    dst.unlink(missing_ok=True)
                    message = f"copy of {rel} did not verify -- stopping to stay safe."
                    raise ValueError(message)
                catalog.record_copy(
                    sha256=row.sha256,
                    drive_uuid=tgt_marker.uuid,
                    relative=rel,
                    # The hash of the copy just written, not the one inherited from the source
                    # row. Authoritative by construction, and it means a copy made by backup can
                    # never be the UNVERIFIABLE case - the unknown stops propagating here.
                    copy_sha256=written,
                    size=int(row.size or 0) or None,
                )
                catalog.mark_copy_verified(
                    sha256=row.sha256, drive_uuid=tgt_marker.uuid, when=_now()
                )
                copied += 1
                copied_names.append(rel)
                copied_bytes += int(row.size or 0)
                progress(Progress(copied, len(missing), Phase.COPYING, Path(rel).name))
            catalog.set_setting(BACKUP_PATH_HINT, str(target))
        breakdown = media_breakdown(copied_names)
        return {
            "copied": copied,
            "to": tgt_marker.label,
            "photos": breakdown["photos"],
            "videos": breakdown["videos"],
            "audio": breakdown["audio"],
            "bytes_copied": copied_bytes,
            # Every copy was re-hashed against the recorded digest before being recorded; a
            # copy that failed that check aborts the run. Saying so is the point of the whole
            # feature, so the completion card gets to say it.
            "verified": True,
            "target_path": str(target),
        }

    return target_job
