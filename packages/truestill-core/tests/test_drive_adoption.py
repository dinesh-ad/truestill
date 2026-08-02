"""Detecting that an unmarked folder is a library the catalog already knows (`(aap)`).

The thresholds are asserted here rather than left to the call sites, because they are the whole
guard: too strict and a half-restored drive mints a duplicate identity anyway, too loose and an
unrelated folder is offered someone else's uuid.
"""

from __future__ import annotations

import threading
from pathlib import Path

import pytest
from truestill_core.drive_adoption import (
    HASH_PROOF,
    PRESENCE_THRESHOLD,
    STAT_SAMPLE,
    AdoptionVerdict,
    RecordedDrive,
    _stride_sample,
    inspect_root,
)


def _tree(root: Path, relatives: list[str], *, content: str = "photo-bytes") -> None:
    for relative in relatives:
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(f"{content}:{relative}")


def _digests(relatives: list[str], *, content: str = "photo-bytes") -> dict[str, str]:
    """The digest each copy should present, under a hasher that just echoes the bytes."""
    return {relative: f"{content}:{relative}" for relative in relatives}


def _echo_hasher(path: Path) -> str:
    return path.read_text()


_RELATIVES = [f"Camera/2021/2021-05/IMG_{i:04d}.jpg" for i in range(60)]

#: Raised by the fixture that proves a failed read is not counted as agreement.
_DEAD_MOUNT = OSError("dead mount")


def _drive(relatives: list[str] | None = None, *, content: str = "photo-bytes") -> RecordedDrive:
    chosen = _RELATIVES if relatives is None else relatives
    return RecordedDrive(
        uuid="uuid-a", label="Photos HDD", digests=_digests(chosen, content=content)
    )


def test_a_moved_library_is_recognised_and_proven(tmp_path: Path) -> None:
    """The case that matters: the whole tree is here, and the bytes prove it."""
    _tree(tmp_path, _RELATIVES)

    offers = inspect_root(tmp_path, [_drive()], hasher=_echo_hasher)

    assert len(offers) == 1
    offer = offers[0]
    assert offer.verdict is AdoptionVerdict.PROVEN
    assert offer.label == "Photos HDD"
    assert offer.sampled == STAT_SAMPLE, "the sample must be capped, not the whole library"
    assert offer.present == STAT_SAMPLE
    assert offer.hashed == HASH_PROOF
    assert offer.proven == HASH_PROOF


def test_an_unrelated_folder_produces_no_offer(tmp_path: Path) -> None:
    """Cry-wolf half. An offer here would hand a stranger's uuid to a brand-new drive."""
    _tree(tmp_path, ["Holiday/DSC_9999.jpg", "Holiday/DSC_9998.jpg"])

    assert inspect_root(tmp_path, [_drive()], hasher=_echo_hasher) == []


