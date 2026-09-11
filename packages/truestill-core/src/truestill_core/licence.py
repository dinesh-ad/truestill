"""What a licence token says, and whether this build is covered by it. `DECISIONS.md` D5, D6, D16.

**Stage 1 of the licensing arc: the format and the verifier, and nothing that acts on them.**
Nothing in the product calls this module yet - there is no gate, no cap and no UI. That is
deliberate: the format is free to change while no token has been issued, and expensive to change
afterwards, because D6 §1 makes every token perpetual.

**The token is a file on the user's disk, verified against a public key compiled into this
module.** D5 §1 is what forces that shape - *"The app receives a signed local token and runs
fully offline thereafter. Activation is one-time; there is no per-launch phone-home and no
periodic revalidation."* So verification touches no network, and a licensing server that is down,
unreachable, or eventually retired cannot reach an install that already activated.

**THE ENTITLEMENT IS A VERSION CEILING, NOT A DATE.** ``covers_through`` is compared against
:data:`BUILD_EPOCH` - a number this source file carries - and never against the system clock.
D16 §2 rules it and gives the reason; the consequence here is worth stating in its own right,
because it deletes an entire class of problem rather than defending against it:

- A machine whose clock is wrong cannot lapse a licence. Not a wrong timezone, not a dead CMOS
  battery, not a VM restored from a snapshot, not a fresh install before NTP has run.
- Rolling the clock back buys nothing, so none of the usual counter-tampering machinery -
  highest-seen-timestamp files, monotonic counters, grace periods - has anything to do.
- The answer is a pure function of two integers that are both already on disk.

``updates_until`` is in the payload anyway, because a buyer needs to see what they bought. It is
**display only** and decides nothing.

**Nothing here raises.** A licence file is 2 KB of text sitting next to a photo library, and
every way it can be wrong - truncated, empty, half-written, corrupted, invalid UTF-8, signed by a
key this build does not know - must end in a *state*, never an exception. `(aje)` is the
precedent and it is exactly this shape one module over: ``read_decisions`` promised *"Never
raises"*, raised on invalid UTF-8, and bricked every catalog open from an unguarded seam. The
tests for this module are written against that list.

**The state is reported; the consequence is not decided here.** :class:`LicenceState` says what
is true. What the product does about each state is stage 2, lives with the surfaces, and is
governed by D16 §1 - the app always opens, every feature works, and what free limits is the
number of files a run *writes*.
"""

from __future__ import annotations

import base64
import binascii
import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Final

import nacl.exceptions
import nacl.signing

from truestill_core.app_paths import licence_path, signed_out_path

#: The payload shape this build can read. Bumped only when a field's *meaning* changes, never
#: when one is added: a reader that ignores unknown keys handles additions already.
#:
#: It exists because tokens are perpetual (D6 §1). Without a version in the payload, the first
#: change to the format would have to either invalidate every token ever issued or be guessed at
#: by shape, and both are worse than one integer.
PAYLOAD_VERSION: Final = 1

#: **The entitlement scale, and the only number ``covers_through`` is ever compared against.**
#:
#: An integer bumped by hand at the release that begins a new entitlement period - not a version
#: string, not a date. Semantic version comparison was considered and refused: it turns "is this
#: build covered" into an argument about what a patch release is, at exactly the moment a paying
#: user is waiting for an answer. An integer has one reading.
#:
#: ⚠ **Bumping this is a commercial act, not a chore.** Every existing token whose
#: ``covers_through`` is below the new value stops covering *new* builds the moment it changes.
#: It never touches a build already installed - D16 §2, *"a lapsed licence loses nothing it
#: bought"* - because that build carries its own :data:`BUILD_EPOCH` and compares against it.
BUILD_EPOCH: Final = 1

