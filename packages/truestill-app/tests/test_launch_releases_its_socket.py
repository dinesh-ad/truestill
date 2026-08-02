"""A launch that dies before handover must not keep the port it bound.

`bind_listening_socket` deliberately *holds* the socket from discovery until uvicorn takes it -
that closes a race where another process could grab the announced port. The cost is an ownership
window: between the bind and `server.run(sockets=[sock])` there are eleven statements, several of
which can raise, and none of them released the socket.

**The user-visible consequence is the confusing one.** The port stays held by the dying process,
so the next launch reports *"Could not listen on 127.0.0.1. Is another copy of Truestill already
running?"* - a message caused by our own leak, blaming a second copy that does not exist.
Reproduced before fixing: `[98] Address already in use` on a re-bind of the same port.

Asserted on the socket's own state and on an external re-bind, never on a `ResourceWarning`:
those are emitted by the collector and land on whichever test is running when it happens.
"""

from __future__ import annotations

import socket
from pathlib import Path

import pytest
from app_support import ImmediateThread, StubServer
from truestill_app import __main__ as entry
from truestill_app import session_link


class _LaunchFailedError(RuntimeError):
    """Injected between bind and handover. Injected, so all three CI lanes run this."""


@pytest.fixture(autouse=True)
def _deterministic_launch(monkeypatch: pytest.MonkeyPatch) -> None:
    StubServer.instances.clear()
    monkeypatch.setattr(entry.uvicorn, "Server", StubServer)
    monkeypatch.setattr(entry.threading, "Thread", ImmediateThread)


@pytest.fixture
def bound(monkeypatch: pytest.MonkeyPatch) -> list[socket.socket]:
    """Every socket the launch path binds, so the test can inspect one it never receives."""
    captured: list[socket.socket] = []
    real = entry.bind_listening_socket

    def spy(preferred: int) -> socket.socket | None:
        sock = real(preferred)
        if sock is not None:
            captured.append(sock)
        return sock

    monkeypatch.setattr(entry, "bind_listening_socket", spy)
    return captured


def _still_open(sock: socket.socket) -> bool:
    return sock.fileno() != -1


def test_a_launch_that_dies_before_handover_releases_the_port(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, bound: list[socket.socket]
) -> None:
    """The leak, asserted two ways: the handle's own state, and whether the port frees up."""

    def exploding_write(_url: str) -> None:
        raise _LaunchFailedError

    monkeypatch.setattr(session_link, "write", exploding_write)

    with pytest.raises(_LaunchFailedError):
        entry.main(["--db", str(tmp_path / "c.sqlite"), "--no-browser"])

    assert len(bound) == 1, "fixture check: exactly one socket should have been bound"
    sock = bound[0]
    assert not _still_open(sock), "the listening socket outlived the failed launch"

    port_probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        port_probe.bind(("127.0.0.1", sock.getsockname()[1] if _still_open(sock) else 0))
    except OSError as exc:  # pragma: no cover - only reached when the fix regresses
        pytest.fail(f"the port is still held by the dead launch: {exc}")
    finally:
        port_probe.close()


def test_a_failure_after_the_link_is_written_also_removes_the_credential(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, bound: list[socket.socket]
) -> None:
    """The second resource in the same window, and the one that matters more.

    `session_link.write` creates a file holding the session token. The pre-existing
    `try/finally` only wraps `server.run`, so a failure between the write and that call left a
    live credential on disk - the exact staleness the session-link work was built to prevent.
    """

    def exploding_server(_config: object) -> None:
        raise _LaunchFailedError

    monkeypatch.setattr(entry.uvicorn, "Server", exploding_server)

    with pytest.raises(_LaunchFailedError):
        entry.main(["--db", str(tmp_path / "c.sqlite"), "--no-browser"])

    assert not session_link.path().exists(), "a token file survived a launch that never served"
    assert not _still_open(bound[0])


def test_a_successful_launch_hands_over_an_open_socket(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The cry-wolf half, and the one an over-eager fix breaks.

    Cleanup has to stop exactly at handover. uvicorn's `Server.shutdown` closes the sockets it
    was given - verified in its source - so closing them ourselves afterwards would be a second
    owner, and closing them *before* `run` would hand over a dead socket and break every start.
    """
    handed: list[int] = []

    class RecordingServer(StubServer):
        def run(self, sockets: list[socket.socket] | None = None) -> None:
            handed.extend(s.fileno() for s in sockets or ())
            super().run(sockets)

    monkeypatch.setattr(entry.uvicorn, "Server", RecordingServer)

    entry.main(["--db", str(tmp_path / "c.sqlite"), "--no-browser"])

    assert len(handed) == 1, "the launch must hand exactly one socket to the server"
    assert handed[0] != -1, "the socket was closed before uvicorn ever received it"
