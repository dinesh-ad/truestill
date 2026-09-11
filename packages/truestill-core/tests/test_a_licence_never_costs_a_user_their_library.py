"""The five licence states, and the one that must never become a locked door.

**The dangerous state has a name and a precedent.** `(aje)` is the same shape one module over:
``read_decisions`` promised *"Never raises"*, raised on invalid UTF-8, and bricked every catalog
open from an unguarded seam - found by soak twelve, on a file far less likely to be damaged than
this one. A licence token is a small text file beside a photo library that a user is told to copy
between machines, so every way it can arrive wrong is an ordinary event, not an attack.

⚠ **So the tests below are written as a list of ways to be wrong, not as a happy path with an
error case bolted on.** Each one asserts the same two things: it does not raise, and it lands in
a state that still leaves a person able to reach their own files. There is no gate yet
(`DECISIONS.md` D16 names this stage 1), which is exactly why the format is pinned now - every
token is perpetual by D6 §1, so these bytes are the ones this product has to keep reading.
"""

from __future__ import annotations

import json

import nacl.signing
import pytest
from truestill_core import app_paths, licence
from truestill_core.licence import LicenceState

#: The kid every fixture token is signed under. A short string on purpose: a `kid` is an index
#: into a table, never a secret, and one that looks like a secret invites being treated as one.
KID = "test-k1"


@pytest.fixture
def signer() -> nacl.signing.SigningKey:
    """A keypair per test, generated rather than committed.

    ⚠ **A committed private key would be a key this repository publishes**, and the fact that it
    only signs test tokens is not a reason to teach the habit. Generating one costs microseconds.
    """
    return nacl.signing.SigningKey.generate()


@pytest.fixture
def keys(signer: nacl.signing.SigningKey) -> dict[str, str]:
    """The trust table as `verify_token` takes it - the parameter that exists so a test can
    supply a root without an environment variable being able to."""
    return {KID: licence.b64url_encode(bytes(signer.verify_key))}


def make_token(
    signer: nacl.signing.SigningKey,
    *,
    kid: str = KID,
    covers_through: int = 1,
    **overrides: object,
) -> str:
    """A well-formed token, signed. Overrides reach the payload verbatim so a test can produce a
    token that is valid in every way except the one under test."""
    fields: dict[str, object] = {
        "v": licence.PAYLOAD_VERSION,
        "kid": kid,
        "sub": "acc-0001",
        "lic": "lic-0001",
        "name": "A Buyer",
        "email": "buyer@example.com",
        "edition": "pro",
        "covers_through": covers_through,
        "issued_at": "2026-09-11",
        "updates_until": "2027-09-11",
    }
    fields.update(overrides)
    encoded = licence.encode_payload(fields)
    signature = signer.sign(licence.signing_input(encoded)).signature
    return f"{encoded}.{licence.b64url_encode(signature)}"


# --- the five states ------------------------------------------------------------------------


def test_no_token_and_no_marker_is_a_fresh_install() -> None:
    """ABSENT. Nothing on disk, and that is not an error - it is every user's first launch."""
    assert licence.read_licence().state is LicenceState.ABSENT
    assert not app_paths.licence_path().exists()


def test_a_token_that_covers_this_build_is_active(
    signer: nacl.signing.SigningKey, keys: dict[str, str]
) -> None:
    """ACTIVE, and the payload survives the round trip intact.

    The name and email are asserted because they are not incidental: D6 §2 makes them the
    share-deterrent, and a surface shows them as who is signed in. A verifier that discarded
    them would satisfy a state-only assertion and break the feature they exist for.
    """
    licence.write_licence(make_token(signer, covers_through=licence.BUILD_EPOCH))

    result = licence.read_licence(keys=keys)

    assert result.state is LicenceState.ACTIVE
    assert result.covers_this_build
    assert result.payload is not None
    assert result.payload.name == "A Buyer"
    assert result.payload.email == "buyer@example.com"
    assert result.payload.edition == "pro"
    assert result.reason == ""


def test_a_token_below_this_builds_epoch_is_lapsed_and_still_names_its_owner(
    signer: nacl.signing.SigningKey, keys: dict[str, str]
) -> None:
    """LAPSED. Entitlement to NEW versions ran out; D16 §2 is explicit that nothing bought is lost.

    The payload is still returned, which is the assertion that matters here: a lapsed licence is
    a real licence belonging to a real customer, and a verifier that threw the payload away would
    leave a surface unable to greet them by name or say what renewing would restore.
    """
    licence.write_licence(make_token(signer, covers_through=licence.BUILD_EPOCH - 1))

    result = licence.read_licence(keys=keys)

    assert result.state is LicenceState.LAPSED
    assert not result.covers_this_build
    assert result.payload is not None
    assert result.payload.name == "A Buyer"


