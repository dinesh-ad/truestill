"""Precedence: when a user has two problems at once, which one do they hear about?

**The case that decides it is a paying customer with a damaged file.** `allowance.remaining_for`
cannot treat an unverifiable token as an entitlement - it has no way to tell one from no token at
all - so a customer whose licence was truncated by a sync client is, by the arithmetic, capped.
Both statements are true at that moment: the licence will not verify, and the run exceeds the
free allowance.

⚠ **Lead with the cap and they are told to buy a thing they already own.** D16 §5 rules the
order, and the reason is not tidiness: *"Showing the cap first would send someone to a purchase
page when their real problem is a corrupt file."* One message at a time, and licence wins.

The four quadrants are all tested because the failure this guards is a function that gets three
of them right.
"""

from __future__ import annotations

import pytest
from truestill_core import allowance
from truestill_core.licence import Licence, LicencePayload, LicenceState
from truestill_core.licence_notice import NoticeKind, notice_for

DAMAGED = "This licence file is damaged and could not be read. Sign in to download a copy."


def _unreadable() -> Licence:
    return Licence(LicenceState.UNREADABLE, reason=DAMAGED)


def _entitled() -> Licence:
    return Licence(
        LicenceState.ACTIVE,
        payload=LicencePayload(
            version=1,
            kid="k1",
            account="a",
            licence="l",
            name="A Buyer",
            email="b@example.com",
            edition="pro",
            covers_through=1,
            issued_at="2026-09-11",
            updates_until="2027-09-11",
        ),
    )


def _refused() -> allowance.CapVerdict:
    verdict = allowance.may_start(4_200, 300)
    assert verdict.may_start is False, "the fixture must actually be a refusal"
    return verdict


def _permitted() -> allowance.CapVerdict:
    verdict = allowance.may_start(10, 300)
    assert verdict.may_start is True, "the fixture must actually be a permission"
    return verdict


# --- the four quadrants --------------------------------------------------------------------


def test_neither_problem_says_nothing_at_all() -> None:
    """**Silence is the ordinary answer and it is a decision, not an absence.**

    D6 §3 forbids a nag, a countdown and a modal. An entitled user with a permitted run hears
    nothing, which is that rule applied to silence rather than to function - and it is what makes
    the messages below carry weight when they do appear.
    """
    assert notice_for(_entitled(), _permitted()) is None


def test_the_cap_alone_speaks_for_itself() -> None:
    """No licence problem, so the cap is the only true thing and the user is told it."""
    notice = notice_for(Licence(LicenceState.ABSENT), _refused())

    assert notice is not None
    assert notice.kind is NoticeKind.CAP
    assert notice.blocks_run is True
    assert "4,200" in notice.message
    assert "300" in notice.message


def test_a_damaged_licence_alone_is_said_without_stopping_the_work() -> None:
    """**A licence notice that does not block, which is the half a naive design loses.**

    Someone well inside the free allowance whose token is damaged needs to know - it is a thing
    they can fix, and it will bite them later. Refusing their run over it would be punishing an
    accident, which is the whole thing D16 §3 refuses to do.
    """
    notice = notice_for(_unreadable(), _permitted())

    assert notice is not None
    assert notice.kind is NoticeKind.LICENCE
    assert notice.blocks_run is False
    assert notice.message == DAMAGED


def test_both_problems_at_once_is_the_licence_and_never_the_cap() -> None:
    """**The ruling itself, and the only quadrant where precedence exists.**

    The cap wording names the free allowance and offers to sell a licence. Showing that to
    someone who has already bought one, because their file was truncated, is the failure D16 §5
    names. So the cap's sentences must be absent, not merely second - which is why the allowance
    figure is asserted missing rather than the licence text asserted present.
    """
    notice = notice_for(_unreadable(), _refused())

    assert notice is not None
    assert notice.kind is NoticeKind.LICENCE
    assert notice.blocks_run is True
    assert DAMAGED in notice.message
    assert "buy a licence" not in notice.message
    assert f"{allowance.FREE_FILE_ALLOWANCE:,}" not in notice.message


def test_a_blocked_licence_notice_still_says_nothing_moved() -> None:
    """The reassurance survives the precedence, and it is the **same words** the cap uses.

    Imported rather than retyped: two spellings of one sentence is exactly the drift §9 exists to
    prevent, and a user who is told their run stopped without being told the library is untouched
    has to go and check it themselves.
    """
    notice = notice_for(_unreadable(), _refused())

    assert notice is not None
    assert allowance.RUN_DID_NOT_START in notice.message
    assert allowance.RUN_DID_NOT_START in _refused().reason


def test_a_blocked_licence_notice_explains_why_the_allowance_applied() -> None:
    """The connection the user cannot see: the run was measured against the FREE allowance
    because the licence could not be read. Without it a paying customer reads a refusal they have
    no way to account for, and concludes they were charged twice."""
    notice = notice_for(_unreadable(), _refused())

    assert notice is not None
    assert "free allowance" in notice.message


# --- the states that are not problems ---------------------------------------------------------


@pytest.mark.parametrize(
    "state",
    [LicenceState.ABSENT, LicenceState.SIGNED_OUT, LicenceState.ACTIVE, LicenceState.LAPSED],
)
def test_no_state_but_unreadable_produces_a_licence_notice(state: LicenceState) -> None:
    """**Anti-vacuity for the precedence, and a real rule.**

    Only UNREADABLE is a *problem*. ABSENT is every new user, SIGNED_OUT is a choice, and ACTIVE
    and LAPSED are both entitlements. A function that treated any of them as a fault would nag
    three quarters of its users on every run, and would still pass the both-problems test above.
    """
    permitted = notice_for(Licence(state), _permitted())
    refused = notice_for(Licence(state), _refused())

    assert permitted is None
    assert refused is not None
    assert refused.kind is NoticeKind.CAP


def test_every_licence_state_is_covered_by_one_of_the_two_rules() -> None:
    """The census: no state falls through into an answer nobody chose.

    A state added later - a trial, a team seat, a revoked token - lands here as `None` by
    default, which is silence about a thing that may need saying. This is what makes that a
    decision rather than an oversight.
    """
    answered = {state: notice_for(Licence(state, reason="x"), _refused()) for state in LicenceState}

    assert all(notice is not None for notice in answered.values()), answered
    assert {n.kind for n in answered.values() if n} == {NoticeKind.LICENCE, NoticeKind.CAP}


def test_an_uncapped_permitted_run_is_silent_even_with_a_lapsed_licence() -> None:
    """D16 §2 reaching this module: a lapsed licence is an entitlement, not a condition to
    announce. Nagging someone about a renewal at the moment they press Apply is the countdown D6
    §3 forbids, arriving one layer down."""
    uncapped = allowance.may_start(50_000, None)

    assert notice_for(Licence(LicenceState.LAPSED), uncapped) is None
