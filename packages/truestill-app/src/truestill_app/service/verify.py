"""Verify: check a connected drive's copies against the catalog."""

from __future__ import annotations

import threading
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import NotRequired, TypedDict

from truestill_core.catalog import Catalog
from truestill_core.drive import read_marker
from truestill_core.progress import ProgressCallback
from truestill_core.verify import CopyStatus, CopyToVerify, verify_copies

from truestill_app.jobs import JobTarget
from truestill_app.service.drive_support import (
    DriveUnavailablePayload,
    drive_path_hint,
    drive_unavailable,
)


class VerifyProblem(TypedDict):
    status: str
    relative: str
    detail: NotRequired[str]


class VerifyJobSummary(TypedDict):
    label: str
    verified: int
    missing: int
    mismatch: int
    unreadable: int
    problems: list[VerifyProblem]
    elapsed_seconds: NotRequired[float]


def _now() -> str:
    return datetime.now(UTC).isoformat()


def verify_run(path: Path, db: Path) -> JobTarget | DriveUnavailablePayload:
    """Build a job target that verifies a connected drive's copies against the catalog.

    Soft-fails with the drive-correction payload when the path is unreachable or unmarked,
    matching migration/trips - so a stale hint never becomes a job that dies on ``OSError``.
    """
    marker = read_marker(path)
    if marker is None:
        return drive_unavailable(path)

    def target(progress: ProgressCallback, cancel: threading.Event) -> VerifyJobSummary:
        with Catalog(db) as catalog:
            catalog.upsert_drive(uuid=marker.uuid, label=marker.label)
            catalog.set_setting(drive_path_hint(marker.uuid), str(path))
            rows = catalog.copies_on_drive(marker.uuid)
            copies = [CopyToVerify(r["sha256"], r["relative"], r["copy_sha256"]) for r in rows]
            results = verify_copies(copies, path, progress=progress, cancel=cancel)
            when = _now()
            for result in results:
                if result.status is CopyStatus.VERIFIED:
                    catalog.mark_copy_verified(
                        sha256=result.copy.sha256, drive_uuid=marker.uuid, when=when
                    )
            catalog.set_drive_verified(marker.uuid, when)
        counts = Counter(r.status.value for r in results)
        problems: list[VerifyProblem] = []
        for r in results:
            if r.status is CopyStatus.VERIFIED:
                continue
            problem: VerifyProblem = {"status": r.status.value, "relative": r.copy.relative}
            if r.detail:
                problem["detail"] = r.detail
            problems.append(problem)
        return {
            "label": marker.label,
            "verified": counts.get("verified", 0),
            "missing": counts.get("missing", 0),
            "mismatch": counts.get("mismatch", 0),
            "unreadable": counts.get("unreadable", 0),
            "problems": problems,
        }

    return target
