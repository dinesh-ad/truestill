"""`self-check` says which entitlement this installation holds. `(akq)`

⚠ **ITS OUTPUT WAS BYTE-IDENTICAL LICENSED AND UNLICENSED**, while printing *"entitlement epoch
1"* - a property of the **build**, not of the install. Support's first question is *"what does
self-check say"*, and the answer said install path, versions, exiftool, trash, catalog, cache and
session url, and nothing whatever about the licence being asked about.

**The module's founding rule is unchanged: a finding reports what it HOLDS, and the comparison
against the source of truth belongs to the caller.** It says which file is there, which key signed
it, what it claims, and what that verifies as **on this build**. Whether that is the licence the
customer paid for is the maintainer's store's answer, from the id this prints.

⚠ **NOTHING PERSONAL, BECAUSE THIS REPORT EXISTS TO BE PASTED.** That is the assertion with teeth
below - the payload carries a name, an email and an account id, and a diagnostic a person is
invited to paste into a public issue must carry none of them.
"""

from __future__ import annotations

from pathlib import Path

import nacl.signing
import pytest
from truestill_core import licence, selfcheck
from truestill_core.licence import LicenceState
from truestill_core.selfcheck import Status, licence_finding

#: A real token, minted in `conftest`-free isolation by the app's own e2e helper shape would be
#: heavier than this needs: the finding reads `read_licence`, so an unverifiable token exercises
#: UNREADABLE and an absent one exercises ABSENT, which is every branch that does not need a key.
_NOT_A_TOKEN = "this is not a licence token"

#: Deliberately not "k1": a fixture reusing the shipped key id would pass even if the injection
#: silently did nothing, because the real key is in the table already.
_KID = "selfcheck-throwaway"


@pytest.fixture(autouse=True)
def _own_data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TRUESTILL_DATA_DIR", str(tmp_path))


def _mint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, covers_through: int = licence.BUILD_EPOCH
) -> None:
    """Write a token this build verifies, against a key injected for the length of one test.

    The identity fields are deliberately distinctive strings rather than plausible ones: the
    privacy assertion searches the rendered finding for them, and a realistic name would be
    indistinguishable from an ordinary word if it ever did leak.
    """
    signer = nacl.signing.SigningKey.generate()
    monkeypatch.setitem(licence.PUBLIC_KEYS, _KID, licence.b64url_encode(bytes(signer.verify_key)))
    fields = {
        "v": licence.PAYLOAD_VERSION,
        "kid": _KID,
        "sub": "account-id-must-not-appear",
        "lic": "licence-id-may-appear",
        "name": "Buyer Nameshouldnotappear",
        "email": "buyer@nowhere.invalid",
        "edition": "pro",
        "covers_through": covers_through,
        "issued_at": "2026-09-15",
        "updates_until": "2027-09-15",
    }
    encoded = licence.encode_payload(fields)
    signature = signer.sign(licence.signing_input(encoded)).signature
    (tmp_path / "licence.token").write_text(
        f"{encoded}.{licence.b64url_encode(signature)}", encoding="utf-8"
    )


def test_self_check_is_no_longer_silent_about_the_licence() -> None:
    """**The headline: the finding exists at all, and core's own list carries it.**

    A finding nobody assembles is a finding nobody reads, so this asserts the list rather than the
    function - which is the difference between the defect being fixed and merely being fixable.
    """
    names = [f.name for f in selfcheck.core_findings()]
    assert "licence" in names, f"self-check still says nothing about the licence: {names}"


def test_an_install_with_no_licence_says_so_and_is_not_a_fault(tmp_path: Path) -> None:
    """ABSENT is what every new user is. `entitlement_epoch_finding`'s rule: a fact, not a fault."""
    finding = licence_finding()

    assert finding.status is Status.INFO, "a free installation was reported as degraded"
    assert str(LicenceState.ABSENT) in finding.detail
    # The path is in every state: it is where to put a licence, and where the one in use lives.
    assert str(tmp_path / "licence.token") in finding.detail


