"""Shared drive identity, path hints, and soft-refuse correction payloads.

Used by Verify, Drives, Migration, Backup, and Trips proposal - extracted so those
surfaces can move without importing the facade.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal, TypedDict

from truestill_core.catalog import Catalog
from truestill_core.drive import locate_drive, path_is_usable_dir, read_marker

from truestill_app.jobs import DriveRef


class NotABackupDriveError(ValueError):
    """The path is a real folder, but not a truestill backup drive.

    Typed rather than a bare ValueError so the UI can answer it with the *next step* ("copy
    your library here to make one") instead of restating the failure. The client matches on
    this class name, never on the message text, which would break on any rewording.
    """


class DriveCorrectionPayload(TypedDict):
    error: str
    suggested_root: str | None
    drive_label: str | None
    can_register: bool


class DriveUnavailablePayload(TypedDict):
    """Connected-drive gate failed: same correction shape migration preview already returns."""

    ok: Literal[False]
    error: str
    suggested_root: str | None
    drive_label: str | None
    can_register: bool


def not_a_drive_message(path: Path) -> str:
    """Say what this path actually is, so the user has something to do about it.

    Three outcomes, three answers. Reporting all of them as "is the drive connected?" asks a
    question whose answer is plainly yes, and leaves someone re-plugging a cable that was never
    loose. The common real case -- naming a folder *inside* a connected drive -- gets a
    correction instead of an error. An unreachable stale hint is a fourth case: ask to browse
    to the current folder; the marker uuid is still the identity.
    """
    if not path_is_usable_dir(path):
        return (
            f"Can't reach '{path}' - it may have moved, been unmounted, or denied access. "
            "Browse to where the drive is now. Identity is the marker on the drive, not this path."
        )
    location = locate_drive(path)
    if location.is_inside and location.marker is not None:
        return (
            f"This is a folder inside '{location.marker.label}'. "
            f"Use the drive root instead: {location.root}"
        )
    return (
        "This folder isn't set up as a backup drive yet. "
        "Copy photos here once and truestill will set it up, "
        "or register this drive first."
    )


def drive_correction(path: Path) -> DriveCorrectionPayload:
    """The machine-readable half of the same answer, so the UI can offer one-click correction."""
    if not path_is_usable_dir(path):
        # Unreachable: never offer "register this" - registering needs a real folder.
        return {
            "error": not_a_drive_message(path),
            "suggested_root": None,
            "drive_label": None,
            "can_register": False,
        }
    location = locate_drive(path)
    return {
        "error": not_a_drive_message(path),
        "suggested_root": str(location.root) if location.is_inside else None,
        "drive_label": location.marker.label if location.marker else None,
        "can_register": location.marker is None,
    }


def drive_unavailable(path: Path) -> DriveUnavailablePayload:
    """Connected-drive gate failure (explicit TypedDict - mypy 1.13 rejects Union ** spreads)."""
    return {"ok": False, **drive_correction(path)}


def drive_ref_for(path: Path) -> DriveRef:
    """Lock identity for a path a job will touch (uuid when marked, else resolved path)."""
    marker = read_marker(path)
    if marker is not None:
        return DriveRef(key=f"uuid:{marker.uuid}", label=marker.label)
    try:
        resolved = str(path.expanduser().resolve())
    except OSError:
        resolved = str(path)
    return DriveRef(key=f"path:{resolved}", label=path.name or resolved)


def not_a_drive(path: Path) -> NotABackupDriveError:
    return NotABackupDriveError(not_a_drive_message(path))


def drive_path_hint(uuid: str) -> str:
    """Settings key for where a drive was last seen mounted.

    A *hint*, like the others: it lets a drive card offer "Check now" for the right folder
    instead of making the user find it again. Identity remains the marker uuid -- a drive that
    remounts elsewhere is the same drive, and this key is simply stale until it is next seen.
    """
    return f"path_hint.drive.{uuid}"


def take_live_path_hint(catalog: Catalog, key: str) -> str | None:
    """Return ``key``'s path when it still names a usable directory; otherwise clear it.

    **Failed hints are cleared, not ignored.** A hint is never identity - only a convenience.
    Leaving a dead path in settings would re-stat it on every Backups/library load (slow and
    noisy on locked FUSE). Clearing once stops the re-hit; the next successful attach/verify
    at the real root writes a fresh hint. This is not a custody write: the uuid and
    ``file_copies`` rows are untouched.
    """
    raw = catalog.get_setting(key)
    if raw is None:
        return None
    if path_is_usable_dir(Path(raw)):
        return raw
    catalog.clear_setting(key)
    return None
