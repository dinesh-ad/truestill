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


def underlying_oserror(error: BaseException) -> OSError | None:
    """The ``OSError`` behind a wrapper, or ``None`` if there is not one. `(agi)`, `(ain)`

    ⚠ **The CAUSE CHAIN, not the exception handed in**, and that was learned the hard way: the
    write paths raise `DestinationError(...) from outcome.error`, so a caller catching one never
    sees an `OSError` at all - and `(agi)`'s first draft, which tested `isinstance` on what it was
    given, was **inert on the surface that runs most**.

    Extracted when the second caller arrived rather than copied into it: `(ain)` has to word a
    refused `set_timestamp`, which reaches it wrapped exactly the same way.
    """
    found: BaseException | None = error
    while found is not None and not isinstance(found, OSError):
        found = found.__cause__
    return found if isinstance(found, OSError) else None


def persists_for_the_run(error: BaseException) -> bool:
    """Will the NEXT file hit this too? `(agi)`

    **The discriminator is not which side failed, it is whether the condition outlives the file.**
    A condition that persists must stop the run; one local to a single file must not, because
    `ENGINEERING_STANDARD.md` §4 Errors is *"one bad file never aborts a batch"*. The table below
    is the **implementation** of that predicate, never the rule itself - so every branch carries
    why the condition persists, and an errno nobody has reasoned about returns `False`, because
    continuing is the recoverable mistake and aborting a good run is not.

    ⚠ **Keyed on ``errno``, never on ``winerror``, and that is what makes it right on Windows for
    free.** Python sets ``errno`` as an approximate POSIX translation of the native code, so
    ``ERROR_DISK_FULL`` (112) and ``ERROR_HANDLE_DISK_FULL`` (39) arrive here as ``ENOSPC``.
    A ``winerror`` table would need a second copy for the one platform that cannot be checked
    locally. PEP 3151 gives the general form of this rule: inspect ``errno`` rather than catching
    a broad exception type.

    **Null result from the research, recorded so it is not re-sought:** no comparable project
    publishes a per-errno persistence table. rsync, restic and rclone all express the same split
    at the level of **exit codes** - rsync's fatal 11 against the per-file 23, restic's fatal
    destination-write against exit 3 - and rclone does not classify at all, which is why it
    carries rclone#6355 and #5308 asking it to. **So this table is ours, and every row states its
    reason or it is folklore.**

    ⚠ **This is not retry classification.** The neighbouring industry idea - transient versus
    permanent, retry the first - is a different axis. Nothing here retries anything; the question
    is only whether to keep going.
    """
    # ⚠ **The CAUSE CHAIN is walked, not just the exception handed in.** `LocalDestination.upload`
    # raises `DestinationError(...) from outcome.error`, so organize's handler never sees an
    # `OSError` at all - and the first draft of `(agi)`, which took an `OSError` and tested
    # `isinstance`, was therefore **inert on the surface that runs most**. Caught by its own
    # end-to-end test rather than in review, which is the only reason it is not shipped.
    found = underlying_oserror(error)
    if found is None:
        return False
    error = found
    kind = classify_unwritable(error)
    if kind is Unwritable.NO_SPACE:
        # 🔑 **The strongest row, and it is a mechanism rather than an inference.** A disk does not
        # refill between files. On a copy-on-write filesystem it is worse than that: btrfs needs
        # to allocate metadata even to DELETE, so a full one can refuse the cleanup as well - and
        # it *"will change your filesystem to read-only to protect itself"*. At that point every
        # remaining file fails, so continuing buys N failures describing one condition.
        return True
    if kind is Unwritable.QUOTA:
        # An account's allowance is external to this run and nothing the run does clears it.
        return True
    if kind is Unwritable.FAILING:
        # `EIO`. Hardware giving up is a property of the device, not of one file; the next read
        # reaches the same device.
        return True
    if kind is Unwritable.REFUSED:
        # ⚠ **The one branch `classify_unwritable` cannot decide alone**, because `EROFS` and
        # `EACCES` share a member. A read-only mount stays read-only for the whole run; one
        # file's permissions are one file's. Read from the errno rather than widening
        # `Unwritable` - a new member is an exhaustiveness gate across every match site
        # (`IMPLEMENTATION_STANDARDS.md` §2), and this needs a different ANSWER to an existing
        # condition, not a new condition.
        return error.errno == errno.EROFS
    # ⚠ **`GONE` is deliberately here rather than above.** A vanished *source* is one file
    # somebody moved. A vanished *destination* does persist - and `DestinationDevice.check`
    # already fails closed on exactly that, at the top of every loop, so a second guard here
    # would be two checks for one condition and the one that fires second would look redundant.
    return False


