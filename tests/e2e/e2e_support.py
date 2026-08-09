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

from PIL import Image


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
