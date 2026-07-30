"""`truestill reclaim`: connected-drive required, dry-run default, typed 'delete' confirmation."""

from __future__ import annotations

from pathlib import Path

import pytest
from truestill_cli.cli import main
from truestill_core.catalog import Catalog
from truestill_core.drive import create_marker
from truestill_core.hashing import sha256_file


def _seed(db: Path, drive: Path, source: Path, content: bytes = b"content") -> None:
    marker = create_marker(drive, "Drive A")
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(content)
    copy = drive / "Camera/a.jpg"
    copy.parent.mkdir(parents=True, exist_ok=True)
    copy.write_bytes(content)
    with Catalog(db) as catalog:
        catalog.upsert_drive(uuid=marker.uuid, label="Drive A")
        catalog.record_uploaded(
            source_path=str(source),
            original_name=source.name,
            sha256=sha256_file(source),
            copy_sha256=sha256_file(source),
            perceptual=None,
            size=len(content),
            captured_at=None,
            category="Camera",
            relative="Camera/a.jpg",
            drive_uuid=marker.uuid,
        )


def test_reclaim_requires_connected_drive(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(["reclaim", str(tmp_path / "not-a-drive"), "--db", str(tmp_path / "c.sqlite")])
    assert code == 2
    # The refusal names what the folder IS and what to do, rather than the marker filename.
    err = capsys.readouterr().err
    assert "isn't a truestill drive yet" in err
    assert "drives --init" in err


def test_reclaim_preview_deletes_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    drive, db = tmp_path / "drive", tmp_path / "c.sqlite"
    drive.mkdir()
    source = tmp_path / "src" / "a.jpg"
    _seed(db, drive, source)

    assert main(["reclaim", str(drive), "--db", str(db)]) == 0
    out = capsys.readouterr().out
    assert "reclaimable: 1" in out
    assert "Preview only" in out
    assert source.exists()  # dry-run never deletes


def test_reclaim_apply_requires_typed_confirmation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    drive, db = tmp_path / "drive", tmp_path / "c.sqlite"
    drive.mkdir()
    source = tmp_path / "src" / "a.jpg"
    _seed(db, drive, source)

    monkeypatch.setattr("builtins.input", lambda _prompt: "no")  # wrong answer -> abort
    assert main(["reclaim", str(drive), "--db", str(db), "--apply"]) == 0
    assert source.exists()  # not confirmed -> nothing deleted


def test_reclaim_apply_deletes_on_confirmation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    drive, db = tmp_path / "drive", tmp_path / "c.sqlite"
    drive.mkdir()
    source = tmp_path / "src" / "a.jpg"
    _seed(db, drive, source)

    monkeypatch.setattr("builtins.input", lambda _prompt: "delete")
    assert main(["reclaim", str(drive), "--db", str(db), "--apply"]) == 0
    assert not source.exists()  # confirmed -> source freed
    assert (drive / "Camera/a.jpg").exists()  # backup copy untouched


def test_reclaim_reports_stale_sources_on_stderr(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    drive, db = tmp_path / "drive", tmp_path / "c.sqlite"
    drive.mkdir()
    source = tmp_path / "src" / "a.jpg"
    _seed(db, drive, source)
    source.unlink()

    assert main(["reclaim", str(drive), "--db", str(db)]) == 0
    captured = capsys.readouterr()
    assert "1 recorded source" in captured.err
    assert "may have moved" in captured.err
    assert str(source) in captured.err
    assert "Preview only" not in captured.out  # nothing to apply; do not nag
    assert "error" not in captured.out.lower()


def test_reclaim_empty_plan_reads_as_calm(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    drive, db = tmp_path / "drive", tmp_path / "c.sqlite"
    drive.mkdir()
    create_marker(drive, "Drive A")

    assert main(["reclaim", str(drive), "--db", str(db)]) == 0
    captured = capsys.readouterr()
    assert "Nothing to reclaim." in captured.out
    assert "Preview only" not in captured.out
    assert "recorded source" not in captured.err
    assert "error" not in captured.out.lower()
