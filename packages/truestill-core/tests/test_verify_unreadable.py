"""(F1) An unreadable copy must be counted as UNREADABLE, never crash verify_copies."""

from __future__ import annotations

import errno
from pathlib import Path

import pytest
from truestill_core.hashing import sha256_file
from truestill_core.verify import CopyStatus, CopyToVerify, verify_copies


def test_verify_unreadable_copy_is_counted_not_raised(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A present file that raises OSError on read is the failure verify exists to detect.

    Before the fix, future.result() re-raised and verify_copies never returned.
    """
    root = tmp_path / "drive"
    root.mkdir()
    good = root / "good.bin"
    good.write_bytes(b"intact")
    locked = root / "locked.bin"
    locked.write_bytes(b"present-but-unreadable")

    real_sha = sha256_file

    def boom(path: Path) -> str:
        if path.name == "locked.bin":
            raise OSError(errno.EIO, "Input/output error", str(path))
        return real_sha(path)

    monkeypatch.setattr("truestill_core.verify.sha256_file", boom)

    copies = [
        CopyToVerify("1", "good.bin", sha256_file(good)),
        CopyToVerify("2", "locked.bin", "0" * 64),
    ]
    results = {r.copy.relative: r for r in verify_copies(copies, root)}
    assert results["good.bin"].status is CopyStatus.VERIFIED
    assert results["locked.bin"].status is CopyStatus.UNREADABLE
    assert results["locked.bin"].actual_hash is None
    assert results["locked.bin"].detail
    assert "Input/output error" in results["locked.bin"].detail
