"""The near-dup index refuses some files, and the report names every one it refused. `(ahq)`

⚠ **THIS IS THE HALF `(ahq)` SHIPPED WITHOUT.** `dedup.carries_no_signal` excluded **97 files on
one real 10,138-image library** from near-duplicate comparison and reached no surface at all - no
count, no reason, nothing. `IMPLEMENTATION_STANDARDS.md`'s never-silent rule binds a *skipped,
refused, degraded or unverifiable* outcome to be **counted and named**, and an exclusion the
product performs on its own initiative is the case that rule most exists for. `make check` was
green throughout, because nothing here existed.

🔑 **IT ASSERTS AGAINST THE INDEX'S OWN BEHAVIOUR, NOT AGAINST A SECOND COPY OF THE PREDICATE.**
The obvious test - build a hash, call `carries_no_signal`, check the report agrees - proves only
that one function equals itself. What has to hold is that **the set the report names is exactly
the set `DedupIndex` refused**, so this file registers files into a real index, reads back what it
indexed, and compares. A drift between the two is the failure; a test that cannot see it is the
fourth declaration-shaped guard in a week.
"""

from __future__ import annotations

from pathlib import Path

from truestill_core.dedup import DedupIndex
from truestill_core.hashing import DEFAULT_PHASH_THRESHOLD
from truestill_core.models import (
    CategoryMatch,
    Confidence,
    DateSource,
    Decision,
    FileHashes,
    Resolution,
    UncomparedReason,
)
from truestill_core.organizer import UncomparedPhotos, uncompared_photos

#: Popcount 32 - as far from either pole as a 64-bit hash gets, so it is indexed under any
#: threshold this product will ever ship.
_SIGNAL = "aaaaaaaaaaaaaaaa"


def _resolution(name: str, perceptual: str | None, *, computed: bool = True) -> Resolution:
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
        hashes=FileHashes(
            sha256=None,
            perceptual=perceptual,
            unreadable=None,
            perceptual_computed=computed,
        ),
        exact_duplicate=None,
        near_duplicate=None,
    )


def _named(groups: tuple[UncomparedPhotos, ...], reason: UncomparedReason) -> set[str]:
    return {f for g in groups if g.reason is reason for f in g.files}


def test_the_report_names_exactly_what_the_index_refused() -> None:
    """The two sets are equal. Not "the report is non-empty" - equal, both ways.

    A flat frame (all-zero), a monotonic gradient (all-one) and a hash four bits off each pole are
    all refused by `DedupIndex`; an ordinary photograph is not. Whatever the index declines to
    hold, the report has to say out loud.
    """
    files = {
        "flat.jpg": "0000000000000000",
        "gradient.jpg": "ffffffffffffffff",
        "near_zero.jpg": "000000000000000f",
        "near_one.jpg": "fffffffffffffff0",
        "photo.jpg": _SIGNAL,
    }
    index = DedupIndex(DEFAULT_PHASH_THRESHOLD)
    for name, perceptual in files.items():
        index.register(name, sha256=None, perceptual=perceptual)
    indexed = set(index._phash_paths)
    refused = set(files) - indexed

    groups = uncompared_photos(
        [_resolution(n, p) for n, p in files.items()],
        phash_threshold=DEFAULT_PHASH_THRESHOLD,
    )

    assert refused == {"flat.jpg", "gradient.jpg", "near_zero.jpg", "near_one.jpg"}, (
        "the index's own behaviour changed; this test's premise, not its subject"
    )
    assert _named(groups, UncomparedReason.NO_SIGNAL) == refused, (
        "the report must name every file the index refused to compare, and no other"
    )


def test_the_threshold_the_run_applied_is_the_threshold_the_report_states() -> None:
    """Raise the threshold and both the refusal and the report widen together. `(ahq)`

    ⚠ **THE FAILURE THIS CATCHES IS A REPORT THAT READS THE DEFAULT.** `analyze` takes
    `--phash-threshold`; a report hard-coding `DEFAULT_PHASH_THRESHOLD` would be right on the app
    and quietly wrong on every CLI run that moved it - a number derived from a different rule than
    the one the run applied.
    """
    middling = _resolution("middling.jpg", "00000000000000ff")  # popcount 8

    at_default = uncompared_photos([middling], phash_threshold=DEFAULT_PHASH_THRESHOLD)
    at_ten = uncompared_photos([middling], phash_threshold=10)

    assert at_default == (), "eight set bits carries more signal than a threshold of five tolerates"
    assert _named(at_ten, UncomparedReason.NO_SIGNAL) == {"middling.jpg"}

    index = DedupIndex(10)
    index.register("middling.jpg", sha256=None, perceptual="00000000000000ff")
    assert index._phash_paths == [], "premise: the index refuses it at ten too"


def test_the_two_reasons_stay_apart() -> None:
    """A file that could not be decoded and a file with nothing to compare are two facts.

    Folding them into one heading would tell someone their photograph failed to open when it
    opened perfectly well - and the remedies are identical, so nothing but the label carries the
    difference.
    """
    groups = uncompared_photos(
        [
            _resolution("broken.jpg", None),
            _resolution("flat.jpg", "0000000000000000"),
        ],
        phash_threshold=DEFAULT_PHASH_THRESHOLD,
    )

    assert {g.reason for g in groups} == {
        UncomparedReason.UNDECODABLE,
        UncomparedReason.NO_SIGNAL,
    }
    assert _named(groups, UncomparedReason.UNDECODABLE) == {"broken.jpg"}
    assert _named(groups, UncomparedReason.NO_SIGNAL) == {"flat.jpg"}
    assert len({g.label for g in groups}) == 2, "two facts, two headings"


def test_a_group_with_nothing_in_it_is_absent() -> None:
    """Never-silent is about what happened, not about what did not - `skipped_folder_groups`'s
    rule, and this report is held to it too. An ordinary library must not sprout a zero row."""
    groups = uncompared_photos(
        [_resolution("photo.jpg", _SIGNAL)], phash_threshold=DEFAULT_PHASH_THRESHOLD
    )
    assert groups == ()
