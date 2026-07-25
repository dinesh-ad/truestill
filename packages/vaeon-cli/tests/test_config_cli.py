"""`vaeon config`: show / set-template / preset / preview, and organize honoring the result."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from PIL import Image
from vaeon_cli.cli import main
from vaeon_core.catalog import Catalog
from vaeon_core.layout import LAYOUT_TEMPLATE_KEY


def test_config_show_lists_default_and_presets(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["config", "--db", str(tmp_path / "c.sqlite")]) == 0
    out = capsys.readouterr().out
    assert "{category}/{yyyy}/{mm}" in out  # the default template
    assert "category-year-month-day" in out  # presets are listed


def test_set_template_persists_and_previews(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    db = tmp_path / "c.sqlite"
    assert main(["config", "--db", str(db), "--set-template", "{category}/{yyyy}"]) == 0
    assert "Preview:" in capsys.readouterr().out
    with Catalog(db) as catalog:
        assert catalog.get_setting(LAYOUT_TEMPLATE_KEY) == "{category}/{yyyy}"


def test_preset_persists_its_template(tmp_path: Path) -> None:
    db = tmp_path / "c.sqlite"
    assert main(["config", "--db", str(db), "--preset", "flat-date"]) == 0
    with Catalog(db) as catalog:
        assert catalog.get_setting(LAYOUT_TEMPLATE_KEY) == "{yyyy}-{mm}-{dd}"


def test_invalid_template_is_rejected_and_not_saved(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    db = tmp_path / "c.sqlite"
    assert main(["config", "--db", str(db), "--set-template", "{nope}"]) == 2
    assert "invalid template" in capsys.readouterr().err
    with Catalog(db) as catalog:
        assert catalog.get_setting(LAYOUT_TEMPLATE_KEY) is None


def test_preview_flag_does_not_persist(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = tmp_path / "c.sqlite"
    code = main(["config", "--db", str(db), "--set-template", "{category}/{yyyy}", "--preview"])
    assert code == 0
    out = capsys.readouterr().out
    assert "Preview:" in out
    assert "not saved" in out
    with Catalog(db) as catalog:
        assert catalog.get_setting(LAYOUT_TEMPLATE_KEY) is None


@pytest.mark.skipif(shutil.which("exiftool") is None, reason="exiftool not installed")
def test_skip_undated_names_skipped_files(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    src = tmp_path / "src"
    src.mkdir()
    # A filename-dated file (kept) and an undateable one (no EXIF, no date in name).
    Image.new("RGB", (16, 16), (1, 2, 3)).save(src / "IMG-20250804-WA0007.jpg", "JPEG")
    Image.new("RGB", (16, 16), (9, 8, 7)).save(src / "mystery-scan.jpg", "JPEG")
    out = tmp_path / "out"
    db = tmp_path / "c.sqlite"

    assert main(["organize", str(src), str(out), "--db", str(db), "--apply", "--skip-undated"]) == 0
    report = capsys.readouterr().out
    assert "SKIPPED (undated" in report
    assert "mystery-scan.jpg" in report  # named, never silent
    # The undated file was not written; the dated one was.
    written = [p.name for p in out.rglob("*.jpg")]
    assert "mystery-scan.jpg" not in written
    assert any("20250804" in n or "WA0007" in n for n in written)


@pytest.mark.skipif(shutil.which("exiftool") is None, reason="exiftool not installed")
def test_organize_honors_stored_template(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    # Filename convention dates + categorizes this without needing embedded EXIF.
    Image.new("RGB", (16, 16), (1, 2, 3)).save(src / "IMG-20250804-WA0007.jpg", "JPEG")
    dest = tmp_path / "out"
    db = tmp_path / "c.sqlite"

    assert main(["config", "--db", str(db), "--set-template", "{category}/{yyyy}"]) == 0
    assert main(["organize", str(src), str(dest), "--db", str(db), "--apply"]) == 0

    placed = list(dest.rglob("*.jpg"))
    assert placed, "a file should have been organized"
    rel = placed[0].relative_to(dest).as_posix()
    assert "/2025/" in rel  # honored the stored template...
    assert "/2025/08/" not in rel  # ...which dropped the month the default would have added
