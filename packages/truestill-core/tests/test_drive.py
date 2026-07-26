"""Drive identity marker + catalog v6 (drives, file_copies) + verify."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from truestill_core.catalog import CURRENT_SCHEMA_VERSION, Catalog
from truestill_core.drive import create_marker, read_marker
from truestill_core.hashing import sha256_file
from truestill_core.verify import CopyStatus, CopyToVerify, verify_copies


def test_marker_roundtrip_and_identity_is_not_the_path(tmp_path: Path) -> None:
    a = create_marker(tmp_path / "driveA", "Photos A")
    assert read_marker(tmp_path / "driveA") == a
    # a re-mount at a different path keeps identity if the marker travels with the data
    (tmp_path / "driveA").rename(tmp_path / "remounted")
    assert read_marker(tmp_path / "remounted") is not None
    assert read_marker(tmp_path / "remounted").uuid == a.uuid  # type: ignore[union-attr]


def test_missing_marker_is_none(tmp_path: Path) -> None:
    assert read_marker(tmp_path) is None


def test_cloned_drive_shares_identity_until_relabelled(tmp_path: Path) -> None:
    original = create_marker(tmp_path / "orig", "Original")
    # a clone copies the marker verbatim -> same uuid (correct: identical at clone time)
    clone_root = tmp_path / "clone"
    clone_root.mkdir()
    (clone_root / ".vaeon-drive.json").write_text(
        (tmp_path / "orig" / ".vaeon-drive.json").read_text()
    )
    assert read_marker(clone_root).uuid == original.uuid  # type: ignore[union-attr]
    # re-labelling mints a fresh identity for the diverged clone
    relabelled = create_marker(clone_root, "Clone", uuid=None)
    assert relabelled.uuid != original.uuid


def _v5_catalog(path: Path) -> None:
    """A minimal v5 catalog (no drives/file_copies tables) with one files row."""
    conn = sqlite3.connect(str(path))
    conn.executescript(
        """
        CREATE TABLE files (
            id INTEGER PRIMARY KEY, source_path TEXT NOT NULL, original_name TEXT,
            sha256 TEXT NOT NULL UNIQUE, copy_sha256 TEXT, perceptual TEXT, size INTEGER,
            captured_at TEXT, category TEXT NOT NULL, relative TEXT NOT NULL, event_id INTEGER,
            upload_status TEXT NOT NULL, processed_at TEXT NOT NULL, uploaded_at TEXT
        );
        PRAGMA user_version = 5;
        """
    )
    conn.execute(
        "INSERT INTO files (source_path, original_name, sha256, category, relative, "
        "upload_status, processed_at) VALUES ('/s.jpg','s.jpg','sha5','Camera',"
        "'Camera/2024/01/s.jpg','uploaded','2024-01-01')"
    )
    conn.commit()
    conn.close()


def test_v5_to_v6_migration_adds_drive_tables_and_preserves_data(tmp_path: Path) -> None:
    db = tmp_path / "old.sqlite"
    _v5_catalog(db)
    with Catalog(db) as catalog:
        assert catalog.schema_version == CURRENT_SCHEMA_VERSION
        assert catalog.find_by_sha256("sha5") is not None  # data survived
        assert catalog.list_drives() == []  # new tables exist and are empty


def _record_copy_on(
    catalog: Catalog, sha: str, drive: str, relative: str, copy_hash: str, size: int
) -> None:
    catalog.record_uploaded(
        source_path=f"/src/{sha}",
        original_name=Path(relative).name,
        sha256=sha,
        copy_sha256=copy_hash,
        perceptual=None,
        size=size,
        captured_at=None,
        category="Camera",
        relative=relative,
        drive_uuid=drive,
    )


def test_status_flags_single_copy_content(tmp_path: Path) -> None:
    with Catalog(tmp_path / "c.sqlite") as catalog:
        catalog.upsert_drive(uuid="A", label="A")
        catalog.upsert_drive(uuid="B", label="B")
        _record_copy_on(catalog, "sha-x", "A", "Camera/x.jpg", "sha-x", 10)
        _record_copy_on(catalog, "sha-x", "B", "Camera/x.jpg", "sha-x", 10)  # x on two drives
        _record_copy_on(catalog, "sha-y", "A", "Camera/y.jpg", "sha-y", 20)  # y on one drive
        singles = {r["original_name"] for r in catalog.single_copy_shas()}
        assert singles == {"y.jpg"}


def test_where_finds_copies_after_rename(tmp_path: Path) -> None:
    with Catalog(tmp_path / "c.sqlite") as catalog:
        catalog.upsert_drive(uuid="A", label="Drive A")
        _record_copy_on(catalog, "sha-z", "A", "Camera/2024/01/holiday.jpg", "sha-z", 5)
        rows = catalog.find_copies("holiday")
        assert len(rows) == 1
        assert rows[0]["drive_label"] == "Drive A"
        assert rows[0]["relative"] == "Camera/2024/01/holiday.jpg"


def test_verify_reports_verified_missing_and_mismatch(tmp_path: Path) -> None:
    root = tmp_path / "driveB"
    (root / "sub").mkdir(parents=True)
    good = root / "sub" / "good.bin"
    good.write_bytes(b"intact content")
    bad = root / "sub" / "bad.bin"
    bad.write_bytes(b"corrupted now")  # will not match its recorded hash
    # 'gone.bin' is recorded but never written -> MISSING

    copies = [
        CopyToVerify(sha256="1", relative="sub/good.bin", expected_hash=sha256_file(good)),
        CopyToVerify(sha256="2", relative="sub/bad.bin", expected_hash="0" * 64),
        CopyToVerify(sha256="3", relative="sub/gone.bin", expected_hash="0" * 64),
    ]
    results = {r.copy.relative: r.status for r in verify_copies(copies, root)}
    assert results["sub/good.bin"] is CopyStatus.VERIFIED
    assert results["sub/bad.bin"] is CopyStatus.MISMATCH
    assert results["sub/gone.bin"] is CopyStatus.MISSING


def test_verify_null_copy_hash_falls_back_to_source_sha(tmp_path: Path) -> None:
    """Pre-v6 rows (copy_sha256 NULL) were byte-identical, so sha256 is the verify hash."""
    root = tmp_path / "drive"
    root.mkdir()
    f = root / "a.bin"
    f.write_bytes(b"legacy")
    # simulate the CLI's NULL fallback: expected_hash = copy_sha256 or sha256
    expected = None or sha256_file(f)
    result = verify_copies([CopyToVerify("sha", "a.bin", expected)], root)[0]
    assert result.status is CopyStatus.VERIFIED
