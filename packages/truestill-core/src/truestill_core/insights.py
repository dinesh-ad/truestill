"""What a library *is*, computed once for every surface that reports it.

These facts existed only inside the app's run summary, so a preview could not state them -- the
same contract written in one place and unreachable from the other, which
`ENGINEERING_STANDARD.md` §4 records as this repo's recurring defect. They live here so the CLI
preview, the app run and (later) Analyze answer from one implementation.

**Sizes are injected rather than measured.** A finished run sizes the file where it *landed*;
a preview can only size the source, because nothing has been copied yet. That difference is
real and belongs to the caller -- baking either choice in here would make one of the two lie.

Everything is pure: no filesystem access, no catalog, no I/O. Read-only by construction rather
than by promise.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from truestill_core.models import Resolution, partition_for_report


@dataclass(frozen=True, slots=True)
class DuplicateBytes:
    """What duplicate detection found, with reclaimable space kept strictly separate.

    **Near-duplicate bytes are not savings and this type refuses to imply otherwise.**
    Truestill *keeps* a near-duplicate -- it is uploaded and flagged for review, never dropped
    -- so no operation will ever return those bytes. Reporting them as space saved would be
    the first number in this product that promises something untrue. Only ``exact_bytes`` is
    reclaimable, and :attr:`reclaimable_bytes` exists to say so at the call site.
    """

    exact_files: int
    exact_bytes: int
    near_files: int
    near_bytes: int

    @property
    def reclaimable_bytes(self) -> int:
        """Space an organize run actually avoids using. Exact duplicates only."""
        return self.exact_bytes


@dataclass(frozen=True, slots=True)
class CaptureSpan:
    """The oldest and newest capture instants seen. ``None`` when nothing carried a date."""

    oldest: datetime
    newest: datetime


@dataclass(frozen=True, slots=True)
class CaptureYears:
    """Files per capture year, oldest first, plus the ones that belong to no year.

    ``undated`` is not an afterthought: ``sum(by_year.values()) + undated`` must equal the
    number of resolutions, so a reader can add the column up. A histogram that silently drops
    undated files disagrees with the file count and nothing says which is wrong.
    """

    by_year: dict[int, int]
    undated: int


@dataclass(frozen=True, slots=True)
class SizedFile:
    path: Path
    size: int


@dataclass(frozen=True, slots=True)
class LargestFiles:
    """A capped enumeration with an exact total - the `{total, shown}` discipline.

    ``total`` counts every file considered; ``shown`` is only what a report will print. A cap
    that also changed the count would be the tally-conservation defect in a new place.
    """

    total: int
    shown: tuple[SizedFile, ...]


def duplicate_bytes(resolutions: Iterable[Resolution], sizes: Mapping[Path, int]) -> DuplicateBytes:
    """Count duplicate files and their bytes, split by tier.

    A file with no recorded size still counts as a *file* and contributes zero *bytes*: a
    source that vanished between the scan and the sizing is ordinary, and dropping it from the
    count would make the tally disagree with the buckets.
    """
    buckets = partition_for_report(resolutions)
    exact, near = buckets.exact_duplicates, buckets.near_duplicates
    return DuplicateBytes(
        exact_files=len(exact),
        exact_bytes=sum(sizes.get(r.decision.source, 0) for r in exact),
        near_files=len(near),
        near_bytes=sum(sizes.get(r.decision.source, 0) for r in near),
    )


def capture_span(resolutions: Iterable[Resolution]) -> CaptureSpan | None:
    """The date range, or ``None`` when nothing is dated.

    ``None`` rather than a placeholder year, for the reason the run summary already gives: an
    undated batch has no range, and inventing one is exactly the "computed for effect" the
    honesty rule forbids.
    """
    dates = [r.decision.captured_at for r in resolutions if r.decision.captured_at is not None]
    return CaptureSpan(oldest=min(dates), newest=max(dates)) if dates else None


def capture_years(resolutions: Iterable[Resolution]) -> CaptureYears:
    """Files per year, oldest first, with undated files counted rather than dropped.

    Only years that hold files appear. A zero row for every gap year would turn a 20-year
    library into a wall of noise, and the gap is visible from the years that are there.
    """
    counts: Counter[int] = Counter()
    undated = 0
    for resolution in resolutions:
        captured = resolution.decision.captured_at
        if captured is None:
            undated += 1
        else:
            counts[captured.year] += 1
    return CaptureYears(by_year={year: counts[year] for year in sorted(counts)}, undated=undated)


def largest_files(sizes: Mapping[Path, int], *, limit: int) -> LargestFiles:
    """The biggest files, capped, with the total left exact.

    Ties break on the path so the same library renders identically on every platform - a
    report that reorders between runs cannot be diffed.
    """
    ranked = sorted(sizes.items(), key=lambda item: (-item[1], str(item[0])))
    shown = tuple(SizedFile(path=path, size=size) for path, size in ranked[: max(0, limit)])
    return LargestFiles(total=len(sizes), shown=shown)


def sizes_for(resolutions: Sequence[Resolution]) -> dict[Path, int]:
    """Source sizes for a preview, via one ``stat`` per file.

    Kept here so a caller cannot accidentally size a *destination* copy that does not exist
    yet. Unreadable files are skipped rather than raised, matching `filesystem.sizes_of`.
    """
    found: dict[Path, int] = {}
    for resolution in resolutions:
        source = resolution.decision.source
        try:
            found[source] = source.stat().st_size
        except OSError:
            continue
    return found
