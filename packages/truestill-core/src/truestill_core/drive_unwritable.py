"""A drive that will not take a write, in words a person can act on.

Named for the condition it recognises, the way ``catalog_busy`` is, so an errno added later has an
obvious home rather than a fourth one. Two writes land on a user's drive - the marker
(:func:`truestill_core.drive.write_marker`) and the decisions document
(:func:`truestill_core.decisions.write_decisions`) - and a read-only disk, a full one, a quota that
is used up and one pulled out mid-write are ordinary events for removable media, not exceptions.

**Only recognition and wording are here.** Presentation stays with each caller, which is where it
differs: `write_marker` returns a `MarkerWrite` its callers turn into a refusal, `write_decisions`
returns a `WriteOutcome` that must never reach the user's actual work.

**Why this is a module rather than a function on either caller.** ``decisions`` already imports
``drive`` (for `drive_path_hint` / `DriveReach`), so `drive` cannot import `decisions` back without
a cycle - and the wording has to have exactly one home or the two disagree the first time one is
corrected. That is ENGINEERING_STANDARD.md §4's *"delete one of the two copies"* applied before the
second copy exists. This module has no truestill imports at all, so it can never be the cycle.

**The wording is deliberately not an ``errno`` name.** §9 already rules that for reads, through
`models.unreadable_label`; the same reasoning holds for writes. ``[Errno 122] Disk quota exceeded``
tells a user nothing to do.
"""

from __future__ import annotations

import errno
from enum import StrEnum

#: ``EDQUOT``, resolved defensively because it is **not defined on every platform** Python runs on,
#: and a bare ``errno.EDQUOT`` would be an ``AttributeError`` at import there rather than a missing
#: branch. ``-1`` can never equal a real ``errno``, so the comparison simply never matches.
#:
#: This is the errno the first soak actually hit - 122, a quota rather than a full filesystem - and
#: it had no branch until `(aek)`. The three-OS `check` matrix is the detector for the guard being
#: wrong; nothing on this machine can see it.
_EDQUOT: int = getattr(errno, "EDQUOT", -1)


class Unwritable(StrEnum):
    """Why a write was refused. **One table, because an errno must be classified once.**

    Split out 2026-08-22 for `(aeo)`: the same six conditions occur on a drive the user chose and
    on this computer's own home directory, and they need **different nouns** - *"the drive is
    read-only"* is wrong, and alarming, about a folder the user never picked. Adding a second
    errno table would be the two-copies failure this module's docstring exists to prevent, so the
    recognition is here once and each noun gets a phrasing below.
    """

    #: Read-only medium, or an account without permission. `EROFS`/`EACCES`/`EPERM`.
    REFUSED = "refused"
    #: Genuinely out of space. `ENOSPC` - delete something.
    NO_SPACE = "no_space"
    #: Space may exist and this account may not have it. `EDQUOT` - opposite advice to NO_SPACE.
    QUOTA = "quota"
    #: The location is gone. `ENOENT`/`ENOTDIR`.
    GONE = "gone"
    #: Hardware or transport gave up mid-write. `EIO`.
    FAILING = "failing"
    #: Recognised by nothing above; the caller falls back to the OS's own words.
    OTHER = "other"


def classify_unwritable(error: OSError) -> Unwritable:
    """Which of the six conditions this ``OSError`` is. **The only errno table in the product.**"""
    if error.errno in (errno.EROFS, errno.EACCES, errno.EPERM):
        return Unwritable.REFUSED
    if error.errno == errno.ENOSPC:
        return Unwritable.NO_SPACE
    if error.errno == _EDQUOT:
        return Unwritable.QUOTA
    if error.errno in (errno.ENOENT, errno.ENOTDIR):
        return Unwritable.GONE
    if error.errno == errno.EIO:
        return Unwritable.FAILING
    return Unwritable.OTHER


_DRIVE_WORDS: dict[Unwritable, str] = {
    Unwritable.REFUSED: "the drive is read-only, or this account cannot write to it",
    Unwritable.NO_SPACE: "there is no space left on the drive",
    Unwritable.QUOTA: "this account's allowance on the drive is used up",
    Unwritable.GONE: "the drive is not there any more",
    Unwritable.FAILING: "the drive stopped responding part way through",
}

#: The same six conditions about a folder on **this computer** - no drive to name. `(aeo)`
_FOLDER_WORDS: dict[Unwritable, str] = {
    Unwritable.REFUSED: "that folder is read-only, or this account cannot write to it",
    Unwritable.NO_SPACE: "this computer has no disk space left",
    Unwritable.QUOTA: "this account's disk allowance is used up",
    Unwritable.GONE: "that folder is not there any more",
    Unwritable.FAILING: "the disk stopped responding part way through",
}


def explain_unwritable_drive(error: OSError) -> str:
    """What went wrong, in words a person can act on rather than an errno.

    **A quota is not a full drive, and they need opposite advice.** ``ENOSPC`` means delete
    something; ``EDQUOT`` means the disk may have plenty of room and this account may not have it,
    so sending that user to free up space points them at files that were never the problem.
    """
    return _DRIVE_WORDS.get(classify_unwritable(error)) or error.strerror or str(error)


def explain_unwritable_folder(error: OSError) -> str:
    """The same six conditions, about a folder on this computer rather than a drive. `(aeo)`

    ⚠ **The noun is the whole reason this exists.** The launch path writes into the user's own
    data directory, which they never chose and cannot swap; telling them *"the drive is
    read-only"* names a thing that is not in the story and sends them looking for hardware.
    """
    return _FOLDER_WORDS.get(classify_unwritable(error)) or error.strerror or str(error)
