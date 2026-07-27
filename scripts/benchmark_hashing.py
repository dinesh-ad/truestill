"""Benchmark thread vs process pool for the concurrent hashing scan.

Not a test (no assertions) -- a decision aid behind the `pool` default recorded in
`docs/IMPLEMENTATION_STANDARDS.md` §8. Run:

    uv run python scripts/benchmark_hashing.py

It times a generated synthetic set of a few thousand files of varied sizes -- and the real
corpus too, if `TRUESTILL_CORPUS` points at one -- hashing with each pool type across a range
of worker counts.
"""

from __future__ import annotations

import os
import random
import shutil
import tempfile
import time
from pathlib import Path

from truestill_core.scan import PoolKind, compute_hashes

#: The external corpus is machine-specific and deliberately not recorded in the repo, so it is
#: named by environment variable (`docs/PROJECT_STATUS.md` §6) and simply skipped when unset.
#: It is read-only here: this script hashes files and writes nothing to them.
_CORPUS_ENV = "TRUESTILL_CORPUS"


def _make_synthetic(root: Path, count: int, *, seed: int = 1) -> list[Path]:
    """Create ``count`` files with a mix of unique and colliding sizes."""
    rng = random.Random(seed)
    paths: list[Path] = []
    for i in range(count):
        # ~40% share one of a few common sizes (exercises the pre-filter + real hashing),
        # the rest get unique-ish sizes (exercises the skip path).
        size = rng.choice([4096, 8192, 16384]) if i % 5 < 2 else rng.randint(1000, 500_000)
        path = root / f"f{i:05d}.bin"
        path.write_bytes(rng.randbytes(size))
        paths.append(path)
    return paths


def _time(paths: list[Path], *, pool: PoolKind, workers: int) -> float:
    start = time.perf_counter()
    compute_hashes(paths, pool=pool, workers=workers)
    return time.perf_counter() - start


def _bench(label: str, paths: list[Path]) -> None:
    cores = os.cpu_count() or 4
    print(f"\n=== {label}: {len(paths)} files ===")
    print(f"{'pool':<9}{'workers':<9}{'seconds':<10}")
    pools: tuple[PoolKind, ...] = ("thread", "process")
    for pool in pools:
        for workers in (1, cores, cores * 2):
            # warm the page cache identically, then time
            best = min(_time(paths, pool=pool, workers=workers) for _ in range(2))
            print(f"{pool:<9}{workers:<9}{best:<10.4f}")


def main() -> None:
    corpus = os.environ.get(_CORPUS_ENV)
    if corpus:
        root = Path(corpus)
        real = [p for p in sorted(root.rglob("*")) if p.is_file()] if root.is_dir() else []
        if real:
            _bench(f"real corpus ({root})", real)
        else:
            print(f"{_CORPUS_ENV}={corpus} is not a directory with files in it; skipping")

    tmp = Path(tempfile.mkdtemp(prefix="truestill-bench-"))
    try:
        for count in (2000, 5000):
            subdir = tmp / str(count)
            subdir.mkdir(parents=True, exist_ok=True)
            paths = _make_synthetic(subdir, count)
            _bench(f"synthetic ({count})", paths)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
