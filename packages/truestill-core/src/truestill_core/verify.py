"""Integrity verification of recorded copies against the catalog.

Given the copies the catalog says live on a drive and that drive's current mount root, re-hash
each file and compare to its recorded hash. Read-only: verification never repairs -- a repair
is an explicit re-copy. Hashing reuses the worker-pool + streaming approach from the scan.

A copy is checked against **its own** ``copy_sha256`` - a baked Takeout copy is not identical to
the source, and copies written at different times need not match each other. Where that is NULL
the copy is reported :attr:`CopyStatus.UNVERIFIABLE` rather than compared to the source
``sha256``: that fallback asserted byte-identity, which is precisely what a bake breaks, so it
made a missing per-drive update indistinguishable from a legacy row and would have surfaced as
corruption on a file truestill had just rewritten.
"""

from __future__ import annotations

import sqlite3
import threading
from concurrent.futures import BrokenExecutor, ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from truestill_core.hashing import sha256_file
from truestill_core.path_reach import Reach, reach
from truestill_core.progress import Phase, Progress, ProgressCallback
from truestill_core.scan import DEFAULT_WORKERS, PoolKind


class CopyStatus(StrEnum):
    VERIFIED = "verified"
    MISSING = "missing"  # the file is gone from the drive
    MISMATCH = "mismatch"  # the file is present but its bytes changed (corruption)
    UNREADABLE = "unreadable"  # present, but the read failed (EIO, permission, broken pool)
    #: Present and readable, but no recorded hash to check it against. Distinct from VERIFIED
    #: (we did not check) and from MISMATCH (we found no damage) - see the module docstring.
    UNVERIFIABLE = "unverifiable"


@dataclass(frozen=True, slots=True)
class CopyToVerify:
    """One recorded copy to check: its content id, its path on the drive, its expected hash."""

    sha256: str
    relative: str
    #: ``None`` when no hash was ever recorded for this copy: unknown, never assumed.
    expected_hash: str | None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> CopyToVerify:
        """Build one from a ``Catalog.copies_on_drive`` row - the only place that mapping lives.

        Every surface that verifies a drive reads the same three columns, and writing that out
        per surface is how ``copy_sha256 or sha256`` survived on the CLI after being removed from
        the app. One home means the next correction cannot land on half of them.
        """
        return cls(
            sha256=row["sha256"],
            relative=row["relative"],
            expected_hash=row["copy_sha256"],
        )


@dataclass(frozen=True, slots=True)
class VerifyResult:
    copy: CopyToVerify
    status: CopyStatus
    actual_hash: str | None  # None when missing or unreadable
    detail: str | None = None  # OSError / pool text for UNREADABLE


def _hash_path(path_str: str) -> str:
    return sha256_file(Path(path_str))


def _partition(
    copies: list[CopyToVerify], root: Path
) -> tuple[list[VerifyResult], list[tuple[CopyToVerify, Path]]]:
    """Split into copies already answered without hashing, and copies that need a read.

    Two are answerable up front. **Absence outranks unknown** - not being there is the more
    specific answer. And a copy with no recorded hash is reported
    :attr:`CopyStatus.UNVERIFIABLE` rather than hashed: the read would produce a value with
    nothing to compare it to, and comparing it to ``sha256`` would assert a byte-identity the
    bake paths deliberately break.
    """
    answered: list[VerifyResult] = []
    to_hash: list[tuple[CopyToVerify, Path]] = []
    for copy in copies:
        path = root / copy.relative
        # `reach`, never a bare `is_file()` - `(aey)`'s sixth site, found 2026-08-24 by an
        # outside audit three days after the class was closed at five. On 3.14 `is_file()`
        # answers False for a path the OS REFUSED to describe (cpython#144525), which read
        # here as MISSING: verify recorded "the drive lost your file" about a file it was
        # never allowed to look at, and the app wrote `mark_copy_missing` on the strength of
        # it. Verify is the OPPOSITE rule from reclaim's deliberate non-use of this primitive:
        # reclaim conflates absent/refused because both mean "never delete", while verify's
        # whole product is the distinction - MISSING is an actionable loss claim, UNREADABLE
        # is "check permissions and look again".
        verdict = reach(path)
        if verdict is Reach.REFUSED:
            answered.append(VerifyResult(copy, CopyStatus.UNREADABLE, None, detail="stat refused"))
        elif verdict is not Reach.FILE:
            answered.append(VerifyResult(copy, CopyStatus.MISSING, None))
        elif copy.expected_hash is None:
            answered.append(VerifyResult(copy, CopyStatus.UNVERIFIABLE, None))
        else:
            to_hash.append((copy, path))
    return answered, to_hash


def verify_copies(
    copies: list[CopyToVerify],
    root: Path,
    *,
    pool: PoolKind = "thread",
    workers: int = DEFAULT_WORKERS,
    progress: ProgressCallback | None = None,
    cancel: threading.Event | None = None,
) -> list[VerifyResult]:
    """Verify ``copies`` under ``root``. Missing files short-circuit; present files hash in parallel.

    ``progress`` is called ``(done, total)`` across all copies; ``cancel`` stops hashing early
    (results are then partial). Read-only: nothing is ever repaired. A present file that cannot
    be read is recorded as :attr:`CopyStatus.UNREADABLE` rather than aborting the batch.
    """
    results, present = _partition(copies, root)

    total, done = len(copies), len(results)  # missing files are already counted
    if progress is not None and done:
        progress(Progress(done, total, Phase.VERIFYING))

    if present:
        executor_cls = ProcessPoolExecutor if pool == "process" else ThreadPoolExecutor
        with executor_cls(max_workers=max(1, workers)) as executor:
            futures = {executor.submit(_hash_path, str(path)): copy for copy, path in present}
            for future in as_completed(futures):
                if cancel is not None and cancel.is_set():
                    for pending in futures:
                        pending.cancel()
                    break
                copy = futures[future]
                try:
                    actual = future.result()
                except OSError as exc:
                    results.append(VerifyResult(copy, CopyStatus.UNREADABLE, None, detail=str(exc)))
                except BrokenExecutor as exc:
                    # ProcessPool death is not an OSError; still one bad file must not abort.
                    results.append(VerifyResult(copy, CopyStatus.UNREADABLE, None, detail=str(exc)))
                else:
                    status = (
                        CopyStatus.VERIFIED if actual == copy.expected_hash else CopyStatus.MISMATCH
                    )
                    results.append(VerifyResult(copy, status, actual))
                done += 1
                if progress is not None:
                    progress(Progress(done, total, Phase.VERIFYING, Path(copy.relative).name))

    return results
