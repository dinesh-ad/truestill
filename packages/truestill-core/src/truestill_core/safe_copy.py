"""A copy whose bytes take the real name only once they are all there.

**The defect this closes, observed rather than theorised** (`(abu)`). `shutil.copy2` raised
`[Errno 5]` at 802 MB of an 852 MB video and left what it had written, carrying a correct
organized name, with no `files` row and no `file_copies` row behind it. The run reported
`1 failed`. It did not report that 802 MB of it had arrived.

**The first fix removed the partial afterwards; this one never creates it** (`(acj)`). The copy
goes to a sibling built by :func:`staging_path` - the target's name, a **per-process token**, then
:data:`STAGING_SUFFIX` - and only a completed copy is renamed onto the target. ⚠ **The token is
not decoration**: a staging path derived from the target alone is shared by every process that
computes it, and two `organize --apply` runs writing one destination wrote into **one** file.
Measured, `(aaw)`. Two things follow, and the second is the reason this is worth
doing rather than tidy:

* **The ownership question disappears.** The old form had to decide whether a file at the target
  was ours to remove, because at two call sites the target may legitimately be occupied - and a
  wrong answer deletes a user's file. Nothing here ever writes at the target path, so there is no
  question to get right. That heuristic is gone rather than improved.
* **A caller can check the bytes before they take the name.** `service/backup.py` hashes what it
  wrote and discards a copy that does not verify; until now it did that *after* the bytes were
  already at the real name, which is `(abu)`'s own shape one step later.

**What this claims, exactly: no partial ever takes the real name.** That holds on every
filesystem. It is deliberately NOT a claim that the rename is atomic across a crash - that is a
POSIX guarantee, and `IMPLEMENTATION_STANDARDS.md` §1 already records that FAT32 and exFAT journal
nothing, so a power cut during the directory-entry update can still orphan it. Against another
*process* the rename is indivisible everywhere; against a power cut on removable media it is not,
and the word "atomic" is avoided here so it cannot be quoted back as a guarantee nobody made.

**No `fsync`, deliberately - do not add one as an obvious improvement.** `shutil.copy2` does not
fsync today, and `archive_extract` writes media the same way for the same reason. The defect being
closed is a *name* worn by incomplete bytes; `fsync` addresses whether *content* survives power
loss, which `copy_sha256` and `verify` already own. A flush per file on a photo library is a full
write-through per file, and §1 already rules that on journal-less media the **journal** is what
makes a run recoverable, not the rename.

**Never raises.** The failure that produced a leftover is often the one that will refuse the
delete - a drive pulled out, a read-only mount, the same I/O error - and a cleanup that raised
would replace a reported failure with an unreported one. When the removal fails the outcome names
the path and the size, so a person who watched 800 MB cross a slow link is told what is on their
disk rather than left to wonder.

**A leftover is now debris rather than a photo, and that is the quiet win.** The old partial wore a
media extension at the organized name, so nothing could tell it from a real file; `rescan` reported
it as STRAY, which is how the original was found. A staged file ends in :data:`STAGING_SUFFIX`,
which is not in `MEDIA_EXTENSIONS`, so `scan_source` can never mistake it for a photo. The cost of
that is stated rather than glossed: **rescan no longer sees it either**, because rescan is fed
`scan_source(...).media`. It is counted and named in the skipped census as an unrecognized
extension instead, and `(acz)` carries what is still owed.

Lives in core rather than on `Destination` because `service/backup.py` never goes through that
interface: it copies paths directly.
"""

from __future__ import annotations

import contextlib
import os
import secrets
import shutil
from dataclasses import dataclass
from pathlib import Path

#: Appended LAST, so `IMG_0001.jpg` stages at `IMG_0001.jpg.<token>.partial`.
#: The same suffix `archive_extract` uses for the same idea - one vocabulary for "bytes that have
#: not earned their name yet" - and deliberately not a dot-prefix: a hidden file is skipped by
#: `scan_source` without being counted, while an unrecognized extension is counted and named.
STAGING_SUFFIX = ".partial"

