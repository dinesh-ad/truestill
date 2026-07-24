"""Benchmark thread vs process pool for the concurrent hashing scan.

Not a test (no assertions) -- a decision aid. Run:

    uv run python scripts/benchmark_hashing.py

It times the real 8-file test set (if present) and a generated synthetic set of a few
thousand files of varied sizes, hashing with each pool type and a range of worker counts.
"""

from __future__ import annotations

import os
import random
import shutil
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from vaeon.scan import compute_hashes

REAL_SET = Path.home() / "gphotos-staging" / "takeout-test" / "extracted" / "takeout-test"


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


def _time(paths: list[Path], *, pool: str, workers: int) -> float:
    start = time.perf_counter()
    compute_hashes(paths, pool=pool, workers=workers)  # type: ignore[arg-type]
    return time.perf_counter() - start


def _bench(label: str, paths: list[Path]) -> None:
    cores = os.cpu_count() or 4
    print(f"\n=== {label}: {len(paths)} files ===")
    print(f"{'pool':<9}{'workers':<9}{'seconds':<10}")
    for pool in ("thread", "process"):
        for workers in (1, cores, cores * 2):
            # warm the page cache identically, then time
            best = min(_time(paths, pool=pool, workers=workers) for _ in range(2))
            print(f"{pool:<9}{workers:<9}{best:<10.4f}")


def main() -> None:
    if REAL_SET.is_dir():
        real = [p for p in sorted(REAL_SET.iterdir()) if p.is_file()]
        if real:
            _bench("real test set", real)

    tmp = Path(tempfile.mkdtemp(prefix="vaeon-bench-"))
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
