"""`(aes)` on the Backups drive card: `was_checked` beside a null `last_verified`.

Stats already sent the field; the card ignored it and printed "Never checked" after a verify
that found gaps. Three states, not two.
"""

from __future__ import annotations

from pathlib import Path

from truestill_app.service.drives import list_drives
from truestill_core.catalog import Catalog
from truestill_core.drive import create_marker, drive_path_hint
from truestill_core.hashing import sha256_file


def _drive(db: Path, root: Path, label: str) -> str:
    root.mkdir(parents=True, exist_ok=True)
    marker = create_marker(root, label)
    with Catalog(db) as catalog:
        catalog.upsert_drive(uuid=marker.uuid, label=marker.label)
        catalog.set_setting(drive_path_hint(marker.uuid), str(root))
    return marker.uuid


def test_a_drive_nobody_looked_at_is_not_was_checked(tmp_path: Path) -> None:
    db = tmp_path / "c.sqlite"
    _drive(db, tmp_path / "A", "Empty")

    (row,) = list_drives(db)

    assert row["last_verified"] is None
    assert row["was_checked"] is False


def test_a_drive_verified_clean_is_was_checked_with_a_date(tmp_path: Path) -> None:
    db = tmp_path / "c.sqlite"
    root = tmp_path / "A"
    uuid = _drive(db, root, "Clean")
    path = root / "Camera/2020/a.jpg"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"clean-bytes")
    sha = sha256_file(path)
    with Catalog(db) as catalog:
        catalog.record_uploaded(
            source_path="/src/a.jpg",
            original_name="a.jpg",
            sha256=sha,
            copy_sha256=sha,
            perceptual=None,
            size=path.stat().st_size,
            captured_at="2020-01-01T12:00:00",
            category="Camera",
            relative="Camera/2020/a.jpg",
            drive_uuid=uuid,
        )
        catalog.mark_copy_verified(sha256=sha, drive_uuid=uuid, when="2020-06-01T00:00:00")
        catalog.refresh_drive_verified(uuid)

    (row,) = list_drives(db)

    assert row["last_verified"] is not None
    assert row["was_checked"] is True


def test_a_drive_checked_with_gaps_is_was_checked_without_a_date(tmp_path: Path) -> None:
    """The defect: null stamp after a look that found damage must not read as never looked."""
    db = tmp_path / "c.sqlite"
    root = tmp_path / "A"
    uuid = _drive(db, root, "Gaps")
    path = root / "Camera/2020/a.jpg"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"gap-bytes")
    sha = sha256_file(path)
    with Catalog(db) as catalog:
        catalog.record_uploaded(
            source_path="/src/a.jpg",
            original_name="a.jpg",
            sha256=sha,
            copy_sha256=sha,
            perceptual=None,
            size=path.stat().st_size,
            captured_at="2020-01-01T12:00:00",
            category="Camera",
            relative="Camera/2020/a.jpg",
            drive_uuid=uuid,
        )
        catalog.mark_copy_missing(sha256=sha, drive_uuid=uuid, when="2020-07-01T00:00:00")
        catalog.refresh_drive_verified(uuid)

    (row,) = list_drives(db)

    assert row["last_verified"] is None
    assert row["was_checked"] is True
    assert row["not_found"] >= 1
