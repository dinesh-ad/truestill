"""The `clean-empty` gate: two removals, two different questions, two different words."""

from __future__ import annotations

from pathlib import Path

import pytest
from truestill_cli.cli import main
from truestill_core.catalog import Catalog
from truestill_core.drive import create_marker


def _drive_with_leftovers(tmp_path: Path) -> tuple[Path, Path]:
    """A drive whose migration journal records an emptied, now-empty Camera skeleton."""
    root = tmp_path / "drive"
    root.mkdir()
    marker = create_marker(root, "Drive A")
    (root / "Camera/2023/08").mkdir(parents=True)
    db = tmp_path / "c.sqlite"
    with Catalog(db) as catalog:
        catalog.upsert_drive(uuid=marker.uuid, label="Drive A")
        catalog.start_migration_run("run-1", marker.uuid)
        catalog.record_migration_moves(
            [("sha-1", marker.uuid, "Camera/2023/08/x.jpg", "2023/2023-08/x.jpg", None, "run-1")]
        )
        catalog.complete_migration_move("sha-1", marker.uuid)
    return root, db


def test_permanent_mode_demands_its_own_word_and_rejects_clean(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """ "clean" was given for a recoverable removal; it must not be reused for an irreversible one.

    Otherwise the word a user typed once, understanding it meant "to the trash", would silently
    authorise something they never agreed to.
    """
    root, db = _drive_with_leftovers(tmp_path)

    monkeypatch.setattr("builtins.input", lambda *_: "clean")
    assert main(["clean-empty", str(root), "--db", str(db), "--apply", "--permanent"]) == 0

    assert "Aborted. Nothing was removed." in capsys.readouterr().out
    assert (root / "Camera/2023/08").is_dir()


@pytest.mark.parametrize("answer", ["", "yes", "delete", "DELETE FOREVER", "delete  forever"])
def test_only_the_exact_phrase_proceeds(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, answer: str
) -> None:
    root, db = _drive_with_leftovers(tmp_path)

    monkeypatch.setattr("builtins.input", lambda *_, a=answer: a)
    assert main(["clean-empty", str(root), "--db", str(db), "--apply", "--permanent"]) == 0

    assert "Aborted. Nothing was removed." in capsys.readouterr().out
    assert (root / "Camera/2023/08").is_dir()


def test_the_permanent_warning_is_stated_before_the_prompt(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Irreversibility is disclosed before the word is asked for, not after it is given."""
    root, db = _drive_with_leftovers(tmp_path)

    monkeypatch.setattr("builtins.input", lambda *_: "no")
    main(["clean-empty", str(root), "--db", str(db), "--apply", "--permanent"])

    out = capsys.readouterr().out
    assert "NOT recoverable" in out
    assert "rmdir" in out  # and that a folder which is no longer empty cannot go


def test_clean_empty_refuses_non_interactive_stdin(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    root, db = _drive_with_leftovers(tmp_path)
    monkeypatch.setattr("builtins.input", lambda *_: (_ for _ in ()).throw(EOFError()))

    assert main(["clean-empty", str(root), "--db", str(db), "--apply"]) == 0
    assert "interactive confirmation is required" in capsys.readouterr().err
    assert (root / "Camera/2023/08").is_dir()


def test_clean_empty_permanent_refuses_non_interactive_stdin(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    root, db = _drive_with_leftovers(tmp_path)
    monkeypatch.setattr("builtins.input", lambda *_: (_ for _ in ()).throw(EOFError()))

    assert main(["clean-empty", str(root), "--db", str(db), "--apply", "--permanent"]) == 0
    assert "interactive confirmation is required" in capsys.readouterr().err
    assert (root / "Camera/2023/08").is_dir()


def test_the_exact_phrase_removes_the_skeleton(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    root, db = _drive_with_leftovers(tmp_path)

    monkeypatch.setattr("builtins.input", lambda *_: "delete forever")
    assert main(["clean-empty", str(root), "--db", str(db), "--apply", "--permanent"]) == 0

    assert "Removed 3 folder(s)" in capsys.readouterr().out
    assert not (root / "Camera").exists()


def test_a_preview_of_permanent_mode_still_removes_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root, db = _drive_with_leftovers(tmp_path)

    assert main(["clean-empty", str(root), "--db", str(db), "--permanent"]) == 0

    assert "Preview only. Nothing was removed." in capsys.readouterr().out
    assert (root / "Camera/2023/08").is_dir()


def _drive_with_an_in_place_run(tmp_path: Path) -> tuple[Path, Path]:
    """A drive whose leftovers came from `organize --in-place`, not from a layout migration."""
    root = tmp_path / "drive"
    root.mkdir()
    marker = create_marker(root, "Drive B")
    (root / "Old Folder").mkdir(parents=True)
    db = tmp_path / "c.sqlite"
    with Catalog(db) as catalog:
        catalog.upsert_drive(uuid=marker.uuid, label="Drive B")
        catalog.start_inplace_run(
            run_id="run-9", source_root=str(root), dest_root=str(root), drive_uuid=marker.uuid
        )
        catalog.record_inplace_move(
            run_id="run-9",
            sha256="c" * 64,
            old_relative="Old Folder/x.jpg",
            new_relative="2023/2023-08/x.jpg",
        )
        catalog.finish_inplace_run("run-9")
    return root, db


def test_clean_empty_sees_what_an_in_place_organize_emptied(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """⚠ It answered *"no migration leftovers recorded"* here until 2026-08-22.

    `organize --in-place` writes `inplace_moves`; `migrated_old_paths` read `migration_journal`
    alone. So the mode that leaves the MOST behind - every file moves out of a tree the user built
    by hand - was the one whose leftovers nothing could see. `(afi)`
    """
    root, db = _drive_with_an_in_place_run(tmp_path)

    assert main(["clean-empty", str(root), "--db", str(db)]) == 0

    out = capsys.readouterr().out
    assert "no migration leftovers recorded" not in out
    assert "Old Folder" in out
    assert (root / "Old Folder").is_dir(), "a preview removed something"


def test_a_folder_that_could_not_be_opened_is_not_called_one_with_something_in_it(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """⚠ It printed two contradictory claims on one line, and the truth was neither. `(afo)`

    ``LEFT ALONE - something is in there (1):`` above ``Camera/2013   []`` - the heading claiming
    contents, the bracket claiming none. Worse than silence, because it asserts.

    The wording is `(aer)`'s, not a fourth phrase for one fact: the scan report already says
    *"folders that could not be opened"*.
    """
    root = tmp_path / "drive"
    root.mkdir()
    marker = create_marker(root, "Drive A")
    (root / "Camera/2023/08").mkdir(parents=True)
    refused = root / "Camera/2023/09"
    refused.mkdir()
    db = tmp_path / "c.sqlite"
    with Catalog(db) as catalog:
        catalog.upsert_drive(uuid=marker.uuid, label="Drive A")
        catalog.start_migration_run("run-1", marker.uuid)
        catalog.record_migration_moves(
            [
                ("sha-1", marker.uuid, "Camera/2023/08/x.jpg", "2023/x.jpg", None, "run-1"),
                ("sha-2", marker.uuid, "Camera/2023/09/y.jpg", "2023/y.jpg", None, "run-1"),
            ]
        )
        catalog.complete_migration_move("sha-1", marker.uuid)
        catalog.complete_migration_move("sha-2", marker.uuid)

    refused.chmod(0o111)  # traversable, not listable: it stats, iterdir raises
    try:
        try:
            list(refused.iterdir())
            pytest.skip("running as root, or a filesystem that ignores the mode")
        except PermissionError:
            pass
        assert main(["clean-empty", str(root), "--db", str(db)]) == 0
    finally:
        refused.chmod(0o755)

    out = capsys.readouterr().out
    assert "could not be opened" in out, "it does not say what actually happened"
    assert "Camera/2023/09   []" not in out, "the empty bracket claims there is nothing in it"
    # The heading that claims contents must not count the folder nobody could look into.
    assert "something is in there (1)" not in out
