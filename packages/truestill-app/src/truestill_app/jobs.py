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
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Final, Literal, TypedDict

from truestill_core.catalog_busy import (
    CATALOG_BUSY_CODE,
    CATALOG_BUSY_MESSAGE,
    CATALOG_UNWRITABLE_CODE,
    catalog_unwritable_message,
    is_catalog_busy,
    is_catalog_unwritable,
)
from truestill_core.drive_lock import DriveBusyError, DriveLock
from truestill_core.organizer import RunStoppedError
from truestill_core.progress import Progress, ProgressCallback

#: A job target receives a progress callback and a cancel event, and returns a JSON-able summary.
#:
#: ⚠ **THIS WAS `Any` UNTIL 2026-08-25, AND THE REASON RECORDED FOR IT ANSWERED A DIFFERENT
#: QUESTION.** It read: *"Heterogeneous return shapes (organize, migrate, verify, backup, …) keep
#: ``JobTarget`` as ``Any`` ... rather than inventing a shared **intersection** type jobs cannot
#: enforce across every target."*
#:
#: **That is correct about an intersection and does not apply to a parameter.** An intersection
#: would claim every target returns some common shape - which is false, and unenforceable. A
#: **parameterised** alias claims nothing shared: ``JobTarget[BakeSummary]`` describes one
#: target's own type and says nothing about any other. The objection was answered before it was
#: raised, against a construct nobody proposed. `(ahn)` stage 1.
#:
#: The rest of the old note still holds: :meth:`JobManager.start` injects ``elapsed_seconds`` at
#: runtime for dict summaries, and service TypedDicts declare that key ``NotRequired``.
#:
#: ⚠ **WHAT THIS DOES NOT DO, said here so nobody reads more into it.** It types the **producer**
#: side - each factory declares what its target returns, and mypy checks the inner function
#: against it. It does **not** type the wire: the manager holds jobs of every shape in one
#: registry, so ``T`` is discharged at :meth:`start` and :attr:`Job.summary` is what the browser
#: is handed. Closing that end is a spec and generated types, which is `(ahn)` stages 4 and 5.
type JobTarget[T] = Callable[[ProgressCallback, threading.Event], T]

_SENTINEL_DONE: Final = "done"
_SENTINEL_ERROR: Final = "error"


class ProgressFrame(TypedDict):
    """One tick on the wire: `Progress` as the browser receives it. `(ahn)` stage B."""

    type: Literal["progress"]
    done: int
    total: int
    phase: str
    item: str
    tally: dict[str, int]


class DoneFrame(TypedDict):
    """The terminal frame of a job that returned. `(ahn)` stage B.

    ⚠ **`summary` is `object` here, and the union it stands for is DERIVED, never listed.** One
    registry holds every job shape, so `T` is discharged at :meth:`JobManager.start` exactly as
    `Job.summary` already says. The wire union is the thirteen factories' `JobTarget[T]` members,
    read from their annotations by `scripts/payload_contract.py`'s `job_summary_types` - a hand
    list here would be a second definition of what stage A made derivable, and stage D emits the
    `oneOf` from that derivation into `openapi.json`.
    """

    type: Literal["done"]
    status: str
    summary: object


class ErrorFrame(TypedDict):
    """The terminal frame of a job that raised. `(ahn)` stage B."""

    type: Literal["error"]
    message: str
    code: str


class UnknownJobFrame(TypedDict):
    """The one frame sent for a job id nobody knows, under `event: error`. `(ahn)` stage B.

    ⚠ **Not queued, and on the wire** - it was a hand-written byte string until 2026-09-03, so no
    census that read the queue could see it. Built through `json.dumps` now; the bytes are
    unchanged.
    """

    message: str


#: Everything the queue can carry. ⚠ Until 2026-09-03 it carried ``dict[str, Any]`` and P91's
#: ruling that the frames were *"three fixed shapes"* was assumed, not checked: 4a typed every
#: route payload and never looked at the stream. `(ahn)` stage B.
type Frame = ProgressFrame | DoneFrame | ErrorFrame
type TerminalFrame = DoneFrame | ErrorFrame

