"""The account surface: who is signed in, what they hold, and what it costs to leave.

**Every sentence here comes from core and none is composed on this side.** `licence_notice`
owns the wording, `licence` owns the states, `allowance` owns the counting; this module turns
three of those into one payload and does no wording of its own. `IMPLEMENTATION_STANDARDS.md` §9
is the rule, and the failure it guards against is specific to this feature: the rail would build
its own "Updates until..." string, the model would change, and two surfaces would say different
things about the same licence.

⚠ **Nothing here is a gate.** `DECISIONS.md` D16 §1: the app always opens, every feature works,
every screen is reachable. This surface is informational in all five states, so no route below
refuses anything and none of them is consulted before doing work.

**Activation is a file on disk**, which is D5's offline path and the whole of activation until a
licensing server exists (`licence.install_token_from`).
"""

from __future__ import annotations

from pathlib import Path
from typing import TypedDict

from truestill_core import allowance, licence
from truestill_core.app_paths import licence_path
from truestill_core.licence_notice import AccountSummary, account_summary


class AccountPayload(TypedDict):
    """What the rail renders. Every field is present in every state.

    ⚠ **Empty strings rather than absent keys**, so a renderer branches on content instead of on
    whether a key arrived. `(ahl)`'s census is about payload keys that quietly stop being sent,
    and a shape that is the same in five states cannot develop that problem in one of them.
    """

    state: str
    headline: str
    detail: str
    #: ``""`` when nobody is signed in. Never invented - it is the name inside the token.
    name: str
    email: str
    #: ``""`` when the licence is an entitlement and no cap applies.
    allowance: str
    #: ⚠ **A STRING, NOT THE `Notice` SHAPE, AND THE CENSUS IS WHY.** The first version shipped
    #: `kind` and `blocks_run` alongside the message, and
    #: `test_no_thirty_fifth_dead_payload_key` refused them: on this surface a notice can only
    #: ever be a non-blocking LICENCE one, because `standing_notice` asks with a run of zero
    #: files and D16 §1 means nothing here refuses anything. Two fields that can each hold one
    #: value are not data, and the same census also refused `edition`, `updates_until` and
    #: `covers_this_build` - every one of them already inside `detail`, in core's words. What is
    #: left is what the rail renders.
    notice: str
    sign_out_warning: str
    #: Where the token lives, so a user who must replace it knows where to put it.
    token_path: str


class ActivationPayload(TypedDict):
    """The result of pointing at a file. ``ok`` is whether the token was installed."""

    ok: bool
    #: The account as it now stands - the same shape the rail already renders, so a successful
    #: activation needs no second request and a failed one cannot leave the rail stale.
    account: AccountPayload
    #: Core's own words when the file was refused; ``""`` on success.
    error: str


def _summary() -> AccountSummary:
    """Read the three sources once and word the result. The only place that joins them."""
    current = licence.read_licence()
    remaining = allowance.remaining_for(current.state, allowance.files_written())
    return account_summary(current, remaining, allowance.FREE_FILE_ALLOWANCE)


def _payload(summary: AccountSummary) -> AccountPayload:
    current = licence.read_licence()
    payload = current.payload
    notice = summary.notice
    return {
        "state": str(summary.state),
        "headline": summary.headline,
        "detail": summary.detail,
        "name": payload.name if payload else "",
        "email": payload.email if payload else "",
        "allowance": summary.allowance,
        "notice": "" if notice is None else notice.message,
        "sign_out_warning": summary.sign_out_warning,
        "token_path": str(licence_path()),
    }


def account() -> AccountPayload:
    """The current account state, for the rail."""
    return _payload(_summary())


def account_activate(path: str) -> ActivationPayload:
    """Install the token at ``path`` if it verifies, and report the account either way.

    **Never raises, for any string.** A user types or pastes this, so it arrives as whatever they
    had - a directory, a folder of downloads, an empty box, a path with a typo. Every one of those
    is an ordinary mistake and gets core's own sentence rather than a traceback.

    ⚠ **A blank path is refused before the filesystem is touched**, because `Path("")` resolves to
    the current working directory, which is a *directory that exists* - so the read fails with a
    message about a file that could not be read when the real answer is that nothing was chosen.
    """
    chosen = path.strip()
    if not chosen:
        return _refused(_NO_PATH)

    result = licence.install_token_from(Path(chosen).expanduser())
    if result.state is licence.LicenceState.UNREADABLE:
        return _refused(result.reason)
    return {"ok": True, "account": account(), "error": ""}


def account_sign_out() -> AccountPayload:
    """Remove the token and record that leaving was deliberate. `(aam)`

    The warning that this removes a file the user will need again is delivered **before** the
    call, by the surface, from `AccountSummary.sign_out_warning` - which is why this function is
    unconditional and has nothing to decide.
    """
    licence.sign_out()
    return account()


def _refused(error: str) -> ActivationPayload:
    return {"ok": False, "account": account(), "error": error}


#: An empty box is not a bad file, and saying so is the difference between a user fixing it and a
#: user hunting for a corrupt download that does not exist.
_NO_PATH = "Choose the licence file you downloaded from your account."
