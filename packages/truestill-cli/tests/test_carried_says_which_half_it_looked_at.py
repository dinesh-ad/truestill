"""`truestill carried` - what a drive holds that this catalog does not. Stage 1 of restore.

⚠ **THIS COMMAND CANNOT TAKE `--apply`, AND THAT IS THE POINT OF IT BEING A COMMAND.** The
comparison it prints is already reachable: `truestill backup <drive> <library>` without `--apply`
prints it, because `copy_to_drive` is direction-agnostic and its only directional refusal is that
the two sides are the same drive. **Which means the restore it previews is reachable today by
adding `--apply`** - an operation nobody has designed, with no collision policy and no undo,
behind wording that says "copy your library to a second drive". So the question gets its own
read-only command rather than an instruction to run `backup` backwards.

The three states the output has to tell apart are the subject of every test here, and two of them
look like the third: a real zero, a drive nobody walked, and a library nothing looked at.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from truestill_cli.cli import main
from truestill_core.catalog import Catalog
from truestill_core.drive import create_marker, read_marker


def _sha(index: int) -> str:
    return f"{index:064x}"


def _both(tmp_path: Path) -> tuple[Path, Path, Path]:
    """A registered drive and a registered library, no rows on either yet."""
    db = tmp_path / "c.sqlite"
    drive, library = tmp_path / "Backup", tmp_path / "Library"
    drive.mkdir(parents=True)
    library.mkdir(parents=True)
    on_drive, here = (
        create_marker(drive, label="Backup Drive"),
        create_marker(library, label="My Library"),
    )
    with Catalog(db) as catalog:
        catalog.upsert_drive(uuid=on_drive.uuid, label=on_drive.label)
        catalog.upsert_drive(uuid=here.uuid, label=here.label)
    return db, drive, library


def _record(db: Path, root: Path, indexes: range, *, on_disk: bool) -> None:
    # ⚠ `read_marker`, never `create_marker` - the first version of this helper called
    # `create_marker` on a drive that already had one, which MINTS A NEW UUID. The rows then sat
    # under an identity the `drives` table had never heard of, and every connected test still
    # passed because a connected run reads the same marker back. Only the by-label test noticed.
    marker = read_marker(root)
    assert marker is not None
    with Catalog(db) as catalog:
        for index in indexes:
            relative = f"Camera/2014/p{index:04d}.jpg"
            catalog.record_copy(
                sha256=_sha(index),
                drive_uuid=marker.uuid,
                relative=relative,
                size=17,
                copy_sha256=None,
            )
            if on_disk:
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(b"x" * 17)


# ------------------------------------------------------------------- the three cases, on the CLI


def test_a_complete_library_reports_zero_and_exits_zero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Nothing to fetch, and a script can chain past it."""
    db, drive, library = _both(tmp_path)
    _record(db, drive, range(5), on_disk=False)
    _record(db, library, range(5), on_disk=True)

    assert main(["carried", str(drive), str(library), "--db", str(db)]) == 0
    assert "carries 0 file(s)" in capsys.readouterr().out


