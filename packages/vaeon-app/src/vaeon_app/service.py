"""Bridge from the web layer to vaeon-core. Imports only vaeon-core -- never vaeon-cli.

Read helpers return plain dicts for JSON; long operations return :data:`JobTarget`s that the
job manager runs on a thread with progress + cancellation. Preview writes nothing (the CLI's
dry-run posture, preserved in the UI).
"""

from __future__ import annotations

import os
import threading
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from vaeon_core.catalog import Catalog
from vaeon_core.categorize import build_rules
from vaeon_core.dedup import DedupIndex
from vaeon_core.destinations import LocalDestination
from vaeon_core.drive import read_marker
from vaeon_core.exif import read_metadata
from vaeon_core.hashing import DEFAULT_PHASH_THRESHOLD, HEIF_AVAILABLE, HEIF_EXTENSIONS
from vaeon_core.layout import (
    DEFAULT_TEMPLATE_STRING,
    LAYOUT_TEMPLATE_KEY,
    PRESETS,
    SAMPLE_CONTEXTS,
    LayoutTemplate,
    TemplateError,
    preview,
    resolve_template,
)
from vaeon_core.migrate import run_migration
from vaeon_core.models import Resolution
from vaeon_core.organizer import (
    MEDIA_EXTENSIONS,
    SourceScan,
    discover,
    execute,
    plan,
    resolve,
    scan_source,
)
from vaeon_core.progress import ProgressCallback
from vaeon_core.takeout import scan_takeout
from vaeon_core.verify import CopyStatus, CopyToVerify, verify_copies

from vaeon_app.jobs import JobTarget


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _summarize(resolutions: list[Resolution]) -> dict[str, Any]:
    uploads = [r for r in resolutions if r.should_upload]
    near = [r for r in uploads if r.near_duplicate is not None]
    labels = Counter(r.decision.category.label for r in uploads)
    heic = sum(1 for r in resolutions if r.decision.source.suffix.lower() in HEIF_EXTENSIONS)
    summary: dict[str, Any] = {
        "files": len(resolutions),
        "new_unique": len(uploads) - len(near),
        "near_dup": len(near),
        "exact_dup": len(resolutions) - len(uploads),
        "undated": sum(1 for r in uploads if r.decision.captured_at is None),
        "folders": dict(labels.most_common()),
    }
    if heic and not HEIF_AVAILABLE:
        # Never silent: HEIC was exact-deduped but not perceptually hashed.
        summary["heic_perceptual_skipped"] = heic
    return summary


def _skipped_summary(scan: SourceScan) -> dict[str, dict[str, int]]:
    """Skipped files grouped by extension, so the UI can account for what was not organized."""
    return {
        "documents": dict(Counter(p.suffix.lower() or "(no ext)" for p in scan.documents)),
        "unrecognized": dict(Counter(p.suffix.lower() or "(no ext)" for p in scan.unrecognized)),
    }


def organize_preview(source: Path, destination: Path, db: Path) -> dict[str, Any]:
    """Plan + dedup with no writes -- the dry-run summary the UI shows before a real run."""
    scan = scan_source(source)
    files = scan.media
    if not files:
        return {"files": 0, "folders": {}, "skipped": _skipped_summary(scan)}
    metadata = read_metadata(files)
    with Catalog(db) as catalog:
        template = resolve_template(catalog.get_setting(LAYOUT_TEMPLATE_KEY))
        decisions = plan(files, metadata, build_rules(), template=template)
        index = DedupIndex.from_catalog_rows(catalog.seed_rows(), DEFAULT_PHASH_THRESHOLD)
        resolutions = resolve(decisions, index, catalog_sizes=catalog.known_sizes())
    summary = _summarize(resolutions)
    summary["destination_is_drive"] = read_marker(destination) is not None
    summary["skipped"] = _skipped_summary(scan)
    return summary


