"""(aek) on the app surface: refuse before registering, without restoring `(aei)`.

`ENGINEERING_STANDARD.md` §4's fifty-sixth member is the class `(aek)` belongs to - a rule carried
to some surfaces and silently not to another - so shipping the CLI's ordering fix alone would have
repeated the defect being fixed. The app registers its destination too
(`service/organize._register_destination`), and its marker write is the same two lines.

Two properties, and they pull in opposite directions, which is why both are pinned here:

* the destination is **not** registered when it cannot hold the run (`(aek)`);
* a **second, fresh** destination still receives every file (`(aei)`).

The second is what makes the first safe to do: registration moved behind the space check, so the
dedup scope now comes from the marker rather than from the act of registering.
"""

from __future__ import annotations

import shutil
import threading
from pathlib import Path
from typing import NamedTuple

import pytest
from PIL import Image
from truestill_app.service import organize_run
from truestill_core.catalog import Catalog
from truestill_core.destinations.base import DestinationError
from truestill_core.drive import MARKER_NAME, read_marker

_EXIFTOOL = pytest.mark.skipif(shutil.which("exiftool") is None, reason="exiftool not installed")


class _Usage(NamedTuple):
    total: int
    used: int
    free: int


def _run(source: Path, destination: Path, db: Path) -> object:
    return organize_run(source, destination, db)(lambda _p: None, threading.Event())


def _source(tmp_path: Path, name: str = "src", count: int = 3) -> Path:
    """Photos a perceptual hash can tell apart - see the CLI twin of this file for why."""
    src = tmp_path / name
    src.mkdir()
    for i in range(count):
        image = Image.new("RGB", (64, 64), (0, 0, 0))
        for x in range(64):
            for y in range(64):
                image.putpixel((x, y), ((x * (i + 1)) % 256, (y * (i + 3)) % 256, (x ^ y) % 256))
        image.save(src / f"photo{i}.jpg", "JPEG", quality=95)
    return src


@_EXIFTOOL
def test_a_full_destination_is_refused_before_the_marker_is_written(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The app's half of `(aek)`. A raw `OSError` out of a job renders as an errno with no next
    step; a `DestinationError` carries the sentence the preview already shows."""
    monkeypatch.setattr(
        "truestill_core.filesystem.shutil.disk_usage",
        lambda _path: _Usage(total=1_000_000, used=1_000_000, free=0),
    )
    src = _source(tmp_path)
    dest = tmp_path / "new-drive"
    db = tmp_path / "c.sqlite"

    with pytest.raises(DestinationError, match="Not enough room"):
        _run(src, dest, db)

    assert read_marker(dest) is None, "the drive was registered on a disk that cannot hold the run"
    assert not (dest / MARKER_NAME).exists()
    with Catalog(db) as catalog:
        assert list(catalog.list_drives()) == []


@_EXIFTOOL
def test_a_destination_with_room_is_still_registered(tmp_path: Path) -> None:
    """The cry-wolf direction: an ordinary run must still register its destination."""
    src = _source(tmp_path)
    dest = tmp_path / "roomy"
    db = tmp_path / "c.sqlite"

    _run(src, dest, db)

    marker = read_marker(dest)
    assert marker is not None
    with Catalog(db) as catalog:
        assert [str(d["uuid"]) for d in catalog.list_drives()] == [marker.uuid]


@_EXIFTOOL
def test_a_second_drive_still_receives_every_file(tmp_path: Path) -> None:
    """`(aei)` after the move - the regression the reorder must not reintroduce.

    Before `(aei)`, organizing into a fresh second destination copied **nothing**, registered a
    0-file drive and reported success. The move puts registration after the space check, so this
    asserts the scope still comes from the marker rather than from having just registered.
    """
    src = _source(tmp_path)
    one = tmp_path / "drive-one"
    two = tmp_path / "drive-two"
    db = tmp_path / "c.sqlite"

    _run(src, one, db)
    _run(src, two, db)

    second = read_marker(two)
    assert second is not None
    with Catalog(db) as catalog:
        on_two = {str(r["sha256"]) for r in catalog.copies_on_drive(second.uuid)}
    assert len(on_two) == 3, f"the second drive received {len(on_two)} of 3 files"
    assert sum(1 for _ in two.rglob("*.jpg")) == 3


@_EXIFTOOL
def test_a_re_run_into_the_same_drive_still_skips_what_is_there(tmp_path: Path) -> None:
    """The other direction of the scope: an unmarked folder reading `{}` must not become a
    catalog-global answer, and a marked one must still see its own contents."""
    src = _source(tmp_path)
    dest = tmp_path / "drive"
    db = tmp_path / "c.sqlite"

    _run(src, dest, db)
    marker = read_marker(dest)
    assert marker is not None
    _run(src, dest, db)

    with Catalog(db) as catalog:
        assert len({str(r["sha256"]) for r in catalog.copies_on_drive(marker.uuid)}) == 3
    assert sum(1 for _ in dest.rglob("*.jpg")) == 3, "a re-run copied the files a second time"
