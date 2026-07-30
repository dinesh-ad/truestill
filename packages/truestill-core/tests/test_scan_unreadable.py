"""(F2) An unreadable source file must not abort compute_hashes."""

from __future__ import annotations

import errno
from pathlib import Path

import pytest
from truestill_core.hashing import sha256_file
from truestill_core.models import FileHashes
from truestill_core.scan import compute_hashes


def test_compute_hashes_unreadable_file_yields_empty_hashes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One EIO mid-batch must leave neighbours hashed and the bad path as FileHashes(None, None)."""
    good_a = tmp_path / "a.bin"
    good_b = tmp_path / "b.bin"
    locked = tmp_path / "locked.bin"
    payload = b"same-size-bytes!!"  # 17 bytes - all three must collide so SHA-256 is required
    good_a.write_bytes(payload)
    good_b.write_bytes(b"other-same-lengtX")  # 17
    locked.write_bytes(b"locked-same-lengt")  # 17

    real_sha = sha256_file

    def boom(path: Path) -> str:
        if path.name == "locked.bin":
            raise OSError(errno.EIO, "Input/output error", str(path))
        return real_sha(path)

    monkeypatch.setattr("truestill_core.scan.sha256_file", boom)

    results = compute_hashes([good_a, good_b, locked])
    assert results[good_a].sha256 == sha256_file(good_a)
    assert results[good_b].sha256 == sha256_file(good_b)
    assert results[locked] == FileHashes(None, None)
