"""Integrity verification of recorded copies against the catalog.

Given the copies the catalog says live on a drive and that drive's current mount root, re-hash
each file and compare to its recorded hash. Read-only: verification never repairs -- a repair
is an explicit re-copy. Hashing reuses the worker-pool + streaming approach from the scan.

A copy is checked against **its own** ``copy_sha256`` (a baked Takeout copy is not identical to
the source, and copies written at different times need not match each other); where that is NULL
(pre-v6 rows, always byte-identical) it falls back to the source ``sha256``.
"""

from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from vaeon_core.hashing import sha256_file
from vaeon_core.scan import DEFAULT_WORKERS, PoolKind


class CopyStatus(StrEnum):
    VERIFIED = "verified"
    MISSING = "missing"  # the file is gone from the drive
    MISMATCH = "mismatch"  # the file is present but its bytes changed (corruption)


@dataclass(frozen=True, slots=True)
class CopyToVerify:
    """One recorded copy to check: its content id, its path on the drive, its expected hash."""

    sha256: str
    relative: str
    expected_hash: str


@dataclass(frozen=True, slots=True)
class VerifyResult:
    copy: CopyToVerify
    status: CopyStatus
    actual_hash: str | None  # None when the file was missing


def _hash_path(path_str: str) -> str:
    return sha256_file(Path(path_str))


def verify_copies(
    copies: list[CopyToVerify],
    root: Path,
    *,
    pool: PoolKind = "thread",
    workers: int = DEFAULT_WORKERS,
) -> list[VerifyResult]:
    """Verify ``copies`` under ``root``. Missing files short-circuit; present files hash in parallel."""
    results: list[VerifyResult] = []
    present: list[tuple[CopyToVerify, Path]] = []
    for copy in copies:
        path = root / copy.relative
        if path.is_file():
            present.append((copy, path))
        else:
            results.append(VerifyResult(copy, CopyStatus.MISSING, None))

    if present:
        executor_cls = ProcessPoolExecutor if pool == "process" else ThreadPoolExecutor
        with executor_cls(max_workers=max(1, workers)) as executor:
            hashes = list(executor.map(_hash_path, [str(path) for _copy, path in present]))
        for (copy, _path), actual in zip(present, hashes, strict=True):
            status = CopyStatus.VERIFIED if actual == copy.expected_hash else CopyStatus.MISMATCH
            results.append(VerifyResult(copy, status, actual))

    return results
