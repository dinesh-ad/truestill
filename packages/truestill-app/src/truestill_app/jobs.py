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

from truestill_core.catalog_busy import (
    CATALOG_BUSY_CODE,
    CATALOG_BUSY_MESSAGE,
    CATALOG_UNWRITABLE_CODE,
    catalog_unwritable_message,
    is_catalog_busy,
    is_catalog_unwritable,
)
from truestill_core.drive_lock import DriveBusyError, DriveLock
from truestill_core.progress import Progress, ProgressCallback

#: A job target receives a progress callback and a cancel event, and returns a JSON-able summary.
#: Heterogeneous return shapes (organize, migrate, verify, backup, …) keep ``JobTarget`` as
#: ``Any``. For dict summaries, :meth:`JobManager.start` always injects ``elapsed_seconds`` at
#: runtime; service TypedDicts declare that key ``NotRequired`` rather than inventing a shared
#: intersection type jobs cannot enforce across every target.
JobTarget = Callable[[ProgressCallback, threading.Event], Any]

_SENTINEL_DONE = "done"
_SENTINEL_ERROR = "error"

#: How long a reader parks on the queue before emitting a keepalive and looking around.
#:
#: Not tuned for latency - a queued event wakes the read immediately, so this costs a real job
#: nothing. It is the interval at which an *idle* stream becomes interruptible, and so the bound
#: on how long a dead one can hold a worker thread. One second keeps a stranded reader's cost
#: near zero while staying far under any proxy idle timeout a keepalive normally guards against.
_HEARTBEAT_SECONDS = 1.0

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
    #: The terminal event, kept after it has been put on the queue.
    #:
    #: **A queue delivers each event to exactly one consumer**, so the terminal event wakes
    #: whichever reader happens to take it and no other. Keeping it here is what lets a SECOND
    #: reader - a page reload, an ``EventSource`` reconnect - be told how the job ended instead of
    #: waiting on a producer that has already finished. ⚠ Written **after** ``status``, and
    #: ``stream`` reads *this* rather than ``status`` for exactly that reason: ``status`` is set
    #: while the summary is still being built, so a reader that trusted it could return before the
    #: terminal event existed.
    terminal: dict[str, Any] | None = None


def _hold_across_processes(held: Sequence[DriveRef]) -> list[DriveLock]:
    """Take every drive against other processes, or give back what was taken and raise. `(aaw)`

    **All-or-nothing, like the in-process claim above it.** A job holding two of three drives is
    a job that cannot run and a drive nobody else can use.
    """
    taken: list[DriveLock] = []
    try:
        for drive in held:
            lock = DriveLock(drive.key, drive.label, operation="a Truestill operation")
            lock.acquire()
            taken.append(lock)
    except DriveBusyError:
        for lock in taken:
            lock.release()
        raise
    return taken


