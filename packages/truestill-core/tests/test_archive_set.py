"""What a user must learn BEFORE 200 GB of extraction starts, not during it ((jj)).

Google Takeout does not hand anyone a folder. It hands them
``takeout-20260801T000000Z-001.zip`` through ``-017.zip``, and *"what a refugee actually has is
a pile of archives"*. Two things about that pile can be known by reading headers alone, and both
are catastrophic to discover late:

* **a missing part.** Sidecar matching is per-folder and a ``Photos from 2014`` folder can
  straddle two archives, so a set with ``-009`` absent produces a library with a hole in it -
  silently, because every individual archive extracts perfectly well.
* **not enough disk.** Extracting 200 GB and failing at 190 is not a smaller version of the same
  problem; it is a wasted afternoon and a half-populated staging directory.

Nothing here extracts anything. These functions read central directories and report, so the
answer arrives in seconds and before any commitment.

**The claimed size is the archive's OWN claim and is never an enforcement input.** It comes from
the header, which an attacker writes. It is what the user is *shown*, clearly labelled; the
running byte counter during extraction is what actually stops a zip bomb, and that lives with
the extractor rather than here.
"""

from __future__ import annotations

import shutil
import struct
import zipfile
from pathlib import Path

import pytest
from truestill_core import archive_set
from truestill_core.archive_set import (
    discover_archive_set,
    inspect_archive_set,
    space_for,
)


def _zip(path: Path, entries: dict[str, bytes], *, encrypted: tuple[str, ...] = ()) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as archive:
        for name, data in entries.items():
            archive.writestr(name, data)
    for name in encrypted:
        _mark_encrypted(path, name)
    return path


def _mark_encrypted(path: Path, target: str) -> None:
    """Set the "needs a password" bit on one entry, at the byte level.

    `zipfile` cannot write encrypted archives, and setting ``flag_bits`` on a `ZipInfo` does not
    work either - ``writestr`` resets the field to zero, which was verified rather than assumed
    after the first version of this fixture silently produced an unflagged entry and the test
    failed for a reason that looked like a detection bug.

    So the bit is set in the **central directory**, which is what `infolist()` reads and
    therefore what the detection under test actually consults.
    """
    data = bytearray(path.read_bytes())
    position = 0
    while (position := data.find(b"PK\x01\x02", position)) >= 0:
        name_length = struct.unpack_from("<H", data, position + 28)[0]
        name = data[position + 46 : position + 46 + name_length].decode()
        if name == target:
            flags = struct.unpack_from("<H", data, position + 8)[0]
            struct.pack_into("<H", data, position + 8, flags | 0x1)
        position += 4
    path.write_bytes(bytes(data))


def _part_path(directory: Path, number: int) -> Path:
    return directory / f"takeout-20260801T000000Z-{number:03d}.zip"


def test_numbered_parts_are_one_logical_source(tmp_path: Path) -> None:
    """The unit of ingestion is the SET, not the archive - a folder can straddle two of them."""
    for number in (1, 2, 3):
        _zip(_part_path(tmp_path, number), {f"Takeout/a/IMG_{number}.jpg": b"x"})

    found = discover_archive_set(sorted(tmp_path.glob("*.zip")))

    assert [part.number for part in found.parts] == [1, 2, 3]
    assert found.missing_numbers == ()


def test_a_missing_part_is_named_before_anything_is_extracted(tmp_path: Path) -> None:
    """The failure this exists to prevent: every archive extracts fine and the library has a hole.

    Silent because per-folder sidecar matching cannot know that the rest of the folder was in a
    file the user never downloaded.
    """
    for number in (1, 2, 4, 5):
        _zip(_part_path(tmp_path, number), {f"Takeout/a/IMG_{number}.jpg": b"x"})

    found = discover_archive_set(sorted(tmp_path.glob("*.zip")))

    assert found.missing_numbers == (3,)
    assert found.is_complete is False


def test_a_single_unnumbered_archive_is_a_valid_set(tmp_path: Path) -> None:
    """Cry-wolf half: a lone `photos.zip` must not be reported as a set missing its siblings."""
    _zip(tmp_path / "photos.zip", {"a/IMG_1.jpg": b"x"})

    found = discover_archive_set([tmp_path / "photos.zip"])

    assert len(found.parts) == 1
    assert found.missing_numbers == ()
    assert found.is_complete is True