def organize_run(
    source: Path, destination: Path, db: Path, *, skip_undated: bool = False
) -> JobTarget:
    """Build a job target that runs the real organize (progress across hashing then copying)."""

    def target(progress: ProgressCallback, cancel: threading.Event) -> dict[str, Any]:
        files = discover(source)
        if not files:
            return {"uploaded": 0}
        metadata = read_metadata(files)
        with Catalog(db) as catalog:
            template = resolve_template(catalog.get_setting(LAYOUT_TEMPLATE_KEY))
            decisions = plan(files, metadata, build_rules(), template=template)
            index = DedupIndex.from_catalog_rows(catalog.seed_rows(), DEFAULT_PHASH_THRESHOLD)
            resolutions = resolve(
                decisions,
                index,
                catalog_sizes=catalog.known_sizes(),
                progress=progress,
                cancel=cancel,
            )
            marker = read_marker(destination)
            drive_uuid = None
            if marker is not None:
                catalog.upsert_drive(uuid=marker.uuid, label=marker.label)
                drive_uuid = marker.uuid
            results = execute(
                resolutions,
                LocalDestination(destination),
                catalog,
                apply=True,
                skip_undated=skip_undated,
                progress=progress,
                cancel=cancel,
                drive_uuid=drive_uuid,
            )
        outcomes = Counter(r.status.value for r in results)
        return {"outcomes": dict(outcomes)}

    return target


def verify_run(path: Path, db: Path) -> JobTarget:
    """Build a job target that verifies a connected drive's copies against the catalog."""

    def target(progress: ProgressCallback, cancel: threading.Event) -> dict[str, Any]:
        marker = read_marker(path)
        if marker is None:
            message = "no .vaeon-drive.json at that path -- is the drive connected?"
            raise ValueError(message)
        with Catalog(db) as catalog:
            catalog.upsert_drive(uuid=marker.uuid, label=marker.label)
            rows = catalog.copies_on_drive(marker.uuid)
            copies = [
                CopyToVerify(r["sha256"], r["relative"], r["copy_sha256"] or r["sha256"])
                for r in rows
            ]
            results = verify_copies(copies, path, progress=progress, cancel=cancel)
            when = _now()
            for result in results:
                if result.status is CopyStatus.VERIFIED:
                    catalog.mark_copy_verified(
                        sha256=result.copy.sha256, drive_uuid=marker.uuid, when=when
                    )
            catalog.set_drive_verified(marker.uuid, when)
        counts = Counter(r.status.value for r in results)
        return {
            "label": marker.label,
            "verified": counts.get("verified", 0),
            "missing": counts.get("missing", 0),
            "mismatch": counts.get("mismatch", 0),
            "problems": [
                {"status": r.status.value, "relative": r.copy.relative}
                for r in results
                if r.status is not CopyStatus.VERIFIED
            ],
        }

    return target


def list_drives(db: Path) -> list[dict[str, Any]]:
    with Catalog(db) as catalog:
        return [
            {
                "label": d["label"],
                "uuid": d["uuid"],
                "files": d["file_count"],
                "size": d["total_size"] or 0,
                "last_seen": d["last_seen"],
                "last_verified": d["last_verified"],
            }
            for d in catalog.list_drives()
        ]


def where(term: str, db: Path) -> list[dict[str, Any]]:
    with Catalog(db) as catalog:
        return [
            {
                "name": r["original_name"] or r["relative"],
                "drive": r["drive_label"],
                "relative": r["relative"],
                "last_verified": r["last_verified"],
            }
            for r in catalog.find_copies(term)
        ]


def at_risk(db: Path) -> list[dict[str, Any]]:
    with Catalog(db) as catalog:
        return [
            {"name": r["original_name"] or r["sha256"][:12], "drive": r["drive_label"]}
            for r in catalog.single_copy_shas()
        ]


# --- event review (used by the Event review screen; merge/split are UI-only) ----------


def plan_resolve(source: Path, db: Path) -> tuple[list[Resolution], dict[Path, dict[str, Any]]]:
    """Plan + dedup a source (no writes), returning resolutions and metadata for clustering."""
    files = discover(source)
    if not files:
        return [], {}
    metadata = read_metadata(files)
    with Catalog(db) as catalog:
        template = resolve_template(catalog.get_setting(LAYOUT_TEMPLATE_KEY))
        decisions = plan(files, metadata, build_rules(), template=template)
        index = DedupIndex.from_catalog_rows(catalog.seed_rows(), DEFAULT_PHASH_THRESHOLD)
        resolutions = resolve(decisions, index, catalog_sizes=catalog.known_sizes())
    return resolutions, metadata


def cluster_json(cluster: Any) -> dict[str, Any]:
    """Serialise an EventCandidate for the review UI."""
    centroid = cluster.gps_centroid()
    return {
        "start": cluster.start.isoformat(),
        "end": cluster.end.isoformat(),
        "count": cluster.count,
        "location": list(centroid) if centroid else None,
    }


# --- Takeout rescue report (Rescue report screen) -------------------------------------


