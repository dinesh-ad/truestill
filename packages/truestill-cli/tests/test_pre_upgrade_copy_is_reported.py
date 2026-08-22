"""`(ady)`: a pre-upgrade copy that could not be taken reaches the user.

The core tests prove the OUTCOME is recorded. This proves the **wiring** - that the CLI's seam
passes it to a reporter and the reporter says something. Those are different claims, and the one
that has historically been wrong here is the second: a value computed correctly and rendered
nowhere is `(aer)`'s shape and §4's fourteenth member.

Asserts on the OUTPUT rather than on the source, because the rule is about what a program says.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from truestill_cli import cli
from truestill_core import catalog_backup
from truestill_core.catalog import CURRENT_SCHEMA_VERSION, Catalog


def _behind(path: Path) -> Path:
    with Catalog(path):
        pass
    con = sqlite3.connect(path)
    con.execute(f"PRAGMA user_version = {CURRENT_SCHEMA_VERSION - 1}")
    con.commit()
    con.close()
    return path


def test_a_copy_that_failed_is_said_on_stderr(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The whole point of degrade-and-say: the user is told the safety net was not there."""
    db = _behind(tmp_path / "catalog.sqlite")

    def refuse(*_args: object, **_kwargs: object) -> None:
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(catalog_backup, "_copy", refuse)

    with cli._catalog(db):
        pass

    err = capsys.readouterr().err
    assert "No space left on device" in err, err
    assert "upgrade" in err, err


def test_a_copy_that_worked_says_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Cry-wolf half. Success is silent, or the line becomes noise and gets ignored.

    Without this the reporter could print on every upgrade and the test above would still pass.
    """
    db = _behind(tmp_path / "catalog.sqlite")

    with cli._catalog(db):
        pass

    captured = capsys.readouterr()
    assert captured.err == "", captured.err
    assert "upgrade" not in captured.out


def test_an_ordinary_open_reports_nothing_at_all(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The common case - no migration, so no outcome exists and the reporter is never reached."""
    db = tmp_path / "catalog.sqlite"
    with Catalog(db):
        pass

    with cli._catalog(db) as catalog:
        assert catalog.pre_migration_backup is None

    assert capsys.readouterr().err == ""
