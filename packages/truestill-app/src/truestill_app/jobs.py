"""Background jobs for long operations, streamed to the browser over SSE.

A job runs a target ``fn(progress, cancel)`` on a worker thread. ``progress(done, total)`` and
terminal events are pushed onto a thread-safe queue; the SSE endpoint drains that queue as
``text/event-stream`` frames. ``cancel`` is a ``threading.Event`` the core ops check between
items (a cancelled run is safe -- truestill is copy-only and resumable).

**One operation per drive.** :meth:`JobManager.start` takes the drive(s) a job will touch and
refuses a second start on an occupied drive with an actionable message. The lock is process-
local and in-memory: a server restart clears it (there is no on-disk stale lock). Release is
unconditional in a ``finally`` on the worker thread - success, cancel, and exception alike -
so a stuck lock cannot outlive the job that held it.
"""

from __future__ import annotations

import json
import queue
import threading
import time
import uuid
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal, TypedDict

from truestill_core.catalog_busy import CATALOG_BUSY_CODE, CATALOG_BUSY_MESSAGE, is_catalog_busy
from truestill_core.progress import Progress, ProgressCallback

#: A job target receives a progress callback and a cancel event, and returns a JSON-able summary.
#: Heterogeneous return shapes (organize, migrate, verify, backup, …) keep ``JobTarget`` as
#: ``Any``. For dict summaries, :meth:`JobManager.start` always injects ``elapsed_seconds`` at
#: runtime; service TypedDicts declare that key ``NotRequired`` rather than inventing a shared
#: intersection type jobs cannot enforce across every target.
JobTarget = Callable[[ProgressCallback, threading.Event], Any]

_SENTINEL_DONE = "done"
_SENTINEL_ERROR = "error"

DRIVE_BUSY_CODE: Literal["DriveBusy"] = "DriveBusy"

#: Completed jobs kept per process, newest first. See `_retire_finished` (F17).
MAX_RETAINED_JOBS = 50


@dataclass(frozen=True, slots=True)
class DriveRef:
    """A drive a job will touch - identity for the lock, label for the refusal message.

    ``key`` is ``uuid:<marker>`` when the path is a connected truestill drive, otherwise
    ``path:<resolved>`` so an unmarked organize/ingest destination is still serialized.
    """

    key: str
    label: str


class DriveBusyPayload(TypedDict):
    """Second start refused - never queued, never raced (backlog oo re-entrancy)."""

    ok: Literal[False]
    error: str
    code: Literal["DriveBusy"]
    operation: str
    drive_label: str
    job_id: str


@dataclass(slots=True)
class _Occupant:
    job_id: str
    operation: str
    drive_label: str


@dataclass(slots=True)
class Job:
    id: str
    cancel: threading.Event = field(default_factory=threading.Event)
    events: queue.Queue[dict[str, Any]] = field(default_factory=queue.Queue)
    status: str = "running"
    summary: Any = None


def _busy_payload(occupant: _Occupant, contested_label: str) -> DriveBusyPayload:
    return {
        "ok": False,
        "error": (
            f"A {occupant.operation} is already running on {occupant.drive_label}. "
            f"Wait for it to finish, or cancel it, before starting another operation "
            f"on {contested_label}."
        ),
        "code": DRIVE_BUSY_CODE,
        "operation": occupant.operation,
        "drive_label": occupant.drive_label,
        "job_id": occupant.job_id,
    }


def _unique_drives(drives: Sequence[DriveRef]) -> list[DriveRef]:
    """Deduplicate by key (backup of a drive onto itself must not double-lock)."""
    seen: dict[str, DriveRef] = {}
    for drive in drives:
        if drive.key not in seen:
            seen[drive.key] = drive
    return list(seen.values())


