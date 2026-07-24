"""Two-tier dedup: exact before perceptual, spanning run and catalog."""

from __future__ import annotations

from vaeon_core.dedup import DedupIndex
from vaeon_core.models import DuplicateKind


def test_new_file_is_not_a_duplicate() -> None:
    index = DedupIndex(threshold=5)
    assert index.check("aa" * 32, "0000000000000000") is None


def test_exact_duplicate_by_sha() -> None:
    index = DedupIndex(threshold=5)
    index.register("/first.jpg", "sha-1", "ffffffffffffffff")
    match = index.check("sha-1", "0000000000000000")
    assert match is not None
    assert match.kind is DuplicateKind.EXACT
    assert match.matched_path == "/first.jpg"
    assert match.origin == "run"


def test_perceptual_duplicate_within_threshold() -> None:
    index = DedupIndex(threshold=5)
    index.register("/orig.jpg", "sha-1", "0000000000000000")
    # differs in 3 bits -> within threshold
    match = index.check("sha-2", "0000000000000007")
    assert match is not None
    assert match.kind is DuplicateKind.PERCEPTUAL
    assert match.matched_path == "/orig.jpg"
    assert match.distance == 3


def test_perceptual_beyond_threshold_is_new() -> None:
    index = DedupIndex(threshold=5)
    index.register("/orig.jpg", "sha-1", "0000000000000000")
    # 0xff = 8 bits set, beyond threshold 5
    assert index.check("sha-2", "00000000000000ff") is None


def test_exact_is_checked_before_perceptual() -> None:
    """A byte-identical file must report EXACT even if a perceptual match also exists."""
    index = DedupIndex(threshold=5)
    index.register("/orig.jpg", "sha-1", "0000000000000000")
    match = index.check("sha-1", "0000000000000001")
    assert match is not None
    assert match.kind is DuplicateKind.EXACT


def test_catalog_origin_is_labelled() -> None:
    index = DedupIndex.from_catalog_rows(
        [("/last-run.jpg", "sha-1", "0000000000000000")], threshold=5
    )
    match = index.check("sha-1", None)
    assert match is not None
    assert match.origin == "catalog"


def test_video_without_perceptual_hash_only_matches_exact() -> None:
    index = DedupIndex(threshold=5)
    index.register("/clip.mp4", "sha-vid", None)
    assert index.check("sha-vid", None) is not None  # exact
    assert index.check("sha-other", None) is None  # nothing perceptual to match
