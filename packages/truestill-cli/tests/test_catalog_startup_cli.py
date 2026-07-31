"""CLI announces the resolved catalog path; first-run is not an error."""

from __future__ import annotations

from pathlib import Path

import pytest
from truestill_cli.cli import main
from truestill_core.app_paths import default_catalog_path
from truestill_core.catalog import Catalog


def test_cli_first_run_prints_will_create(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A fresh machine announces the OS-conventional catalog, not a path under the CWD.

    This used to assert ``<cwd>/reports/catalog.sqlite``, which is what `(aae)` changed: a
    CWD-relative default is undefined for an installed app. The data directory is redirected by
    the session fixture, so this asserts the *resolved* default rather than a hardcoded home.
    """
    monkeypatch.chdir(tmp_path)

    code = main(["status"])

    assert code == 0
    out = capsys.readouterr().out
    assert "Catalog: " in out
    assert str(default_catalog_path()) in out
    assert "reports" not in out, "a CWD-relative default came back"
    assert "No catalog yet" in out
    for banned in ("Error", "WARNING", "failed"):
        assert banned not in out


def test_an_existing_legacy_catalog_is_still_the_one_announced(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The backwards-compatibility promise, at the surface a user actually reads.

    Someone upgrading must not be told truestill is using a different, empty catalog while
    their real one sits in `reports/` - that reads exactly like data loss.
    """
    monkeypatch.chdir(tmp_path)
    legacy = tmp_path / "reports" / "catalog.sqlite"
    legacy.parent.mkdir()
    with Catalog(legacy):
        pass

    code = main(["status"])

    assert code == 0
    out = capsys.readouterr().out
    assert str(Path("reports/catalog.sqlite")) in out
    assert "No catalog yet" not in out, "an existing catalog was announced as absent"


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
