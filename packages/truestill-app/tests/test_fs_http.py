"""Folder-picker + library-status endpoints (the UI v2 home screen's backend)."""

from __future__ import annotations

from pathlib import Path

import pytest
from starlette.testclient import TestClient
from truestill_app.server import create_app

_TOKEN = "tok"


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    app = create_app(token=_TOKEN, db=tmp_path / "c.sqlite")
    return TestClient(app, headers={"host": "127.0.0.1:7357", "x-truestill-token": _TOKEN})


def test_library_status_is_honest_when_empty(client: TestClient) -> None:
    s = client.get("/api/library/status").json()
    assert s["photos"] == 0
    assert s["videos"] == 0
    assert s["places"] == 0  # honest zero -> "not backed up yet", never a fake count


def _seed_media(db: Path) -> None:
    from truestill_core.catalog import Catalog  # noqa: PLC0415 - test-local

    with Catalog(db) as catalog:
        catalog.upsert_drive(uuid="D1", label="BackupA")
        rows = [
            ("IMG_1.jpg", "Camera/2023/08/IMG_1.jpg"),
            ("IMG_2.heic", "Camera/2023/08/IMG_2.heic"),
            ("VID_1.mp4", "Camera/2023/08/VID_1.mp4"),
        ]
        for i, (name, rel) in enumerate(rows):
            sha = f"{i:064x}"
            catalog.record_uploaded(
                source_path=f"/src/{name}",
                original_name=name,
                sha256=sha,
                copy_sha256=sha,
                perceptual=None,
                size=1000,
                captured_at=None,
                category="Camera",
                relative=rel,
                drive_uuid="D1",
            )


def test_library_status_splits_photos_and_videos(client: TestClient, tmp_path: Path) -> None:
    _seed_media(tmp_path / "c.sqlite")
    s = client.get("/api/library/status").json()
    assert s["photos"] == 2  # jpg + heic
    assert s["videos"] == 1  # mp4
    assert s["by_format"]["photos"] == {"jpg": 1, "heic": 1}
    assert s["by_format"]["videos"] == {"mp4": 1}


def test_drives_split_photos_and_videos(client: TestClient, tmp_path: Path) -> None:
    _seed_media(tmp_path / "c.sqlite")
    drives = client.get("/api/drives").json()["drives"]
    assert len(drives) == 1
    assert drives[0]["photos"] == 2
    assert drives[0]["videos"] == 1


def test_fs_dirs_returns_roots_when_no_path(client: TestClient) -> None:
    data = client.get("/api/fs/dirs").json()
    assert any(r["label"] == "Home" for r in data["roots"])
    assert data["entries"] == []


def test_fs_dirs_lists_subdirectories(client: TestClient, tmp_path: Path) -> None:
    (tmp_path / "sub-a").mkdir()
    (tmp_path / "sub-b").mkdir()
    (tmp_path / ".hidden").mkdir()
    (tmp_path / "file.txt").write_text("x", encoding="utf-8")
    data = client.get("/api/fs/dirs", params={"path": str(tmp_path)}).json()
    names = [e["name"] for e in data["entries"]]
    assert names == ["sub-a", "sub-b"]  # dirs only, hidden excluded, sorted


def test_fs_validate_counts_media(client: TestClient, tmp_path: Path) -> None:
    (tmp_path / "a.jpg").write_bytes(b"x")
    (tmp_path / "b.mp4").write_bytes(b"x")
    (tmp_path / "notes.txt").write_bytes(b"x")
    v = client.get("/api/fs/validate", params={"path": str(tmp_path)}).json()
    assert v["is_dir"] is True
    assert v["media"] == 2  # jpg + mp4, not the txt


def test_fs_validate_missing_path(client: TestClient, tmp_path: Path) -> None:
    v = client.get("/api/fs/validate", params={"path": str(tmp_path / "nope")}).json()
    assert v["exists"] is False
    assert v["media"] == 0


def test_fs_create_makes_a_new_backup_folder(client: TestClient, tmp_path: Path) -> None:
    target = tmp_path / "new" / "BackupA"  # a nested, not-yet-existing destination
    r = client.post("/api/fs/create", json={"path": str(target)}).json()
    assert r["created"] is True
    assert r["is_dir"] is True
    assert r["writable"] is True
    assert target.is_dir()
