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
