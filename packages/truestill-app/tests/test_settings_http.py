"""The Settings screen's HTTP surface: layout show/preview/set + migration preview."""

from __future__ import annotations

from pathlib import Path

import pytest
from starlette.testclient import TestClient
from truestill_app.server import create_app
from truestill_core.catalog import Catalog
from truestill_core.drive import create_marker
from truestill_core.hashing import sha256_file

_TOKEN = "tok"


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    app = create_app(token=_TOKEN, db=tmp_path / "c.sqlite")
    return TestClient(app, headers={"host": "127.0.0.1:7357", "x-truestill-token": _TOKEN})


def test_layout_get_reports_default_and_presets(client: TestClient) -> None:
    state = client.get("/api/layout").json()
    assert state["template"] == "{category}/{yyyy}/{mm}"
    assert state["is_default"] is True
    assert "year-month-day" in state["presets"]
    assert len(state["preview"]) == 3  # the three sample files
    # The payload is JSON that app.js iterates as [name, template]. Handing it preset objects
    # would serialize dataclasses into the API -- invisible to mypy, since the response is
    # dict[str, Any], and invisible to a test that only checks a key is present.
    assert all(isinstance(v, str) for v in state["presets"].values())


def test_layout_preview_valid_and_invalid(client: TestClient) -> None:
    ok = client.post("/api/layout/preview", json={"template": "{yyyy}/{yyyy}-{mm}/{dd}"}).json()
    assert ok["valid"] is True
    assert len(ok["preview"]) == 3

    bad = client.post("/api/layout/preview", json={"template": "{nope}"}).json()
    assert bad["valid"] is False
    assert "unknown" in bad["error"]


def test_layout_set_persists(client: TestClient) -> None:
    saved = client.post("/api/layout", json={"template": "{yyyy}/{yyyy}-{mm}/{dd}"}).json()
    assert saved["valid"] is True
    assert saved["template"] == "{yyyy}/{yyyy}-{mm}/{dd}"
    assert saved["is_default"] is False
    assert client.get("/api/layout").json()["template"] == "{yyyy}/{yyyy}-{mm}/{dd}"


def test_layout_set_rejects_invalid_without_saving(client: TestClient) -> None:
    bad = client.post("/api/layout", json={"template": "{category}/a:b"}).json()
    assert bad["valid"] is False
    assert client.get("/api/layout").json()["is_default"] is True  # nothing was stored


def test_migrate_preview_requires_a_connected_drive(client: TestClient, tmp_path: Path) -> None:
    r = client.post("/api/migrate/preview", json={"path": str(tmp_path / "nope")}).json()
    assert r["ok"] is False
    assert "drive" in r["error"]


def test_migrate_preview_lists_moves(client: TestClient, tmp_path: Path) -> None:
    drive = tmp_path / "drive"
    drive.mkdir()
    marker = create_marker(drive, "Drive A")
    photo = drive / "Camera/2023/08/x.jpg"
    photo.parent.mkdir(parents=True)
    photo.write_bytes(b"data")
    with Catalog(tmp_path / "c.sqlite") as catalog:
        catalog.upsert_drive(uuid=marker.uuid, label="Drive A")
        catalog.record_uploaded(
            source_path="/src/x.jpg",
            original_name="x.jpg",
            sha256=sha256_file(photo),
            copy_sha256=sha256_file(photo),
            perceptual=None,
            size=4,
            captured_at="2023-08-20T14:30:00",
            category="Camera",
            relative="Camera/2023/08/x.jpg",
            drive_uuid=marker.uuid,
        )

    client.post("/api/layout", json={"template": "{yyyy}/{yyyy}-{mm}/{dd}"})  # year-first
    r = client.post("/api/migrate/preview", json={"path": str(drive)}).json()
    assert r["ok"] is True
    assert len(r["moves"]) == 1
    assert r["moves"][0]["new"] == "2023/2023-08/20/x.jpg"
