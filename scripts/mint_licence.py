#!/usr/bin/env python3
"""Generate a signing key, and sign licence tokens by hand. `DECISIONS.md` D5, D6, D16.

**This is stage 3's manual issue, arriving at stage 1**, and that ordering is the point: it is
what lets the maintainer serve a first customer before a licensing server exists, and it is how
the token format gets exercised end to end while it is still free to change.

Usage::

    # Once, on a machine that is not this repository. Prints the line to paste into licence.py.
    python3 scripts/mint_licence.py --new-key ~/keys/truestill-k1.key --kid k1

    # Per customer.
    python3 scripts/mint_licence.py \\
        --key ~/keys/truestill-k1.key --kid k1 \\
        --name "A Buyer" --email buyer@example.com \\
        --covers-through 1 --updates-until 2027-09-11

⚠ **THE PRIVATE KEY IS THE WHOLE SYSTEM.** Anyone holding it can issue a licence that every
build ever shipped will accept, and because tokens are perpetual on the build they cover (D18;
D6 §1's surviving property) a compromise cannot be
cleaned up by rotating - it needs a release that drops the ``kid`` plus a re-issue to everyone
who holds one. So this script refuses to write a key anywhere inside a git work tree, which is
the one mistake that turns a private key into a public one in a single ``git push``.

**It is also not where the key should stay.** D5 §5 requires a design pass covering backups and
what happens if the server is retired; a key on one laptop with no copy is the same single point
of failure one layer down. Keep a copy somewhere an estate can reach - a file this script can
write is not a key management plan.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

import nacl.signing

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "packages/truestill-core/src"))

from truestill_core.licence import (
    PAYLOAD_VERSION,
    b64url_decode,
    b64url_encode,
    encode_payload,
    signing_input,
)


def inside_a_repository(path: Path) -> bool:
    """Whether ``path`` sits inside a git work tree.

    Asks git rather than looking for a ``.git`` directory: a work tree can be configured
    elsewhere, and the question that matters is "would this be committable", which only git can
    answer.
    """
    probe = path.expanduser().resolve().parent
    if not probe.exists():
        return False
    result = subprocess.run(
        ["git", "-C", str(probe), "rev-parse", "--is-inside-work-tree"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0 and result.stdout.strip() == "true"


def write_new_key(target: Path, kid: str) -> int:
    """Generate a keypair, save the private half, print the public half as a table entry."""
    target = target.expanduser()
    if inside_a_repository(target):
        print(
            f"refusing to write a private key inside a git work tree: {target}\n"
            "Put it somewhere that is never committed - a password manager, an encrypted volume,"
            " or a directory outside every checkout.",
            file=sys.stderr,
        )
        return 2
    if target.exists():
        print(f"refusing to overwrite an existing key: {target}", file=sys.stderr)
        return 2

    signing_key = nacl.signing.SigningKey.generate()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.touch(mode=0o600)
    target.write_text(b64url_encode(bytes(signing_key)) + "\n", encoding="utf-8")

    public = b64url_encode(bytes(signing_key.verify_key))
    print(f"private key written to {target} (mode 0600)")
    print(
        "\nPaste this into PUBLIC_KEYS in packages/truestill-core/src/truestill_core/licence.py:\n"
    )
    print(f'    "{kid}": "{public}",')
    return 0


def sign_payload(signing_key: nacl.signing.SigningKey, fields: dict[str, object]) -> str:
    """Turn a payload into a signed token. **The only place a token is signed.**

    Extracted when `licences.py` arrived: two callers building the same two lines is how one of
    them ends up signing something subtly different - a different canonicalisation, a different
    thing signed - and the resulting token verifies nowhere with no obvious reason why.
    """
    encoded = encode_payload(fields)
    return f"{encoded}.{b64url_encode(signing_key.sign(signing_input(encoded)).signature)}"


def load_signing_key(path: Path) -> nacl.signing.SigningKey:
    """Read a private key, or raise ``ValueError`` with something a person can act on."""
    try:
        return nacl.signing.SigningKey(b64url_decode(path.expanduser().read_text().strip()))
    except (OSError, ValueError) as exc:
        msg = f"could not read the signing key at {path}: {exc}"
        raise ValueError(msg) from exc


def mint(args: argparse.Namespace) -> int:
    """Sign one token and print it."""
    try:
        signing_key = load_signing_key(Path(args.key))
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    fields = {
        "v": PAYLOAD_VERSION,
        "kid": args.kid,
        "sub": args.account or str(uuid.uuid4()),
        "lic": str(uuid.uuid4()),
        "name": args.name,
        "email": args.email,
        "edition": args.edition,
        "covers_through": args.covers_through,
        "issued_at": args.issued_at or datetime.now(tz=UTC).date().isoformat(),
        "updates_until": args.updates_until,
    }
    print(sign_payload(signing_key, fields))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--new-key", metavar="PATH", help="generate a keypair and write it here")
    parser.add_argument("--key", metavar="PATH", help="the signing key to mint with")
    parser.add_argument("--kid", default="k1", help="key id recorded in the token (default: k1)")
    parser.add_argument("--name", help="the buyer's name, embedded in the token (D6 §2)")
    parser.add_argument("--email", help="the buyer's email, embedded in the token (D6 §2)")
    parser.add_argument("--edition", default="pro", help="what was bought (default: pro)")
    parser.add_argument(
        "--covers-through",
        type=int,
        default=1,
        help="entitlement ceiling, compared against licence.BUILD_EPOCH (default: 1)",
    )
    parser.add_argument("--account", help="reuse an existing account id rather than minting one")
    parser.add_argument("--issued-at", help="ISO date (default: today). Display only.")
    parser.add_argument("--updates-until", help="ISO date shown to the buyer. Display only.")
    args = parser.parse_args(argv)

    if args.new_key:
        return write_new_key(Path(args.new_key), args.kid)

    missing = [f for f in ("key", "name", "email", "updates_until") if not getattr(args, f)]
    if missing:
        parser.error(
            "required for minting: " + ", ".join("--" + f.replace("_", "-") for f in missing)
        )
    return mint(args)


if __name__ == "__main__":
    raise SystemExit(main())
