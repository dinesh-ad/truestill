"""CLI announces the resolved catalog path; first-run is not an error."""

from __future__ import annotations

from pathlib import Path

import pytest
from truestill_cli.cli import main
from truestill_core.catalog import Catalog


def test_cli_first_run_prints_will_create(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    code = main(["status"])
    assert code == 0
    out = capsys.readouterr().out
    assert "Catalog: " in out
    assert str((tmp_path / "reports" / "catalog.sqlite").resolve()) in out
    assert "No catalog yet" in out
    for banned in ("Error", "WARNING", "failed"):
        assert banned not in out


def test_cli_explicit_db_honoured(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = tmp_path / "my.sqlite"
    with Catalog(db):
        pass
    code = main(["status", "--db", str(db)])
    assert code == 0
    out = capsys.readouterr().out
    assert str(db.resolve()) in out
    assert "from --db" in out or "empty catalog" in out


def test_cli_empty_with_drives_goes_to_stderr(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    db = tmp_path / "c.sqlite"
    with Catalog(db) as catalog:
        catalog.upsert_drive(uuid="d1", label="Cabinet")
    code = main(["status", "--db", str(db)])
    assert code == 0
    captured = capsys.readouterr()
    assert "0 files but 1 drive" in captured.err
    assert str(db.resolve()) in captured.err or str(db.resolve()) in captured.out
