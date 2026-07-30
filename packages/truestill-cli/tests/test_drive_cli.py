"""CLI: drives / where / status / verify subcommands."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from PIL import Image
from truestill_cli.cli import main
from truestill_core.drive import LEGACY_MARKER_NAMES, MARKER_NAME, DriveMarker


def test_drives_init_and_list(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    dest = tmp_path / "driveA"
    db = tmp_path / "c.sqlite"
    assert main(["drives", "--init", str(dest), "--label", "Drive A", "--db", str(db)]) == 0
    assert (dest / MARKER_NAME).is_file()
    assert main(["drives", "--db", str(db)]) == 0
    assert "Drive A" in capsys.readouterr().out


def test_drives_migrate_marker_upgrades_a_legacy_drive(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = tmp_path / "oldDrive"
    root.mkdir()
    (root / LEGACY_MARKER_NAMES[0]).write_text(
        DriveMarker(uuid="legacy-uuid", label="Old Drive", created="2025-01-01T00:00:00").to_json()
    )
    db = tmp_path / "c.sqlite"
    assert main(["drives", "--migrate-marker", str(root), "--db", str(db)]) == 0
    out = capsys.readouterr().out
    assert "legacy-uuid" in out  # identity reported unchanged
    assert (root / MARKER_NAME).is_file()
    assert (root / LEGACY_MARKER_NAMES[0]).is_file()  # old file retained
    # the drive is now registered in the catalog under its original uuid
    assert main(["drives", "--db", str(db)]) == 0
    assert "Old Drive" in capsys.readouterr().out
    # second run is a no-op
    assert main(["drives", "--migrate-marker", str(root), "--db", str(db)]) == 0
    assert "nothing to do" in capsys.readouterr().out


def test_drives_migrate_marker_on_unmarked_root_errors(tmp_path: Path) -> None:
    assert (
        main(["drives", "--migrate-marker", str(tmp_path), "--db", str(tmp_path / "c.sqlite")]) == 2
    )


def test_init_requires_label(tmp_path: Path) -> None:
    assert main(["drives", "--init", str(tmp_path / "d"), "--db", str(tmp_path / "c.sqlite")]) == 2


def test_where_and_status_empty(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = tmp_path / "c.sqlite"
    assert main(["where", "holiday", "--db", str(db)]) == 0
    assert "No catalogued copies" in capsys.readouterr().out
    assert main(["status", "--db", str(db)]) == 0
    assert "at least two" in capsys.readouterr().out.lower()


def test_verify_without_marker_errors(tmp_path: Path) -> None:
    assert main(["verify", str(tmp_path / "nodrive"), "--db", str(tmp_path / "c.sqlite")]) == 2


@pytest.mark.skipif(shutil.which("exiftool") is None, reason="exiftool not installed")
def test_organize_to_drive_records_copies_then_verify(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    src = tmp_path / "src"
    src.mkdir()
    Image.new("RGB", (32, 32), (1, 2, 3)).save(src / "photo.jpg", "JPEG")
    dest = tmp_path / "driveA"
    db = tmp_path / "c.sqlite"

    main(["drives", "--init", str(dest), "--label", "Drive A", "--db", str(db)])
    capsys.readouterr()

    assert main(["organize", str(src), str(dest), "--apply", "--db", str(db)]) == 0

    # where finds the copy on the labelled drive
    assert main(["where", "photo", "--db", str(db)]) == 0
    assert "Drive A" in capsys.readouterr().out

    # verify (drive connected at dest) passes, exit 0
    assert main(["verify", str(dest), "--db", str(db)]) == 0
    out = capsys.readouterr().out
    assert "MISMATCH : 0" in out
    assert "MISSING  : 0" in out
    assert "UNREADABLE : 0" in out

    # status: the photo exists on a single drive -> flagged
    assert main(["status", "--db", str(db)]) == 0
    assert "only ONE drive" in capsys.readouterr().out
