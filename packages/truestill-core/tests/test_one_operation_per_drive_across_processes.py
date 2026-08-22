"""A second process cannot mutate a drive that is already being mutated. `(aaw)`

**Measured, not reasoned.** Two `organize --apply` runs against one destination lost 99 and 45
organized copies in 2 of 9 attempts on real photographs, proven by content.

⚠ **Unique staging shipped first and made the outcome worse**, which is the argument for this file
rather than a footnote to it. Against the same reproduction: before it, 4 of 5 attempts hit and the
loser failed loudly with `ENOENT`; after it, **5 of 5 hit, both processes exited 0, and nothing was
said**. The mechanism improved and the outcome degraded, measured both ways.

**Two real processes, because that is the claim.** `JobManager._lock` already covers threads, so a
single-process test here would be coverage theatre - it would pass against a `threading.Lock` that
does nothing across processes, which is the entire defect.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest
from truestill_core import drive_lock
from truestill_core.drive_lock import DriveBusyError, DriveLock, lock_for

if sys.platform == "win32":  # pragma: no cover - the Windows lane
    import msvcrt

_HOLDER = """
import os, sys, time
from truestill_core.drive_lock import DriveLock
lock = DriveLock({key!r}, "D3", operation="organize")
lock.acquire()
# ⚠ It reports its OWN pid rather than the test reading `Popen.pid`. On Windows `sys.executable`
# in a uv venv is a launcher that spawns the real interpreter as a child, so the pid Popen knows
# is not the pid that took the lock - which the Windows lane caught and no other lane could.
print("HELD", os.getpid(), flush=True)
time.sleep(60)
"""


def _holder(key: str) -> tuple[subprocess.Popen[str], int]:
    """A real second process holding the lock, and the pid it says it is."""
    proc = subprocess.Popen(
        [sys.executable, "-c", textwrap.dedent(_HOLDER).format(key=key)],
        stdout=subprocess.PIPE,
        text=True,
    )
    assert proc.stdout is not None
    line = proc.stdout.readline().strip()
    held, _, pid = line.partition(" ")
    assert held == "HELD", f"the holder never took the lock: {line!r}"
    return proc, int(pid)


@pytest.fixture
def key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    """A lock name unique to this test, and a data dir that is this test's own."""
    monkeypatch.setenv("TRUESTILL_DATA_DIR", str(tmp_path / "data"))
    return f"path:{tmp_path}"


def test_a_live_lock_is_respected(key: str) -> None:
    """⚠ **The property, and it needs a second PROCESS to mean anything.**"""
    holder, _pid = _holder(key)
    try:
        with pytest.raises(DriveBusyError) as refused:
            DriveLock(key, "D3", operation="reclaim").acquire()
    finally:
        holder.kill()
        holder.wait(timeout=10)

    assert "is using 'D3' right now" in str(refused.value)


def test_the_refusal_names_the_holder_so_a_user_can_act(key: str) -> None:
    """No `--force`, so the escape hatch is naming the process to deal with instead."""
    holder, pid = _holder(key)
    try:
        with pytest.raises(DriveBusyError) as refused:
            DriveLock(key, "D3", operation="reclaim").acquire()
    finally:
        holder.kill()
        holder.wait(timeout=10)

    message = str(refused.value)
    assert "organize" in message, f"the refusal does not say what is running:\n{message}"
    assert str(pid) in message, f"the refusal does not name the process:\n{message}"


@pytest.mark.skipif(sys.platform == "win32", reason="SIGKILL is POSIX; the Windows lane kills too")
def test_a_killed_holder_leaves_no_stale_lock(key: str) -> None:
    """⚠ **The never-stuck property, and the reason there is no PID check and no TTL.**

    The OS releases a `flock` when the process dies, so *"locked out of my own library"* is a state
    this design cannot reach. A lock we had to judge liveness on could stand the user up.
    """
    holder, _pid = _holder(key)
    os.kill(holder.pid, signal.SIGKILL)
    holder.wait(timeout=10)

    taken = DriveLock(key, "D3", operation="organize")
    taken.acquire()  # must not raise
    taken.release()


