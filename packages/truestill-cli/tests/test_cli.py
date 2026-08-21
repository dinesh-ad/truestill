"""Smoke tests for the CLI wiring (does not require exiftool)."""

from __future__ import annotations

from pathlib import Path

import pytest
from truestill_cli.cli import main


def test_help_exits_zero() -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0


def test_empty_source_reports_nothing(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    source = tmp_path / "empty"
    source.mkdir()
    code = main(["organize", str(source), str(tmp_path / "out")])
    assert code == 0
    assert "No media files" in capsys.readouterr().out


def test_missing_source_is_an_error(tmp_path: Path) -> None:
    code = main(["organize", str(tmp_path / "does-not-exist"), str(tmp_path / "out")])
    assert code == 2


def test_organize_reports_skipped_files_by_extension(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = tmp_path / "src"
    source.mkdir()
    # No media -- only a document and two unrecognized video formats. Never silently dropped.
    (source / "scheme.pdf").write_bytes(b"x")
    (source / "clip.vob").write_bytes(b"x")
    (source / "movie.ogv").write_bytes(b"x")

    code = main(["organize", str(source), str(tmp_path / "out")])
    assert code == 0
    out = capsys.readouterr().out
    assert "No media files" in out
    assert "documents: 1  (.pdf x1)" in out
    assert "unrecognized: 2" in out
    assert ".vob x1" in out
    assert ".ogv x1" in out


def test_organize_reports_exiftool_backup_plainly_even_with_all_files(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Sidecars are refused at scan; skipped copy says 'exiftool backup', not '.jpg_original'.

    ⚠ **The heading moved from `exiftool backup: 2` to `exiftool backups: 2  (exiftool backup x2)`
    when `(aer)` made this report render the census** - which is the wording `analyze` has shown
    all along, so the two surfaces now agree rather than one being restyled. The assertion below
    pins the PROMISE this test was written for, in the docstring's own words: the plain phrase
    appears and the sidecar's extension never does. Stated that way it cannot be satisfied by the
    defect returning, and it does not break again the next time a heading is pluralised.
    """
    source = tmp_path / "src"
    source.mkdir()
    (source / "holiday.jpg_original").write_bytes(b"backup")
    (source / "clip.mp4_original").write_bytes(b"vbackup")

    code = main(["organize", str(source), str(tmp_path / "out"), "--all-files"])
    assert code == 0
    out = capsys.readouterr().out
    assert "No media files" in out
    assert "exiftool backup" in out, "the plain phrase is what a person can act on"
    assert "2" in out.split("exiftool backups:")[1][:4], "the count of sidecars is not stated"
    assert ".jpg_original" not in out
    assert ".mp4_original" not in out
