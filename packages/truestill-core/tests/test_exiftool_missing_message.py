"""What a user is told when exiftool cannot be found, and why the message has two forms.

**The audience changed with `(aad)`.** Until installers existed, a missing exiftool meant a
developer had not run ``apt install`` yet, and ``"not found on PATH"`` told them everything.
A double-clicked desktop app has a different user and a different cause: exiftool ships *inside*
the application, so its absence means the **installation is broken**, and PATH is a concept that
user has no reason to know.

Both remain possible, so the message asks which situation this is - via
`binaries.is_bundled_install`, derived from truestill's own bundling contract rather than from
any bundler's marker - and answers accordingly:

* **packaged install** - something is wrong with the installation; reinstalling is the fix, and
  no terminal command is offered to someone who has no terminal open;
* **source checkout** - the per-platform install command, which is the actionable thing there.

Both forms must name the tool, say what truestill needed it *for*, and give a next action. A
message that names a missing binary without saying what it was doing leaves the user knowing a
word and nothing else.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from truestill_core.binaries import BIN_DIR_ENV
from truestill_core.exif import EXIFTOOL_BIN_ENV, ExiftoolMissingError, ensure_exiftool


def _nowhere(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """No exiftool anywhere: empty PATH, no bundle, no override."""
    monkeypatch.delenv(BIN_DIR_ENV, raising=False)
    monkeypatch.delenv(EXIFTOOL_BIN_ENV, raising=False)
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))


def test_it_raises_rather_than_returning_a_path_that_is_not_there(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _nowhere(monkeypatch, tmp_path)

    with pytest.raises(ExiftoolMissingError):
        ensure_exiftool()


def test_the_message_names_the_tool_and_what_it_was_needed_for(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Naming a binary without naming its job leaves the user knowing a word and nothing else."""
    _nowhere(monkeypatch, tmp_path)

    with pytest.raises(ExiftoolMissingError) as raised:
        ensure_exiftool()

    message = str(raised.value).lower()
    assert "exiftool" in message
    assert "date" in message or "photo" in message, f"no statement of purpose: {message}"


def test_a_packaged_install_is_told_its_installation_is_incomplete(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The (aad) case. exiftool ships inside the app, so its absence is a broken install.

    Offering ``sudo apt install`` to someone who double-clicked an icon is advice they cannot
    act on, about a cause that is not theirs.
    """
    _nowhere(monkeypatch, tmp_path)
    bundled = tmp_path / "bundled"
    bundled.mkdir()
    monkeypatch.setenv(BIN_DIR_ENV, str(bundled))

    with pytest.raises(ExiftoolMissingError) as raised:
        ensure_exiftool()

    message = str(raised.value).lower()
    assert "install" in message
    offered = [command for command in ("sudo", "apt", "brew") if command in message]
    assert not offered, f"terminal commands {offered} offered to a packaged install: {message}"


def test_a_source_checkout_is_told_how_to_install_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The developer case keeps the actionable command it always had."""
    _nowhere(monkeypatch, tmp_path)

    with pytest.raises(ExiftoolMissingError) as raised:
        ensure_exiftool()

    message = str(raised.value)
    assert "exiftool.org" in message or "apt" in message or "brew" in message, (
        f"no way to obtain it: {message}"
    )


def test_neither_message_is_a_traceback_fragment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ENGINEERING_STANDARD: user-facing errors are actionable sentences, not diagnostics."""
    _nowhere(monkeypatch, tmp_path)

    for bundled in (False, True):
        if bundled:
            (tmp_path / "b").mkdir(exist_ok=True)
            monkeypatch.setenv(BIN_DIR_ENV, str(tmp_path / "b"))
        with pytest.raises(ExiftoolMissingError) as raised:
            ensure_exiftool()
        message = str(raised.value)
        for jargon in ("Traceback", "shutil", "PATHEXT", "None", "subprocess"):
            assert jargon not in message, f"{jargon!r} leaked into a user-facing message"
        assert message.rstrip().endswith((".", ":")), "not a sentence"


def test_a_bundled_exiftool_is_used_when_present(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The whole point: a packaged app runs the exiftool it shipped with."""
    _nowhere(monkeypatch, tmp_path)
    bundled = tmp_path / "bundled"
    bundled.mkdir()
    if sys.platform == "win32":
        binary = bundled / "exiftool.exe"
        binary.write_bytes(b"MZ")
    else:
        binary = bundled / "exiftool"
        binary.write_text("#!/bin/sh\n")
        binary.chmod(0o755)
    monkeypatch.setenv(BIN_DIR_ENV, str(bundled))

    assert Path(ensure_exiftool()).parent == bundled


def test_an_explicit_override_is_honoured(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The escape hatch, at the surface that actually uses it."""
    _nowhere(monkeypatch, tmp_path)
    chosen = tmp_path / "my-exiftool"
    chosen.write_text("#!/bin/sh\n")
    chosen.chmod(0o755)
    monkeypatch.setenv(EXIFTOOL_BIN_ENV, str(chosen))

    assert ensure_exiftool() == str(chosen)
