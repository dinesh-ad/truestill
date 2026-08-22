"""A home directory that will not take a write costs the way-in file, not the app. `(aeo)`

`session_link.write` does `unlink` -> `touch(mode=0o600)` -> `write_text` on the launch path, none
of it guarded, and `__main__` called it before serving anything. A full or read-only home directory
therefore ended startup in an interpreter stack trace - on the worst day a user could meet it, and
with no way to tell what had happened.

⚠ **The decision `(aeo)` left open was "stop the launch or degrade", and the module had already
answered it twice.** `session_link`'s docstring rules that when a filesystem discards the mode the
file is still written, because *"warning beats refusing"*; `session_link.clear` is documented
*"never raises: failing to clean up must not take the app down with it"*. The server **is** the
product. This file is one of two ways in and the browser is the other, so losing it costs a
fallback rather than the app.

**What must not regress, and it is the trap the fix itself creates.** Once the write is guarded,
`link.path` names a file that was never written - and the browser fallback said *"The address is
in {path}"*. Sending someone to a path that does not exist is `(aey)`'s failure introduced by the
repair, so the address is given directly instead.
"""

from __future__ import annotations

import errno
from pathlib import Path

import pytest
from app_support import ImmediateThread, StubServer
from truestill_app import __main__ as launcher
from truestill_app import session_link
from truestill_app.__main__ import main
from truestill_core.drive_unwritable import explain_unwritable_drive, explain_unwritable_folder

_URL = "http://127.0.0.1:8823/?t=abc"


@pytest.fixture
def _deterministic_launch(monkeypatch: pytest.MonkeyPatch) -> None:
    """No real server, no real thread - the same harness `test_session_link.py` uses."""
    StubServer.instances.clear()
    monkeypatch.setattr(launcher.uvicorn, "Server", StubServer)
    monkeypatch.setattr(launcher.threading, "Thread", ImmediateThread)


def _refusing(code: int) -> OSError:
    return OSError(code, "synthetic")


def test_the_folder_wording_names_no_drive() -> None:
    """⚠ The whole reason a second phrasing exists rather than reusing the drive's.

    The launch path writes into the user's own data directory, which they never chose and cannot
    swap. *"The drive is read-only"* names a thing that is not in the story.
    """
    for code in (errno.EROFS, errno.EACCES, errno.ENOSPC, errno.ENOENT, errno.EIO):
        folder = explain_unwritable_folder(_refusing(code))
        assert "drive" not in folder, f"errno {code} still talks about a drive: {folder!r}"


def test_the_drive_wording_is_untouched() -> None:
    """The split must not move the sentences two other callers and an e2e test assert on."""
    assert (
        explain_unwritable_drive(_refusing(errno.EROFS))
        == "the drive is read-only, or this account cannot write to it"
    )
    assert (
        explain_unwritable_drive(_refusing(errno.ENOSPC)) == "there is no space left on the drive"
    )


def test_a_quota_and_a_full_disk_still_get_opposite_advice() -> None:
    """`(aek)`'s finding, carried across the split: space may exist and this account may not."""
    quota = getattr(errno, "EDQUOT", None)
    if quota is None:  # pragma: no cover - platform without EDQUOT
        pytest.skip("EDQUOT is not defined on this platform")
    assert explain_unwritable_folder(_refusing(quota)) != explain_unwritable_folder(
        _refusing(errno.ENOSPC)
    )


def test_the_browser_fallback_never_names_a_file_that_was_not_written(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """⚠ The defect the guard would otherwise have introduced.

    With no file, the address itself is the only true thing to say. `open_browser` is forced to
    fail because that is the only branch that says anything at all.
    """
    monkeypatch.setattr(session_link, "open_browser", lambda _url: False)

    launcher._attempt_browser(_URL, None)

    err = capsys.readouterr().err
    assert _URL in err, f"with no file written, the address must be given directly:\n{err}"
    assert "is in" not in err, "there is no file to point at, so nothing may be pointed at"


def test_the_fallback_still_names_the_file_when_there_is_one(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The unchanged half. A file that exists is still the better answer than a long URL."""
    monkeypatch.setattr(session_link, "open_browser", lambda _url: False)
    written = tmp_path / "session-url.txt"

    launcher._attempt_browser(_URL, written)

    err = capsys.readouterr().err
    assert str(written) in err, f"the file was written and must still be named:\n{err}"


def test_write_still_raises_so_the_launch_path_owns_the_policy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """⚠ The guard belongs at the launch path, and this pins that it was not buried in the module.

    `session_link.write` stays *"do it or raise"*: it is what every privacy test asserts against,
    and whether a failure is fatal is a **launch** question, not a file-format one. Swallowing the
    error inside `write` would have given it a second, silent contract.
    """
    target = tmp_path / "nope" / "session-url.txt"
    monkeypatch.setattr(session_link, "path", lambda: target)

    def _full(_self: Path, **_kwargs: object) -> None:
        raise OSError(errno.ENOSPC, "No space left on device")

    monkeypatch.setattr(Path, "touch", _full)

    with pytest.raises(OSError, match="No space left on device"):
        session_link.write(_URL)


@pytest.mark.usefixtures("_deterministic_launch")
def test_a_home_directory_that_refuses_the_write_still_serves(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """⚠ **The fix, end to end.** Before this, `main` died here with a stack trace.

    A full home disk is staged at the one call the launch makes, so every step around it - the
    signal handlers, the browser thread, the server - runs exactly as it does in life.
    """
    opened: list[str] = []
    monkeypatch.setattr(session_link, "open_browser", lambda url: bool(opened.append(url)))
    monkeypatch.setattr(
        session_link,
        "write",
        lambda _url: (_ for _ in ()).throw(OSError(errno.ENOSPC, "No space left on device")),
    )

    code = main(["--db", str(tmp_path / "c.sqlite")])

    assert code == 0, "a home directory that cannot take the way-in file must not fail the launch"
    assert opened, "the browser is the other way in and must still be attempted"
    err = capsys.readouterr().err
    assert "no disk space left" in err, f"the reason must be said, in words:\n{err}"
    assert "Errno" not in err, f"§9: a sentence, never an errno:\n{err}"
    assert "drive" not in err, f"there is no drive in this story:\n{err}"
    # ⚠ The WIRING, not just the renderer, and scoped to the BROWSER line - the path belongs in
    # the "could not save" line above and asserting over the whole stream measures that instead.
    # A mutation passing `session_link.path()` through regardless survived until this existed:
    # the `None` branch was written, tested in isolation, and never reached from `main`. §4's
    # sixtieth member exactly.
    fallback = next(line for line in err.splitlines() if "Could not open a browser" in line)
    assert str(session_link.path()) not in fallback, (
        f"the launch pointed at a file it could not write:\n{fallback}"
    )
    assert "The address is:" in fallback, (
        f"with no file, the address itself must be given:\n{fallback}"
    )
