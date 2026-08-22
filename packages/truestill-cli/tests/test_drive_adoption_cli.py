"""`drives --init` must not mint a second identity for a library the catalog already has.

`BACKLOG.md` ``(aap)``. Observed on the shipped build: point `--init` at a tree whose files are
already recorded under another drive uuid and it mints a fresh uuid with no warning. The catalog
then holds two drives for one library - and `moving-machines.md` names exactly this as the worst
failure mode of a move, because the user's copies look orphaned (CLI) or doubly-redundant (app).

The CLI actively steered people here: with a drive unmounted, `verify` printed *"isn't a
truestill drive yet - register it with `truestill drives --init`"*. Both halves are fixed
together; a fix that reached one copy of a message and not its twin is this repo's named
recurring defect.
"""

from __future__ import annotations

import json
import os
import random
import shutil
from pathlib import Path

import pytest
from PIL import Image
from truestill_cli.cli import main
from truestill_core.catalog import Catalog


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
def library(tmp_path: Path) -> tuple[Path, Path, Path]:
    """An organized drive, plus a marker-less copy of it - the move that lost its marker."""
    src, drive, db = tmp_path / "src", tmp_path / "DriveA", tmp_path / "c.sqlite"
    src.mkdir()
    for i in range(4):
        _jpeg(src / f"p{i}.jpg", seed=i, size=(64 + i, 64))
    assert main(["drives", "--init", str(drive), "--label", "Photos HDD", "--db", str(db)]) == 0
    assert main(["organize", str(src), str(drive), "--apply", "--db", str(db)]) == 0

    moved = tmp_path / "DriveMoved"
    shutil.copytree(drive, moved)
    (moved / ".truestill-drive.json").unlink()
    return drive, moved, db


