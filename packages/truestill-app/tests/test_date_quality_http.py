"""The two date-quality signals must reach the app's organize summary, not just the CLI.

Both front-ends read the same ``models.date_quality`` helper, so this also guards against
them drifting into reporting different numbers for the same run.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
from PIL import Image
from truestill_app.service import organize_preview

pytestmark = pytest.mark.skipif(shutil.which("exiftool") is None, reason="exiftool not installed")


def _dated_image(path: Path, stamp: str, colour: int) -> None:
    """A photo carrying exactly one embedded date, written verbatim by exiftool."""
    Image.new("RGB", (32, 32), (colour % 256, 40, 60)).save(path, "JPEG")
    subprocess.run(
        ["exiftool", "-overwrite_original", "-q", "-m", f"-DateTimeOriginal={stamp}", str(path)],
        check=True,
    )


def test_organize_summary_reports_both_date_quality_signals(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    _dated_image(src / "sentinel.jpg", "1904:01:01 00:00:00", 10)  # Tier A -> refused
    _dated_image(src / "reset.jpg", "2000:01:01 00:00:00", 20)  # Tier B -> filed + flagged
    _dated_image(src / "normal.jpg", "2019:05:02 14:10:00", 30)  # neither

    summary = organize_preview(src, tmp_path / "dest", tmp_path / "c.sqlite")

    assert summary["sentinel_rejected"] == 1
    assert summary["suspect_default"] == 1
    # The refused date lands in Undated/ -- but is never *only* reported as "undated".
    assert summary["undated"] == 1


def test_a_clean_library_reports_zero_for_both(tmp_path: Path) -> None:
    """No signal is a real answer: the UI hides these lines rather than showing '0'."""
    src = tmp_path / "src"
    src.mkdir()
    _dated_image(src / "a.jpg", "2019:05:02 14:10:00", 40)

    summary = organize_preview(src, tmp_path / "dest", tmp_path / "c.sqlite")

    assert summary["sentinel_rejected"] == 0
    assert summary["suspect_default"] == 0


def test_a_pre_1990_scan_is_dated_not_undated(tmp_path: Path) -> None:
    """The lowered floor, end to end: a 1985 negative scan keeps its year."""
    src = tmp_path / "src"
    src.mkdir()
    _dated_image(src / "negative.jpg", "1985:07:04 18:22:10", 50)

    summary = organize_preview(src, tmp_path / "dest", tmp_path / "c.sqlite")

    assert summary["undated"] == 0  # before the floor moved to 1900, this was 1
    assert summary["sentinel_rejected"] == 0  # a real early date is not a sentinel