#: Ed25519 verify keys this build trusts, ``kid`` -> base64url public key (32 bytes, unpadded).
#:
#: **A table rather than one key, and that is the whole of key rotation.** A new release adds a
#: new ``kid`` and the server signs new tokens with it; every token signed by an older one keeps
#: verifying because its ``kid`` is still here.
#:
#: ⚠ **AN ENTRY CAN NEVER BE REMOVED, and this is an accumulating cost accepted deliberately
#: rather than discovered later.** Tokens are perpetual, so dropping a ``kid`` retroactively
#: breaks whoever holds a token signed by it - the strand-a-paying-customer failure this whole
#: design is arranged against. A *compromised* key is a different event from a rotated one, and
#: its only honest remedy is a release that drops the entry plus a re-issue to everyone affected.
#: That is why where the private key lives matters more than how often it turns over.
#:
#: ``k1`` was generated 2026-09-11 by ``scripts/mint_licence.py --new-key``. **Its private half
#: has never been in this repository and cannot be**: the script refuses to write a key inside a
#: git work tree, asking git rather than looking for a ``.git`` directory. What is below is the
#: *public* half, which is meant to be published - that is the whole point of an embedded
#: verification key.
PUBLIC_KEYS: Final[dict[str, str]] = {
    "k1": "QjGET80IOexfMibpDrdui3aAf5e1C6yk5ZMyo9dkeBc",
}

#: **Which release opened each entitlement period.** The map is the mechanism by which bumping
#: :data:`BUILD_EPOCH` stays a deliberate act, and it exists because a bare integer changing from
#: ``1`` to ``2`` is a one-character diff that reads like a typo and costs every unrenewed
#: customer their next update.
#:
#: ``test_the_entitlement_epoch_cannot_move_by_accident.py`` holds three properties against it:
#: :data:`BUILD_EPOCH` is the highest key, an epoch may only be opened by a **minor or major**
#: version (never a patch), and the running package version is at or beyond the version that
#: opened the current epoch. So a release that means to open an epoch must add a row and bump a
#: minor, and a release that does not mean to cannot open one at all.
EPOCH_OPENED_AT: Final[dict[int, str]] = {
    1: "0.1.0",
}


class LicenceState(StrEnum):
    """The five states, and every one of them is reachable by an ordinary user.

    ⚠ **:attr:`UNREADABLE` is the dangerous one and it is deliberately adjacent to
    :attr:`LAPSED`, never to "no licence".** A corrupt 2 KB file must never cost someone access
    to their own photographs, so whatever the product does about a lapsed licence it must do
    about an unreadable one, plus say what went wrong and how to replace it.
    """

    #: No token and no sign-out marker: this install has never been activated.
    ABSENT = "absent"
    #: Verifies, and ``covers_through`` reaches this build.
    ACTIVE = "active"
    #: Verifies, and ``covers_through`` does not reach this build. Entitlement to **new versions**
    #: has lapsed; D16 §2 is explicit that nothing already bought is lost.
    LAPSED = "lapsed"
    #: The user signed out. Distinct from :attr:`ABSENT` only in what a surface should say - one
    #: has never been here, the other chose to leave.
    SIGNED_OUT = "signed_out"
    #: A token is present and this build cannot make sense of it.
    UNREADABLE = "unreadable"


@dataclass(frozen=True, slots=True)
class LicencePayload:
    """What the token says. Every field is the server's claim, signed and unmodifiable.

    **Readable by design.** A user can open the file, decode it and see exactly what it records
    about them. That is what makes D5's *"an account for the software, never for your data"*
    honest at the level of the artifact rather than only in the copy.
    """

    version: int
    kid: str
    #: Opaque account id. **Not** the email: the token should not be the only durable link
    #: between a person and their identity, and support needs a handle that survives a change of
    #: address.
    account: str
    #: Opaque licence id. One account may buy twice, and entitlement belongs to the purchase.
    licence: str
    #: D6 §2's decision, which survived the move from key to token: *"A shared key carries the
    #: sharer's own name and email. That is a social deterrent rather than a technical
    #: restriction... it costs an honest user nothing, and it never risks locking out someone who
    #: has paid."* It is also what a surface shows as who is signed in.
    name: str
    email: str
    #: What was bought. Present before a second tier exists, because a token issued without it
    #: could never be read as anything but the tier that existed on the day it was signed.
    edition: str
    #: The entitlement. Compared against :data:`BUILD_EPOCH`, never against a clock.
    covers_through: int
    #: ISO dates, both **display only**. Neither is ever compared against anything.
    issued_at: str
    updates_until: str


