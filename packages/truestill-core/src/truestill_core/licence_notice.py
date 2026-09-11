"""What a user needs to be told about their entitlement, right now. `DECISIONS.md` D16 §5.

**One question, one answer, and the precedence is the whole module.** A user can have two true
problems at once - a licence file that will not verify *and* a run over the free cap - and two
messages is the same as none: they read the first, act on it, and the second is noise. So this
answers with **at most one notice**, and D16 §5 rules which:

> **The licence problem outranks the cap.** An UNREADABLE token is a thing the user can fix and
> must know about; the cap is a thing they chose by using the product. Showing the cap first
> would send someone to a purchase page when their real problem is a corrupt file.

⚠ **That ordering is not a preference, it is the difference between helping and charging.** A
customer who has already paid, whose token was truncated by a sync client, is *by definition*
capped - `allowance.remaining_for` cannot treat an unverifiable token as an entitlement. Lead
with the cap and they are told to buy a thing they own. Lead with the licence and they are told
to re-download a file, which is the fix.

**Why this lives in core, and what stays out of it.** `catalog_busy` is the pattern and its own
sentence applies unchanged: *"Only recognition and wording are here. Presentation stays with each
surface, which is where it differs: the CLI has an exit code and stderr, the app has an SSE
terminal event and an HTTP status."* Nothing here knows about a screen, a route or a rail slot.

**When it is asked: at Apply, never live.** D16 §5 again - a number that updates as a user types
is a countdown, and D6 §3 forbids countdowns. The preview stays complete and silent about the
cap; this is asked once, when the user asks for the run, before anything moves.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from truestill_core.allowance import RUN_DID_NOT_START, CapVerdict
from truestill_core.licence import Licence, LicenceState


class NoticeKind(StrEnum):
    """Which family a notice belongs to.

    Carried so a surface can route without parsing the sentence - the CLI picks an exit code, the
    app picks a payload `code`. `catalog_busy.CATALOG_BUSY_CODE` is the same idea one module over.
    """

    #: Something is wrong with the licence file itself, and the user can fix it.
    LICENCE = "licence"
    #: The free allowance cannot cover this run.
    CAP = "cap"


@dataclass(frozen=True, slots=True)
class Notice:
    """The one thing to say, and whether saying it also means the run did not start.

    ⚠ **`kind` and `blocks_run` are independent, and conflating them was the trap.** A damaged
    licence on a user well inside the free allowance is worth telling them about and must **not**
    stop their work; the same damaged licence on a user past 1,000 files does stop it. So a
    LICENCE notice comes in both forms, and the message differs accordingly - a surface that
    assumed "licence notice means blocked" would either refuse runs it should allow or stay
    silent about a file the user needs to replace.
    """

    kind: NoticeKind
    message: str
    blocks_run: bool


def notice_for(licence: Licence, verdict: CapVerdict) -> Notice | None:
    """The single notice to show, or ``None`` when there is nothing to say.

    ``None`` is the ordinary answer and is not an absence of information: an entitled user with a
    permitted run is told nothing, which is D6 §3's rule - *"never withholds function to force
    the question"* - applied to silence rather than to function.

    **Pure.** No filesystem, no network, no clock. Both arguments are already-computed answers,
    so this can be exercised in every combination that exists.
    """
    if licence.state is LicenceState.UNREADABLE:
        return _licence_notice(licence, blocks_run=not verdict.may_start)
    if not verdict.may_start:
        return Notice(NoticeKind.CAP, verdict.reason, blocks_run=True)
    return None


def _licence_notice(licence: Licence, *, blocks_run: bool) -> Notice:
    """The licence half, worded once.

    `licence.reason` already says what is wrong with the file and how to replace it, and it is
    not restated here - §9's rule is one home per outcome, and this is a *second* outcome built
    on the first rather than a second telling of it. What this adds is the sentence the user
    needs only when the run was stopped, and it is the **same** sentence the cap refusal uses,
    imported rather than retyped so the two cannot drift apart.
    """
    if not blocks_run:
        return Notice(NoticeKind.LICENCE, licence.reason, blocks_run=False)
    return Notice(
        NoticeKind.LICENCE,
        f"{licence.reason} {RUN_DID_NOT_START} {_WHILE_UNREADABLE}",
        blocks_run=True,
    )


#: Why a run stopped for someone whose licence may well be valid, said without accusing them.
#:
#: It names the connection the user cannot see - that the run was measured against the **free**
#: allowance because the licence could not be read - so that a paying customer understands they
#: are looking at a file problem rather than a bill.
_WHILE_UNREADABLE: Final = (
    "Until the licence can be read, runs are measured against the free allowance."
)
