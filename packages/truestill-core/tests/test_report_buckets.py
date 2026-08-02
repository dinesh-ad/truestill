"""Every scanned file lands in exactly one reported bucket, and the buckets sum to the scan.

`BACKLOG.md` ``(aac)`` residue 1. The preview counted an unreadable file **twice**: once in
*"organized (unique)"*, because a file with no hash matches nothing and so reads as new, and
again in *"files that could not be read"*. Two contradictory statements about the same photo.

The conservation law is the point of this file, not the corrected number. A future category -
"corrupt", "over the pixel ceiling", whatever residue 2 turns into - that forgets to be disjoint
fails :func:`test_the_buckets_always_sum_to_the_files_scanned` rather than silently
double-counting the way this one did.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from truestill_core.categorize import CategoryMatch, Confidence
from truestill_core.models import (
    DateSource,
    Decision,
    DuplicateKind,
    DuplicateMatch,
    FileHashes,
    Resolution,
    UnreadableReason,
    partition_for_report,
)


def _resolution(
    name: str,
    *,
    unreadable: UnreadableReason | None = None,
    exact: bool = False,
    near: bool = False,
) -> Resolution:
    decision = Decision(
        source=Path("/src") / name,
        category=CategoryMatch(
            label="Camera", reason="t", confidence=Confidence.HIGH, rule="device"
        ),
        captured_at=None,
        date_source=DateSource.NONE,
        date_tag=None,
        relative=Path("Camera/Undated") / name,
    )
    return Resolution(
        decision=decision,
        hashes=FileHashes(sha256="a" * 64, perceptual=None, unreadable=unreadable),
        exact_duplicate=(
            DuplicateMatch(kind=DuplicateKind.EXACT, matched_path="/lib/twin.jpg", origin="run")
            if exact
            else None
        ),
        near_duplicate=(
            DuplicateMatch(
                kind=DuplicateKind.PERCEPTUAL,
                matched_path="/lib/similar.jpg",
                origin="run",
                distance=3,
            )
            if near
            else None
        ),
    )


#: One of every shape a resolution can take, including the two overlaps that caused the defect.
_MIXED = [
    _resolution("new.jpg"),
    _resolution("also-new.jpg"),
    _resolution("twin.jpg", exact=True),
    _resolution("lookalike.jpg", near=True),
    _resolution("locked.jpg", unreadable=UnreadableReason.PERMISSION),
    _resolution("failing.jpg", unreadable=UnreadableReason.IO_ERROR, exact=True),
    _resolution("gone.jpg", unreadable=UnreadableReason.MISSING, near=True),
]


def test_the_buckets_always_sum_to_the_files_scanned() -> None:
    """Conservation. The law that retires the class rather than the instance."""
    buckets = partition_for_report(_MIXED)

    assert buckets.total == len(_MIXED), (
        "a file went missing or was counted twice; every scanned file must be in exactly one "
        "bucket, which is what lets a report's numbers be added up at all"
    )


def test_no_file_appears_in_two_buckets() -> None:
    """Disjointness stated directly, so a failure names the overlap instead of a wrong total."""
    buckets = partition_for_report(_MIXED)
    seen: dict[Path, str] = {}
    for label, group in (
        ("unreadable", buckets.unreadable),
        ("exact_duplicates", buckets.exact_duplicates),
        ("near_duplicates", buckets.near_duplicates),
        ("unique", buckets.unique),
    ):
        for resolution in group:
            source = resolution.decision.source
            assert source not in seen, f"{source.name} is in both {seen[source]} and {label}"
            seen[source] = label

    assert len(seen) == len(_MIXED)


def test_an_unreadable_file_is_never_counted_as_one_that_will_be_organized() -> None:
    """The reported defect, as a property. This is what said "organized (unique): 5"."""
    buckets = partition_for_report(_MIXED)
    organized_names = {r.decision.source.name for r in buckets.organized}

    assert "locked.jpg" not in organized_names
    assert "failing.jpg" not in organized_names
    assert "gone.jpg" not in organized_names
    assert organized_names == {"new.jpg", "also-new.jpg", "lookalike.jpg"}


@pytest.mark.parametrize(
    ("name", "reason"),
    [("failing.jpg", "exact"), ("gone.jpg", "near")],
)
def test_unreadable_wins_over_a_duplicate_verdict(name: str, reason: str) -> None:
    """Precedence, and it is not academic: a cache hit gives an unreadable file real hashes.

    `HashCache` keys on size and mtime, both from ``stat``, and ``stat`` succeeds on a file whose
    bytes cannot be read - so a file that was readable last run can match the exact or perceptual
    tier while being unreadable now. Filing it under "duplicate, will skip" would describe it as
    a routine skip when truestill could not read it.
    """
    buckets = partition_for_report(_MIXED)
    unreadable_names = {r.decision.source.name for r in buckets.unreadable}
    duplicate_names = {
        r.decision.source.name for r in buckets.exact_duplicates + buckets.near_duplicates
    }

    assert name in unreadable_names, f"an unreadable {reason} duplicate belongs in unreadable"
    assert name not in duplicate_names


def test_an_ordinary_scan_partitions_exactly_as_it_always_did() -> None:
    """Cry-wolf half. With nothing unreadable, the split must match the old `should_upload` one.

    Without this, a partition that quietly reclassified ordinary files would pass every
    assertion above - the totals would still conserve, just into the wrong buckets.
    """
    readable = [r for r in _MIXED if r.hashes.unreadable is None]
    buckets = partition_for_report(readable)

    assert not buckets.unreadable
    assert buckets.organized == [r for r in readable if r.should_upload]
    assert buckets.exact_duplicates == [r for r in readable if not r.should_upload]
    assert buckets.total == len(readable)
