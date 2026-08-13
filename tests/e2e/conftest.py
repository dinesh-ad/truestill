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
from collections.abc import Iterator
from pathlib import Path

import pytest
from e2e_support import (
    AppServer,
    RetiringServers,
    boot_app,
    make_photo,
    open_app,
    stamp_capture_date,
)
from playwright.sync_api import Page


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
    # The boot itself lives in `e2e_support.boot_app`, shared with `scripts/shoot_screens.py`.
    # Teardown stays here because it is the half the two callers disagree about - see that
    # function's docstring, and `RetiringServers` for why this one does not wait.
    started, server, thread, sock = boot_app(
        tmp_path / "catalog.sqlite", token=f"e2e-{secrets.token_urlsafe(16)}"
    )
    yield started

    # Signalled, then handed over: the 197 ms uvicorn takes to notice is not this test's problem,
    # and the next test does not wait for it. See `RetiringServers` for why nothing is shared and
    # why the socket cannot be closed under a live server.
    server.should_exit = True
    retiring.retire(server, thread, sock)


@pytest.fixture
def ui(page: Page, app_server: AppServer) -> Page:
    """The app, open and authenticated, with a short default timeout - and **loaded**.

    A low timeout costs nothing when things work and fails fast when they do not.

    `goto` resolves on the `load` event, which says nothing about the six requests the shell
    fires afterwards - `loadCustody` alone rewrites the rail, the catalog banner and five input
    fields. Every test using this fixture used to begin racing those, and the ones that noticed
    re-derived a wait of their own: `wait_for_selector(".nav-item")` at eleven sites (markup the
    server rendered, so it proves nothing about the fetches), a sleep at several more.

    **This makes every test stricter, and measurement says none of them currently need it.**
    Removing this wait leaves all 407 green (measured 2026-08-10). That is the honest state: the
    wait is insurance against a class of race, not an assertion any test's outcome rests on
    today. It costs nothing measurable - the run without it was 409s against 397s with it, which
    is variance, and in the wrong direction to be a cost.

    What proves the wait works is not this suite passing - it passed before. It is the
    differential: with a screen's load broken so it never lands, a converted test FAILS and the
    same test in its old form PASSES. A green run cannot tell those apart, which is the whole
    reason the gate for depending on this signal is a differential rather than a run count.

    The claim this docstring used to make - "every wait in these tests is an auto-retrying
    assertion, never a sleep" - was false when written: 63 `wait_for_timeout` calls across 19
    files say otherwise. It is now an aspiration with a plan behind it rather than a description,
    and it is recorded that way instead of being repeated.
    """
    return open_app(page, app_server.url)


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