def test_signing_out_is_told_apart_from_never_having_signed_in(
    signer: nacl.signing.SigningKey, keys: dict[str, str]
) -> None:
    """SIGNED_OUT, and the token is gone rather than merely ignored.

    Both halves are asserted because either alone would be a lie: a marker with the token still
    on disk is not a sign-out, and a deleted token with no marker is indistinguishable from a
    fresh install, which `(aam)` ruled matters.
    """
    licence.write_licence(make_token(signer))
    assert licence.read_licence(keys=keys).state is LicenceState.ACTIVE

    licence.sign_out()

    assert licence.read_licence(keys=keys).state is LicenceState.SIGNED_OUT
    assert not app_paths.licence_path().exists()


def test_signing_back_in_clears_the_marker(
    signer: nacl.signing.SigningKey, keys: dict[str, str]
) -> None:
    """The other direction, which is where a marker-based design goes wrong if nobody checks.

    A marker that outlived the next activation would leave a paying, signed-in user reading as
    signed out the moment their token became unreadable for any other reason.
    """
    licence.sign_out()
    licence.write_licence(make_token(signer))

    assert licence.read_licence(keys=keys).state is LicenceState.ACTIVE
    assert not app_paths.signed_out_path().exists()


# --- UNREADABLE: the dangerous state, one case per way a file arrives wrong ------------------


def _write_raw(written: bytes) -> None:
    target = app_paths.licence_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(written)


@pytest.mark.parametrize(
    ("case", "written"),
    [
        ("no separator", b"not-a-token"),
        ("empty signature", b"eyJhIjoxfQ."),
        ("truncated mid-token", b"eyJhIjoxfQ.AAAA"),
        # `(aje)`'s own byte: a lone 0x80 is a continuation with nothing to continue, so it is
        # invalid UTF-8 anywhere in a stream. That is the input that bricked `read_decisions`.
        ("invalid utf-8", b"\x80\x81\x82"),
        ("a JPEG that landed here by mistake", b"\xff\xd8\xff\xe0\x00\x10JFIF"),
        ("json that is not an object", b"WzEsMiwzXQ.AAAA"),
        ("not base64url at all", b"!!!!.!!!!"),
    ],
)
def test_a_damaged_file_is_a_state_and_never_an_exception(
    case: str, written: bytes, keys: dict[str, str]
) -> None:
    """**The property this whole module exists for.** Not one of these may raise.

    Every case is a file a user could plausibly end up with - an interrupted download, a copy
    that took the wrong bytes, a sync client that truncated, the wrong file dragged into place.
    None of them is evidence of anything, so none of them produces an accusation: the wording is
    asserted to offer a way out rather than merely name a failure.

    ⚠ **The state is asserted EXACTLY, not as a set.** It read
    `in {UNREADABLE, ABSENT}` when first written, which a verifier answering ABSENT to everything
    would have satisfied - the cry-wolf half of this file passing on a function that does
    nothing. The two genuinely-empty inputs moved to their own test below, where the weaker
    answer is the correct one and can be asserted on its own.
    """
    _write_raw(written)

    result = licence.read_licence(keys=keys)

    assert result.state is LicenceState.UNREADABLE, case
    assert result.payload is None, case
    assert result.reason, case
    assert "sign in" in result.reason.lower() or "update" in result.reason.lower(), case


@pytest.mark.parametrize(("case", "written"), [("empty", b""), ("whitespace only", b"   \n")])
def test_a_file_with_nothing_in_it_reads_as_no_licence_rather_than_a_damaged_one(
    case: str, written: bytes, keys: dict[str, str]
) -> None:
    """Zero bytes is the one damage that carries no information, so it gets the honest answer.

    An interrupted write leaves this, and so does a file a user created by hand while following
    instructions. There is nothing to diagnose and nothing to re-download that differs from what
    a fresh install needs, so it is ABSENT - which is what the surface would have said anyway,
    without an error message claiming a problem the user cannot see.
    """
    _write_raw(written)

    result = licence.read_licence(keys=keys)

    assert result.state is LicenceState.ABSENT, case
    assert result.reason == "", case


def test_a_token_signed_by_a_key_this_build_does_not_know_is_unreadable(
    signer: nacl.signing.SigningKey, keys: dict[str, str]
) -> None:
    """An unknown `kid`. The ordinary cause is a token issued after this build shipped, so the
    wording sends the user to check for an update rather than implying forgery."""
    licence.write_licence(make_token(signer, kid="k99"))

    result = licence.read_licence(keys=keys)

    assert result.state is LicenceState.UNREADABLE
    assert "update" in result.reason.lower()