#: The three terminal statuses a job that RETURNED can carry. A job that raised is `type: error`
#: and has no status of its own.
#:
#: ⚠ **THREE, BECAUSE TWO WERE MEASURED TO BE INSUFFICIENT.** Until 2026-09-01 this was derived
#: from control flow alone - `"cancelled" if cancel.is_set() else "done"` - so it asked *did the
#: target return*, never *what did it return*. Soak twelve's app half measured `organize` onto a
#: drive that vanished: **1,130 of 1,324 files failed and the terminal event said
#: `status: "done"`.** A run that lost 85% of its work reported success. `(aiq)`
#:
#: **The field reached three states independently, twice, and both times by way of the same
#: mistake.** BackInTime ignored `rsync`'s exit 23, switched to treating it as an error, and then
#: *every* snapshot reported failure; their own remedy was *"Introduce a new snapshot result state
#: 'Warning' (currently we have only OK and with errors)"* (#1587). Proxmox arrived at
#: *"Backup job finished with errors"* as an outcome distinct from both. The trap runs in both
#: directions: success hides the shortfall, and blanket failure teaches people to ignore the
#: status entirely.
#:
#: 🔑 **THE LINE IS THE CLI'S, NOT A NEW ONE.** `truestill` already exits **1** for exactly this
#: state - `(air)` quotes it as *"finished, but something is wrong with the library"* - and
#: `_cmd_verify` returns 1 on `missing or mismatch or unreadable`, which is a **finding** rather
#: than work it could not do. So the third state is not "the run broke": it is **the run finished
#: and the library is not clean**, and this makes the app say what the CLI already says.
STATUS_DONE: Final = "done"
STATUS_CANCELLED: Final = "cancelled"
STATUS_COMPLETED_WITH_ERRORS: Final = "completed_with_errors"

#: The key a summary sets to declare its own verdict. **The SERVICE decides, never this module.**
#:
#: ⚠ **This is why the fix was not one line, and the reason is layering rather than caution.**
#: There are thirteen job shapes and "not clean" is spelled differently in each: `failed` for
#: organize / backup / bake, `missing`/`mismatch`/`unreadable` for verify, `stopped`/`refused` for
#: migrate and undo, `applied is False` for an interrupted rename. `jobs.py` holds every shape in
#: one registry and discharges ``T`` at :meth:`start`, so it **cannot** know which key means what
#: - and a table here would put thirteen services' vocabulary in the one module that is supposed
#: to be blind to it.
#:
#: **Absent means clean, and for most shapes that is correct rather than a default.** A preview
#: computes and returns; there is no partial state for it to be in. What absence must never hide
#: is a *mutating* shape that forgot - which is what
#: `test_a_run_with_failures_is_not_done.py` pins, shape by shape.
FINISHED_CLEAN: Final = "finished_clean"

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


def _terminal_status(summary: object, *, cancelled: bool) -> str:
    """The status of a job that RETURNED, from what it returned rather than from how it ended.

    ⚠ **CANCELLED WINS OVER UNCLEAN, deliberately.** A run the user stopped may also have failed
    files, and both are true - but *why it ended* is the more specific fact and the one the person
    already knows they caused. `(aiq)` records that the cancel path *"returns normally, carries the
    full summary, and already renders 'Stopped - N files organized before you stopped it'"* - that
    half was correct before this change and is not disturbed by it.

    **Only a `Mapping` can carry a verdict.** Every mutating target returns a `TypedDict`; the
    check is `isinstance(..., Mapping)` for the same reason :meth:`start` uses it to inject
    ``elapsed_seconds`` - the runtime question has always been "is this a dict", not "is this one
    of thirteen listed types".
    """
    if cancelled:
        return STATUS_CANCELLED
    if isinstance(summary, Mapping) and summary.get(FINISHED_CLEAN) is False:
        return STATUS_COMPLETED_WITH_ERRORS
    return STATUS_DONE


