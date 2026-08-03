"""Exact duplicates without look-alikes: the cheap duplicate tier, run on its own.

The size pre-filter spares SHA-256 for most files, so exact-duplicate detection reads only the
size-colliding minority. The *perceptual* hash has no such filter -- it decodes every image --
so bundling the two prices the cheap answer at the expensive one's cost. Splitting them is the
whole value of Analyze's tier 2a.

**The guard that matters is the cache one.** A run that computes only some of a file's hashes
must never record that: `perceptual` is nullable and means both "not an image" and "not
computed", so a partial row returns as a hit and silently deletes near-duplicate detection.
`compute_hashes` refuses the combination outright rather than trusting callers to remember.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image
from truestill_core.hash_cache import HashCache
from truestill_core.scan import compute_hashes


def _photo(path: Path, tint: int) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (48, 32), (tint, 40, 90)).save(path, "JPEG")
    return path


@pytest.fixture
def twins(tmp_path: Path) -> list[Path]:
    """Two byte-identical files plus one unique - so the size pre-filter has work to do."""
    first = _photo(tmp_path / "a.jpg", 10)
    second = tmp_path / "b.jpg"
    second.write_bytes(first.read_bytes())
    third = _photo(tmp_path / "c.jpg", 200)
    return [first, second, third]


def test_exact_duplicates_are_still_found_without_the_perceptual_hash(twins: list[Path]) -> None:
    """Tier 2a's whole promise: identical bytes are still identified."""
    hashes = compute_hashes(twins, perceptual=False)

    first, second, third = twins
    assert hashes[first].sha256 is not None
    assert hashes[first].sha256 == hashes[second].sha256
    assert hashes[third].sha256 != hashes[first].sha256


def test_no_perceptual_hash_is_computed(twins: list[Path]) -> None:
    """Asserted on the RESULT, not on a flag - a flag that stopped being honoured would pass."""
    hashes = compute_hashes(twins, perceptual=False)
    assert all(h.perceptual is None for h in hashes.values())


def test_the_default_still_computes_both(twins: list[Path]) -> None:
    """Cry-wolf: every existing caller must be unaffected."""
    hashes = compute_hashes(twins)
    assert all(h.perceptual is not None for h in hashes.values())
    assert hashes[twins[0]].sha256 is not None


def test_skipping_the_perceptual_hash_with_a_writable_cache_is_refused(
    twins: list[Path], tmp_path: Path
) -> None:
    """The poisoning combination is refused at the seam, not documented and hoped for.

    A partially-hashed row written to a writable cache would return as a hit on the next
    organize preview and silently remove near-duplicate detection for those files. Making it
    raise means the mistake is impossible to ship rather than merely discouraged.
    """
    with HashCache(tmp_path / "c.cache.sqlite") as cache:
        assert cache.writable
        with pytest.raises(ValueError, match="read-only"):
            compute_hashes(twins, perceptual=False, cache=cache)


def test_skipping_the_perceptual_hash_with_a_read_only_cache_is_allowed(
    twins: list[Path], tmp_path: Path
) -> None:
    """Cry-wolf for the refusal: the safe combination must not be blocked as well."""
    cache_path = tmp_path / "c.cache.sqlite"
    with HashCache(cache_path) as writable:
        assert writable.enabled

    with HashCache(cache_path, writable=False) as cache:
        hashes = compute_hashes(twins, perceptual=False, cache=cache)

    assert all(h.perceptual is None for h in hashes.values())


def test_the_full_pass_with_a_writable_cache_is_untouched(
    twins: list[Path], tmp_path: Path
) -> None:
    """The ordinary organize path: both hashes, writable cache, no refusal."""
    with HashCache(tmp_path / "c.cache.sqlite") as cache:
        hashes = compute_hashes(twins, cache=cache)
    assert all(h.perceptual is not None for h in hashes.values())
