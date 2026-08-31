"""A backup row is a claim; the second run must check it against the target. `(aiz)`

**Measured on NTFS in soak eleven.** `truestill backup --apply` was interrupted by a physical pull
and wrote **429 `file_copies` rows** for the target. **124 files were actually on the medium.**
305 rows were custody claims for bytes that never landed - and `status` counts rows, so the user
is told they have two copies while they have one.

⚠ **This is NOT an argument for `fsync`**, which `safe_copy` refuses in its own words. It is that
the second run must not believe the first run's rows without asking the target, which is
`(aja)`'s root cause on `backup`'s side of the same catalog table.
"""

from __future__ import annotations

import threading
from pathlib import Path

from truestill_core.backup import BackupPair, _files_missing_on_target, copy_to_drive
from truestill_core.catalog import Catalog
from truestill_core.drive import create_marker, read_marker
from truestill_core.hashing import sha256_file


def _silent(*_args: object, **_kwargs: object) -> None:
    """A progress sink: this test is about what lands, not about what is reported."""


def _drive(tmp_path: Path, name: str) -> tuple[Path, str]:
    root = tmp_path / name
    root.mkdir()
    return root, create_marker(root, label=name).uuid


def _seed(catalog: Catalog, uuid: str, root: Path, relative: str, payload: bytes) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    # ⚠ **A real digest, not a label.** `copy_to_drive` verifies what it wrote against
    # `copy_sha256` and discards a copy that does not match, so a fake hash would make the first
    # backup copy nothing and the test would prove the opposite of what it claims.
    digest = sha256_file(path)
    catalog.record_uploaded(
        source_path=f"/src/{relative}",
        original_name=Path(relative).name,
        sha256=digest,
        copy_sha256=digest,
        perceptual=None,
        size=len(payload),
        captured_at="2024-01-01T00:00:00",
        category="Camera",
        relative=relative,
        drive_uuid=uuid,
    )


def test_a_target_row_whose_file_is_empty_is_copied_again(tmp_path: Path) -> None:
    """THE DETECTOR. Against today's code the second run reports nothing to do."""
    db = tmp_path / "c.sqlite"
    src, src_uuid = _drive(tmp_path, "source")
    dst, dst_uuid = _drive(tmp_path, "target")
    with Catalog(db) as catalog:
        catalog.upsert_drive(uuid=src_uuid, label="source")
        catalog.upsert_drive(uuid=dst_uuid, label="target")
        _seed(catalog, src_uuid, src, "a/one.jpg", b"x" * 500)
        _seed(catalog, dst_uuid, dst, "a/one.jpg", b"x" * 500)

        assert _files_missing_on_target(catalog, src_uuid, dst_uuid, dst) == []

        # What the pull left: the entry, none of the bytes.
        (dst / "a/one.jpg").write_bytes(b"")

        missing = _files_missing_on_target(catalog, src_uuid, dst_uuid, dst)

    assert [m.relative for m in missing] == ["a/one.jpg"], (
        "the backup believed a row for a copy the target does not hold"
    )


def test_a_target_row_whose_file_is_gone_is_copied_again(tmp_path: Path) -> None:
    """The NTFS shape: the journal rolled the incomplete entry out of existence."""
    db = tmp_path / "c.sqlite"
    src, src_uuid = _drive(tmp_path, "source")
    dst, dst_uuid = _drive(tmp_path, "target")
    with Catalog(db) as catalog:
        catalog.upsert_drive(uuid=src_uuid, label="source")
        catalog.upsert_drive(uuid=dst_uuid, label="target")
        _seed(catalog, src_uuid, src, "a/one.jpg", b"x" * 500)
        _seed(catalog, dst_uuid, dst, "a/one.jpg", b"x" * 500)
        (dst / "a/one.jpg").unlink()

        missing = _files_missing_on_target(catalog, src_uuid, dst_uuid, dst)

    assert [m.relative for m in missing] == ["a/one.jpg"]


def test_an_intact_target_still_copies_nothing(tmp_path: Path) -> None:
    """⚠ THE CRY-WOLF HALF. A fix that re-copies an intact backup is worse than the defect."""
    db = tmp_path / "c.sqlite"
    src, src_uuid = _drive(tmp_path, "source")
    dst, dst_uuid = _drive(tmp_path, "target")
    with Catalog(db) as catalog:
        catalog.upsert_drive(uuid=src_uuid, label="source")
        catalog.upsert_drive(uuid=dst_uuid, label="target")
        for n in range(3):
            _seed(catalog, src_uuid, src, f"a/{n}.jpg", b"y" * (100 + n))
            _seed(catalog, dst_uuid, dst, f"a/{n}.jpg", b"y" * (100 + n))

        assert _files_missing_on_target(catalog, src_uuid, dst_uuid, dst) == []


def test_no_target_path_keeps_the_old_answer(tmp_path: Path) -> None:
    """``target=None`` means "I cannot ask cheaply", never "the rows are wrong"."""
    db = tmp_path / "c.sqlite"
    src, src_uuid = _drive(tmp_path, "source")
    dst, dst_uuid = _drive(tmp_path, "target")
    with Catalog(db) as catalog:
        catalog.upsert_drive(uuid=src_uuid, label="source")
        catalog.upsert_drive(uuid=dst_uuid, label="target")
        _seed(catalog, src_uuid, src, "a/one.jpg", b"x" * 500)
        _seed(catalog, dst_uuid, dst, "a/one.jpg", b"x" * 500)
        (dst / "a/one.jpg").write_bytes(b"")

        assert _files_missing_on_target(catalog, src_uuid, dst_uuid, None) == []


def test_the_call_site_passes_the_target_so_a_real_backup_repairs(tmp_path: Path) -> None:
    """⚠ THE WIRING, not the helper. A correct helper nobody hands the target to fixes nothing.

    Asserted through `copy_to_drive` - the shared body `truestill backup --apply` runs - because
    the defect this closes was in what the call site passed, and a unit test on the helper cannot
    see that.
    """
    db = tmp_path / "c.sqlite"
    src, src_uuid = _drive(tmp_path, "source")
    dst, dst_uuid = _drive(tmp_path, "target")
    with Catalog(db) as catalog:
        catalog.upsert_drive(uuid=src_uuid, label="source")
        catalog.upsert_drive(uuid=dst_uuid, label="target")
        _seed(catalog, src_uuid, src, "a/one.jpg", b"x" * 500)

    src_marker, dst_marker = read_marker(src), read_marker(dst)
    assert src_marker is not None
    assert dst_marker is not None
    pair = BackupPair(src, src_marker, dst, dst_marker)

    copy_to_drive(pair, db, progress=_silent, cancel=threading.Event())
    landed = dst / "a/one.jpg"
    assert landed.read_bytes() == b"x" * 500, "the first backup did not copy"

    # What the pull left behind, with the row still claiming the copy.
    landed.write_bytes(b"")

    copy_to_drive(pair, db, progress=_silent, cancel=threading.Event())

    assert landed.read_bytes() == b"x" * 500, (
        "the second backup believed its own row and left a zero-byte copy on the drive"
    )
