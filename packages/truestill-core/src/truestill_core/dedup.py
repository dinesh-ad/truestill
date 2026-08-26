"""Two-tier duplicate detection.

For each incoming file, in this order:

1. **Exact** -- SHA-256 equal to something already seen. First and cheapest.
2. **Perceptual** -- dHash within a Hamming-distance threshold of something already seen.

"Already seen" spans both the current run and prior runs: the index is seeded from the
catalog, so a re-run recognises files it processed before and a forwarded copy of a photo
backed up last month is caught against that month's original. Only files matching neither
tier are considered genuinely new.

Perceptual lookup compares one incoming hash against every image already known, which makes
the matching pass O(n^2) in the number of images. **That is unchanged and is not the thing
that was expensive.** The comparison used to be
``(int(hex_a, 16) ^ int(hex_b, 16)).bit_count()`` per pair, so every pair re-parsed two hex
strings into Python integers: measured **263-269 ns/pair, flat in n**, of which the XOR is
free and the parsing is the entire bill. The curve in ``docs/PERFORMANCE.md`` §3 is that
implementation: **0.685 s at 2,275 images, 13.709 s at 10,000** (median of 9 and 5 runs
respectively; AMD Ryzen 7 4800H, Linux, Python 3.13).

**The hashes are now packed to ``uint64`` once, at registration, and compared with one
vectorised XOR + ``np.bitwise_count`` per incoming file.** Same O(n^2) pair count, ~300x less
work per pair, because the parsing happens once per image instead of once per pair and the
popcount is a hardware instruction. Measured on the same machine: **147 s -> 0.5 s at 33,457
images (291x), 2,996 s -> 8.9 s at 150,000 (338x)**.

**Deliberately one-vs-many, never all-pairs-at-once.** Matching is incremental - one new hash
against those already seen - so the full pairwise matrix is never needed, and building it
would cost ~560M entries at 33,457 images and ~11.2B at 150,000. ``scipy``'s ``pdist`` and
``sklearn``'s ``pairwise_distances`` both materialise that matrix *and* work on unpacked
vectors (64 elements per hash rather than one integer), which is why neither is used here.

**No BK-tree** (`SHIPPED.md` ``(v)``, closed on measurement). At threshold 5 a BK-tree prunes
only ~85% of the index per query and loses to this by 89x at 150,000 - the reason is in that
entry and it is a property of the geometry, not of any implementation.
"""

from __future__ import annotations

from collections.abc import Iterable

import numpy as np

from truestill_core.models import DuplicateKind, DuplicateMatch, DuplicateOrigin

#: Both perceptual algorithms are built at ``hash_size=8`` (`hashing._HASH_SIDE`), so every
#: stored hash is exactly 64 bits. That is what lets one ``uint64`` be the whole
#: representation of an image here, and it is asserted rather than assumed on the way in.
HASH_BITS = 64

#: Starting length of the packed array, doubled whenever it fills. Registration stays
#: amortised O(1); the transient cost is one copy of the current contents. At 150,000 images
#: the array holds 1.2 MB, and at most 2.4 MB in the moment before a grow settles - less than
#: the hex strings it replaced, which cost roughly 11 MB at the same count.
_INITIAL_CAPACITY = 1024


def pack_hash(perceptual: str) -> np.uint64:
    """A hex perceptual hash as the single unsigned integer the matcher compares.

    Rejecting anything wider than 64 bits is the point of the check: the previous per-pair
    comparison ran on Python integers and would have silently accepted a wider hash from some
    future algorithm, comparing it correctly while everything vectorised beside it did not.
    """
    value = int(perceptual, 16)
    if value >> HASH_BITS:
        message = (
            f"perceptual hash {perceptual!r} is wider than {HASH_BITS} bits; the packed index "
            f"holds one uint64 per image and cannot represent it"
        )
        raise ValueError(message)
    return np.uint64(value)


def carries_no_signal(perceptual: str, threshold: int) -> bool:
    """Whether a hash carries less distinguishing information than ``threshold`` tolerates. `(ahq)`

    🔑 **DERIVED, NEVER PICKED.** The Hamming distance from a hash to the all-zero hash **is** that
    hash's bit population, so *"within the matching threshold of all-zero"* is exactly
    ``bit_count(h) <= threshold``. The floor is not a new constant - **it is the threshold**,
    whatever the caller sets. A number nobody measured becoming a rule is a shape this repo has
    filed before; this one follows from the hash's own definition.

    **Both poles, because the mirror case is equally degenerate.** dHash compares each pixel with
    its right neighbour, so a gradient-free image gives all zeros and a monotonic left-to-right
    gradient gives all ones. Both carry no *distinguishing* structure and both cluster. Hence
    ``min(popcount, 64 - popcount)``, not ``popcount``.

    ⚠ **What this costs, measured rather than assumed away.** On a real 10,138-image library it
    excludes **97 files (0.96%)**, 13 of them real photographs - and among those,
    ``IMG_20150901_123909`` and ``IMG_20150901_123912``, three seconds apart, pair today at
    distance 3. **That pairing is not lost evidence; it was never evidence.** Those two hashes
    carry **four set bits each**, so a distance of 3 means they agree on one or two bits out of
    sixty-four. Agreement that thin is the absence of signal, not the presence of similarity - the
    pair is right for a reason the hash cannot see, and the hash should not take the credit.

    ⚠ **Nobody in the field does this**, checked: no competitor filters on hash entropy or
    variance, and the literature discusses threshold tuning and nothing else. Unprecedented raises
    the bar rather than lowering it, which is why this is derived, costs no decode and no column,
    and is one predicate with one home.

    ⚠ **Assumes a well-formed hash and raises on anything else**, via :func:`pack_hash` - which is
    that function's own rule and not softened here. The stats path now parses every distinct hash
    where it used to compare strings, so a hand-corrupted `files.perceptual` would raise where it
    once rendered. **Left strict deliberately**: the product writes only `imagehash` output, and a
    tolerant branch for a value it cannot produce is a compat path. Two test fixtures carrying
    fake values were corrected rather than accommodated.
    """
    population = int(pack_hash(perceptual)).bit_count()
    return min(population, HASH_BITS - population) <= threshold


