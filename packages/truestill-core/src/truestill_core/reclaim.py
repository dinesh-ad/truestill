"""Space-safe source reclamation: delete source files whose content is safely backed up.

The standalone half of feature (k) -- `truestill reclaim`. It frees a source file **only** after
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
from truestill_core.drive import CopyIndependence, copy_independence, device_for_drive
from truestill_core.hashing import sha256_file
from truestill_core.progress import Phase, Progress, ProgressCallback


@dataclass(frozen=True)
class ReclaimCandidate:
    """A source file eligible to be freed: its content re-verifies on the connected drive."""

    source_path: Path
    sha256: str
    size: int
    copies: int  # total recorded copies of this content across all drives
    relative: str  # the copy on the connected drive, to re-verify
    expected_sha: str  # copy_sha256 (or the source sha for legacy copies)
    #: Whether this content's holders can fail separately. `(aiy)`. **Never a count** - `copies`
    #: above answers "how many", this answers "how many failure domains", and conflating them is
    #: the defect this field exists for.
    independence: CopyIndependence = CopyIndependence.UNKNOWN


@dataclass(frozen=True)
class ReclaimPlan:
    """What reclaim would free (pure; deletes nothing).

    An empty ``candidates`` list is normal when there is nothing left to free. That is distinct
    from ``missing_sources``: recorded ``files.source_path`` values that are gone or
    unreachable (moved machine, deleted already, locked mount). Only the latter must read as
    a problem; a calm empty plan must not.
    """

    candidates: list[ReclaimCandidate]
    unverified: int  # copies on the drive that failed re-verify -> their sources are NOT offered
    below_min_copies: int  # sources excluded because too few copies exist
    organized_in_place: int = 0  # source IS the drive copy -- freeing it would delete the only one
    missing_sources: int = 0  # catalog rows whose source_path is gone / unreachable
    missing_examples: tuple[str, ...] = ()  # sample absolute paths for the message

    @property
    def total_bytes(self) -> int:
        return sum(c.size for c in self.candidates)

    @property
    def single_copy(self) -> list[ReclaimCandidate]:
        """Candidates whose content would exist in only one place after the source is freed."""
        return [c for c in self.candidates if c.copies <= 1]

    @property
    def not_independent(self) -> list[ReclaimCandidate]:
        """Candidates **proven** to have all their copies inside one failure domain. `(aiy)`

        Two folders on one USB stick are two `file_copies` rows, so `copies` is 2 and
        :attr:`single_copy` is empty - the guard that stands between a user and
        ``reclaim --apply`` never fires. This is the bucket that fires instead.

        ⚠ **``copies > 1`` EXCLUDES WHAT :attr:`single_copy` ALREADY SAYS.** A lone copy is
        honestly one failure domain, so `drive.copy_independence` returns ``NOT_INDEPENDENT`` for
        it - but reporting one file under two warnings tells a user two things about one fact.
        This bucket is the case the count **cannot** see; that one is the case it can.
        """
        return [
            c
            for c in self.candidates
            if c.independence is CopyIndependence.NOT_INDEPENDENT and c.copies > 1
        ]

    @property
    def independence_unknown(self) -> list[ReclaimCandidate]:
        """Candidates with at least one holder that could not be asked. **The common case.**

        A drive in a drawer cannot be stat'd, so this is most content most of the time. It is
        reported and **never refused** - see `cli._print_reclaim_plan`, which states what is not
        known rather than implying a verdict either way.
        """
        return [c for c in self.candidates if c.independence is CopyIndependence.UNKNOWN]


@dataclass(frozen=True)
class ReclaimOutcome:
    plan: ReclaimPlan
    deleted: int
    freed_bytes: int
    kept: int  # candidates that failed the fresh re-verify at delete time (never deleted)


_MISSING_EXAMPLE_CAP = 5


def _safe_size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


def _readable_file(path: Path) -> bool:
    """True when ``path`` is a regular file we can stat. Every failure answers **False**.

    ⚠ **REFUSED IS DELIBERATELY COLLAPSED INTO ABSENT HERE, AND THAT IS A DECISION - NOT A SITE
    `(aey)` MISSED.** `truestill_core.path_reach` exists to tell *absent* from *refused*, and
    reclaim **must not use it**: this is the only path in the product that deletes a user's files,
    and the only question it may ask is *"have I positively established that this file is fine?"*
    A file we cannot examine must never become a delete candidate, so both answers - it is not
    there, and I could not look - have to land on the same conservative side. Acquiring the
    distinction here would mean acquiring the ability to act on it, which is the opposite of what
    this gate is for.

    **Named for the question rather than for the caller**: it guards a source and a destination
    copy alike, and calling it `_source_present` at a destination site is how the two probes below
    came to bypass it in the first place.
    """
    try:
        return path.is_file()
    except OSError:
        return False


def _is_the_copy_itself(source: Path, mount_root: Path, relative: str) -> bool:
    """Whether ``source`` and the drive's copy are the *same file*, not two copies of it.

    After an in-place organize the source was renamed into the library rather than copied, so
    ``files.source_path`` and ``file_copies.relative`` name one inode. Reclaim's safety rests
    on re-hashing the destination copy before deleting the source -- but a file verifies
    against itself unconditionally, which would turn the strongest gate in the product into a
    tautology and delete the only copy of content whose owner, by definition of the feature,
    has no backup. Such a file is never a reclaim candidate.
    """
    try:
        return (mount_root / relative).samefile(source)
    except OSError:
        return False  # one side missing or unreadable -- the normal checks below handle it


def _verify(mount_root: Path, relative: str, expected_sha: str) -> bool:
    """Whether the destination copy exists and re-hashes to the expected content hash, now.

    ⚠ **The probe goes through `_readable_file`, and a bare `path.is_file()` here was a live
    defect on 3.13** - found 2026-08-21 by writing the pin `(aey)` called for, `(aez)`. A backup
    copy on a folder that refused made `is_file()` **raise**, uncaught, so `plan_reclaim` aborted
    with a traceback instead of counting the copy unverified. The guarded helper was three
    functions above and this call did not reach it.
    """
    path = mount_root / relative
    if not _readable_file(path):
        return False
    try:
        return sha256_file(path) == expected_sha
    except OSError:
        return False


def plan_reclaim(
    catalog: Catalog, drive_uuid: str, mount_root: Path, *, min_copies: int = 1
) -> ReclaimPlan:
    """Find source files safely backed up on the connected drive. Re-verifies; deletes nothing.

    Missing ``source_path`` rows are counted and sampled, never silently dropped into an
    unexplained empty plan.
    """
    candidates: list[ReclaimCandidate] = []
    #: uuid -> device, asked at most once per drive. `(aiy)`. A stat per DRIVE, not per file:
    #: there are a handful of drives and there may be a hundred thousand candidates.
    devices: dict[str, int | None] = {}

    def _independence(holder_uuids: str | None) -> CopyIndependence:
        uuids = [u for u in (holder_uuids or "").split(",") if u]
        for u in uuids:
            if u not in devices:
                devices[u] = device_for_drive(catalog, u)
        return copy_independence([devices[u] for u in uuids])

    unverified = 0
    below = 0
    in_place = 0
    missing = 0
    missing_examples: list[str] = []
    for row in catalog.reclaim_candidates(drive_uuid):
        source = Path(row["source_path"])
        if not _readable_file(source):
            missing += 1
            if len(missing_examples) < _MISSING_EXAMPLE_CAP:
                missing_examples.append(str(source))
            continue
        if _is_the_copy_itself(source, mount_root, str(row["relative"])):
            in_place += 1
            continue  # organized in place: deleting the "source" deletes the only copy
        # No recorded hash means the re-verify gate cannot be satisfied, and reclaim's whole
        # safety argument is that gate. Counted as unverified, never offered for deletion.
        expected = row["copy_sha256"]
        if expected is None:
            unverified += 1
            continue
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
                independence=_independence(row["holder_uuids"]),
            )
        )
    return ReclaimPlan(
        candidates=candidates,
        unverified=unverified,
        below_min_copies=below,
        organized_in_place=in_place,
        missing_sources=missing,
        missing_examples=tuple(missing_examples),
    )


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
        # ⚠ `_readable_file`, not a bare `is_file()`: the same defect as `_verify`'s, and worse
        # here. This runs mid-loop, so a source that became unreadable after the plan was built
        # raised **after earlier candidates had already been deleted** - a partial run ending in a
        # traceback rather than a kept file and a count. `(aez)`
        if not (
            _readable_file(candidate.source_path)
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
            progress(Progress(done, total, Phase.FREEING, candidate.source_path.name))
    return ReclaimOutcome(plan=plan, deleted=deleted, freed_bytes=freed, kept=kept)
