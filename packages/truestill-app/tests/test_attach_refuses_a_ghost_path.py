"""`attach_drive` refuses to mint where a known drive was recorded and its marker is gone. `(agr)`

⚠ **THE DEFECT, demonstrated before this existed**: at the recorded path of an unplugged drive -
an ordinary empty directory, which is exactly what an unmounted mountpoint is -
`attach_drive(ghost, db, write=True)` returned `registered=True` and minted a phantom identity.
The catalog then held the real drive *offline* and the phantom *connected*, on the local disk,
and every byte written there would be shadowed the moment the real drive remounted. `(aap)`'s
data-loss door, app-side, reachable from `backup_run` on both user-supplied paths
(`backup.py:633-634`).

**The census that scoped the fix**: four mint sites, three already guarded - `cli.py` `drives
--init`, `cli.py` organize, `service/organize._approve_registration`. This file pins the fourth
calling the same core rule (`ghost_drive_at`), so a fifth caller of `attach_drive` inherits it.

⚠ **THE HEADLINE ASSERTS THE ABSENCE OF THE MARKER, not the presence of a refusal** - a guard
that raised *and still wrote the marker* would pass the weaker assertion while leaving the
phantom on disk, which is the whole loss.

**The unmount shape is the real one** (`(agr)` Q119): `backup_run` pre-checks `is_dir()`
(`backup.py:625-627`), so only an *existing, empty* directory ever reaches `attach_drive` - and
`ghost_drive_at` is path-shape agnostic anyway (lexical hint compare; *"a path that cannot be
resolved must still get an answer"*). The fixture moves the drive's tree away and recreates the
mountpoint empty, byte-for-byte what a vanished FUSE mount leaves.
"""

from __future__ import annotations

import shutil
import threading
from pathlib import Path

import pytest
from truestill_app.service.backup import backup_run
from truestill_app.service.drives import attach_drive, list_drives
from truestill_cli.cli import main
from truestill_core.drive import DriveGhostError, read_marker


@pytest.fixture
def unplugged(tmp_path: Path) -> tuple[Path, Path, str]:
    """A registered drive whose recorded path is now an empty directory - the unmount shape.

    Registered through the CLI because `drives --init` both writes the marker and records the
    path hint, which is the one fact `ghost_drive_at` discriminates on.
    """
    root, db = tmp_path / "BackupHDD", tmp_path / "c.sqlite"
    root.mkdir()
    assert main(["drives", "--init", str(root), "--label", "Backup HDD", "--db", str(db)]) == 0
    label_uuid = read_marker(root)
    assert label_uuid is not None, "fixture check: the drive registered"

    shutil.move(str(root), str(tmp_path / "actually-unplugged"))
    root.mkdir()  # the mountpoint is back, empty - what an unmounted drive looks like
    return root, db, label_uuid.uuid


def test_attach_does_not_mint_at_a_ghost_path(unplugged: tuple[Path, Path, str]) -> None:
    """⚠ **THE HEADLINE - fails against yesterday's code by MINTING.**"""
    ghost, db, _real_uuid = unplugged
    before = len(list_drives(db))

    with pytest.raises(DriveGhostError):
        attach_drive(ghost, db, write=True)

    assert read_marker(ghost) is None, "the guard refused AND STILL WROTE THE MARKER"
    assert len(list_drives(db)) == before, "a phantom identity reached the catalog"


def test_the_refusal_names_the_drive_and_the_path(unplugged: tuple[Path, Path, str]) -> None:
    """⚠ **Q120.** "Plug the drive in" is only the obvious next step if the user learns it is
    their *Backup HDD* that is missing - a path alone reads as "delete this folder"."""
    ghost, db, _uuid = unplugged

    with pytest.raises(DriveGhostError) as raised:
        attach_drive(ghost, db, write=True)

    message = str(raised.value)
    assert "Backup HDD" in message, "the refusal does not name the drive"
    assert str(ghost) in message, "the refusal does not name the recorded path"
    assert "not plugged in or not mounted" in message


def test_backup_run_is_refused_at_a_ghost_target_and_mints_nothing(
    unplugged: tuple[Path, Path, str], tmp_path: Path
) -> None:
    """The reachable user flow: *"Copy your library to another drive"* at the usual path.

    The SECOND path is the ghost (`(agr)` Q114): the legitimate source attaches first - harmless,
    idempotent, work the run needed - and the run then refuses before any copy, naming the
    target. The marker-absence assertion repeats here THROUGH the caller, because the guard
    living in `attach_drive` is exactly what this pins.
    """
    ghost, db, _uuid = unplugged
    source = tmp_path / "library"
    source.mkdir()
    (source / "a.txt").write_text("not a photo, and that is fine for this test")

    target = backup_run(source, ghost, db)
    with pytest.raises(DriveGhostError) as raised:
        target(lambda _p: None, threading.Event())

    assert read_marker(ghost) is None, "backup minted at the ghost target"
    assert "Backup HDD" in str(raised.value)
    assert read_marker(source) is not None, (
        "the legitimate source should have attached before the refusal - idempotent work the "
        "run needed either way"
    )


def test_a_genuinely_new_folder_still_registers(tmp_path: Path) -> None:
    """⚠ **CRY-WOLF HALF ONE.** A guard that refused every unmarked folder would break the whole
    attach feature - `ghost_drive_at` fails open on purpose: no recorded hint means no opinion."""
    db = tmp_path / "c.sqlite"
    fresh = tmp_path / "BrandNewDrive"
    fresh.mkdir()

    outcome = attach_drive(fresh, db, write=True)

    assert outcome.registered is True
    assert read_marker(fresh) is not None, "a genuinely new folder was refused registration"


def test_the_real_drive_at_its_own_path_is_never_refused(tmp_path: Path) -> None:
    """⚠ **CRY-WOLF HALF TWO.** The real drive, plugged in, marker present: `ghost_drive_at`
    answers None the moment a marker exists (`drive.py`: "a marker is here: whatever this is,
    it is not a ghost"), and attach must stay idempotent - same uuid, no refusal."""
    root, db = tmp_path / "BackupHDD", tmp_path / "c.sqlite"
    root.mkdir()
    assert main(["drives", "--init", str(root), "--label", "Backup HDD", "--db", str(db)]) == 0
    marker = read_marker(root)
    assert marker is not None

    # `registered` means "newly registered by THIS call" - False here is the correct existing
    # answer for a drive that already had its marker, and the first draft of this test misread
    # it. What the cry-wolf half actually pins: no refusal raised, and the identity unchanged.
    attach_drive(root, db, write=True)

    after = read_marker(root)
    assert after is not None
    assert after.uuid == marker.uuid, "reattaching the real drive changed its identity"
