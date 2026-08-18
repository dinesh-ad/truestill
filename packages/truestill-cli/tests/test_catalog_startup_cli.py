"""CLI announces the resolved catalog path; first-run is not an error."""

from __future__ import annotations

from pathlib import Path

import pytest
from truestill_cli.cli import CATALOG_BUSY_EXIT, main
from truestill_core.app_paths import default_catalog_path
from truestill_core.catalog import Catalog
from truestill_core.catalog_startup import CATALOG_UNUSABLE_EXIT


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


def test_the_cli_refuses_a_zero_byte_catalog_before_it_dispatches(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`(adr)`: every subcommand is refused, not only the catalog ones.

    The banner runs in `_dispatch` ahead of the dispatch table, so this is the one place that
    covers all of them. Asserting the file is still 0 bytes is the real check: a refusal printed
    *after* the inspection opened the catalog would exit non-zero and still have destroyed the
    evidence.
    """
    db = tmp_path / "catalog.sqlite"
    db.write_bytes(b"")

    code = main(["status", "--db", str(db)])

    assert code == CATALOG_UNUSABLE_EXIT
    assert code != CATALOG_BUSY_EXIT, "'unusable' must not read as 'busy', which means retry"
    assert db.stat().st_size == 0
    captured = capsys.readouterr()
    assert "0 bytes" in captured.err
    assert "0 bytes" not in captured.out, "a refusal belongs on stderr"


def test_the_cli_still_runs_against_an_ordinary_empty_catalog(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The guard against a check that keys on file_count instead of file size."""
    db = tmp_path / "catalog.sqlite"
    with Catalog(db):
        pass

    code = main(["status", "--db", str(db)])

    assert code == 0
    assert "0 bytes" not in capsys.readouterr().err
