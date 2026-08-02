"""The app must not mint a second identity for a library it already knows (`(aap)`).

**This is the more dangerous of the two surfaces, and it fails in the opposite direction.** The
CLI's `--init` mints a drive showing **0 files** - visibly wrong. The app registers as a side
effect of backup, and `attach_drive` attaches by *content*, so the phantom drive shows **all**
the files. Observed on the shipped build: after a move whose marker was lost, `truestill status`
said

    All catalogued content has at least two drive copies. Nicely redundant.

about photos that existed in exactly one place. A custody tool overstating redundancy is worse
than one understating it, which is why this is guarded at the point of minting rather than left
to the screen that reads the count.
"""

from __future__ import annotations

import random
import shutil
from pathlib import Path

import pytest
from PIL import Image
from truestill_app.service import attach_drive, backup_preview
from truestill_app.service.drives import list_drives
from truestill_cli.cli import main


def _jpeg(path: Path, *, seed: int, size: tuple[int, int]) -> None:
    rng = random.Random(seed)
    image = Image.new("RGB", size)
    image.putdata(
        [
            (rng.randrange(256), rng.randrange(256), rng.randrange(256))
            for _ in range(size[0] * size[1])
        ]
    )
    image.save(path, "JPEG", quality=95)


@pytest.fixture
def moved_library(tmp_path: Path) -> tuple[Path, Path]:
    """An organized drive, and a copy of it whose marker was lost. Returns (moved, db)."""
    src, drive, db = tmp_path / "src", tmp_path / "DriveA", tmp_path / "c.sqlite"
    src.mkdir()
    for i in range(4):
        _jpeg(src / f"p{i}.jpg", seed=i, size=(64 + i, 64))
    assert main(["drives", "--init", str(drive), "--label", "Photos HDD", "--db", str(db)]) == 0
    assert main(["organize", str(src), str(drive), "--apply", "--db", str(db)]) == 0

    moved = tmp_path / "DriveMoved"
    shutil.copytree(drive, moved)
    (moved / ".truestill-drive.json").unlink()
    return moved, db


def test_attach_refuses_to_mint_over_a_library_the_catalog_already_knows(
    moved_library: tuple[Path, Path],
) -> None:
    """No marker is written, so the phantom drive cannot come into existence at all."""
    moved, db = moved_library

    result = attach_drive(moved, db, write=True)

    assert not (moved / ".truestill-drive.json").exists(), "a refusal must write nothing"
    assert result.registered is False
    assert result.blocked_by is not None, "the refusal must be reported, never silent"
    assert result.blocked_by.label == "Photos HDD"


def test_the_phantom_drive_never_appears_so_redundancy_is_not_overstated(
    moved_library: tuple[Path, Path],
) -> None:
    """The consequence, asserted where a user would have met it.

    Before this guard the catalog gained a second drive holding the same four photos, and every
    surface that counts places - `status`, the app's Drives screen, the 3-2-1 promise - reported
    two copies of files that existed once.
    """
    moved, db = moved_library
    attach_drive(moved, db, write=True)

    drives = list_drives(db)
    assert len(drives) == 1, f"a second identity appeared: {[d['label'] for d in drives]}"
    assert drives[0]["label"] == "Photos HDD"


def test_backup_preview_refuses_and_names_the_drive(moved_library: tuple[Path, Path]) -> None:
    """The user-facing half, in the words they read.

    Backup is the only place the app registers a drive, so it is the only place this refusal
    can surface - and it uses the refusal shape the screen already renders.
    """
    moved, db = moved_library
    target = moved.parent / "Elsewhere"
    target.mkdir()

    result = backup_preview(moved, target, db)

    assert result["ok"] is False
    error = result["error"]
    assert "Photos HDD" in error, "the user must be told which drive this folder already is"
    assert "second" in error.lower() or "already" in error.lower()


def test_an_ordinary_unregistered_folder_still_registers(tmp_path: Path) -> None:
    """Cry-wolf half. Backing up into a brand-new empty folder is the normal case.

    A guard that refused here would break the feature it is protecting: the app registers the
    destination precisely so a user never has to hear the word "marker".
    """
    src, drive, db = tmp_path / "src", tmp_path / "DriveA", tmp_path / "c.sqlite"
    src.mkdir()
    for i in range(3):
        _jpeg(src / f"p{i}.jpg", seed=100 + i, size=(48 + i, 48))
    assert main(["drives", "--init", str(drive), "--label", "Photos HDD", "--db", str(db)]) == 0
    assert main(["organize", str(src), str(drive), "--apply", "--db", str(db)]) == 0

    fresh = tmp_path / "NewBackup"
    fresh.mkdir()
    result = attach_drive(fresh, db, write=True)

    assert result.registered is True
    assert result.blocked_by is None
    assert (fresh / ".truestill-drive.json").exists()


def test_a_folder_that_is_already_a_drive_is_untouched(tmp_path: Path) -> None:
    """Anti-vacuity: the check must only run where a marker would be minted.

    An already-marked drive has an identity; re-inspecting it would be wasted reads on every
    backup preview, and could only ever produce an offer to adopt itself.
    """
    src, drive, db = tmp_path / "src", tmp_path / "DriveA", tmp_path / "c.sqlite"
    src.mkdir()
    _jpeg(src / "p0.jpg", seed=7, size=(64, 64))
    assert main(["drives", "--init", str(drive), "--label", "Photos HDD", "--db", str(db)]) == 0
    assert main(["organize", str(src), str(drive), "--apply", "--db", str(db)]) == 0

    result = attach_drive(drive, db, write=True)

    assert result.blocked_by is None
    assert result.registered is False, "it was already registered; nothing new was written"
