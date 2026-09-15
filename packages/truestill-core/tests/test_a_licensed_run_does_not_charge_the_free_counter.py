"""An entitlement's run does not draw down the free allowance. `(akq)`, `DECISIONS.md` D16 §8.

⚠ **FOUND BY BUYING A LICENCE AND WATCHING THE NUMBER MOVE.** `record_files_written` was
unconditional, so one licensed run over a 2,574-file library took the counter from **844 to
3,418**. Nothing looked wrong at the time - an entitled install never reads the counter - but the
moment that token file is lost or signed out, the fallback is *"0 of 1,000 left"*: **worse off
than someone who had just downloaded truestill**, at exactly the moment they are already in
trouble.

D16 §1's *"cumulative across every run"* is about the **free tier's** arithmetic, and says so in
its own words - *"A per-run cap is not a cap: a user runs it n times and the free tier is the
entire product."* It was never an argument for billing a licence holder against a limit that does
not apply to them.

**The counter records what this install wrote WHILE ON THE FREE TIER**, and that fact survives a
purchase - which is why installing a licence does not reset it, only stops adding to it.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from truestill_core import allowance
from truestill_core.allowance import FREE_FILE_ALLOWANCE, files_written, record_files_written
from truestill_core.licence import Licence, LicenceState


@pytest.fixture(autouse=True)
def _own_data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The counter is per-installation, so every test needs its own or they share one file."""
    monkeypatch.setenv("TRUESTILL_DATA_DIR", str(tmp_path))


def _lic(state: LicenceState) -> Licence:
    return Licence(state=state)


def test_an_unlicensed_run_still_charges() -> None:
    """**The half that must not change.** The cap only works if the free tier is counted."""
    assert files_written() == 0
    assert record_files_written(300, licence=_lic(LicenceState.ABSENT)) == 300
    assert files_written() == 300


@pytest.mark.parametrize("state", [LicenceState.ACTIVE, LicenceState.LAPSED])
def test_an_entitled_run_does_not_charge(state: LicenceState) -> None:
    """**The headline.** ACTIVE and LAPSED are both entitlements, and D16 §2 is why LAPSED is:
    *"a lapsed licence loses nothing it bought"* - charging it would hand someone who paid a
    smaller free tier than someone who never did."""
    record_files_written(300, licence=_lic(LicenceState.ABSENT))

    assert record_files_written(2574, licence=_lic(state)) == 300
    assert files_written() == 300, f"a {state} run drew down the free allowance"


def test_an_unreadable_token_still_charges() -> None:
    """⚠ **The asymmetry `remaining_for` already rules, applied here rather than re-decided.**

    A token that will not verify cannot be told from no token at all, so it cannot be the basis of
    an entitlement - otherwise the cap would be bypassable by writing garbage into the file.
    """
    assert record_files_written(40, licence=_lic(LicenceState.UNREADABLE)) == 40
    assert files_written() == 40


def test_installing_a_licence_does_not_reset_what_the_free_tier_wrote() -> None:
    """⚠ **NOT A RESET, AND THAT IS DELIBERATE** (D16 §8). What a user wrote before they paid is a
    fact about this install and survives the purchase; what changes is that nothing is added."""
    record_files_written(161, licence=_lic(LicenceState.ABSENT))
    record_files_written(2574, licence=_lic(LicenceState.ACTIVE))

    assert files_written() == 161, "buying a licence rewrote the free tier's own history"


def test_a_lost_token_leaves_the_free_tier_where_the_user_left_it() -> None:
    """**The defect, stated as the outcome a customer would meet.**

    Write 161 files free, buy a licence, organize 2,574 more, then lose the token. Before `(akq)`
    that user had **0** of 1,000 left. They should have exactly what they had not spent.
    """
    record_files_written(161, licence=_lic(LicenceState.ABSENT))
    record_files_written(2574, licence=_lic(LicenceState.ACTIVE))

    remaining = allowance.remaining_for(LicenceState.ABSENT, files_written())

    assert remaining == FREE_FILE_ALLOWANCE - 161 == 839, (
        f"a customer who lost their token was left with {remaining} of {FREE_FILE_ALLOWANCE}"
    )


def test_the_default_reads_the_installed_licence(tmp_path: Path) -> None:
    """The guard must hold for a caller that passes nothing, because two of the three call sites
    do exactly that. With no token on disk the state is ABSENT, so the run charges."""
    assert record_files_written(12) == 12
    assert json.loads((tmp_path / "licence.usage.json").read_text())["files_written"] == 12
