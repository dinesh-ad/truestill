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


@dataclass(frozen=True, slots=True)
class AccountSummary:
    """Everything the account surface says, worded here so no surface retypes a sentence.

    ⚠ **This exists because the seam this product keeps getting wrong is a second copy of a
    sentence.** `IMPLEMENTATION_STANDARDS.md` §9's rule is one home per outcome; a rail that built
    its own "Updates until..." string would be a second home the moment the model changed. So the
    frontend renders fields and composes nothing.

    Every string is present in every state - empty rather than absent - so a renderer branches on
    content, never on a key that may not be there.
    """

    state: LicenceState
    #: One line, always. Who is signed in, or what this is when nobody is.
    headline: str
    #: One sentence under it, explaining the state without asking for anything.
    detail: str
    #: The standing licence notice, when there is one. Never blocks - nothing is being refused.
    notice: Notice | None
    #: The free allowance, worded. Empty when the licence is an entitlement and there is no cap.
    allowance: str
    #: What signing out will actually do, said before it is done rather than after.
    sign_out_warning: str


def account_summary(licence: Licence, remaining: int | None, cap: int) -> AccountSummary:
    """What the account surface shows, for any state. **Pure.**

    ⚠ **D16 §1 binds every branch: none of these is a gate.** The app always opens and every
    feature works, so every sentence below is informational - there is no countdown, no nag, and
    nothing here withholds anything. `ABSENT` in particular is **not** an error state: it is what
    every new user is, and it says what the product is rather than what they are missing.

    ``remaining`` is ``None`` for an entitlement, which is why the allowance line is empty there
    rather than reading "unlimited" - a number that is absent because it does not apply should not
    be dressed up as a very large one.
    """
    payload = licence.payload
    notice = standing_notice(licence)
    allowance = "" if remaining is None else _ALLOWANCE.format(remaining=remaining, cap=cap)

    if licence.state is LicenceState.ACTIVE and payload is not None:
        detail = _ACTIVE.format(edition=payload.edition.title(), until=payload.updates_until)
        return _summary(licence, payload.name, detail, notice, allowance)
    if licence.state is LicenceState.LAPSED and payload is not None:
        detail = _LAPSED.format(edition=payload.edition.title(), until=payload.updates_until)
        return _summary(licence, payload.name, detail, notice, allowance)
    if licence.state is LicenceState.SIGNED_OUT:
        return _summary(licence, _SIGNED_OUT_HEAD, _SIGNED_OUT, notice, allowance)
    if licence.state is LicenceState.UNREADABLE:
        return _summary(licence, _UNREADABLE_HEAD, _UNREADABLE, notice, allowance)
    # ABSENT, and the two entitlement states when a payload somehow did not survive - which is
    # unreachable through `verify_token` and is still answered rather than left to fall off the
    # end, because a rail with no sentence in it is the one outcome nobody would notice.
    return _summary(licence, _ABSENT_HEAD, _ABSENT, notice, allowance)


def _summary(
    licence: Licence, headline: str, detail: str, notice: Notice | None, allowance: str
) -> AccountSummary:
    return AccountSummary(
        state=licence.state,
        headline=headline,
        detail=detail,
        notice=notice,
        allowance=allowance,
        sign_out_warning=_SIGN_OUT_WARNING,
    )


def standing_notice(licence: Licence) -> Notice | None:
    """The licence notice with **no run in play** - what the account surface shows at rest.

    D16 §5 rules that a non-blocking licence notice appears with the account, in the same place as
    the allowance, *"because it is the user's relationship with their licence and that has one
    home"*. This is that question, and it is :func:`notice_for` asked with a run of zero files
    rather than a second code path - a run that writes nothing is always permitted, so the answer
    can only ever be the non-blocking licence notice or silence.
    """
    return notice_for(licence, CapVerdict(may_start=True, will_organize=0, remaining=None))


#: Why a run stopped for someone whose licence may well be valid, said without accusing them.
#:
#: It names the connection the user cannot see - that the run was measured against the **free**
#: allowance because the licence could not be read - so that a paying customer understands they
#: are looking at a file problem rather than a bill.
_WHILE_UNREADABLE: Final = (
    "Until the licence can be read, runs are measured against the free allowance."
)


#: The five states, worded once. Each says what IS true rather than what is missing - D16 §1 makes
#: every one of these informational, so none of them may read as a refusal or a prompt.
#: ⚠ SHORT BY MEASUREMENT, NOT BY TASTE. The summary row is a 232px rail less its padding, the
#: state dot and the chevron - about 154px, or roughly 20 characters at `--type-sm`. "No licence
#: on this computer" rendered as "No licence on this comput..." with the tail under the chevron,
#: which is what a screenshot showed and no assertion would have. The long form lives in
#: :data:`_ABSENT`, inside the fold, where it wraps.
_ABSENT_HEAD: Final = "No licence"
_ABSENT: Final = (
    "truestill is free to use and every feature works. The free allowance covers the files a run "
    "writes. If you have bought a licence, point at the file you downloaded."
)
_SIGNED_OUT_HEAD: Final = "Signed out"
_SIGNED_OUT: Final = (
    "You signed out on this computer, and every feature still works. Your licence has not been "
    "cancelled - point at your licence file to sign back in."
)
_UNREADABLE_HEAD: Final = "Licence not readable"
_UNREADABLE: Final = (
    "Every feature still works, and nothing about your library has changed. Replacing the file "
    "restores your licence."
)
_ACTIVE: Final = "{edition}. Updates included until {until}."
_LAPSED: Final = (
    "{edition}. Updates ran out on {until}. This version is yours for ever and nothing has been "
    "taken away; renewing brings new versions."
)
#: Same ~22-character budget as the headline above it. The first wording - "1,000 of 1,000 free
#: files left to organize" - was 42 characters and truncated under the chevron; the second,
#: "{remaining} free files left", fitted but **dropped the cap**, so a user who had spent 300
#: files could no longer learn what the allowance was from anywhere in the product. Both numbers
#: fit if the words go instead: 19 characters, and the sentence that says what a free allowance
#: IS is one line below in :data:`_ABSENT`.
_ALLOWANCE: Final = "{remaining:,} of {cap:,} left"

#: Said **before** signing out, never after. `(aam)`: *"a casual logout can strand a paying user
#: on an offline machine"*, which is why the action lives inside account details rather than
#: beside Help - and why the one thing it must do is tell the truth about what it removes.
_SIGN_OUT_WARNING: Final = (
    "Signing out removes the licence file from this computer. You will need that file again to "
    "sign back in, so keep a copy before you do."
)