#: Unique to THIS PROCESS, and the whole of `(aaw)`'s first half.
#:
#: ⚠ **A staging path derived from the target alone is shared between processes**, and that was
#: measured rather than reasoned: two `organize --apply` runs writing one destination wrote into
#: **one** `.partial`, then one renamed it and reported success while holding the other run's
#: bytes. 2 of 9 attempts on real photographs lost 99 and 45 organized copies. The reproduction is
#: kept at `scratch-race-2026-08-22`.
#:
#: **PID and randomness, not either alone.** A pid is unique among live processes on one machine
#: and repeats across machines sharing a mount; six random hex characters cover that without
#: needing a machine identity. Computed **once per process** rather than per copy, so a crashed
#: run's litter is attributable to one run.
#:
#: ⚠ **The token goes BEFORE the suffix, not after**, because `.partial` ending the name is a
#: contract: `cli`'s rescan picks debris with `path.name.endswith(STAGING_SUFFIX)`, and
#: `scan_source` must keep seeing an unrecognized extension rather than a media one. The shape is
#: `thumbnails.py`'s, which already staged this way.
_STAGING_TOKEN = f"{os.getpid():x}{secrets.token_hex(3)}"


def staging_overhead_bytes() -> int:
    """How many bytes :func:`staging_path` adds to a name. **Measured, never written down.**

    ⚠ **IT IS NOT A CONSTANT, AND THAT IS THE WHOLE REASON THIS IS A FUNCTION.** The token is
    ``f"{os.getpid():x}"`` plus six hex characters, so its width follows the pid the OS happened
    to hand this process. On a Linux box with the default ``pid_max`` of 4,194,304 the pid is one
    to six hex digits, so this returns **16 to 21** and the usable budget for a dated filename
    moves between **218 and 223 bytes on one machine**.

    🔑 **`(aid)` recorded 219 as "the real budget" and it is one process's reading of that
    range** - measured in P140 with an 11-character token, and re-measured in P146 with a
    10-character one, where the true threshold was 220. A hardcoded number would be wrong on most
    runs, in the safe direction sometimes and the unsafe direction others.
    """
    return len(f".{_STAGING_TOKEN}{STAGING_SUFFIX}".encode())


def staging_path(target: Path) -> Path:
    """Where bytes wait before they earn ``target``'s name. **Never shared between processes.**

    One home for the three sites that used to build this themselves - here, `archive_extract` and
    `selfcheck` - because two copies of a staging rule disagree the first time one is corrected,
    and this one has already been wrong once.
    """
    return target.with_name(f"{target.name}.{_STAGING_TOKEN}{STAGING_SUFFIX}")


@dataclass(frozen=True, slots=True)
class CopyOutcome:
    """What happened, in a form a caller can turn into its own message. **Never an exception.**"""

    ok: bool
    error: OSError | None = None
    #: The bytes arrived and their **decoration** did not - see :func:`staged_copy`. Set with
    #: ``ok=True``, which is the whole point: this is a copy that succeeded, carrying a fact the
    #: caller should say out loud rather than a failure it should report.
    metadata_error: OSError | None = None
    #: Bytes this call wrote and could not remove. `None` when nothing was left behind. Under
    #: staging this is always the staged sibling, never the target - the target is only ever
    #: written by a rename, which leaves nothing half-done for us to own.
    leftover: Path | None = None
    #: How much is sitting there, so the report can say it rather than gesture at it.
    leftover_bytes: int = 0


