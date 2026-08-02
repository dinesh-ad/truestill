"""The session URL must be recoverable, because losing it makes a running app unreachable.

**The defect ((aad)).** The token is `secrets.token_urlsafe(32)`, minted per process, never
persisted, and printed once to a console a double-clicked app does not have. The entire path to
the app was ``webbrowser.open(url)`` **with its return value discarded**. When that fails - no
browser found, no ``DISPLAY`` on Linux - the app is running, listening, and unreachable, and
restarting mints a *different* token. There was no second chance.

**A file, not a tray icon or a notification.** Those are per-platform UI dependencies a
local-web app does not otherwise need, and would have to be bundled and signed. A file is
zero-dependency, identical on three platforms, and greppable when someone reports a problem.

**It is a credential.** It contains the token, so it is created with mode ``0600`` at open time
rather than chmod-ed afterwards - the latter leaves a window where the file exists readable by
others. Windows does not honour POSIX modes; there the protection is that the data directory
lives under the user's own profile, which is stated rather than glossed.

**Staleness is the interesting half.** Someone opening yesterday's link hits one of two cases:
a **dead port**, which gives a confusing browser error, or - worse - a **live port with a
different token**, which is an authentication failure on an app that *is* running and reads as
"broken" rather than "expired". So the file is removed on exit, and the token check answers a
stale link by naming the file. It names the *path*, never the current token: the whole point of
the token is that an unauthenticated request cannot learn it.
"""

from __future__ import annotations

import socket
import sys
from pathlib import Path

import pytest
from app_support import ImmediateThread, StubServer, release_sockets
from starlette.testclient import TestClient
from truestill_app import __main__ as entry
from truestill_app import session_link
from truestill_app.__main__ import main
from truestill_app.server import create_app


@pytest.fixture(autouse=True)
def _deterministic_launch(monkeypatch: pytest.MonkeyPatch) -> None:
    """No real server, and no real thread - see `app_support` for why both are stubbed."""
    StubServer.instances.clear()
    monkeypatch.setattr(entry.uvicorn, "Server", StubServer)
    monkeypatch.setattr(entry.threading, "Thread", ImmediateThread)


def test_the_url_file_is_written_before_the_browser_is_attempted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The ordering is the whole point: a failed open must still leave the file behind."""
    existed: list[bool] = []
    monkeypatch.setattr(
        session_link,
        "open_browser",
        lambda _url: existed.append(session_link.path().is_file()),
    )

    main(["--db", str(tmp_path / "c.sqlite")])

    assert existed == [True], "the browser was attempted before the URL was recoverable"


def test_the_file_holds_the_session_url_including_its_token(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A URL without the token is not a way in, which is the only thing this file is for.

    Read *during* the run, not after: the file is deliberately removed on exit, so asserting on
    it afterwards would only ever prove the cleanup works.
    """
    seen: dict[str, str] = {}

    def capture(url: str) -> bool:
        seen["url"] = url
        seen["file"] = session_link.path().read_text()
        return True

    monkeypatch.setattr(session_link, "open_browser", capture)

    main(["--db", str(tmp_path / "c.sqlite")])

    assert "token=" in seen["url"]
    assert seen["url"] in seen["file"]


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX file modes")
def test_the_file_is_readable_only_by_its_owner(tmp_path: Path) -> None:
    """It is a credential. 0600 is set at creation, not after, so there is no readable window."""
    link = session_link.write(f"http://127.0.0.1:1/?token=secret-{tmp_path.name}")

    assert link.path.stat().st_mode & 0o777 == 0o600
    assert link.private is True, "the mode took, so the file must not claim otherwise"


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX file modes")
def test_a_pre_existing_wider_file_is_narrowed_rather_than_written_into() -> None:
    """A mode is applied only when a file is CREATED, so writing over one keeps its old mode.

    A file left by an older build, or by a run under a different umask, would otherwise receive
    the token while staying group-readable - and every test that only checks a fresh write would
    still pass.
    """
    stale = session_link.path()
    stale.parent.mkdir(parents=True, exist_ok=True)
    stale.touch(mode=0o644)
    stale.write_text("an older session, world-readable")

    session_link.write("http://127.0.0.1:1/?token=secret")

    assert stale.stat().st_mode & 0o777 == 0o600


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX symlinks")
def test_a_symlink_at_the_path_is_replaced_not_written_through(tmp_path: Path) -> None:
    """Otherwise the token is written into whatever the link points at, at that file's mode."""
    victim = tmp_path / "victim.txt"
    victim.write_text("do not touch")
    link = session_link.path()
    link.parent.mkdir(parents=True, exist_ok=True)
    link.symlink_to(victim)

    session_link.write("http://127.0.0.1:1/?token=secret")

    assert victim.read_text() == "do not touch", "the token was written through the link"
    assert not link.is_symlink()
    assert "token=secret" in link.read_text()


