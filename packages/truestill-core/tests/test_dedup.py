"""Two-tier dedup: exact before perceptual, spanning run and catalog."""

from __future__ import annotations

import logging

import pytest
from truestill_core.dedup import DedupIndex
from truestill_core.models import DuplicateKind


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


def test_a_large_index_says_nothing_because_there_is_nothing_to_announce(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """**Replaces `test_the_linear_scan_alarm_fires_once_at_the_threshold`.**

    `LINEAR_SCAN_ALARM` warned at 10,000 images that *"perceptual matching is now the slow
    path"*. That was true of the hex-parsing loop - 13.709 s at 10,000, measured - and it is
    false of the packed matcher, which does the same 10,000 at about 0.1 s. The warning had no
    trigger point left: even at 150,000 images matching costs ~9 s against per-file stages
    measured in the thousands of seconds, so there is no library size at which it becomes the
    slow path and no honest number to re-aim the constant at.

    Deleting a warning is a behaviour change, so the *absence* is asserted rather than left to
    the reader: a user past 10,000 photos must no longer be told their library is slow.
    """
    index = DedupIndex(threshold=5)
    with caplog.at_level(logging.WARNING, logger="truestill_core.dedup"):
        for i in range(10_050):
            index.register(f"/p/{i}.jpg", f"sha{i}", f"{i:016x}")

    assert not [r for r in caplog.records if "slow path" in r.message]
