"""(F8) Backup missing-copy rows are typed - dual-hash fields must not travel as Any."""

from __future__ import annotations

from pathlib import Path
from typing import get_type_hints

from truestill_app import service
from truestill_app.service import MissingCopy
from truestill_core.catalog import Catalog
from truestill_core.drive import create_marker, read_marker
from truestill_core.hashing import sha256_file


def test_files_missing_on_target_is_annotated_as_missing_copy() -> None:
    """list[Any] made swapping copy_sha256 and sha256 invisible to mypy (audit F8)."""
    hints = get_type_hints(service._files_missing_on_target)
    assert hints["return"] == list[MissingCopy]


def test_missing_copy_verify_sha_is_the_copy_hash_and_never_the_content_hash() -> None:
    """§3: copy_sha256 is the verification identity; sha256 is the dedup identity.

    This used to assert that a NULL copy hash **falls back** to the content hash. That fallback
    is now refused: it asserts the copy is byte-identical to its source, which the Takeout bake
    already breaks and date-rescue baking breaks again - and it made an un-recorded hash
    indistinguishable from a legacy row, so a skipped per-drive write would have surfaced as
    corruption on a file truestill had just rewritten. Unknown is now ``None``, and `backup_run`
    answers it by recording the hash of the copy it actually writes.
    """
    row = MissingCopy(
        sha256="content-hash",
        relative="2020/a.jpg",
        copy_sha256="copy-hash",
        size=12,
    )
    assert row.verify_sha == "copy-hash"
    unknown = MissingCopy(
        sha256="content-hash",
        relative="2020/a.jpg",
        copy_sha256=None,
        size=12,
    )
    assert unknown.verify_sha is None, "an unrecorded hash must not borrow the source's"


def test_files_missing_on_target_returns_missing_copy_instances(tmp_path: Path) -> None:
    source = tmp_path / "A"
    target = tmp_path / "B"
    source.mkdir()
    target.mkdir()
    create_marker(source, "A")
    create_marker(target, "B")
    marker_a = read_marker(source)
    marker_b = read_marker(target)
    assert marker_a is not None
    assert marker_b is not None

    photo = source / "p.jpg"
    photo.write_bytes(b"backup-typed-row")
    sha = sha256_file(photo)
    db = tmp_path / "c.sqlite"
    with Catalog(db) as catalog:
        catalog.upsert_drive(uuid=marker_a.uuid, label="A")
        catalog.upsert_drive(uuid=marker_b.uuid, label="B")
        catalog.record_uploaded(
            source_path=str(photo),
            original_name="p.jpg",
            sha256=sha,
            copy_sha256=sha,
            perceptual=None,
            size=photo.stat().st_size,
            captured_at=None,
            category="Camera",
            relative="Camera/p.jpg",
            drive_uuid=marker_a.uuid,
        )
        missing = service._files_missing_on_target(catalog, marker_a.uuid, marker_b.uuid)

    assert len(missing) == 1
    assert isinstance(missing[0], MissingCopy)
    assert missing[0].sha256 == sha
    assert missing[0].relative == "Camera/p.jpg"
    assert missing[0].verify_sha == sha
