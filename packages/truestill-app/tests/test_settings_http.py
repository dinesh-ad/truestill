"""The Settings screen's HTTP surface: layout show/preview/set + migration preview."""

from __future__ import annotations

from pathlib import Path

import pytest
from starlette.testclient import TestClient
from truestill_app.server import create_app
from truestill_core.catalog import Catalog
from truestill_core.drive import create_marker
from truestill_core.hashing import sha256_file
from truestill_core.layout import (
    DEFAULT_TEMPLATE_STRING,
    LAYOUT_TEMPLATE_KEY,
    pin_existing_layout,
)

_TOKEN = "tok"


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    """The same catalog the `client` fixture serves, so a test can inspect what it wrote."""
    return tmp_path / "c.sqlite"


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    app = create_app(token=_TOKEN, db=tmp_path / "c.sqlite")
    return TestClient(app, headers={"host": "127.0.0.1:7357", "x-truestill-token": _TOKEN})


def test_layout_get_reports_default_and_presets(client: TestClient) -> None:
    state = client.get("/api/layout").json()
    assert state["template"] == "{category}/{yyyy}/{mm}"
    assert state["is_default"] is True
    assert "year-month-day" in state["presets"]
    assert len(state["preview"]) == 4  # camera, camera event, undated, side bin
    # The payload is JSON that app.js iterates as [name, template]. Handing it preset objects
    # would serialize dataclasses into the API -- invisible to mypy, since the response is
    # dict[str, Any], and invisible to a test that only checks a key is present.
    assert all(isinstance(v, str) for v in state["presets"].values())


def test_layout_preview_valid_and_invalid(client: TestClient) -> None:
    ok = client.post("/api/layout/preview", json={"template": "{yyyy}/{yyyy}-{mm}/{dd}"}).json()
    assert ok["valid"] is True
    assert len(ok["preview"]) == 4

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


def _organize_one(db: Path, category: str = "Camera") -> None:
    """Place a file for real, so the catalog counts as organized (and can be pinned)."""

    with Catalog(db) as catalog:
        catalog.record_uploaded(
            source_path="/src/a.jpg",
            original_name="a.jpg",
            sha256="sha-a",
            copy_sha256="sha-a",
            perceptual=None,
            size=10,
            captured_at="2021-06-15T10:30:00",
            category=category,
            relative=f"{category}/2021/06/a.jpg",
            event_id=None,
            albums=[],
            drive_uuid=None,
        )


def test_a_fresh_library_reports_the_layout_actually_in_force(client: TestClient) -> None:
    """The Current: label is derived, never hardcoded -- and it is not called legacy."""

    state = client.get("/api/layout").json()
    assert state["template"] == DEFAULT_TEMPLATE_STRING  # whatever the default currently is
    assert state["is_default"] is True
    assert state["is_legacy"] is False
    assert state["legacy_note"] == ""  # nothing to migrate, so nothing to warn about


def test_a_pinned_legacy_library_is_framed_as_legacy(client: TestClient, db_path: Path) -> None:
    """A library organized before the year-first default keeps its shape and is told why."""

    _organize_one(db_path)
    with Catalog(db_path) as catalog:
        assert pin_existing_layout(catalog) is True

    state = client.get("/api/layout").json()
    assert state["template"] == "{category}/{yyyy}/{mm}"  # its real shape, truthfully
    assert state["is_legacy"] is True
    assert "Legacy layout" in state["legacy_note"]
    assert "choose a preset" in state["legacy_note"]
    # A legacy library previews its OWN shape, not the one it has not adopted.
    assert state["preview"][0]["path"].startswith("Camera/")


def test_opening_settings_never_writes_a_setting(client: TestClient, db_path: Path) -> None:
    """A read never writes: previewing must not pin a layout as a side effect.

    The whole preview is derived from `effective_layout_string`, which is pure -- so a library
    that qualifies for the pin can be inspected all day without the pin firing.
    """

    _organize_one(db_path)

    client.get("/api/layout")
    client.post("/api/layout/preview", json={"template": "{yyyy}/{yyyy}-{mm}"})
    client.get("/api/layout")

    with Catalog(db_path) as catalog:
        assert catalog.get_setting(LAYOUT_TEMPLATE_KEY) is None  # nothing was persisted


def test_the_preview_shows_the_routing_split(client: TestClient) -> None:
    """The split is what a user cannot infer from a template string, so it must be shown."""
    rows = client.get("/api/layout").json()["preview"]
    described = {r["description"] for r in rows}
    assert described == {"Camera", "Camera event", "Camera undated", "Screenshots"}


def test_a_typed_category_template_is_rejected_with_the_actionable_message(
    client: TestClient,
) -> None:
    """R2 at the app door: the UI shows why and what to do, not a bare failure."""
    r = client.post("/api/layout/preview", json={"template": "{category}/{yyyy}"}).json()
    assert r["valid"] is False
    assert "{category} cannot be used in the timeline" in r["error"]
    assert "{yyyy}/{yyyy}-{mm}" in r["error"]


def test_presets_carry_titles_and_name_the_default(client: TestClient) -> None:
    state = client.get("/api/layout").json()
    assert state["default_preset"] == "year-month-event"
    assert set(state["preset_titles"]) == set(state["presets"])
    assert all(isinstance(t, str) and t for t in state["preset_titles"].values())
