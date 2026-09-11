"""The account's five sentences, and the file a user points at to activate.

**Every string the rail shows is asserted here rather than in the browser**, because the seam
this product keeps getting wrong is a second copy of a sentence. `IMPLEMENTATION_STANDARDS.md` §9
puts one home under each outcome; this is that home's test, and the e2e suite asserts only that
the rail renders what this file pins.

⚠ **D16 §1 binds every branch below: none of these states is a gate.** The app always opens and
every feature works, so no sentence here may read as a refusal, a prompt or a countdown - and the
tests check that as a property rather than trusting the prose.
"""

from __future__ import annotations

from pathlib import Path

import nacl.signing
import pytest
from truestill_core import allowance, app_paths, licence
from truestill_core.licence import Licence, LicenceState
from truestill_core.licence_notice import account_summary, standing_notice

KID = "test-k1"
CAP = allowance.FREE_FILE_ALLOWANCE


@pytest.fixture
def signer() -> nacl.signing.SigningKey:
    return nacl.signing.SigningKey.generate()


@pytest.fixture
def keys(signer: nacl.signing.SigningKey) -> dict[str, str]:
    return {KID: licence.b64url_encode(bytes(signer.verify_key))}


def make_token(signer: nacl.signing.SigningKey, **overrides: object) -> str:
    fields: dict[str, object] = {
        "v": licence.PAYLOAD_VERSION,
        "kid": KID,
        "sub": "acc-1",
        "lic": "lic-1",
        "name": "A Buyer",
        "email": "buyer@example.com",
        "edition": "pro",
        "covers_through": licence.BUILD_EPOCH,
        "issued_at": "2026-09-11",
        "updates_until": "2027-09-11",
    }
    fields.update(overrides)
    encoded = licence.encode_payload(fields)
    return (
        f"{encoded}.{licence.b64url_encode(signer.sign(licence.signing_input(encoded)).signature)}"
    )


def _entitled(signer: nacl.signing.SigningKey, keys: dict[str, str], **over: object) -> Licence:
    return licence.verify_token(make_token(signer, **over), keys=keys)


# --- the five states --------------------------------------------------------------------------


def test_a_fresh_install_is_told_what_the_product_is_not_what_it_lacks() -> None:
    """ABSENT is **every new user**, so it must not read as an error or a prompt.

    The assertion is the positive claim - that every feature works - because that is the sentence
    D16 §1 makes true and the one a first-run rail has to carry. A state that only said what was
    missing would be the degraded free experience D6 §3 forbids, written in words instead of code.
    """
    summary = account_summary(Licence(LicenceState.ABSENT), CAP, CAP)

    assert summary.state is LicenceState.ABSENT
    assert "every feature works" in summary.detail
    assert summary.allowance == f"{CAP:,} of {CAP:,} left"
    assert summary.notice is None


def test_an_active_licence_says_who_is_signed_in_and_shows_no_allowance(
    signer: nacl.signing.SigningKey, keys: dict[str, str]
) -> None:
    """ACTIVE. The headline is the buyer's own name - `(aam)`'s *"identity visible in the
    interface"* - and the allowance is **empty** rather than "unlimited", because a number that
    is absent because it does not apply must not be dressed up as a very large one."""
    summary = account_summary(_entitled(signer, keys), None, CAP)

    assert summary.headline == "A Buyer"
    assert "Pro" in summary.detail
    assert "2027-09-11" in summary.detail
    assert summary.allowance == ""


