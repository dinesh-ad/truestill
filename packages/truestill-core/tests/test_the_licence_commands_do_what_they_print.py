"""Every `licences.py` command through its real entry point, asserting what it PRINTS and WRITES.

⚠ **THE LAYER THIS COVERS HAD NOTHING, AND IT IS THE LAYER THE MAINTAINER USES WITH A CUSTOMER
WAITING.** The store's own tests call `issue`, `mint_for` and `forget` directly, so argument
parsing, the printed instructions and the file that actually gets attached to an email were
verified by one hand-run and nothing else.

**A return code is not an assertion here.** A command that succeeded silently and wrote nowhere
would satisfy `assert main(...) == 0` perfectly, and the operator would send an empty mail. So
every test below asserts at least one of: the bytes on disk, the path named in the output, or the
sentence the operator is meant to act on.

Everything runs against a store in the test's own `tmp_path` (`TRUESTILL_LICENCE_STORE`) and signs
with a throwaway key trusted for one test. No key and no customer record touches the tree.
"""

from __future__ import annotations

import sys
from pathlib import Path

import nacl.signing
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))

import licences
from truestill_core import licence as licence_module
from truestill_core.licence import LicenceState

KID = "cli-throwaway"


@pytest.fixture
def bench(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A store, a signing key, and an output directory - all inside this test.

    `monkeypatch.setenv` rather than a parameter: the point of these tests is the **real entry
    point**, and the real entry point resolves its own store. A test that passed a path in would
    be testing a function the operator never calls.
    """
    signer = nacl.signing.SigningKey.generate()
    key = tmp_path / "k.key"
    key.write_text(licence_module.b64url_encode(bytes(signer)) + "\n")
    monkeypatch.setitem(
        licence_module.PUBLIC_KEYS, KID, licence_module.b64url_encode(bytes(signer.verify_key))
    )
    monkeypatch.setenv(licences.STORE_ENV, str(tmp_path / "customers.db"))
    return tmp_path


def run(bench: Path, *argv: str) -> int:
    """`licences.py` as the shell invokes it, with the signing flags filled in."""
    signing = ["--key", str(bench / "k.key"), "--kid", KID, "--out", str(bench / "out")]
    needs_key = argv[0] in {"issue", "reissue", "correct-email"}
    return licences.main([*argv, *(signing if needs_key else [])])


def issue(bench: Path, **overrides: str) -> int:
    fields = {
        "--name": "Ada Lovelace",
        "--email": "ada@example.com",
        "--order-ref": "PAD-1",
        "--updates-until": "2027-09-11",
    }
    fields.update(overrides)
    flat = [part for pair in fields.items() for part in pair]
    return run(bench, "issue", *flat)


def token_at(bench: Path, order_ref: str = "PAD-1") -> Path:
    return bench / "out" / licences.token_filename(order_ref)


# --- issue ---------------------------------------------------------------------------------


def test_issue_writes_a_token_file_and_names_it_in_the_output(
    bench: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """**The whole point of the command: a file the operator can attach, and its path.**

    The exit code is asserted last and is the weakest of the three claims here. What matters is
    that a file exists, that it verifies, and that the output tells the operator where it is -
    a command that succeeded and wrote nowhere would pass a returncode check and waste a
    customer's afternoon.
    """
    assert issue(bench) == 0
    printed = capsys.readouterr().out

    written = token_at(bench)
    assert written.is_file(), "issue succeeded and wrote no token"
    assert licence_module.verify_token(written.read_text()).state is LicenceState.ACTIVE
    assert str(written) in printed, "the operator is not told where the file is"
    assert "Ada Lovelace <ada@example.com>" in printed
    assert "keep a copy with your backups" in printed


def test_issue_prints_the_identifiers_a_support_conversation_will_need(
    bench: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The licence and account ids, printed at the one moment they exist and nowhere else yet.

    Without them the operator's only handle on a fresh sale is the order reference, which is the
    one value that can be mistyped and is the one a customer will not quote.
    """
    assert issue(bench) == 0
    printed = capsys.readouterr().out

    with licences.opened() as db:
        row = licences.licence_row(db, order_ref="PAD-1")

    assert row["licence_id"] in printed
    assert row["account_id"] in printed
    assert "PAD-1" in printed


def test_issue_refuses_a_duplicate_order_reference_and_writes_nothing(
    bench: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The refusal, through the entry point, with the second customer's file **absent**.

    Asserting the exit code alone would miss the failure that matters: a refusal that still wrote
    a token would leave a file on disk that an operator might attach anyway.
    """
    assert issue(bench) == 0
    capsys.readouterr()

    assert issue(bench, **{"--name": "Someone Else", "--email": "e@x.com"}) == 2
    refused = capsys.readouterr().err

    assert "already belongs to licence" in refused
    assert "reissue --order-ref PAD-1" in refused
    assert licence_module.verify_token(token_at(bench).read_text()).payload.name == "Ada Lovelace"


def test_issue_refuses_an_entitlement_period_that_does_not_exist(
    bench: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`--covers-through` against an epoch nobody opened. `DECISIONS.md` D16 §4.

    The message must name the valid range, because the operator's next move is to find the right
    number and a refusal that does not say what is right sends them to read source code.
    """
    assert issue(bench, **{"--covers-through": "99"}) == 2
    refused = capsys.readouterr().err

    assert "does not exist" in refused
    assert "epochs 1-1" in refused
    assert not token_at(bench).exists(), "a refused issue still wrote a token"


# --- reissue -------------------------------------------------------------------------------


def test_reissue_writes_the_file_again_and_says_it_is_not_a_new_purchase(
    bench: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """⚠ **The output is asserted because the operator reads it to a customer.**

    "issue 2 of this licence, not a new purchase" is the sentence that stops somebody concluding
    they have been charged twice, and it is the only place that distinction is visible at the
    moment it is needed.
    """
    assert issue(bench) == 0
    token_at(bench).unlink()
    capsys.readouterr()

    assert run(bench, "reissue", "--order-ref", "PAD-1") == 0
    printed = capsys.readouterr().out

    assert token_at(bench).is_file(), "reissue wrote no token"
    assert "not a new purchase" in printed
    assert "issue 2 of this licence" in printed


def test_reissue_without_a_licence_or_an_order_reference_is_refused(bench: Path) -> None:
    """argparse's job, asserted through the entry point: `parser.error` exits 2 rather than
    falling into the store with nothing to look up."""
    with pytest.raises(SystemExit) as stopped:
        run(bench, "reissue")

    assert stopped.value.code == 2


def test_reissue_for_a_customer_who_is_not_there_says_which_handle_failed(
    bench: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """An unknown order reference. The message quotes the value, because the realistic cause is
    a typo and the operator needs to see what the tool actually looked for."""
    assert run(bench, "reissue", "--order-ref", "PAD-NOPE") == 2

    assert "no licence with order_ref 'PAD-NOPE'" in capsys.readouterr().err


# --- correct-email -------------------------------------------------------------------------


def test_correct_email_rewrites_the_token_and_warns_about_the_old_one(
    bench: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """⚠ **The warning is the assertion with teeth.**

    The address is inside the signed payload, so the file the customer already holds keeps
    verifying for ever saying the typo. Nothing revokes it. If that instruction is missing, the
    customer keeps using the wrong file and the correction achieved nothing - so the sentence is
    asserted as carefully as the new token is.
    """
    assert issue(bench, **{"--email": "ada@exmaple.com"}) == 0
    capsys.readouterr()

    assert run(bench, "correct-email", "--order-ref", "PAD-1", "--email", "ada@example.com") == 0
    printed = capsys.readouterr().out

    corrected = licence_module.verify_token(token_at(bench).read_text()).payload
    assert corrected is not None
    assert corrected.email == "ada@example.com"
    assert "DELETE the old file" in printed
    assert "Nothing revokes it" in printed


# --- find ----------------------------------------------------------------------------------


def test_find_prints_the_customer_the_entitlement_and_the_issue_history(
    bench: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """One search, everything a support conversation opens with.

    The issue **history** rather than only a count, because "four re-issues this week" and "four
    over three years" are the same number and different situations.
    """
    assert issue(bench) == 0
    assert run(bench, "reissue", "--order-ref", "PAD-1") == 0
    capsys.readouterr()

    assert run(bench, "find", "ada@example.com") == 0
    printed = capsys.readouterr().out

    assert "PAD-1" in printed
    assert "Ada Lovelace <ada@example.com>" in printed
    assert "updates until 2027-09-11" in printed
    assert "issued 2 time(s)" in printed
    assert "purchase" in printed
    assert "reissue" in printed


def test_find_matches_a_partial_name_as_well_as_an_exact_handle(
    bench: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A support mail says "Ada", not a UUID. The cry-wolf half of the test above: a `find` that
    only ever matched exact ids would satisfy it and be useless in the situation it exists for."""
    assert issue(bench) == 0
    capsys.readouterr()

    assert run(bench, "find", "lovelace") == 0

    assert "PAD-1" in capsys.readouterr().out


def test_find_that_matches_nothing_says_so_and_exits_non_zero(
    bench: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Not-found is an outcome a script can branch on, and a sentence a person can read."""
    assert issue(bench) == 0
    capsys.readouterr()

    assert run(bench, "find", "nobody@example.com") == 1

    assert "nothing matches" in capsys.readouterr().out


# --- whois ---------------------------------------------------------------------------------


def test_whois_reads_the_file_and_reconciles_it_with_the_store(
    bench: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The first thing a support conversation needs: they send a file, you say who they are."""
    assert issue(bench) == 0
    capsys.readouterr()

    assert run(bench, "whois", str(token_at(bench))) == 0
    printed = capsys.readouterr().out

    assert "verifies as: active" in printed
    assert "the token says   Ada Lovelace <ada@example.com>" in printed
    assert "the store says   Ada Lovelace <ada@example.com>" in printed


def test_whois_flags_a_token_that_disagrees_with_the_store(
    bench: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """After an email correction the old file says the old address for ever.

    An operator holding two files needs to be told which is current, and told *why* they differ -
    otherwise the natural reading is that the store is wrong.
    """
    assert issue(bench, **{"--email": "ada@exmaple.com"}) == 0
    old = bench / "old.token"
    old.write_text(token_at(bench).read_text())
    assert run(bench, "correct-email", "--order-ref", "PAD-1", "--email", "ada@example.com") == 0
    capsys.readouterr()

    assert run(bench, "whois", str(old)) == 0
    printed = capsys.readouterr().out

    assert "ada@exmaple.com" in printed
    assert "disagree about the address" in printed


def test_whois_on_a_file_that_is_not_a_token_asks_for_the_file_itself(
    bench: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A customer pastes a token into a mail client and sends back something wrapped, or sends a
    screenshot saved as `.token`. The tool must not guess; it says it cannot read it and asks for
    the file, which is the only next step that works."""
    rubbish = bench / "not-a-token"
    rubbish.write_bytes(b"\xff\xd8\xff\xe0 a photograph, actually")

    assert run(bench, "whois", str(rubbish)) == 1
    printed = capsys.readouterr().out

    assert "cannot read that file" in printed
    assert "send the file itself" in printed


def test_whois_on_a_missing_file_names_the_path_rather_than_the_errno(
    bench: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """⚠ **The generic-error path, fixed and then asserted.**

    `main` caught `OSError` and printed `str(exc)`, which for a missing file is a bare "No such
    file or directory" - true, and silent about which of the store, the key and the token it
    meant. It now names the command and the path.
    """
    assert run(bench, "whois", str(bench / "gone.token")) == 2
    reported = capsys.readouterr().err

    assert "whois" in reported
    assert "gone.token" in reported


# --- forget --------------------------------------------------------------------------------


def test_forget_erases_the_person_and_says_what_it_could_not_reach(
    bench: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A deletion request, end to end, with the honest half printed.

    The token on the customer's disk still carries their name and email and nothing here can
    reach it. An operator who answers a deletion request without knowing that will tell somebody
    their data is gone when it is not.
    """
    assert issue(bench) == 0
    with licences.opened() as db:
        account = licences.licence_row(db, order_ref="PAD-1")["account_id"]
    capsys.readouterr()

    assert run(bench, "forget", "--account", account) == 0
    printed = capsys.readouterr().out

    assert "erased the name and email" in printed
    assert "that is a tax record" in printed
    assert "still contains their name and email" in printed

    capsys.readouterr()
    assert run(bench, "find", "PAD-1") == 0
    assert "(forgotten)" in capsys.readouterr().out


def test_forget_on_an_account_that_is_not_there_is_refused(
    bench: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """An account id typed by hand. Quoting the value back is what lets the operator see the
    typo, which is the only realistic cause."""
    assert run(bench, "forget", "--account", "not-an-account") == 2

    assert "no account 'not-an-account'" in capsys.readouterr().err


# --- the store itself ----------------------------------------------------------------------


def test_a_command_against_a_store_that_does_not_exist_yet_creates_it(bench: Path) -> None:
    """There is no `init`. The first `issue` on a new machine must work, because the alternative
    is a maintainer discovering a missing setup step with a customer waiting."""
    store = bench / "customers.db"
    assert not store.exists()

    assert issue(bench) == 0

    assert store.is_file()


def test_a_command_refuses_a_store_inside_a_checkout_before_touching_anything(
    bench: Path, monkeypatch: pytest.CaptureFixture[str], capsys: pytest.CaptureFixture[str]
) -> None:
    """The rule the tool rests on, through the entry point rather than through `store_path`.

    Asserted here as well as in the unit test because the refusal has to survive being wrapped by
    `main`'s exception handling - a `StoreError` swallowed into a traceback would still be a
    refusal, and would not look like one.
    """
    monkeypatch.setenv(licences.STORE_ENV, str(Path(__file__).resolve().parent / "leak.db"))

    assert issue(bench) == 2
    assert "git work tree" in capsys.readouterr().err
    assert not (Path(__file__).resolve().parent / "leak.db").exists()


def test_an_order_reference_cannot_steer_the_token_out_of_the_output_directory(
    bench: Path,
) -> None:
    """⚠ **The order reference is operator input and it was interpolated straight into a path.**

    `../` in a reference wrote the token outside `--out`, silently, to a path nobody chose. A
    support tool on a maintainer's laptop rather than a public surface, so this was carelessness
    rather than a vulnerability - and still the kind of line a reviewer stops on.
    """
    assert issue(bench, **{"--order-ref": "../../escaped"}) == 0

    written = list((bench / "out").glob("*.token"))
    assert len(written) == 1, written
    assert written[0].parent == bench / "out"
    assert not (bench.parent / "escaped.token").exists()
    assert ".." not in written[0].name
