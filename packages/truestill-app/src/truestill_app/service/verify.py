"""Verify: check a connected drive's copies against the catalog, and REMEMBER what it found.

**A check dates the custody claim only for what it actually confirmed** (`(abg)` Stage 2). This
used to stamp ``drives.last_verified`` unconditionally at the end of every run, and Stage 1 had
just carried that date to the sentence a person reads - so a run whose own summary said
``missing: 2269`` reported the claim as checked today. The date is now derived from the copies by
:meth:`~truestill_core.catalog.Catalog.refresh_drive_verified`, on `custody_freshness`'s
weakest-leg rule.

**Only MISSING is persisted**, and the other two failures are deliberately not folded into it:
``UNREADABLE`` is an EIO or a permission, which is *we could not look*, and ``MISMATCH`` is a
drive that still holds something at that path. Different facts need different words - `(ach)`.

**Two preconditions this relies on are already structural. Do not build them again, and do not
"fix" the second:**

* A negative can only be produced for a drive that identified itself, because `verify_run` starts
  by reading the marker and soft-fails without one. The cloud-mount case that motivated `(abg)` -
  where *gone* and *unplugged* are indistinguishable - cannot reach this code at all.
* `verify_copies` answers every ``MISSING`` in ``_partition``, **before any hashing starts**, so a
  run the user cancels still has a complete set of absences rather than a truncated one. That is
  counter-intuitive and it is what makes persisting from a cancelled run sound.

The one window that is not structural is a drive pulled out mid-run, whose remaining copies would
all read as absent - so the marker is re-read after the run and negatives are dropped if it is
gone.
"""

from __future__ import annotations

import threading
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import NotRequired, TypedDict

from truestill_core.catalog_session import open_catalog
from truestill_core.drive import read_marker, remember_drive_path, second_location_for
from truestill_core.progress import ProgressCallback
from truestill_core.verify import CopyStatus, CopyToVerify, verify_copies

from truestill_app.jobs import JobTarget
from truestill_app.service.drive_support import (
    DriveUnavailablePayload,
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
    #: Present and readable, but no recorded hash to check against. Its own count so a drive
    #: of such copies cannot report four zeros and read as a clean verify (§9).
    unverifiable: int
    problems: list[VerifyProblem]
    #: Whether the drive is clean. `(aiq)`; matches `_cmd_verify`'s exit-1 condition exactly.
    finished_clean: bool
    elapsed_seconds: NotRequired[float]
    #: Set only when this drive's identity also answers at a second live path. `(adx)` gap 1: the
    #: catalog counts both places as one drive, so its custody claim is short by one - the only
    #: direction in which under-reporting gets a user to delete a copy they still needed.
    second_location: NotRequired[str]


def _now() -> str:
    return datetime.now(UTC).isoformat()


def verify_run(path: Path, db: Path) -> JobTarget[VerifyJobSummary] | DriveUnavailablePayload:
    """Build a job target that verifies a connected drive's copies against the catalog.

    Soft-fails with the drive-correction payload when the path is unreachable or unmarked,
    matching migration/trips - so a stale hint never becomes a job that dies on ``OSError``.
    """
    marker = read_marker(path)
    if marker is None:
        return drive_unavailable(path, db)

    def target(progress: ProgressCallback, cancel: threading.Event) -> VerifyJobSummary:
        with open_catalog(db) as catalog:
            # ⚠ BEFORE BOTH WRITES BELOW, and that ordering is the contract. `upsert_drive`
            # refreshes `last_seen` and the hint write replaces the remembered path - the two
            # halves of the evidence, destroyed one line apart. `(adx)`.
            second_place = second_location_for(
                catalog, uuid=marker.uuid, label=marker.label, here=path
            )
            catalog.upsert_drive(uuid=marker.uuid, label=marker.label)
            remember_drive_path(catalog, marker.uuid, path)
            rows = catalog.copies_on_drive(marker.uuid)
            copies = [CopyToVerify.from_row(r) for r in rows]
            results = verify_copies(copies, path, progress=progress, cancel=cancel)
            when = _now()
            still_here = read_marker(path)
            for result in results:
                if result.status is CopyStatus.VERIFIED:
                    catalog.mark_copy_verified(
                        sha256=result.copy.sha256, drive_uuid=marker.uuid, when=when
                    )
                elif result.status is CopyStatus.MISSING and still_here is not None:
                    catalog.mark_copy_missing(
                        sha256=result.copy.sha256, drive_uuid=marker.uuid, when=when
                    )
            catalog.refresh_drive_verified(marker.uuid)
        counts = Counter(r.status.value for r in results)
        problems: list[VerifyProblem] = []
        for r in results:
            if r.status is CopyStatus.VERIFIED:
                continue
            problem: VerifyProblem = {"status": r.status.value, "relative": r.copy.relative}
            if r.detail:
                problem["detail"] = r.detail
            problems.append(problem)
        summary: VerifyJobSummary = {
            "label": marker.label,
            "verified": counts.get("verified", 0),
            "missing": counts.get("missing", 0),
            "mismatch": counts.get("mismatch", 0),
            "unreadable": counts.get("unreadable", 0),
            "unverifiable": counts.get("unverifiable", 0),
            "problems": problems,
            # 🔑 **`(aiq)`. A FINDING, not a failure of the run - and it still counts as
            # unclean, because that is the line the CLI already draws.** `_cmd_verify` returns
            # `1 if (missing or mismatch or unreadable)`, so a verify that does its job
            # perfectly and finds seven missing files is a non-zero exit there while the app
            # said "done". ⚠ `unverifiable` is deliberately NOT here: it means no recorded hash
            # to check against, a gap in the catalog rather than damage on the drive, and the
            # CLI does not exit 1 for it either.
            "finished_clean": not (
                counts.get("missing", 0) or counts.get("mismatch", 0) or counts.get("unreadable", 0)
            ),
        }
        # Absent rather than empty when there is nothing to say, so a screen can test presence.
        if second_place is not None:
            summary["second_location"] = second_place
        return summary

    return target
