"""The packed matcher must return **the same answers** as the per-pair loop it replaces.

Not "similar" - identical. This decides which files are flagged as near-duplicates across an
entire library, and a near-duplicate is kept-and-flagged rather than backed up again, so a
subtle divergence changes what a user's backup contains without ever announcing itself.

**Red-first does not apply and saying so is part of the record** (`ENGINEERING_STANDARD.md`
§4). The code being replaced was correct, only slow, so the equivalence test below passes
against both implementations by construction - that is what makes it an equivalence test.
What it cannot show on its own is that the *new* path is the one running, so
`test_the_packed_array_is_what_the_matcher_reads` asserts on the representation and the
mutation proof in the commit message drives the vectorised comparison red.
"""

from __future__ import annotations

import random
import time

import numpy as np
import pytest
from truestill_core.dedup import HASH_BITS, DedupIndex, pack_hash
from truestill_core.hashing import DEFAULT_PHASH_THRESHOLD, hamming_distance
from truestill_core.models import DuplicateKind

T = DEFAULT_PHASH_THRESHOLD


def _hex(value: int) -> str:
    return f"{value:016x}"


def _reference_match(
    known: list[tuple[str, str]], probe: str, threshold: int
) -> tuple[str | None, int]:
    """The replaced implementation, kept here as the oracle.

    A copy, deliberately: comparing the new code against itself proves nothing, and the point
    of an equivalence test is that the thing it agrees with does not change when the
    production code does.
    """
    best_path: str | None = None
    best_distance = threshold + 1
    for path, value in known:
        distance = hamming_distance(probe, value)
        if distance <= threshold and distance < best_distance:
            best_path, best_distance = path, distance
    return best_path, best_distance


def test_the_packed_array_is_what_the_matcher_reads() -> None:
    """Anti-vacuity for every equivalence assertion below: prove the new path is live.

    Without this, all of them would still pass if the packed representation were quietly
    dropped and the old loop restored - which is exactly the change this commit makes.
    """
    index = DedupIndex(threshold=T)
    index.register("/p/a.jpg", "sha-a", _hex(0xDEADBEEFCAFEF00D))

    assert index._packed.dtype == np.uint64
    assert index._count == 1
    assert int(index._packed[0]) == 0xDEADBEEFCAFEF00D
    assert not hasattr(index, "_phash_values"), "the hex-string list is gone, not shadowed"


def _near(rng: random.Random, base: int, spread: int) -> int:
    """``base`` with up to ``spread`` bits flipped - a re-encode, a resize, a re-save."""
    value = base
    for bit in rng.sample(range(HASH_BITS), rng.randint(0, spread)):
        value ^= 1 << bit
    return value


@pytest.mark.parametrize("seed", [1, 2, 3, 4])
def test_exact_equivalence_over_a_large_random_hash_set(seed: int) -> None:
    """500 known images x 250 probes x 4 seeds = 500,000 pair comparisons, all agreeing.

    **The corpus is deliberately not uniform random, and a mutation is why.** With purely
    random 64-bit hashes every probe misses - they sit ~32 bits apart - so an earlier version
    of this test never once exercised the code that picks *which* of several near images
    wins, and replacing `argmin` with "first within threshold" left it green. A real library
    is clusters: bursts, re-saves, exports. So ~20% of the corpus here is planted as
    near-duplicates of an earlier entry, half the probes are drawn near a known hash, and the
    hit path is exercised alongside the miss path that dominates a real run.
    """
    rng = random.Random(seed)
    known: list[tuple[str, str]] = []
    for i in range(500):
        if known and rng.random() < 0.2:
            value = _near(rng, int(known[rng.randrange(len(known))][1], 16), T + 2)
        else:
            value = rng.getrandbits(HASH_BITS)
        known.append((f"/p/{i}.jpg", _hex(value)))

    index = DedupIndex(threshold=T)
    for path, value in known:
        index.register(path, f"sha-{path}", value)

    hits = 0
    for _ in range(250):
        if rng.random() < 0.5:
            probe = _hex(_near(rng, int(rng.choice(known)[1], 16), T + 2))
        else:
            probe = _hex(rng.getrandbits(HASH_BITS))
        expected_path, expected_distance = _reference_match(known, probe, T)
        match = index.check(None, probe)

        if expected_path is None:
            assert match is None
        else:
            hits += 1
            assert match is not None
            assert match.matched_path == expected_path
            assert match.distance == expected_distance

    assert hits > 50, (
        f"only {hits} of 250 probes matched; this corpus is meant to exercise the hit path as "
        f"well as the miss path, and a near-miss-only run would prove far less than it looks"
    )


@pytest.mark.parametrize("distance", [0, 1, T - 1, T, T + 1, T + 2, 32, HASH_BITS])
def test_every_boundary_distance_lands_the_same_way(distance: int) -> None:
    """The threshold edges, exhaustively: 0, either side of 5, and a full 64-bit inversion.

    `T` and `T + 1` are the pair that an inclusive/exclusive slip would swap, and they are
    the whole reason this is parametrized rather than spot-checked.
    """
    base = 0x0F0F0F0F0F0F0F0F
    flipped = base
    for bit in range(distance):
        flipped ^= 1 << bit

    index = DedupIndex(threshold=T)
    index.register("/p/base.jpg", "sha-base", _hex(base))
    match = index.check(None, _hex(flipped))

    assert hamming_distance(_hex(base), _hex(flipped)) == distance, "fixture check"
    if distance <= T:
        assert match is not None
        assert match.distance == distance
        assert match.kind is DuplicateKind.PERCEPTUAL
    else:
        assert match is None