def test_a_token_that_will_not_verify_is_degraded_and_says_why(tmp_path: Path) -> None:
    """⚠ **THE ONLY DEGRADED STATE HERE**, and it must be: a file is present and this build cannot
    read it, which is a real fault with a real remedy. The reason travels so the user knows what
    to replace rather than only that something is wrong."""
    (tmp_path / "licence.token").write_text(_NOT_A_TOKEN, encoding="utf-8")

    finding = licence_finding()

    assert finding.status is Status.DEGRADED
    assert "cannot read it" in finding.detail
    assert finding.evidence["reason"], "the finding says it is unreadable and not why"


def test_the_finding_never_carries_the_buyers_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """⚠ **THE ASSERTION WITH TEETH, AND IT NEEDS A REAL TOKEN TO HAVE ANY.**

    This report is designed to be pasted, so the buyer's name, their email and the account id must
    never reach it. The licence id may, and does: it is opaque on its own and is the exact key
    `scripts/licences.py find` resolves, so support needs no second round trip.

    ⚠ **A first version of this test asserted the substring `"name"` was absent and failed against
    correct code** - `Finding.as_json()` always carries a `name` KEY, which is the finding's own
    name. Searching for a field name proves nothing; the VALUES are what leak, so they are minted
    into a real payload and searched for by content.
    """
    _mint(tmp_path, monkeypatch)

    finding = licence_finding()
    assert finding.status is Status.OK, f"the minted token did not verify: {finding.detail}"
    rendered = str(finding.as_json())

    for leaked in (
        "Buyer Nameshouldnotappear",
        "buyer@nowhere.invalid",
        "account-id-must-not-appear",
    ):
        assert leaked not in rendered, (
            f"the licence finding carries {leaked!r}, which a person would paste into an issue"
        )
    # And the one identifier that earns its place is present, or support has nothing to look up.
    assert "licence-id-may-appear" in rendered


def test_the_evidence_is_machine_readable_and_the_detail_is_a_sentence(tmp_path: Path) -> None:
    """`Finding`'s own contract: *"``detail`` is the sentence a person reads; ``evidence`` is what
    a job parses"*. A state present in one and absent from the other breaks whichever reader
    trusted it."""
    finding = licence_finding()

    assert finding.evidence["state"] == str(LicenceState.ABSENT)
    assert finding.evidence["path"] == str(tmp_path / "licence.token")
    assert finding.detail.startswith(str(LicenceState.ABSENT))


def test_a_lapsed_licence_still_reports_what_it_bought_and_is_not_a_fault(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """⚠ **INFO, NOT DEGRADED**, and D16 §2 is the reason: *"a lapsed licence loses nothing it
    bought."* Reporting it as a fault would be this module telling a paying customer their install
    is broken because a ceiling was passed.

    ⚠ **THE ENTITLEMENT IS A VERSION CEILING, NOT A DATE** (`licence.py`'s own opening), which is
    why the fixture lowers `covers_through` rather than backdating `updates_until` - a first
    version of this test moved the date, got `ACTIVE`, and would have asserted nothing. The
    comparison the finding prints - `covers_through` against this build's epoch - is exactly the
    pair support needs, so both survive into the evidence.
    """
    _mint(tmp_path, monkeypatch, covers_through=licence.BUILD_EPOCH - 1)

    finding = licence_finding()

    assert finding.evidence["state"] == str(LicenceState.LAPSED), (
        "the fixture did not produce a lapsed licence, so this test proves nothing"
    )
    assert finding.status is Status.INFO
    assert finding.evidence["covers_through"] == licence.BUILD_EPOCH - 1


def test_a_signed_out_install_says_so_rather_than_reading_as_a_fresh_one(tmp_path: Path) -> None:
    """Signed out and never licensed are different facts about an install and print differently,
    which is the whole point of putting `state` in the evidence rather than a boolean."""
    (tmp_path / "licence.signed-out").write_text("1", encoding="utf-8")

    finding = licence_finding()

    assert finding.evidence["state"] == str(LicenceState.SIGNED_OUT), (
        "the sign-out marker is not at the name this test writes"
    )
    assert finding.status is Status.INFO
    assert finding.detail.startswith(str(LicenceState.SIGNED_OUT))
