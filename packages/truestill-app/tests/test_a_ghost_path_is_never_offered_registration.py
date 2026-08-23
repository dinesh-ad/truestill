"""No app surface advises registering at a ghost path. `(agr)` part 2.

⚠ **THE DEFECT**: `verify_run` at the recorded path of an unplugged drive answered *"This folder
isn't set up as a backup drive yet... **or register this drive first**"* with
`can_register: true` - the one suggestion `(afc)` forbade, at the one path where following it
used to mint a phantom identity (part 1 now refuses the mint). And it was never one surface:
the app's door - `drive_support.not_a_drive_message` / `drive_correction` - serves **nine**
soft-fail sites across verify, migrate, bake and trips, plus three exception-form raises, and
`(afc)`'s fix reached only the CLI's door (`_drive_or_explain`). The part-1 shape again: one
door per surface, and one of them never learned the rule.

**So the fix is the door, once**: the ghost branch sits between "unreachable" and
"unregistered", exactly where the CLI put it, wording from `ghost_drive_refusal` - the one home -
and `can_register` is **False** there because part 1 made it literally false.

⚠ **At the exception door the TYPE changes**, not just the sentence: `NotABackupDriveError` is
keyed by `app.js`'s `FRIENDLY_ERRORS`, which renders its own register-this advice regardless of
the message - so `not_a_drive` returns `DriveGhostError` at a ghost, whose message renders
verbatim, the same sentence the CLI prints (`(afe)`'s one-sentence rule).
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from truestill_app.service.drive_support import NotABackupDriveError, drive_correction, not_a_drive
from truestill_app.service.verify import verify_run
from truestill_cli.cli import main
from truestill_core.drive import DriveGhostError, read_marker


@pytest.fixture
def unplugged(tmp_path: Path) -> tuple[Path, Path]:
    """A registered drive whose recorded path is now an empty directory - the unmount shape."""
    root, db = tmp_path / "BackupHDD", tmp_path / "c.sqlite"
    root.mkdir()
    assert main(["drives", "--init", str(root), "--label", "Backup HDD", "--db", str(db)]) == 0
    shutil.move(str(root), str(tmp_path / "actually-unplugged"))
    root.mkdir()
    return root, db


def test_verify_at_a_ghost_path_says_the_drive_is_missing_not_register_it(
    unplugged: tuple[Path, Path],
) -> None:
    """⚠ **THE HEADLINE - fails against yesterday's code with the forbidden sentence.**"""
    ghost, db = unplugged

    payload = verify_run(ghost, db)

    assert isinstance(payload, dict), "a ghost path started a verify job"
    assert "register this drive" not in payload["error"], "the forbidden advice survived"
    assert "is where Truestill recorded the drive 'Backup HDD'" in payload["error"]
    assert "not plugged in or not mounted" in payload["error"]
    assert payload["can_register"] is False, (
        "can_register asserted a registration part 1 now refuses - the payload contradicting "
        "the guard is the two-places-disagree shape"
    )
    assert payload["drive_label"] == "Backup HDD"


def test_the_exception_door_changes_type_at_a_ghost(unplugged: tuple[Path, Path]) -> None:
    """`FRIENDLY_ERRORS` keys on `NotABackupDriveError` and shows its own register advice
    regardless of the message - so at a ghost the sentence can only reach the screen by the
    TYPE changing."""
    ghost, db = unplugged

    exc = not_a_drive(ghost, db)

    assert isinstance(exc, DriveGhostError), f"the ghost raised {type(exc).__name__}"
    assert "Backup HDD" in str(exc)


def test_a_genuinely_new_folder_still_gets_the_register_advice(tmp_path: Path) -> None:
    """⚠ **CRY-WOLF HALF ONE, and the catalog is NOT empty.** The register suggestion is right
    for a folder no drive was ever recorded at - removing it everywhere would orphan the real
    first-run flow. A drive IS registered elsewhere, because the first draft probed against a
    catalog that did not exist yet: the file-first check answered before the ghost logic ran,
    and a mutation that ghosted every unmarked folder survived it."""
    other, db = tmp_path / "SomeOtherDrive", tmp_path / "c.sqlite"
    other.mkdir()
    assert main(["drives", "--init", str(other), "--label", "Other", "--db", str(db)]) == 0
    fresh = tmp_path / "BrandNew"
    fresh.mkdir()

    payload = drive_correction(fresh, db)

    assert "register this drive first" in payload["error"]
    assert payload["can_register"] is True

    exc = not_a_drive(fresh, db)
    assert isinstance(exc, NotABackupDriveError)


def test_the_real_drive_at_its_own_path_is_unaffected(tmp_path: Path) -> None:
    """⚠ **CRY-WOLF HALF TWO.** Marker present: `ghost_drive_at` has no opinion, and verify
    builds its job exactly as before."""
    root, db = tmp_path / "BackupHDD", tmp_path / "c.sqlite"
    root.mkdir()
    assert main(["drives", "--init", str(root), "--label", "Backup HDD", "--db", str(db)]) == 0
    assert read_marker(root) is not None

    target = verify_run(root, db)

    assert not isinstance(target, dict), "the real drive at its own path was refused"


def test_an_unreachable_path_keeps_its_own_answer(tmp_path: Path) -> None:
    """The pre-existing first branch is untouched: a path that is not there gets "can't reach",
    never the ghost sentence and never the register advice - registering needs a real folder."""
    gone = tmp_path / "never-existed"
    db = tmp_path / "c.sqlite"

    payload = drive_correction(gone, db)

    assert "Can't reach" in payload["error"]
    assert payload["can_register"] is False


def test_the_ghost_branch_answers_none_when_there_is_no_catalog_yet(tmp_path: Path) -> None:
    """A first run has recorded no expectation and so has none to violate - and the probe must
    not CREATE the catalog to ask (`Catalog` would): the file-first check is load-bearing."""
    fresh = tmp_path / "SomeFolder"
    fresh.mkdir()
    db = tmp_path / "never-created.sqlite"

    payload = drive_correction(fresh, db)

    assert "register this drive first" in payload["error"]
    assert not db.exists(), "asking the ghost question CREATED the catalog"
