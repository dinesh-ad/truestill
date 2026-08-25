"""Takeout rescue preview (Rescue report screen).

Self-contained surface: Catalog + takeout/organize core. Owns
``InferredLocalShiftPayload`` (also used by Organize summaries via the facade re-export).
"""

from __future__ import annotations

import threading
from collections import Counter
from pathlib import Path
from typing import NotRequired, TypedDict

from truestill_core.archive_extract import extract_archive_set
from truestill_core.archive_ingest import archives_at, precheck_archives
from truestill_core.catalog_session import open_catalog
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
    partition_for_report,
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
    #: Named on its own so `files == kept + dup_collapsed + unreadable` holds. A file truestill
    #: could not read is neither kept nor collapsed, and counting it as kept promised one that
    #: will not be organized.
    unreadable: int
    reclaimed_mb: float
    dates_photo_taken: int
    dates_upload_approx: int
    dates_exif: int
    undated: int
    sentinel_rejected: int
    future_rejected: int
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
    with open_catalog(db) as catalog, HashCache.beside(db) as cache:
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
    # Same disjointness as the organize summary: an unreadable file is neither kept nor a
    # collapsed duplicate, and counting it as kept promised a file that will not be organized.
    buckets = partition_for_report(resolutions)
    uploads = buckets.organized
    dups = buckets.exact_duplicates
    sources = Counter(r.decision.date_source.value for r in uploads)
    reclaimed = sum(_safe_size(r.decision.source) for r in dups)
    quality = date_quality(uploads)
    return {
        "files": len(resolutions),
        "kept": len(uploads),
        "dup_collapsed": len(dups),
        "unreadable": len(buckets.unreadable),
        "reclaimed_mb": round(reclaimed / 1e6, 1),
        "dates_photo_taken": sources.get("takeout", 0),
        "dates_upload_approx": sources.get("takeout_upload", 0),
        "dates_exif": sources.get("exif", 0),
        "undated": sources.get("none", 0),
        "sentinel_rejected": quality.sentinel_rejected,
        "future_rejected": quality.future_rejected,
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


class ArchivePrecheckPayload(TypedDict):
    """What the Rescue screen shows before a single byte is written."""

    ok: bool
    claimed_bytes: int
    free_bytes: int
    media_entries: int
    parts: int
    refusals: list[str]
    detail: str


def archive_precheck(source: Path, destination: Path) -> ArchivePrecheckPayload:
    """Preview-then-confirm for archives: the refusals and the cost, before anything is written.

    ``source`` is the single path the user pointed at - a folder in the app, since its picker is
    a folder picker. `archives_at` turns that into the set, and it is shared with the CLI so the
    two surfaces cannot drift on what "pointing at a Takeout" means. **Neither ever asks the
    user to enumerate parts**, because forgetting one would succeed rather than fail.

    Reads headers only. Declining is free, which is the whole point of showing this first - the
    alternative is finding out 190 GB into 200.

    ``claimed_bytes`` is **the archives' own claim**, and `detail` says so in words. A user must
    not read a header field as a measurement truestill made.
    """
    report = precheck_archives(archives_at(source), destination)
    return {
        "ok": report.may_proceed,
        "claimed_bytes": report.claimed_bytes,
        "free_bytes": report.free_bytes,
        "media_entries": report.media_entries,
        "parts": len(report.archive_set.parts),
        "refusals": [str(refusal) for refusal in report.refusals],
        "detail": report.detail,
    }


def archive_ingest_run(
    source: Path, destination: Path, db: Path
) -> JobTarget[IngestPreviewEmpty | IngestPreviewSummary | ArchivePrecheckPayload]:
    """Unpack an archive set, then run the ordinary Takeout preview over the merged tree.

    **The precheck is re-run inside the job**, not trusted from the earlier call: the user may
    have unplugged the drive or deleted a part between previewing and confirming, and a refusal
    is cheaper than a half-extraction.

    Cancel needs no special handling here. `extract_archive_set` leaves the staging tree in the
    same journalled state a crash leaves, so recovery has one path rather than one for crashes
    and another for the button.
    """

    def target(
        progress: ProgressCallback, cancel: threading.Event
    ) -> IngestPreviewEmpty | IngestPreviewSummary | ArchivePrecheckPayload:
        report = precheck_archives(archives_at(source), destination)
        if not report.may_proceed:
            return archive_precheck(source, destination)
        extraction = extract_archive_set(
            report.archive_set, destination, progress=progress, cancel=cancel
        )
        if extraction.cancelled:
            return archive_precheck(source, destination)
        return ingest_preview(
            extraction.staging_root, destination, db, progress=progress, cancel=cancel
        )

    return target


def ingest_preview_run(
    takeout: Path, destination: Path, db: Path
) -> JobTarget[IngestPreviewEmpty | IngestPreviewSummary]:
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
