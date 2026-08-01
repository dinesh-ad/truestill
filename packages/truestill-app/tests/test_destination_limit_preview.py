"""The app preview says the destination cannot hold the run, rather than finding out later.

The refusal itself lives in `organizer.execute`, so the app's *run* is already covered by it.
This is the other half: a preview that reads as clean and then fails on Organize moves the
discovery to after the user has committed - and on the app that is worse than on the CLI,
because the button that follows the preview is the one that starts the work.

The FAT32 answer is injected on `destinations.local`, the module that uses the detection
(guard rule 3). Producing a real FAT32 filesystem in a test needs root and a loopback mount;
what is under test here is the reporting, not the detection, which `test_filesystem_limits`
pins on its own.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from truestill_app.service import organize_preview
from truestill_core.filesystem import FilesystemFacts

_FAT = FilesystemFacts(filesystem="vfat", max_file_bytes=1_000)


@pytest.fixture
def fat_destination(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "truestill_core.destinations.local.facts_for", lambda _target: _FAT, raising=True
    )


def _library(tmp_path: Path) -> Path:
    source = tmp_path / "src"
    source.mkdir()
    (source / "IMG_0001.jpg").write_bytes(b"\xff\xd8" + b"x" * 200)
    (source / "VID_4K.mp4").write_bytes(b"\x00" * 4_000)
    return source


@pytest.mark.usefixtures("fat_destination")
def test_the_preview_carries_the_limit_and_names_the_file(tmp_path: Path) -> None:
    preview = organize_preview(_library(tmp_path), tmp_path / "dest", tmp_path / "c.sqlite")

    limit = preview.get("destination_limit")
    assert limit is not None, "the preview reported a plan the run will refuse"
    assert "VID_4K.mp4" in limit["detail"], "the file that would fail was not named"
    assert limit["oversized"] == 1
    assert limit["filesystem"] == "vfat"


def test_an_ordinary_destination_carries_no_limit(tmp_path: Path) -> None:
    """The cry-wolf direction: ext4, NTFS and exFAT previews must be unchanged."""
    preview = organize_preview(_library(tmp_path), tmp_path / "dest", tmp_path / "c.sqlite")

    assert preview.get("destination_limit") is None
