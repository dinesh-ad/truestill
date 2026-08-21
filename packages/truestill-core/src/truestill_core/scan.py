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

import errno
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
from dataclasses import replace
from pathlib import Path
from typing import Literal

from truestill_core import decode_noise
from truestill_core.hash_cache import HashCache
from truestill_core.hashing import perceptual_hash, sha256_file
from truestill_core.models import FileHashes, UnreadableReason
from truestill_core.progress import Phase, Progress, ProgressCallback

PoolKind = Literal["thread", "process"]

#: Default worker count. Hashing is largely I/O plus GIL-releasing C, so a small multiple
#: of the core count keeps the disk queue full without thrashing.
DEFAULT_WORKERS = os.cpu_count() or 4


#: One worker's answer: ``(path, sha256, perceptual, why_it_could_not_be_read)``.
#: ``(path, sha256, perceptual, unreadable, library_warnings)``.
#:
#: ⚠ The fifth field is a **sum contribution, never a per-file fact** - see
#: `decode_noise.take_warnings`. It rides the return value because that is the only channel a
#: `ProcessPoolExecutor` child has back to the parent; under a thread pool the split between
#: tasks is arbitrary and only the total is ever read. `(aev)`
HashJobResult = tuple[str, str | None, str | None, UnreadableReason | None, int]


def _reason_for(exc: OSError) -> UnreadableReason:
    """Classify a failed read into the wording the user will eventually see.

    Split by ``errno`` rather than by message text, for the reason §9 gives for error matching
    generally: a message is free to be reworded and an ``errno`` is not.
    """
    if isinstance(exc, PermissionError):
        return UnreadableReason.PERMISSION
    if isinstance(exc, FileNotFoundError):
        return UnreadableReason.MISSING
    if exc.errno == errno.EIO:
        return UnreadableReason.IO_ERROR
    return UnreadableReason.OTHER


def _probe_readability(paths: Sequence[Path]) -> dict[Path, UnreadableReason]:
    """Which of ``paths`` cannot be opened, and why. One ``open`` plus a 1-byte read each.

    **This runs over every path, and must keep doing so. Do not move it into the worker.**
    ``HashCache.get`` keys on size and mtime, both of which come from ``stat`` - and ``stat``
    SUCCEEDS on a file whose contents cannot be read. So a file that was readable when it was
    last hashed and is unreadable now returns a cache **hit**, never reaches :func:`_hash_one`,
    and would be invisible to a probe living there. On a repeat preview - the ordinary way
    someone uses this tool - that is the common path, not the corner one. Pinned by
    ``test_a_cached_file_that_became_unreadable_is_still_named``.

    **An explicit open, deliberately, and not a reason read off ``perceptual_hash``.** That
    function already opens every file, so the information looks free. It is not: Pillow raises
    a plain ``OSError`` for *"image file is truncated"* - a corrupt but perfectly readable
    JPEG. Deriving readability from Pillow's exception taxonomy would report a corruption
    problem as a permission problem, which sends the user after the wrong remedy. ``open``
    answers exactly the question asked and ``errno`` answers why. Pinned by
    ``test_a_corrupt_but_readable_image_is_not_called_unreadable``.

    Cost: **O(n)** syscalls and **no extra bytes read**. Measured 6.9 us/file against
    ``perceptual_hash`` at 58 us/file on the same pass (`docs/PERFORMANCE.md` §3.2).
    """
    unreadable: dict[Path, UnreadableReason] = {}
    for path in paths:
        try:
            with path.open("rb") as handle:
                handle.read(1)
        except OSError as exc:
            unreadable[path] = _reason_for(exc)
    return unreadable


