"""An SSE reader with nothing left to read must return, not pin a worker thread forever.

**The defect these were written against, measured before anything was changed.**
``JobManager.stream`` drained the job queue with a timeout-less ``queue.Queue.get()`` inside a
**synchronous** generator. Two consequences, both reproduced:

1. ``queue.Queue`` hands each event to exactly ONE consumer. A job's terminal event is put once,
   so a **second** reader of the same job - which is what a page reload or an ``EventSource``
   reconnect produces - blocked forever with no producer left to wake it.
2. Starlette runs a sync generator in a worker thread, and a thread blocked in ``get()`` cannot be
   cancelled. uvicorn's graceful shutdown waits for the in-flight request, so **the server thread
   never died**: measured at *still alive 20.00 s after* ``should_exit``, with the client already
   disconnected. In the e2e harness that thread is what ``RetiringServers._sweep()`` waits on, so
   a leaked server can never be reclaimed and every later test pays ``_join_one``'s 10 s join.

⚠ **This is a latent defect, and it is NOT established as the cause of the `(ado)` WebKit tail.**
Instrumenting a real run of `test_ui_regressions.py` - 31 tests, both engines - showed **zero**
live-thread growth, so the suite does not trigger it locally. These guards are here because the
defect is real on its own evidence, not because they close `(ado)`.

**Why a heartbeat rather than a shorter block.** A periodic SSE comment frame (``: ping``) is the
standard keepalive: comment lines are ignored by every ``EventSource`` client, so no client changes,
and the write is what lets the server notice a client that has gone away.
"""

from __future__ import annotations

import socket
import threading
import time
from typing import Any

import pytest
import uvicorn
from starlette.applications import Starlette
from starlette.responses import StreamingResponse
from starlette.routing import Route
from truestill_app.jobs import DriveRef, JobManager

#: Long enough that a correct implementation cannot pass by being slow, short enough that a
#: regression fails the suite in seconds rather than hanging it.
_PATIENCE = 6.0


def _drive() -> list[DriveRef]:
    return [DriveRef(key="path:/tmp/sse-guard", label="Guard")]


def _finished_job(jobs: JobManager) -> str:
    """A job that has run to completion, with its terminal event already on the queue."""

    def target(_progress: Any, _cancel: Any) -> dict[str, Any]:
        return {"ok": True}

    job_id = jobs.start(target, drives=_drive(), operation="guard", mutating=False)
    assert isinstance(job_id, str), job_id
    deadline = time.monotonic() + _PATIENCE
    while jobs.get(job_id) is not None and jobs.get(job_id).status == "running":  # type: ignore[union-attr]
        if time.monotonic() > deadline:  # pragma: no cover - a hung target, not this guard
            pytest.fail("the probe job never finished")
        time.sleep(0.01)
    return job_id


def _drain(stream: Any, sink: list[bytes]) -> threading.Thread:
    def run() -> None:
        for frame in stream:
            sink.append(frame)

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return thread


def test_a_second_reader_of_one_job_is_answered_rather_than_blocked() -> None:
    """GUARD 1. The page-reload case: the terminal event went to whoever read it first.

    A `queue.Queue` event is delivered once. The second reader must still be told how the job
    ended - blocking it is what pinned a thread, and returning silently would leave the browser
    with a spinner and no outcome, which is the §9 failure this repo already refuses elsewhere.
    """
    jobs = JobManager()
    job_id = _finished_job(jobs)

    first = list(jobs.stream(job_id))
    assert first, "the first reader got no frames at all"

    second: list[bytes] = []
    thread = _drain(jobs.stream(job_id), second)
    thread.join(timeout=_PATIENCE)

    assert not thread.is_alive(), (
        f"a second reader of job {job_id} was still blocked after {_PATIENCE}s. Its terminal "
        "event was consumed by the first reader and nothing will ever wake it - this is the read "
        "that pins a worker thread, and through it a uvicorn server that can never shut down."
    )
    payload = b"".join(second)
    assert b"data:" in payload, (
        "the second reader returned without saying how the job ended. A reader that is answered "
        f"with silence leaves the screen with no outcome. Frames: {second!r}"
    )


def test_a_stream_nobody_is_reading_lets_its_server_shut_down() -> None:
    """GUARD 2. The measured leak, end to end: a disconnected client and a real uvicorn.

    Serves the real `JobManager.stream` through a real `StreamingResponse`, opens the request on a
    raw socket, drops the socket, and asks the server to stop. A generator that never comes up for
    air keeps `server.run()` from returning - and `RetiringServers` reclaims a server by exactly
    that thread going dead.
    """
    jobs = JobManager()
    job_id = _finished_job(jobs)
    # Consume the terminal event, so the request below is the blocked second reader.
    assert list(jobs.stream(job_id))

    def events(_request: Any) -> StreamingResponse:
        return StreamingResponse(jobs.stream(job_id), media_type="text/event-stream")

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]

    server = uvicorn.Server(
        uvicorn.Config(
            Starlette(routes=[Route("/events", events)]), log_level="error", lifespan="off"
        )
    )
    thread = threading.Thread(target=lambda: server.run(sockets=[sock]), daemon=True)
    thread.start()
    deadline = time.monotonic() + _PATIENCE
    while not server.started:
        if time.monotonic() > deadline:  # pragma: no cover - the probe server failed to boot
            pytest.fail("the probe server did not start")
        time.sleep(0.05)

    raw = socket.create_connection(("127.0.0.1", port))
    raw.sendall(f"GET /events HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\n\r\n".encode())
    time.sleep(0.5)  # the request is in flight and the generator is reading
    raw.close()  # the tab closes

    server.should_exit = True
    thread.join(timeout=_PATIENCE)
    alive = thread.is_alive()
    if not alive:
        sock.close()

    assert not alive, (
        f"the server thread was still alive {_PATIENCE}s after should_exit, with no client "
        "attached. RetiringServers._sweep() reclaims a server by thread.is_alive() going false, "
        "so this one is never reclaimed: _pending grows past LIMIT = 8 and every later test pays "
        "a 10 s join."
    )
