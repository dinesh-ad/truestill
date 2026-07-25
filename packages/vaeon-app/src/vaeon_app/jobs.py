"""Background jobs for long operations, streamed to the browser over SSE.

A job runs a target ``fn(progress, cancel)`` on a worker thread. ``progress(done, total)`` and
terminal events are pushed onto a thread-safe queue; the SSE endpoint drains that queue as
``text/event-stream`` frames. ``cancel`` is a ``threading.Event`` the core ops check between
items (a cancelled run is safe -- vaeon is copy-only and resumable).
"""

from __future__ import annotations

import json
import queue
import threading
import uuid
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from typing import Any

from vaeon_core.progress import ProgressCallback

#: A job target receives a progress callback and a cancel event, and returns a JSON-able summary.
JobTarget = Callable[[ProgressCallback, threading.Event], Any]

_SENTINEL_DONE = "done"
_SENTINEL_ERROR = "error"


@dataclass(slots=True)
class Job:
    id: str
    cancel: threading.Event = field(default_factory=threading.Event)
    events: queue.Queue[dict[str, Any]] = field(default_factory=queue.Queue)
    status: str = "running"
    summary: Any = None


class JobManager:
    """Registry of running/finished jobs. In-memory, single-process (a local app has one user)."""

    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def start(self, target: JobTarget) -> str:
        job = Job(id=uuid.uuid4().hex)
        with self._lock:
            self._jobs[job.id] = job

        def run() -> None:
            def progress(done: int, total: int) -> None:
                job.events.put({"type": "progress", "done": done, "total": total})

            try:
                summary = target(progress, job.cancel)
                job.status = "cancelled" if job.cancel.is_set() else "done"
                job.summary = summary
                job.events.put({"type": _SENTINEL_DONE, "status": job.status, "summary": summary})
            except Exception as exc:
                job.status = "error"
                job.events.put({"type": _SENTINEL_ERROR, "message": str(exc)})

        threading.Thread(target=run, daemon=True).start()
        return job.id

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
