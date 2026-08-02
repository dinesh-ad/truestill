"""Values the app's HTTP tests **import**, as opposed to fixtures pytest injects for them.

Split out of ``conftest.py`` deliberately. A conftest is a file pytest discovers and whose
fixtures it supplies by name; importing one by its bare module name works only by accident of
``sys.path`` and breaks the moment two of them are in the same session - which this repo proved
by resolving the app suite's ``from conftest import TOKEN`` against the browser suite's file.
See ``test_shared_test_helpers.py`` for the reproduction and the rule.

So the split is: **fixtures stay in ``conftest.py``, importable values live here**, under a
basename no other test directory claims.
"""

from __future__ import annotations

import socket
from typing import Any, ClassVar

#: One value for every app test. The app mints a real token per process; tests only need it to
#: be consistent between the server they build and the requests they send.
#:
#: It is importable because several modules put it in a query string (``?token=...``) as well as
#: a header; that is a real second use, not a leak of a fixture's internals.
TOKEN = "test-token"


def release_sockets(sockets: list[socket.socket] | None) -> None:
    """Close what the launch path handed the server, as uvicorn's `Server.shutdown` does.

    **Any double that overrides `run` must call this.** In production uvicorn owns these; a stub
    that records and drops them leaks a listening socket per launch, and the warning then
    surfaces against whichever test the collector happened to interrupt.
    """
    for sock in sockets or ():
        sock.close()


class StubServer:
    """Stands in for `uvicorn.Server`, recording what the launch path handed it.

    Reports itself **started** so readiness-gated work proceeds, and never touches the socket it
    is given - the real one blocks forever, which is exactly what a test must not do.
    """

    #: Every instance built during a test, newest last. A list rather than a single slot so a
    #: test that accidentally launches twice fails loudly instead of silently inspecting one.
    instances: ClassVar[list[StubServer]] = []

    def __init__(self, config: Any) -> None:
        self.config = config
        self.started = True
        self.should_exit = False
        self.sockets: list[socket.socket] | None = None
        StubServer.instances.append(self)

    def run(self, sockets: list[socket.socket] | None = None) -> None:
        self.sockets = sockets  # recorded, never served
        release_sockets(sockets)


class ImmediateThread:
    """A `threading.Thread` replacement that runs the target inline, at ``start()``.

    The launch path defers the browser to a thread so it does not block on readiness. Letting a
    real thread race the assertions would make these tests flaky in the direction that hides
    bugs - a missing call looks like a slow one. What is under test is *whether and in what
    order* the call happens, never *how fast*.
    """

    def __init__(
        self, *, target: Any = None, args: tuple[Any, ...] = (), daemon: bool | None = None
    ) -> None:
        self._target = target
        self._args = args
        self.daemon = daemon

    def start(self) -> None:
        if self._target is not None:
            self._target(*self._args)

    def join(self, _timeout: float | None = None) -> None:
        return None
