"""Two-tier duplicate detection.

For each incoming file, in this order:

1. **Exact** -- SHA-256 equal to something already seen. First and cheapest.
2. **Perceptual** -- dHash within a Hamming-distance threshold of something already seen.

"Already seen" spans both the current run and prior runs: the index is seeded from the
catalog, so a re-run recognises files it processed before and a forwarded copy of a photo
backed up last month is caught against that month's original. Only files matching neither
tier are considered genuinely new.

Perceptual lookup is a linear scan (a 64-bit XOR + popcount per known image), which makes the
matching pass O(n^2) in the number of images. Measured on the curve in ``docs/PERFORMANCE.md``
§3: **0.72 s at 2,275 images, 13.5 s at 10,000** (AMD Ryzen 7 4800H, Linux, Python 3.13). At
10,000 it is no longer the cheapest stage in a cold preview - that is exactly why
:data:`LINEAR_SCAN_ALARM` fires there. A BK-tree today would still be machinery bought before
most libraries need it, so the scan stays and the alarm announces the crossing to whoever
actually hits it rather than leaving the trigger only in a document. The swap, when it is due,
fits behind this module's interface unchanged.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable

from truestill_core.hashing import hamming_distance
from truestill_core.models import DuplicateKind, DuplicateMatch

_log = logging.getLogger(__name__)

#: Index size at which the linear perceptual scan stops being negligible. Chosen from the
#: measured curve in `docs/PERFORMANCE.md`: quadratic growth means the cost past here rises
#: 4x for every doubling, so this is the last comfortable point, not the first painful one.
LINEAR_SCAN_ALARM = 10_000


class DedupIndex:
    """Accumulating index of known file hashes, queried before each file is accepted."""

    def __init__(self, threshold: int) -> None:
        self._threshold = threshold
        self._by_sha: dict[str, str] = {}
        # Parallel lists, only holding image (perceptual-hashable) entries.
        self._phash_paths: list[str] = []
        self._phash_values: list[str] = []
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
            index.register(path, sha256, perceptual, origin="catalog")
        return index

    def check(self, sha256: str | None, perceptual: str | None) -> DuplicateMatch | None:
        """Return the strongest duplicate match, or ``None`` if the file is new.

        ``sha256`` is ``None`` for a unique-size file the pre-filter chose not to hash; such
        a file cannot be an exact duplicate, so the exact tier is simply skipped.
        """
        existing = self._by_sha.get(sha256) if sha256 is not None else None
        if existing is not None:
            return DuplicateMatch(
                kind=DuplicateKind.EXACT,
                matched_path=existing,
                origin=self._origin_of(existing),
            )

        if perceptual is not None:
            best_path: str | None = None
            best_distance = self._threshold + 1
            for path, value in zip(self._phash_paths, self._phash_values, strict=True):
                distance = hamming_distance(perceptual, value)
                if distance <= self._threshold and distance < best_distance:
                    best_path, best_distance = path, distance
            if best_path is not None:
                return DuplicateMatch(
                    kind=DuplicateKind.PERCEPTUAL,
                    matched_path=best_path,
                    origin=self._origin_of(best_path),
                    distance=best_distance,
                )

        return None

    def register(
        self,
        path: str,
        sha256: str | None,
        perceptual: str | None,
        *,
        origin: str = "run",
    ) -> None:
        """Add a file's hashes so later files can be compared against it.

        A ``None`` sha (unique-size, unhashed) is not indexed for exact matching -- there is
        nothing it could exact-match -- but its perceptual hash still participates.
        """
        if sha256 is not None:
            self._by_sha.setdefault(sha256, path)
        if perceptual is not None:
            self._phash_paths.append(path)
            self._phash_values.append(perceptual)
            if len(self._phash_values) == LINEAR_SCAN_ALARM:
                # Once per index, on the crossing itself -- so it costs one integer comparison
                # per registration and reaches the person who hit it, not the person reading
                # the docs.
                _log.warning(
                    "perceptual matching is now the slow path at %d images -- known, planned "
                    "(see docs/PERFORMANCE.md)",
                    LINEAR_SCAN_ALARM,
                )
        if origin == "catalog":
            self._catalog_paths.add(path)

    def _origin_of(self, path: str) -> str:
        return "catalog" if path in self._catalog_paths else "run"
