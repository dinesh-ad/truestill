"""Stale path hints must correct, not raise - backlog (ww).

Identity is the marker uuid. A hint is disposable convenience. Failed hints are *cleared*
so list_drives does not re-stat a dead mount on every Backups load.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from starlette.testclient import TestClient
from truestill_app.server import create_app
from truestill_app.service import (
    _drive_correction,
    _drive_path_hint,
    list_drives,
    reveal_in_file_manager,
)
from truestill_core.catalog import Catalog
from truestill_core.drive import create_marker, locate_drive, path_is_usable_dir, read_marker

_TOKEN = "test-token-stale-hints"


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    app = create_app(token=_TOKEN, db=tmp_path / "c.sqlite")
    return TestClient(app, headers={"host": "127.0.0.1:7357"})


def _register_drive(db: Path, root: Path, label: str = "Cabinet") -> str:
    marker = create_marker(root, label)
    with Catalog(db) as catalog:
        catalog.upsert_drive(uuid=marker.uuid, label=marker.label)
        catalog.set_setting(_drive_path_hint(marker.uuid), str(root))
    return marker.uuid


# --- locate_drive / path_is_usable_dir: never leak OSError ---------------------------


def test_locate_drive_missing_path_returns_empty_location(tmp_path: Path) -> None:
    """Mutation: bare ``path.exists()`` without a guard still returns False here - the
    PermissionError cases below are what catch a missing try/except."""
    gone = tmp_path / "no-such-folder"
    loc = locate_drive(gone)
    assert loc.marker is None
    assert loc.root is None


def test_locate_drive_permission_error_returns_empty_not_raise(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Locked Crypto / dead FUSE: Path.exists raises PermissionError.

    Mutation: remove the ``except OSError`` in ``locate_drive`` -> this test raises.
    """
    locked = tmp_path / "locked-crypto"
    locked.mkdir()
    real_exists = Path.exists

    def boom(self: Path) -> bool:
        if self == locked or str(self).startswith(str(locked)):
            raise PermissionError(13, "Permission denied", str(self))
        return real_exists(self)

    monkeypatch.setattr(Path, "exists", boom)
    loc = locate_drive(locked)
    assert loc.marker is None
    assert loc.root is None


def test_path_is_usable_dir_false_for_file_not_dir(tmp_path: Path) -> None:
    f = tmp_path / "a-file.txt"
    f.write_text("x")
    assert path_is_usable_dir(f) is False


def test_path_is_usable_dir_swallows_permission_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Mutation: ``return path.is_dir()`` without try/except -> raises."""
    target = tmp_path / "denied"
    target.mkdir()

    def boom(self: Path) -> bool:
        if self == target:
            msg = "denied"
            raise PermissionError(msg)
        return False

    monkeypatch.setattr(Path, "is_dir", boom)
    assert path_is_usable_dir(target) is False


# --- drive-correction payload (no exception) ----------------------------------------


def test_drive_correction_nonexistent_is_ask_not_exception(tmp_path: Path) -> None:
    payload = _drive_correction(tmp_path / "never-existed")
    assert "Can't reach" in payload["error"]
    assert payload["can_register"] is False
    assert payload["suggested_root"] is None


def test_drive_correction_file_not_dir_is_ask_not_exception(tmp_path: Path) -> None:
    f = tmp_path / "file-not-dir"
    f.write_text("x")
    payload = _drive_correction(f)
    assert "Can't reach" in payload["error"]
    assert payload["can_register"] is False


def test_drive_correction_permission_error_is_ask_not_exception(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Mutation: let ``locate_drive`` call bare ``exists()`` on a raising path -> exception."""
    locked = tmp_path / "locked"
    locked.mkdir()

    def denied(_self: Path) -> bool:
        msg = "denied"
        raise PermissionError(msg)

    monkeypatch.setattr(Path, "exists", denied)
    monkeypatch.setattr("truestill_app.service.drive_support.path_is_usable_dir", lambda _p: False)
    payload = _drive_correction(locked)
    assert "Can't reach" in payload["error"]
    assert payload["can_register"] is False
    assert locate_drive(locked).marker is None


# --- list_drives clears failed hints; moved drive found at new root -----------------


def test_list_drives_clears_unreachable_hint_and_omits_check_path(tmp_path: Path) -> None:
    """Mutation: ``get_setting`` without ``_take_live_path_hint`` -> path still returned."""
    db = tmp_path / "c.sqlite"
    root = tmp_path / "drive"
    root.mkdir()
    uuid = _register_drive(db, root)
    gone = tmp_path / "old-mount"
    with Catalog(db) as catalog:
        catalog.set_setting(_drive_path_hint(uuid), str(gone))

    drives = list_drives(db)
    assert len(drives) == 1
    assert drives[0]["path"] is None
    with Catalog(db) as catalog:
        assert catalog.get_setting(_drive_path_hint(uuid)) is None  # cleared, not ignored

    assert list_drives(db)[0]["path"] is None


def test_moved_drive_found_by_uuid_at_new_root(tmp_path: Path) -> None:
    """Remount: same marker uuid at a new path; locate_drive / read_marker agree.

    Mutation: identity keyed on path instead of marker -> uuid would change on rename.
    """
    old = tmp_path / "old-mount"
    old.mkdir()
    marker = create_marker(old, "Cabinet")
    new = tmp_path / "new-mount"
    old.rename(new)

    assert read_marker(new) is not None
    assert read_marker(new).uuid == marker.uuid  # type: ignore[union-attr]
    loc = locate_drive(new)
    assert loc.is_root
    assert loc.marker is not None
    assert loc.marker.uuid == marker.uuid
    assert path_is_usable_dir(old) is False
    assert _drive_correction(old)["can_register"] is False


def test_verify_unreachable_soft_fails_with_correction(client: TestClient, tmp_path: Path) -> None:
    """Mutation: starting a job on a missing path would put ``job_id`` in the body."""
    missing = tmp_path / "was-here"
    r = client.post(f"/api/verify/run?token={_TOKEN}", json={"path": str(missing)})
    body = r.json()
    assert body["ok"] is False
    assert "job_id" not in body
    assert "Can't reach" in body["error"]
    assert body["can_register"] is False


def test_reveal_unreachable_returns_correction_not_oserror(
    client: TestClient, tmp_path: Path
) -> None:
    locked = tmp_path / "locked"
    locked.mkdir()
    with (
        patch("truestill_app.service.drives.path_is_usable_dir", return_value=False),
        patch("truestill_app.service.drive_support.path_is_usable_dir", return_value=False),
    ):
        body = reveal_in_file_manager(locked)
    assert body["ok"] is False
    assert "Can't reach" in body["error"]

    r = client.post(f"/api/reveal?token={_TOKEN}", json={"path": str(tmp_path / "gone")})
    assert r.json()["ok"] is False
    assert "Can't reach" in r.json()["error"]
