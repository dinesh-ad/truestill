"""Per-drive re-entrancy in JobManager (backlog oo): refuse, never queue, always release."""

from __future__ import annotations

import json
import threading
import time

import pytest
from truestill_app.jobs import DRIVE_BUSY_CODE, DriveRef, JobManager


def _ref(key: str, label: str) -> DriveRef:
    return DriveRef(key=key, label=label)


def _drain(mgr: JobManager, job_id: str, *, timeout: float = 2.0) -> None:
    """Wait until the job has published a terminal event (lock already released by then)."""
    deadline = time.monotonic() + timeout
    for frame in mgr.stream(job_id):
        if time.monotonic() > deadline:
            pytest.fail(f"job {job_id} did not finish within {timeout}s")
        if not frame.startswith(b"data:"):
            continue
        event = json.loads(frame[len(b"data:") :].decode().strip())
        if event["type"] in ("done", "error"):
            return
    pytest.fail(f"job {job_id} stream ended without a terminal event")


def _wait_until_free(mgr: JobManager, drive: DriveRef, *, timeout: float = 2.0) -> str:
    """Poll until a new start on ``drive`` is accepted (lock released)."""
    deadline = time.monotonic() + timeout

    def idle(_progress: object, _cancel: threading.Event) -> dict[str, bool]:
        return {"ok": True}

    while time.monotonic() < deadline:
        result = mgr.start(idle, drives=[drive], operation="probe", mutating=False)
        if isinstance(result, str):
            _drain(mgr, result)
            return result
        time.sleep(0.01)
    pytest.fail(f"drive {drive.label!r} stayed locked past {timeout}s")


def test_second_start_on_same_drive_is_refused_with_the_running_operation() -> None:
    """The overlapping-run bug: a second click must get a clear refusal, not a second job."""
    mgr = JobManager()
    hold = threading.Event()
    drive = _ref("uuid:A", "Drive A")

    def blocked(_progress: object, _cancel: threading.Event) -> dict[str, str]:
        hold.wait(timeout=5)
        return {"phase": "done"}

    first = mgr.start(blocked, drives=[drive], operation="migrate preview", mutating=False)
    assert isinstance(first, str)

    busy = mgr.start(blocked, drives=[drive], operation="migrate", mutating=False)
    assert isinstance(busy, dict)
    assert busy["ok"] is False
    assert busy["code"] == DRIVE_BUSY_CODE
    assert busy["job_id"] == first
    assert busy["operation"] == "migrate preview"
    assert "migrate preview" in busy["error"]
    assert "Drive A" in busy["error"]
    assert "Wait" in busy["error"]
    assert "cancel" in busy["error"]

    hold.set()
    _drain(mgr, first)
    _wait_until_free(mgr, drive)


def test_start_on_a_different_drive_succeeds_while_first_is_running() -> None:
    mgr = JobManager()
    hold_a = threading.Event()
    hold_b = threading.Event()
    drive_a = _ref("uuid:A", "Drive A")
    drive_b = _ref("uuid:B", "Drive B")

    def block_a(_progress: object, _cancel: threading.Event) -> dict[str, str]:
        hold_a.wait(timeout=5)
        return {"drive": "A"}

    def block_b(_progress: object, _cancel: threading.Event) -> dict[str, str]:
        hold_b.wait(timeout=5)
        return {"drive": "B"}

    first = mgr.start(block_a, drives=[drive_a], operation="verify", mutating=False)
    second = mgr.start(block_b, drives=[drive_b], operation="backup", mutating=False)
    assert isinstance(first, str)
    assert isinstance(second, str)
    assert first != second

    hold_a.set()
    hold_b.set()
    _drain(mgr, first)
    _drain(mgr, second)


def test_lock_releases_after_success() -> None:
    mgr = JobManager()
    drive = _ref("uuid:A", "Library")

    def quick(_progress: object, _cancel: threading.Event) -> dict[str, bool]:
        return {"ok": True}

    first = mgr.start(quick, drives=[drive], operation="organize preview", mutating=False)
    assert isinstance(first, str)
    _drain(mgr, first)
    second = _wait_until_free(mgr, drive)
    assert isinstance(second, str)
    assert second != first


def test_lock_releases_after_cancel() -> None:
    mgr = JobManager()
    drive = _ref("uuid:A", "Library")
    started = threading.Event()

    def until_cancelled(_progress: object, cancel: threading.Event) -> dict[str, str]:
        started.set()
        while not cancel.is_set():
            time.sleep(0.01)
        return {"status": "stopping"}

    job_id = mgr.start(until_cancelled, drives=[drive], operation="migrate", mutating=False)
    assert isinstance(job_id, str)
    assert started.wait(timeout=2)
    assert mgr.cancel(job_id) is True
    _drain(mgr, job_id)
    freed = _wait_until_free(mgr, drive)
    assert isinstance(freed, str)


def test_lock_releases_after_exception() -> None:
    mgr = JobManager()
    drive = _ref("uuid:A", "Library")

    def boom(_progress: object, _cancel: threading.Event) -> dict[str, bool]:
        msg = "simulated failure"
        raise RuntimeError(msg)

    job_id = mgr.start(boom, drives=[drive], operation="verify", mutating=False)
    assert isinstance(job_id, str)
    _drain(mgr, job_id)
    job = mgr.get(job_id)
    assert job is not None
    assert job.status == "error"
    freed = _wait_until_free(mgr, drive)
    assert isinstance(freed, str)


def test_backup_locks_both_drives_and_names_the_contested_one() -> None:
    """A backup occupies source and target; a migrate on either is refused."""
    mgr = JobManager()
    hold = threading.Event()
    source = _ref("uuid:SRC", "Library")
    target = _ref("uuid:TGT", "Backup B")

    def blocked(_progress: object, _cancel: threading.Event) -> dict[str, str]:
        hold.wait(timeout=5)
        return {"ok": "held"}

    backup = mgr.start(blocked, drives=[source, target], operation="backup", mutating=False)
    assert isinstance(backup, str)

    busy_on_source = mgr.start(
        blocked, drives=[source], operation="migrate preview", mutating=False
    )
    assert isinstance(busy_on_source, dict)
    assert busy_on_source["code"] == DRIVE_BUSY_CODE
    assert "backup" in busy_on_source["error"]
    assert "Library" in busy_on_source["error"]

    busy_on_target = mgr.start(blocked, drives=[target], operation="verify", mutating=False)
    assert isinstance(busy_on_target, dict)
    assert "Backup B" in busy_on_target["error"]

    hold.set()
    _drain(mgr, backup)
    _wait_until_free(mgr, source)
    _wait_until_free(mgr, target)
