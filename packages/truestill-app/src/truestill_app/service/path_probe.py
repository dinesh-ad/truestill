"""Honest filesystem probes: present, absent, or refused - never absent-by-default.

`Path.exists` and `Path.is_dir` look total and are not. They swallow ``OSError`` only for the
"not there" family (pathlib's ``_ignore_error``: ENOENT, ENOTDIR, EBADF, ELOOP) and **re-raise
everything else**, ``EACCES`` included. Three app surfaces read them as "False means no" and so
crashed on a permission-denied folder - a 500 from Browse, from the path hint, and from the
organize mode briefing (audit F21). ``truestill_core.drive.path_is_usable_dir`` already guards
its own probe for exactly this reason; this module is that discipline made reusable, and typed,
so a caller has to decide what "refused" means instead of inheriting a wrong default.

The distinction that matters to a user: **absent and refused are different answers.** A folder
that does not exist yet can be created, and offering that is helpful. A folder that exists and
will not answer cannot be created - the create fails the same way the probe did - so offering it
sends the user round a loop.

Complexity: :func:`probe_dir` is **O(1)** - one stat. :func:`nearest_device` is **O(depth)**
stat calls, bounded by the filesystem root, matching ``drive.locate_drive``'s existing walk.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class PathReach(StrEnum):
    """What the filesystem was willing to say about a path."""

    #: An existing directory.
    DIRECTORY = "directory"
    #: Something is there, but it is not a directory.
    NOT_A_DIRECTORY = "not_a_directory"
    #: Nothing is there. Creatable.
    MISSING = "missing"
    #: Something is there and the OS refused to describe it. Not creatable, not absent.
    UNREADABLE = "unreadable"


@dataclass(frozen=True, slots=True)
class DeviceProbe:
    """The filesystem device a path lives on (or would be created on), or what blocked the walk.

    ``device_id`` is ``None`` **only** when a directory refused to be described;
    ``blocked_at`` then names it, so a message can say which folder is the problem. A path that
    merely does not exist yet is not a failure: it resolves through its nearest existing
    ancestor, which is the filesystem it would be created on, and that is the answer the
    same-filesystem question actually wants.
    """

    device_id: int | None
    blocked_at: Path | None = None


def probe_dir(path: Path) -> PathReach:
    """Classify ``path`` as a directory, a non-directory, absent, or unreadable. **O(1)**."""
    try:
        if path.is_dir():
            return PathReach.DIRECTORY
    except OSError:
        return PathReach.UNREADABLE
    # is_dir() said False: either nothing is there, or something that is not a directory.
    try:
        return PathReach.NOT_A_DIRECTORY if path.exists() else PathReach.MISSING
    except OSError:
        return PathReach.UNREADABLE


def nearest_device(path: Path) -> DeviceProbe:
    """The device ``path`` occupies, walking up through ancestors that do not exist yet.

    Stops and reports rather than walking *past* a directory that refused to be described:
    borrowing a readable ancestor's device would answer the same-filesystem question with a
    different folder's answer, confidently and sometimes wrongly. **O(depth)** stat calls.
    """
    probe = path
    while True:
        try:
            exists = probe.exists()
        except OSError:
            return DeviceProbe(device_id=None, blocked_at=probe)
        if exists:
            try:
                return DeviceProbe(device_id=probe.stat().st_dev)
            except OSError:
                return DeviceProbe(device_id=None, blocked_at=probe)
        if probe.parent == probe:
            # Walked to the root without finding anything readable. Unreachable on a normal
            # filesystem (the root always stats); reported rather than assumed away.
            return DeviceProbe(device_id=None, blocked_at=probe)
        probe = probe.parent


def unreadable_message(path: Path) -> str:
    """One wording for "it is there and I cannot read it", shared by every surface that says it.

    Names the folder, states what actually happened, and gives the next step. Deliberately does
    not say "not found": the folder is present, and sending someone to look for it wastes the
    one piece of information the OS did give us.
    """
    return (
        f"Can't read '{path}' - it exists, but access was denied or the disk did not respond. "
        "Check the folder's permissions, or pick another folder."
    )
