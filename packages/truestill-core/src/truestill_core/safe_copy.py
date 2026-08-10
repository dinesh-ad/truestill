"""One copy that never leaves bytes nobody owns - and never deletes bytes it did not write.

**The defect this closes, observed rather than theorised** (`(abu)`). `shutil.copy2` raised
`[Errno 5]` at 802 MB of an 852 MB video and left what it had written, carrying a correct
organized name, with no `files` row and no `file_copies` row behind it. The run reported
`1 failed`. It did not report that 802 MB of it had arrived. `rescan` finds it as STRAY, which is
how it was found at all.

**Why the obvious fix is dangerous, and this one is not.** `copy2` opens the SOURCE first. A
failure before the destination is opened - unreadable source, denied permission, a parent that
could not be made - leaves the target **untouched**. And at two of the three call sites the
target can legitimately be occupied already: `LocalDestination.relocate` overwrites a partial
from an interrupted run *by design*, and `service/backup.py` builds its work list from the
CATALOG, so anything the catalog does not know about can be sitting at that path. An `unlink` in
the `except` would delete a user's file to tidy up after an error that never touched it.

So the rule is **remove only what this call created**, and the `exists()` answer is taken here,
immediately before the copy - never accepted from a caller. `organizer._free_relative` also
checks, some lines earlier; a stale "it was free" is precisely the input that would turn this
into a deletion.

**Never raises.** The failure that produced a partial is often the one that will refuse the
delete - a drive pulled out, a read-only mount, the same I/O error - and a cleanup that raised
would replace a reported failure with an unreported one. When the removal fails the outcome names
the path and the size, so a person who watched 800 MB cross a slow link is told what is on their
disk rather than left to wonder.

Lives in core rather than on `Destination` because `service/backup.py` never goes through that
interface: it calls `shutil.copy2` on paths directly.
"""

from __future__ import annotations

import contextlib
import shutil
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class CopyOutcome:
    """What happened, in a form a caller can turn into its own message. **Never an exception.**"""

    ok: bool
    error: OSError | None = None
    #: A partial this call wrote and could not remove. `None` when there is nothing left behind -
    #: including when the target was already occupied, because an untouched incumbent is not ours.
    leftover: Path | None = None
    #: How much is sitting there, so the report can say it rather than gesture at it.
    leftover_bytes: int = 0


def _size_of(path: Path) -> int:
    with contextlib.suppress(OSError):
        return path.stat().st_size
    return 0


def copy_leaving_nothing(source: Path, target: Path) -> CopyOutcome:
    """Copy ``source`` to ``target``; on failure remove the bytes **this call** wrote.

    **The signature is the guarantee. Do not add an ``existed=`` parameter**, however convenient
    it looks at a call site that has already checked - `organizer._free_relative` has, some lines
    earlier. A caller's answer is stale by the time it arrives, and a stale "it was free" is the
    single input that turns the cleanup below into deleting somebody else's file. Taking only the
    two paths is what makes that unreachable rather than unlikely, and
    `test_the_decision_is_taken_here_and_never_passed_in` fails if a third parameter appears.

    Returns rather than raises: see the module note on why a cleanup must never replace a
    reported failure with an unreported one.
    """
    # Taken here and now, not accepted from a caller: a stale "it was free" is the one input
    # that would turn the cleanup below into a deletion of somebody else's file.
    occupied_before = target.exists()
    try:
        shutil.copy2(source, target)
    except OSError as error:
        if occupied_before or not target.exists():
            # Either it was not ours to begin with, or the copy died before creating anything.
            return CopyOutcome(ok=False, error=error)
        size = _size_of(target)
        try:
            target.unlink()
        except OSError:
            return CopyOutcome(ok=False, error=error, leftover=target, leftover_bytes=size)
        return CopyOutcome(ok=False, error=error)
    return CopyOutcome(ok=True)
