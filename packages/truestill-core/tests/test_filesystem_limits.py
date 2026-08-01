"""What a destination filesystem can actually hold, and refusing before the work rather than after.

**The failure this closes.** FAT32 cannot store a file of 4 GiB or more, and 4K phone video
crosses that routinely. Today a >4 GB video produces ``[Errno 27] File too large`` against a
drive showing 200 GB free - a message whose only reasonable reading is that Truestill is broken.
And because organize has no preflight at all, a library with a few big videos organizes nine
thousand files and *then* fails N of them, one errno at a time.

**Detection is honest about where it works.** ``/proc/mounts`` on Linux and
``GetVolumeInformationW`` on Windows are cheap, need no subprocess, and name the filesystem
exactly. macOS exposes it only through `statfs`'s ``f_fstypename`` or a subprocess, and neither
is worth a per-run cost - so macOS returns **unknown**, which is a real answer rather than a
guessed one. An unknown limit never refuses anything; the improved error message covers it.

**Oversized files are never silently skipped.** They are named and the run refuses, because the
alternative is a library that is quietly missing exactly the footage the user cared most about.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from truestill_core.filesystem import (
    FAT32_MAX_FILE_BYTES,
    FilesystemFacts,
    fat_family,
    max_file_bytes_for,
    oversized_for,
    parse_proc_mounts,
    sizes_of,
)

_MOUNTS = """\
/dev/sda2 / ext4 rw,relatime 0 0
/dev/sdb1 /media/usb vfat rw,relatime,fmask=0022 0 0
/dev/sdc1 /media/card exfat rw,relatime 0 0
/dev/sdd1 /media/big/deeper ntfs3 rw 0 0
"""


def test_the_longest_matching_mount_point_wins() -> None:
    """A file under /media/big/deeper is on ntfs3, not on the / that also matches."""
    assert parse_proc_mounts(_MOUNTS, Path("/media/big/deeper/photos/a.mp4")) == "ntfs3"
    assert parse_proc_mounts(_MOUNTS, Path("/media/usb/a.mp4")) == "vfat"
    assert parse_proc_mounts(_MOUNTS, Path("/home/dinesh/a.mp4")) == "ext4"


def test_only_the_fat_family_reports_a_limit() -> None:
    """exFAT lifted the cap; ext4 and NTFS never had one at this scale.

    A wrong limit here would refuse work that would have succeeded, which is worse than the bug
    being fixed - so the mapping is deliberately narrow and everything unknown means no limit.
    """
    assert max_file_bytes_for("vfat") == FAT32_MAX_FILE_BYTES
    assert max_file_bytes_for("msdos") == FAT32_MAX_FILE_BYTES
    assert max_file_bytes_for("FAT32") == FAT32_MAX_FILE_BYTES

    for unlimited in ("ext4", "ntfs3", "ntfs", "apfs", "exfat", "btrfs", "xfs"):
        assert max_file_bytes_for(unlimited) is None, unlimited


def test_an_unknown_filesystem_never_refuses_anything() -> None:
    """macOS returns unknown, and unknown must mean "proceed", never "guess"."""
    assert max_file_bytes_for(None) is None
    assert max_file_bytes_for("something-nobody-has-heard-of") is None


def test_the_fat_limit_is_the_real_one() -> None:
    """4 GiB minus one byte. A file of exactly 4 GiB does not fit."""
    assert FAT32_MAX_FILE_BYTES == 4 * 1024**3 - 1


@pytest.mark.parametrize("family", ["vfat", "msdos", "fat", "fat32"])
def test_fat_family_recognises_the_spellings_linux_and_windows_use(family: str) -> None:
    """Linux says vfat/msdos; Windows says FAT32. Both must land on the same answer."""
    assert fat_family(family) is True


# --- the preflight ------------------------------------------------------------------------


def _facts(limit: int | None, name: str | None = "vfat") -> FilesystemFacts:
    return FilesystemFacts(filesystem=name, max_file_bytes=limit)


def test_oversized_files_are_named_not_counted() -> None:
    """Naming them is the whole point - "3 files are too large" is not actionable."""
    offenders = oversized_for(
        [(Path("IMG_1.jpg"), 10), (Path("VID_4K.mp4"), 5000)], _facts(limit=1000)
    )

    assert [path.name for path, _size in offenders] == ["VID_4K.mp4"]
    assert offenders[0][1] == 5000


def test_nothing_is_oversized_when_the_limit_is_unknown() -> None:
    """An unknown filesystem must not refuse a perfectly good 8 GB video."""
    assert oversized_for([(Path("VID_4K.mp4"), 5000)], _facts(limit=None, name=None)) == []


def test_a_file_exactly_at_the_limit_is_allowed() -> None:
    """Boundary stated explicitly: the limit is the largest size that FITS."""
    assert oversized_for([(Path("edge.mp4"), 1000)], _facts(limit=1000)) == []


def test_a_file_one_byte_over_is_refused() -> None:
    assert oversized_for([(Path("edge.mp4"), 1001)], _facts(limit=1000)) != []


def test_an_unreadable_file_is_skipped_rather_than_crashing_the_preflight(tmp_path: Path) -> None:
    """A preflight that raises is worse than one that misses a file: it blocks the whole run
    over something the real copy would have reported per-file anyway.

    Sizing is where that decision lives, now that the comparison itself takes sizes.
    """
    real = tmp_path / "here.jpg"
    real.write_bytes(b"xyz")

    assert sizes_of([tmp_path / "gone.mp4", real]) == [(real, 3)]


def test_sizes_come_from_the_caller_so_backup_can_use_the_same_check() -> None:
    """Backup reads its sizes from catalog rows, never from disk. A path-only signature here
    would have forced a second copy of this logic to serve it - the failure the whole
    "one home per rule" standard exists to prevent."""
    from_catalog = [(Path("Camera/2024/06/VID.mp4"), 5_000_000_000)]

    assert oversized_for(from_catalog, _facts(limit=FAT32_MAX_FILE_BYTES)) == from_catalog
