"""Drive identity marker + catalog v6 (drives, file_copies) + verify."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from truestill_core.catalog import CURRENT_SCHEMA_VERSION, Catalog
from truestill_core.drive import (
    LEGACY_MARKER_NAMES,
    MARKER_NAME,
    DriveMarker,
    create_marker,
    existing_marker_path,
    needs_marker_upgrade,
    read_marker,
    upgrade_marker,
    write_marker,
)
from truestill_core.hashing import sha256_file
from truestill_core.verify import CopyStatus, CopyToVerify, verify_copies

LEGACY_NAME = LEGACY_MARKER_NAMES[0]


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
    (clone_root / MARKER_NAME).write_text((tmp_path / "orig" / MARKER_NAME).read_text())
    assert read_marker(clone_root).uuid == original.uuid  # type: ignore[union-attr]
    # re-labelling mints a fresh identity for the diverged clone
    relabelled = create_marker(clone_root, "Clone", uuid=None)
    assert relabelled.uuid != original.uuid


# --- legacy marker compatibility (vaeon -> truestill rename) ---------------------------


def _write_legacy(
    root: Path, *, uuid: str, label: str, created: str = "2025-01-01T00:00:00"
) -> None:
    """Write a pre-rename marker exactly as the old code would have."""
    root.mkdir(parents=True, exist_ok=True)
    (root / LEGACY_NAME).write_text(
        DriveMarker(uuid=uuid, label=label, created=created).to_json(), encoding="utf-8"
    )


def test_legacy_only_drive_is_still_readable(tmp_path: Path) -> None:
    _write_legacy(tmp_path, uuid="legacy-uuid", label="Old Drive")
    marker = read_marker(tmp_path)
    assert marker is not None
    assert (marker.uuid, marker.label) == ("legacy-uuid", "Old Drive")
    assert existing_marker_path(tmp_path).name == LEGACY_NAME  # type: ignore[union-attr]
    assert needs_marker_upgrade(tmp_path)


def test_reading_a_legacy_drive_never_writes(tmp_path: Path) -> None:
    """A read on a preview/browse path must not touch the user's drive."""
    _write_legacy(tmp_path, uuid="legacy-uuid", label="Old Drive")
    before = {p.name for p in tmp_path.iterdir()}
    for _ in range(3):
        read_marker(tmp_path)
    assert {p.name for p in tmp_path.iterdir()} == before
    assert not (tmp_path / MARKER_NAME).exists()


def test_upgrade_preserves_identity_verbatim_and_keeps_the_legacy_file(tmp_path: Path) -> None:
    _write_legacy(tmp_path, uuid="keep-me", label="Photos A", created="2024-06-05T10:00:00")
    upgraded = upgrade_marker(tmp_path)
    assert upgraded is not None
    # the uuid is the catalog foreign key -- re-minting would orphan every recorded copy
    assert upgraded.uuid == "keep-me"
    assert upgraded.label == "Photos A"
    assert upgraded.created == "2024-06-05T10:00:00"
    assert (tmp_path / MARKER_NAME).is_file()
    assert (tmp_path / LEGACY_NAME).is_file()  # deliberately retained
    assert not needs_marker_upgrade(tmp_path)
    # both files now describe the same identity, so an older build still agrees
    assert json.loads((tmp_path / LEGACY_NAME).read_text())["uuid"] == "keep-me"


def test_upgrade_is_idempotent_and_noops_on_a_canonical_drive(tmp_path: Path) -> None:
    created = create_marker(tmp_path, "Fresh")
    stamp = (tmp_path / MARKER_NAME).stat().st_mtime_ns
    again = upgrade_marker(tmp_path)
    assert again is not None
    assert again.uuid == created.uuid
    assert (tmp_path / MARKER_NAME).stat().st_mtime_ns == stamp  # no rewrite
    assert not (tmp_path / LEGACY_NAME).exists()


def test_upgrade_on_an_unmarked_root_returns_none_and_writes_nothing(tmp_path: Path) -> None:
    assert upgrade_marker(tmp_path) is None
    assert list(tmp_path.iterdir()) == []


def test_canonical_wins_when_both_markers_exist_and_diverge(tmp_path: Path) -> None:
    _write_legacy(tmp_path, uuid="stale-uuid", label="Stale")
    write_marker(
        tmp_path, DriveMarker(uuid="live-uuid", label="Live", created="2026-01-01T00:00:00")
    )
    marker = read_marker(tmp_path)
    assert marker is not None
    assert marker.uuid == "live-uuid"  # documented precedence, never a merge
    assert existing_marker_path(tmp_path).name == MARKER_NAME  # type: ignore[union-attr]


def test_new_drives_only_ever_get_the_canonical_name(tmp_path: Path) -> None:
    create_marker(tmp_path, "Brand New")
    names = {p.name for p in tmp_path.iterdir()}
    assert names == {MARKER_NAME}


def test_a_corrupt_legacy_marker_reads_as_no_marker(tmp_path: Path) -> None:
    tmp_path.joinpath(LEGACY_NAME).write_text("{not json", encoding="utf-8")
    assert read_marker(tmp_path) is None


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


def test_single_copy_count_matches_the_listing(tmp_path: Path) -> None:
    """The custody strip's cheap count and the at-risk listing must never disagree.

    They are two queries answering one question -- the count exists only because the strip was
    paying 425 ms at 100k files to build rows it then measured the length of. This is what
    stops that shortcut from quietly becoming a different answer.
    """
    with Catalog(tmp_path / "c.sqlite") as catalog:
        assert catalog.single_copy_count() == len(catalog.single_copy_shas()) == 0  # empty

        catalog.upsert_drive(uuid="A", label="A")
        catalog.upsert_drive(uuid="B", label="B")
        _record_copy_on(catalog, "sha-x", "A", "Camera/x.jpg", "sha-x", 10)
        _record_copy_on(catalog, "sha-x", "B", "Camera/x.jpg", "sha-x", 10)  # safe: two drives
        _record_copy_on(catalog, "sha-y", "A", "Camera/y.jpg", "sha-y", 20)  # at risk
        _record_copy_on(catalog, "sha-z", "B", "Camera/z.jpg", "sha-z", 30)  # at risk

        assert catalog.single_copy_count() == len(catalog.single_copy_shas()) == 2

        _record_copy_on(catalog, "sha-y", "B", "Camera/y.jpg", "sha-y", 20)  # y becomes safe
        assert catalog.single_copy_count() == len(catalog.single_copy_shas()) == 1


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