class DedupIndex:
    """Accumulating index of known file hashes, queried before each file is accepted."""

    def __init__(self, threshold: int) -> None:
        self._threshold = threshold
        self._by_sha: dict[str, str] = {}
        # Parallel by position: `_phash_paths[i]` owns `_packed[i]`. Only images
        # (perceptual-hashable files) appear in either.
        self._phash_paths: list[str] = []
        self._packed: np.ndarray = np.empty(_INITIAL_CAPACITY, dtype=np.uint64)
        self._count = 0
        # Paths that came from a prior run, so matches can be labelled run vs catalog.
        self._catalog_paths: set[str] = set()

    @classmethod
    def from_catalog_rows(
        cls,
        rows: Iterable[tuple[str, str, str | None]],
        threshold: int,
    ) -> DedupIndex:
        """Seed an index from ``(path, sha256, perceptual)`` rows, e.g. from the catalog."""
        index = cls(threshold)
        for path, sha256, perceptual in rows:
            index.register(path, sha256, perceptual, origin=DuplicateOrigin.CATALOG)
        return index

    def check(self, sha256: str | None, perceptual: str | None) -> DuplicateMatch | None:
        """Return the strongest duplicate match, or ``None`` if the file is new.

        ``sha256`` is ``None`` for a unique-size file the pre-filter chose not to hash; such
        a file cannot be an exact duplicate, so the exact tier is simply skipped.

        ``perceptual`` is ``None`` for a video, an audio file or anything Pillow could not
        decode. **Those must never reach the packed comparison.** A missing hash is not the
        number zero, and packing it as one would make every file without a perceptual hash a
        near-duplicate of every other - the whole library collapsing into one match, silently.

        ⚠ **AND THE SENTENCE ABOVE DESCRIBED A FAILURE THIS GUARD COULD NOT SEE.** `(ahq)` It
        tested **provenance** - ``is None``, "no hash exists" - and never **value**. A photograph
        of a flat surface produces an *honest* all-zero hash: `perceptual_hash` opened it, decoded
        it, and returned `"0000000000000000"`. That is not ``None``, so it walked straight past
        this check and did exactly what the paragraph warns of - measured at **89 files within the
        default threshold of the all-zero hash on one real library**, mutually near-duplicate by
        construction. The synthetic route was closed and the photographic one was open.
        :func:`carries_no_signal` is the value half, and it is why the two are now tested together.
        """
        existing = self._by_sha.get(sha256) if sha256 is not None else None
        if existing is not None:
            return DuplicateMatch(
                kind=DuplicateKind.EXACT,
                matched_path=existing,
                origin=self._origin_of(existing),
            )

        if (
            perceptual is not None
            and not carries_no_signal(perceptual, self._threshold)
            and self._count
        ):
            known = self._packed[: self._count]
            distances = np.bitwise_count(np.bitwise_xor(known, pack_hash(perceptual)))
            # `argmin` returns the FIRST position holding the minimum, and a match exists
            # exactly when that minimum is within the threshold. That is the same answer the
            # per-pair loop gave: it kept a candidate only on `distance < best_distance`,
            # strictly, so the earliest of several equally-near images won there too. The
            # results are identical, not merely similar - which matters, because this decides
            # what gets flagged as a near-duplicate across an entire library.
            nearest = int(np.argmin(distances))
            best_distance = int(distances[nearest])
            if best_distance <= self._threshold:
                return DuplicateMatch(
                    kind=DuplicateKind.PERCEPTUAL,
                    matched_path=self._phash_paths[nearest],
                    origin=self._origin_of(self._phash_paths[nearest]),
                    distance=best_distance,
                )

        return None

    def register(
        self,
        path: str,
        sha256: str | None,
        perceptual: str | None,
        *,
        origin: DuplicateOrigin = DuplicateOrigin.RUN,
    ) -> None:
        """Add a file's hashes so later files can be compared against it.

        A ``None`` sha (unique-size, unhashed) is not indexed for exact matching -- there is
        nothing it could exact-match -- but its perceptual hash still participates. A ``None``
        perceptual hash is not indexed at all: see :meth:`check`.

        ⚠ **Nor is one that carries no signal** (:func:`carries_no_signal`). Refused at
        REGISTRATION rather than at comparison, deliberately: a flat frame must neither match nor
        be matched, and excluding it here does both with one test. It keeps the hash it honestly
        computed - the exclusion is a fact about the comparison, not about the file.
        """
        if sha256 is not None:
            self._by_sha.setdefault(sha256, path)
        if perceptual is not None and not carries_no_signal(perceptual, self._threshold):
            if self._count == self._packed.size:
                grown = np.empty(self._packed.size * 2, dtype=np.uint64)
                grown[: self._count] = self._packed
                self._packed = grown
            self._packed[self._count] = pack_hash(perceptual)
            self._count += 1
            self._phash_paths.append(path)
        if origin is DuplicateOrigin.CATALOG:
            self._catalog_paths.add(path)

    def _origin_of(self, path: str) -> DuplicateOrigin:
        if path in self._catalog_paths:
            return DuplicateOrigin.CATALOG
        return DuplicateOrigin.RUN