def test_a_file_with_no_perceptual_hash_matches_nothing_perceptually() -> None:
    """**The failure mode this design exists to refuse.**

    A video, an audio file or an undecodable image has no perceptual hash. Packing `None` as
    the integer zero would make every one of them sit at distance 0 from every other and
    within 5 bits of any hash with few set bits - the entire library collapsing into one
    near-duplicate chain, silently, with the files never backed up.
    """
    index = DedupIndex(threshold=T)
    index.register("/p/zero.jpg", "sha-zero", _hex(0))
    index.register("/p/movie.mov", "sha-movie", None)

    assert index.check("sha-other", None) is None, "no hash cannot mean 'matches everything'"
    assert index._count == 1, "an unhashable file must not occupy a slot in the packed array"
    assert index._phash_paths == ["/p/zero.jpg"]

    # And it is still found by content, which is the tier that does apply to it.
    exact = index.check("sha-movie", None)
    assert exact is not None
    assert exact.kind is DuplicateKind.EXACT
    assert exact.matched_path == "/p/movie.mov"


def test_the_earliest_of_several_equally_near_images_still_wins() -> None:
    """Ordering semantics, checked rather than assumed.

    The replaced loop updated only on `distance < best_distance`, strictly, so among equally
    near candidates the first registered won. `np.argmin` returns the first position holding
    the minimum, which is the same rule - but only by coincidence of choosing `argmin` over
    any other reduction, so it is pinned.
    """
    base = 0x0F0F0F0F0F0F0F0F
    index = DedupIndex(threshold=T)
    for name in ("first", "second", "third"):
        index.register(f"/p/{name}.jpg", f"sha-{name}", _hex(base ^ 0b11))

    match = index.check(None, _hex(base))

    assert match is not None
    assert match.matched_path == "/p/first.jpg"
    assert match.distance == 2


def test_a_nearer_image_registered_later_still_wins() -> None:
    """The other half of the ordering rule: earliest wins only among *equals*."""
    base = 0x0F0F0F0F0F0F0F0F
    index = DedupIndex(threshold=T)
    index.register("/p/far.jpg", "sha-far", _hex(base ^ 0b1111))
    index.register("/p/near.jpg", "sha-near", _hex(base ^ 0b1))

    match = index.check(None, _hex(base))

    assert match is not None
    assert match.matched_path == "/p/near.jpg"
    assert match.distance == 1


def test_growing_past_the_initial_capacity_keeps_every_entry_findable() -> None:
    """The doubling buffer is the one place a file could be silently dropped from the index.

    A grow that copied the wrong slice would lose early images - and a lost image is not an
    error, it is a near-duplicate that stops being recognised. Probes the first, last and a
    middle entry across two doublings.
    """
    index = DedupIndex(threshold=T)
    count = 2_500  # past the 1,024 initial capacity, twice
    for i in range(count):
        index.register(f"/p/{i}.jpg", f"sha-{i}", _hex(i << 8))

    assert index._count == count
    for i in (0, 1, 1_023, 1_024, 2_047, 2_048, count - 1):
        match = index.check(None, _hex(i << 8))
        assert match is not None, f"entry {i} fell out of the index"
        assert match.matched_path == f"/p/{i}.jpg"
        assert match.distance == 0


def test_a_hash_wider_than_the_packed_word_is_refused_loudly() -> None:
    """A future algorithm at a larger `hash_size` must not be silently truncated to 64 bits."""
    with pytest.raises(ValueError, match="wider than 64 bits"):
        pack_hash("f" * 17)


def test_matching_a_realistic_library_is_fast_enough_to_be_a_regression_guard() -> None:
    """20,000 images, accumulating - 200,000,000 pair comparisons - inside 10 seconds.

    **Chosen so the bound cannot flake and cannot pass by accident.** The replaced
    implementation ran at 263-269 ns/pair measured, so it needed ~53 s here on the
    development machine and more on any CI runner: it fails this bound by 5x or worse. The
    packed path takes well under a second locally, so the 10 s ceiling leaves an order of
    magnitude of headroom for the slowest lane (Windows, consistently the slowest of the
    four) before it could false-alarm. Anything between those two numbers is a real
    regression, which is the only thing a timing assertion should ever be asked to catch.
    """
    rng = random.Random(99)
    hashes = [_hex(rng.getrandbits(HASH_BITS)) for _ in range(20_000)]

    index = DedupIndex(threshold=T)
    started = time.perf_counter()
    for i, value in enumerate(hashes):
        index.check(None, value)
        index.register(f"/p/{i}.jpg", f"sha-{i}", value)
    elapsed = time.perf_counter() - started

    assert index._count == 20_000, "fixture check: every image was indexed"
    assert elapsed < 10.0, (
        f"perceptual matching took {elapsed:.1f}s for 20,000 images; the per-pair comparison "
        f"has regressed to something like the hex-parsing loop this replaced"
    )