def test_a_lapsed_licence_says_nothing_was_taken_away(
    signer: nacl.signing.SigningKey, keys: dict[str, str]
) -> None:
    """**LAPSED is where a wrong word does real damage**, so the sentence is asserted directly.

    D16 §2: *"a lapsed licence loses nothing it bought."* A rail that said "expired" would be
    telling a paying customer something false about software they own outright, at the exact
    moment they are most likely to believe it.
    """
    lapsed = _entitled(signer, keys, covers_through=licence.BUILD_EPOCH - 1)
    summary = account_summary(lapsed, None, CAP)

    assert lapsed.state is LicenceState.LAPSED
    assert summary.headline == "A Buyer"
    assert "yours for ever" in summary.detail
    assert "nothing has been taken away" in summary.detail
    # Uncapped, which is the same ruling reaching the arithmetic rather than the prose.
    assert summary.allowance == ""


def test_signing_out_says_the_licence_was_not_cancelled() -> None:
    """SIGNED_OUT is the same as never activated **plus** that a licence still exists.

    `(aam)`'s whole worry is a casual logout stranding someone, so the one thing this state must
    not do is read as though the purchase went with it.
    """
    summary = account_summary(Licence(LicenceState.SIGNED_OUT), CAP, CAP)

    assert summary.headline == "Signed out"
    assert "has not been cancelled" in summary.detail
    assert "sign back in" in summary.detail


def test_an_unreadable_licence_is_never_an_accusation() -> None:
    """UNREADABLE. The notice says what to do; the detail says what did **not** happen.

    The overwhelmingly likely cause is a damaged file, so the wording must not imply the user did
    anything - and it must say the library is untouched, because that is the fear a message about
    a licence actually provokes in a tool that holds someone's photographs.
    """
    damaged = Licence(LicenceState.UNREADABLE, reason="This licence file is damaged.")
    summary = account_summary(damaged, CAP, CAP)

    assert summary.headline == "Licence not readable"
    assert "nothing about your library has changed" in summary.detail
    assert summary.notice is not None
    assert summary.notice.message == "This licence file is damaged."


@pytest.mark.parametrize("state", list(LicenceState))
def test_no_state_is_left_without_a_sentence(state: LicenceState) -> None:
    """**The census, and the cry-wolf half of every test above.**

    A state that fell off the end would render an empty rail - the one outcome nobody would
    notice, because an empty slot looks exactly like a slot that is doing its job. A state added
    later lands in the ABSENT arm and still says something true rather than nothing.
    """
    summary = account_summary(Licence(state, reason="x"), CAP, CAP)

    assert summary.headline.strip()
    assert summary.detail.strip()
    assert summary.sign_out_warning.strip()


@pytest.mark.parametrize("state", list(LicenceState))
def test_no_sentence_anywhere_reads_as_a_countdown_or_a_gate(state: LicenceState) -> None:
    """**D16 §1 and D6 §3 as a property, not as a promise in a docstring.**

    D6 §3 names what is never done: a nag, a countdown, a modal, a degraded experience, a feature
    that stops working to make a point. This checks the vocabulary that would carry any of them
    into the rail - the words a well-meaning rewrite reaches for first.
    """
    summary = account_summary(Licence(state, reason="x"), CAP, CAP)
    prose = f"{summary.headline} {summary.detail} {summary.allowance}".lower()

    for banned in ("expired", "days left", "upgrade now", "unlock", "trial", "locked"):
        assert banned not in prose, f"{state}: {banned!r} in {prose!r}"


@pytest.mark.parametrize("state", list(LicenceState))
def test_the_summary_row_strings_fit_the_rail_they_are_rendered_in(state: LicenceState) -> None:
    """**The defect a screenshot found and no assertion would have.**

    The headline and the allowance render on one row of a 232px rail, beside an 8px dot and a
    14px chevron - about 154px, or roughly 20 characters at `--type-sm`. The first wording
    ("No licence on this computer", "1,000 of 1,000 free files left to organize") was 27 and 42,
    so both truncated and the name ran under the chevron. The second attempt fitted by dropping
    the cap, which left a user who had spent 300 files unable to learn the allowance anywhere;
    both numbers fit once the WORDS went instead. The long forms live in `detail`, inside
    the fold, where they wrap.

    ⚠ **A character budget is coarse, and it is the honest instrument available here.** The
    rail's sans is not pinned, which is exactly what made the prose-measure lane fail on `ch`
    units earlier in this project: a pixel figure would be one number locally and another on CI.
    So this is a cheap guard against the wording growing back, and **the screenshot is what
    actually proves it fits** - 22 is a rounded estimate, not a measurement.
    """
    summary = account_summary(Licence(state, reason="x"), CAP, CAP)

    assert len(summary.headline) <= 22, summary.headline
    assert len(summary.allowance) <= 22, summary.allowance