def _underlying(exc: Exception) -> Exception:
    """The failure a job should be judged on: `RunStoppedError`'s cause, or ``exc`` itself.

    **One layer, deliberately.** `RunStoppedError` is raised by `organizer.execute` with the
    original as its direct cause and nothing else wraps it here, so a deeper walk would be
    guessing at chains this code did not build - and could reach past a wrapper that was
    *meant* to be the answer.
    """
    if isinstance(exc, RunStoppedError) and isinstance(exc.__cause__, Exception):
        return exc.__cause__
    return exc


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


class JobStarted(TypedDict):
    """The body every job-start route returns once the work is under way. `(ahn)` stage 4a.

    ⚠ **One key, and it was the largest untyped payload in the app** - built as a dict literal in
    `_start_drive_job` and returned by **15** job-start sites, so a spec could describe none of
    them. The shape is unchanged: `{"job_id": "..."}` is what it was and what it is, which is why
    typing it is not a screen change.
    """

    job_id: str


class CatalogBusyPayload(TypedDict):
    """The 503 a request gets when another process holds the catalog. `(ahn)` stage 4a.

    Beside :class:`DriveBusyPayload` because they are the same kind of thing - a refusal carrying
    a machine-readable ``code`` next to the sentence a person reads - and the codes are the pair a
    client branches on.
    """

    error: str
    code: Literal["CatalogBusy"]


@dataclass(slots=True)
class ExclusiveClaim:
    """A synchronous route's hold on the exclusion a job would get. Release in ``finally``."""

    manager: JobManager
    keys: list[str]
    token: str
    cross: list[DriveLock]

    def release(self) -> None:
        for lock in self.cross:
            lock.release()
        self.manager._release_drives(self.keys, self.token)


@dataclass(slots=True)
class _Occupant:
    job_id: str
    operation: str
    drive_label: str