def ingest_preview(takeout: Path, destination: Path, db: Path) -> dict[str, Any]:  # noqa: ARG001
    """Dry-run Takeout rescue: the honest report the Rescue screen shows before any run."""
    scan = scan_takeout(takeout)
    files = discover(takeout)
    if not files:
        return {"files": 0, "missing_sidecar": 0}
    metadata = read_metadata(files)
    with Catalog(db) as catalog:
        template = resolve_template(catalog.get_setting(LAYOUT_TEMPLATE_KEY))
        decisions = plan(files, metadata, build_rules(), takeout=scan.sidecars, template=template)
        index = DedupIndex.from_catalog_rows(catalog.seed_rows(), DEFAULT_PHASH_THRESHOLD)
        resolutions = resolve(decisions, index, catalog_sizes=catalog.known_sizes())
    uploads = [r for r in resolutions if r.should_upload]
    dups = [r for r in resolutions if not r.should_upload]
    sources = Counter(r.decision.date_source.value for r in uploads)
    reclaimed = sum(_safe_size(r.decision.source) for r in dups)
    return {
        "files": len(resolutions),
        "kept": len(uploads),
        "dup_collapsed": len(dups),
        "reclaimed_mb": round(reclaimed / 1e6, 1),
        "dates_photo_taken": sources.get("takeout", 0),
        "dates_upload_approx": sources.get("takeout_upload", 0),
        "dates_exif": sources.get("exif", 0),
        "undated": sources.get("none", 0),
        "missing_sidecar": len(scan.missing_sidecar),
    }


def _safe_size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


# --- server-side folder picker (Browse) -----------------------------------------------


def fs_roots() -> list[dict[str, str]]:
    """Friendly starting points: Home + common media folders + mounted drives."""
    roots: list[dict[str, str]] = []
    home = Path.home()
    roots.append({"label": "Home", "path": str(home)})
    for name in ("Pictures", "Downloads", "Desktop", "Documents"):
        candidate = home / name
        if candidate.is_dir():
            roots.append({"label": name, "path": str(candidate)})
    for base in ("/media", "/mnt", "/run/media", "/Volumes"):
        root = Path(base)
        if not root.is_dir():
            continue
        try:
            for child in sorted(root.iterdir()):
                if child.is_dir():
                    roots.append({"label": child.name, "path": str(child)})
        except OSError:
            continue
    return roots


def fs_dirs(path_str: str) -> dict[str, Any]:
    """List the immediate sub-directories of ``path`` (or the roots when empty)."""
    if not path_str.strip():
        return {"path": "", "parent": None, "roots": fs_roots(), "entries": []}
    path = Path(path_str).expanduser()
    try:
        path = path.resolve()
    except OSError:
        return {"error": "that path could not be read", "roots": fs_roots(), "entries": []}
    if not path.is_dir():
        return {"error": "not a folder", "roots": fs_roots(), "entries": []}
    entries: list[dict[str, str]] = []
    try:
        for child in sorted(path.iterdir(), key=lambda p: p.name.lower()):
            if child.is_dir() and not child.name.startswith("."):
                entries.append({"name": child.name, "path": str(child)})
    except OSError:
        return {"error": "that folder could not be read", "roots": fs_roots(), "entries": []}
    parent = str(path.parent) if path.parent != path else None
    return {"path": str(path), "parent": parent, "roots": fs_roots(), "entries": entries}


def fs_create(path_str: str) -> dict[str, Any]:
    """Create a folder (and parents) - for the "Create it?" action on a new backup destination."""
    path = Path(path_str).expanduser()
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return {"created": False, "error": str(exc)}
    return {"created": True, **fs_validate(str(path))}


def fs_validate(path_str: str, *, cap: int = 10000) -> dict[str, Any]:
    """Report whether ``path`` is a usable folder and roughly how much media it holds."""
    path = Path(path_str).expanduser()
    try:
        path = path.resolve()
    except OSError:
        return {"exists": False, "is_dir": False, "readable": False, "writable": False, "media": 0}
    is_dir = path.is_dir()
    media = 0
    capped = False
    if is_dir and os.access(path, os.R_OK):
        for child in path.rglob("*"):
            if child.suffix.lower() in MEDIA_EXTENSIONS:
                media += 1
                if media >= cap:
                    capped = True
                    break
    return {
        "exists": path.exists(),
        "is_dir": is_dir,
        "readable": os.access(path, os.R_OK) if path.exists() else False,
        "writable": os.access(path, os.W_OK) if path.exists() else False,
        "is_drive": read_marker(path) is not None,
        "media": media,
        "media_capped": capped,
    }