def test_unrelated_archives_are_not_grouped_into_one_set(tmp_path: Path) -> None:
    """Two different downloads in one folder are two sources, and numbering must not merge them."""
    _zip(tmp_path / "takeout-A-001.zip", {"a/IMG_1.jpg": b"x"})
    _zip(tmp_path / "holiday-002.zip", {"b/IMG_2.jpg": b"x"})

    found = discover_archive_set(sorted(tmp_path.glob("*.zip")))

    assert len(found.sets) == 2, "archives with different stems were merged"


def test_the_claimed_size_is_reported_as_the_archives_own_claim(tmp_path: Path) -> None:
    """Shown to the user, never trusted as a limit - the header is attacker-controlled."""
    _zip(tmp_path / "photos.zip", {"a/IMG_1.jpg": b"x" * 500, "a/IMG_2.jpg": b"y" * 700})

    inspection = inspect_archive_set(discover_archive_set([tmp_path / "photos.zip"]))

    assert inspection.claimed_bytes == 1200
    assert inspection.entries == 2


def test_an_encrypted_entry_is_detected_and_named(tmp_path: Path) -> None:
    """ "This needs a password" beats a confusing exception 190 GB in.

    Detected from the header flag, so it costs nothing and happens before extraction.
    """
    _zip(
        tmp_path / "photos.zip",
        {"open.jpg": b"x", "locked.jpg": b"y"},
        encrypted=("locked.jpg",),
    )

    inspection = inspect_archive_set(discover_archive_set([tmp_path / "photos.zip"]))

    assert inspection.encrypted == ("locked.jpg",)


def test_a_nested_archive_is_detected_and_named(tmp_path: Path) -> None:
    """Refused outright: recursive extraction is unbounded depth on untrusted input.

    Naming the entry is the whole of the report - "this archive contains another archive, which
    truestill does not open" is useless without saying which one.
    """
    _zip(tmp_path / "photos.zip", {"a/IMG_1.jpg": b"x", "a/more-photos.zip": b"PK"})

    inspection = inspect_archive_set(discover_archive_set([tmp_path / "photos.zip"]))

    assert inspection.nested_archives == ("a/more-photos.zip",)


def test_media_entries_are_counted_separately_from_everything_else(tmp_path: Path) -> None:
    """A Takeout is mostly JSON sidecars, so "12,000 entries" tells a user nothing useful."""
    _zip(
        tmp_path / "photos.zip",
        {"a/IMG_1.jpg": b"x", "a/IMG_1.jpg.json": b"{}", "a/IMG_2.mp4": b"y"},
    )

    inspection = inspect_archive_set(discover_archive_set([tmp_path / "photos.zip"]))

    assert inspection.entries == 3
    assert inspection.media_entries == 2


def test_space_is_checked_against_the_destination_drive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The check is about the drive the user chose, which is why staging goes there too.

    **Asserts WHICH path was measured, not what the number came back as.** This used to compare
    `check.free_bytes` against a second `shutil.disk_usage` reading, which is two samples of a
    live metric taken at different moments: anything writing to the disk in between - another
    test worker, a browser, the OS - moves the second one. Serial runs hid it because nothing
    else was writing; it failed on the first parallel run. The recorded path is the claim this
    test's name makes, and it cannot race.
    """
    _zip(tmp_path / "photos.zip", {"a/IMG_1.jpg": b"x" * 100})
    inspection = inspect_archive_set(discover_archive_set([tmp_path / "photos.zip"]))

    measured: list[Path] = []
    real = shutil.disk_usage

    def record(path: Path) -> object:
        measured.append(Path(path))
        return real(path)

    # Aimed at the module under test's own reference, which is what it resolves at call time.
    monkeypatch.setattr(archive_set.shutil, "disk_usage", record)
    check = space_for(inspection, tmp_path)

    assert measured == [tmp_path], f"the space check measured {measured}, not the destination"
    assert check.claimed_bytes == 100
    assert check.enough is True


def test_not_enough_space_is_a_refusal_not_a_warning(tmp_path: Path) -> None:
    """Discovered at 190 of 200 GB this is a wasted afternoon; discovered here it is a sentence."""
    _zip(tmp_path / "photos.zip", {"a/IMG_1.jpg": b"x" * 100})
    inspection = inspect_archive_set(discover_archive_set([tmp_path / "photos.zip"]))

    check = space_for(inspection, tmp_path, free_bytes=50)

    assert check.enough is False