def _hash_one(args: tuple[str, bool, bool]) -> HashJobResult:
    """Worker body: ``(path, sha256, perceptual, unreadable, library_warnings)``.

    Module-level and picklable so it works under a ProcessPoolExecutor. SHA-256 is computed
    only when ``need_sha`` is set (the size pre-filter's decision); perceptual hashing is
    attempted for every file and simply returns None for non-images. An unreadable path
    returns empty hashes so one bad file cannot abort the batch.

    The handler stays even though :func:`_probe_readability` has already opened every file,
    because it catches a **different** failure: opened fine, then failed at byte N. A 1-byte
    probe cannot see that, and a large file on a failing disk is exactly where it happens.
    """
    path_str, need_sha, need_perceptual = args
    path = Path(path_str)
    try:
        sha = sha256_file(path) if need_sha else None
    except OSError as exc:
        return path_str, None, None, _reason_for(exc), decode_noise.take_warnings()
    try:
        perceptual = perceptual_hash(path) if need_perceptual else None
    except OSError as exc:
        return path_str, None, None, _reason_for(exc), decode_noise.take_warnings()
    except Exception:  # EXEMPTION from a CONVENTION, argued in full below. `(aet)`
        # ⚠ **A DELIBERATE EXEMPTION FROM §4's "exceptions typed and specific - no bare except",
        # SCOPED TO THIS ONE CALL AND NOWHERE ELSE.** It is not a pattern to copy: the `sha256_file`
        # call above keeps its narrow `OSError`, because a plain byte read has a knowable failure
        # set. This one does not.
        #
        # ⚠ There is no `noqa` here because there is nothing to suppress: `BLE001` is not
        # enabled in this repo, so `except Exception` passes ruff silently. The rule being
        # bent is §4's PROSE - *"exceptions typed and specific - no bare except"* - which
        # means §5 governs it: a violation must be **explicit, commented and contained**,
        # written for the next engineer so no archaeology is needed. That is this comment,
        # and its absence would make the deviation invisible rather than merely unmarked.
        #
        # **The argument: the defect is a taxonomy that cannot be completed.** `perceptual_hash`
        # already catches `UnidentifiedImageError`, `OSError`, `ValueError` and
        # `DecompressionBombError` - a careful list. The first soak's format corpus escaped it
        # **eight times in two classes nobody would have listed**: `EOFError` from a truncated
        # HEIC, and `SyntaxError` - the *builtin* - which Pillow raises for a malformed PNG `zTXt`
        # chunk. Any one of the eight aborted a 1,428-file run with a traceback and no report.
        #
        # Widening the tuple would fix those eight and leave the ninth decoder to abort a run in
        # six months, identically. §1's partial-failure policy - *"one bad file never aborts a
        # batch - it is logged, counted, and reported at the end"* - is a statement about the
        # **boundary**, and a boundary defined by enumeration is not one. This is that sentence
        # implemented rather than approximated.
        #
        # **Nothing is swallowed.** The file comes back named, with `UNDECODABLE` - its own reason,
        # not folded into `OTHER`'s *"could not be opened"*, which would be false about a file
        # whose bytes read perfectly. `models.unreadable_label` words it, both surfaces render it,
        # and §9 already rules that the run still ATTEMPTS an unreadable file, so this costs the
        # user nothing but the perceptual-dedup pass on that one file.
        #
        # `BaseException` is deliberately NOT caught: a `KeyboardInterrupt` or a `SystemExit` is
        # the operator stopping the run, and a worker that ate one would make Ctrl-C stop working.
        return path_str, None, None, UnreadableReason.UNDECODABLE, decode_noise.take_warnings()
    return path_str, sha, perceptual, None, decode_noise.take_warnings()