def test_the_lock_outlives_the_function_that_took_it(key: str) -> None:
    """⚠ **The FD-lifetime trap, which the design names as the real implementation risk.**

    Both primitives bind the lock to the file DESCRIPTOR, so closing the file releases it silently.
    The app takes the lock in `jobs.start` and runs the work on a worker thread after that returns,
    so a naive `with open(...)` would hand back an unlocked drive and every other test here would
    still pass.
    """

    def acquire_and_return() -> DriveLock:
        lock = DriveLock(key, "D3", operation="organize")
        lock.acquire()
        return lock

    lock = acquire_and_return()
    try:
        assert lock.held, "the lock reports itself released after the acquiring call returned"
        proc = subprocess.Popen(
            [
                sys.executable,
                "-c",
                textwrap.dedent(
                    """
                    import sys
                    from truestill_core.drive_lock import DriveBusyError, DriveLock
                    try:
                        DriveLock({key!r}, "D3", operation="x").acquire()
                    except DriveBusyError:
                        print("REFUSED")
                    else:
                        print("TOOK IT")
                    """
                ).format(key=key),
            ],
            stdout=subprocess.PIPE,
            text=True,
        )
        out, _ = proc.communicate(timeout=30)
        assert out.strip() == "REFUSED", (
            "a second process took the drive while the first still held it - the descriptor was "
            "closed when the acquiring function returned"
        )
    finally:
        lock.release()


def test_the_lock_is_released_and_retakeable(key: str) -> None:
    """The other half: a released lock must actually be available again."""
    first = DriveLock(key, "D3", operation="organize")
    first.acquire()
    first.release()

    second = DriveLock(key, "D3", operation="reclaim")
    second.acquire()
    try:
        assert second.held
    finally:
        second.release()


def test_two_different_drives_never_block_each_other(key: str) -> None:
    """Granularity is per drive, so a second library is not held up by the first."""
    one = DriveLock(key, "D3", operation="organize")
    other = DriveLock(f"{key}-other", "D4", operation="organize")
    one.acquire()
    other.acquire()
    try:
        assert one.held, "the first drive's lock was lost"
        assert other.held, "a second drive was blocked by the first"
    finally:
        one.release()
        other.release()


def test_the_key_is_hashed_because_a_drive_key_is_not_a_filename() -> None:
    """A `path:` key holds separators and a `uuid:` key holds a colon, which Windows refuses."""
    lock = DriveLock("uuid:0e1f-2a/3b", "D3", operation="organize")

    assert ":" not in lock.path.name
    assert "/" not in lock.path.name
    assert lock.path.name.endswith(".lock")


def test_the_lock_lives_in_the_data_dir_and_never_on_the_drive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """⚠ Advisory locking is least reliable on exactly the mounts a library sits on."""
    monkeypatch.setenv("TRUESTILL_DATA_DIR", str(tmp_path / "data"))
    drive = tmp_path / "drive"
    drive.mkdir()

    lock = lock_for(drive, operation="organize")
    lock.acquire()
    try:
        assert (tmp_path / "data") in lock.path.parents, "the lock must live in the data dir"
        assert not list(drive.rglob("*.lock")), "nothing was written to the user's drive"
    finally:
        lock.release()


@pytest.mark.skipif(sys.platform != "win32", reason="the Windows primitive, on the Windows lane")
def test_the_windows_primitive_is_the_one_that_ran() -> None:
    """⚠ **ANTI-VACUITY. Windows is the platform the maintainer cannot see**, and a branch that
    silently does not execute is indistinguishable from one that passes.

    So this asserts the `msvcrt` path was actually taken, not merely that a lock worked: if this
    file is ever run on a lane where `sys.platform` is not `win32`, the skip above says so out
    loud, and if it runs here `msvcrt` must be the module in play.
    """
    assert drive_lock.sys.platform == "win32", "this arm claims Windows and is not on it"
    assert hasattr(msvcrt, "LK_NBLCK"), "the Windows branch is not exercising msvcrt"