def _size_of(path: Path) -> int | None:
    """The staged file's size, or ``None`` when the filesystem would not say. `(aid)`

    ⚠ **`None` RATHER THAN `0`, AND THE DIFFERENCE REACHED A USER.** This returned `0` for both
    *"the partial is empty"* and *"there is no answer"*, and `_discard` then reported a leftover
    of `0 bytes` for a file that had **never been created**. Measured in P140: a name too long to
    create is also too long to `stat` and too long to `unlink`, so every step failed with the same
    errno and the message named a path that was not there.

    The honest shape already existed one module over - `organizer._safe_size` returns
    ``int | None`` for exactly this reason - and `(aac)`'s ruling is the general form: a value
    that means two things is not acceptable where one of them is *"we do not know"*.
    """
    with contextlib.suppress(OSError):
        return path.stat().st_size
    return None


def _discard(temp: Path, error: OSError) -> CopyOutcome:
    """Remove a staged file, reporting it when it will not go. Never raises.

    ⚠ **A leftover is claimed only where there is evidence of one.** `unlink(missing_ok=True)`
    swallows `FileNotFoundError` and nothing else, so a name the filesystem refuses outright
    raises here just as the create did - and reporting that as debris sends the user looking for
    a file that was never written.
    """
    size = _size_of(temp)
    try:
        temp.unlink(missing_ok=True)
    except OSError:
        if size is None:
            # The unlink failed and the stat failed too: no evidence anything was created, and
            # `(aey)`'s rule applies - a filesystem that will not describe a path has not
            # established that something is at it.
            return CopyOutcome(ok=False, error=error)
        return CopyOutcome(ok=False, error=error, leftover=temp, leftover_bytes=size)
    return CopyOutcome(ok=False, error=error)


@dataclass(frozen=True, slots=True)
class StagedCopy:
    """A completed copy sitting under a name that is not the target's yet.

    Two ends, and a caller must choose one: :meth:`commit` gives the bytes the real name,
    :meth:`abandon` removes them. Nothing here is reached unless the copy succeeded, so `temp` is
    a real file whenever `ok` is true.
    """

    ok: bool
    #: Where the finished bytes are. `None` when the copy failed.
    temp: Path | None = None
    #: Where they go on :meth:`commit`. Carried so a caller cannot commit to a different path
    #: than the one that was staged for.
    target: Path | None = None
    error: OSError | None = None
    leftover: Path | None = None
    leftover_bytes: int = 0
    #: See :func:`staged_copy`. Travels with ``ok=True``, and :meth:`commit` carries it onto the
    #: :class:`CopyOutcome` so a caller two layers up does not have to know staging exists.
    metadata_error: OSError | None = None

    def commit(self) -> CopyOutcome:
        """Give the staged bytes the target's name, replacing whatever is there.

        `Path.replace` rather than `Path.rename`: rename raises on Windows when the target
        exists, and an occupied target is ordinary here - `relocate` overwrites an interrupted
        run's copy by design, and `backup` writes paths the catalog may not know about.
        """
        if not self.ok or self.temp is None or self.target is None:  # pragma: no cover - guarded
            message = "commit() on a copy that did not complete"
            raise ValueError(message)
        try:
            self.temp.replace(self.target)
        except OSError as error:
            return _discard(self.temp, error)
        return CopyOutcome(ok=True, metadata_error=self.metadata_error)

    def abandon(self) -> CopyOutcome:
        """Discard the staged bytes. The target is untouched, because it was never written."""
        if self.temp is None:  # pragma: no cover - guarded by construction
            return CopyOutcome(ok=False, error=self.error)
        removed = _discard(self.temp, OSError("staged copy abandoned"))
        return CopyOutcome(
            ok=False, leftover=removed.leftover, leftover_bytes=removed.leftover_bytes
        )


