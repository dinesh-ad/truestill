"""Space-safe source reclamation: delete source files whose content is safely backed up.

The standalone half of feature (k) -- `vaeon reclaim`. It frees a source file **only** after
re-hashing a destination copy of that content on a currently-connected drive and confirming it
matches (the re-verify-always policy: a stale ``last_verified`` is never trusted for an
irreversible delete). The delete is journalled for audit/resume. `--min-copies` gates on how many
recorded copies must exist; the default is 1, with the single-copy cases surfaced as a warning.

This is a documented, contained exception to the copy-only invariant (see
IMPLEMENTATION_STANDARDS §1), scoped exactly like the Takeout write path.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from truestill_core.catalog import Catalog
from truestill_core.hashing import sha256_file
from truestill_core.progress import ProgressCallback


@dataclass(frozen=True)
class ReclaimCandidate:
    """A source file eligible to be freed: its content re-verifies on the connected drive."""

    source_path: Path
    sha256: str
    size: int
    copies: int  # total recorded copies of this content across all drives
    relative: str  # the copy on the connected drive, to re-verify
    expected_sha: str  # copy_sha256 (or the source sha for legacy copies)


@dataclass(frozen=True)
class ReclaimPlan:
    """What reclaim would free (pure; deletes nothing)."""

    candidates: list[ReclaimCandidate]
    unverified: int  # copies on the drive that failed re-verify -> their sources are NOT offered
    below_min_copies: int  # sources excluded because too few copies exist

    @property
    def total_bytes(self) -> int:
        return sum(c.size for c in self.candidates)

    @property
    def single_copy(self) -> list[ReclaimCandidate]:
        """Candidates whose content would exist in only one place after the source is freed."""
        return [c for c in self.candidates if c.copies <= 1]


@dataclass(frozen=True)
class ReclaimOutcome:
    plan: ReclaimPlan
    deleted: int
    freed_bytes: int
    kept: int  # candidates that failed the fresh re-verify at delete time (never deleted)


def _safe_size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


def _verify(mount_root: Path, relative: str, expected_sha: str) -> bool:
    """Whether the destination copy exists and re-hashes to the expected content hash, now."""
    path = mount_root / relative
    if not path.is_file():
        return False
    try:
        return sha256_file(path) == expected_sha
    except OSError:
        return False


def plan_reclaim(
    catalog: Catalog, drive_uuid: str, mount_root: Path, *, min_copies: int = 1
) -> ReclaimPlan:
    """Find source files safely backed up on the connected drive. Re-verifies; deletes nothing."""
    candidates: list[ReclaimCandidate] = []
    unverified = 0
    below = 0
    for row in catalog.reclaim_candidates(drive_uuid):
        source = Path(row["source_path"])
        if not source.is_file():
            continue  # source already gone -- nothing to reclaim
        expected = row["copy_sha256"] or row["sha256"]
        if not _verify(mount_root, row["relative"], expected):
            unverified += 1
            continue  # the copy on this drive did not re-verify -- never offer to delete
        if row["copy_count"] < min_copies:
            below += 1
            continue
        size = row["size"] if row["size"] is not None else _safe_size(source)
        candidates.append(
            ReclaimCandidate(
                source_path=source,
                sha256=str(row["sha256"]),
                size=int(size),
                copies=int(row["copy_count"]),
                relative=str(row["relative"]),
                expected_sha=str(expected),
            )
        )
    return ReclaimPlan(candidates=candidates, unverified=unverified, below_min_copies=below)


def run_reclaim(
    catalog: Catalog,
    drive_uuid: str,
    mount_root: Path,
    *,
    min_copies: int = 1,
    progress: ProgressCallback | None = None,
) -> ReclaimOutcome:
    """Delete each candidate's source after a fresh re-verify, journalling every deletion."""
    plan = plan_reclaim(catalog, drive_uuid, mount_root, min_copies=min_copies)
    deleted = 0
    freed = 0
    kept = 0
    total = len(plan.candidates)
    for done, candidate in enumerate(plan.candidates, start=1):
        # Re-verify fresh, immediately before deleting: never delete on a stale check.
        if not (
            candidate.source_path.is_file()
            and _verify(mount_root, candidate.relative, candidate.expected_sha)
        ):
            kept += 1
            continue
        catalog.record_reclaim(str(candidate.source_path), candidate.sha256, candidate.size)
        try:
            candidate.source_path.unlink()
        except OSError:
            catalog.clear_reclaim(str(candidate.source_path))
            kept += 1
            continue
        catalog.clear_reclaim(str(candidate.source_path))
        deleted += 1
        freed += candidate.size
        if progress is not None:
            progress(done, total)
    return ReclaimOutcome(plan=plan, deleted=deleted, freed_bytes=freed, kept=kept)
