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

Complexity: :func:`probe_dir` is **O(1)** - one stat, always (it was one or two). :func:`nearest_device` is **O(depth)**
stat calls, bounded by the filesystem root, matching ``drive.locate_drive``'s existing walk.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from truestill_core.path_reach import Reach, reach
from truestill_core.path_reach import probe as path_probe_stat


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


#: This surface's four answers, from `path_reach`'s five. `FILE` and `OTHER` collapse because a
#: caller choosing a *folder* has the same next step either way: pick something else.
_FROM_REACH: dict[Reach, PathReach] = {
    Reach.DIRECTORY: PathReach.DIRECTORY,
    Reach.FILE: PathReach.NOT_A_DIRECTORY,
    Reach.OTHER: PathReach.NOT_A_DIRECTORY,
    Reach.MISSING: PathReach.MISSING,
    Reach.REFUSED: PathReach.UNREADABLE,
}


def probe_dir(path: Path) -> PathReach:
    """Classify ``path`` as a directory, a non-directory, absent, or unreadable. **One stat.**

    ⚠ **The verdict comes from `path_reach.reach`, never from `is_dir()`/`exists()`.** Those two
    stopped raising on ``EACCES`` in Python 3.14, so this function answered ``MISSING`` - absent
    **and creatable** - about a folder that had refused. `(aey)`; the argument lives in
    `path_reach`, and `test_refused_is_never_absent.py` pins the answer with the predicates made
    to swallow.

    **Cheaper than what it replaced**, which is worth saying because the docstring used to promise
    O(1) and spend two stats: `is_dir()` then `exists()` on every non-directory. One now.
    """
    return _FROM_REACH[reach(path)]


def nearest_device(path: Path) -> DeviceProbe:
    """The device ``path`` occupies, walking up through ancestors that do not exist yet.

    Stops and reports rather than walking *past* a directory that refused to be described:
    borrowing a readable ancestor's device would answer the same-filesystem question with a
    different folder's answer, confidently and sometimes wrongly. **O(depth)** stat calls -
    exactly one per level, which is why it reads the stat `path_reach.probe` already took.
    """
    probe = path
    while True:
        # ⚠ `reach`, not `exists()`: on 3.14 a refused ancestor answered "not there" and this walk
        # went straight past it, borrowing a *different* folder's device to answer the
        # same-filesystem question. That is the failure the docstring above forbids. `(aey)`
        found, stat_result = path_probe_stat(probe)
        if found is Reach.REFUSED:
            return DeviceProbe(device_id=None, blocked_at=probe)
        if stat_result is not None:
            return DeviceProbe(device_id=stat_result.st_dev)
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
