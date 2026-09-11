#!/usr/bin/env python3
"""The maintainer's customer store, and the four things a support conversation needs.

⚠ **THIS IS THE FIRST THING IN THIS REPOSITORY THAT IS NOT PART OF THE PRODUCT.** Nothing built
here ships to a user, nothing a user runs touches it, and no code in `packages/` imports it. It
is a tool the maintainer runs on his own machine against his own records.

**THE TOOL IS IN THE TREE. THE DATA IS NOT.** The store is a single SQLite file beside the
signing key, outside every checkout, for the same reason the key is: customer names and email
addresses are personal data, and a private repository is still a repository - it is cloned onto
laptops, pushed to a host, and kept for ever by design. `git` is the wrong shape for a thing a
person may one day ask you to erase (`DECISIONS.md` D5's GDPR duties are not optional).

That is enforced rather than asked for: :func:`store_path` refuses a location inside a git work
tree, by asking git rather than looking for a `.git` directory - the same guard
`mint_licence.py` already uses on the private key, and for the same reason.

⚠ **IT JOINS THE SIGNING KEY ON THE LIST OF THINGS THAT ARE UNRECOVERABLE IF LOST.** See the
closing note of `--help`, and `Q1806` in the session record: losing the key means no new licence
can ever be issued that existing builds accept; losing this file means every customer's identity,
entitlement and history is gone while their tokens keep working for ever.

**Identity is the LICENCE, not the person.** An account may buy twice, so the token carries both
`sub` (the account) and `lic` (the purchase), and this store is shaped the same way: one
`accounts` row may own many `licences` rows, and every issue is recorded against a *licence*.

Usage::

    licences.py issue    --name "A Buyer" --email a@example.com --order-ref PAD-1234 \\
                         --updates-until 2027-09-11 --key ~/.truestill-signing/truestill-k1.key
    licences.py reissue  --order-ref PAD-1234 --key ...     # same licence, new token file
    licences.py find     buyer@example.com                  # or an order ref, or a licence id
    licences.py whois    ./truestill-licence.token          # who does THIS token belong to
    licences.py correct-email --order-ref PAD-1234 --email right@example.com --key ...
    licences.py forget   --account <account-id>             # a deletion request
"""

from __future__ import annotations

import argparse
import os
import re
import sqlite3
import sys
import uuid
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "packages/truestill-core/src"))

from mint_licence import inside_a_repository, load_signing_key, sign_payload
from truestill_core.licence import (
    BUILD_EPOCH,
    EPOCH_OPENED_AT,
    PAYLOAD_VERSION,
    LicenceState,
    verify_token,
)

#: Where the store lives, and the environment name that moves it. The default sits beside the
#: signing key deliberately: the two are lost together or backed up together, and a maintainer
#: who protects one directory has protected both.
STORE_ENV = "TRUESTILL_LICENCE_STORE"
DEFAULT_STORE = Path.home() / ".truestill-signing" / "customers.db"

#: The consent text a signup agreed to, versioned. D5 captures EU consent at signup; storing
#: *which wording* was agreed to is what makes the consent provable later, and a bare timestamp
#: against wording nobody recorded proves nothing. There is no signup yet, so a hand-issued
#: licence records the version the operator names.
DEFAULT_CONSENT_VERSION = "hand-issued"

SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
    account_id           TEXT PRIMARY KEY,
    email                TEXT,
    name                 TEXT,
    email_verified_at    TEXT,
    consent_at           TEXT,
    consent_text_version TEXT,
    created_at           TEXT NOT NULL,
    forgotten_at         TEXT
);
CREATE TABLE IF NOT EXISTS licences (
    licence_id     TEXT PRIMARY KEY,
    account_id     TEXT NOT NULL REFERENCES accounts(account_id),
    order_ref      TEXT NOT NULL UNIQUE,
    edition        TEXT NOT NULL,
    covers_through INTEGER NOT NULL,
    updates_until  TEXT NOT NULL,
    purchased_at   TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS issues (
    issue_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    licence_id     TEXT NOT NULL REFERENCES licences(licence_id),
    kid            TEXT NOT NULL,
    issued_at      TEXT NOT NULL,
    reason         TEXT NOT NULL,
    name_at_issue  TEXT,
    email_at_issue TEXT
);
"""


class StoreError(RuntimeError):
    """Anything the operator must read and act on, rather than a traceback."""


def now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def store_path() -> Path:
    """Where the store is, refusing any location inside a checkout.

    ⚠ **The refusal is the point of this function.** The whole rule - tool in the tree, data
    outside it - is one `git add -A` away from being broken by accident, and the only moment that
    can be caught is before the file is created. Asking git rather than looking for a `.git`
    directory is `mint_licence.inside_a_repository`'s reasoning unchanged: a work tree can be
    configured elsewhere, and the question is "would this be committable".
    """
    chosen = Path(os.environ.get(STORE_ENV, "").strip() or DEFAULT_STORE).expanduser()
    if inside_a_repository(chosen):
        msg = (
            f"refusing to keep customer records inside a git work tree: {chosen}\n"
            "Names and email addresses are personal data and a private repository is still a "
            "repository. Put the store beside the signing key, outside every checkout."
        )
        raise StoreError(msg)
    return chosen


@contextmanager
def opened(path: Path | None = None) -> Iterator[sqlite3.Connection]:
    """The store, committed on success, rolled back on failure, and **closed either way**.

    ⚠ `with sqlite3.connect(...) as db` commits or rolls back and **does not close** - a detail
    every one of the six commands here got wrong, because the shape looks exactly like a file
    handle and is not. It leaks a handle per invocation, which for a process that exits a
    millisecond later is invisible; that is precisely why it survives review and why it is worth
    writing once rather than six times.
    """
    connection = connect(path)
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def connect(path: Path | None = None) -> sqlite3.Connection:
    """Open (creating if needed) the store, at mode 0600.

    ``0600`` at creation for `session_link`'s reason and its caveat: a mode is applied only when
    a file is created, and on Windows CPython synthesizes `st_mode` so the number means nothing
    there - the protection is the user's own profile. This is a maintainer's machine, so the
    weaker platform story is acceptable and is stated rather than glossed.
    """
    target = path or store_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    fresh = not target.exists()
    if fresh:
        target.touch(mode=0o600)
    connection = sqlite3.connect(target)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(SCHEMA)
    return connection


def _account_for(db: sqlite3.Connection, email: str, name: str, consent_version: str) -> str:
    """The account that owns this email, created if it is new.

    **Matched on email, lowercased**, because that is the only handle a buyer gives you twice and
    "A@example.com" and "a@example.com" are one person to every mail server that will ever
    deliver to them. A second purchase by the same person must land on the same account or the
    issue counts D5 monitors are counting the wrong thing.
    """
    key = email.strip().lower()
    # ⚠ `forgotten_at IS NULL` IS A SECOND LOCK ON A DOOR THAT IS ALREADY LOCKED, and that is
    # recorded rather than removed. `forget` NULLs the email, so a forgotten row can never match
    # this comparison anyway - a mutation dropping this clause survives, because no test can
    # distinguish it. It stays because the two mechanisms protect against different mistakes: the
    # NULL is what erasure MEANS, and this is what stops a later `forget` that kept the address
    # for some reason from silently re-attaching a name to an erased account.
    found = db.execute(
        "SELECT account_id FROM accounts WHERE lower(email) = ? AND forgotten_at IS NULL", (key,)
    ).fetchone()
    if found:
        return str(found["account_id"])

    account_id = str(uuid.uuid4())
    db.execute(
        "INSERT INTO accounts (account_id, email, name, consent_at, consent_text_version,"
        " created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (account_id, email.strip(), name.strip(), now(), consent_version, now()),
    )
    return account_id


def issue(db: sqlite3.Connection, args: argparse.Namespace) -> tuple[str, sqlite3.Row]:
    """Record a purchase and mint its first token.

    ⚠ **A SECOND `issue` AGAINST THE SAME ORDER REFERENCE IS REFUSED, NOT SILENTLY TREATED AS A
    RE-ISSUE**, and the reason is the failure mode rather than tidiness. The realistic mistake is
    pasting the *previous* order reference while issuing for a new buyer. Turning that into a
    re-issue would mint a token carrying **the previous customer's name and email**, print it as
    a success, and the operator would send someone else's identity to a stranger - signed, and
    unrevokable, because nothing in this design ever revokes. A refusal costs one command and
    names the licence that already holds the reference.

    The order reference is the idempotency key because it is the only value that comes from
    outside and identifies one payment. `UNIQUE` on the column is what enforces it; this check
    exists to turn an `IntegrityError` into a sentence.
    """
    existing = db.execute(
        "SELECT licence_id FROM licences WHERE order_ref = ?", (args.order_ref,)
    ).fetchone()
    if existing:
        msg = (
            f"order reference {args.order_ref!r} already belongs to licence "
            f"{existing['licence_id']}.\n"
            "If this is the same purchase and the customer needs their file again, that is a "
            "re-issue:\n"
            f"    licences.py reissue --order-ref {args.order_ref} --key ...\n"
            "If this is a different purchase, the reference is wrong - check it before issuing, "
            "because issuing here would put the other customer's name and email in a signed "
            "token."
        )
        raise StoreError(msg)

    check_covers_through(args.covers_through)
    account_id = _account_for(db, args.email, args.name, args.consent_version)
    licence_id = str(uuid.uuid4())
    db.execute(
        "INSERT INTO licences (licence_id, account_id, order_ref, edition, covers_through,"
        " updates_until, purchased_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            licence_id,
            account_id,
            args.order_ref,
            args.edition,
            args.covers_through,
            args.updates_until,
            now(),
        ),
    )
    return mint_for(db, licence_id, args, reason="purchase")


def check_covers_through(epoch: int) -> None:
    """Refuse an entitlement for an epoch that does not exist. `DECISIONS.md` D16 §4.

    ⚠ **A typo here is expensive in a way nothing downstream notices.** `--covers-through 2`
    against a product that has only opened epoch 1 mints a signed, perpetual, unrevokable token
    granting an entitlement that was never sold - and it verifies, because `verify_token` asks
    whether the ceiling *reaches* this build and a ceiling from the future reaches everything.
    The customer is covered for years they did not pay for, and nothing ever reports it.
    `0` is the mirror image: a licence that is lapsed the day it is issued.

    `EPOCH_OPENED_AT` is the table `test_the_entitlement_epoch_cannot_move_by_accident.py`
    already holds to a release, so there is one answer to "which epochs exist" rather than two.
    """
    valid = sorted(EPOCH_OPENED_AT)
    if epoch not in EPOCH_OPENED_AT:
        msg = (
            f"--covers-through {epoch} names an entitlement period that does not exist.\n"
            f"This build knows epochs {valid[0]}-{valid[-1]} "
            f"(opened at {', '.join(f'{k}: {EPOCH_OPENED_AT[k]}' for k in valid)}).\n"
            "An epoch is opened by adding a row to licence.EPOCH_OPENED_AT in a minor or major "
            "release - never here, and never by issuing against it."
        )
        raise StoreError(msg)


def mint_for(
    db: sqlite3.Connection, licence_id: str, args: argparse.Namespace, *, reason: str
) -> tuple[str, sqlite3.Row]:
    """Sign a token for an **existing** licence row and record the issue.

    ⚠ **THE SINGLE PLACE A TOKEN IS MINTED AGAINST THE STORE, and that is what makes re-issue
    safe.** `sub` and `lic` are read from the row rather than generated, so a re-issue cannot
    quietly become a new purchase - which would break the issue counts D5 monitors, orphan the
    customer's history, and leave two licences for one payment.
    """
    row = licence_row(db, licence_id=licence_id)
    signing_key = load_signing_key(Path(args.key))
    fields: dict[str, object] = {
        "v": PAYLOAD_VERSION,
        "kid": args.kid,
        "sub": row["account_id"],
        "lic": row["licence_id"],
        "name": row["name"] or "",
        "email": row["email"] or "",
        "edition": row["edition"],
        "covers_through": row["covers_through"],
        "issued_at": datetime.now(tz=UTC).date().isoformat(),
        "updates_until": row["updates_until"],
    }
    token = sign_payload(signing_key, fields)
    db.execute(
        "INSERT INTO issues (licence_id, kid, issued_at, reason, name_at_issue, email_at_issue)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        (row["licence_id"], args.kid, now(), reason, row["name"], row["email"]),
    )
    return token, row


def licence_row(
    db: sqlite3.Connection, *, licence_id: str | None = None, order_ref: str | None = None
) -> sqlite3.Row:
    """One licence with its account joined, by id or by order reference.

    ⚠ **Refuses when neither is given**, rather than falling through to `WHERE order_ref = NULL`
    and reporting "no licence with order_ref None". The CLI already refuses this at
    `parser.error`, which is argparse's job and a better message; this is the store declining to
    have an undefined branch, because the next caller may not be the CLI.
    """
    if not (licence_id or order_ref):
        msg = "a licence must be named by its id or by its order reference"
        raise StoreError(msg)
    column, value = ("licence_id", licence_id) if licence_id else ("order_ref", order_ref)
    row = db.execute(
        "SELECT l.*, a.email, a.name, a.forgotten_at FROM licences l"
        f" JOIN accounts a ON a.account_id = l.account_id WHERE l.{column} = ?",
        (value,),
    ).fetchone()
    if row is None:
        msg = f"no licence with {column} {value!r}"
        raise StoreError(msg)
    assert isinstance(row, sqlite3.Row)
    return row


def issues_for(db: sqlite3.Connection, licence_id: str) -> list[sqlite3.Row]:
    """Every issue against one licence, oldest first."""
    return list(
        db.execute(
            "SELECT * FROM issues WHERE licence_id = ? ORDER BY issue_id", (licence_id,)
        ).fetchall()
    )


def issues_by_licence(
    db: sqlite3.Connection, licence_ids: Sequence[str]
) -> dict[str, list[sqlite3.Row]]:
    """Issues for many licences, in **one** query.

    ⚠ **This replaced a query inside a loop**, and the reason is structural rather than a speed
    claim. At this size the loop was free - a handful of licences, tens of issues, a local SQLite
    file - and adding an index or a cache here would be ceremony. What is not free is the SHAPE:
    a query inside a loop is the thing that stops being free later without anybody changing it,
    and it is the pattern a reader copies into somewhere it matters.

    `IN (?, ?, ...)` with a generated placeholder list because SQLite has no array binding.
    SQLITE_MAX_VARIABLE_NUMBER is 32,766 on any build this decade, and the caller is a
    maintainer's own customer list, so the bound is stated rather than defended against.
    """
    if not licence_ids:
        return {}
    holes = ", ".join("?" for _ in licence_ids)
    grouped: dict[str, list[sqlite3.Row]] = {one: [] for one in licence_ids}
    for row in db.execute(
        f"SELECT * FROM issues WHERE licence_id IN ({holes}) ORDER BY issue_id",
        tuple(licence_ids),
    ):
        grouped[str(row["licence_id"])].append(row)
    return grouped


def forget(db: sqlite3.Connection, account_id: str) -> int:
    """A deletion request. `DECISIONS.md` D5's GDPR duties, and Q1743's shape.

    **Erased:** name, email, and the name and email recorded against every past issue.
    **Retained:** `licence_id`, `order_ref`, the entitlement and the dates - a tax record, kept
    on legal obligation rather than on consent, which is why a deletion request does not reach
    it. The account becomes a pseudonymous row.

    ⚠ **WHAT THIS CANNOT REACH, and the customer must be told before they buy rather than
    during a deletion request: the token already on their disk contains their name and email,
    and nothing here can erase it.** That is a direct consequence of D6 §2's share-deterrent
    decision, and it is defensible - it is their copy of their own data - only if it was said
    plainly up front.
    """
    if db.execute("SELECT 1 FROM accounts WHERE account_id = ?", (account_id,)).fetchone() is None:
        msg = f"no account {account_id!r}"
        raise StoreError(msg)
    db.execute(
        "UPDATE accounts SET email = NULL, name = NULL, forgotten_at = ? WHERE account_id = ?",
        (now(), account_id),
    )
    cursor = db.execute(
        "UPDATE issues SET name_at_issue = NULL, email_at_issue = NULL WHERE licence_id IN"
        " (SELECT licence_id FROM licences WHERE account_id = ?)",
        (account_id,),
    )
    return int(cursor.rowcount)


def whois(
    db: sqlite3.Connection, token: str
) -> tuple[LicenceState, sqlite3.Row | None, dict[str, str]]:
    """Who does this token belong to. **The first thing a support conversation needs.**

    Verified rather than merely decoded: a token that does not verify is the customer's actual
    problem, and reading its payload anyway would answer a question about a file that this
    product would refuse. The payload is returned alongside so the operator can see what the
    *token* claims even when the store disagrees - which is exactly the case after an email
    correction, where the old file says the old address for ever.
    """
    result = verify_token(token)
    # ⚠ ONE CONDITION, NOT TWO. This read `state is UNREADABLE or payload is None` and a mutation
    # removing the first clause SURVIVED - because `verify_token` never returns a payload with an
    # UNREADABLE state, so the clause could not change an outcome and no test could distinguish
    # it. Dead code that reads as a safety check is worse than none: it invites the next person
    # to trust a check that never fires. The invariant it was restating belongs to `licence.py`,
    # which is where it is enforced.
    if result.payload is None:
        return result.state, None, {}
    payload = result.payload
    try:
        row = licence_row(db, licence_id=payload.licence)
    except StoreError:
        row = None
    return result.state, row, {"name": payload.name, "email": payload.email, "kid": payload.kid}


# --- the command line ---------------------------------------------------------------------------


#: What may appear in a filename built from an order reference. Everything else becomes `-`.
_FILENAME_SAFE = re.compile(r"[^A-Za-z0-9._-]+")


def token_filename(order_ref: str) -> str:
    """What the customer's file is called: their order reference, sanitised.

    ⚠ **THE SANITISE IS NOT COSMETIC.** The order reference comes from whatever the operator
    types or pastes out of a processor's dashboard, and it was interpolated straight into a path.
    A reference containing `/` or `..` writes the token **outside `--out`** - silently, to a path
    nobody chose, possibly over something. It is a support tool run on a maintainer's own laptop
    rather than a public surface, so this is carelessness rather than a vulnerability; it is
    still the kind of line a reviewer stops on, and the fix is four characters of regex.

    The reference stays in the name because a support mail quoting a filename is already quoting
    the key that finds them - so the sanitised form is kept close to the original rather than
    hashed into something unreadable.
    """
    safe = _FILENAME_SAFE.sub("-", order_ref).strip("-.") or "unknown"
    return f"truestill-licence-{safe}.token"


def write_token_file(token: str, order_ref: str, out_dir: Path) -> Path:
    """Put the token where the operator can attach it, and return where that was.

    Split from the printing so a caller - and a test - can ask *what was written* without
    capturing stdout to find out. The two were one function and it did two jobs: a command that
    both produces an artifact and narrates it has no seam to assert against.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / token_filename(order_ref)
    target.write_text(token + "\n", encoding="utf-8")
    return target


def _hand_over(token: str, row: sqlite3.Row, out_dir: Path, note: str) -> None:
    """Print what to send, having written it.

    The file is written rather than printed alone because the thing the customer needs is a
    FILE, and a token pasted out of a terminal is one wrapped line away from being unusable -
    which is the failure JetBrains' own documentation warns about for its offline codes.
    """
    target = write_token_file(token, str(row["order_ref"]), out_dir)
    print(f"{note}\n")
    print(f"  licence   {row['licence_id']}")
    print(f"  account   {row['account_id']}")
    print(f"  order     {row['order_ref']}")
    print(f"  for       {row['name']} <{row['email']}>")
    print(
        f"  edition   {row['edition']}, covers epoch {row['covers_through']}, "
        f"updates until {row['updates_until']}"
    )
    print(f"\n  file      {target}")
    print(
        "\nSend that file. Tell them: keep a copy with your backups - this file IS the licence,"
        "\nand truestill can read it with no internet connection."
    )


def cmd_issue(args: argparse.Namespace) -> int:
    with opened() as db:
        token, row = issue(db, args)
        _hand_over(token, row, Path(args.out), "issued a new licence")
    return 0


def cmd_reissue(args: argparse.Namespace) -> int:
    with opened() as db:
        row = licence_row(db, order_ref=args.order_ref, licence_id=args.licence)
        before = len(issues_for(db, row["licence_id"]))
        token, row = mint_for(db, row["licence_id"], args, reason="reissue")
        _hand_over(
            token,
            row,
            Path(args.out),
            f"re-issued the SAME licence - issue {before + 1} of this licence, not a new purchase",
        )
    return 0


def cmd_correct_email(args: argparse.Namespace) -> int:
    """Correct a typo in a buyer's email and re-issue against the same licence.

    ⚠ **THE OLD TOKEN CANNOT BE CORRECTED AND IS NOT REVOKED.** The email is inside the signed
    payload (D6 §2), so the only fix is a new signature over corrected fields - and the file the
    customer already has keeps verifying, for ever, saying the wrong address. Nothing in this
    design revokes anything; that is D5's no-phone-home guarantee working exactly as intended and
    costing exactly this. So the instruction to delete the old file is printed as part of the
    correction rather than left to the operator to remember.
    """
    with opened() as db:
        row = licence_row(db, order_ref=args.order_ref, licence_id=args.licence)
        db.execute(
            "UPDATE accounts SET email = ? WHERE account_id = ?", (args.email, row["account_id"])
        )
        token, row = mint_for(db, row["licence_id"], args, reason="email-correction")
        _hand_over(token, row, Path(args.out), "corrected the email and re-issued")
        print(
            "\n⚠ The token they already have still verifies and still says the old address."
            "\n  Nothing revokes it. Tell them to DELETE the old file and use this one."
        )
    return 0


def cmd_find(args: argparse.Namespace) -> int:
    with opened() as db:
        rows = db.execute(
            "SELECT l.*, a.email, a.name, a.forgotten_at FROM licences l"
            " JOIN accounts a ON a.account_id = l.account_id"
            " WHERE l.order_ref = :q OR l.licence_id = :q OR a.account_id = :q"
            " OR lower(a.email) LIKE :like OR lower(a.name) LIKE :like"
            " ORDER BY l.purchased_at",
            {"q": args.query, "like": f"%{args.query.strip().lower()}%"},
        ).fetchall()
        if not rows:
            print(f"nothing matches {args.query!r}")
            return 1
        issues = issues_by_licence(db, [str(row["licence_id"]) for row in rows])
        for row in rows:
            issued = issues[str(row["licence_id"])]
            who = f"{row['name']} <{row['email']}>" if row["email"] else "(forgotten)"
            print(f"{row['order_ref']}  {who}")
            print(f"  licence {row['licence_id']}  account {row['account_id']}")
            print(
                f"  {row['edition']}, epoch {row['covers_through']}, "
                f"updates until {row['updates_until']}, bought {row['purchased_at']}"
            )
            # The COUNT is what D5 asks to monitor; the list is what a support conversation
            # needs, because "four re-issues in a week" and "four over three years" are the
            # same number and different situations.
            print(f"  issued {len(issued)} time(s):")
            for one in issued:
                print(f"    {one['issued_at']}  {one['reason']}  kid={one['kid']}")
    return 0


def cmd_whois(args: argparse.Namespace) -> int:
    # ⚠ `errors="replace"`, because a customer sends whatever they have. A screenshot saved as
    # `.token` raises `UnicodeDecodeError` - a `ValueError` - and `main` printed its decode
    # message instead of this command's own "cannot read that file, send the file itself". The
    # bytes cannot be a token either way; replacing lets that answer come from the verifier
    # rather than from the codec, which is the difference between an operator being told what to
    # do and being shown a stack of jargon.
    token = Path(args.token).expanduser().read_text(encoding="utf-8", errors="replace")
    with opened() as db:
        state, row, claimed = whois(db, token)
        print(f"the token verifies as: {state}")
        if row is None and not claimed:
            print(
                "\nThis build cannot read that file at all. Either it was not signed by a key"
                "\nthis checkout ships, or it is damaged. Ask them to send the file itself."
            )
            return 1
        print(f"  the token says   {claimed['name']} <{claimed['email']}>  (kid {claimed['kid']})")
        if row is None:
            print(
                "\n⚠ It verifies and this store has no such licence. It was signed by a key we"
                "\n  hold but issued from a different store - or this store has been restored"
                "\n  from a backup older than the issue."
            )
            return 1
        who = f"{row['name']} <{row['email']}>" if row["email"] else "(forgotten)"
        print(f"  the store says   {who}")
        print(f"  order {row['order_ref']}, licence {row['licence_id']}")
        if row["email"] and claimed["email"].lower() != str(row["email"]).lower():
            print(
                "\n⚠ The token and the store disagree about the address. That is what an email"
                "\n  correction leaves behind: the old file keeps saying the old address for"
                "\n  ever. Check `find` for a later issue and send them that one."
            )
    return 0


def cmd_forget(args: argparse.Namespace) -> int:
    with opened() as db:
        touched = forget(db, args.account)
    print(f"erased the name and email on account {args.account} and on {touched} past issue(s).")
    print("Retained: licence id, order reference and the dates - that is a tax record.")
    print(
        "\n⚠ The token on their disk still contains their name and email. Nothing here can"
        "\n  reach it, and nothing revokes it."
    )
    return 0


def _signing_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--key", required=True, help="the private signing key")
    parser.add_argument("--kid", default="k1", help="key id recorded in the token (default: k1)")
    parser.add_argument("--out", default=".", help="where to write the token file (default: .)")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__.split("\n", 1)[0],
        epilog=(
            "THE STORE AND THE SIGNING KEY ARE UNRECOVERABLE IF LOST. Back up "
            f"{DEFAULT_STORE.parent} somewhere off this machine. Without the key no licence can "
            "ever be issued again that shipped builds accept; without the store every customer's "
            "identity, entitlement and history is gone while their tokens keep working for ever."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    one = sub.add_parser("issue", help="record a purchase and mint its first token")
    one.add_argument("--name", required=True)
    one.add_argument("--email", required=True)
    one.add_argument("--order-ref", required=True, help="the processor's reference for this sale")
    one.add_argument("--edition", default="pro")
    one.add_argument("--covers-through", type=int, default=BUILD_EPOCH)
    one.add_argument("--updates-until", required=True, help="ISO date shown to the buyer")
    one.add_argument("--consent-version", default=DEFAULT_CONSENT_VERSION)
    _signing_args(one)
    one.set_defaults(func=cmd_issue)

    again = sub.add_parser("reissue", help="mint another token for an EXISTING licence")
    again.add_argument("--order-ref")
    again.add_argument("--licence")
    _signing_args(again)
    again.set_defaults(func=cmd_reissue)

    fix = sub.add_parser("correct-email", help="fix a typo and re-issue the same licence")
    fix.add_argument("--order-ref")
    fix.add_argument("--licence")
    fix.add_argument("--email", required=True)
    _signing_args(fix)
    fix.set_defaults(func=cmd_correct_email)

    look = sub.add_parser("find", help="by email, name, order reference, licence or account id")
    look.add_argument("query")
    look.set_defaults(func=cmd_find)

    who = sub.add_parser("whois", help="who does this token file belong to")
    who.add_argument("token")
    who.set_defaults(func=cmd_whois)

    gone = sub.add_parser("forget", help="a deletion request: erase the person, keep the record")
    gone.add_argument("--account", required=True)
    gone.set_defaults(func=cmd_forget)

    args = parser.parse_args(argv)
    wants_a_licence = args.command in {"reissue", "correct-email"}
    if wants_a_licence and not (args.order_ref or args.licence):
        parser.error("one of --order-ref or --licence is required")
    try:
        return int(args.func(args))
    except StoreError as exc:
        # Already worded for a person by whoever raised it - printed as the sentence it is.
        print(str(exc), file=sys.stderr)
        return 2
    except ValueError as exc:
        # `load_signing_key` is the one source of these and it words its own message. Narrowed
        # from a blanket `(StoreError, ValueError, OSError)`, which would also have swallowed a
        # programming error and printed it as advice.
        print(str(exc), file=sys.stderr)
        return 2
    except OSError as exc:
        # ⚠ The only path here with NO wording of its own, so the address is added: a bare
        # "Permission denied" tells the operator nothing about which of the store, the key and
        # the output directory refused them.
        print(
            f"{args.command}: {exc.strerror or exc} ({exc.filename or 'no path reported'})",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
