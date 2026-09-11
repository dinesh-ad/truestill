"""The free tier's cumulative cap, and whether a run may start. `DECISIONS.md` D16.

**Stage 1 again: the mechanism with nothing behind it.** Nothing in the product calls this yet -
no route reads it, no screen shows it, and no organize run records against it. The cap is being
proved while it is still free to change, exactly as the token format was.

**What is capped, precisely: files an organize run WRITES, cumulative across every run.** Not
files scanned, not files previewed, not files in a library. D16 §1 rules the cumulative part and
gives the reason - *"A per-run cap is not a cap: a user runs it n times and the free tier is the
entire product."*

**What is NOT capped, and this is the boundary D6 §4 calls immovable.** Opening, scanning,
previewing, finding, browsing, exporting, retrieving and reading the catalog are untouched at any
count, because the cap governs only what truestill *writes into a library*. `DECISIONS.md:384` -
*"Nothing behind the paywall may ever stand between a user and their own files."*

**A lapsed licence is UNCAPPED**, which is D16 §2 followed to its conclusion rather than an
oversight: the buyer paid for an organiser with no cap, and *"a lapsed licence loses nothing it
bought."* What lapses is entitlement to new versions, and that is enforced by not shipping them
(D16 §4), never by taking a number away from someone here.

⚠ **THE COUNTER IS RESETTABLE AND THAT IS THE DESIGN, NOT A DEFECT.** D16 §3: *"Enforcement is a
speed bump, not a wall."* This file is plain JSON - unsigned, unobfuscated, unchecksummed - and
deleting it, or editing it to zero, restores the full allowance. Enforcing the count properly
would require asking a server, which D5 forbids outright. So **hardening this is the refused
direction**, and the refusal is written here rather than left for whoever next notices the file
is editable: every mechanism that makes the count harder to reset makes it likelier to strand
someone who paid.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Final

from truestill_core.app_paths import allowance_path
from truestill_core.licence import Licence, LicenceState
from truestill_core.models import ActionResult, ActionStatus

#: D16 §1's starting number, and it is deliberately low.
#:
#: > **Raising a cap later is a gift. Lowering one is Evernote.** In 2023 Evernote cut its free
#: > tier from 100,000 notes to 50, and took immediate and lasting public damage for it.
#:
#: A number set generously and corrected downward costs more reputation than the revenue it
#: recovers, so it starts where every later move is upward. D6 §4's instrument decides what it
#: should become: real users, not a guess made before anyone has used the thing.
FREE_FILE_ALLOWANCE: Final = 1_000

#: The counter file's format version, so a later shape change is a migration rather than a reset.
USAGE_VERSION: Final = 1

#: The sentence that makes an early refusal worth making. **Public, and imported rather than
#: retyped**, because `licence_notice` needs the identical words for a run stopped by a licence
#: it could not read - two spellings of one reassurance is the drift §9 exists to prevent.
#:
#: A user told only that something was refused has to go and look at their library to find out
#: what state it is in. D16 §4's whole reason for asking the question before anything moves is
#: worthless if the message does not say that is what happened.
RUN_DID_NOT_START: Final = "Nothing has moved - truestill does not start a run it cannot finish."

#: ``None`` as an allowance means **uncapped**, and it is a distinct value rather than a very
#: large number on purpose: a sentinel integer invites arithmetic that quietly reintroduces a
#: ceiling, and there is no number here that is "effectively unlimited" for a library of photos.
Allowance = int | None


@dataclass(frozen=True, slots=True)
class CapVerdict:
    """Whether a run may start, and everything a surface needs to say why it may not.

    The numbers travel with the verdict because D16's refusal has to *name* them - a cap that
    says "not allowed" without saying how many files remain is the nag D6 §3 forbids, wearing a
    different hat.
    """

    may_start: bool
    will_organize: int
    remaining: Allowance
    reason: str = ""


def may_start(will_organize: int, remaining: Allowance) -> CapVerdict:
    """**The whole cap, as a pure function.** No filesystem, no licence, no clock, no I/O.

    ⚠ **REFUSE TO START, NEVER STOP MID-RUN** (D16 §4). Half an organize run is the worst state
    available: some files moved, some not, and a user who cannot tell which. This product's
    promise is that a run either happens or does not, so the question is asked **before anything
    moves** - which is possible only because the preview already knows ``will_organize``.

    The boundary, stated rather than left to the comparison: a run that would write **exactly**
    the remaining allowance **starts**. The allowance is what may be written, not what may be
    approached, and refusing the run that lands exactly on it would make the advertised number a
    lie by one.

    ``remaining=None`` is uncapped and returns immediately - an entitled user's run is never
    arithmetic.
    """
    if remaining is None:
        return CapVerdict(may_start=True, will_organize=will_organize, remaining=None)

    if will_organize <= remaining:
        return CapVerdict(may_start=True, will_organize=will_organize, remaining=remaining)

    return CapVerdict(
        may_start=False,
        will_organize=will_organize,
        remaining=remaining,
        reason=_refusal(will_organize, remaining),
    )


def remaining_for(state: LicenceState, used: int) -> Allowance:
    """How much allowance a licence in ``state`` has left, given ``used`` already written.

    ⚠ **LAPSED is uncapped**, by D16 §2. UNREADABLE is **not**, and that asymmetry is deliberate
    rather than an omission: a token that will not verify cannot be told from no token at all, so
    it cannot be the basis of an entitlement. The cost is bounded and recoverable - a paying user
    with a damaged file can still open, find, browse and export everything, still organize
    whatever allowance remains, and is told in `licence`'s own wording to re-download. The
    alternative, treating unreadable as entitled, would make the cap bypassable by writing
    garbage into the token, which is not a wall this design wants either way but is a worse
    reason to have no wall.

    Never negative: a counter that has run past the allowance answers ``0``, not a debt.
    """
    if state in {LicenceState.ACTIVE, LicenceState.LAPSED}:
        return None
    return max(0, FREE_FILE_ALLOWANCE - used)


def remaining_for_licence(licence: Licence, used: int) -> Allowance:
    """:func:`remaining_for` reached through a whole :class:`~truestill_core.licence.Licence`."""
    return remaining_for(licence.state, used)


def files_written() -> int:
    """How many files organize runs have written on this installation. **Never raises.**

    ⚠ **Missing, corrupt, unreadable, negative and non-integer all answer ZERO, and one rule
    covers them because any other answer punishes an accident without deterring intent.** The
    counter is already resettable by deleting the file (D16 §3), so treating a damaged one as
    exhausted would stop an organize run for a user who did nothing wrong while stopping nobody
    who meant to. Corrupting a file is strictly harder than deleting it; a design that punished
    the first and permitted the second would be a wall facing the wrong way.

    Hand-edited to zero is the same answer, and it is the speed bump working as ruled rather than
    a hole to be closed.
    """
    try:
        raw = allowance_path().read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return 0

    try:
        record = json.loads(raw)
    except json.JSONDecodeError:
        return 0
    if not isinstance(record, dict):
        return 0

    written = record.get("files_written")
    # `isinstance(True, int)` is True in Python, so a boolean would otherwise arrive as 1 - the
    # same trap `licence._payload_from` guards on `covers_through`, one file over.
    if not isinstance(written, int) or isinstance(written, bool) or written < 0:
        return 0
    return written


def record_files_written(count: int) -> int:
    """Add ``count`` to the cumulative total and return the new one. **Never raises.**

    **Read-modify-write, with the read going through :func:`files_written`**, so a damaged
    counter is replaced by a sound one rather than compounding. Two runs at once can lose an
    increment; that is accepted for the same reason nothing here is signed - the value of the
    number is not worth the machinery, and D16 §3 already settled which way this trades.

    Failing to write is **not** an error a run may die on. A full disk must not be able to stop
    an organize run that was already permitted - the write is bookkeeping, and the work it
    records has more value than the record.
    """
    total = files_written() + max(0, count)
    target = allowance_path()
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps({"v": USAGE_VERSION, "files_written": total}, separators=(",", ":"))
        target.write_text(payload + "\n", encoding="utf-8")
    except OSError:
        return total
    return total


#: The statuses that mean **this run put a file in the library**, which is what the cap counts.
#:
#: ⚠ **THIS IS NOT `organizer._BYTES_WRITTEN_STATUSES`, AND THE DIFFERENCE IS ONE MEMBER ON
#: PURPOSE.** That set answers *"did bytes reach a disk"* - it feeds the disk-filling message, and
#: its own comment says a rename is excluded because *"counting one would put a number in the
#: disk-filling message that no disk ever saw"*. This set answers a different question: what did
#: the run **organize**. An in-place move writes no bytes and still files a photograph, so it is
#: charged here and not there.
#:
#: `ALREADY_PLACED` is absent for the mirror reason: an in-place re-run over a file that is
#: already at its target does nothing at all, and charging a user for a second run that moved
#: nothing would make re-running - the ordinary way people recover from a partial run - cost them
#: allowance for work that already happened.
#:
#: `PLANNED` is absent because that is a dry run, `DUPLICATE` and `SKIPPED_UNDATED` because the
#: file stayed where it was, and `FAILED` because nothing landed.
FILES_WRITTEN_STATUSES: Final = frozenset(
    {
        ActionStatus.UPLOADED,
        ActionStatus.RENAMED,
        ActionStatus.MOVED,
        ActionStatus.MOVE_KEPT,
        ActionStatus.MOVED_IN_PLACE,
    }
)


def files_written_by(results: Iterable[ActionResult]) -> int:
    """How many files a finished run actually put in the library.

    **Counted from what happened, never from what was planned**, which is the whole of D16 §4's
    "record after the run, not before". A run that was stopped by a full disk, or cancelled
    halfway, hands back the results it managed - and those files are in the library, so they are
    charged. A run that planned 4,000 files and wrote 12 costs 12.
    """
    return sum(1 for result in results if result.status in FILES_WRITTEN_STATUSES)


def _refusal(will_organize: int, remaining: int) -> str:
    """The refusal, worded once. `IMPLEMENTATION_STANDARDS.md` §9.

    It names both numbers because the user's next decision needs them: how many this run would
    write, and how many are left. It says what is still possible rather than only what is not,
    and it does not nag - D6 §3 forbids a countdown, and a sentence that appears exactly when a
    run is refused is not one.
    """
    if remaining == 0:
        return (
            f"This run would organize {will_organize:,} files, and the free allowance of "
            f"{FREE_FILE_ALLOWANCE:,} is used up. {RUN_DID_NOT_START} Finding, browsing and "
            "exporting your library stay free - organizing more files needs a licence."
        )
    return (
        f"This run would organize {will_organize:,} files, and {remaining:,} of the free "
        f"allowance of {FREE_FILE_ALLOWANCE:,} remain. {RUN_DID_NOT_START} Organize a smaller "
        "folder, or buy a licence to lift the limit."
    )