@dataclass(slots=True)
class Job:
    id: str
    cancel: threading.Event = field(default_factory=threading.Event)
    events: queue.Queue[Frame] = field(default_factory=queue.Queue)
    status: str = "running"
    #: ⚠ **``object``, not ``Any``** (`(ahn)` stage 1). One registry holds every job shape, so this
    #: cannot carry the target's ``T``; but ``object`` makes that a narrowing anybody who later
    #: reads it must perform, where ``Any`` let it be used as anything without a word. Nothing
    #: reads it today - checked: the only references are the two writes below.
    summary: object = None
    #: The terminal event, kept after it has been put on the queue.
    #:
    #: **A queue delivers each event to exactly one consumer**, so the terminal event wakes
    #: whichever reader happens to take it and no other. Keeping it here is what lets a SECOND
    #: reader - a page reload, an ``EventSource`` reconnect - be told how the job ended instead of
    #: waiting on a producer that has already finished. ⚠ Written **after** ``status``, and
    #: ``stream`` reads *this* rather than ``status`` for exactly that reason: ``status`` is set
    #: while the summary is still being built, so a reader that trusted it could return before the
    #: terminal event existed.
    terminal: TerminalFrame | None = None


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
            f"{occupant.drive_label} is busy: {occupant.operation} is already running. "
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

    def claim(
        self,
        *,
        drives: Sequence[DriveRef],
        operation: str,
        mutating: bool,
    ) -> DriveBusyPayload | ExclusiveClaim:
        """The exclusion HALF of :meth:`start`, for a fast synchronous route. `(agu)`

        The app's clean-empty apply deleted folders through a bare `run_in_threadpool` - no
        in-process occupancy, no `(aaw)` cross-process lock - while the CLI declared the same
        command locked. The requirement was always the EXCLUSION; the job machinery (worker
        thread, SSE events, job record) was one client of it, and wrapping a sub-second
        synchronous delete in a job would have changed what the screen receives for lock
        reasons only. So the claim is factored out: same occupancy dict, same refusal wording,
        same DriveLock, no job. A claim that cannot be taken returns the same
        :class:`DriveBusyPayload` a refused job start does, so the screen needs no new state.

        The caller MUST release - hold it in a ``try/finally`` around the synchronous work.
        """
        held = _unique_drives(drives)
        assert held, "jobs.claim requires at least one drive"
        token = uuid.uuid4().hex
        with self._lock:
            for drive in held:
                occupant = self._occupied.get(drive.key)
                if occupant is not None:
                    return _busy_payload(occupant, drive.label)
            for drive in held:
                self._occupied[drive.key] = _Occupant(
                    job_id=token, operation=operation, drive_label=drive.label
                )
            keys = [drive.key for drive in held]
        try:
            cross = _hold_across_processes(held) if mutating else []
        except DriveBusyError as busy:
            self._release_drives(keys, token)
            return _busy_payload_for_other_process(busy)
        return ExclusiveClaim(manager=self, keys=keys, token=token, cross=cross)

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
        target: JobTarget[object],
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
            terminal: TerminalFrame | None = None

            def progress(update: Progress) -> None:
                frame: ProgressFrame = {
                    "type": "progress",
                    "done": update.done,
                    "total": update.total,
                    "phase": update.phase,
                    "item": update.item,
                    "tally": dict(update.tally),
                }
                job.events.put(frame)

            try:
                try:
                    summary = target(progress, job.cancel)
                    job.status = _terminal_status(summary, cancelled=job.cancel.is_set())
                    # Measured here rather than in each op: every job wants it, and the job is the
                    # only layer that sees the whole run including setup. Runtime guarantee for
                    # dict summaries only -- see JobTarget docstring (NotRequired on service types).
                    if isinstance(summary, dict):
                        # Named for what it is: the target's mapping plus one key. The service
                        # TypedDicts declare `elapsed_seconds` NotRequired for this line.
                        timed: dict[str, object] = {
                            **summary,
                            "elapsed_seconds": round(time.monotonic() - started, 1),
                        }
                        summary = timed
                    job.summary = summary
                    done: DoneFrame = {
                        "type": _SENTINEL_DONE,
                        "status": job.status,
                        "summary": summary,
                    }
                    terminal = done
                except Exception as exc:
                    job.status = "error"
                    # ⚠ **CLASSIFIED ON THE CAUSE, because `organizer.execute` now wraps. `(agj)`**
                    #
                    # `is_catalog_busy` is an `isinstance` check and does not walk the chain, so a
                    # wrapper would make it answer "not busy" about a catalog that is - and the
                    # user would get SQLite's "database is locked" instead of the sentence written
                    # for exactly that situation. **It is reachable**: `record_inplace_move` is a
                    # bare catalog write inside `execute`'s loop, unguarded by `_record_or_stop`.
                    #
                    # This is `(agi)`'s lesson on the other surface - a classifier that reads only
                    # the outermost exception is inert the moment anyone wraps one. `str()` is
                    # unchanged either way, because `RunStoppedError` reports its cause's sentence.
                    failure = _underlying(exc)
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
                    if is_catalog_busy(failure):
                        message, code = CATALOG_BUSY_MESSAGE, CATALOG_BUSY_CODE
                    elif is_catalog_unwritable(failure):
                        message, code = catalog_unwritable_message(failure), CATALOG_UNWRITABLE_CODE
                    else:
                        message, code = str(failure), type(failure).__name__
                    failed: ErrorFrame = {
                        "type": _SENTINEL_ERROR,
                        "message": message,
                        "code": code,
                    }
                    terminal = failed
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
            unknown: UnknownJobFrame = {"message": "unknown job"}
            yield f"event: error\ndata: {json.dumps(unknown)}\n\n".encode()
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
