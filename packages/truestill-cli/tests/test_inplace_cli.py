"""CLI surface for in-place organize: the confirmation gate, the refusals, and undo."""

from __future__ import annotations

from pathlib import Path

import pytest
from truestill_cli.cli import main


def _library(root: Path, count: int = 2) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    for i in range(count):
        path = root / "DCIM" / f"img{i}.jpg"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(bytes([i + 1]) * 2048)
    return root


def test_in_place_preview_writes_nothing_and_says_so(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _library(tmp_path / "drive")
    before = sorted(p.relative_to(root) for p in root.rglob("*") if p.is_file())

    code = main(["organize", str(root), str(root), "--in-place", "--db", str(tmp_path / "c.db")])

    out = capsys.readouterr().out
    assert code == 0
    assert "files will be MOVED" in out
    assert "Originals will NOT remain" in out
    assert "undo-organize" in out  # the way back is stated up front, not after the fact
    assert sorted(p.relative_to(root) for p in root.rglob("*") if p.is_file()) == before


def test_in_place_apply_aborts_without_the_typed_word(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _library(tmp_path / "drive")
    before = sorted(p.relative_to(root) for p in root.rglob("*") if p.is_file())
    monkeypatch.setattr("builtins.input", lambda _="": "yes")  # not the required word

    code = main(
        ["organize", str(root), str(root), "--in-place", "--apply", "--db", str(tmp_path / "c.db")]
    )

    assert code == 0
    assert "Aborted" in capsys.readouterr().out
    assert sorted(p.relative_to(root) for p in root.rglob("*") if p.is_file()) == before


def test_in_place_apply_moves_and_reports_the_mechanism(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _library(tmp_path / "drive")
    monkeypatch.setattr("builtins.input", lambda _="": "move")

    code = main(
        ["organize", str(root), str(root), "--in-place", "--apply", "--db", str(tmp_path / "c.db")]
    )

    out = capsys.readouterr().out
    assert code == 0
    assert "moved by rename (no bytes copied)" in out  # the split, not just a total
    assert not (root / "DCIM" / "img0.jpg").exists()
    assert len([p for p in root.rglob("*.jpg") if p.is_file()]) == 2


def test_ingest_refuses_in_place_with_a_reason(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Not 'unrecognized argument': a user with a full drive is told why it cannot work."""
    takeout = _library(tmp_path / "takeout")

    code = main(
        ["ingest", "--takeout", str(takeout), str(tmp_path / "out"), "--in-place", "--apply"]
    )

    assert code == 2
    err = capsys.readouterr().err
    assert "cannot be used with ingest" in err
    assert "not byte-identical" in err


def test_undo_lists_runs_and_reverses_the_last_one(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _library(tmp_path / "drive")
    db = tmp_path / "c.db"
    originals = sorted(p for p in root.rglob("*.jpg") if p.is_file())
    monkeypatch.setattr("builtins.input", lambda _="": "move")
    main(["organize", str(root), str(root), "--in-place", "--apply", "--db", str(db)])
    assert not originals[0].exists()
    capsys.readouterr()

    assert main(["undo-organize", "--list", "--db", str(db)]) == 0
    assert "completed" in capsys.readouterr().out

    assert main(["undo-organize", "--db", str(db)]) == 0
    assert "Preview only" in capsys.readouterr().out
    assert not originals[0].exists()  # preview moved nothing

    assert main(["undo-organize", "--apply", "--db", str(db)]) == 0
    assert "Restored 2 file(s)" in capsys.readouterr().out
    assert all(p.is_file() for p in originals)


def test_undo_with_nothing_recorded_is_a_clear_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(["undo-organize", "--db", str(tmp_path / "empty.db")])

    assert code == 2
    assert "nothing has been organized in place" in capsys.readouterr().err
