"""Smoke tests for the CLI wiring (does not require exiftool)."""

from __future__ import annotations

from pathlib import Path

import pytest
from vaeon_cli.cli import main


def test_help_exits_zero() -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0


def test_empty_source_reports_nothing(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    source = tmp_path / "empty"
    source.mkdir()
    code = main([str(source), str(tmp_path / "out")])
    assert code == 0
    assert "No media files" in capsys.readouterr().out


def test_missing_source_is_an_error(tmp_path: Path) -> None:
    code = main([str(tmp_path / "does-not-exist"), str(tmp_path / "out")])
    assert code == 2
