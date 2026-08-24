"""(F1) An unreadable copy must be counted as UNREADABLE, never crash verify_copies."""

from __future__ import annotations

import errno
import os
import sys
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


@pytest.mark.skipif(
    sys.platform == "win32" or os.geteuid() == 0,
    reason="a mode-000 parent does not deny the owner on Windows, and root ignores it - the "
    "refusal must be REAL (a mocked stat is the blind spot this test exists to close)",
)
def test_a_stat_refused_copy_is_unreadable_never_missing(tmp_path: Path) -> None:
    """⚠ **(aey)'s sixth site - fails today by answering MISSING.**

    The test above patches `sha256_file`, which runs only AFTER `is_file()` succeeded - so the
    stat-refused class was invisible to this file while being its exact subject. The refusal
    here is the kernel's own: mode 000 on the PARENT removes search permission, and stat of a
    child is then EACCES. (Mode 000 on the FILE itself does not stop stat - `(agk)`'s M9
    lesson - the parent's execute bit is what gates it.)

    MISSING is an actionable loss claim the app records (`mark_copy_missing`); a file the OS
    refused to describe has not been lost, and saying so teaches the user to ignore the one
    report whose value is being believed - `(aba)` symptom 1's exact words.
    """
    root = tmp_path / "drive"
    vault = root / "vault"
    vault.mkdir(parents=True)
    hidden = vault / "hidden.bin"
    hidden.write_bytes(b"present-but-undescribable")
    expected = sha256_file(hidden)
    vault.chmod(0o000)
    try:
        results = {
            r.copy.relative: r
            for r in verify_copies([CopyToVerify("1", "vault/hidden.bin", expected)], root)
        }
    finally:
        vault.chmod(0o755)

    verdict = results["vault/hidden.bin"]
    assert verdict.status is CopyStatus.UNREADABLE, (
        f"a copy the OS refused to stat was classified {verdict.status} - verify recorded a "
        "loss that did not happen"
    )
    assert verdict.actual_hash is None


def test_a_genuinely_absent_copy_still_reads_missing(tmp_path: Path) -> None:
    """⚠ **CRY-WOLF HALF ONE.** Absence outranks unknown, and it must stay that way - a verify
    that answered UNREADABLE for a plainly deleted file would never again say MISSING."""
    root = tmp_path / "drive"
    root.mkdir()

    results = verify_copies([CopyToVerify("1", "gone.bin", "0" * 64)], root)

    assert results[0].status is CopyStatus.MISSING


def test_a_readable_copy_is_unaffected(tmp_path: Path) -> None:
    """⚠ **CRY-WOLF HALF TWO.** The ordinary file, verified exactly as before."""
    root = tmp_path / "drive"
    root.mkdir()
    fine = root / "fine.bin"
    fine.write_bytes(b"intact")

    results = verify_copies([CopyToVerify("1", "fine.bin", sha256_file(fine))], root)

    assert results[0].status is CopyStatus.VERIFIED
