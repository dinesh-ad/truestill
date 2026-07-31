"""Review sessions and finished jobs are bounded, and a stale id is answered (audit F17).

Two in-memory registries grew without limit for the life of the process: ``sessions`` in
``server.create_app`` (a whole proposal's cards per "Find trips and events" click) and
``JobManager._jobs`` (every run, with its full summary). Neither had any removal path.

The second half is the user-visible one. Six handlers subscripted ``sessions[...]`` bare, so a
session id that no longer exists - after a restart, or once newer reviews evicted it - raised
``KeyError`` and Starlette answered **500**. `app.js`'s `api()` raises on a non-2xx and puts the
body in the banner, so a 409 with a sentence is something a user can act on; a 500 is not.

Both halves are paired against a cry-wolf case: eviction must not touch a live session or a
running job, and a *valid* id must still work.
"""

from __future__ import annotations

import threading

import pytest
from starlette.testclient import TestClient
from truestill_app.jobs import MAX_RETAINED_JOBS, DriveRef, JobManager
from truestill_app.server import MAX_REVIEW_SESSIONS

# --- stale review sessions --------------------------------------------------------------


@pytest.mark.parametrize(
    "method_and_path",
    [
        ("POST", "/api/events/nope/apply"),
        ("POST", "/api/events/nope/merge"),
        ("POST", "/api/events/nope/split"),
        ("POST", "/api/events/nope/preview"),
        ("POST", "/api/events/nope/apply-to-disk"),
    ],
)
def test_a_stale_session_id_is_answered_not_a_500(
    client: TestClient, method_and_path: tuple[str, str]
) -> None:
    """Every session-keyed route. A KeyError here used to be an unhandled 500."""
    method, path = method_and_path
    response = client.request(method, path, json={"names": [], "indices": [0], "index": 0})

    assert response.status_code == 409, response.text
    body = response.json()
    assert body["ok"] is False
    assert "expired" in body["error"].lower(), body["error"]
    # The message must say what to do next, not merely what went wrong.
    assert "Find trips and events" in body["error"]


def test_the_session_cap_is_small_enough_to_bound_and_large_enough_to_use() -> None:
    """A cap of 1 would evict the session a user is working in on their next click."""
    assert 8 <= MAX_REVIEW_SESSIONS <= 256


# --- finished-job retirement ------------------------------------------------------------


def _finished_job(manager: JobManager, name: str) -> str:
    done = threading.Event()

    def target(progress: object, cancel: threading.Event) -> dict[str, str]:  # noqa: ARG001 - JobTarget signature
        return {"name": name}

    job_id = manager.start(target, drives=[DriveRef(key=f"path:{name}", label=name)], operation="t")
    assert isinstance(job_id, str)
    for _ in range(2000):  # auto-waiting rather than a sleep: poll the job's own status
        job = manager.get(job_id)
        if job is not None and job.status != "running":
            break
        done.wait(0.005)
    return job_id


def test_finished_jobs_are_retired_past_the_cap() -> None:
    manager = JobManager()
    ids = [_finished_job(manager, f"j{i}") for i in range(MAX_RETAINED_JOBS + 5)]

    live = [jid for jid in ids if manager.get(jid) is not None]
    assert len(live) <= MAX_RETAINED_JOBS + 1, f"registry unbounded: {len(live)} retained"
    # Cry-wolf half: the newest must survive - retiring the wrong end would break the client
    # that is still draining the job it just started.
    assert manager.get(ids[-1]) is not None


def test_a_running_job_is_never_retired() -> None:
    """Cry-wolf half: only terminal jobs are eligible, or a live stream loses its job."""
    manager = JobManager()
    release = threading.Event()

    def blocked(progress: object, cancel: threading.Event) -> dict[str, str]:  # noqa: ARG001 - JobTarget signature
        release.wait(10)
        return {}

    running = manager.start(
        blocked, drives=[DriveRef(key="path:held", label="held")], operation="held"
    )
    assert isinstance(running, str)
    try:
        for i in range(MAX_RETAINED_JOBS + 5):
            _finished_job(manager, f"f{i}")
        assert manager.get(running) is not None, "a running job was retired out from under it"
    finally:
        release.set()
