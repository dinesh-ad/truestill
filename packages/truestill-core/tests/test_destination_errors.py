"""(F3) LocalDestination must raise DestinationError, not raw OSError."""

from __future__ import annotations

import errno
from pathlib import Path

import pytest
from truestill_core.destinations.base import DestinationError
from truestill_core.destinations.local import LocalDestination
from truestill_core.migrate import _matches


def test_local_checksum_translates_oserror_to_destination_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ABC contract: checksum raises DestinationError; a raw OSError is the bug."""
    (tmp_path / "a.bin").write_bytes(b"present")
    dest = LocalDestination(tmp_path)

    def boom(_path: Path) -> str:
        raise OSError(errno.EIO, "Input/output error", "a.bin")

    monkeypatch.setattr("truestill_core.destinations.local.sha256_file", boom)
    with pytest.raises(DestinationError, match="cannot checksum"):
        dest.checksum("a.bin")


def test_migrate_matches_returns_false_when_checksum_is_unreadable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """_matches must not let OSError abort a migration mid-move."""
    (tmp_path / "a.bin").write_bytes(b"present")
    dest = LocalDestination(tmp_path)

    def boom(_path: Path) -> str:
        raise OSError(errno.EIO, "Input/output error", "a.bin")

    monkeypatch.setattr("truestill_core.destinations.local.sha256_file", boom)
    assert _matches(dest, "a.bin", "0" * 64) is False


def _copy_fails_with(monkeypatch: pytest.MonkeyPatch, number: int, text: str) -> None:
    """Make the copy raise a given errno, on the module that performs it (guard rule 3)."""

    def boom(_src: Path, _dst: Path) -> Path:
        raise OSError(number, text)

    monkeypatch.setattr("truestill_core.destinations.local.shutil.copy2", boom)


def test_efbig_is_named_as_the_fat32_limit_rather_than_passed_through(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``[Errno 27] File too large`` against a drive showing 200 GB free reads as truestill
    being broken. The only reading a user can act on is the one that names FAT32.

    The preflight catches this case before the run starts; this covers the copy that still
    fails - a file that grew after the check, or a limit no platform could report.
    """
    (tmp_path / "VID_4K.mp4").write_bytes(b"\x00" * 16)
    _copy_fails_with(monkeypatch, errno.EFBIG, "File too large")

    with pytest.raises(DestinationError) as raised:
        LocalDestination(tmp_path).upload(tmp_path / "VID_4K.mp4", "Camera/2024/VID_4K.mp4")

    message = str(raised.value)
    assert "VID_4K.mp4" in message
    assert "FAT32" in message, f"the reason was not named: {message}"
    assert "4 GB" in message
    assert "27" not in message, "the raw errno leaked into a user-facing sentence"


def test_an_ordinary_copy_failure_is_not_dressed_up_as_a_size_limit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The cry-wolf direction: a full disk (ENOSPC) is a different problem with a different
    fix, and telling that user to reformat their drive as exFAT would be actively wrong."""
    (tmp_path / "a.jpg").write_bytes(b"\xff\xd8")
    _copy_fails_with(monkeypatch, errno.ENOSPC, "No space left on device")

    with pytest.raises(DestinationError) as raised:
        LocalDestination(tmp_path).upload(tmp_path / "a.jpg", "Camera/2024/a.jpg")

    assert "FAT32" not in str(raised.value)