def _take_hash_result(future: Future[HashJobResult]) -> HashJobResult | None:
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
    want_perceptual: bool,
    results: dict[Path, FileHashes],
    unreadable: dict[Path, UnreadableReason],
    done: int,
    total: int,
) -> None:
    """Hash ``to_hash`` into ``results``, defending one unreadable file and a dead process pool."""
    jobs = [(str(path), path in need_sha, want_perceptual) for path in to_hash]
    # ⚠ INSTALLED IN BOTH PLACES, AND EACH HAS ITS OWN TEST. `pool="thread"` is the DEFAULT, so
    # this parent-side call is the one that carries the common path; `initializer` below carries
    # a `ProcessPoolExecutor`'s children, which are separate interpreters and inherit nothing.
    # Installing in only one of the two leaves the other unhooked and every test green. `(aev)`
    decode_noise.install()
    executor_cls = ProcessPoolExecutor if pool == "process" else ThreadPoolExecutor
    # The C half is not a Python warning and cannot be filtered: libtiff and libjpeg write to
    # file descriptor 2 directly. Children inherit that descriptor, so one capture in the parent
    # covers both pools. Progress still reaches the terminal - `capture_decoder_output` repoints
    # `sys.stderr`, which is what `cli._progress_printer` writes through.
    # ⚠ The initializer is for a PROCESS pool only. A thread pool's initializer runs in each
    # worker thread of THIS process, so arming it there would write global warning state
    # concurrently with other workers - the exact undefined behaviour this replaces. The parent
    # call above already covers every thread, because they share one interpreter.
    initializer = decode_noise.install if pool == "process" else None
    with (
        decode_noise.capture_decoder_output(),
        executor_cls(max_workers=max(1, workers), initializer=initializer) as executor,
    ):
        futures = [executor.submit(_hash_one, job) for job in jobs]
        for future in as_completed(futures):
            if cancel is not None and cancel.is_set():
                for pending in futures:
                    pending.cancel()
                break
            got = _take_hash_result(future)
            if got is None:
                # Pool death is not an OSError; abandon remaining work with empty hashes. The
                # probe's verdict still rides along: a file we already know we cannot read is
                # not made unknown again by the pool dying underneath it.
                for path in to_hash:
                    results.setdefault(
                        path,
                        FileHashes(None, None, unreadable.get(path), perceptual_computed=False),
                    )
                break
            path_str, sha, perceptual, late, library_warnings = got
            decode_noise.record_warnings(library_warnings)
            path = Path(path_str)
            # The worker's reason wins where it has one: it read further than the probe did.
            hashes = FileHashes(
                sha256=sha,
                perceptual=perceptual,
                unreadable=late or unreadable.get(path),
                # The pass's own flag, not the value: `perceptual` is None for a video AND for a
                # pass that never tried, and only the caller knows which.
                perceptual_computed=want_perceptual,
            )
            results[path] = hashes
            if cache is not None and (sha is not None or perceptual is not None):
                # An unreadable file has neither hash, so it is never cached and the reason is
                # never persisted - `put` writes the two hashes and nothing else either way.
                cache.put(
                    path,
                    sizes.get(path, -1),
                    _mtime_ns(path),
                    hashes,
                    perceptual_computed=want_perceptual,
                )
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
    perceptual: bool = True,
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
    if not perceptual and cache is not None and cache.writable:
        # Refused rather than documented. A row carrying `perceptual=None` because it was never
        # computed is indistinguishable from one carrying it because the file is not an image,
        # so a later run would take it as a hit and lose near-duplicate detection silently.
        # `HashCache(..., writable=False)` is the supported pairing.
        message = "a partial hashing pass needs a read-only cache; see IMPLEMENTATION_STANDARDS 8"
        raise ValueError(message)

    sizes = _sizes(paths)
    # Over *all* paths and before the cache split below, which is the whole point: `stat`
    # succeeds on a file whose bytes cannot be read, so an unreadable file can still produce a
    # cache hit and skip the worker entirely. See `_probe_readability`.
    unreadable = _probe_readability(paths)
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
            hit = cache.get(
                path,
                sizes.get(path, -1),
                _mtime_ns(path),
                need_sha=path in need_sha,
                # A run that wants perceptual hashes must MISS a row nobody perceptually hashed,
                # rather than take its NULL as "not an image".
                need_perceptual=perceptual,
            )
            if hit is None:
                to_hash.append(path)
            else:
                # The cached hashes stay usable for dedup - they describe content that has not
                # changed. What has changed is that the file cannot be read *now*, so the copy
                # will fail, and a preview that omits it is predicting the wrong run.
                reason = unreadable.get(path)
                results[path] = hit if reason is None else replace(hit, unreadable=reason)
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
        want_perceptual=perceptual,
        results=results,
        unreadable=unreadable,
        done=done,
        total=total,
    )
    return results
