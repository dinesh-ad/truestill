"""Takeout rescue preview (Rescue report screen).

Self-contained surface: Catalog + takeout/organize core. Owns
``InferredLocalShiftPayload`` (also used by Organize summaries via the facade re-export).
"""

from __future__ import annotations

import threading
from collections import Counter
from pathlib import Path
from typing import NotRequired, TypedDict

from truestill_core.catalog import Catalog
from truestill_core.categorize import build_rules
from truestill_core.date_provenance import format_offset
from truestill_core.dedup import DedupIndex
from truestill_core.exif import read_metadata
from truestill_core.hash_cache import HashCache
from truestill_core.hashing import DEFAULT_PHASH_THRESHOLD
from truestill_core.layout_settings import resolve_scheme
from truestill_core.models import (
    date_quality,
    format_inferred_local_shift_line,
    inferred_local_shifts,
)
from truestill_core.organizer import discover, heavy_days_for_organize, plan, resolve
from truestill_core.progress import Phase, Progress, ProgressCallback
from truestill_core.takeout import scan_takeout

from truestill_app.jobs import JobTarget


class InferredLocalShiftPayload(TypedDict):
    name: str
    before: str
    after: str
    offset: str
    evidence: str
    line: str


class IngestPreviewEmpty(TypedDict):
    files: int
    missing_sidecar: int


class IngestPreviewSummary(TypedDict):
    files: int
    kept: int
    dup_collapsed: int
    reclaimed_mb: float
    dates_photo_taken: int
    dates_upload_approx: int
    dates_exif: int
    undated: int
    sentinel_rejected: int
    suspect_default: int
    inferred_local_shifts: list[InferredLocalShiftPayload]
    missing_sidecar: int
    elapsed_seconds: NotRequired[float]


def ingest_preview(
    takeout: Path,
    destination: Path,  # noqa: ARG001 - kept for API symmetry with organize preview
    db: Path,
    *,
    progress: ProgressCallback | None = None,
    cancel: threading.Event | None = None,
) -> IngestPreviewEmpty | IngestPreviewSummary:
    """Dry-run Takeout rescue: the honest report the Rescue screen shows before any run.

    Discovery has no progress callback, so the first tick is indeterminate (:attr:`Phase.SCANNING`
    with ``total=0``) rather than a fake count. Metadata and hashing then reuse the same
    callbacks :func:`read_metadata` and :func:`resolve` already expose to organize preview.
    """
    if progress is not None:
        progress(Progress(0, 0, Phase.SCANNING, ""))
    scan = scan_takeout(takeout)
    files = discover(takeout)
    if not files:
        return {"files": 0, "missing_sidecar": 0}
    with Catalog(db) as catalog, HashCache.beside(db) as cache:
        metadata = read_metadata(files, progress=progress, cancel=cancel, cache=cache)
        scheme = resolve_scheme(catalog)
        rules = build_rules()
        heavy = heavy_days_for_organize(catalog, files, metadata, rules, takeout=scan.sidecars)
        decisions = plan(
            files, metadata, rules, takeout=scan.sidecars, scheme=scheme, heavy_days=heavy
        )
        index = DedupIndex.from_catalog_rows(catalog.seed_rows(), DEFAULT_PHASH_THRESHOLD)
        resolutions = resolve(
            decisions,
            index,
            catalog_sizes=catalog.known_sizes(),
            progress=progress,
            cancel=cancel,
            cache=cache,
        )
    uploads = [r for r in resolutions if r.should_upload]
    dups = [r for r in resolutions if not r.should_upload]
    sources = Counter(r.decision.date_source.value for r in uploads)
    reclaimed = sum(_safe_size(r.decision.source) for r in dups)
    quality = date_quality(uploads)
    return {
        "files": len(resolutions),
        "kept": len(uploads),
        "dup_collapsed": len(dups),
        "reclaimed_mb": round(reclaimed / 1e6, 1),
        "dates_photo_taken": sources.get("takeout", 0),
        "dates_upload_approx": sources.get("takeout_upload", 0),
        "dates_exif": sources.get("exif", 0),
        "undated": sources.get("none", 0),
        "sentinel_rejected": quality.sentinel_rejected,
        "suspect_default": quality.suspect_default,
        "inferred_local_shifts": [
            {
                "name": s.name,
                "before": s.before.strftime("%H:%M:%S"),
                "after": s.after.strftime("%H:%M:%S"),
                "offset": format_offset(s.offset),
                "evidence": s.evidence,
                "line": format_inferred_local_shift_line(s),
            }
            for s in inferred_local_shifts(uploads)
        ],
        "missing_sidecar": len(scan.missing_sidecar),
    }


def ingest_preview_run(takeout: Path, destination: Path, db: Path) -> JobTarget:
    """Takeout rescue preview as a cancellable job - same dry-run, streamed progress."""

    def target(
        progress: ProgressCallback, cancel: threading.Event
    ) -> IngestPreviewEmpty | IngestPreviewSummary:
        return ingest_preview(takeout, destination, db, progress=progress, cancel=cancel)

    return target


def _safe_size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0