class JobManager:
    """Registry of running/finished jobs. In-memory, single-process (a local app has one user)."""

    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._finished: list[str] = []
        self._occupied: dict[str, _Occupant] = {}
        self._lock = threading.Lock()

    def start(
        self,
        target: JobTarget,
        *,
        drives: Sequence[DriveRef],
        operation: str,
    ) -> str | DriveBusyPayload:
        """Start ``target`` on a worker thread, or refuse if any named drive is already busy.

        Acquires every drive in ``drives`` atomically (all-or-nothing). Two jobs on different
        drives run concurrently; a second job on an occupied drive is refused with
        :class:`DriveBusyPayload` - never queued behind the first.
        """
        held = _unique_drives(drives)
        assert held, "jobs.start requires at least one drive"
        job = Job(id=uuid.uuid4().hex)
        with self._lock:
            for drive in held:
                occupant = self._occupied.get(drive.key)
                if occupant is not None:
                    return _busy_payload(occupant, drive.label)
            for drive in held:
                self._occupied[drive.key] = _Occupant(
                    job_id=job.id, operation=operation, drive_label=drive.label
                )
            self._jobs[job.id] = job
            self._retire_finished()
            keys = [drive.key for drive in held]

        def run() -> None:
            started = time.monotonic()
            terminal: dict[str, Any] | None = None

            def progress(update: Progress) -> None:
                job.events.put(
                    {
                        "type": "progress",
                        "done": update.done,
                        "total": update.total,
                        "phase": update.phase,
                        "item": update.item,
                        "tally": dict(update.tally),
                    }
                )

            try:
                try:
                    summary = target(progress, job.cancel)
                    job.status = "cancelled" if job.cancel.is_set() else "done"
                    # Measured here rather than in each op: every job wants it, and the job is the
                    # only layer that sees the whole run including setup. Runtime guarantee for
                    # dict summaries only -- see JobTarget docstring (NotRequired on service types).
                    if isinstance(summary, dict):
                        summary = {
                            **summary,
                            "elapsed_seconds": round(time.monotonic() - started, 1),
                        }
                    job.summary = summary
                    terminal = {
                        "type": _SENTINEL_DONE,
                        "status": job.status,
                        "summary": summary,
                    }
                except Exception as exc:
                    job.status = "error"
                    # The exception's class name travels with the message so the UI can answer a
                    # known situation with a next step. Matching on a class is stable; matching on
                    # message text would break the first time anyone rewords it.
                    #
                    # A catalog held by another process is the one failure whose own words are
                    # useless to the person reading them: `str(exc)` is "database is locked",
                    # which describes SQLite's internals and no action. It is also not a fault
                    # -- an `--apply` run in a terminal while the app is open is ordinary -- so
                    # it is reworded here rather than left to read as a crash. Recognition and
                    # wording come from core because the CLI answers the same condition and the
                    # two must not drift.
                    busy = is_catalog_busy(exc)
                    terminal = {
                        "type": _SENTINEL_ERROR,
                        "message": CATALOG_BUSY_MESSAGE if busy else str(exc),
                        "code": CATALOG_BUSY_CODE if busy else type(exc).__name__,
                    }
            finally:
                # Always release, including cancel and exception - a stuck lock is worse than
                # the overlapping-run bug this guard exists to stop. Release *before* the
                # terminal SSE event so a client that sees "done" can start the next job
                # without racing the unlock.
                with self._lock:
                    for key in keys:
                        current = self._occupied.get(key)
                        if current is not None and current.job_id == job.id:
                            del self._occupied[key]
                if terminal is not None:
                    job.events.put(terminal)

        threading.Thread(target=run, daemon=True).start()
        return job.id

    def _retire_finished(self) -> None:
        """Drop the oldest completed jobs past the cap. Call with ``self._lock`` held.

        Nothing removed a job before (audit F17): every run stayed in memory with its whole
        summary - folder maps, leftover-folder lists - for the life of the process. Only jobs
        that have reached a terminal state are dropped, so a running job and the SSE stream
        draining it are never pulled out from under a client.
        """
        finished = [jid for jid, job in self._jobs.items() if job.status != "running"]
        for jid in finished[: max(0, len(finished) - MAX_RETAINED_JOBS)]:
            del self._jobs[jid]

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def cancel(self, job_id: str) -> bool:
        job = self.get(job_id)
        if job is None:
            return False
        job.cancel.set()
        return True

    def stream(self, job_id: str) -> Iterator[bytes]:
        """Yield SSE frames for a job until a terminal event. Blocks on the job's queue."""
        job = self.get(job_id)
        if job is None:
            yield b'event: error\ndata: {"message": "unknown job"}\n\n'
            return
        while True:
            event = job.events.get()
            yield f"data: {json.dumps(event)}\n\n".encode()
            if event["type"] in (_SENTINEL_DONE, _SENTINEL_ERROR):
                return