# --- library custody status (the sidebar's always-true status line) -------------------


def library_status(db: Path) -> dict[str, Any]:
    """Honest, catalog-driven totals for the custody strip. Zeros when the catalog is empty."""
    with Catalog(db) as catalog:
        photos = catalog.count()
        drives = [d for d in catalog.list_drives() if d["file_count"]]
        single_copy = len(catalog.single_copy_shas())
        total_bytes = sum(d["total_size"] or 0 for d in drives)
    return {
        "photos": photos,
        "places": len(drives),
        "single_copy": single_copy,
        "bytes": total_bytes,
    }


# --- layout Settings screen (template + migration) ------------------------------------


def _render_preview(template: LayoutTemplate) -> list[dict[str, Any]]:
    """The three sample files rendered through a template, for the live preview."""
    rows = []
    for context, row in zip(SAMPLE_CONTEXTS, preview(template, SAMPLE_CONTEXTS), strict=True):
        when = context.captured_at.strftime("%Y-%m-%d") if context.captured_at else "undated"
        rows.append(
            {
                "category": context.category,
                "when": when,
                "path": row.path.as_posix(),
                "warnings": list(row.warnings),
            }
        )
    return rows


def layout_state(db: Path) -> dict[str, Any]:
    """Current template, whether it is the default, the presets, and a live preview."""
    with Catalog(db) as catalog:
        stored = catalog.get_setting(LAYOUT_TEMPLATE_KEY)
    current = stored or DEFAULT_TEMPLATE_STRING
    return {
        "template": current,
        "is_default": stored is None,
        "presets": dict(PRESETS),
        "preview": _render_preview(resolve_template(stored)),
    }


def preview_layout(template_str: str) -> dict[str, Any]:
    """Validate a template and render the samples; report the error instead of raising."""
    try:
        template = LayoutTemplate.parse(template_str)
    except TemplateError as exc:
        return {"valid": False, "error": str(exc)}
    return {"valid": True, "preview": _render_preview(template)}


def set_layout(template_str: str, db: Path) -> dict[str, Any]:
    """Persist a template after validating it; returns the new :func:`layout_state` or an error."""
    try:
        LayoutTemplate.parse(template_str)
    except TemplateError as exc:
        return {"valid": False, "error": str(exc)}
    with Catalog(db) as catalog:
        catalog.set_setting(LAYOUT_TEMPLATE_KEY, template_str)
    return {"valid": True, **layout_state(db)}


def migration_preview(path: Path, db: Path) -> dict[str, Any]:
    """Preview relocating a connected drive's files to the current template (moves nothing)."""
    marker = read_marker(path)
    if marker is None:
        return {
            "ok": False,
            "error": "no .vaeon-drive.json at that path -- is the drive connected?",
        }
    with Catalog(db) as catalog:
        catalog.upsert_drive(uuid=marker.uuid, label=marker.label)
        template = resolve_template(catalog.get_setting(LAYOUT_TEMPLATE_KEY))
        outcome = run_migration(catalog, LocalDestination(path), marker.uuid, template, apply=False)
        pending = [
            d["label"]
            for d in catalog.list_drives()
            if d["uuid"] != marker.uuid and d["file_count"]
        ]
    plan = outcome.plan
    return {
        "ok": True,
        "label": marker.label,
        "template": template.template,
        "unchanged": plan.unchanged,
        "moves": [{"old": m.old_relative, "new": m.new_relative} for m in plan.moves],
        "warnings": plan.warnings,
        "pending_drives": pending,
    }


def migration_apply(path: Path, db: Path) -> JobTarget:
    """Build a job target that relocates a connected drive's files under the current template."""

    def target(progress: ProgressCallback, cancel: threading.Event) -> dict[str, Any]:
        marker = read_marker(path)
        if marker is None:
            message = "no .vaeon-drive.json at that path -- is the drive connected?"
            raise ValueError(message)
        with Catalog(db) as catalog:
            catalog.upsert_drive(uuid=marker.uuid, label=marker.label)
            template = resolve_template(catalog.get_setting(LAYOUT_TEMPLATE_KEY))
            outcome = run_migration(
                catalog,
                LocalDestination(path),
                marker.uuid,
                template,
                apply=True,
                progress=progress,
                cancel=cancel,
            )
        return {"label": marker.label, "migrated": outcome.migrated, "resumed": outcome.resumed}

    return target
