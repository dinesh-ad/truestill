"""The Settings screen's HTTP surface: layout show/preview/set + migration preview."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest
import truestill_core.migrate as migrate_module
from starlette.testclient import TestClient
from truestill_app.server import create_app
from truestill_core.catalog import Catalog
from truestill_core.drive import create_marker
from truestill_core.events import DEFAULT_MIN_FILES, EVENT_MIN_FILES_KEY
from truestill_core.hashing import sha256_file
from truestill_core.layout import DEFAULT_TEMPLATE_STRING, LAYOUT_TEMPLATE_KEY

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
    assert state["template"] == "{yyyy}/{yyyy}-{mm}/{yyyy}-{mm} - Everyday"
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


def test_event_min_files_setting_changes_proposals_and_unset_keeps_default(
    client: TestClient, db_path: Path, tmp_path: Path
) -> None:
    drive = tmp_path / "drive"
    drive.mkdir()
    marker = create_marker(drive, "Drive A")
    with Catalog(db_path) as catalog:
        catalog.upsert_drive(uuid=marker.uuid, label=marker.label)
        for day, count in ((datetime(2026, 6, 14, 9), 8), (datetime(2026, 6, 20, 9), 10)):
            for index in range(count):
                captured_at = day + timedelta(minutes=5 * index)
                sha = f"sha-{day:%Y%m%d}-{index}"
                catalog.record_uploaded(
                    source_path=f"/src/{sha}.jpg",
                    original_name=f"{sha}.jpg",
                    sha256=sha,
                    copy_sha256=sha,
                    perceptual=None,
                    size=10,
                    captured_at=captured_at.isoformat(),
                    category="Camera",
                    relative=f"{day:%Y/%m}/{sha}.jpg",
                    drive_uuid=marker.uuid,
                )

    settings = client.get("/api/events/settings").json()
    assert settings == {
        "valid": True,
        "min_files": DEFAULT_MIN_FILES,
        "default_min_files": DEFAULT_MIN_FILES,
        "is_default": True,
    }
    default_proposals = client.post("/api/events/propose", json={"path": str(drive)}).json()
    assert sorted(card["count"] for card in default_proposals["cards"]) == [8, 10]

    saved = client.post("/api/events/settings", json={"min_files": 9}).json()
    assert saved == {
        "valid": True,
        "min_files": 9,
        "default_min_files": DEFAULT_MIN_FILES,
        "is_default": False,
    }

    changed_proposals = client.post("/api/events/propose", json={"path": str(drive)}).json()
    assert [card["count"] for card in changed_proposals["cards"]] == [10]
    with Catalog(db_path) as catalog:
        assert catalog.get_setting(EVENT_MIN_FILES_KEY) == "9"


def test_invalid_stored_event_min_files_is_actionable(
    client: TestClient, db_path: Path, tmp_path: Path
) -> None:
    drive = tmp_path / "drive"
    drive.mkdir()
    create_marker(drive, "Drive A")
    with Catalog(db_path) as catalog:
        catalog.set_setting(EVENT_MIN_FILES_KEY, "many")

    settings = client.get("/api/events/settings").json()
    assert settings["valid"] is False
    assert EVENT_MIN_FILES_KEY in settings["error"]
    assert "whole number" in settings["error"]
    assert "Settings" in settings["error"]

    proposals = client.post("/api/events/propose", json={"path": str(drive)}).json()
    assert proposals["ok"] is False
    assert proposals["error"] == settings["error"]


def test_migrate_preview_requires_a_connected_drive(client: TestClient, tmp_path: Path) -> None:
    r = client.post("/api/migrate/preview", json={"path": str(tmp_path / "nope")}).json()
    assert r["ok"] is False
    assert "drive" in r["error"]


@pytest.mark.parametrize("endpoint", ["/api/migrate/preview", "/api/events/propose"])
def test_drive_preview_endpoints_never_refresh_the_catalog(
    client: TestClient, db_path: Path, tmp_path: Path, endpoint: str
) -> None:
    """A connected-drive preview is still a read, including its drive discovery.

    The marker deliberately disagrees with the catalog: an accidental `upsert_drive` therefore
    changes both observable state and the database bytes, proving the guard is not a timestamp
    coincidence and covering both migration preview and Trips & events review startup.
    """
    drive = tmp_path / "drive"
    drive.mkdir()
    marker = create_marker(drive, "Marker Label")
    with Catalog(db_path) as catalog:
        catalog.upsert_drive(uuid=marker.uuid, label="Catalog Label")
        before_row = dict(catalog.list_drives()[0])
    before_db = db_path.read_bytes()

    response = client.post(endpoint, json={"path": str(drive)})

    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert db_path.read_bytes() == before_db
    with Catalog(db_path) as catalog:
        after_row = dict(catalog.list_drives()[0])
    assert after_row["label"] == "Catalog Label"
    assert after_row["last_seen"] == before_row["last_seen"]
    assert after_row == before_row


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
    assert r["moves"][0]["new"] == "Camera/2023/2023-08/x.jpg"  # no camera evidence -> side bin
    # This file has no real capture metadata (dummy bytes) -- genuinely unresolvable, unaffected
    # by the fix below. Left exactly as-is: it is the correct, still-tested side-bin answer for a
    # Camera label re-derivation cannot back up with evidence, not the bug §13.6 found.


def test_migrate_preview_routes_a_camera_photo_by_its_own_evidence(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§13.6: `Camera` is ambiguous by construction, and the app never resolved it -- every
    `Camera` row defaulted to the side bin regardless of real evidence, exactly like migrating
    through the CLI without `label_routes`/`rederive_rules`. Fails against the pre-fix code: the
    named-event photo below was proposed for `Camera/2023/2023-08/2023-08-20 - Goa Trip/x.jpg`
    instead of the timeline -- the exact result §13.6 reproduced.

    Two files, opposite evidence, in one fixture: `resolvable` has metadata `rederive_rules` can
    read back as the device rule (a fake `read_metadata`, the same technique
    `test_rederivation_degrades_instead_of_failing_when_exiftool_is_missing` uses to control it
    deterministically); `unresolvable` has none. Both start under the *same* ambiguous `Camera`
    label, so only the evidence tells them apart -- proving the fix does not just flip the
    default the other way.
    """
    drive = tmp_path / "drive"
    drive.mkdir()
    marker = create_marker(drive, "Drive A")

    resolvable = drive / "2023/2023-08/resolvable.jpg"  # already on the timeline, as organize
    resolvable.parent.mkdir(parents=True)  # would have placed it -- a real drive's shape
    resolvable.write_bytes(b"data")

    unresolvable = drive / "Camera/2023/08/unresolvable.jpg"  # no evidence -> stays a side bin
    unresolvable.parent.mkdir(parents=True)
    unresolvable.write_bytes(b"different bytes -- distinct content, distinct sha256")

    def fake_read_metadata(_paths: object, **_kwargs: object) -> dict[Path, dict[str, str]]:
        return {resolvable: {"Model": "Pixel 7"}}  # unresolvable is simply absent -- no evidence

    monkeypatch.setattr(migrate_module, "read_metadata", fake_read_metadata)

    with Catalog(tmp_path / "c.sqlite") as catalog:
        catalog.upsert_drive(uuid=marker.uuid, label="Drive A")
        sha_resolvable = sha256_file(resolvable)
        catalog.record_uploaded(
            source_path="/src/resolvable.jpg",
            original_name="resolvable.jpg",
            sha256=sha_resolvable,
            copy_sha256=sha_resolvable,
            perceptual=None,
            size=4,
            captured_at="2023-08-20T14:30:00",
            category="Camera",
            relative="2023/2023-08/resolvable.jpg",
            drive_uuid=marker.uuid,
        )
        event_id = catalog.record_event(
            name="Goa Trip",
            slug="goa-trip",
            start_date="2023-08-20",
            file_count=1,
            signature="sig-goa",
        )
        catalog.set_event_id([sha_resolvable], event_id)
        catalog.record_uploaded(
            source_path="/src/unresolvable.jpg",
            original_name="unresolvable.jpg",
            sha256=sha256_file(unresolvable),
            copy_sha256=sha256_file(unresolvable),
            perceptual=None,
            size=unresolvable.stat().st_size,
            captured_at="2023-08-21T09:00:00",
            category="Camera",
            relative="Camera/2023/08/unresolvable.jpg",
            drive_uuid=marker.uuid,
        )

    client.post("/api/layout", json={"template": "{yyyy}/{yyyy}-{mm}"})  # year-first
    r = client.post("/api/migrate/preview", json={"path": str(drive)}).json()
    assert r["ok"] is True
    moves = {m["old"]: m["new"] for m in r["moves"]}

    # Real evidence -> the timeline, under its named event, exactly as organize would place it.
    assert (
        moves["2023/2023-08/resolvable.jpg"] == "2023/2023-08/2023-08-20 - Goa Trip/resolvable.jpg"
    )
    # No evidence -> still the conservative side bin. The fix resolves ambiguity; it does not
    # remove the safe default for a label that stays genuinely ambiguous.
    assert moves["Camera/2023/08/unresolvable.jpg"] == "Camera/2023/2023-08/unresolvable.jpg"


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
