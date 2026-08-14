"""The sidecar stops when its parent does, and says so when it cannot.

`(adh)` (f): killing the Tauri shell left this process serving, with `session-url.txt` still
naming a live port and a valid token. No signal reaches the sidecar, so the signal handler that
would have cleaned up never runs.

The last test here is the one that matters - a real process, a real closed pipe, and the
assertion is that **the credential is gone**, not that a function was called. The rest exist
because that test cannot see ordering, and ordering is the security property: the credential is
cleared before anything else is attempted, so a slow or wedged shutdown cannot leave it on disk.
"""

from __future__ import annotations

import io
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest
from truestill_app import parent_watch


class _Pipe(io.RawIOBase):
    """A stream that blocks until it is told the parent has gone. Never a terminal."""

    def __init__(self) -> None:
        self._closed_by_parent = False

    def release(self) -> None:
        self._closed_by_parent = True

    def read(self, _size: int = -1) -> bytes:
        while not self._closed_by_parent:
            time.sleep(0.005)
        return b""

    def isatty(self) -> bool:
        return False


# ------------------------------------------------------------------ the contract, checked


def test_a_terminal_on_stdin_is_refused_rather_than_watched(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """THE ONE THAT KEEPS THE FAILURE LOUD.

    A terminal is never closed by a dying parent, so a watchdog given one would start, block, and
    protect nothing - while looking exactly like a watchdog that works. Refusing is the whole
    point: the alternative is silent absence of the guarantee.
    """
    terminal = _Pipe()
    monkeypatch.setattr(terminal, "isatty", lambda: True)

    with pytest.raises(parent_watch.ParentPipeMissingError, match="terminal"):
        parent_watch.require_pipe(terminal)


def test_no_stdin_at_all_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    """A console-less frozen Windows build has `sys.stdin is None`. That is the parent failing
    its side of the contract too, and must not reach the watchdog as a crash."""
    with pytest.raises(parent_watch.ParentPipeMissingError, match="none"):
        parent_watch.require_pipe(None)

    monkeypatch.setattr(sys, "stdin", None)
    assert parent_watch.stdin_stream() is None


def test_a_real_pipe_is_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    """The cry-wolf half: the check must let through what it exists to permit, or the flag is
    unusable and somebody deletes the check rather than the caller."""
    read_fd, write_fd = os.pipe()
    try:
        with os.fdopen(read_fd, "rb", buffering=0) as stream:
            monkeypatch.setattr(sys, "stdin", type("S", (), {"buffer": stream})())
            assert parent_watch.require_pipe(parent_watch.stdin_stream()) is stream
    finally:
        os.close(write_fd)


# ------------------------------------------------------------------------- what it does


def test_the_credential_is_cleared_before_the_shutdown_is_requested() -> None:
    """ORDERING IS THE SECURITY PROPERTY, so it is asserted rather than assumed.

    A shutdown that is slow, queued behind a long job, or abrupt must not be able to leave the
    token on disk. Recording the sequence is the only way to see that; asserting both happened
    would pass with them the other way round.
    """
    pipe = _Pipe()
    order: list[str] = []
    thread = parent_watch.start(
        stream=pipe,
        clear_credential=lambda: order.append("cleared"),
        request_shutdown=lambda: order.append("shutdown"),
        grace_seconds=30,
        hard_exit=lambda: order.append("hard-exit"),
    )
    assert order == [], "the watchdog acted before the parent went away"

    pipe.release()
    deadline = time.monotonic() + 5
    while len(order) < 2 and time.monotonic() < deadline:
        time.sleep(0.01)

    assert order == ["cleared", "shutdown"], f"wrong order: {order}"
    assert thread.is_alive(), "the backstop stopped waiting early"


def test_a_shutdown_that_never_happens_is_backstopped() -> None:
    """A sidecar that cannot be asked to stop is exactly the orphan this module prevents, so the
    graceful request has a deadline. Short grace and an injected exit, because the production
    one is `os._exit` and would take the test runner with it."""
    pipe = _Pipe()
    calls: list[str] = []
    parent_watch.start(
        stream=pipe,
        clear_credential=lambda: calls.append("cleared"),
        request_shutdown=lambda: None,  # a wedged server: asked, never stops
        grace_seconds=0.05,
        hard_exit=lambda: calls.append("hard-exit"),
    )
    pipe.release()

    deadline = time.monotonic() + 5
    while "hard-exit" not in calls and time.monotonic() < deadline:
        time.sleep(0.01)

    assert calls == ["cleared", "hard-exit"], f"the backstop did not fire: {calls}"


def test_an_unreadable_pipe_counts_as_the_parent_going_away() -> None:
    """A pipe that errors is not one a parent is still holding. Treating the error as "keep
    waiting" would leave the orphan running on exactly the path least likely to be exercised."""

    class Broken(_Pipe):
        def read(self, _size: int = -1) -> bytes:
            message = "pipe went away"
            raise OSError(message)

    calls: list[str] = []
    parent_watch.start(
        stream=Broken(),
        clear_credential=lambda: calls.append("cleared"),
        request_shutdown=lambda: calls.append("shutdown"),
        grace_seconds=30,
        hard_exit=lambda: calls.append("hard-exit"),
    )
    deadline = time.monotonic() + 5
    while len(calls) < 2 and time.monotonic() < deadline:
        time.sleep(0.01)

    assert calls == ["cleared", "shutdown"]


# ------------------------------------------------------- the real thing, end to end


def test_a_real_orphaned_sidecar_stops_and_takes_its_credential_with_it(tmp_path: Path) -> None:
    """`(adh)` (f) REPRODUCED AND CLOSED, with a real process and a real pipe.

    Before this, closing the parent's end of stdin did nothing: the app kept serving and
    `session-url.txt` kept naming a live port with a valid token. Here the pipe is closed - which
    is what a dying shell does, however it dies, including under `SIGKILL` - and the assertions
    are the two that matter: **the file is gone** and **the process is gone**.

    The file first. It is the credential, and it is the half a shell-side signal handler could
    never have covered.
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
            "--parent-stdin-watch",
        ],
        env=env,
        stdin=subprocess.PIPE,
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

        # What a dying parent does, whatever killed it. Not a signal: the whole defect is that
        # no signal reaches this process.
        assert child.stdin is not None
        child.stdin.close()

        assert child.wait(timeout=30) is not None, "the orphaned sidecar kept running"
        assert not url_file.exists(), (
            "the sidecar stopped but left session-url.txt naming its port with a live token"
        )
    finally:
        if child.poll() is None:  # pragma: no cover - only on a hung child
            child.kill()
            child.wait(timeout=10)


def test_without_the_flag_a_closed_stdin_changes_nothing(tmp_path: Path) -> None:
    """The flag is opt-in, and this is why that matters rather than being caution.

    Somebody who launches `truestill-app` from a terminal and closes it must not have the app
    vanish because a shell it never had went away. Opt-in keeps the shipped standalone behaviour
    exactly as it was, and this asserts that rather than trusting the default.
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
        stdin=subprocess.PIPE,
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

        assert child.stdin is not None
        child.stdin.close()
        time.sleep(1.0)

        assert child.poll() is None, "the app stopped on a closed stdin it was never watching"
    finally:
        child.terminate()
        child.wait(timeout=30)