def test_the_standing_notice_never_blocks_anything() -> None:
    """`standing_notice` is `notice_for` asked with a run of zero files, so by construction the
    answer can only be the non-blocking licence notice or silence. Asserted because the account
    surface renders it and D16 §1 means nothing there may refuse."""
    for state in LicenceState:
        notice = standing_notice(Licence(state, reason="x"))
        assert notice is None or notice.blocks_run is False, state


# --- activation from a file --------------------------------------------------------------------


def test_pointing_at_a_good_file_activates(
    tmp_path: Path, signer: nacl.signing.SigningKey, keys: dict[str, str]
) -> None:
    """D5's offline path, and the whole of activation until a server exists."""
    source = tmp_path / "truestill-licence.token"
    source.write_text(make_token(signer))

    result = licence.install_token_from(source, keys=keys)

    assert result.state is LicenceState.ACTIVE
    assert licence.read_licence(keys=keys).state is LicenceState.ACTIVE


def test_a_lapsed_file_is_still_installed(
    tmp_path: Path, signer: nacl.signing.SigningKey, keys: dict[str, str]
) -> None:
    """A licence that does not cover this build is a real entitlement, not a failed activation.

    D16 §2 again: refusing to install it would be the product deciding a paying customer has no
    licence because they are on a build they did not buy - which D16 §4 already rules they should
    never have been given.
    """
    source = tmp_path / "old.token"
    source.write_text(make_token(signer, covers_through=licence.BUILD_EPOCH - 1))

    assert licence.install_token_from(source, keys=keys).state is LicenceState.LAPSED
    assert licence.read_licence(keys=keys).state is LicenceState.LAPSED


@pytest.mark.parametrize(
    ("case", "written"),
    [
        ("a photograph", b"\xff\xd8\xff\xe0\x00\x10JFIF"),
        ("empty", b""),
        ("half a token", b"eyJhIjoxfQ.AAAA"),
        ("invalid utf-8", b"\x80\x81\x82"),
    ],
)
def test_a_bad_file_installs_nothing_and_leaves_a_good_licence_alone(
    case: str,
    written: bytes,
    tmp_path: Path,
    signer: nacl.signing.SigningKey,
    keys: dict[str, str],
) -> None:
    """**Verify BEFORE installing, and this is the case that decides it.**

    A user with a working licence points at the wrong file out of their downloads folder. Writing
    first and reporting afterwards would replace a good token with a broken one over a misclick -
    turning an ordinary mistake into the strand `(aam)` is written about. So the installed token
    is asserted **unchanged**, not merely the return value.
    """
    licence.write_licence(make_token(signer))
    source = tmp_path / "wrong"
    source.write_bytes(written)

    result = licence.install_token_from(source, keys=keys)

    assert result.state is LicenceState.UNREADABLE, case
    assert result.reason, case
    assert licence.read_licence(keys=keys).state is LicenceState.ACTIVE, case


def test_a_missing_file_and_a_directory_are_both_states_not_crashes(
    tmp_path: Path, keys: dict[str, str]
) -> None:
    """Both are what a user produces by typing a path, and neither may raise."""
    assert licence.install_token_from(tmp_path / "nope", keys=keys).state is LicenceState.UNREADABLE
    assert licence.install_token_from(tmp_path, keys=keys).state is LicenceState.UNREADABLE
    assert not app_paths.licence_path().exists()
