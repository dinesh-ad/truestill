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
