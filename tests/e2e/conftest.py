"""Harness for the browser end-to-end suite.

**Why this layer exists.** Every UI bug the soak found -- a failed job rendering "NaN
verified", two Cancel buttons wired to nothing, a stale "isn't a backup yet" message
surviving the copy that disproved it, a successful run reporting "nothing to do" -- lived in
client-side JavaScript. pytest cannot reach that layer and manual checking cannot pin it, so
each of those bugs shipped, was found by a human, and could have come back the same way.

**The server runs in-process, not as a subprocess.** ``create_app`` is a plain factory, so the
harness builds the app itself, chooses the token, and binds the socket. That removes the two
usual flake sources in this kind of fixture -- scraping a port or token out of a child's
stdout, and racing its startup -- and lets a test open the same catalog the UI is writing to,
so "the screen says 2 places" can be checked against what was actually recorded.

The cost of that choice, stated: ``__main__.py`` (port selection, argument parsing, opening a
browser) is bypassed and stays uncovered. It is uncovered today too; this suite does not
change that, and should not be read as if it did.
"""

from __future__ import annotations

import secrets
import socket
import threading
from collections.abc import Iterator
from pathlib import Path

import pytest
import uvicorn
from e2e_support import AppServer, RetiringServers, make_photo, stamp_capture_date
from playwright.sync_api import Page
from truestill_app.server import create_app

_HOST = "127.0.0.1"
_BOOT_TIMEOUT_SECONDS = 10


@pytest.fixture(scope="session")
def retiring() -> Iterator[RetiringServers]:
    """The one piece of shared state in this lane, and it holds no application state at all.

    Session-scoped so a server signalled by the last test is still waited for: without the drain
    a run could end with a thread mid-shutdown, which is the leak this has to not have. It is
    torn down after every test has finished, so nothing it holds can reach a running test.
    """
    servers = RetiringServers()
    yield servers
    servers.drain()


@pytest.fixture
def app_server(tmp_path: Path, retiring: RetiringServers) -> Iterator[AppServer]:
    """A real app on an ephemeral port with an empty catalog, torn down after each test.

    Function-scoped on purpose: these tests assert on custody counts and drive registration,
    which are exactly the state a shared server would leak between them.
    """
    token = f"e2e-{secrets.token_urlsafe(16)}"
    db = tmp_path / "catalog.sqlite"

    # Bind first, then hand the bound socket to uvicorn: the port is known before the server
    # starts, so nothing has to poll for it or parse it out of a log line.
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((_HOST, 0))
    port = sock.getsockname()[1]

    server = uvicorn.Server(
        uvicorn.Config(create_app(token=token, db=db), log_level="warning", lifespan="off")
    )
    thread = threading.Thread(target=lambda: server.run(sockets=[sock]), daemon=True)
    thread.start()

    deadline = threading.Event()
    while not server.started and thread.is_alive():
        if deadline.wait(0.05):  # pragma: no cover - only reached if the server dies at boot
            break
        if not thread.is_alive():
            pytest.fail("the app server thread died during startup")
    if not server.started:
        pytest.fail("the app server did not start")

    yield AppServer(base_url=f"http://{_HOST}:{port}", token=token, db=db)

    # Signalled, then handed over: the 197 ms uvicorn takes to notice is not this test's problem,
    # and the next test does not wait for it. See `RetiringServers` for why nothing is shared and
    # why the socket cannot be closed under a live server.
    server.should_exit = True
    retiring.retire(server, thread, sock)


@pytest.fixture
def ui(page: Page, app_server: AppServer) -> Page:
    """The app, open and authenticated, with a short default timeout.

    Every wait in these tests is an auto-retrying assertion, never a sleep, so a low timeout
    costs nothing when things work and fails fast when they do not.
    """
    page.set_default_timeout(15_000)
    page.goto(app_server.url)
    return page


@pytest.fixture
def library(tmp_path: Path):
    """Build a source folder of synthetic photos on demand."""

    def _build(count: int = 6, *, name: str = "Pictures", dated: bool = True) -> Path:
        root = tmp_path / name
        made = [make_photo(root / f"IMG_{i:04d}.jpg", i) for i in range(count)]
        if dated:
            stamp_capture_date(made)
        return root

    return _build