def test_each_launch_replaces_the_file_rather_than_appending() -> None:
    """Two URLs in one file is two guesses. The newest session is the only true one."""
    session_link.write("http://127.0.0.1:1/?token=first")

    session_link.write("http://127.0.0.1:2/?token=second")

    body = session_link.path().read_text()
    assert "token=second" in body
    assert "token=first" not in body, f"the previous session's URL survived: {body}"


def test_the_first_line_is_the_url_so_it_can_be_used_without_parsing() -> None:
    """`head -1` should be enough for someone on the phone to a confused user."""
    url = "http://127.0.0.1:7357/?token=abc"

    session_link.write(url)

    assert session_link.path().read_text().splitlines()[0] == url


def test_the_file_is_removed_when_the_app_exits(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A file that outlives its process is a link that fails confusingly the next day."""
    monkeypatch.setattr(session_link, "open_browser", lambda url: True)  # noqa: ARG005

    main(["--db", str(tmp_path / "c.sqlite")])

    assert not session_link.path().exists(), "yesterday's URL was left on disk"


def test_the_file_is_removed_even_when_the_server_dies(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Crashes are exactly when a stale file would be left, so the cleanup cannot be on the
    happy path only."""

    class _Dying(StubServer):
        def run(self, sockets: list[socket.socket] | None = None, **_kwargs: object) -> None:
            release_sockets(sockets)
            raise KeyboardInterrupt

    monkeypatch.setattr(entry.uvicorn, "Server", _Dying)
    monkeypatch.setattr(session_link, "open_browser", lambda url: True)  # noqa: ARG005

    with pytest.raises(KeyboardInterrupt):
        main(["--db", str(tmp_path / "c.sqlite")])

    assert not session_link.path().exists()


def test_a_failed_browser_open_tells_the_user_where_the_url_is(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`webbrowser.open` returns False when it finds no browser; discarding that was the bug."""
    monkeypatch.setattr(session_link, "open_browser", lambda url: False)  # noqa: ARG005

    main(["--db", str(tmp_path / "c.sqlite")])

    out = capsys.readouterr()
    said = out.out + out.err
    assert str(session_link.path()) in said, f"the user was not told where to look: {said}"


# --- the stale link ---------------------------------------------------------------------------


def _client(tmp_path: Path, token: str) -> TestClient:
    app = create_app(token=token, db=tmp_path / "c.sqlite")
    return TestClient(app, headers={"host": "127.0.0.1:7357"})


def test_a_stale_link_is_told_it_is_stale_rather_than_rejected(tmp_path: Path) -> None:
    """The worse of the two staleness cases: a live app that answers an old link.

    A bare "bad token" on an app that is plainly running reads as broken software. Naming the
    file turns it into an expired link with a next step.
    """
    with _client(tmp_path, "current-token") as client:
        response = client.get("/?token=yesterdays-token")

    assert response.status_code == 403
    assert str(session_link.path()) in response.text


def test_the_stale_link_message_never_reveals_the_current_token(tmp_path: Path) -> None:
    """The security half. Handing the live token to an unauthenticated caller would make the
    token pointless - the message names a path only the local user can read, never the secret."""
    with _client(tmp_path, "current-token") as client:
        response = client.get("/?token=yesterdays-token")

    assert "current-token" not in response.text
