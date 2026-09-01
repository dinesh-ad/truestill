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

import os
import sqlite3
import threading
from concurrent.futures import BrokenExecutor, ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Final

from truestill_core.hashing import sha256_file
from truestill_core.path_reach import Reach, reach
from truestill_core.progress import Phase, Progress, ProgressCallback
from truestill_core.scan import DEFAULT_WORKERS, PoolKind


class CopyStatus(StrEnum):
    VERIFIED = "verified"
    MISSING = "missing"  # the file is gone from the drive
    #: Not at the recorded path, but the same bytes are on this drive somewhere else. `(aba)`
    #: **A different fact from MISSING with a different remedy**, which is why it is a status and
    #: not a softer wording: MISSING says content is gone and you should restore it, MOVED says
    #: the catalog's path is stale and nothing was lost. Folding the two would make the loud one
    #: quieter, and a file that really vanished must stay loud.
    MOVED = "moved"
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
    #: Recorded byte size, used ONLY to narrow the `(aba)` search - never to prove identity.
    #: ``None`` for a row written before the column existed.
    size: int | None = None
    #: ⚠ **A date write was interrupted, so ``expected_hash`` describes bytes that are no longer
    #: there.** `(agv)`: a bake rewrites a copy and records the new hash in a second step, and a
    #: crash between them leaves the catalog holding the value from BEFORE the write. Comparing
    #: against it reports MISMATCH - *corruption*, by this module's own definition - on a
    #: photograph truestill rewrote correctly. The honest answer is that we cannot check this
    #: copy, which is what :attr:`CopyStatus.UNVERIFIABLE` already means.
    bake_in_flight: bool = False

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
            size=row["size"],
            bake_in_flight=row["bake_started_at"] is not None,
        )


@dataclass(frozen=True, slots=True)
class VerifyResult:
    copy: CopyToVerify
    status: CopyStatus
    actual_hash: str | None  # None when missing or unreadable
    detail: str | None = None  # OSError / pool text for UNREADABLE


#: 🔑 **ONE WORDING HOME**, the `migrate.STOP_WORDING` pattern. The two claims `(aba)` is about
#: are different facts with different remedies, and a surface that composed its own sentence for
#: either would be free to blur them. Surfaces render these; they never write their own.
VERIFY_WORDING: Final[dict[CopyStatus, str]] = {
    CopyStatus.MISSING: "not on this drive - the content is gone and needs restoring from another copy",
    CopyStatus.MOVED: "not at the recorded path, but the same bytes are on this drive - nothing was lost",
    CopyStatus.MISMATCH: "present, but its bytes changed since they were recorded",
    CopyStatus.UNREADABLE: "present, but it could not be read - check permissions and look again",
    CopyStatus.UNVERIFIABLE: "present, with no recorded hash to check it against",
    CopyStatus.VERIFIED: "present, and its bytes are exactly what was recorded",
}


def _locate_moved(
    misses: list[VerifyResult], root: Path, *, cancel: threading.Event | None = None
) -> list[VerifyResult]:
    """Re-answer each MISSING by looking for its bytes elsewhere on the drive. `(aba)`

    ⚠ **THE COST IS PAID ONLY WHEN A LOSS IS ABOUT TO BE CLAIMED.** `verify` otherwise never
    walks - it stats recorded paths and nothing else (checked: no ``rglob``, ``os.walk``,
    ``scandir`` or ``iterdir`` in this module before `(aba)`) - so a clean run costs exactly what
    it did. Measured on a real 109,431-file library: the walk is **1.73 s at 63,000 files/s**, and
    the size index it builds bounds the hashing - **median 10 candidates** for a given file, 90th
    percentile 21.

    🔑 **SIZE NARROWS, SHA-256 DECIDES.** A same-named or same-sized file elsewhere is not proof
    of anything; only the recorded hash is identity. So a copy whose ``expected_hash`` is ``None``
    can never be relocated by this and stays MISSING - unknown is not a match.
    """
    # 🔑 **THE COST GATE, and the only one.** `verify` never walked before `(aba)` - it stats
    # recorded paths and nothing else - so a run with nothing to find must still not walk. This
    # returns before `os.walk` for a clean drive AND for a drive whose misses carry no recorded
    # hash, because neither can produce a match.
    wanted = [m for m in misses if m.copy.expected_hash is not None and m.copy.size is not None]
    if not wanted:
        return misses

    by_size = _files_by_size(root, {m.copy.size for m in wanted if m.copy.size is not None})
    hashed: dict[Path, str | None] = {}
    return [_relocate(r, root, by_size, hashed, cancel) for r in misses]


def _files_by_size(root: Path, sizes: set[int]) -> dict[int, list[Path]]:
    """Every file under ``root`` whose size is one we are looking for. One walk, stat only."""
    found: dict[int, list[Path]] = {}
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            path = Path(dirpath) / name
            try:
                size = path.stat().st_size
            except OSError:
                continue  # a file we cannot describe is not evidence either way
            if size in sizes:
                found.setdefault(size, []).append(path)
    return found


def _relocate(
    result: VerifyResult,
    root: Path,
    by_size: dict[int, list[Path]],
    hashed: dict[Path, str | None],
    cancel: threading.Event | None,
) -> VerifyResult:
    """``result`` again, as MOVED if its bytes are elsewhere under ``root``. Otherwise unchanged."""
    copy = result.copy
    if copy.expected_hash is None or copy.size is None:
        return result
    for candidate in by_size.get(copy.size, ()):
        if cancel is not None and cancel.is_set():
            break
        if candidate not in hashed:
            try:
                hashed[candidate] = sha256_file(candidate)
            except OSError:
                hashed[candidate] = None
        if hashed[candidate] == copy.expected_hash:
            where = candidate.relative_to(root).as_posix()
            return VerifyResult(
                copy, CopyStatus.MOVED, copy.expected_hash, detail=f"found at {where}"
            )
    return result


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
        elif copy.bake_in_flight:
            # ⚠ **Answered WITHOUT hashing, like the two branches above it.** Reading the file
            # would produce a value with nothing trustworthy to compare it to: the recorded hash
            # describes the bytes from before an interrupted write. Hashing to then discard the
            # result is the wasted read `(abo)`'s "nobody looked" reasoning already refuses.
            answered.append(
                VerifyResult(
                    copy,
                    CopyStatus.UNVERIFIABLE,
                    None,
                    detail="a date write was interrupted; run it again to finish it",
                )
            )
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

    # `(aba)`: before any loss is claimed, look for the bytes elsewhere on the drive. ONLY
    # MISSING is offered - a MISMATCH is present-and-damaged, a different fact whose remedy is
    # not "look elsewhere". `_locate_moved` owns the cost gate; there is deliberately no second
    # one here, because a guard a mutation cannot kill is either dead or unexplained.
    misses = [r for r in results if r.status is CopyStatus.MISSING]
    others = [r for r in results if r.status is not CopyStatus.MISSING]
    return others + _locate_moved(misses, root, cancel=cancel)
