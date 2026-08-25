"""The browser is pointed at the app only once the app can answer - proven, not timed.

**The bug.** ``threading.Timer(0.5, ...)`` opened the browser half a second after being
*scheduled*, while ``uvicorn.run`` bound the socket afterwards on the main thread. A slow start
meant the browser arrived first and the user got a connection-refused page, which reads as
"broken" rather than "too early".

**The trap this commit exists to avoid.** The obvious fix - open the browser from uvicorn's
ASGI *startup* hook - is not a fix. Verified against uvicorn's source and by measurement:
``Server.startup`` awaits ``lifespan.startup()`` **before** it creates any socket, so a TCP
connect from inside that hook is **refused (errno 111)**. Trading a timer for the startup hook
trades one race for another, and the name makes it look settled.

**What is actually guaranteed.** A socket that *we* bind and ``listen()`` on accepts connections
from that instant - the kernel queues them until uvicorn calls ``accept``. Measured: a connect
to a listening socket nobody has accepted yet succeeds. So the launch path binds the socket
itself and hands it to uvicorn, which is also what `tests/e2e/conftest.py` already does, and for
the same reason: the port is known before anything is told about it.

That removes a second race nobody had noticed - `_choose_port` used to bind a socket, **close
it**, and let uvicorn bind again, leaving a window in which another process could take the port
truestill had just announced.

**Two orderings, two different guarantees, both asserted here rather than slept on:** the port
accepts connections before `open_browser` is called, and the browser is not opened at all if the
server never reports itself started.
"""

from __future__ import annotations

import contextlib
import socket
from collections.abc import Callable
from pathlib import Path

import pytest
from app_support import ImmediateThread, StubServer, release_sockets
from truestill_app import __main__ as entry
from truestill_app import session_link

_STARTUP_FAILED = "startup failed"


class _FakeServer:
    """Stands in for `uvicorn.Server`, whose readiness the launch path waits on."""

    def __init__(self, *, started: bool, should_exit: bool = False) -> None:
        self.started = started
        self.should_exit = should_exit


def _recorder(opened: list[str]) -> Callable[[str], bool]:
    """A stand-in for `open_browser` that records the URL and reports success."""

    def open_browser(url: str) -> bool:
        opened.append(url)
        return True

    return open_browser


def _accepts(port: int) -> bool:
    """Whether a TCP connect to ``port`` succeeds right now."""
    with contextlib.closing(socket.socket()) as probe:
        probe.settimeout(1.0)
        try:
            probe.connect(("127.0.0.1", port))
        except OSError:
            return False
        return True


def test_the_port_accepts_connections_before_the_browser_is_opened(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The property, asserted at the only moment that matters: inside the browser call.

    No sleep anywhere. A test that waits 0.5s and then connects proves the timing of the machine
    it ran on; this proves the ordering itself.
    """
    sock = entry.bind_listening_socket(0)
    assert sock is not None
    port = sock.getsockname()[1]
    reachable: list[bool] = []

    def observe(_url: str) -> bool:
        reachable.append(_accepts(port))
        return True

    monkeypatch.setattr(session_link, "open_browser", observe)
    try:
        entry.open_when_ready(_FakeServer(started=True), f"http://127.0.0.1:{port}/", tmp_path)
    finally:
        sock.close()

    assert reachable == [True], "the browser was pointed at a port that was not accepting yet"


def test_binding_returns_a_socket_that_is_already_listening() -> None:
    """The guarantee the whole design rests on, separated so its failure is unambiguous."""
    sock = entry.bind_listening_socket(0)
    assert sock is not None

    try:
        assert _accepts(sock.getsockname()[1])
    finally:
        sock.close()


def test_the_browser_is_not_opened_when_the_server_never_starts(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Startup failure: a browser pointed at an app that is not up would show a broken page."""
    opened: list[str] = []
    monkeypatch.setattr(session_link, "open_browser", _recorder(opened))

    entry.open_when_ready(
        _FakeServer(started=False, should_exit=True), "http://127.0.0.1:1/", tmp_path
    )

    assert opened == []


def test_a_port_that_cannot_be_bound_starts_nothing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """No socket means no app. Nothing is announced, and no URL file claims a live address."""
    opened: list[str] = []
    StubServer.instances.clear()
    monkeypatch.setattr(entry.uvicorn, "Server", StubServer)
    monkeypatch.setattr(entry.threading, "Thread", ImmediateThread)
    monkeypatch.setattr(entry, "bind_listening_socket", lambda _preferred: None)
    monkeypatch.setattr(session_link, "open_browser", _recorder(opened))

    code = entry.main(["--db", str(tmp_path / "c.sqlite")])

    assert code != 0
    assert opened == []
    assert not session_link.path().exists(), "a URL file was left claiming a working address"
    assert capsys.readouterr().err.strip(), "the failure was silent"


def test_the_url_file_does_not_survive_a_server_that_dies_at_startup(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The file must never outlive the address it names, however the run ends."""

    class _DyingServer(StubServer):
        def run(self, sockets: list[socket.socket] | None = None, **_kwargs: object) -> None:
            release_sockets(sockets)
            raise RuntimeError(_STARTUP_FAILED)

    monkeypatch.setattr(entry.uvicorn, "Server", _DyingServer)
    monkeypatch.setattr(entry.threading, "Thread", ImmediateThread)

    with pytest.raises(RuntimeError):
        entry.main(["--db", str(tmp_path / "c.sqlite"), "--no-browser"])

    assert not session_link.path().exists()


def test_the_announced_port_is_the_one_that_is_held(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """`_choose_port` bound a socket, closed it, and let uvicorn bind again - so the port could
    be taken between announcing it and serving on it. The socket is now held throughout."""
    StubServer.instances.clear()
    monkeypatch.setattr(entry.uvicorn, "Server", StubServer)
    monkeypatch.setattr(entry.threading, "Thread", ImmediateThread)

    entry.main(["--db", str(tmp_path / "c.sqlite"), "--no-browser"])

    handed = StubServer.instances[-1].sockets
    assert handed is not None, "uvicorn was left to bind its own socket"
    assert len(handed) == 1
