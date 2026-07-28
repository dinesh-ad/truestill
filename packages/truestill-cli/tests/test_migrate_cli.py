"""`truestill migrate-layout`: requires a connected drive, previews by default, applies on request."""

from __future__ import annotations

from pathlib import Path

import pytest
from truestill_cli.cli import main
from truestill_core.catalog import Catalog
from truestill_core.drive import MARKER_NAME, create_marker
from truestill_core.hashing import sha256_file


def _seed_drive(db: Path, root: Path, relative: str, content: bytes) -> None:
    marker = create_marker(root, "Drive A")
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    with Catalog(db) as catalog:
        catalog.upsert_drive(uuid=marker.uuid, label="Drive A")
        catalog.record_uploaded(
            source_path="/src/x.jpg",
            original_name="x.jpg",
            sha256=sha256_file(path),
            copy_sha256=sha256_file(path),
            perceptual=None,
            size=len(content),
            captured_at="2023-08-20T14:30:00",
            category="Camera",
            relative=relative,
            drive_uuid=marker.uuid,
        )


def test_migrate_layout_requires_a_connected_drive(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(
        ["migrate-layout", str(tmp_path / "not-a-drive"), "--db", str(tmp_path / "c.sqlite")]
    )
    assert code == 2
    assert f"no {MARKER_NAME}" in capsys.readouterr().err


def test_migrate_layout_previews_then_applies(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = tmp_path / "drive"
    root.mkdir()
    db = tmp_path / "c.sqlite"
    _seed_drive(db, root, "Camera/2023/08/x.jpg", b"data")
    assert main(["config", "--db", str(db), "--set-template", "{yyyy}/{yyyy}-{mm}/{dd}"]) == 0
    capsys.readouterr()

    # Preview leaves everything in place.
    assert main(["migrate-layout", str(root), "--db", str(db)]) == 0
    out = capsys.readouterr().out
    assert "to relocate" in out
    assert "Preview only" in out
    assert (root / "Camera/2023/08/x.jpg").exists()

    # Apply relocates under the stored template.
    assert main(["migrate-layout", str(root), "--db", str(db), "--apply"]) == 0
    assert (root / "2023/2023-08/20/x.jpg").exists()
    assert not (root / "Camera/2023/08/x.jpg").exists()
