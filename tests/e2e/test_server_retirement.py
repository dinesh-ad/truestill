"""The deferred server teardown cannot strand a server or close a socket under a live one.

**Why this file exists rather than a comment.** The saving here comes from *not* waiting for a
server to finish, which is one step away from a real defect: a socket closed while uvicorn still
holds it. A prototype that skipped the wait outright did exactly that and produced 17 errors in
a single file. The distance between "fast" and "broken" is one `is_alive()` check, so that check
is tested rather than trusted.

**A flake here would be misread as `(abq)`.** That entry is an unexplained lost click in this
same lane, and a server torn down at the wrong moment would look like one - a page that does not
respond, blamed on the browser. So these run with fake threads and sockets: no timing, no
sleeping, no browser, and every ordering forced rather than waited for.
"""

from __future__ import annotations

import socket
import threading

import pytest
from e2e_support import RetiringServers

#: THE MIGRATION'S EARLY-WARNING SYSTEM. This file belongs to no screen, so no screen's commit
#: carries it - and an island landing on a DIFFERENT screen changes the DOM around it without
#: touching a line here. `make e2e-shell` runs the set after every island; see
#: `docs/react-migration-plan.md`.
pytestmark = pytest.mark.shell


class _FakeThread:
    """A thread whose liveness the test decides, so no ordering has to be waited for."""

    def __init__(self, *, alive: bool = True) -> None:
        self.alive = alive
        self.joined = False

    def is_alive(self) -> bool:
        return self.alive

    def join(self, timeout: float | None = None) -> None:  # noqa: ARG002 - matches Thread.join
        self.joined = True
        self.alive = False


class _FakeSocket:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


def _retire(servers: RetiringServers, thread: _FakeThread, sock: _FakeSocket) -> None:
    servers.retire(object(), thread, sock)  # type: ignore[arg-type]


def test_a_socket_is_not_closed_while_its_server_is_still_running() -> None:
    """THE ONE THAT MATTERS. Closing early is what the skip-the-wait prototype did, and it cost
    17 errors in one file - a live server left holding a closed socket."""
    servers = RetiringServers()
    thread, sock = _FakeThread(alive=True), _FakeSocket()

    _retire(servers, thread, sock)

    assert sock.closed is False, "the socket was closed while its server was still alive"
    assert servers.outstanding == 1


def test_a_server_that_has_finished_is_closed_out_by_the_next_test() -> None:
    """The cry-wolf half: a retirement list that never closed anything would also pass the test
    above, and would leak a socket per test for the length of the run."""
    servers = RetiringServers()
    finished, sock = _FakeThread(alive=False), _FakeSocket()
    _retire(servers, finished, sock)

    assert sock.closed is True
    assert servers.outstanding == 0


def test_the_last_server_of_a_run_is_waited_for_rather_than_abandoned() -> None:
    """Without the drain a run ends with a thread mid-shutdown. Nothing would notice, which is
    exactly why it needs a test: a leak whose only symptom is a warning nobody reads."""
    servers = RetiringServers()
    still_going, sock = _FakeThread(alive=True), _FakeSocket()
    _retire(servers, still_going, sock)

    servers.drain()

    assert still_going.joined is True
    assert sock.closed is True
    assert servers.outstanding == 0


def test_a_failing_test_still_hands_its_server_over() -> None:
    """Teardown runs whatever the test's outcome, so the list must not depend on success. Pinned
    because the opposite - stranding a server only on failures - would show up as a slow, flaky
    suite exactly when the suite was already red."""
    servers = RetiringServers()
    thread, sock = _FakeThread(alive=False), _FakeSocket()

    try:
        raise RuntimeError  # noqa: TRY301 - stands in for the test body failing
    except RuntimeError:
        _retire(servers, thread, sock)

    assert sock.closed is True
    assert servers.outstanding == 0


def test_retiring_servers_cannot_pile_up_without_bound() -> None:
    """A list that only ever grows is a leak with a slower fuse. Above the limit the oldest is
    waited for, so the cost is bounded rather than deferred forever."""
    servers = RetiringServers()
    threads = [_FakeThread(alive=True) for _ in range(RetiringServers.LIMIT + 3)]
    for thread in threads:
        _retire(servers, thread, _FakeSocket())

    assert servers.outstanding <= RetiringServers.LIMIT
    assert threads[0].joined is True, "the oldest server was never waited for"


def test_the_helper_matches_the_real_thread_and_socket_it_stands_in_for() -> None:
    """THE FAKES ARE ONLY WORTH WHAT THEY RESEMBLE. A fake that drifted from `threading.Thread`
    or `socket.socket` would let these tests pass against a helper that cannot work in the lane.
    """
    assert hasattr(threading.Thread, "is_alive")
    assert hasattr(threading.Thread, "join")
    assert hasattr(socket.socket, "close")

    real = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    real.close()
    real.close()  # idempotent, which is why a swept socket can also be closed by uvicorn
