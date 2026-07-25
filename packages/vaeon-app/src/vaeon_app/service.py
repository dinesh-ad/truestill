"""Bridge from the web layer to vaeon-core. Imports only vaeon-core -- never vaeon-cli.

Read helpers return plain dicts for JSON; long operations return :data:`JobTarget`s that the
job manager runs on a thread with progress + cancellation. Preview writes nothing (the CLI's
dry-run posture, preserved in the UI).
"""

from __future__ import annotations

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
from vaeon_core.hashing import DEFAULT_PHASH_THRESHOLD
from vaeon_core.models import Resolution
from vaeon_core.organizer import discover, execute, plan, resolve
from vaeon_core.progress import ProgressCallback
from vaeon_core.verify import CopyStatus, CopyToVerify, verify_copies

from vaeon_app.jobs import JobTarget


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _summarize(resolutions: list[Resolution]) -> dict[str, Any]:
    uploads = [r for r in resolutions if r.should_upload]
    near = [r for r in uploads if r.near_duplicate is not None]
    labels = Counter(r.decision.category.label for r in uploads)
    return {
        "files": len(resolutions),
        "new_unique": len(uploads) - len(near),
        "near_dup": len(near),
        "exact_dup": len(resolutions) - len(uploads),
        "undated": sum(1 for r in uploads if r.decision.captured_at is None),
        "folders": dict(labels.most_common()),
    }


def organize_preview(source: Path, destination: Path, db: Path) -> dict[str, Any]:
    """Plan + dedup with no writes -- the dry-run summary the UI shows before a real run."""
    files = discover(source)
    if not files:
        return {"files": 0, "folders": {}}
    metadata = read_metadata(files)
    decisions = plan(files, metadata, build_rules())
    with Catalog(db) as catalog:
        index = DedupIndex.from_catalog_rows(catalog.seed_rows(), DEFAULT_PHASH_THRESHOLD)
        resolutions = resolve(decisions, index, catalog_sizes=catalog.known_sizes())
    summary = _summarize(resolutions)
    summary["destination_is_drive"] = read_marker(destination) is not None
    return summary


def organize_run(source: Path, destination: Path, db: Path) -> JobTarget:
    """Build a job target that runs the real organize (progress across hashing then copying)."""

    def target(progress: ProgressCallback, cancel: threading.Event) -> dict[str, Any]:
        files = discover(source)
        if not files:
            return {"uploaded": 0}
        metadata = read_metadata(files)
        decisions = plan(files, metadata, build_rules())
        with Catalog(db) as catalog:
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
