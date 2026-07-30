"""Catalog path startup: first-run is calm; wrong-catalog is loud."""

from __future__ import annotations

from pathlib import Path

import pytest
from truestill_core.catalog import Catalog
from truestill_core.catalog_startup import (
    CatalogPresence,
    db_flag_explicit,
    format_startup_lines,
    inspect_catalog,
)


def test_missing_default_is_will_create_not_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Mutation: treating missing as empty/alert would fail the tone/presence asserts."""
    monkeypatch.chdir(tmp_path)
    db = Path("reports/catalog.sqlite")
    info = inspect_catalog(db, explicit_db=False)
    assert info.presence is CatalogPresence.WILL_CREATE
    assert info.tone == "info"
    assert "No catalog yet" in info.detail
    assert "error" not in info.detail.lower()
    assert "warning" not in info.detail.lower()
    assert "fail" not in info.detail.lower()
    assert str(tmp_path / "reports" / "catalog.sqlite") == info.absolute_path
    assert not db.exists()  # inspect must not create the file
    lines = format_startup_lines(info)
    assert lines[0].startswith("Catalog: ")
    assert info.absolute_path in lines[0]
    assert any("No catalog yet" in line for line in lines)


def test_empty_default_names_absolute_path(tmp_path: Path) -> None:
    db = tmp_path / "reports" / "catalog.sqlite"
    db.parent.mkdir(parents=True)
    with Catalog(db):
        pass
    info = inspect_catalog(db, explicit_db=False)
    assert info.presence is CatalogPresence.EMPTY
    assert info.tone == "notice"
    assert info.absolute_path == str(db.resolve())
    assert "Opened empty catalog" in info.detail
    assert "--db" in info.detail or "working" in info.detail.lower()


def test_empty_while_drives_registered_is_alert(tmp_path: Path) -> None:
    db = tmp_path / "c.sqlite"
    with Catalog(db) as catalog:
        catalog.upsert_drive(uuid="drive-1", label="Cabinet")
    info = inspect_catalog(db, explicit_db=False)
    assert info.presence is CatalogPresence.EMPTY_WITH_DRIVES
    assert info.tone == "alert"
    assert info.drive_count == 1
    assert info.file_count == 0
    assert "0 files but 1 drive" in info.detail
    assert "may not be the catalog" in info.detail


def test_explicit_db_honoured_in_message(tmp_path: Path) -> None:
    db = tmp_path / "elsewhere" / "mine.sqlite"
    db.parent.mkdir(parents=True)
    with Catalog(db):
        pass
    info = inspect_catalog(db, explicit_db=True)
    assert info.presence is CatalogPresence.EMPTY
    assert info.explicit_db is True
    assert "from --db" in info.detail
    assert info.absolute_path == str(db.resolve())


def test_ready_catalog_lists_count(tmp_path: Path) -> None:
    db = tmp_path / "c.sqlite"
    with Catalog(db) as catalog:
        catalog.record_uploaded(
            source_path="/src/a.jpg",
            original_name="a.jpg",
            sha256="a" * 64,
            copy_sha256="a" * 64,
            perceptual=None,
            size=1,
            captured_at=None,
            category="Camera",
            relative="2024/a.jpg",
            event_id=None,
            albums=[],
        )
    info = inspect_catalog(db, explicit_db=True)
    assert info.presence is CatalogPresence.READY
    assert info.file_count == 1
    assert format_startup_lines(info) == [f"Catalog: {db.resolve()} (1 files)"]


def test_db_flag_explicit() -> None:
    assert db_flag_explicit(["status"]) is False
    assert db_flag_explicit(["status", "--db", "x.sqlite"]) is True
    assert db_flag_explicit(["status", "--db=x.sqlite"]) is True


def test_first_run_lines_are_not_alarmist(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    info = inspect_catalog(Path("reports/catalog.sqlite"), explicit_db=False)
    blob = "\n".join(format_startup_lines(info)).lower()
    for banned in ("error", "warning", "fail", "wrong", "missing library"):
        assert banned not in blob
