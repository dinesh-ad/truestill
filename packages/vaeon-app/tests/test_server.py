"""Server security + endpoints via Starlette's TestClient."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from starlette.testclient import TestClient
from vaeon_app.server import create_app
from vaeon_core.catalog import Catalog

_TOKEN = "test-token-123"


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    app = create_app(token=_TOKEN, db=tmp_path / "c.sqlite")
    # TestClient sends Host: testserver by default; our guard requires a localhost Host.
    return TestClient(app, headers={"host": "127.0.0.1:7357"})


def test_missing_token_is_rejected(client: TestClient) -> None:
    assert client.get("/api/drives").status_code == 403


def test_bad_host_is_rejected(tmp_path: Path) -> None:
    app = create_app(token=_TOKEN, db=tmp_path / "c.sqlite")
    evil = TestClient(app, headers={"host": "evil.example.com"})
    assert evil.get(f"/api/drives?token={_TOKEN}").status_code == 421


def test_cross_origin_is_rejected(client: TestClient) -> None:
    r = client.get(f"/api/drives?token={_TOKEN}", headers={"origin": "http://evil.example.com"})
    assert r.status_code == 403


def test_static_is_exempt_from_token(client: TestClient) -> None:
    assert client.get("/static/style.css").status_code == 200


def test_home_serves_and_injects_token(client: TestClient) -> None:
    r = client.get(f"/?token={_TOKEN}")
    assert r.status_code == 200
    assert _TOKEN in r.text
    assert "{{TOKEN}}" not in r.text  # placeholder was replaced


def test_drives_and_where_empty(client: TestClient) -> None:
    drives = client.get(f"/api/drives?token={_TOKEN}").json()
    assert drives == {"drives": [], "at_risk": []}
    where = client.get(f"/api/where?token={_TOKEN}&term=x").json()
    assert where == {"copies": []}


def test_organize_preview_no_media(client: TestClient, tmp_path: Path) -> None:
    src = tmp_path / "empty"
    src.mkdir()
    r = client.post(
        f"/api/organize/preview?token={_TOKEN}",
        json={"source": str(src), "destination": str(tmp_path / "out")},
    )
    assert r.status_code == 200
    assert r.json()["files"] == 0


def test_verify_job_streams_error_for_non_drive(client: TestClient, tmp_path: Path) -> None:
    """A verify on a path with no marker surfaces the error over SSE, not a crash."""
    started = client.post(f"/api/verify/run?token={_TOKEN}", json={"path": str(tmp_path / "nope")})
    job_id = started.json()["job_id"]
    events = []
    with client.stream("GET", f"/api/jobs/{job_id}/events?token={_TOKEN}") as stream:
        for line in stream.iter_lines():
            if line.startswith("data:"):
                events.append(json.loads(line[len("data:") :].strip()))
                if events[-1]["type"] in ("done", "error"):
                    break
    assert events[-1]["type"] == "error"
    assert "drive" in events[-1]["message"]


def _stream_to_done(client: TestClient, job_id: str) -> dict:
    """Collect a job's SSE stream and return the terminal (done/error) event."""
    events = []
    with client.stream("GET", f"/api/jobs/{job_id}/events?token={_TOKEN}") as stream:
        for line in stream.iter_lines():
            if line.startswith("data:"):
                events.append(json.loads(line[len("data:") :].strip()))
                if events[-1]["type"] in ("done", "error"):
                    break
    return events[-1]


def test_organize_run_summary_matches_files_on_disk(client: TestClient, tmp_path: Path) -> None:
    """Regression for the 'Done / nothing to do' blocker.

    The UI reads the run outcome as ``(d.summary || d).outcomes`` (same shape Verify/Migrate use).
    This pins that contract: the organize done-event must carry ``summary.outcomes`` whose counts
    equal what actually landed on disk -- so a successful run can never report "nothing to do".
    """
    src = tmp_path / "src"
    src.mkdir()
    (src / "a.jpg").write_bytes(b"first-unique-bytes")
    (src / "b.jpg").write_bytes(b"second-unique-bytes")
    out = tmp_path / "out"

    started = client.post(
        f"/api/organize/run?token={_TOKEN}",
        json={"source": str(src), "destination": str(out), "skip_undated": False},
    )
    done = _stream_to_done(client, started.json()["job_id"])

    assert done["type"] == "done"
    # The frontend unwraps the target's return from under ``summary`` (jobs.py contract).
    outcomes = (done.get("summary") or done).get("outcomes")
    assert outcomes, (
        "organize done-event must expose non-empty summary.outcomes (else 'nothing to do')"
    )

    files_on_disk = [p for p in out.rglob("*") if p.is_file()]
    assert outcomes.get("uploaded", 0) == len(files_on_disk) == 2  # summary == on-disk reality


def test_organize_result_handler_unwraps_summary(client: TestClient) -> None:
    """Guard the frontend fix: the Organize done-handler must read the outcome the same way
    Verify/Migrate do -- via the ``summary`` wrapper -- not the bare top-level key that caused
    a successful run to render "nothing to do". (No JS runtime here, so we pin it in source.)"""
    app_js = client.get(f"/static/app.js?token={_TOKEN}").text
    assert "(d.summary || d).outcomes" in app_js  # the correct unwrap is present
    assert "d.outcomes" not in app_js  # the bare buggy read is gone


def test_catalog_db_is_created(client: TestClient, tmp_path: Path) -> None:
    client.get(f"/api/drives?token={_TOKEN}")  # opening the catalog creates it
    assert Catalog(tmp_path / "c.sqlite").schema_version >= 6
