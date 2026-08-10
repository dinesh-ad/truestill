"""Types and helpers the browser tests **import**, as opposed to fixtures pytest injects.

Split out of ``conftest.py`` deliberately - see ``test_shared_test_helpers.py`` for the rule and
for the reproduction of what the shared bare name ``conftest`` did when both suites were
collected at once. Fixtures stay in ``conftest.py``; anything a test imports lives here, under a
basename no other test directory claims.
"""

from __future__ import annotations

import socket
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image
from playwright.sync_api import Page, expect


@dataclass(frozen=True, slots=True)
class AppServer:
    """A running app instance, and the catalog behind it."""

    base_url: str
    token: str
    db: Path

    @property
    def url(self) -> str:
        """The page URL a user would open, token included -- exactly as the app prints it."""
        return f"{self.base_url}/?token={self.token}"


# --- synthetic fixtures ------------------------------------------------------------------
# Generated, never committed. Media files do not belong in git whatever their provenance, and
# generating them keeps each test's corpus exactly the shape that test needs.


def make_photo(path: Path, seed: int, *, size: tuple[int, int] = (320, 240)) -> Path:
    """A JPEG with unique content, so dedup treats every generated file as its own file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, ((seed * 37) % 256, (seed * 91) % 256, (seed * 13) % 256)).save(
        path, "JPEG", quality=90
    )
    return path


def stamp_capture_date(paths: list[Path], when: str = "2021:06:15 10:30:00") -> None:
    """Give files a real embedded capture date, so they land in dated folders like real photos.

    Skipped silently when exiftool is absent: the tests that need dating declare it, and the
    rest do not care.
    """
    if not paths:
        return
    subprocess.run(
        [
            "exiftool",
            "-q",
            "-m",
            "-overwrite_original",
            f"-DateTimeOriginal={when}",
            *map(str, paths),
        ],
        check=False,
    )


class RetiringServers:
    """Servers signalled to stop, whose 197 ms shutdown no longer sits on the critical path.

    **Measured, which is why this exists.** Booting a per-test app costs 6.2 ms; tearing it down
    costs **196.9 ms**, and 96% of that is uvicorn's 0.1 s main-loop tick, twice. `force_exit`
    does not change it. Across 381 browser tests that is ~78 s of a ~308 s lane, spent waiting
    for a server nobody is using any more.

    **Nothing is shared to buy that back.** Each test keeps its own server, catalog and token -
    sharing one would have shared `create_app`'s `JobManager()`, which is live in-process state,
    so a job from one test would be visible to the next.

    **THE SOCKET IS CLOSED ONLY AFTER ITS SERVER'S THREAD IS DEAD**, and that is the whole safety
    argument. A prototype that simply skipped the wait closed the socket while uvicorn still held
    it and produced 17 errors in one file. `thread.is_alive()` going false means `server.run()`
    has returned, so the close cannot land underneath a live server whatever the ordering.
    """

    #: Above this many still retiring, wait for the oldest rather than letting them accumulate.
    #: Bounds the list by construction; in practice ~1-2 are alive at once at 0.5 s per test.
    LIMIT = 8

    def __init__(self) -> None:
        self._pending: list[tuple[object, threading.Thread, socket.socket]] = []

    def retire(self, server: object, thread: threading.Thread, sock: socket.socket) -> None:
        """Take ownership of a signalled server. The caller does not wait."""
        self._pending.append((server, thread, sock))
        self._sweep()
        while len(self._pending) > self.LIMIT:
            self._join_one(*self._pending.pop(0))

    def _sweep(self) -> None:
        """Close out everything that has finished on its own since the last test."""
        for entry in list(self._pending):
            if not entry[1].is_alive():
                entry[2].close()
                self._pending.remove(entry)

    def _join_one(self, _server: object, thread: threading.Thread, sock: socket.socket) -> None:
        thread.join(timeout=10.0)
        sock.close()

    def drain(self) -> None:
        """Wait for every outstanding server. Called once when the session ends.

        **On a hard interrupt this may not run**, and that is survivable rather than ignored:
        the threads are daemons and the sockets are the process's, so the OS reclaims both when
        it exits. Nothing outlives the run either way.
        """
        while self._pending:
            self._join_one(*self._pending.pop(0))

    @property
    def outstanding(self) -> int:
        return len(self._pending)


def open_app(page: Page, url: str) -> Page:
    """Open the app and wait until the screen it lands on has finished loading.

    `goto` returns on `load`, which says nothing about the six requests the shell makes after
    that - so every test that read the page immediately was racing them. Organize ships open, and
    its readiness folds in the shell's loads, so waiting here covers both.
    """
    page.set_default_timeout(15_000)
    page.goto(url)
    expect(page.locator(".screen.active")).to_have_attribute("data-ready", "ready")
    return page


def open_screen(ui: Page, name: str) -> None:
    """Switch to a screen and wait until it has finished loading.

    One condition, `data-ready="ready"`, which the screen sets after every load it owes has
    settled - see `settleScreen` in `app.js`. It replaces the per-site guesses that came before:
    a `wait_for_selector` on some element the load happens to write, or `networkidle`, or a
    sleep. Each of those is a **proxy** for "the screen is done", and each is wrong in a case the
    others are not - the selector never appears when the result is legitimately empty,
    `networkidle` is satisfied by a screen that fetched nothing, and a sleep is satisfied by
    everything.

    A screen that FAILED to load never becomes ready, so this times out rather than proceeding
    against a half-rendered page. That is deliberate: the alternative is a test that runs on
    whatever the failure left behind.
    """
    ui.click(f'[data-screen="{name}"]')
    expect(ui.locator(f"#screen-{name}")).to_have_attribute("data-ready", "ready")


def open_backups(ui: Page) -> None:
    """Switch to Backups and wait for it to finish loading.

    **The reasoning this docstring used to carry was wrong, and it is corrected rather than
    quietly dropped**, because a wrong comment surviving a fix is how the next person re-learns
    the wrong lesson. It said `loadDrives` and `loadCustody` both rewrite the screen and blamed
    the pair for the +4.9px in `(abq)`. There are two movers on this screen and neither is
    `loadCustody`, which writes into the rail and into the fields themselves, not above the
    controls:

    * `loadDrives` writes `#drives-list`. It used to sit ABOVE the cards holding the controls, so
      writing it moved them - measured at +142px with no drives and +563px with three, `(acd)`.
      **Fixed by moving that region below every control**, so it can no longer move one; this
      wait no longer stands between a caller and that defect.
    * `validatePath` writes the hint spans immediately above `#bk-preview`, on a 400ms debounce,
      AFTER typing. **That is the one `(abq)` measured at +4.9px**, it happens long after this
      wait returns, and nothing here touches it.

    So this closes the screen-open race and leaves `(abq)`'s alone.
    """
    open_screen(ui, "backups")


def hold_route(ui: Page, url: str) -> list[Any]:
    """Hold the next request to ``url`` open, and hand back the handle that releases it.

    The route handler stores the route and returns without fulfilling, so the request stays
    pending while the driver stays responsive. A handler that slept instead would block the same
    connection the assertions travel over, and nothing could be observed mid-flight.

    Lifted here from `test_screen_readiness.py` when a second file needed it: this module is
    where anything a test *imports* lives, by the rule in its own docstring.
    """
    held: list[Any] = []
    # The lambda is required, not stylistic: Playwright stamps an attribute onto the handler it
    # is given, and a built-in method (`held.append`) has no `__dict__` to stamp - it raises
    # AttributeError at route registration. Ruff's PLW0108 is a false positive here.
    ui.route(url, lambda route: held.append(route))  # noqa: PLW0108
    return held


def release_held(held: list[Any], *, body: str | None = None) -> None:
    """Let the held request through - to the real server, or to a stubbed ``body``.

    No polling loop is needed, and a sleep would be wrong: the auto-retrying assertions that run
    before every call site pump the driver's message loop, which is when the route handler
    actually fires. If `held` is still empty by here, the load never happened - a missing
    registry entry or a wrong glob - and that deserves to be said, not waited out.

    Every held route is drained, not just the first. One screen holds more than one: filling
    `#ev-source` fires a `change` listener that refreshes the same panel, so the field and the
    screen open each ask once. Releasing only the first leaves the screen at "loading" for a
    reason that has nothing to do with the flag being wrong.
    """
    assert held, "the load never fired: check the SCREEN_LOADS entry and the URL pattern"
    for route in held:
        if body is None:
            route.continue_()
        else:
            route.fulfill(status=200, content_type="application/json", body=body)
    held.clear()