def explain_unwritable_drive(error: OSError) -> str:
    """What went wrong, in words a person can act on rather than an errno.

    **A quota is not a full drive, and they need opposite advice.** ``ENOSPC`` means delete
    something; ``EDQUOT`` means the disk may have plenty of room and this account may not have it,
    so sending that user to free up space points them at files that were never the problem.
    """
    return _DRIVE_WORDS.get(classify_unwritable(error)) or error.strerror or str(error)


def explain_metadata_not_preserved(error: OSError) -> str:
    """The copy arrived; its **decoration** did not. `(aie)`

    ⚠ **A third phrasing rather than a third table, and the distinction is the point.** The six
    conditions above are recognised once, by :func:`classify_unwritable`; what differs here is
    only the sentence, exactly as `_FOLDER_WORDS` differs from `_DRIVE_WORDS`. Adding an errno
    branch here would be the second table this module's docstring exists to prevent.

    ⚠ **AND THE EXISTING WORDS ARE FALSE ON THIS PATH, WHICH IS WHY IT NEEDS ITS OWN.**
    `explain_unwritable_drive` answers `EPERM` with *"the drive is read-only, or this account
    cannot write to it"* - a sentence that has just been disproved by the write that succeeded
    two lines earlier. A user told their drive is read-only about a file now sitting on it looks
    for a hardware fault that is not there.

    **The condition is still classified**, because the advice differs: a quota and a refusal
    reach this for different reasons even though neither costs the user a photograph. What the
    caller must add is the half this sentence deliberately leaves out - **which file, and that it
    is safely on the drive** - because the words below say only what did not happen.
    """
    kind = classify_unwritable(error)
    if kind is Unwritable.REFUSED:
        return "this drive does not let Truestill set timestamps or permissions"
    if kind in (Unwritable.NO_SPACE, Unwritable.QUOTA):
        return "there was no room left on the drive to record them"
    if kind is Unwritable.FAILING:
        return "the drive stopped responding while they were being set"
    return error.strerror or str(error)


def metadata_not_preserved_note(name: str, relative_path: str, error: BaseException) -> str:
    """The whole sentence for a copy that arrived without its timestamps. `(aie)`, `(ain)`

    ⚠ **One home, because there are now TWO ways to reach this state and they must not word it
    differently.** `copystat` can be refused inside the copy (`safe_copy`, `(aie)`) and
    `os.utime` can be refused on the committed file afterwards (`LocalDestination.set_timestamp`,
    `(ain)`) - different call sites, different exception wrappers, **the same fact for the user**:
    the photograph is on the drive and its date stamp is not. Two sentences for one fact is the
    drift this module's docstring exists to prevent.

    **Says the file is safe FIRST.** `explain_metadata_not_preserved` deliberately words only what
    did not happen, because on its own it cannot know; a caller reaching this one is asserting
    that it does.

    Takes a ``BaseException`` and unwraps it, so a caller holding a `DestinationError` does not
    have to remember that the errno is one `__cause__` further down.
    """
    found = underlying_oserror(error)
    reason = explain_metadata_not_preserved(found) if found is not None else str(error)
    return f"{name} was copied to {relative_path!r} and is safe, but {reason}"


def explain_unwritable_folder(error: OSError) -> str:
    """The same six conditions, about a folder on this computer rather than a drive. `(aeo)`

    ⚠ **The noun is the whole reason this exists.** The launch path writes into the user's own
    data directory, which they never chose and cannot swap; telling them *"the drive is
    read-only"* names a thing that is not in the story and sends them looking for hardware.
    """
    return _FOLDER_WORDS.get(classify_unwritable(error)) or error.strerror or str(error)
