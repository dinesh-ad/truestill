"""Profile organize_preview phases + file opens. Measure only -- changes no product behaviour.

Mirrors ``service.organize_preview`` call-for-call with wall-clock timers around each stage,
and wraps ``Path.open`` / ``PIL.Image.open`` to count opens (the FUSE-relevant cost).

Cold catalog + cold hash cache (temp paths) so a repeat does not hide the first-preview cost
that backlog (ss) recorded.

Usage::

    uv run python scripts/profile_organize_preview.py \\
        --source "/path/to/Wayanad '14" --label local

    uv run python scripts/profile_organize_preview.py \\
        --source "/path/to/pCloud/.../Wayanad '14" --label pcloud

Writes JSON to stdout (and optionally ``--json-out``). Complexity: O(n) files, same as preview.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import threading
import time
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import truestill_core.hashing as hashing_mod
import truestill_core.scan as scan_mod
from PIL import Image
from truestill_app.service import _skipped_summary, _summarize
from truestill_core.catalog import Catalog
from truestill_core.categorize import build_rules
from truestill_core.dedup import DedupIndex
from truestill_core.exif import read_metadata
from truestill_core.hash_cache import HashCache
from truestill_core.hashing import DEFAULT_PHASH_THRESHOLD
from truestill_core.layout_settings import resolve_scheme
from truestill_core.models import Decision, DuplicateKind, FileHashes, Resolution
from truestill_core.organizer import plan, scan_source
from truestill_core.scan import compute_hashes


@dataclass
class OpenTally:
    """Thread-safe open counters. Keys are absolute path strings."""

    lock: threading.Lock = field(default_factory=threading.Lock)
    path_open: Counter[str] = field(default_factory=Counter)
    image_open: Counter[str] = field(default_factory=Counter)
    path_open_total: int = 0
    image_open_total: int = 0

    def record_path(self, path: Path) -> None:
        # str only -- never resolve/exists here; that would add FUSE round-trips and
        # distort the profile we are measuring.
        with self.lock:
            self.path_open[str(path)] += 1
            self.path_open_total += 1

    def record_image(self, path: Path | str) -> None:
        with self.lock:
            self.image_open[str(path)] += 1
            self.image_open_total += 1


@dataclass
class TimedFn:
    """Accumulate wall time and call count for a wrapped function (thread-safe)."""

    name: str
    lock: threading.Lock = field(default_factory=threading.Lock)
    seconds: float = 0.0
    calls: int = 0

    def wrap(self, fn: Callable[..., Any]) -> Callable[..., Any]:
        def wrapped(*args: Any, **kwargs: Any) -> Any:
            start = time.perf_counter()
            try:
                return fn(*args, **kwargs)
            finally:
                elapsed = time.perf_counter() - start
                with self.lock:
                    self.seconds += elapsed
                    self.calls += 1

        return wrapped


def _install_open_hooks(tally: OpenTally) -> Callable[[], None]:
    """Patch Path.open and Image.open; return a restore callable."""
    orig_path_open = Path.open
    orig_image_open = Image.open

    def path_open(self: Path, *args: Any, **kwargs: Any) -> Any:
        tally.record_path(self)
        return orig_path_open(self, *args, **kwargs)

    def image_open(fp: Any, *args: Any, **kwargs: Any) -> Any:
        if isinstance(fp, (str, Path)):
            tally.record_image(fp)
        return orig_image_open(fp, *args, **kwargs)

    Path.open = path_open  # type: ignore[method-assign]
    Image.open = image_open  # type: ignore[assignment]

    def restore() -> None:
        Path.open = orig_path_open  # type: ignore[method-assign]
        Image.open = orig_image_open  # type: ignore[assignment]

    return restore


def _classify(
    decisions: list[Decision],
    hashes: dict[Path, FileHashes],
    index: DedupIndex,
) -> list[Resolution]:
    """Sequential dedup classification - same order-dependent loop as ``organizer.resolve``."""
    resolutions: list[Resolution] = []
    for decision in decisions:
        file_hashes = hashes.get(decision.source)
        if file_hashes is None:
            break
        match = index.check(file_hashes.sha256, file_hashes.perceptual)
        exact = match if match is not None and match.kind is DuplicateKind.EXACT else None
        near = match if match is not None and match.kind is DuplicateKind.PERCEPTUAL else None
        if exact is None:
            index.register(str(decision.source), file_hashes.sha256, file_hashes.perceptual)
        resolutions.append(
            Resolution(
                decision=decision,
                hashes=file_hashes,
                exact_duplicate=exact,
                near_duplicate=near,
            )
        )
    return resolutions


def _report(
    *,
    label: str,
    source: Path,
    n: int,
    wall: float,
    phases: dict[str, float],
    timed_sha: TimedFn,
    timed_phash: TimedFn,
    opens: OpenTally,
    exiftool_file_opens: int,
    hashes: dict[Path, FileHashes],
    summary: dict[str, Any],
) -> dict[str, Any]:
    accounted = sum(
        phases[k]
        for k in (
            "walk_scan_source",
            "read_metadata",
            "catalog_plan_index",
            "compute_hashes_wall",
            "dedup_classify",
            "summarize",
        )
    )
    return {
        "label": label,
        "source": str(source),
        "files": n,
        "wall_seconds": wall,
        "accounted_phase_seconds": accounted,
        "files_per_sec": n / wall if wall else 0.0,
        "phases_seconds": phases,
        "phases_per_file_ms": {k: (v / n) * 1000 for k, v in phases.items()},
        "phase_share_pct_of_wall": {k: (v / wall) * 100 for k, v in phases.items()},
        "hashing": {
            "need_sha_count": timed_sha.calls,
            "need_sha_pct": 100.0 * timed_sha.calls / n,
            "sha256_calls": timed_sha.calls,
            "sha256_seconds_summed": timed_sha.seconds,
            "sha256_ms_per_call": (
                (timed_sha.seconds / timed_sha.calls) * 1000 if timed_sha.calls else 0.0
            ),
            "perceptual_calls": timed_phash.calls,
            "perceptual_seconds_summed": timed_phash.seconds,
            "perceptual_ms_per_call": (
                (timed_phash.seconds / timed_phash.calls) * 1000 if timed_phash.calls else 0.0
            ),
            "sha256_skipped_unique_size": sum(1 for h in hashes.values() if h.sha256 is None),
            "perceptual_non_null": sum(1 for h in hashes.values() if h.perceptual is not None),
        },
        "opens": {
            "path_open_total": opens.path_open_total,
            "image_open_total": opens.image_open_total,
            "exiftool_file_args": exiftool_file_opens,
            "per_file": {
                "path_open_mean": opens.path_open_total / n,
                "image_open_mean": opens.image_open_total / n,
                "exiftool_args_mean": exiftool_file_opens / n,
                "estimated_total_opens_mean": (
                    opens.path_open_total + opens.image_open_total + exiftool_file_opens
                )
                / n,
            },
            "note": (
                "path_open = Python Path.open (sha256 streams + any other). "
                "image_open = PIL.Image.open. "
                "exiftool opens happen in a subprocess and are counted as one per "
                "media file passed to read_metadata (batched, but each file is read)."
            ),
        },
        "summary_counts": {
            "files": summary.get("files"),
            "photos": summary.get("photos"),
            "videos": summary.get("videos"),
            "exact_dup": summary.get("exact_dup"),
            "near_dup": summary.get("near_dup"),
            "new_unique": summary.get("new_unique"),
        },
        "notes": [
            "Cold throwaway catalog + hash cache (temp dir).",
            "Mirrors organize_preview; does not mutate product code paths.",
            (
                "sha256/perceptual seconds are summed wall time inside workers "
                "(can exceed wall when parallel)."
            ),
            "sizes_stat_pass is the timed cost of _sizes inside compute_hashes.",
        ],
    }


def profile_preview(source: Path, *, label: str) -> dict[str, Any]:
    """Run the organize_preview pipeline once under instrumentation. Writes nothing lasting."""
    phases: dict[str, float] = {}
    timed_sha = TimedFn("sha256_file")
    timed_phash = TimedFn("perceptual_hash")
    timed_sizes = TimedFn("_sizes")
    opens = OpenTally()
    restore_opens = _install_open_hooks(opens)

    orig_sha = hashing_mod.sha256_file
    orig_phash = hashing_mod.perceptual_hash
    orig_sizes = scan_mod._sizes
    hashing_mod.sha256_file = timed_sha.wrap(orig_sha)  # type: ignore[assignment]
    hashing_mod.perceptual_hash = timed_phash.wrap(orig_phash)  # type: ignore[assignment]
    scan_mod.sha256_file = hashing_mod.sha256_file  # type: ignore[assignment]
    scan_mod.perceptual_hash = hashing_mod.perceptual_hash  # type: ignore[assignment]
    scan_mod._sizes = timed_sizes.wrap(orig_sizes)  # type: ignore[assignment]

    wall0 = time.perf_counter()
    try:
        with tempfile.TemporaryDirectory(prefix="truestill-profile-") as tmp:
            db = Path(tmp) / "catalog.sqlite"
            (Path(tmp) / "dest").mkdir()

            t = time.perf_counter()
            scan = scan_source(source)
            files = scan.media
            phases["walk_scan_source"] = time.perf_counter() - t
            if not files:
                return {"label": label, "error": "no media", "source": str(source)}

            t = time.perf_counter()
            metadata = read_metadata(files)
            phases["read_metadata"] = time.perf_counter() - t

            t = time.perf_counter()
            with Catalog(db) as catalog, HashCache.beside(db) as cache:
                scheme = resolve_scheme(catalog)
                decisions = plan(files, metadata, build_rules(), scheme=scheme)
                index = DedupIndex.from_catalog_rows(catalog.seed_rows(), DEFAULT_PHASH_THRESHOLD)
                catalog_sizes = catalog.known_sizes()
                phases["catalog_plan_index"] = time.perf_counter() - t

                t = time.perf_counter()
                hashes = compute_hashes(
                    [d.source for d in decisions],
                    catalog_sizes=catalog_sizes,
                    cache=cache,
                )
                phases["compute_hashes_wall"] = time.perf_counter() - t
                phases["sizes_stat_pass"] = timed_sizes.seconds
                phases["sha256_file_summed"] = timed_sha.seconds
                phases["perceptual_hash_summed"] = timed_phash.seconds

                t = time.perf_counter()
                resolutions = _classify(decisions, hashes, index)
                phases["dedup_classify"] = time.perf_counter() - t

            t = time.perf_counter()
            summary = _summarize(resolutions)
            report_summary: dict[str, Any] = {
                **summary,
                "destination_is_drive": False,
                "skipped": _skipped_summary(scan),
            }
            phases["summarize"] = time.perf_counter() - t

            return _report(
                label=label,
                source=source,
                n=len(files),
                wall=time.perf_counter() - wall0,
                phases=phases,
                timed_sha=timed_sha,
                timed_phash=timed_phash,
                opens=opens,
                exiftool_file_opens=len(files),
                hashes=hashes,
                summary=report_summary,
            )
    finally:
        hashing_mod.sha256_file = orig_sha  # type: ignore[assignment]
        hashing_mod.perceptual_hash = orig_phash  # type: ignore[assignment]
        scan_mod.sha256_file = orig_sha  # type: ignore[assignment]
        scan_mod.perceptual_hash = orig_phash  # type: ignore[assignment]
        scan_mod._sizes = orig_sizes  # type: ignore[assignment]
        restore_opens()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--label", required=True)
    parser.add_argument("--json-out", type=Path, default=None)
    args = parser.parse_args()
    if not args.source.is_dir():
        print(f"not a directory: {args.source}", file=sys.stderr)
        return 2
    result = profile_preview(args.source, label=args.label)
    text = json.dumps(result, indent=2, sort_keys=True)
    print(text)
    if args.json_out is not None:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(text + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