def test_init_refuses_to_mint_over_a_library_the_catalog_already_knows(
    library: tuple[Path, Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    """The bug. Minting here is what makes a user's backups look like they never existed."""
    _drive, moved, db = library

    code = main(["drives", "--init", str(moved), "--label", "New Drive", "--db", str(db)])
    out = capsys.readouterr()
    combined = out.out + out.err

    assert code == 2, "minting a duplicate identity must fail, not succeed quietly"
    assert "Photos HDD" in combined, "the user must be told WHICH drive this already is"
    # Both, separately: a refusal naming only one way forward is a dead end for whoever has
    # the other case.
    assert "--adopt-existing" in combined
    assert "--force-new-identity" in combined
    assert not (moved / ".truestill-drive.json").exists(), "a refusal must write nothing"

    listed = main(["drives", "--db", str(db)])
    assert listed == 0
    assert capsys.readouterr().out.count("Photos HDD") == 1, "no second drive may have appeared"


def test_adopt_existing_reuses_the_uuid_so_the_library_stays_one_drive(
    library: tuple[Path, Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    """The repair: one drive, at its new location, with its recorded copies intact."""
    drive, moved, db = library
    original = (drive / ".truestill-drive.json").read_text()

    code = main(
        ["drives", "--init", str(moved), "--label", "x", "--adopt-existing", "--db", str(db)]
    )
    assert code == 0
    adopted = (moved / ".truestill-drive.json").read_text()
    assert '"uuid"' in adopted
    assert json.loads(adopted)["uuid"] == json.loads(original)["uuid"], (
        "adoption must reuse the recorded uuid; a new one orphans every file_copies row"
    )
    assert json.loads(adopted)["label"] == "Photos HDD", (
        "the adopted label comes from the catalog, not from --label: the drive is that drive"
    )
    capsys.readouterr()


def test_force_new_identity_still_works_because_a_clone_is_legitimate(
    library: tuple[Path, Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    """Declining must be possible. Two physical drives holding the same photos are two drives.

    This is why adoption is never automatic: the evidence for "same library" and the evidence
    for "second copy of that library" is identical, and only the user knows which they have.
    """
    _drive, moved, db = library

    code = main(
        [
            "drives",
            "--init",
            str(moved),
            "--label",
            "Clone HDD",
            "--force-new-identity",
            "--db",
            str(db),
        ]
    )
    assert code == 0
    assert (moved / ".truestill-drive.json").exists()
    capsys.readouterr()

    assert main(["drives", "--db", str(db)]) == 0
    listing = capsys.readouterr().out
    assert "Photos HDD" in listing
    assert "Clone HDD" in listing


def test_an_unrelated_folder_initialises_with_no_adoption_prompt(
    library: tuple[Path, Path, Path], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Cry-wolf half. A check that fires on a genuinely new drive would be switched off in a week."""
    _drive, _moved, db = library
    fresh = tmp_path / "BrandNew"
    fresh.mkdir()
    _jpeg(fresh / "unrelated.jpg", seed=999, size=(50, 50))

    code = main(["drives", "--init", str(fresh), "--label", "Brand New", "--db", str(db)])
    out = capsys.readouterr().out

    assert code == 0, "an unrelated folder must still register in one step"
    assert "already" not in out.lower()
    assert "adopt" not in out.lower()


def test_verify_on_an_absent_path_asks_about_the_drive_rather_than_sending_you_to_init(
    library: tuple[Path, Path, Path], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The message that caused the damage.

    An unplugged drive and an unregistered folder are different states with opposite remedies,
    and the old wording gave the dangerous remedy for both.
    """
    _drive, _moved, db = library
    gone = tmp_path / "NotMounted"

    code = main(["verify", str(gone), "--db", str(db)])
    err = capsys.readouterr().err

    assert code == 2
    assert "drives --init" not in err, (
        "telling someone to register a path that is simply not mounted is what mints the "
        "duplicate identity this item exists to prevent"
    )
    assert "isn't a truestill drive yet" not in err
    assert "plugged in" in err.lower() or "not there" in err.lower()


def test_an_existing_unregistered_folder_still_gets_the_register_suggestion(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The other half of that message, which was correct and must survive.

    A folder that *is* there and simply is not a drive should still be told how to become one -
    otherwise fixing the absent-path wording would strand the case it was written for.
    """
    here = tmp_path / "SomeFolder"
    here.mkdir()

    code = main(["verify", str(here), "--db", str(tmp_path / "c.sqlite")])
    err = capsys.readouterr().err

    assert code == 2
    assert "drives --init" in err


def _deny_the_library(moved: Path) -> Path:
    """Make most of a moved library unreadable, and return a KNOWN denied child.

    ⚠ Returned rather than discovered: `glob` has to read the directory, which is the thing being
    denied, so it comes back empty instead of raising - and `os.stat` on the folder itself
    succeeds, because that needs execute on the parent. Both traps skip the test silently.
    """
    inner = next(p for p in sorted(moved.rglob("*.jpg")))
    inner.parent.chmod(0o000)
    return inner


def test_init_refuses_a_library_it_could_not_read_rather_than_minting_a_second_id(
    library: tuple[Path, Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    """⚠ THE DEFECT. A drive the product could not read was registered as a NEW one, silently.

    `inspect_root` returned `[]` because `NO_MATCH` is filtered, so `_init_drive`'s refusal never
    fired and a second drive id was minted for one library - the exact harm the refusal beside it
    describes. `(afn)`
    """
    _drive, moved, db = library
    denied_child = _deny_the_library(moved)
    try:
        try:
            os.stat(denied_child)  # noqa: PTH116 - precondition, independent of the subject
            pytest.skip("running as root, or a filesystem that ignores the mode")
        except PermissionError:
            pass
        code = main(["drives", "--init", str(moved), "--label", "Second", "--db", str(db)])
    finally:
        denied_child.parent.chmod(0o755)

    assert code == 2, "a drive that could not be read was registered anyway"
    assert not (moved / ".truestill-drive.json").exists()
    with Catalog(db) as catalog:
        assert len(catalog.list_drives()) == 1, "a second drive id was minted for one library"

    err = capsys.readouterr().err
    assert "could not be read" in err
    assert "would not open" in err
    assert "--force-new-identity" in err, "the refusal must name the way through"
    # ⚠ It must NOT claim to know what the folder holds - that is what it could not find out.
    assert "already holds the library recorded as" not in err


def test_the_unreadable_refusal_is_a_message_and_not_a_dead_end(
    library: tuple[Path, Path, Path],
) -> None:
    """The cost of this ruling is refusing a legitimate action, so the escape must work.

    A user who knows the folder really is a new place passes the flag the message names, and it
    registers - `cli.py` skips the inspection entirely when it is given.
    """
    _drive, moved, db = library
    denied_child = _deny_the_library(moved)
    try:
        try:
            os.stat(denied_child)  # noqa: PTH116 - precondition, independent of the subject
            pytest.skip("running as root, or a filesystem that ignores the mode")
        except PermissionError:
            pass
        code = main(
            [
                "drives",
                "--init",
                str(moved),
                "--label",
                "Second",
                "--db",
                str(db),
                "--force-new-identity",
            ]
        )
    finally:
        denied_child.parent.chmod(0o755)

    assert code == 0, "the escape the refusal names does not work"
    with Catalog(db) as catalog:
        assert len(catalog.list_drives()) == 2, "a genuinely new drive could not be registered"