def _busy_payload_for_other_process(busy: DriveBusyError) -> DriveBusyPayload:
    """The same refusal shape, for a holder this process cannot see. `(aaw)`

    ⚠ **Reuses `DriveBusyPayload` deliberately.** To the person clicking, *"something else is
    using this drive"* is one situation; which process holds it is our problem, not theirs, and a
    second payload type would make every consumer learn a distinction that changes nothing they
    can do. The holder's identity is in the message, which is where `(aaw)` ruled it belongs.
    """
    holder = busy.holder
    return {
        "ok": False,
        "error": str(busy),
        "code": DRIVE_BUSY_CODE,
        # ⚠ **No job id, because there is no job of ours to name.** The holder is another
        # process - possibly the CLI - so `job_id` is empty rather than invented: a client that
        # polls a fabricated id would wait for something that never existed.
        "operation": holder.operation if holder is not None else "operation",
        "drive_label": busy.label,
        "job_id": "",
    }


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

    def _release_drives(self, keys: Sequence[str], job_id: str) -> None:
        """Release this job's claim on every drive it held. Idempotent.

        ⚠ **The job itself stays in `_jobs`.** A finished job must still be retrievable - that is
        what `get` is for, and what the retirement cap manages. Removing it here made
        `manager.get(...)` answer `None` for a job that had completed, and every poller waited out
        its own timeout instead of seeing the result.
        """
        with self._lock:
            for key in keys:
                current = self._occupied.get(key)
                if current is not None and current.job_id == job_id:
                    del self._occupied[key]

    def _abandon(self, keys: Sequence[str], job_id: str) -> None:
        """Undo `start` entirely, for a job that was never allowed to run.

        The drives go back **and** the job record goes, because a job that never started must
        leave no trace - unlike one that finished, which `_release_drives` leaves retrievable.
        """
        self._release_drives(keys, job_id)
        with self._lock:
            self._jobs.pop(job_id, None)

    def start(
        self,
        target: JobTarget,
        *,
        drives: Sequence[DriveRef],
        operation: str,
        mutating: bool,
    ) -> str | DriveBusyPayload:
        """Start ``target`` on a worker thread, or refuse if any named drive is already busy.

        Acquires every drive in ``drives`` atomically (all-or-nothing). Two jobs on different
        drives run concurrently; a second job on an occupied drive is refused with
        :class:`DriveBusyPayload` - never queued behind the first.

        ⚠ **``mutating`` is REQUIRED and has no default**, and that is `(aaw)`'s ruling rather
        than an oversight. It says whether this job writes files on the drive, and so whether the
        **cross-process** lock is taken as well as this manager's in-process one. Neither default
        is safe: `False` would silently skip the lock the next time a writing route is added, and
        `True` would make a preview refuse with nobody deciding. A caller that says nothing fails
        at the call, and `test_every_job_declares_whether_it_mutates` fails before that ships.

        ⚠ **Not derived from ``operation``.** A string used as a control is one rename away from
        a lock that stops firing - `"organize"` and `"organize preview"` differ by one word.
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

        # ⚠ **Taken AFTER the in-process claim and OUTSIDE its lock.** After, so a second tab in
        # this app is refused by the cheap check rather than by a syscall; outside, because
        # acquiring touches the filesystem and holding `self._lock` across that would make every
        # other route wait on a disk. `(aaw)`
        try:
            cross_process = _hold_across_processes(held) if mutating else []
        except DriveBusyError as busy:
            # Give back everything, including the in-process claim: a job that cannot start must
            # leave no trace, or the drive stays occupied by a job that never ran.
            self._abandon(keys, job.id)
            return _busy_payload_for_other_process(busy)

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
                    #
                    # ⚠ A catalog failure that is not busy is no better served by `str(exc)`:
                    # "disk I/O error" and "attempt to write a readonly database" describe
                    # SQLite's internals and name no action either. It gets its own wording and
                    # its own code, from core, so this surface and the CLI keep answering the
                    # same condition the same way. `(afe)`
                    #
                    # ⚠ **Three cases, not two, and this `except` catches `Exception`.** A first
                    # cut here reworded everything that was not busy, which turned every job
                    # failure in the product -- a backup with too little space, a bad path --
                    # into "the library catalog could not be written" -- including a missing
                    # table, which is a bug of ours. `is_catalog_unwritable` names the codes that
                    # are actually about reaching or storing the catalog; everything else keeps
                    # its own class and message exactly as before. `(afe)`
                    if is_catalog_busy(exc):
                        message, code = CATALOG_BUSY_MESSAGE, CATALOG_BUSY_CODE
                    elif is_catalog_unwritable(exc):
                        message, code = catalog_unwritable_message(exc), CATALOG_UNWRITABLE_CODE
                    else:
                        message, code = str(exc), type(exc).__name__
                    terminal = {
                        "type": _SENTINEL_ERROR,
                        "message": message,
                        "code": code,
                    }
            finally:
                # Always release, including cancel and exception - a stuck lock is worse than
                # the overlapping-run bug this guard exists to stop. Release *before* the
                # terminal SSE event so a client that sees "done" can start the next job
                # without racing the unlock.
                self._release_drives(keys, job.id)
                # ⚠ **Released HERE, not when `start` returned.** The lock is bound to a file
                # descriptor, so it lives exactly as long as this object holds it - and the work
                # runs on this thread, after `start` has already handed back a job id. `(aaw)`
                for lock in cross_process:
                    lock.release()
                if terminal is not None:
                    # Recorded before it is queued: a reader that comes up for air between these
                    # two statements must not conclude there is nothing left to wait for.
                    job.terminal = terminal
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
        """Yield SSE frames for a job until a terminal event.

        **Comes up for air rather than blocking outright, and that is a leak fix rather than a
        style preference.** This is a *synchronous* generator, so Starlette runs it in a worker
        thread - and a thread parked in a timeout-less ``queue.Queue.get()`` cannot be cancelled.
        uvicorn's graceful shutdown waits for the in-flight request, so one such read kept a
        server thread alive **20.00 s after ``should_exit`` with the client already gone**, and it
        would have stayed alive indefinitely. ``test_a_dead_sse_reader_does_not_pin_the_server``
        holds both halves.

        On each timeout it emits an SSE **comment** frame. Comment lines are ignored by every
        ``EventSource`` client, so this needs no client change; its job is to be a write, because
        a write is what discovers a client that has gone away.
        """
        job = self.get(job_id)
        if job is None:
            yield b'event: error\ndata: {"message": "unknown job"}\n\n'
            return
        while True:
            try:
                event = job.events.get(timeout=_HEARTBEAT_SECONDS)
            except queue.Empty:
                # Nothing queued. If the job has already published its terminal event, this reader
                # is a SECOND one - the queue handed that event to whoever took it first - so
                # answer from the record instead of waiting for a producer that has finished.
                terminal = job.terminal
                if terminal is not None:
                    yield f"data: {json.dumps(terminal)}\n\n".encode()
                    return
                yield b": ping\n\n"
                continue
            yield f"data: {json.dumps(event)}\n\n".encode()
            if event["type"] in (_SENTINEL_DONE, _SENTINEL_ERROR):
                return
