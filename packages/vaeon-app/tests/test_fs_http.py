"""Folder-picker + library-status endpoints (the UI v2 home screen's backend)."""

from __future__ import annotations

from pathlib import Path

import pytest
from starlette.testclient import TestClient
from vaeon_app.server import create_app

_TOKEN = "tok"


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    app = create_app(token=_TOKEN, db=tmp_path / "c.sqlite")
    return TestClient(app, headers={"host": "127.0.0.1:7357", "x-vaeon-token": _TOKEN})


def test_library_status_is_honest_when_empty(client: TestClient) -> None:
    s = client.get("/api/library/status").json()
    assert s["photos"] == 0
    assert s["places"] == 0  # honest zero -> "not backed up yet", never a fake count


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
