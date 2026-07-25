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


def test_catalog_db_is_created(client: TestClient, tmp_path: Path) -> None:
    client.get(f"/api/drives?token={_TOKEN}")  # opening the catalog creates it
    assert Catalog(tmp_path / "c.sqlite").schema_version >= 6
