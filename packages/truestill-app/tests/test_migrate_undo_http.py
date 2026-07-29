"""In-app migration undo HTTP surface (backlog pp): armed-state + preview/apply jobs."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from starlette.testclient import TestClient
from truestill_app.server import create_app
from truestill_core.catalog import Catalog
from truestill_core.destinations.local import LocalDestination
from truestill_core.drive import create_marker
from truestill_core.hashing import sha256_file
from truestill_core.layout import LayoutScheme, LayoutTemplate
from truestill_core.migrate import run_migration

_TOKEN = "tok"


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "c.sqlite"


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    app = create_app(token=_TOKEN, db=tmp_path / "c.sqlite")
    return TestClient(app, headers={"host": "127.0.0.1:7357", "x-truestill-token": _TOKEN})


def _finish(client: TestClient, job_id: str) -> dict:
    with client.stream("GET", f"/api/jobs/{job_id}/events?token={_TOKEN}") as stream:
        for line in stream.iter_lines():
            if line.startswith("data:"):
                event = json.loads(line[5:].strip())
                if event["type"] in ("done", "error"):
                    return event
    message = "job never finished"
    raise AssertionError(message)


def _scheme(template: str) -> LayoutScheme:
    parsed = LayoutTemplate.parse(template)
    return LayoutScheme.of(timeline=parsed, timeline_evented=parsed, side_bin=parsed)


def _migrated_drive(tmp_path: Path, db_path: Path) -> Path:
    """Two files migrated under a year-first scheme so a reversible journal exists."""
    drive = tmp_path / "drive"
    drive.mkdir()
    marker = create_marker(drive, "Drive A")
    with Catalog(db_path) as catalog:
        catalog.upsert_drive(uuid=marker.uuid, label="Drive A")
        for name, content, captured in (
            ("a.jpg", b"aaaa", "2023-08-20T14:30:00"),
            ("b.jpg", b"bbbb", "2024-01-15T00:00:00"),
        ):
            relative = f"Camera/2023/08/{name}" if name == "a.jpg" else f"WhatsApp/2024/01/{name}"
            path = drive / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
            sha = sha256_file(path)
            catalog.record_uploaded(
                source_path=f"/src/{name}",
                original_name=name,
                sha256=sha,
                copy_sha256=sha,
                perceptual=None,
                size=len(content),
                captured_at=captured,
                category="Camera" if name == "a.jpg" else "WhatsApp",
                relative=relative,
                drive_uuid=marker.uuid,
            )
        run_migration(
            catalog,
            LocalDestination(drive),
            marker.uuid,
            _scheme("{yyyy}/{yyyy}-{mm}"),
            apply=True,
        )
        assert catalog.reversible_migration(marker.uuid) is not None
    return drive


def test_armed_state_is_false_when_no_journal(client: TestClient, tmp_path: Path) -> None:
    drive = tmp_path / "drive"
    drive.mkdir()
    create_marker(drive, "Empty")
    r = client.get(f"/api/migrate/undo?path={drive}&token={_TOKEN}").json()
    assert r == {"ok": True, "armed": False, "file_count": 0, "run_id": None}


def test_armed_state_reports_the_reversible_journal(
    client: TestClient, db_path: Path, tmp_path: Path
) -> None:
    drive = _migrated_drive(tmp_path, db_path)
    r = client.get(f"/api/migrate/undo?path={drive}&token={_TOKEN}").json()
    assert r["ok"] is True
    assert r["armed"] is True
    assert r["file_count"] == 2
    assert isinstance(r["run_id"], str)
    assert r["run_id"]


def test_armed_state_never_writes(client: TestClient, db_path: Path, tmp_path: Path) -> None:
    """Same byte-snapshot discipline as migration_preview: a read must leave the catalog alone."""
    drive = tmp_path / "drive"
    drive.mkdir()
    marker = create_marker(drive, "Marker Label")
    with Catalog(db_path) as catalog:
        catalog.upsert_drive(uuid=marker.uuid, label="Catalog Label")
        before_row = dict(catalog.list_drives()[0])
    before_db = db_path.read_bytes()

    r = client.get(f"/api/migrate/undo?path={drive}&token={_TOKEN}").json()

    assert r["ok"] is True
    assert r["armed"] is False
    assert db_path.read_bytes() == before_db
    with Catalog(db_path) as catalog:
        after_row = dict(catalog.list_drives()[0])
    assert after_row == before_row


def test_armed_state_returns_drive_correction_when_unconnected(
    client: TestClient, tmp_path: Path
) -> None:
    inside = tmp_path / "nope"
    inside.mkdir()
    r = client.get(f"/api/migrate/undo?path={inside}&token={_TOKEN}").json()
    assert r["ok"] is False
    assert "drive" in r["error"].lower() or "folder" in r["error"].lower()
    assert "suggested_root" in r


def test_undo_preview_job_streams_progress_and_surfaces_refusals(
    client: TestClient, db_path: Path, tmp_path: Path
) -> None:
    drive = _migrated_drive(tmp_path, db_path)
    with Catalog(db_path) as catalog:
        marker_uuid = str(catalog.list_drives()[0]["uuid"])
        record = catalog.reversible_migration(marker_uuid)
        assert record is not None
        edited = drive / str(record[1][0]["new_relative"])
        edited.write_bytes(b"edited since the migration")

    started = client.post("/api/migrate/undo/preview", json={"path": str(drive)}).json()
    assert "job_id" in started
    done = _finish(client, started["job_id"])
    assert done["type"] == "done"
    summary = done["summary"]
    assert summary["applied"] is False
    assert summary["reversed_files"] == 1
    assert len(summary["refused"]) == 1
    assert "changed since the migration" in summary["refused"][0]["reason"]
    # Preview wrote nothing to the journal.
    with Catalog(db_path) as catalog:
        still = catalog.reversible_migration(marker_uuid)
        assert still is not None
        assert len(still[1]) == 2


def test_undo_preview_job_never_writes_the_catalog(
    client: TestClient, db_path: Path, tmp_path: Path
) -> None:
    drive = _migrated_drive(tmp_path, db_path)
    before_db = db_path.read_bytes()
    done = _finish(
        client,
        client.post("/api/migrate/undo/preview", json={"path": str(drive)}).json()["job_id"],
    )
    assert done["type"] == "done"
    assert done["summary"]["reversed_files"] == 2
    assert done["summary"]["refused"] == []
    assert db_path.read_bytes() == before_db


def test_undo_apply_job_puts_files_back_and_spends_the_record(
    client: TestClient, db_path: Path, tmp_path: Path
) -> None:
    drive = _migrated_drive(tmp_path, db_path)
    done = _finish(
        client,
        client.post("/api/migrate/undo/apply", json={"path": str(drive)}).json()["job_id"],
    )
    assert done["type"] == "done"
    assert done["summary"]["applied"] is True
    assert done["summary"]["reversed_files"] == 2
    assert done["summary"]["refused"] == []
    with Catalog(db_path) as catalog:
        assert catalog.reversible_migration(catalog.list_drives()[0]["uuid"]) is None
    r = client.get(f"/api/migrate/undo?path={drive}&token={_TOKEN}").json()
    assert r["armed"] is False


def test_undo_endpoints_return_drive_correction_not_a_job(
    client: TestClient, tmp_path: Path
) -> None:
    path = tmp_path / "not-a-drive"
    path.mkdir()
    for endpoint in ("/api/migrate/undo/preview", "/api/migrate/undo/apply"):
        r = client.post(endpoint, json={"path": str(path)}).json()
        assert "job_id" not in r
        assert r["ok"] is False
        assert "error" in r
