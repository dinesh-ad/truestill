"""A copy whose bytes take the real name only once they are all there.

**The defect this closes, observed rather than theorised** (`(abu)`). `shutil.copy2` raised
`[Errno 5]` at 802 MB of an 852 MB video and left what it had written, carrying a correct
organized name, with no `files` row and no `file_copies` row behind it. The run reported
`1 failed`. It did not report that 802 MB of it had arrived.

**The first fix removed the partial afterwards; this one never creates it** (`(acj)`). The copy
goes to a sibling under the target's own name plus :data:`STAGING_SUFFIX`, and only a completed
copy is renamed onto the target. Two things follow, and the second is the reason this is worth
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
import shutil
from dataclasses import dataclass
from pathlib import Path

#: Appended to the target's full name, so `IMG_0001.jpg` stages at `IMG_0001.jpg.partial`.
#: The same suffix `archive_extract` uses for the same idea - one vocabulary for "bytes that have
#: not earned their name yet" - and deliberately not a dot-prefix: a hidden file is skipped by
#: `scan_source` without being counted, while an unrecognized extension is counted and named.
STAGING_SUFFIX = ".partial"


@dataclass(frozen=True, slots=True)
class CopyOutcome:
    """What happened, in a form a caller can turn into its own message. **Never an exception.**"""

    ok: bool
    error: OSError | None = None
    #: Bytes this call wrote and could not remove. `None` when nothing was left behind. Under
    #: staging this is always the staged sibling, never the target - the target is only ever
    #: written by a rename, which leaves nothing half-done for us to own.
    leftover: Path | None = None
    #: How much is sitting there, so the report can say it rather than gesture at it.
    leftover_bytes: int = 0


def _size_of(path: Path) -> int:
    with contextlib.suppress(OSError):
        return path.stat().st_size
    return 0


def _discard(temp: Path, error: OSError) -> CopyOutcome:
    """Remove a staged file, reporting it when it will not go. Never raises."""
    size = _size_of(temp)
    try:
        temp.unlink(missing_ok=True)
    except OSError:
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
        return CopyOutcome(ok=True)

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
    """
    temp = target.with_name(target.name + STAGING_SUFFIX)
    try:
        shutil.copy2(source, temp)
    except OSError as error:
        failed = _discard(temp, error)
        return StagedCopy(
            ok=False,
            error=error,
            leftover=failed.leftover,
            leftover_bytes=failed.leftover_bytes,
        )
    return StagedCopy(ok=True, temp=temp, target=target)


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
    return staged.commit()