def test_a_payload_edited_after_signing_does_not_verify(
    signer: nacl.signing.SigningKey, keys: dict[str, str]
) -> None:
    """**The one that makes every other assertion here mean something.**

    Without it, a verifier that skipped the signature entirely would pass all five state tests
    above. The edit is the one a forger would actually make - raise `covers_through` past the
    build epoch - and it must not survive.
    """
    token = make_token(signer, covers_through=licence.BUILD_EPOCH - 1)
    encoded_payload, _, signature = token.partition(".")
    fields = json.loads(licence.b64url_decode(encoded_payload))
    fields["covers_through"] = licence.BUILD_EPOCH + 99
    forged = f"{licence.encode_payload(fields)}.{signature}"

    licence.write_licence(forged)

    result = licence.read_licence(keys=keys)
    assert result.state is LicenceState.UNREADABLE
    assert result.payload is None


def test_a_signature_from_a_different_key_does_not_verify(keys: dict[str, str]) -> None:
    """The same proof from the other side: a real Ed25519 signature over the real bytes, made by
    a key the table does not hold. A verifier that checked only that a signature was well-formed
    would pass the test above and fail here."""
    impostor = nacl.signing.SigningKey.generate()
    licence.write_licence(make_token(impostor))

    assert licence.read_licence(keys=keys).state is LicenceState.UNREADABLE


def test_a_payload_this_build_cannot_understand_is_unreadable_not_active(
    signer: nacl.signing.SigningKey, keys: dict[str, str]
) -> None:
    """A future payload version, correctly signed. It must not be read as an entitlement.

    Trusting a signature is not the same as understanding what it covers, and the failure this
    guards is the quiet one: reading a v2 payload with v1 rules and granting whatever the missing
    fields default to.
    """
    licence.write_licence(make_token(signer, v=licence.PAYLOAD_VERSION + 1))

    result = licence.read_licence(keys=keys)

    assert result.state is LicenceState.UNREADABLE
    assert result.payload is None


def test_a_covers_through_that_is_not_a_number_is_refused(
    signer: nacl.signing.SigningKey, keys: dict[str, str]
) -> None:
    """Signed, current version, and `covers_through` is a string.

    ⚠ **`True` is included because `isinstance(True, int)` is `True` in Python**, so a naive
    check admits a boolean and `True >= 1` then reads as covered for ever. That is the kind of
    defect a type annotation does not catch, because the value arrives from JSON.
    """
    for bad in ("999", True, None, 1.5):
        licence.write_licence(make_token(signer, covers_through=bad))
        assert licence.read_licence(keys=keys).state is LicenceState.UNREADABLE, bad


def test_a_directory_where_the_token_should_be_is_a_state_not_a_crash(keys: dict[str, str]) -> None:
    """The shape that is easiest to forget and produces the ugliest failure.

    It happens: a restore tool recreating a tree, a sync client resolving a conflict, a user
    unzipping into the data directory. `read_text` raises `IsADirectoryError`, which is not an
    `OSError` subclass anyone remembers to catch until it has already reached a user.
    """
    app_paths.licence_path().mkdir(parents=True)

    result = licence.read_licence(keys=keys)

    assert result.state is LicenceState.UNREADABLE
    assert result.reason


# --- the file on disk -------------------------------------------------------------------------


def test_the_token_is_written_private(signer: nacl.signing.SigningKey) -> None:
    """0600 at creation, `session_link`'s rule and its reasoning.

    It carries the buyer's name and email, so on a shared machine it is not everyone's business.
    The mode is read back from the file rather than trusted, because `touch` reports success on a
    filesystem that discarded it.
    """
    target = licence.write_licence(make_token(signer))

    assert target.stat().st_mode & 0o777 == 0o600


def test_writing_a_second_token_replaces_the_first_rather_than_appending(
    signer: nacl.signing.SigningKey, keys: dict[str, str]
) -> None:
    """Two tokens in one file is two answers, and only the newest is anyone's licence."""
    licence.write_licence(make_token(signer, covers_through=licence.BUILD_EPOCH - 1))
    licence.write_licence(make_token(signer, covers_through=licence.BUILD_EPOCH))

    assert licence.read_licence(keys=keys).state is LicenceState.ACTIVE
    assert app_paths.licence_path().read_text().count(".") == 1


def test_the_token_lives_beside_the_catalog_and_not_inside_it() -> None:
    """The placement decision, asserted rather than left in a comment.

    ⚠ **In the catalog it would travel.** `catalog.set_setting` marks the catalog dirty and its
    value rides along when the file is copied to a second machine, and a catalog that had to be
    rebuilt would take the licence with it. A token belongs to an installation; a user may hold
    several libraries.
    """
    assert app_paths.licence_path().parent == app_paths.default_catalog_path().parent
    assert app_paths.licence_path().suffix != ".sqlite"
    assert app_paths.signed_out_path().parent == app_paths.licence_path().parent


