"""A path recorded as a drive's home, with no marker on it, is refused - never offered `--init`.

**The defect, `(afc)`, found by soak three R4 against a real FUSE mount.** A drive was unmounted
cleanly, so its mountpoint became *there, a directory, and empty*. `verify` said:

    error: <mount> isn't a Truestill drive yet.
           Register it with:  truestill drives --init <mount>

Following that minted a **second drive identity** for a library the catalog already held, and
wrote a marker **into the mountpoint** - after which the real drive could not be mounted there
again, and `verify` reported *"has no recorded copies"* about a drive holding forty.

⚠ **The guard for this already existed and was wired to the wrong commands.**
`drive.ghost_drive_at` was written for exactly this - *"A FUSE mountpoint with nothing mounted on
it is an ordinary empty directory: writes into it succeed, and they land on the computer's own
disk"* - and had two callers, both on the `organize` registration path. `drives --init` guards by
**content** (`drive_adoption` samples files) and an empty mountpoint has none, which is the door
`ghost_drive_at`'s own docstring says `(aap)`'s content guard is blind to. The resolver that
produced the advice consulted neither.

**The discriminator is a RECORDED EXPECTATION, not filesystem detection**, and that is the
industry pattern rather than our invention: an unmounted mountpoint is byte-for-byte an ordinary
empty directory (`os.path.ismount` is False, `st_dev` equals the parent's, and it is absent from
`/proc/mounts`), so administrators protect mountpoints with `chattr +i` **by hand** because the
system cannot tell either. Only `path_hint.drive.<uuid>` discriminates.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from truestill_cli.cli import main
from truestill_core.catalog import Catalog
from truestill_core.drive import drive_path_hint


def _a_drive_that_has_gone_missing(tmp_path: Path) -> tuple[Path, Path]:
    """A registered drive whose root is now an empty directory - the mountpoint after unmount.

    Built by registering a real drive and then removing its marker, which is what an unmount
    leaves behind: the recorded path, present and empty. Nothing is monkeypatched.
    """
    db = tmp_path / "c.sqlite"
    root = tmp_path / "mnt"
    root.mkdir()
    assert main(["drives", "--db", str(db), "--init", str(root), "--label", "Backup"]) == 0
    for marker in root.iterdir():
        marker.unlink()
    assert not any(root.iterdir()), "fixture: the mountpoint must be empty, as an unmount leaves it"
    return db, root


def test_verify_refuses_a_ghost_instead_of_offering_registration(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """⚠ THE REGRESSION. The advice that damages the drive must not be printed."""
    db, root = _a_drive_that_has_gone_missing(tmp_path)

    code = main(["verify", str(root), "--db", str(db)])
    err = capsys.readouterr().err

    assert "--init" not in err, (
        "the product told the user to register a folder it has recorded as a drive's home. "
        "Following that mints a second identity and writes a marker into the mountpoint."
    )
    assert "not plugged in or not mounted" in err, "the refusal must name the likely cause"
    assert code != 0


def test_the_refusal_warns_about_the_space_that_disappears(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The sentence nobody would derive alone, and the reason this wording is reused not rewritten.

    Files written into a mountpoint while nothing is mounted are **shadowed the moment the drive
    returns** while still occupying the disk: `verify` calls them missing, `df` shows the space
    gone, and only unmounting reveals them.
    """
    db, root = _a_drive_that_has_gone_missing(tmp_path)

    main(["verify", str(root), "--db", str(db)])
    err = capsys.readouterr().err

    assert "DISAPPEAR" in err
    assert "using the space" in err


def test_init_refuses_the_same_path(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """The command the message used to point at. Guarding the message alone would leave the door.

    `_init_drive` already refuses a folder that **holds** a known library; this is the one that
    holds nothing.
    """
    db, root = _a_drive_that_has_gone_missing(tmp_path)

    code = main(["drives", "--db", str(db), "--init", str(root), "--label", "Backup"])
    err = capsys.readouterr().err

    assert code != 0, "a second identity was minted for a library the catalog already holds"
    assert "not plugged in or not mounted" in err

    with Catalog(db) as catalog:
        assert len(catalog.list_drives()) == 1, "the catalog gained a phantom drive"


def test_a_genuinely_new_folder_is_still_registrable(tmp_path: Path) -> None:
    """⚠ The cry-wolf half. A guard that blocks the ordinary case gets removed.

    Nothing was ever recorded at this path, so there is no expectation to violate.
    """
    db = tmp_path / "c.sqlite"
    fresh = tmp_path / "brand-new"
    fresh.mkdir()

    assert main(["drives", "--db", str(db), "--init", str(fresh), "--label", "Fresh"]) == 0
    with Catalog(db) as catalog:
        assert len(catalog.list_drives()) == 1


def test_a_path_with_no_expectation_offers_both_readings_rather_than_instructing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The residual: no hint, so nothing discriminates. `drive.py:145` calls that the normal state
    for a CLI-only user, so it cannot be refused - and it must not be instructed either.

    The message stops asserting one reading and names both, because the product genuinely does
    not know which is true.
    """
    db = tmp_path / "c.sqlite"
    unknown = tmp_path / "somewhere"
    unknown.mkdir()

    main(["verify", str(unknown), "--db", str(db)])
    err = capsys.readouterr().err

    assert "should be mounted" in err, "the message does not offer the unmounted-drive reading"
    assert "creates a second" in err or "second identity" in err, (
        "it points at --init without saying what that costs if the guess is wrong"
    )


def test_reclaim_records_where_it_found_the_drive(tmp_path: Path) -> None:
    """`(afc)` half E: the discriminator only exists where a path was recorded.

    ⚠ Five CLI commands resolve a drive root; only `verify` and `--init` recorded where they found
    it, and the widening goes in the **apply** paths only, which is why `cli.py:2333` already notes that *"a CLI-only user accumulates drives whose
    location is unknown - and why nothing could tell an unmounted mountpoint from a new folder."*
    A guard that reads a hint is only as good as how often the hint is written.
    """
    db = tmp_path / "c.sqlite"
    root = tmp_path / "drive"
    root.mkdir()
    assert main(["drives", "--db", str(db), "--init", str(root), "--label", "D"]) == 0
    with Catalog(db) as catalog:
        uuid = str(catalog.list_drives()[0]["uuid"])
        catalog.set_setting(drive_path_hint(uuid), "")  # forget where it was

    # ⚠ `--apply` on a drive with nothing to reclaim: it deletes nothing (no candidates) but
    # takes the apply path, which is where the hint is recorded. A PREVIEW deliberately does not
    # record - `test_a_preview_moves_nothing_and_writes_nothing` asserts the catalog file is
    # byte-identical after one, and a location hint is still a write.
    main(["reclaim", str(root), "--db", str(db), "--apply"])

    with Catalog(db) as catalog:
        assert catalog.get_setting(drive_path_hint(uuid)) == str(root), (
            "reclaim resolved this drive root and did not record where it found it"
        )
