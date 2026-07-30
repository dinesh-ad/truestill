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
No BLAKE3, no algorithm setting, one catalog column (see ``DECISIONS.md`` D8).
"""

from __future__ import annotations

import os
import threading
from collections import Counter
from collections.abc import Sequence
from concurrent.futures import (
    BrokenExecutor,
    Future,
    ProcessPoolExecutor,
    ThreadPoolExecutor,
    as_completed,
)
from pathlib import Path
from typing import Literal

from truestill_core.hash_cache import HashCache
from truestill_core.hashing import perceptual_hash, sha256_file
from truestill_core.models import FileHashes
from truestill_core.progress import Phase, Progress, ProgressCallback

PoolKind = Literal["thread", "process"]

#: Default worker count. Hashing is largely I/O plus GIL-releasing C, so a small multiple
#: of the core count keeps the disk queue full without thrashing.
DEFAULT_WORKERS = os.cpu_count() or 4


def _hash_one(args: tuple[str, bool]) -> tuple[str, str | None, str | None]:
    """Worker body: return ``(path, sha256_or_None, perceptual_or_None)``.

    Module-level and picklable so it works under a ProcessPoolExecutor. SHA-256 is computed
    only when ``need_sha`` is set (the size pre-filter's decision); perceptual hashing is
    attempted for every file and simply returns None for non-images. An unreadable path
    returns ``(path, None, None)`` so one bad file cannot abort the batch.
    """
    path_str, need_sha = args
    path = Path(path_str)
    try:
        sha = sha256_file(path) if need_sha else None
        perceptual = perceptual_hash(path)
    except OSError:
        return path_str, None, None
    return path_str, sha, perceptual


def _take_hash_result(
    future: Future[tuple[str, str | None, str | None]],
) -> tuple[str, str | None, str | None] | None:
    """Unpack one worker future, or ``None`` when the process pool itself has died."""
    try:
        return future.result()
    except BrokenExecutor:
        return None


def _mtime_ns(path: Path) -> int:
    """Modification time in integer nanoseconds -- exact, so no float comparison is needed.

    Used only to answer "has this file changed since we hashed it". It never influences where
    a file is placed; that is `dates.resolve_capture_datetime`, which does not read the
    filesystem at all (`IMPLEMENTATION_STANDARDS.md` §1).
    """
    try:
        return path.stat().st_mtime_ns
    except OSError:
        return -1


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


def _run_hash_jobs(
    to_hash: list[Path],
    need_sha: set[Path],
    sizes: dict[Path, int],
    *,
    pool: PoolKind,
    workers: int,
    progress: ProgressCallback | None,
    cancel: threading.Event | None,
    cache: HashCache | None,
    results: dict[Path, FileHashes],
    done: int,
    total: int,
) -> None:
    """Hash ``to_hash`` into ``results``, defending one unreadable file and a dead process pool."""
    jobs = [(str(path), path in need_sha) for path in to_hash]
    executor_cls = ProcessPoolExecutor if pool == "process" else ThreadPoolExecutor
    with executor_cls(max_workers=max(1, workers)) as executor:
        futures = [executor.submit(_hash_one, job) for job in jobs]
        for future in as_completed(futures):
            if cancel is not None and cancel.is_set():
                for pending in futures:
                    pending.cancel()
                break
            got = _take_hash_result(future)
            if got is None:
                # Pool death is not an OSError; abandon remaining work with empty hashes.
                for path in to_hash:
                    results.setdefault(path, FileHashes(None, None))
                break
            path_str, sha, perceptual = got
            path = Path(path_str)
            hashes = FileHashes(sha256=sha, perceptual=perceptual)
            results[path] = hashes
            if cache is not None and (sha is not None or perceptual is not None):
                cache.put(path, sizes.get(path, -1), _mtime_ns(path), hashes)
            done += 1
            if progress is not None:
                progress(Progress(done, total, Phase.HASHING, Path(path_str).name))


def compute_hashes(
    paths: Sequence[Path],
    *,
    catalog_sizes: frozenset[int] = frozenset(),
    pool: PoolKind = "thread",
    workers: int = DEFAULT_WORKERS,
    progress: ProgressCallback | None = None,
    cancel: threading.Event | None = None,
    cache: HashCache | None = None,
) -> dict[Path, FileHashes]:
    """Hash ``paths`` concurrently, applying the size pre-filter.

    Returns a mapping from path to :class:`FileHashes`, where ``sha256`` is ``None`` for a
    unique-size file that was deliberately not hashed. ``progress`` is called ``(done, total)``
    as files finish; ``cancel`` stops early (pending files are cancelled, results are partial).

    ``cache`` skips files whose size and mtime are unchanged since they were last hashed. It
    can only remove work: a miss, a mismatch or a broken cache all mean hashing from scratch,
    and the returned hashes are identical either way.
    """
    if not paths:
        return {}

    sizes = _sizes(paths)
    # Computed over *all* paths, cached or not: a collision is a property of the batch, and
    # dropping cached files from the tally would silently change who needs a SHA-256.
    need_sha = _needs_sha(sizes, catalog_sizes)

    results: dict[Path, FileHashes] = {}
    total, done = len(paths), 0
    to_hash: list[Path] = []
    if cache is None:
        to_hash = list(paths)
    else:
        # Looked up here rather than inside the worker: the worker stays a pure, picklable
        # function that a ProcessPoolExecutor can run, and the cache stays single-threaded.
        for path in paths:
            hit = cache.get(path, sizes.get(path, -1), _mtime_ns(path), need_sha=path in need_sha)
            if hit is None:
                to_hash.append(path)
            else:
                results[path] = hit
        done = len(results)
        if progress is not None and done:
            # Report the hits as done in one step -- a run that is entirely cached should show
            # a completed phase instantly rather than a bar that never moves.
            progress(Progress(done, total, Phase.HASHING, ""))

    _run_hash_jobs(
        to_hash,
        need_sha,
        sizes,
        pool=pool,
        workers=workers,
        progress=progress,
        cancel=cancel,
        cache=cache,
        results=results,
        done=done,
        total=total,
    )
    return results
