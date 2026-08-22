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
from pathlib import Path

import pytest
from starlette.testclient import TestClient
from truestill_app.jobs import MAX_RETAINED_JOBS, DriveRef, JobManager
from truestill_app.server import MAX_REVIEW_SESSIONS
from truestill_core.drive import create_marker

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


def _marked_drive(tmp_path: Path, name: str = "DriveA") -> Path:
    """A connected drive with nothing on it.

    `service.propose_events` needs a marker and a catalog, not photographs - it assembles from
    catalog rows, so an empty marked directory yields a real, empty review session. That is what
    keeps these tests off exiftool: a cap test that skips on a machine without it would be
    covered in exactly the way the old one was.
    """
    drive = tmp_path / name
    drive.mkdir()
    create_marker(drive, name)
    return drive


def _propose(client: TestClient, drive: Path) -> str:
    """Create one review session, returning its id."""
    body = client.post("/api/events/propose", json={"path": str(drive)}).json()
    assert body.get("ok") is not False, body
    return str(body["session"])


def _resolves(client: TestClient, session_id: str) -> bool:
    """Is this session still in the store? 409 is the store's own not-found answer."""
    return client.post(f"/api/events/{session_id}/apply", json={"names": []}).status_code != 409


def test_the_oldest_review_session_is_evicted_past_the_cap(
    client: TestClient, tmp_path: Path
) -> None:
    """The bound the constant asserts, observed rather than asserted.

    The predecessor of this test checked ``8 <= MAX_REVIEW_SESSIONS <= 256`` and passed against a
    `remember_session` that called itself and was never called - a cap that had never once
    evicted anything. A range check on an integer cannot fail against that. This creates one
    session past the cap and looks.
    """
    drive = _marked_drive(tmp_path)
    ids = [_propose(client, drive) for _ in range(MAX_REVIEW_SESSIONS + 1)]

    assert not _resolves(client, ids[0]), "the oldest session survived past the cap"
    assert _resolves(client, ids[-1]), "the newest session was evicted"
    assert all(_resolves(client, sid) for sid in ids[1:]), "eviction took more than the oldest"


def test_no_session_is_evicted_at_or_under_the_cap(client: TestClient, tmp_path: Path) -> None:
    """Cry-wolf half (§4): a bound that fires early is worse than none.

    Filling the store exactly to the cap must leave every session usable - including the first,
    which is the one a user could still be working in.
    """
    drive = _marked_drive(tmp_path)
    ids = [_propose(client, drive) for _ in range(MAX_REVIEW_SESSIONS)]

    survivors = [sid for sid in ids if _resolves(client, sid)]
    assert len(survivors) == MAX_REVIEW_SESSIONS, (
        f"{MAX_REVIEW_SESSIONS - len(survivors)} session(s) evicted at the cap, none should be"
    )


def test_applying_to_disk_discards_that_session_and_leaves_the_others(
    client: TestClient, tmp_path: Path
) -> None:
    """The lifecycle hook: the one moment a review is provably finished.

    Without it the cap is the only thing that ever removes an entry, so a finished review sits
    in the store until 32 more push it out. With it the cap goes back to being the backstop for
    reviews the user walked away from. The second assertion is the one that matters: discarding
    must be surgical, not a flush.
    """
    drive = _marked_drive(tmp_path)
    keep, finish = _propose(client, drive), _propose(client, drive)

    applied = client.post(f"/api/events/{finish}/apply-to-disk", json={})
    assert applied.status_code == 200, applied.text

    assert not _resolves(client, finish), "the applied session was left in the store"
    assert _resolves(client, keep), "discarding one session disturbed another"


# --- finished-job retirement ------------------------------------------------------------


def _finished_job(manager: JobManager, name: str) -> str:
    done = threading.Event()

    def target(progress: object, cancel: threading.Event) -> dict[str, str]:  # noqa: ARG001 - JobTarget signature
        return {"name": name}

    job_id = manager.start(
        target,
        drives=[DriveRef(key=f"path:{name}", label=name)],
        operation="t",
        mutating=False,
    )
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
        blocked,
        drives=[DriveRef(key="path:held", label="held")],
        operation="held",
        mutating=False,
    )
    assert isinstance(running, str)
    try:
        for i in range(MAX_RETAINED_JOBS + 5):
            _finished_job(manager, f"f{i}")
        assert manager.get(running) is not None, "a running job was retired out from under it"
    finally:
        release.set()
