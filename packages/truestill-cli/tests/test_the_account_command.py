"""`truestill account` - the CLI's only licence surface. `(akq)`

⚠ **THERE WAS NONE.** A terminal-only customer received a token file and had to discover, unaided,
that it belongs at `app_paths.licence_path()`. `scripts/licences.py` is the **maintainer's** tool,
lives outside the product, and `whois` is not theirs to run.

**Named for what the rail already calls it.** The app's surface is the account slot -
``aria-label="Account and licence"``, `/api/account`, `service/account.py` - and its activation
button reads *"Use this licence file"*. Inventing `licence`, `activate` or `register` would be a
second vocabulary for one idea, which §9 forbids and which `restore`/`recover`/`import` already
cost this product once.

**Two things only: see the state, and use a file.** Sign-out is deliberately absent - it deletes
the licence file, and the app spends a paragraph warning before it does. A one-line destructive
verb with no ceremony is worse than no verb, and the path is printed in every state.
"""

from __future__ import annotations

from pathlib import Path

import nacl.signing
import pytest
from truestill_cli.cli import _build_parser, main
from truestill_core import licence

_KID = "cli-account-throwaway"


@pytest.fixture(autouse=True)
def _own_data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TRUESTILL_DATA_DIR", str(tmp_path / "data"))


@pytest.fixture
def token(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    signer = nacl.signing.SigningKey.generate()
    monkeypatch.setitem(licence.PUBLIC_KEYS, _KID, licence.b64url_encode(bytes(signer.verify_key)))
    fields = {
        "v": licence.PAYLOAD_VERSION,
        "kid": _KID,
        "sub": "acc",
        "lic": "lic",
        "name": "Ada Lovelace",
        "email": "ada@example.com",
        "edition": "pro",
        "covers_through": licence.BUILD_EPOCH,
        "issued_at": "2026-09-15",
        "updates_until": "2027-09-15",
    }
    encoded = licence.encode_payload(fields)
    signed = signer.sign(licence.signing_input(encoded)).signature
    path = tmp_path / "bought.token"
    path.write_text(f"{encoded}.{licence.b64url_encode(signed)}", encoding="utf-8")
    return path


def test_an_unlicensed_install_says_what_it_is_and_what_it_has_left(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """ABSENT is what every new user is, so this is informational rather than an error."""
    assert main(["account"]) == 0
    out = capsys.readouterr().out

    assert "No licence" in out
    assert "1,000 of 1,000 left" in out, "a free install was not told what it has"
    # The path in every state: where to put one, where the one in use lives, what to delete.
    assert "licence.token" in out


def test_using_a_licence_file_activates_it(token: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """**The headline.** The same act as the app's *"Use this licence file"*, from a terminal."""
    assert main(["account", "--use-file", str(token)]) == 0
    out = capsys.readouterr().out

    assert "Ada Lovelace" in out
    assert "2027-09-15" in out
    # ⚠ **No allowance line for an entitlement** - a number that does not apply must not be shown,
    # and `account_summary` leaves it empty rather than writing "unlimited".
    assert "of 1,000 left" not in out, "an entitled install was shown a free-tier count"


def test_the_activation_persists_for_the_next_command(
    token: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Activation writes the file; it does not merely report on the one it was handed."""
    main(["account", "--use-file", str(token)])
    capsys.readouterr()

    assert main(["account"]) == 0
    assert "Ada Lovelace" in capsys.readouterr().out


def test_a_path_that_is_not_a_licence_is_refused_in_cores_own_words(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """⚠ **Core's sentence, not a second wording of it** (§9). The CLI and the app refuse the same
    mistake, so they must refuse it identically."""
    bad = tmp_path / "holiday.jpg"
    bad.write_text("not a token", encoding="utf-8")

    assert main(["account", "--use-file", str(bad)]) == 2
    assert "could not be read" in capsys.readouterr().err


def test_an_empty_path_is_refused_before_the_filesystem_is_touched(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """`Path("")` resolves to the working directory, which exists - so a blank argument would read
    as *"that file could not be read"* when the real answer is that nothing was chosen.
    `service/account.py` makes the same check for the same reason."""
    assert main(["account", "--use-file", "   "]) == 2
    assert "No path given" in capsys.readouterr().err


def test_the_command_offers_no_sign_out() -> None:
    """⚠ **Asserted absent, deliberately.** Sign-out deletes the licence file; the app warns in a
    paragraph before doing it. A CLI flag with no ceremony would be the weakest word in the
    product guarding one of its more surprising acts - `reclaim`'s rule."""
    account = _build_parser().parse_args(["account"])
    assert not hasattr(account, "sign_out"), "a destructive verb arrived without its ceremony"
