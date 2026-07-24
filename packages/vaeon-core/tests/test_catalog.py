"""Catalog persistence and idempotency."""

from __future__ import annotations

from pathlib import Path

from vaeon_core.catalog import Catalog


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
