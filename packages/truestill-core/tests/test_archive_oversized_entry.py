"""An archive holding a file the destination cannot store is refused before it is unpacked.

**The gap this closes, and why the organize preflight did not already cover it.** Commit 1 made
`organizer.execute` refuse a destination that cannot hold the run. That runs before *organize*
moves any bytes - but an archive ingest extracts to a staging tree on that same destination
**first**, and organize only sees what came out. Point an ingest at a FAT32 card with a 5 GB
video inside the zip and the extraction dies part way with a raw ``[Errno 27]``, having already
written most of the tree. The organize preflight never gets a turn.

So the precheck is the right place, and the cost of asking is zero: `inspect_archive_set`
already reads every entry's declared uncompressed size to total the claim, so the comparison is
free. It is the same claim the space refusal already trusts.

**Belt and braces, deliberately.** A header can under-declare, so the extractor's own write is
also taught to name EFBIG rather than pass the errno through - the identical fix `local.py` got,
in the one write path that does not go through `LocalDestination`.
"""

from __future__ import annotations

import errno
import zipfile
from pathlib import Path

import pytest
from truestill_core.archive_extract import extract_archive_set
from truestill_core.archive_ingest import ArchiveRefusal, precheck_archives
from truestill_core.archive_set import discover_archive_set, inspect_archive_set
from truestill_core.filesystem import FAT32_MAX_FILE_BYTES, FilesystemFacts

_FAT = "truestill_core.archive_ingest.facts_for"


def _zip(path: Path, entries: dict[str, int]) -> Path:
    """A zip whose *declared* sizes are what the test is about, written for real."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, size in entries.items():
            archive.writestr(name, b"\0" * size)
    return path


@pytest.fixture
def fat_destination(monkeypatch: pytest.MonkeyPatch) -> None:
    """Answer as FAT32 with a small stand-in ceiling, patched on the module that asks."""
    monkeypatch.setattr(
        _FAT, lambda _target: FilesystemFacts(filesystem="vfat", max_file_bytes=1_000)
    )


@pytest.mark.usefixtures("fat_destination")
def test_an_entry_too_large_for_the_destination_refuses_the_ingest(tmp_path: Path) -> None:
    """Before extraction, not 40 GB into it."""
    _zip(tmp_path / "src" / "photos.zip", {"a/IMG_1.jpg": 10, "a/VID_4K.mp4": 5_000})

    report = precheck_archives([tmp_path / "src" / "photos.zip"], tmp_path / "dest")

    assert ArchiveRefusal.OVERSIZED_ENTRY in report.refusals
    assert report.may_proceed is False


@pytest.mark.usefixtures("fat_destination")
def test_the_refusal_names_the_entry_and_the_filesystem(tmp_path: Path) -> None:
    """Naming it is the whole point - the user has to know which file to deal with, and that
    the drive is the reason rather than the archive being broken."""
    _zip(tmp_path / "src" / "photos.zip", {"a/VID_4K.mp4": 5_000})

    report = precheck_archives([tmp_path / "src" / "photos.zip"], tmp_path / "dest")

    assert "a/VID_4K.mp4" in report.detail
    assert "FAT32" in report.detail


def test_an_ordinary_destination_does_not_refuse_a_large_entry(tmp_path: Path) -> None:
    """The cry-wolf direction. exFAT and NTFS hold these files perfectly well, and an ingest
    that refused them would be worse than the bug being fixed."""
    _zip(tmp_path / "src" / "photos.zip", {"a/VID_4K.mp4": 5_000})

    report = precheck_archives([tmp_path / "src" / "photos.zip"], tmp_path / "dest")

    assert ArchiveRefusal.OVERSIZED_ENTRY not in report.refusals


def test_no_limit_means_no_oversized_entries_however_large(tmp_path: Path) -> None:
    """Unknown (macOS) and unlimited (ext4) take the same path: report nothing."""
    _zip(tmp_path / "photos.zip", {"a/VID.mp4": 5_000})
    archive_set = discover_archive_set([tmp_path / "photos.zip"])

    assert inspect_archive_set(archive_set, max_file_bytes=None).oversized_entries == ()


def test_the_boundary_is_the_largest_size_that_fits(tmp_path: Path) -> None:
    """A file of exactly the limit fits; one byte more does not. Stated here because the whole
    refusal turns on which way the comparison points."""
    _zip(tmp_path / "photos.zip", {"exact.mp4": 1_000, "over.mp4": 1_001})
    archive_set = discover_archive_set([tmp_path / "photos.zip"])

    oversized = inspect_archive_set(archive_set, max_file_bytes=1_000).oversized_entries

    assert [name for name, _size in oversized] == ["over.mp4"]


def test_the_real_fat32_ceiling_is_what_a_real_drive_would_use() -> None:
    """The stand-in limit above keeps the tests fast; this pins that the constant it stands in
    for is the actual one, so a wrong constant cannot hide behind a convenient fixture."""
    assert FAT32_MAX_FILE_BYTES == 4 * 1024**3 - 1


def test_the_extractors_own_write_names_efbig_rather_than_passing_the_errno_through(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Belt and braces for a header that under-declares.

    The precheck refuses on *declared* sizes, so an archive that lies about them reaches the
    extractor - which writes with a plain ``open()`` and is the one write path in the codebase
    that does not go through `LocalDestination`. Without this it is the original bug again, in
    the neighbouring function: ``[Errno 27] File too large`` against a drive showing 200 GB free.
    """
    _zip(tmp_path / "src" / "photos.zip", {"a/VID.mp4": 40})
    archive_set = discover_archive_set([tmp_path / "src" / "photos.zip"])

    real_open = Path.open

    def refusing_open(self: Path, *args: object, **kwargs: object):  # type: ignore[no-untyped-def]
        if self.name.endswith(".partial"):
            raise OSError(errno.EFBIG, "File too large")
        return real_open(self, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(Path, "open", refusing_open)

    with pytest.raises(OSError, match="too large for this drive") as raised:
        extract_archive_set(archive_set, tmp_path / "dest")

    assert "FAT32" in str(raised.value), f"the errno was passed through bare: {raised.value}"
    assert "VID.mp4" in str(raised.value)
