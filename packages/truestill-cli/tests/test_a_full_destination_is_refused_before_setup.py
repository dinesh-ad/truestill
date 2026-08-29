"""(aek) A destination that cannot hold the run is refused BEFORE it is registered.

**The ordering is the defect.** Truestill already words a full disk correctly - *"Not enough room:
this needs about X and the drive has Y free"* (`filesystem.DestinationPreflight.detail`) - and the
CLI already turns that into `error: <sentence>` and exit 4 rather than a traceback. That sentence
was computed *after* the marker write, so the first run against a new drive on a full disk died at
`write_marker` and never reached the explanation the product already had.

So this file asserts a **sequence**, not a message: when the destination cannot hold the run,
nothing about it is written down. No marker on the drive, no `drives` row, no path hint. The
sentence is asserted too, because a refusal nobody can act on is the failure this replaced.

**The cry-wolf half is not optional here** - a gate that refuses a destination with room would
stop every ordinary run, so `test_a_destination_with_room_is_still_registered` holds the other
direction. Mutating the gate to *always* and to *never* must kill one test each
(ENGINEERING_STANDARD.md §4, thirty-first member).
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import NamedTuple

import pytest
from PIL import Image
from truestill_cli.cli import main
from truestill_core.catalog import Catalog
from truestill_core.drive import MARKER_NAME, create_marker, drive_path_hint, read_marker

_EXIFTOOL = pytest.mark.skipif(shutil.which("exiftool") is None, reason="exiftool not installed")

#: `cli.py`'s "unusable destination", the code a `DestinationError` already exits on.
_UNUSABLE_DESTINATION = 4


class _Usage(NamedTuple):
    total: int
    used: int
    free: int


@pytest.fixture
def full_disk(monkeypatch: pytest.MonkeyPatch) -> None:
    """Report the destination as having no room, without needing a real full filesystem.

    Aimed at `truestill_core.filesystem`, which is the module that performs the call - patching
    `shutil` globally would also reach `safe_copy`'s own copy and change what the copy path does,
    which is the half of this feature that already works and must not move.
    """
    monkeypatch.setattr(
        "truestill_core.filesystem.shutil.disk_usage",
        lambda _path: _Usage(total=1_000_000, used=1_000_000, free=0),
    )


def _source(tmp_path: Path, count: int = 2) -> Path:
    src = tmp_path / "src"
    src.mkdir()
    for i in range(count):
        Image.new("RGB", (64, 64), (i + 1, 2, 3)).save(src / f"photo{i}.jpg", "JPEG")
    return src


def _drive_rows(db: Path) -> list[str]:
    with Catalog(db) as catalog:
        return [str(row["uuid"]) for row in catalog.list_drives()]


@_EXIFTOOL
@pytest.mark.usefixtures("full_disk")
def test_a_full_destination_is_refused_before_the_marker_is_written(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The whole of `(aek)`: a sentence, an exit code, and nothing written down."""
    src = _source(tmp_path)
    dest = tmp_path / "new-drive"
    db = tmp_path / "c.sqlite"

    code = main(["organize", str(src), str(dest), "--apply", "--db", str(db)])

    assert code == _UNUSABLE_DESTINATION
    captured = capsys.readouterr()
    assert "Not enough room" in captured.err + captured.out
    # The traceback this replaced named a pathlib frame; a sentence names the drive.
    assert "Traceback" not in captured.err

    assert read_marker(dest) is None, "the drive was registered on a disk that cannot hold the run"
    assert not (dest / MARKER_NAME).exists()
    assert _drive_rows(db) == [], "a drives row survived a refused registration"


@_EXIFTOOL
@pytest.mark.usefixtures("full_disk")
def test_a_refused_registration_leaves_no_debris_at_the_destination(tmp_path: Path) -> None:
    """A destination Truestill declined to use must look untouched afterwards.

    Separate from the assertions above because it is a different promise: that one is about the
    catalog, this is about the user's disk. `(aek)` left a zero-byte marker there.
    """
    src = _source(tmp_path)
    dest = tmp_path / "new-drive"
    db = tmp_path / "c.sqlite"

    main(["organize", str(src), str(dest), "--apply", "--db", str(db)])

    assert not dest.exists() or list(dest.iterdir()) == []


@_EXIFTOOL
def test_a_destination_with_room_is_still_registered(tmp_path: Path) -> None:
    """The cry-wolf direction. A gate that refuses an ordinary run gets switched off, and takes
    its real coverage with it (ENGINEERING_STANDARD.md §4)."""
    src = _source(tmp_path)
    dest = tmp_path / "roomy"
    db = tmp_path / "c.sqlite"

    assert main(["organize", str(src), str(dest), "--apply", "--db", str(db)]) == 0

    marker = read_marker(dest)
    assert marker is not None
    assert _drive_rows(db) == [marker.uuid]
    with Catalog(db) as catalog:
        assert catalog.get_setting(drive_path_hint(marker.uuid)) == str(dest)


@_EXIFTOOL
@pytest.mark.usefixtures("full_disk")
def test_the_refusal_does_not_depend_on_the_destination_being_new(tmp_path: Path) -> None:
    """An ALREADY-registered destination still refuses, and still keeps its identity.

    The ordering change moves registration; it must not turn the refusal into something only a
    fresh folder gets. The marker here was written before the disk filled, so it must survive -
    a refusal that deleted a drive's identity would be far worse than the crash it replaced.
    """
    src = _source(tmp_path)
    dest = tmp_path / "known"
    db = tmp_path / "c.sqlite"
    dest.mkdir()
    Image.new("RGB", (8, 8)).save(dest / "seed.jpg", "JPEG")
    minted = create_marker(dest, label="Known")

    code = main(["organize", str(src), str(dest), "--apply", "--db", str(db)])

    assert code == _UNUSABLE_DESTINATION
    survivor = read_marker(dest)
    assert survivor is not None
    assert survivor.uuid == minted.uuid, "a refusal re-minted or removed an existing identity"
