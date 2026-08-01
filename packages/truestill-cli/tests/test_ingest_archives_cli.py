"""Pointing `ingest` at one archive part ingests the whole download ((jj)).

**Why one part is enough, and why requiring all of them would be worse.** Google splits an
export across numbered files *by size, not by folder*, so a ``Photos from 2014`` folder can
straddle two of them. If the command line required every part, forgetting one would not fail -
it would **succeed** and quietly leave the photos in the missing part without their real dates.
An easy mistake with a silent, permanent cost is the worst shape a CLI can have, so the siblings
are gathered from the directory instead.

The archive route refuses on its preconditions **before writing anything**, which is the same
preview-then-confirm discipline every other path that touches a user's disk follows.
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest
from truestill_cli.cli import _source_root_or_none

_SIDECAR = json.dumps({"photoTakenTime": {"timestamp": "1403000000"}}).encode()


def _part(directory: Path, number: int, entries: dict[str, bytes]) -> Path:
    path = directory / f"takeout-20260801T000000Z-{number:03d}.zip"
    with zipfile.ZipFile(path, "w") as archive:
        for name, data in entries.items():
            archive.writestr(name, data)
    return path


def test_a_directory_is_passed_straight_through(tmp_path: Path) -> None:
    """The pre-existing route must keep working exactly as it did."""
    extracted = tmp_path / "Takeout"
    extracted.mkdir()

    assert _source_root_or_none(extracted, tmp_path / "dest") == extracted


def test_pointing_at_one_part_gathers_its_siblings(tmp_path: Path) -> None:
    """The photo is in part 1 and its sidecar in part 2; naming only part 1 must still find both."""
    folder = "Takeout/Google Photos/Photos from 2014"
    first = _part(tmp_path, 1, {f"{folder}/IMG_0001.jpg": b"\xff\xd8jpeg"})
    _part(tmp_path, 2, {f"{folder}/IMG_0001.jpg.json": _SIDECAR})

    root = _source_root_or_none(first, tmp_path / "dest")

    assert root is not None
    assert (root / folder / "IMG_0001.jpg").exists()
    assert (root / folder / "IMG_0001.jpg.json").exists(), "the sibling part was not unpacked"


def test_a_refusal_writes_nothing_and_reports_why(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A missing part must stop the run rather than produce a library with a hole in it."""
    for number in (1, 3):
        _part(tmp_path, number, {f"Takeout/a/IMG_{number}.jpg": b"\xff\xd8x"})
    destination = tmp_path / "dest"

    result = _source_root_or_none(tmp_path / "takeout-20260801T000000Z-001.zip", destination)

    assert result is None
    assert not destination.exists(), "a refused ingest still touched the destination"
    printed = capsys.readouterr().out
    assert "missing part 2" in printed, f"the refusal did not say what was wrong: {printed}"


def test_a_path_that_is_neither_file_nor_directory_is_named(tmp_path: Path) -> None:
    assert _source_root_or_none(tmp_path / "nope.zip", tmp_path / "dest") is None
