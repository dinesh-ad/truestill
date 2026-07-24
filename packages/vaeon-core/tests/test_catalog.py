"""Catalog persistence and idempotency."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from vaeon_core.catalog import (
    CURRENT_SCHEMA_VERSION,
    Catalog,
    CatalogVersionError,
)


def _record(
    catalog: Catalog, sha: str, *, relative: str, perceptual: str | None = "ff" * 8
) -> None:
    catalog.record_uploaded(
        source_path=f"/src/{sha}.jpg",
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
    """Hand-build a pre-``size`` (v1) catalog with one row, as an old vaeon would leave it."""
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
