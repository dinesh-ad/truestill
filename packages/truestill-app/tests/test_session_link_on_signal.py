"""The session URL file is removed when the app is asked to stop, not only when it returns.

**The bug, and why the `finally` was not enough.** `main` wrapped `server.run()` in
``try/finally: session_link.clear()``, which is correct for an ordinary return and does nothing
at all on Ctrl-C or ``kill``. uvicorn's `Server.capture_signals` installs its own handlers,
shuts down gracefully, restores the **original** handlers, and then **re-raises the captured
signal at itself**::

    for captured_signal in reversed(self._captured_signals):
        signal.raise_signal(captured_signal)

It does that so the parent process sees the conventional exit status. The effect is that the
default handler is back in place when the signal is re-raised, so the process dies **inside**
``server.run()`` and the ``finally`` is never reached. Measured, not inferred: a bare script with
``try: server.run() finally: marker.write_text(...)`` leaves no marker after ``SIGTERM``.

**Why it mattered.** The file is the way back into a running app, and a file that outlives its
process is a link that fails tomorrow - against a dead port, or worse against a live one holding
a different token. That staleness is exactly what the file was designed to avoid, and on the
ordinary exit path the protection did not work.

**The fix rides uvicorn's own mechanism rather than fighting it.** Handlers installed *before*
``server.run()`` are the ones uvicorn snapshots and restores, so the re-raise lands on ours: it
clears the file, restores the default, and re-raises again so the exit status is still the
conventional one.

**What still cannot be cleaned up, stated rather than discovered:** ``SIGKILL`` by definition -
no handler runs, and no process can promise otherwise. Also a power loss, and ``SIGSTOP``
followed by a kill. A stale file after one of those is unavoidable, which is why the stale-link
message exists and names the file rather than trusting it to be absent.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest
from app_support import ImmediateThread, StubServer
from truestill_app import __main__ as entry
from truestill_app import session_link

pytestmark = pytest.mark.skipif(
    os.name == "nt", reason="POSIX signal delivery; Windows terminates differently"
)


def test_a_terminating_signal_removes_the_url_file(monkeypatch: pytest.MonkeyPatch) -> None:
    """The handler's own job, isolated from the re-raise that would end the test process."""
    session_link.write("http://127.0.0.1:1/?token=abc")
    assert session_link.path().is_file(), "precondition: a file to remove"
    monkeypatch.setattr(entry.signal, "signal", lambda *_a: None)
    monkeypatch.setattr(entry.signal, "raise_signal", lambda *_a: None)

    entry.release_session_link(signal.SIGTERM, None)

    assert not session_link.path().exists()


def test_the_handlers_are_installed_before_the_server_starts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ordering is the whole fix: uvicorn snapshots whatever is installed when it starts.

    Installed afterwards, ours would never be restored and the re-raise would hit the default
    handler again - the original bug with extra code.
    """
    seen: dict[int, object] = {}

    class _RecordingServer(StubServer):
        def run(self, **_kwargs: object) -> None:
            for sig in (signal.SIGINT, signal.SIGTERM):
                seen[sig] = signal.getsignal(sig)

    monkeypatch.setattr(entry.uvicorn, "Server", _RecordingServer)
    monkeypatch.setattr(entry.threading, "Thread", ImmediateThread)

    entry.main(["--db", str(tmp_path / "c.sqlite"), "--no-browser"])

    assert seen[signal.SIGINT] is entry.release_session_link
    assert seen[signal.SIGTERM] is entry.release_session_link


@pytest.mark.parametrize("sig", [signal.SIGTERM, signal.SIGINT])
def test_a_real_process_leaves_no_url_file_behind(tmp_path: Path, sig: signal.Signals) -> None:
    """The assertion that actually matters: **the file is gone**, not that the process exited.

    A real subprocess, a real signal, and a wait on the file rather than a sleep. The previous
    attempt at this concluded nothing because it force-killed with ``SIGKILL``, under which no
    ``finally`` can run by definition - so the surviving file proved nothing either way.
    """
    data = tmp_path / "data"
    env = {
        **os.environ,
        "TRUESTILL_DATA_DIR": str(data),
        "TRUESTILL_CACHE_DIR": str(tmp_path / "cache"),
    }
    child = subprocess.Popen(
        [
            sys.executable,
            "-c",
            "from truestill_app.__main__ import main; raise SystemExit(main())",
            "--db",
            str(tmp_path / "c.sqlite"),
            "--port",
            "0",
            "--no-browser",
        ],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    url_file = data / "session-url.txt"
    try:
        deadline = time.monotonic() + 30
        while not url_file.exists():
            assert child.poll() is None, "the app exited before writing its URL file"
            assert time.monotonic() < deadline, "the app never wrote its URL file"
            time.sleep(0.05)

        child.send_signal(sig)
        assert child.wait(timeout=30) is not None
    finally:
        if child.poll() is None:  # pragma: no cover - only on a hung child
            child.kill()
            child.wait(timeout=10)

    assert not url_file.exists(), f"the URL file survived {sig.name}"
