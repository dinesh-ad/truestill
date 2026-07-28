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
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
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

    # Apply relocates under the stored template -- but only after the typed confirm.
    monkeypatch.setattr("builtins.input", lambda *_: "move")
    assert main(["migrate-layout", str(root), "--db", str(db), "--apply"]) == 0
    # `x.jpg` carries no camera evidence, so it re-derives as `fallback` and is kept in a
    # labelled side bin rather than hoisted onto the timeline. The side-bin shape is fixed.
    assert (root / "Camera/2023/2023-08/x.jpg").exists()
    assert not (root / "Camera/2023/08/x.jpg").exists()


def _tree_fingerprint(root: Path) -> list[tuple[str, int]]:
    """Every file under a root with its size -- enough to catch a move, a write or a delete."""
    return sorted(
        (p.relative_to(root).as_posix(), p.stat().st_size) for p in root.rglob("*") if p.is_file()
    )


def test_a_preview_moves_nothing_and_writes_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The gate's first half: previewing is a read.

    Same discipline as the Settings preview -- the migration preview computes and displays, and
    must leave both the drive and the catalog byte-identical. If a preview could write, the plan
    a user is reviewing would already be partly executed.
    """
    root = tmp_path / "drive"
    root.mkdir()
    db = tmp_path / "c.sqlite"
    _seed_drive(db, root, "Camera/2023/08/x.jpg", b"data")
    capsys.readouterr()

    before_tree = _tree_fingerprint(root)
    before_db = db.read_bytes()

    assert main(["migrate-layout", str(root), "--db", str(db)]) == 0

    assert _tree_fingerprint(root) == before_tree  # not one byte moved
    assert db.read_bytes() == before_db  # and the catalog is untouched
    assert "Preview only. Nothing was moved." in capsys.readouterr().out


def test_without_the_typed_confirm_nothing_moves(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The gate's second half: --apply is permission to ask, not permission to move.

    There is no default-yes and no bare-Enter path -- anything other than the exact word aborts,
    and the command's terminal state is "previewed, nothing moved".
    """
    root = tmp_path / "drive"
    root.mkdir()
    db = tmp_path / "c.sqlite"
    _seed_drive(db, root, "Camera/2023/08/x.jpg", b"data")
    assert main(["config", "--db", str(db), "--set-template", "{yyyy}/{yyyy}-{mm}/{dd}"]) == 0
    capsys.readouterr()

    before_tree = _tree_fingerprint(root)

    for answer in ("", "y", "yes", "MOVE", " move me "):
        monkeypatch.setattr("builtins.input", lambda *_, a=answer: a)
        assert main(["migrate-layout", str(root), "--db", str(db), "--apply"]) == 0
        assert "Aborted. Nothing was moved." in capsys.readouterr().out
        assert _tree_fingerprint(root) == before_tree