def staged_copy(source: Path, target: Path) -> StagedCopy:
    """Copy ``source`` to a sibling of ``target``, leaving the target untouched either way.

    **The signature is the guarantee, and it is the same one the one-shot form carries.** Do not
    add a parameter naming the staging path or asking a caller whether the target was free. The
    staged name is derived from the target here, so it cannot be pointed somewhere this function
    would not clean up, and `test_the_staged_name_is_derived_here_and_never_passed_in` fails if a
    third parameter appears.

    Returns rather than raises: see the module note.

    ⚠ **`copyfile` then `copystat`, deliberately, rather than the one `copy2` that is both**
    (`(aie)`). `copy2` **is** those two calls, and wrapping the pair in one `except` cannot tell
    *"none of the bytes arrived"* from *"all of the bytes arrived and the mtime did not"*. It
    reported the second as the first and threw the file away - measured, on a `copystat` refused
    with `EPERM`: three complete photographs deleted, three `FAILED` lines, and the run continued
    to do it to every file on that destination.

    **The discriminator is WHICH CALL RAISED, and it is structural for that reason.** Two shapes
    were available and the other is refused here rather than left as a choice:

    * **Not the errno.** `EPERM` from `copyfile` (the destination will not take the write) and
      `EPERM` from `copystat` (the mount will not take a `utime`) are the same number with
      opposite meanings, so no errno table can separate them. A *"keep on any `OSError`"* is
      worse still: it keeps `(abu)`'s 802-MB `EIO` truncation, which is the defect this module
      was written to close.
    * **Not a size comparison.** It is an inference where this is a fact - the source can change
      under a long copy, and a short file that happens to match tells you nothing about whether
      the write completed. It also needs two `stat` calls to answer a question the call stack
      already knows.

    So a `copyfile` failure discards exactly as before, and a `copystat` failure returns
    ``ok=True`` with :attr:`StagedCopy.metadata_error` set. **This covers every step inside
    `copystat`, not just the one that was measured**: `utime`, `chmod`, xattrs and `chflags` all
    raise from the same call, and two of them - `utime`, which the stdlib does not guard at all,
    and `chmod`, which it guards against `NotImplementedError` rather than `OSError` - reach a
    caller unfiltered.

    **What is lost when `copystat` fails is the decoration and nothing else**: the copy keeps
    default permissions and its own mtime. Truestill has no filesystem-mtime date tier
    (`models.DateSource`, and `dates.py`'s `DATE_TAGS` refuses one by name) and identity is
    `sha256`, so nothing the product decides is computed from either. This is the behaviour the
    standard library documents for `shutil.copy` and names for callers that *"cannot tolerate
    metadata errors"* - and what rsync (exit 23, file kept), restic and robocopy all do.
    """
    temp = staging_path(target)
    try:
        shutil.copyfile(source, temp)
    except OSError as error:
        failed = _discard(temp, error)
        return StagedCopy(
            ok=False,
            error=error,
            leftover=failed.leftover,
            leftover_bytes=failed.leftover_bytes,
        )
    metadata_error: OSError | None = None
    try:
        shutil.copystat(source, temp)
    except OSError as error:
        # Whatever `copystat` managed before it raised is kept. It is not re-attempted and not
        # rolled back: a partial `copystat` is a partly-decorated file, never a partly-written one.
        metadata_error = error
    return StagedCopy(ok=True, temp=temp, target=target, metadata_error=metadata_error)


def copy_leaving_nothing(source: Path, target: Path) -> CopyOutcome:
    """Copy ``source`` to ``target`` in one step, staging so no partial ever wears its name.

    The two-argument form for callers with nothing to check between the copy and the rename.
    Callers that do have something to check - a hash, a size - use :func:`staged_copy` and commit
    only when it passes; that is the whole reason the staged form exists.

    **Do not add an ``existed=`` parameter**, however convenient it looks at a call site that has
    already checked. It was never needed and now cannot be: nothing is written at the target, so
    no code here has to decide whether a file there is ours.
    """
    staged = staged_copy(source, target)
    if not staged.ok:
        return CopyOutcome(
            ok=False,
            error=staged.error,
            leftover=staged.leftover,
            leftover_bytes=staged.leftover_bytes,
        )
    # `commit` carries `metadata_error` through, so this form's caller sees the same fact without
    # having to know a staged copy existed.
    return staged.commit()
