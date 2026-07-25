"""Concurrent hashing pass with a byte-size pre-filter.

The bottleneck of a bulk dedup scan is keeping disk and CPU busy across the whole library,
not the speed of one hash call. Two levers, both here:

* **Size pre-filter** -- a file can only be an *exact* duplicate of another file with the
  identical byte size. So SHA-256 is computed only for files whose size collides with
  another file in this scan *or* with a size already recorded in the catalog (the latter
  keeps cross-run exact-dedup correct). Unique-size files skip the full-file read entirely;
  their hash is computed lazily only if they are later uploaded. This removes far more work
  than any change of hash algorithm -- especially for large videos, which are expensive to
  read in full.
* **Worker pool** -- files are hashed concurrently. SHA-256 (``hashlib``) and Pillow's
  decode both release the GIL during their C work, so a thread pool already overlaps I/O
  and hashing; a process pool sidesteps the GIL entirely at the cost of IPC. The right
  choice is machine-dependent, so it is selectable and benchmarked, not assumed.

SHA-256 is the one and only content hash (hardware-accelerated via OpenSSL on modern CPUs).
No BLAKE3, no algorithm setting, one catalog column.
"""

from __future__ import annotations

import os
import threading
from collections import Counter
from collections.abc import Sequence
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Literal

from vaeon_core.hashing import perceptual_hash, sha256_file
from vaeon_core.models import FileHashes
from vaeon_core.progress import ProgressCallback

PoolKind = Literal["thread", "process"]

#: Default worker count. Hashing is largely I/O plus GIL-releasing C, so a small multiple
#: of the core count keeps the disk queue full without thrashing.
DEFAULT_WORKERS = os.cpu_count() or 4


def _hash_one(args: tuple[str, bool]) -> tuple[str, str | None, str | None]:
    """Worker body: return ``(path, sha256_or_None, perceptual_or_None)``.

    Module-level and picklable so it works under a ProcessPoolExecutor. SHA-256 is computed
    only when ``need_sha`` is set (the size pre-filter's decision); perceptual hashing is
    attempted for every file and simply returns None for non-images.
    """
    path_str, need_sha = args
    path = Path(path_str)
    sha = sha256_file(path) if need_sha else None
    perceptual = perceptual_hash(path)
    return path_str, sha, perceptual


def _sizes(paths: Sequence[Path]) -> dict[Path, int]:
    sizes: dict[Path, int] = {}
    for path in paths:
        try:
            sizes[path] = path.stat().st_size
        except OSError:
            sizes[path] = -1
    return sizes


def _needs_sha(sizes: dict[Path, int], catalog_sizes: frozenset[int]) -> set[Path]:
    """Files that must be SHA-256'd: size shared within the scan, or known to the catalog."""
    counts = Counter(sizes.values())
    return {path for path, size in sizes.items() if counts[size] > 1 or size in catalog_sizes}


def compute_hashes(
    paths: Sequence[Path],
    *,
    catalog_sizes: frozenset[int] = frozenset(),
    pool: PoolKind = "thread",
    workers: int = DEFAULT_WORKERS,
    progress: ProgressCallback | None = None,
    cancel: threading.Event | None = None,
) -> dict[Path, FileHashes]:
    """Hash ``paths`` concurrently, applying the size pre-filter.

    Returns a mapping from path to :class:`FileHashes`, where ``sha256`` is ``None`` for a
    unique-size file that was deliberately not hashed. ``progress`` is called ``(done, total)``
    as files finish; ``cancel`` stops early (pending files are cancelled, results are partial).
    """
    if not paths:
        return {}

    sizes = _sizes(paths)
    need_sha = _needs_sha(sizes, catalog_sizes)
    jobs = [(str(path), path in need_sha) for path in paths]

    executor_cls = ProcessPoolExecutor if pool == "process" else ThreadPoolExecutor
    results: dict[Path, FileHashes] = {}
    total, done = len(jobs), 0
    with executor_cls(max_workers=max(1, workers)) as executor:
        futures = [executor.submit(_hash_one, job) for job in jobs]
        for future in as_completed(futures):
            if cancel is not None and cancel.is_set():
                for pending in futures:
                    pending.cancel()
                break
            path_str, sha, perceptual = future.result()
            results[Path(path_str)] = FileHashes(sha256=sha, perceptual=perceptual)
            done += 1
            if progress is not None:
                progress(done, total)
    return results
