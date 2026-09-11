"""`truestill recover` - the rails, on the terminal. Stage 2 of the restore arc.

⚠ **THE NAME.** `restore` was taken by the decisions command, declared in the lock table as
*"writes catalog rows from a drive's document, never files onto the drive"*. Two commands that
both "restore" and move entirely different things is how a person runs the wrong one, so the
writer is `recover`.

⚠ **AND IT INHERITS THE RAILS THAT `restore` NEVER HAD** - no lock, no run record, no undo. This
one declares `"recover": "library"` in `_LOCKS_DRIVE_AT`, writes a run record on every applied
run, previews by default and asks for a typed word before it writes.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from truestill_cli import cli
from truestill_cli.cli import main
from truestill_core import recover
from truestill_core.app_paths import RUN_RECORD_FILENAME
from truestill_core.catalog import Catalog
from truestill_core.drive import create_marker, read_marker
from truestill_core.hashing import sha256_file

RELATIVE = "Camera/2014/p{:04d}.jpg"


def _content(index: int) -> bytes:
    return f"photograph-{index:04d}-".encode() * 32


def _snapshot(root: Path) -> dict[str, tuple[str, int]]:
    return {
        p.relative_to(root).as_posix(): (sha256_file(p), p.stat().st_mtime_ns)
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


def _world(tmp_path: Path, *, on_drive: int = 40, here: int = 34) -> tuple[Path, Path, Path]:
    """A registered drive with ``on_drive`` photographs and a library with the first ``here``."""
    db = tmp_path / "c.sqlite"
    drive, library = tmp_path / "Backup", tmp_path / "Library"
    drive.mkdir()
    library.mkdir()
    create_marker(drive, label="Backup Drive")
    create_marker(library, label="My Library")
    with Catalog(db) as catalog:
        for root, count in ((drive, on_drive), (library, here)):
            marker = read_marker(root)
            assert marker is not None
            catalog.upsert_drive(uuid=marker.uuid, label=marker.label)
            for index in range(count):
                target = root / RELATIVE.format(index)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(_content(index))
                catalog.record_copy(
                    sha256=f"{index:064x}",
                    drive_uuid=marker.uuid,
                    relative=RELATIVE.format(index),
                    size=len(_content(index)),
                    copy_sha256=None,
                )
    return db, drive, library


def _say(monkeypatch: pytest.MonkeyPatch, word: str) -> None:
    """Answer the typed confirmation."""
    monkeypatch.setattr("builtins.input", lambda _prompt="": word)


# --------------------------------------------------------------------------- preview and apply


def test_a_preview_writes_nothing_and_says_what_it_would_do(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """**Preview by default**, and the promise stated before anything is typed."""
    db, drive, library = _world(tmp_path)
    before = _snapshot(library)

    assert main(["recover", str(drive), str(library), "--db", str(db)]) == 0

    out = capsys.readouterr().out
    assert "6 file(s) to copy" in out
    assert "Preview only. Nothing was copied." in out
    # ⚠ Asserted against the CORE constant, not a copy of it. A literal here would go stale
    # the moment the sentence is reworded, and the reason the sentence lives in core is that
    # the drive card must say the same thing.
    assert recover.NOTHING_IS_LOST.split(". ")[0] in out.replace("\n       ", " ")
    assert "left exactly as it is" in out.replace("\n       ", " ")
    assert _snapshot(library) == before
    assert not (db.parent / RUN_RECORD_FILENAME).exists(), "a preview wrote a run record"


def test_apply_copies_the_gap_and_leaves_every_other_file_alone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """40 against 34 copies 6 - and the 34 are proved untouched by digest and mtime."""
    db, drive, library = _world(tmp_path)
    before = _snapshot(library)
    # Two empty dicts compare equal, so an empty library would make the comparison below free.
    assert len(before) > 1, "the fixture is empty, so 'nothing was touched' proves nothing"
    _say(monkeypatch, "recover")

    assert main(["recover", str(drive), str(library), "--db", str(db), "--apply"]) == 0

    assert "Copied 6 file(s)" in capsys.readouterr().out
    after = _snapshot(library)
    assert {k: v for k, v in after.items() if k in before} == before
    assert len(after) == len(before) + 6


def test_a_second_apply_copies_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """*"copy only adds files"*. The gap is empty, so it reports that and exits 0."""
    db, drive, library = _world(tmp_path)
    _say(monkeypatch, "recover")
    main(["recover", str(drive), str(library), "--db", str(db), "--apply"])
    settled = _snapshot(library)
    capsys.readouterr()

    assert main(["recover", str(drive), str(library), "--db", str(db), "--apply"]) == 0

    assert "Nothing to bring back" in capsys.readouterr().out
    assert _snapshot(library) == settled


# ------------------------------------------------------------------------------ the confirmation


def test_the_wrong_word_aborts_and_copies_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A typed confirmation that accepts anything is decoration."""
    db, drive, library = _world(tmp_path)
    before = _snapshot(library)
    _say(monkeypatch, "yes")

    assert main(["recover", str(drive), str(library), "--db", str(db), "--apply"]) == 2

    assert _snapshot(library) == before


