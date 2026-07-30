"""Catalog persistence and idempotency."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from truestill_core.catalog import (
    CURRENT_SCHEMA_VERSION,
    Catalog,
    CatalogVersionError,
)


def _record(
    catalog: Catalog, sha: str, *, relative: str, perceptual: str | None = "ff" * 8
) -> None:
    catalog.record_uploaded(
        source_path=f"/src/{sha}.jpg",
        original_name=f"{sha}.jpg",
        sha256=sha,
        perceptual=perceptual,
        size=1234,
        captured_at="2025-08-04T11:16:38",
        category="Camera",
        relative=relative,
    )


def test_record_and_find(tmp_path: Path) -> None:
    with Catalog(tmp_path / "c.sqlite") as catalog:
        _record(catalog, "sha-1", relative="Camera/2025/08/a.jpg")
        row = catalog.find_by_sha256("sha-1")
        assert row is not None
        assert row["upload_status"] == "uploaded"
        assert row["relative"] == "Camera/2025/08/a.jpg"
        assert catalog.find_by_sha256("missing") is None


def test_seed_rows_shape_matches_dedup(tmp_path: Path) -> None:
    with Catalog(tmp_path / "c.sqlite") as catalog:
        _record(catalog, "sha-1", relative="Camera/2025/08/a.jpg", perceptual="0000000000000000")
        rows = catalog.seed_rows()
        assert rows == [("/src/sha-1.jpg", "sha-1", "0000000000000000")]


def test_record_is_idempotent_on_sha(tmp_path: Path) -> None:
    with Catalog(tmp_path / "c.sqlite") as catalog:
        _record(catalog, "sha-1", relative="Camera/2025/08/a.jpg")
        _record(catalog, "sha-1", relative="Camera/2025/08/a.jpg")
        assert catalog.count() == 1


def test_persists_across_reopen(tmp_path: Path) -> None:
    db = tmp_path / "c.sqlite"
    with Catalog(db) as catalog:
        _record(catalog, "sha-1", relative="Camera/2025/08/a.jpg")
    with Catalog(db) as reopened:
        assert reopened.count() == 1
        assert reopened.find_by_sha256("sha-1") is not None


def test_in_memory_database(tmp_path: Path) -> None:  # noqa: ARG001 - fixture kept for symmetry
    with Catalog(Path(":memory:")) as catalog:
        _record(catalog, "sha-1", relative="Camera/2025/08/a.jpg")
        assert catalog.count() == 1


def test_fresh_catalog_is_current_version(tmp_path: Path) -> None:

    with Catalog(tmp_path / "c.sqlite") as catalog:
        assert catalog.schema_version == CURRENT_SCHEMA_VERSION


def _make_v1_catalog(path: Path) -> None:
    """Hand-build a pre-``size`` (v1) catalog with one row, as an old truestill would leave it."""
    conn = sqlite3.connect(str(path))
    conn.executescript(
        """
        CREATE TABLE files (
            id INTEGER PRIMARY KEY, source_path TEXT NOT NULL, sha256 TEXT NOT NULL UNIQUE,
            perceptual TEXT, captured_at TEXT, category TEXT NOT NULL, relative TEXT NOT NULL,
            upload_status TEXT NOT NULL, processed_at TEXT NOT NULL, uploaded_at TEXT
        );
        PRAGMA user_version = 1;
        """
    )
    conn.execute(
        "INSERT INTO files (source_path, sha256, perceptual, category, relative, "
        "upload_status, processed_at) VALUES ('/old.jpg', 'old-sha', NULL, 'Camera', "
        "'Camera/2024/01/old.jpg', 'uploaded', '2024-01-01T00:00:00')"
    )
    conn.commit()
    conn.close()


def test_v1_catalog_migrates_and_preserves_data(tmp_path: Path) -> None:

    db = tmp_path / "old.sqlite"
    _make_v1_catalog(db)

    with Catalog(db) as catalog:
        assert catalog.schema_version == CURRENT_SCHEMA_VERSION  # migration ran
        row = catalog.find_by_sha256("old-sha")
        assert row is not None  # pre-existing data survived
        assert row["relative"] == "Camera/2024/01/old.jpg"
        assert "size" in row.keys()  # noqa: SIM118 - sqlite3.Row has no __contains__  # new column now present (NULL for the legacy row)


def test_newer_catalog_is_refused(tmp_path: Path) -> None:

    db = tmp_path / "future.sqlite"
    with Catalog(db):
        pass
    conn = sqlite3.connect(str(db))
    conn.execute("PRAGMA user_version = 999")
    conn.commit()
    conn.close()

    with pytest.raises(CatalogVersionError):
        Catalog(db)


def _make_v6_catalog(path: Path) -> None:
    """A pre-settings (v6) catalog: a files table + user_version 6, no settings table yet."""
    conn = sqlite3.connect(str(path))
    conn.executescript(
        """
        CREATE TABLE files (
            id INTEGER PRIMARY KEY, source_path TEXT NOT NULL, sha256 TEXT NOT NULL UNIQUE,
            category TEXT NOT NULL, relative TEXT NOT NULL, upload_status TEXT NOT NULL,
            processed_at TEXT NOT NULL
        );
        PRAGMA user_version = 6;
        """
    )
    conn.commit()
    conn.close()


def test_v6_catalog_migrates_to_settings_table(tmp_path: Path) -> None:
    db = tmp_path / "v6.sqlite"
    _make_v6_catalog(db)

    with Catalog(db) as catalog:
        assert catalog.schema_version == CURRENT_SCHEMA_VERSION  # v7 migration ran
        assert catalog.get_setting("layout_template") is None  # settings table exists, empty
        catalog.set_setting("layout_template", "{category}/{yyyy}")

    with Catalog(db) as catalog:  # persisted across reopen
        assert catalog.get_setting("layout_template") == "{category}/{yyyy}"


def test_setting_overwrites_and_missing_is_none(tmp_path: Path) -> None:
    with Catalog(tmp_path / "c.sqlite") as catalog:
        catalog.set_setting("k", "first")
        catalog.set_setting("k", "second")
        assert catalog.get_setting("k") == "second"
        assert catalog.get_setting("never-set") is None


def test_stats_counts_by_format_and_zero_drive_samples(tmp_path: Path) -> None:
    """F6: format tallies and zero-drive samples the stats view expects, via Catalog methods."""
    with Catalog(tmp_path / "c.sqlite") as catalog:
        catalog.upsert_drive(uuid="A", label="Drive A")
        catalog.record_uploaded(
            source_path="/src/a.jpg",
            original_name="a.jpg",
            sha256="sha-a",
            copy_sha256="sha-a",
            perceptual=None,
            size=100,
            captured_at="2020-01-01T10:00:00",
            category="Camera",
            relative="2020/a.jpg",
            drive_uuid="A",
        )
        catalog.record_uploaded(
            source_path="/src/b.mp4",
            original_name="b.mp4",
            sha256="sha-b",
            copy_sha256="sha-b",
            perceptual=None,
            size=200,
            captured_at="2021-01-01T10:00:00",
            category="Camera",
            relative="2021/b.mp4",
            drive_uuid="A",
        )
        catalog.record_uploaded(
            source_path="/src/orphan.jpg",
            original_name="orphan.jpg",
            sha256="sha-orphan",
            copy_sha256="sha-orphan",
            perceptual=None,
            size=50,
            captured_at=None,
            category="Saved",
            relative="Saved/orphan.jpg",
            drive_uuid=None,
        )
        counts = catalog.stats_counts_by_format([".jpg", ".mp4", ".wav"])
        assert counts == {"jpg": 2, "mp4": 1}
        assert catalog.stats_zero_drive_samples(limit=12) == ["orphan.jpg"]
        assert catalog.stats_zero_drive_samples(limit=0) == []