def test_a_half_restored_drive_is_still_recognised(tmp_path: Path) -> None:
    """The threshold's reason for being 50% and not 90%.

    A restore that is still running, or a sync that dropped a subtree, is exactly when someone
    reaches for "register this folder" - and exactly when a strict threshold would let them
    mint the duplicate identity this guard exists to stop.
    """
    _tree(tmp_path, _RELATIVES[: len(_RELATIVES) * 6 // 10])

    offers = inspect_root(tmp_path, [_drive()], hasher=_echo_hasher)

    assert offers, "a 60%-restored drive must still be recognised"
    assert offers[0].verdict is AdoptionVerdict.PROVEN


def test_a_folder_below_the_presence_threshold_is_not_offered(tmp_path: Path) -> None:
    """The other side of the same number: a few coincidental names are not a library."""
    _tree(tmp_path, _RELATIVES[:5])

    offers = inspect_root(tmp_path, [_drive()], hasher=_echo_hasher)

    assert offers == [], f"5 of 60 is {5 / 60:.0%}, well under the {PRESENCE_THRESHOLD:.0%} bar"


def test_matching_paths_with_different_bytes_are_reported_not_adopted(tmp_path: Path) -> None:
    """Same layout, different photos - a second library organized by the same scheme.

    This must never read as PROVEN. `reclaim` deletes files on the strength of catalog rows, so
    an adoption that attached rows to a tree they were not proven against is the one failure
    with a real cost to a user's photos.
    """
    _tree(tmp_path, _RELATIVES, content="different-photos")

    offers = inspect_root(tmp_path, [_drive()], hasher=_echo_hasher)

    assert len(offers) == 1, "it must be reported, not silently dropped"
    assert offers[0].verdict is AdoptionVerdict.CONTENT_DIFFERS
    assert offers[0].present == STAT_SAMPLE
    assert offers[0].proven == 0


def test_one_matching_file_among_mismatches_is_not_enough(tmp_path: Path) -> None:
    """Why HASH_PROOF is 3 and why unanimity is required, in one fixture.

    A single agreeing file is reachable by coincidence - a stock image, a zero-byte placeholder.
    Requiring every sampled file to agree is what makes the verdict mean what it says.
    """
    _tree(tmp_path, _RELATIVES, content="different-photos")
    drive = _drive()
    # Make exactly one of the files that will be hashed genuinely match.
    for relative, digest in drive.digests.items():
        if (tmp_path / relative).is_file():
            (tmp_path / relative).write_text(digest)
            break

    offers = inspect_root(tmp_path, [drive], hasher=_echo_hasher)

    assert offers[0].verdict is AdoptionVerdict.CONTENT_DIFFERS
    assert 0 < offers[0].proven < offers[0].hashed


def test_a_majority_of_matching_files_is_still_not_proof(tmp_path: Path) -> None:
    """Unanimity, not a majority - the distinction a 0/3-or-3/3 fixture cannot see.

    Two of three agreeing is exactly what a *partial* overlap looks like: one library restored
    over another, or a folder where some files were replaced. Adopting there would attach the
    catalog's rows - the rows `reclaim` deletes files on the strength of - to a tree that is
    demonstrably not the recorded one. The third disagreement is the whole signal.
    """
    _tree(tmp_path, _RELATIVES)
    drive = _drive()
    # Break exactly one of the three files the stride sampler will hash.
    sampled = _stride_sample(sorted(drive.digests), STAT_SAMPLE)
    for relative in _stride_sample(sampled, HASH_PROOF)[:1]:
        (tmp_path / relative).write_text("replaced-by-a-different-photo")

    offers = inspect_root(tmp_path, [drive], hasher=_echo_hasher)

    assert offers[0].verdict is AdoptionVerdict.CONTENT_DIFFERS
    assert offers[0].proven == HASH_PROOF - 1, "fixture must leave a majority, not a minority"


def test_two_drives_holding_the_same_library_are_both_offered(tmp_path: Path) -> None:
    """A clone is legitimate, and a caller must not be handed one arbitrary winner.

    The evidence for "this is drive A moved" and "this is a clone of drive A" is identical, so
    the only honest output when two match is both of them.
    """
    _tree(tmp_path, _RELATIVES)
    a = RecordedDrive(uuid="uuid-a", label="Photos HDD", digests=_digests(_RELATIVES))
    b = RecordedDrive(uuid="uuid-b", label="Backup HDD", digests=_digests(_RELATIVES))

    offers = inspect_root(tmp_path, [a, b], hasher=_echo_hasher)

    assert {o.uuid for o in offers} == {"uuid-a", "uuid-b"}
    assert all(o.verdict is AdoptionVerdict.PROVEN for o in offers)


def test_the_sample_is_bounded_rather_than_walking_the_library(tmp_path: Path) -> None:
    """Cost is per known drive, not per file - the property that keeps this usable on FUSE."""
    many = [f"Camera/{i // 100:03d}/IMG_{i:05d}.jpg" for i in range(5_000)]
    _tree(tmp_path, many)
    hashed: list[Path] = []

    def counting_hasher(path: Path) -> str:
        hashed.append(path)
        return _echo_hasher(path)

    offers = inspect_root(
        tmp_path, [RecordedDrive("u", "Big", _digests(many))], hasher=counting_hasher
    )

    assert offers[0].verdict is AdoptionVerdict.PROVEN
    assert offers[0].sampled == STAT_SAMPLE, "5,000 recorded files, 40 stats"
    assert len(hashed) == HASH_PROOF, "5,000 recorded files, 3 reads"


def test_the_sample_spans_the_library_rather_than_its_first_rows(tmp_path: Path) -> None:
    """Stride, not head. A drive missing a contiguous region must not read as absent or perfect."""
    _tree(tmp_path, _RELATIVES)
    seen: list[Path] = []

    def tracking_hasher(path: Path) -> str:
        seen.append(path)
        return _echo_hasher(path)

    inspect_root(tmp_path, [_drive()], hasher=tracking_hasher)

    names = sorted(int(p.name[4:8]) for p in seen)
    assert names[-1] - names[0] > len(_RELATIVES) // 2, (
        f"hash samples {names} are clustered; a head-sample would miss a half-synced tail"
    )


def test_a_cancelled_inspection_stops_and_offers_nothing_it_did_not_prove(tmp_path: Path) -> None:
    """Cancellation is a supported outcome on a slow mount, and must not fabricate a verdict."""
    _tree(tmp_path, _RELATIVES)
    cancel = threading.Event()
    cancel.set()

    assert inspect_root(tmp_path, [_drive()], hasher=_echo_hasher, cancel=cancel) == []


def test_a_drive_with_no_recorded_copies_is_never_offered(tmp_path: Path) -> None:
    """Anti-vacuity: an empty digest map must not clear a threshold of zero."""
    _tree(tmp_path, _RELATIVES)

    offers = inspect_root(tmp_path, [RecordedDrive("u", "Empty", {})], hasher=_echo_hasher)

    assert offers == []


def test_an_unreadable_file_is_not_counted_as_proof(tmp_path: Path) -> None:
    """A read that fails is not evidence; treating it as agreement would prove nothing at all."""
    _tree(tmp_path, _RELATIVES)

    def failing_hasher(_path: Path) -> str:
        raise _DEAD_MOUNT

    offers = inspect_root(tmp_path, [_drive()], hasher=failing_hasher)

    assert offers[0].verdict is AdoptionVerdict.CONTENT_DIFFERS
    assert offers[0].proven == 0


@pytest.mark.parametrize("count", [1, 2])
def test_a_tiny_library_still_requires_every_sampled_file_to_agree(
    tmp_path: Path, count: int
) -> None:
    """Fewer files than HASH_PROOF must not weaken the rule to 'nothing disagreed'."""
    relatives = _RELATIVES[:count]
    _tree(tmp_path, relatives, content="different-photos")

    offers = inspect_root(tmp_path, [_drive(relatives)], hasher=_echo_hasher)

    assert offers[0].verdict is AdoptionVerdict.CONTENT_DIFFERS