def test_a_gap_is_counted_named_as_records_and_exits_one(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """⚠ **Exit 1 is `rescan`'s precedent**: something did not reconcile, so
    `truestill carried X Y && next_step` must not chain past it."""
    db, drive, library = _both(tmp_path)
    _record(db, drive, range(10), on_disk=False)
    _record(db, library, range(4), on_disk=True)

    assert main(["carried", str(drive), str(library), "--db", str(db)]) == 1
    out = capsys.readouterr().out
    assert "carries 6 file(s)" in out
    assert "Counted from records, not from a fresh look at the drive" in out


def test_the_drive_may_be_named_by_label_when_it_is_not_connected(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """⚠ **THE STATE THE QUESTION IS USUALLY ASKED FROM.** A person asks what a drive carries
    precisely because they no longer have it, and a path-only argument would refuse at the
    resolver and never reach the catalog - which answers offline, by design.

    The count must be the same one the connected run gives, and the output must say the drive was
    not read, because a number read with no disk in hand is a different fact.
    """
    db, drive, library = _both(tmp_path)
    _record(db, drive, range(9), on_disk=False)
    _record(db, library, range(2), on_disk=True)
    for path in sorted(drive.rglob("*"), reverse=True):
        path.unlink() if path.is_file() else path.rmdir()
    drive.rmdir()

    assert main(["carried", "Backup Drive", str(library), "--db", str(db)]) == 1
    out = capsys.readouterr().out
    assert "carries 7 file(s)" in out
    assert "is NOT CONNECTED" in out
    assert str(drive) not in out, "a rescan of a folder that is not there was offered"


def test_a_path_that_is_not_there_is_told_about_the_label(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """⚠ **Found by running it.** The generic refusal says "is it plugged in?" and stops, which
    sends somebody who has lost the disk away to look for it - when the catalog could have
    answered them without it. A stated refusal carries its remedy."""
    db, drive, library = _both(tmp_path)
    _record(db, drive, range(3), on_disk=False)
    for path in sorted(drive.rglob("*"), reverse=True):
        path.unlink() if path.is_file() else path.rmdir()
    drive.rmdir()

    assert main(["carried", str(drive), str(library), "--db", str(db)]) == 2
    err = capsys.readouterr().err
    assert "Name it instead of its folder" in err
    assert "Backup Drive" in err


# ---------------------------------------------------------------- the answer that must not be 0


def test_a_drive_nobody_walked_refuses_to_print_a_number(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """⚠ **THE WORST WRONG ANSWER IN THE PRODUCT, one `drives --init` away.**

    That command writes a marker and does not walk, so `file_copies` is empty while the drive is
    full. A set difference reads **0 carried** and tells somebody who has just lost a disk that
    their backup holds nothing to recover. Exit 1, because there IS something to act on.
    """
    db, drive, library = _both(tmp_path)
    _record(db, library, range(5), on_disk=True)

    assert main(["carried", str(drive), str(library), "--db", str(db)]) == 1
    out = capsys.readouterr().out
    assert "no record of anything on 'Backup Drive'" in out
    assert "not the same as the drive being empty" in out
    assert "0 file(s)" not in out
    assert f"truestill rescan {drive}" in out


# ------------------------------------------------------------------------------- the refusals


def test_the_same_drive_twice_is_refused(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    db, _drive, library = _both(tmp_path)
    assert main(["carried", str(library), str(library), "--db", str(db)]) == 2
    assert "same drive" in capsys.readouterr().err


def test_an_unregistered_folder_is_refused_rather_than_registered(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`_cmd_backup`'s rule: registering is a distinct act with its own ghost guard, and a
    command that mints a drive id as a side effect is how a ghost drive is created from a
    shell. A **read-only** command doing it would be worse, not better."""
    db, _drive, library = _both(tmp_path)
    stranger = tmp_path / "NotADrive"
    stranger.mkdir()

    assert main(["carried", str(stranger), str(library), "--db", str(db)]) == 2
    assert "is not a Truestill drive" in capsys.readouterr().err
    assert not (stranger / ".truestill-drive.json").exists()


def test_it_writes_nothing_at_all(tmp_path: Path) -> None:
    """**The property the whole stage rests on**, asserted on bytes rather than on intent."""
    db, drive, library = _both(tmp_path)
    _record(db, drive, range(6), on_disk=False)
    _record(db, library, range(2), on_disk=True)
    before = {p: p.stat().st_mtime_ns for p in library.rglob("*") if p.is_file()}
    catalog_bytes = db.read_bytes()
    assert before, "the library is empty, so the comparison below cannot fail"

    assert main(["carried", str(drive), str(library), "--db", str(db)]) == 1

    assert {p: p.stat().st_mtime_ns for p in library.rglob("*") if p.is_file()} == before
    assert db.read_bytes() == catalog_bytes, "a read-only report changed the catalog"
