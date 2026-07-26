"""Copy the library to a second drive: per-drive presence, verify-after-write, free-space guard."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image
from starlette.testclient import TestClient
from vaeon_app import service
from vaeon_app.server import create_app
from vaeon_core.drive import create_marker

_TOKEN = "tok"


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    app = create_app(token=_TOKEN, db=tmp_path / "c.sqlite")
    return TestClient(app, headers={"host": "127.0.0.1:7357", "x-vaeon-token": _TOKEN})


def _finish(client: TestClient, job_id: str) -> dict:
    with client.stream("GET", f"/api/jobs/{job_id}/events?token={_TOKEN}") as stream:
        for line in stream.iter_lines():
            if line.startswith("data:"):
                event = json.loads(line[5:].strip())
                if event["type"] in ("done", "error"):
                    return event
    message = "job never finished"
    raise AssertionError(message)


def _library_on(client: TestClient, drive: Path, n: int) -> None:
    src = drive.parent / f"src-{drive.name}"
    src.mkdir()
    for i in range(n):
        Image.new("RGB", (16, 16), (i * 7 % 256, 30, 60)).save(src / f"p{i}.jpg", "JPEG")
    drive.mkdir()
    create_marker(drive, drive.name)
    started = client.post("/api/organize/run", json={"source": str(src), "destination": str(drive)})
    _finish(client, started.json()["job_id"])


def test_backup_copies_library_and_records_per_drive(client: TestClient, tmp_path: Path) -> None:
    a, b = tmp_path / "DriveA", tmp_path / "DriveB"
    _library_on(client, a, 4)
    b.mkdir()
    create_marker(b, "DriveB")

    preview = client.post("/api/backup/preview", json={"source": str(a), "target": str(b)}).json()
    assert preview["ok"] is True
    assert preview["count"] == 4
    assert preview["enough"] is True

    done = _finish(
        client,
        client.post("/api/backup/run", json={"source": str(a), "target": str(b)}).json()["job_id"],
    )
    assert done["type"] == "done"
    assert done["summary"]["copied"] == 4

    # the files are physically on DriveB, byte-verified and recorded as copies there
    assert len(list(b.rglob("*.jpg"))) == 4
    drives = {d["label"]: d for d in client.get(f"/api/drives?token={_TOKEN}").json()["drives"]}
    assert drives["DriveB"]["photos"] == 4
    assert client.get(f"/api/drives?token={_TOKEN}").json()["at_risk"] == []  # now safe in 2 places

    # second run: everything is already on DriveB -> nothing to copy
    again = client.post("/api/backup/preview", json={"source": str(a), "target": str(b)}).json()
    assert again["count"] == 0


def test_backup_rejects_same_and_non_drive(client: TestClient, tmp_path: Path) -> None:
    a = tmp_path / "DriveA"
    _library_on(client, a, 2)
    plain = tmp_path / "plain"
    plain.mkdir()

    same = client.post("/api/backup/preview", json={"source": str(a), "target": str(a)}).json()
    assert same["ok"] is False
    assert "same drive" in same["error"]

    non = client.post("/api/backup/preview", json={"source": str(a), "target": str(plain)}).json()
    assert non["ok"] is False
    assert "drive" in non["error"]


def test_backup_warns_and_blocks_when_target_is_too_small(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A disk-full mid-copy is the failure this feature exists to prevent: preview must flag it
    and the run must refuse rather than start and stop half-way."""
    a, b = tmp_path / "DriveA", tmp_path / "DriveB"
    _library_on(client, a, 4)
    b.mkdir()
    create_marker(b, "DriveB")

    tiny = SimpleNamespace(total=100, used=99, free=8)  # 8 bytes free
    monkeypatch.setattr(service.shutil, "disk_usage", lambda _p: tiny)

    preview = client.post("/api/backup/preview", json={"source": str(a), "target": str(b)}).json()
    assert preview["enough"] is False  # UI blocks the Copy button on this

    done = _finish(
        client,
        client.post("/api/backup/run", json={"source": str(a), "target": str(b)}).json()["job_id"],
    )
    assert done["type"] == "error"
    assert "not enough space" in done["message"]
    assert not list(b.rglob("*.jpg"))  # nothing was copied