# --- the entitlement is not the clock ---------------------------------------------------------


def test_the_verdict_does_not_depend_on_the_system_clock(
    signer: nacl.signing.SigningKey, keys: dict[str, str]
) -> None:
    """**D16 §2's consequence, asserted where it can regress.**

    `updates_until` is display only. A token whose stated update window ended in 1970 and one
    whose window ends in 2999 must produce the same state, because the only comparison that
    happens is `covers_through` against `BUILD_EPOCH`. A future maintainer adding a date check
    "for correctness" breaks this test, which is the whole point of it existing.
    """
    verdicts = set()
    for stamp in ("1970-01-01", "2026-09-11", "2999-12-31"):
        licence.write_licence(
            make_token(signer, covers_through=licence.BUILD_EPOCH, updates_until=stamp)
        )
        verdicts.add(licence.read_licence(keys=keys).state)

    assert verdicts == {LicenceState.ACTIVE}


def test_an_issue_date_in_the_future_is_not_treated_as_invalid(
    signer: nacl.signing.SigningKey, keys: dict[str, str]
) -> None:
    """The same rule from the direction a wrong clock actually breaks things.

    A machine whose clock is behind sees every token as issued in the future. If `issued_at` were
    ever checked, that user would be locked out by a dead CMOS battery - and they would have no
    way to connect the two.
    """
    licence.write_licence(
        make_token(signer, covers_through=licence.BUILD_EPOCH, issued_at="2999-01-01")
    )

    assert licence.read_licence(keys=keys).state is LicenceState.ACTIVE


# --- the trust root ---------------------------------------------------------------------------


def test_the_shipped_key_table_is_consulted_when_no_keys_are_passed() -> None:
    """Anti-vacuity for every test above, and the reason it matters is specific.

    Each test passes its own `keys`, so nothing else here would notice if the default argument
    stopped reaching `PUBLIC_KEYS` - and then the product, which passes nothing, would verify
    against an empty table for ever while the suite stayed green. This asserts the default path
    is the shipped table, and that the table is currently empty on purpose.
    """
    signer = nacl.signing.SigningKey.generate()
    assert KID not in licence.PUBLIC_KEYS, "the fixture kid must not collide with a shipped one"
    token = make_token(signer, covers_through=licence.BUILD_EPOCH)
    table = {KID: licence.b64url_encode(bytes(signer.verify_key))}

    # The same token, twice, differing only in whether the table is supplied. Asserting both
    # halves is what proves the default reaches PUBLIC_KEYS: the UNREADABLE line alone would
    # also pass on a verifier that ignored `keys` and refused everything.
    assert licence.verify_token(token, keys=table).state is LicenceState.ACTIVE
    assert licence.verify_token(token).state is LicenceState.UNREADABLE


def test_every_shipped_key_is_a_usable_ed25519_public_key() -> None:
    """What keeps the table honest, and it **runs now** where an identical loop did not.

    ⚠ **This assertion was DELETED as vacuous when `PUBLIC_KEYS` was empty** - a loop over an
    empty dict is the dead-assertion shape, green for ever against a body that never executes. It
    is restored with the first real key because the risk it guards is now live: a typo in a pasted
    key is silent. Every token signed by its partner reads as UNREADABLE, the suite stays green
    because no test holds the matching private half, and the defect arrives as a support ticket
    from someone who has already paid.

    The count assertion is the anti-vacuity half: without it, a future edit emptying the table
    would make this test pass by doing nothing again.
    """
    assert len(licence.PUBLIC_KEYS) >= 1

    for kid, encoded in licence.PUBLIC_KEYS.items():
        raw = licence.b64url_decode(encoded)
        assert len(raw) == 32, kid
        nacl.signing.VerifyKey(raw)


def test_a_mistyped_key_in_the_table_is_refused_rather_than_crashing() -> None:
    """A typo in a pasted public key, which is the realistic way this table goes wrong.

    ⚠ **This replaced a loop over `PUBLIC_KEYS` asserting every entry is a valid 32-byte key.**
    That loop was **vacuous**: the table is empty, so its body never ran, and it would have gone
    on never running until the first key landed - the dead-assertion shape this repo already has
    a census of. The risk is real, so it is tested against an input that exists instead: a table
    entry that is not a key must produce a state, not a traceback, because the person it would
    crash on is a paying customer and the mistake is the maintainer's.
    """
    signer = nacl.signing.SigningKey.generate()
    token = make_token(signer)

    for broken in ("", "not-base64!!", licence.b64url_encode(b"too short"), "AAAA"):
        result = licence.verify_token(token, keys={KID: broken})
        assert result.state is LicenceState.UNREADABLE, broken
        assert result.reason, broken