@dataclass(frozen=True, slots=True)
class Licence:
    """A state, the payload behind it when there is one, and wording for a person.

    ``reason`` is filled for :attr:`LicenceState.UNREADABLE` alone and says what could not be
    read, in a sentence a user can act on. Presentation stays with each surface -
    ``catalog_busy`` is the pattern - but the wording has one home, which is
    `IMPLEMENTATION_STANDARDS.md` §9's rule.
    """

    state: LicenceState
    payload: LicencePayload | None = None
    reason: str = ""

    @property
    def covers_this_build(self) -> bool:
        """Whether this build is inside the entitlement. Only :attr:`LicenceState.ACTIVE` is."""
        return self.state is LicenceState.ACTIVE


def b64url_encode(raw: bytes) -> str:
    """Unpadded base64url. The one encoding this format uses, in one place."""
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def b64url_decode(text: str) -> bytes:
    """Inverse of :func:`b64url_encode`. Raises ``ValueError`` on anything that is not one."""
    padded = text + "=" * (-len(text) % 4)
    try:
        return base64.urlsafe_b64decode(padded.encode("ascii"))
    except (binascii.Error, UnicodeEncodeError) as exc:  # pragma: no cover - message only
        msg = f"not base64url: {exc}"
        raise ValueError(msg) from exc


