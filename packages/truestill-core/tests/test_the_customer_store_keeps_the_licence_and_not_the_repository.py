"""The maintainer's customer store: what it must never do, and what re-issue must preserve.

**This tests a tool, not the product.** `scripts/licences.py` ships to nobody and nothing under
`packages/` imports it. It is here because it is the only place in this repository that handles
**other people's names and email addresses**, and two of its properties are the kind that are
discovered at the worst possible moment: customer data reaching git, and a re-issue silently
minting a second licence for one payment.

⚠ **The private key is never used here.** Every test generates a throwaway pair and injects the
public half through `monkeypatch.setitem`, exactly as the browser suite does - see
`tests/e2e/test_the_account_slot_draws_every_licence_state.py` for the reasoning. No key is
committed, and the shipped table is restored even on failure.
"""

from __future__ import annotations

import sqlite3
import sys
from argparse import Namespace
from collections.abc import Callable
from pathlib import Path

import nacl.signing
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))

import licences
import mint_licence
from truestill_core import licence as licence_module
from truestill_core.licence import LicenceState

KID = "store-throwaway"


@pytest.fixture
def key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A signing key for one test, trusted for one test."""
    signer = nacl.signing.SigningKey.generate()
    path = tmp_path / "k.key"
    path.write_text(licence_module.b64url_encode(bytes(signer)) + "\n")
    monkeypatch.setitem(
        licence_module.PUBLIC_KEYS, KID, licence_module.b64url_encode(bytes(signer.verify_key))
    )
    return path


@pytest.fixture
def db(tmp_path: Path) -> sqlite3.Connection:
    """A store in this test's own directory, never the maintainer's real one."""
    return licences.connect(tmp_path / "customers.db")


def _args(key: Path, **overrides: object) -> Namespace:
    fields: dict[str, object] = {
        "name": "Ada Lovelace",
        "email": "ada@example.com",
        "order_ref": "PAD-1",
        "edition": "pro",
        "covers_through": licence_module.BUILD_EPOCH,
        "updates_until": "2027-09-11",
        "consent_version": "test",
        "key": str(key),
        "kid": KID,
        "out": ".",
    }
    fields.update(overrides)
    return Namespace(**fields)


# --- the data must not reach the tree ------------------------------------------------------------


def test_the_store_refuses_to_live_inside_a_git_work_tree(monkeypatch: pytest.MonkeyPatch) -> None:
    """**The rule the whole tool rests on, and the only moment it can be enforced.**

    Tool in the tree, data outside it - one `git add -A` from being broken by accident, and
    unfixable afterwards because git keeps what it is given. Asking git rather than looking for a
    `.git` directory is `mint_licence.inside_a_repository`'s reasoning: a work tree can be
    configured elsewhere, and the question is "would this be committable".
    """
    monkeypatch.setenv(licences.STORE_ENV, str(Path(__file__).resolve().parent / "customers.db"))

    with pytest.raises(licences.StoreError) as refused:
        licences.store_path()

    assert "git work tree" in str(refused.value)
    assert "personal data" in str(refused.value)


def test_a_path_outside_every_checkout_is_accepted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """**The cry-wolf half.** A `store_path` that refused everything would satisfy the test above
    while making the tool unusable, and nothing else here calls it - both tests pass their own
    path to `connect`."""
    monkeypatch.setenv(licences.STORE_ENV, str(tmp_path / "customers.db"))

    assert licences.store_path() == tmp_path / "customers.db"


def test_no_tracked_file_holds_the_store(monkeypatch: pytest.MonkeyPatch) -> None:
    """The other half of the same rule: the default location is outside this repository.

    Asserted against the tree rather than trusted, because "beside the signing key" is a sentence
    in a docstring until something checks that the path it resolves to is not a path git would
    take.
    """
    monkeypatch.delenv(licences.STORE_ENV, raising=False)

    assert not licences.inside_a_repository(licences.DEFAULT_STORE)
    assert ".truestill-signing" in str(licences.DEFAULT_STORE)


# --- issue ---------------------------------------------------------------------------------------


def test_issuing_records_the_purchase_and_mints_a_token_that_verifies(
    db: sqlite3.Connection, key: Path
) -> None:
    """The whole of a first sale: one account, one licence, one issue, one readable token."""
    token, row = licences.issue(db, _args(key))

    assert licence_module.verify_token(token).state is LicenceState.ACTIVE
    assert row["order_ref"] == "PAD-1"
    assert len(licences.issues_for(db, row["licence_id"])) == 1
    assert licences.issues_for(db, row["licence_id"])[0]["reason"] == "purchase"


def test_a_second_purchase_by_one_person_is_a_second_licence_on_one_account(
    db: sqlite3.Connection, key: Path
) -> None:
    """**Identity is the licence, not the person** - Q1742 put both `sub` and `lic` in the token
    and the store is shaped to match.

    An account that bought twice must own two licences, not have its first overwritten and not
    become two people. Matched on lowercased email, because that is the only handle a buyer gives
    you twice and two mail servers will never disagree about the case.
    """
    _, first = licences.issue(db, _args(key, order_ref="PAD-1"))
    _, second = licences.issue(db, _args(key, order_ref="PAD-2", email="ADA@example.com"))

    assert first["account_id"] == second["account_id"], "one buyer became two accounts"
    assert first["licence_id"] != second["licence_id"], "a second purchase overwrote the first"


def test_issuing_twice_against_one_order_reference_is_refused(
    db: sqlite3.Connection, key: Path
) -> None:
    """⚠ **REFUSED, NOT SILENTLY TREATED AS A RE-ISSUE, and the failure mode decides it.**

    The realistic mistake is pasting the *previous* order reference while issuing for a new
    buyer. Converting that into a re-issue would mint a token carrying **the previous customer's
    name and email**, print it as a success, and the operator would send someone else's identity
    to a stranger - signed, and unrevokable, because nothing in this design ever revokes.

    So the refusal names the licence that already holds the reference and offers the command that
    is actually wanted. The test asserts the *other* customer's details are absent from the
    message too: a refusal that leaked them would be a smaller version of the same defect.
    """
    licences.issue(db, _args(key, order_ref="PAD-1"))

    with pytest.raises(licences.StoreError) as refused:
        licences.issue(db, _args(key, order_ref="PAD-1", name="Someone Else", email="e@x.com"))

    assert "already belongs to licence" in str(refused.value)
    assert "reissue --order-ref PAD-1" in str(refused.value)
    assert db.execute("SELECT count(*) FROM licences").fetchone()[0] == 1


# --- re-issue ------------------------------------------------------------------------------------


def test_reissue_preserves_the_licence_rather_than_minting_a_new_one(
    db: sqlite3.Connection, key: Path
) -> None:
    """**The ruling, asserted on the identifiers rather than on the outcome looking right.**

    A customer loses their file and writes to you. If re-issue quietly minted a new licence: the
    issue counts D5 monitors become noise, the customer's history splits in two, and one payment
    owns two licences. So `sub`, `lic` and the entitlement are all read from the stored row -
    asserted here **out of the token**, because that is what the customer's machine will read.
    """
    first, row = licences.issue(db, _args(key))
    second, again = licences.mint_for(db, row["licence_id"], _args(key), reason="reissue")

    one = licence_module.verify_token(first).payload
    two = licence_module.verify_token(second).payload
    assert one is not None
    assert two is not None

    assert two.licence == one.licence, "a re-issue minted a NEW licence"
    assert two.account == one.account, "a re-issue moved the licence to a new account"
    # ⚠ AGAINST THE STORED ROW, NOT AGAINST EACH OTHER. This read
    # `two.covers_through == one.covers_through` and a mutation SURVIVED it: forcing the
    # entitlement to `BUILD_EPOCH + 1` corrupts BOTH tokens, so they still agreed with each other
    # while both disagreed with the purchase. Two wrong answers that match are the shape a
    # self-comparison cannot see, and the store is the only thing entitled to say what was sold.
    assert one.covers_through == row["covers_through"], "the first token left the entitlement"
    assert two.covers_through == row["covers_through"], "a re-issue changed the entitlement"
    assert one.licence == row["licence_id"]
    assert one.account == row["account_id"]
    assert db.execute("SELECT count(*) FROM licences").fetchone()[0] == 1
    assert [i["reason"] for i in licences.issues_for(db, row["licence_id"])] == [
        "purchase",
        "reissue",
    ]
    assert again["licence_id"] == row["licence_id"]


def test_an_unchanged_reissue_is_byte_identical_and_that_is_correct(
    db: sqlite3.Connection, key: Path
) -> None:
    """⚠ **MEASURED, AND IT REFUTED THE ASSERTION THIS TEST WAS FIRST WRITTEN TO MAKE.**

    It began as `assert first != second` - an anti-vacuity check that a re-issue is not just the
    stored token handed back. It failed, and the reason is a property of the signature scheme
    rather than a defect: **Ed25519 is deterministic** (RFC 8032 derives the nonce from the key
    and the message, with no randomness), and a same-day re-issue of an unchanged licence signs
    an identical payload. Identical input, identical signature, identical bytes.

    That is the behaviour you want: a customer who lost their file gets back **exactly** the file
    they lost, and an operator comparing two copies sees they are the same rather than wondering
    which is current. It is recorded here because "the bytes differ" is the natural thing to
    assume about re-issuing, and assuming it is how somebody later writes a test that fails for a
    correct reason - as this one did.

    The real anti-vacuity is below: something the payload depends on must change the bytes.
    """
    first, row = licences.issue(db, _args(key))
    second, _ = licences.mint_for(db, row["licence_id"], _args(key), reason="reissue")

    assert first == second


def test_a_reissue_under_a_different_key_id_really_re_signs(
    db: sqlite3.Connection, key: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """**The anti-vacuity the byte comparison could not provide.**

    A `mint_for` that ignored its arguments and returned the stored token would satisfy every
    identifier assertion above *and* the determinism test. Changing the `kid` changes the payload,
    so the bytes must change - and the new token must still verify, which is what distinguishes
    "re-signed correctly" from "corrupted".
    """
    rotated = "store-throwaway-2"
    monkeypatch.setitem(licence_module.PUBLIC_KEYS, rotated, licence_module.PUBLIC_KEYS[KID])
    first, row = licences.issue(db, _args(key))
    second, _ = licences.mint_for(db, row["licence_id"], _args(key, kid=rotated), reason="reissue")

    assert first != second
    verified = licence_module.verify_token(second)
    assert verified.state is LicenceState.ACTIVE
    assert verified.payload is not None
    assert verified.payload.kid == rotated
    assert verified.payload.licence == row["licence_id"], "rotating a key moved the licence"


# --- the email typo --------------------------------------------------------------------------


def test_correcting_an_email_re_signs_the_same_licence_and_the_old_token_still_lies(
    db: sqlite3.Connection, key: Path
) -> None:
    """⚠ **THE OLD TOKEN CANNOT BE CORRECTED, AND THIS TEST EXISTS TO STOP ANYONE ASSUMING IT
    CAN.**

    The buyer's email is inside the signed payload (D6 §2), so a typo cannot be edited out - the
    signature covers it. The only repair is a new signature over corrected fields, and the file
    the customer already holds **keeps verifying for ever, saying the wrong address**. Nothing
    revokes it; that is D5's no-phone-home guarantee working as designed and costing exactly
    this.

    Both halves are asserted because only asserting the new token would leave the expensive half
    undocumented and un-noticed.
    """
    typo, row = licences.issue(db, _args(key, email="ada@exmaple.com"))
    db.execute(
        "UPDATE accounts SET email = ? WHERE account_id = ?",
        ("ada@example.com", row["account_id"]),
    )
    fixed, _ = licences.mint_for(db, row["licence_id"], _args(key), reason="email-correction")

    old = licence_module.verify_token(typo)
    new = licence_module.verify_token(fixed)
    assert old.payload is not None
    assert new.payload is not None

    assert new.payload.email == "ada@example.com"
    assert new.payload.licence == old.payload.licence, "correcting an email changed the licence"
    # The expensive half: the file already sent still verifies and still says the typo.
    assert old.state is LicenceState.ACTIVE
    assert old.payload.email == "ada@exmaple.com"


# --- a deletion request ----------------------------------------------------------------------


def test_forgetting_erases_the_person_and_keeps_the_tax_record(
    db: sqlite3.Connection, key: Path
) -> None:
    """Q1743's shape, implemented. Erase name and email everywhere they were recorded; keep the
    licence id, the order reference and the dates, which are kept on legal obligation rather than
    on consent and so are not reached by a deletion request.

    The issue history's own copies are erased too - they are the same personal data, recorded a
    second time so that `whois` can explain a token that disagrees with the account.
    """
    _, row = licences.issue(db, _args(key))
    licences.mint_for(db, row["licence_id"], _args(key), reason="reissue")

    touched = licences.forget(db, row["account_id"])

    assert touched == 2
    account = db.execute(
        "SELECT * FROM accounts WHERE account_id = ?", (row["account_id"],)
    ).fetchone()
    assert account["email"] is None
    assert account["name"] is None
    assert account["forgotten_at"]
    kept = licences.licence_row(db, licence_id=row["licence_id"])
    assert kept["order_ref"] == "PAD-1"
    assert kept["purchased_at"]
    assert kept["updates_until"] == "2027-09-11"
    assert all(i["email_at_issue"] is None for i in licences.issues_for(db, row["licence_id"]))


def test_a_forgotten_buyer_who_buys_again_gets_a_new_account(
    db: sqlite3.Connection, key: Path
) -> None:
    """Erasure must not be undone by the next purchase.

    The account lookup skips forgotten rows, so buying again creates a fresh account rather than
    re-attaching a name to the row that was erased - which would quietly restore the data a
    person asked to have removed.
    """
    _, row = licences.issue(db, _args(key, order_ref="PAD-1"))
    licences.forget(db, row["account_id"])

    _, later = licences.issue(db, _args(key, order_ref="PAD-2"))

    assert later["account_id"] != row["account_id"]
    erased = db.execute(
        "SELECT email FROM accounts WHERE account_id = ?", (row["account_id"],)
    ).fetchone()
    assert erased["email"] is None, "a later purchase undid a deletion request"


# --- whois ---------------------------------------------------------------------------------------


def test_whois_answers_the_first_question_a_support_conversation_asks(
    db: sqlite3.Connection, key: Path
) -> None:
    """Given a file, who is it and what did they buy."""
    token, row = licences.issue(db, _args(key))

    state, found, claimed = licences.whois(db, token)

    assert state is LicenceState.ACTIVE
    assert found is not None
    assert found["order_ref"] == "PAD-1"
    assert found["licence_id"] == row["licence_id"]
    assert claimed["email"] == "ada@example.com"


def test_whois_reports_a_token_it_cannot_read_rather_than_decoding_it_anyway(
    db: sqlite3.Connection,
) -> None:
    """A token that does not verify is the customer's actual problem.

    Reading its payload regardless would answer a question about a file the product itself would
    refuse, and would let an operator reassure somebody about a licence that will not work.
    """
    state, found, claimed = licences.whois(db, "not a token at all")

    assert state is LicenceState.UNREADABLE
    assert found is None
    assert claimed == {}


def test_whois_on_a_token_this_store_never_issued_says_so(
    db: sqlite3.Connection, key: Path, tmp_path: Path
) -> None:
    """It verifies, and the store has never heard of it.

    That is a real situation with two real causes - issued from a different store, or this store
    restored from a backup older than the issue - and both are things the operator must be told
    rather than left to infer from an empty result.
    """
    token, _issued = licences.issue(db, _args(key))
    elsewhere = licences.connect(tmp_path / "other.db")

    state, found, claimed = licences.whois(elsewhere, token)

    assert state is LicenceState.ACTIVE
    assert found is None
    assert claimed["email"] == "ada@example.com"


# --- the signer has one home ---------------------------------------------------------------------


def test_both_tools_sign_through_the_same_function(key: Path) -> None:
    """`mint_licence` and `licences` must not grow two ways to sign a token.

    Two callers building the same two lines is how one of them ends up signing something subtly
    different - a different canonicalisation, a different thing signed - producing a token that
    verifies nowhere with no obvious reason why. Asserted by identity rather than by reading the
    source, so moving the function does not silently pass.
    """
    assert licences.sign_payload is mint_licence.sign_payload

    signer = nacl.signing.SigningKey(licence_module.b64url_decode(key.read_text().strip()))
    fields: dict[str, object] = {
        "v": licence_module.PAYLOAD_VERSION,
        "kid": KID,
        "sub": "a",
        "lic": "l",
        "name": "N",
        "email": "e@x.com",
        "edition": "pro",
        "covers_through": licence_module.BUILD_EPOCH,
        "issued_at": "2026-09-11",
        "updates_until": "2027-09-11",
    }

    assert (
        licence_module.verify_token(mint_licence.sign_payload(signer, fields)).state
        is LicenceState.ACTIVE
    )


def test_the_store_is_created_private(tmp_path: Path) -> None:
    """0600 at creation. Same rule and the same Windows caveat as the licence token: CPython
    synthesizes `st_mode` there, so the number means nothing and the protection is the user's own
    profile."""
    target = tmp_path / "customers.db"
    licences.connect(target)

    if sys.platform != "win32":
        assert target.stat().st_mode & 0o777 == 0o600
    assert target.is_file()


def test_nothing_the_product_ships_imports_this_tool() -> None:
    """**The boundary, asserted rather than described.**

    This tool handles other people's personal data and has no business inside anything a user
    installs. A stray import would put `sqlite3` handling of customer records into the shipped
    graph, and `(ahn)`'s route census would never see it because it is not a route.
    """
    root = Path(__file__).resolve().parents[3] / "packages"
    offenders = [
        path.relative_to(root)
        for path in root.rglob("src/**/*.py")
        if "licences" in path.read_text(encoding="utf-8").replace("licences_", "")
        and "import licences" in path.read_text(encoding="utf-8")
    ]

    assert not offenders, offenders


def _callables() -> list[Callable[..., object]]:
    return [licences.issue, licences.mint_for, licences.forget, licences.whois]


def test_every_store_operation_is_reachable_by_name() -> None:
    """Anti-vacuity for the module: a rename that broke the CLI would leave every test above
    green, because they call the functions directly rather than through `main`."""
    for name in (
        "cmd_issue",
        "cmd_reissue",
        "cmd_find",
        "cmd_whois",
        "cmd_forget",
        "cmd_correct_email",
    ):
        assert callable(getattr(licences, name)), name
    assert all(callable(one) for one in _callables())