def test_a_non_interactive_shell_refuses_rather_than_assuming_yes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """⚠ EOF on stdin is *"nobody is there to ask"*, which must never read as consent - this is
    the one that would fire under cron.

    ⚠ **THE MESSAGE IS ASSERTED, NOT JUST THE EXIT CODE, and a mutation is why.** Deleting the
    `confirmed is None` arm left this test green: `not None` is true, so the run still exits 2
    having copied nothing. The only thing that changes is what the operator is told - *"Aborted"*,
    as though somebody had declined, instead of *"this cannot run non-interactively"*. Identical
    behaviour, opposite diagnosis, and the exit code cannot tell them apart.
    """
    db, drive, library = _world(tmp_path)
    before = _snapshot(library)

    def no_one_there(_prompt: str = "") -> str:
        raise EOFError

    monkeypatch.setattr("builtins.input", no_one_there)

    assert main(["recover", str(drive), str(library), "--db", str(db), "--apply"]) == 2

    captured = capsys.readouterr()
    assert "cannot run non-interactively" in captured.err
    assert "Aborted" not in captured.out, "a refusal to ask read as somebody declining"
    assert _snapshot(library) == before


# ----------------------------------------------------------------------------------- it refuses


def test_an_unregistered_drive_is_refused_rather_than_registered(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`_cmd_backup`'s rule: registering is a distinct act with its own ghost guard."""
    db, _drive, library = _world(tmp_path)
    stranger = tmp_path / "NotADrive"
    stranger.mkdir()

    assert main(["recover", str(stranger), str(library), "--db", str(db)]) == 2

    assert "is not a Truestill drive" in capsys.readouterr().err
    assert not (stranger / ".truestill-drive.json").exists()


def test_a_drive_that_is_not_there_is_refused(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """⚠ **No route by label here, unlike `carried`.** Stage 1 answers from the catalog and can
    name a drive that is absent; this one reads bytes off it, so a label route would plan a copy
    from a disk nobody can see."""
    db, drive, library = _world(tmp_path)
    for path in sorted(drive.rglob("*"), reverse=True):
        path.unlink() if path.is_file() else path.rmdir()
    drive.rmdir()

    assert main(["recover", str(drive), str(library), "--db", str(db)]) == 2
    assert main(["recover", "Backup Drive", str(library), "--db", str(db)]) == 2
    assert "is not there" in capsys.readouterr().err


def test_a_library_that_is_not_there_is_refused(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    db, drive, library = _world(tmp_path)
    for path in sorted(library.rglob("*"), reverse=True):
        path.unlink() if path.is_file() else path.rmdir()
    library.rmdir()

    assert main(["recover", str(drive), str(library), "--db", str(db)]) == 2
    assert "is not there" in capsys.readouterr().err


def test_the_same_drive_twice_is_refused(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    db, _drive, library = _world(tmp_path)
    assert main(["recover", str(library), str(library), "--db", str(db)]) == 2
    assert "same drive" in capsys.readouterr().err


def test_a_drive_nobody_walked_refuses_and_names_the_command_that_fills_it(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """⚠ **THE WORST WRONG ANSWER, and worse with a writer holding it.**

    `drives --init` writes a marker and does not walk, so `file_copies` is empty while the drive
    is full. Reporting "nothing to bring back" to somebody who has just lost their library, about
    a drive holding all of it, is the most expensive sentence in the product. Exit 1.
    """
    db, _drive, library = _world(tmp_path)
    fresh = tmp_path / "Fresh"
    fresh.mkdir()
    (fresh / "everything.jpg").write_bytes(b"the drive is full")
    marker = create_marker(fresh, label="Never Walked")
    with Catalog(db) as catalog:
        catalog.upsert_drive(uuid=marker.uuid, label=marker.label)

    assert main(["recover", str(fresh), str(library), "--db", str(db), "--apply"]) == 1

    out = capsys.readouterr().out
    assert "'Never Walked'" in out
    assert "not the same as the drive being empty" in out.replace("\n", " ")
    assert f"truestill rescan {fresh}" in out
    assert "file(s) to copy" not in out


# --------------------------------------------------------------------- never overwrite, on the CLI


def test_an_occupied_path_is_kept_and_reported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The rule, and the user being told which rule accounts for the shortfall.

    A person who asked for 6 and sees 5 must be told why, or the missing one reads as a defect.
    """
    db, drive, library = _world(tmp_path)
    squatter = library / RELATIVE.format(39)
    squatter.parent.mkdir(parents=True, exist_ok=True)
    squatter.write_bytes(b"something the user put here")
    _say(monkeypatch, "recover")

    assert main(["recover", str(drive), str(library), "--db", str(db), "--apply"]) == 0

    out = capsys.readouterr().out
    assert squatter.read_bytes() == b"something the user put here"
    assert "Copied 5 file(s)" in out
    assert "1 file(s) were already at that path" in out
    assert "Nothing was overwritten." in out
    assert f"kept: {RELATIVE.format(39)}" in out


# ------------------------------------------------------------------------------------ the rails


def test_it_declares_the_library_as_the_drive_it_locks() -> None:
    """⚠ **The LIBRARY, which is the side being written into.** Locking the drive instead would
    leave the tree that actually changes unprotected, which is the whole point of the lock.

    Read off the table rather than asserted in prose: `_run_holding_the_drive` reaches
    `getattr(args, where)`, so a value naming an argument that does not exist would raise at run
    time rather than fail here.
    """
    assert cli._LOCKS_DRIVE_AT["recover"] == "library"


def test_an_applied_run_writes_a_record_naming_its_kind(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """⚠ **The rail the decisions `restore` never had.** `IMPLEMENTATION_STANDARDS.md` §1: a run
    that changes the library writes down what it did, beside the catalog, without being asked."""
    db, drive, library = _world(tmp_path)
    _say(monkeypatch, "recover")

    main(["recover", str(drive), str(library), "--db", str(db), "--apply"])

    record = json.loads((db.parent / RUN_RECORD_FILENAME).read_text(encoding="utf-8"))
    assert record["run"]["kind"] == "recover"
    assert record["run"]["attempted"] == 6
    assert record["run"]["destination_label"] == "My Library"
    assert len(record["files"]) == 6