def encode_payload(fields: dict[str, Any]) -> str:
    """Canonical JSON, base64url. Shared with the mint script so one place defines the bytes."""
    canonical = json.dumps(fields, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return b64url_encode(canonical.encode("utf-8"))


def signing_input(encoded_payload: str) -> bytes:
    """The exact bytes that are signed and verified.

    ⚠ **The ENCODED payload, never the JSON it decodes to, and the difference is load-bearing.**
    Signing the decoded object would make verification depend on this build re-serialising it to
    the same bytes the server produced - so a different key order, a different unicode escape or
    a float rendered differently would read as a forged signature on a perfectly good token.
    Verifying the received bytes removes canonicalisation from the trust path entirely. This is
    the one thing JWS gets right and it is worth copying without copying JWS.
    """
    return encoded_payload.encode("ascii")


def verify_token(
    token: str,
    *,
    keys: dict[str, str] | None = None,
    build_epoch: int = BUILD_EPOCH,
) -> Licence:
    """Read ``token`` and say what state it puts this build in. **Never raises.**

    ``keys`` defaults to :data:`PUBLIC_KEYS`; it is a parameter so that tests can supply a
    keypair they generated, rather than the alternative - an environment variable naming a trust
    root, which is a forgery hole wearing a test helper's clothes.
    """
    trusted = PUBLIC_KEYS if keys is None else keys

    encoded_payload, _, encoded_signature = token.strip().partition(".")
    if not encoded_payload or not encoded_signature:
        return Licence(LicenceState.UNREADABLE, reason=_UNREADABLE_SHAPE)

    try:
        signature = b64url_decode(encoded_signature)
        raw_payload = b64url_decode(encoded_payload)
    except ValueError:
        return Licence(LicenceState.UNREADABLE, reason=_UNREADABLE_SHAPE)

    try:
        fields = json.loads(raw_payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return Licence(LicenceState.UNREADABLE, reason=_UNREADABLE_SHAPE)
    if not isinstance(fields, dict):
        return Licence(LicenceState.UNREADABLE, reason=_UNREADABLE_SHAPE)

    kid = fields.get("kid")
    if not isinstance(kid, str) or kid not in trusted:
        return Licence(LicenceState.UNREADABLE, reason=_UNREADABLE_KEY)

    try:
        verify_key = nacl.signing.VerifyKey(b64url_decode(trusted[kid]))
        verify_key.verify(signing_input(encoded_payload), signature)
    except (ValueError, TypeError, nacl.exceptions.CryptoError):
        # `CryptoError` is the parent of BadSignatureError and of the malformed-key and
        # wrong-length-signature errors, so one clause covers "not signed by this key" and "this
        # is not a signature at all" - which are the same answer to the only question here.
        return Licence(LicenceState.UNREADABLE, reason=_UNREADABLE_SIGNATURE)

    payload = _payload_from(fields)
    if payload is None:
        return Licence(LicenceState.UNREADABLE, reason=_UNREADABLE_FIELDS)

    state = LicenceState.ACTIVE if payload.covers_through >= build_epoch else LicenceState.LAPSED
    return Licence(state, payload=payload)


def read_licence(
    *,
    keys: dict[str, str] | None = None,
    build_epoch: int = BUILD_EPOCH,
) -> Licence:
    """The state of this installation. **Never raises**, for any state of the filesystem.

    Reads :func:`~truestill_core.app_paths.licence_path`, falling back to the sign-out marker so
    that "never activated" and "signed out" can be told apart - a difference that changes only
    what a surface says, which is reason enough for one empty file.
    """
    try:
        token = licence_path().read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return _no_token(exc)

    if not token.strip():
        return _no_token(None)
    return verify_token(token, keys=keys, build_epoch=build_epoch)


def _no_token(exc: Exception | None) -> Licence:
    """No readable token: which of the three no-token states this is.

    ⚠ **An unreadable FILE is not an unreadable TOKEN, and they must not collapse.** A directory
    where the file should be, a permission refusal, invalid UTF-8 on disk - none of those is a
    licence problem a user can fix by re-downloading, so each keeps its own wording. A *missing*
    file is the ordinary case and is not an error at all.
    """
    if isinstance(exc, FileNotFoundError | IsADirectoryError | NotADirectoryError) or exc is None:
        if isinstance(exc, IsADirectoryError | NotADirectoryError):
            return Licence(LicenceState.UNREADABLE, reason=_UNREADABLE_PATH)
        return Licence(_absent_or_signed_out())
    return Licence(LicenceState.UNREADABLE, reason=_UNREADABLE_PATH)


def _absent_or_signed_out() -> LicenceState:
    try:
        marker = signed_out_path().exists()
    except OSError:
        marker = False
    return LicenceState.SIGNED_OUT if marker else LicenceState.ABSENT


def _payload_from(fields: dict[str, Any]) -> LicencePayload | None:
    """Build a payload, or ``None`` when the signed object is not one this build understands.

    **Checked after the signature, never before.** Reading fields out of an unverified object and
    acting on them is how a parser becomes an attack surface; by the time this runs, every byte
    has been signed by a key in the table.

    **Unknown keys are ignored on purpose** - that is what lets a later payload add a field
    without a release of this build refusing the tokens that carry it.
    """
    version = fields.get("v")
    if version != PAYLOAD_VERSION:
        return None
    covers_through = fields.get("covers_through")
    if not isinstance(covers_through, int) or isinstance(covers_through, bool):
        return None

    text: dict[str, str] = {}
    for key in ("kid", "sub", "lic", "name", "email", "edition", "issued_at", "updates_until"):
        value = fields.get(key)
        if not isinstance(value, str):
            return None
        text[key] = value

    return LicencePayload(
        version=version,
        kid=text["kid"],
        account=text["sub"],
        licence=text["lic"],
        name=text["name"],
        email=text["email"],
        edition=text["edition"],
        covers_through=covers_through,
        issued_at=text["issued_at"],
        updates_until=text["updates_until"],
    )


def write_licence(token: str) -> Path:
    """Store ``token``, replacing whatever is there, and clear the sign-out marker.

    **Created at mode 0600 by the call that creates it**, which is ``session_link``'s rule and
    its reasoning applies unchanged: a mode is applied only when a file is *created*, so writing
    over an existing file keeps whatever mode it already had, and ``write_text`` alone yields the
    umask default. Unlinking first also drops a symlink sitting at this path rather than writing
    the token through it to somewhere else.

    The token is the user's own and is meant to be copied between their machines - D5's
    offline-activation path is exactly that - so 0600 is about a shared machine, not about
    keeping it from its owner.
    """
    target = licence_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.unlink(missing_ok=True)
    target.touch(mode=0o600)
    target.write_text(token.strip() + "\n", encoding="utf-8")
    signed_out_path().unlink(missing_ok=True)
    return target


def install_token_from(
    source: Path,
    *,
    keys: dict[str, str] | None = None,
    build_epoch: int = BUILD_EPOCH,
) -> Licence:
    """Activate from a file the user points at. **Never raises.**

    ⚠ **THIS IS THE WHOLE OF ACTIVATION UNTIL THERE IS A SERVER**, and it is not a stopgap - D5's
    offline path is exactly this shape and survives the server existing: *"sign in on any device
    with a browser, download the token file, copy it onto the target machine."* JetBrains and
    DBeaver both end in a file the user drops in; ours is simpler only because the token is not
    machine-bound, so there is no challenge to exchange.

    **It verifies BEFORE it installs, and installs nothing when verification fails.** The
    alternative - write it, then read it back and report - would replace a working licence with a
    broken one because the user picked the wrong file out of their downloads folder. The
    installed token is not touched unless the new one is good.

    A licence that verifies but does not cover this build is still **installed**: that is a lapsed
    licence, and D16 §2 is explicit that it is a real entitlement rather than a failure.
    """
    try:
        token = source.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return Licence(LicenceState.UNREADABLE, reason=_ACTIVATION_UNREADABLE_FILE)

    candidate = verify_token(token, keys=keys, build_epoch=build_epoch)
    if candidate.state is LicenceState.UNREADABLE:
        return candidate

    write_licence(token)
    return candidate


def sign_out() -> None:
    """Remove the token and record that leaving was deliberate.

    ⚠ **The marker is what keeps sign-out from being indistinguishable from a fresh install**,
    and `(aam)` already ruled why the difference is worth a file: *"a casual logout can strand a
    paying user on an offline machine"*, so the surface that offers this has to be able to say
    what happened rather than greeting a returning customer as a stranger.
    """
    licence_path().unlink(missing_ok=True)
    marker = signed_out_path()
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.touch(mode=0o600, exist_ok=True)


#: Wording, in one home. `IMPLEMENTATION_STANDARDS.md` §9: an outcome is worded once, so two
#: surfaces cannot drift. Each says what is wrong and what to do, and none of them accuses
#: anybody of anything - the overwhelmingly likely cause of every one is a damaged file.
_UNREADABLE_SHAPE: Final = (
    "This licence file is damaged and could not be read. Sign in to your account to download "
    "a fresh copy."
)
_UNREADABLE_KEY: Final = (
    "This licence was issued for a different version of truestill than this one. Check for an "
    "update, or sign in to your account to download a fresh copy."
)
_UNREADABLE_SIGNATURE: Final = (
    "This licence file could not be verified. Sign in to your account to download a fresh copy."
)
_UNREADABLE_FIELDS: Final = (
    "This licence is in a format this version of truestill does not understand. Check for an "
    "update."
)
_ACTIVATION_UNREADABLE_FILE: Final = (
    "That file could not be read. Choose the licence file you downloaded from your account - it "
    "is one line of text."
)
_UNREADABLE_PATH: Final = (
    "The licence file could not be opened. Check that nothing else is using it, then sign in to "
    "your account to download a fresh copy."
)
