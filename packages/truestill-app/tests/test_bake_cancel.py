"""Cancelling a bake leaves every finished file correct and every unfinished one untouched.

**Why this holds, structurally rather than by luck.** The bake is deliberately per file: each
one is written, re-read from the drive, and recorded by `Catalog.record_bake` in its **own single
transaction**. There is no batch to be half-applied and no end-of-run flush, so the only states a
file can be in when the loop stops are *written and recorded* or *not written at all*.

That makes the failure this test guards for impossible **by construction** rather than by
ordering discipline - which is the point of testing it: a later refactor that batches the writes
for speed would break the property silently, and this is what would say so.

Cancel is also not a rollback. A cancelled bake keeps what it finished, exactly like a cancelled
attach or a cancelled backup: the work is real, the files are correct, and the remainder stays
pending so the next run continues rather than starting over.
"""

from __future__ import annotations

import shutil
import threading
from datetime import datetime
from pathlib import Path

import pytest
from PIL import Image
from truestill_app.service.bake import bake_run
from truestill_core.catalog import Catalog
from truestill_core.drive import create_marker
from truestill_core.hashing import sha256_file
from truestill_core.verify import CopyStatus, CopyToVerify, verify_copies

pytestmark = pytest.mark.skipif(shutil.which("exiftool") is None, reason="needs exiftool")

CONFIRMED = datetime(2011, 3, 4, 9, 15, 0)


def _library(tmp_path: Path, count: int) -> tuple[Path, Path, str]:
    db, root = tmp_path / "c.sqlite", tmp_path / "drive"
    root.mkdir()
    marker = create_marker(root, label="Everyday")
    with Catalog(db) as catalog:
        catalog.upsert_drive(uuid=marker.uuid, label=marker.label)
        for index in range(count):
            relative = f"Camera/2014/{index:02d}.jpg"
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            Image.new("RGB", (48, 32), (index * 20 % 255, 40, 90)).save(path)
            sha = sha256_file(path)
            catalog.record_uploaded(
                source_path=f"/src/{index}.jpg",
                original_name=f"{index:02d}.jpg",
                sha256=sha,
                copy_sha256=sha,
                perceptual=None,
                size=path.stat().st_size,
                captured_at="2014-08-16T10:46:26",
                category="Camera",
                relative=relative,
                drive_uuid=marker.uuid,
            )
            catalog.confirm_date(sha, CONFIRMED.isoformat(), confirmed_by="test")
    return db, root, marker.uuid


def _run_cancelling_after(root: Path, db: Path, after: int) -> dict:
    """Run the bake, setting cancel once ``after`` progress ticks have been seen."""
    target = bake_run(root, db)
    assert callable(target), f"bake_run refused: {target}"
    cancel = threading.Event()
    seen = 0

    def progress(_update: object) -> None:
        nonlocal seen
        seen += 1
        if seen >= after:
            cancel.set()

    return target(progress, cancel)


def test_a_cancelled_bake_stops_early(tmp_path: Path) -> None:
    """The fixture must really cancel mid-run, or everything below proves nothing."""
    db, root, _uuid = _library(tmp_path, 6)

    summary = _run_cancelling_after(root, db, after=2)

    assert 0 < summary["baked"] < 6, f"cancel did not land mid-run: {summary['baked']} of 6"


def test_every_file_the_cancelled_bake_finished_verifies_clean(tmp_path: Path) -> None:
    """The property per-file transactions buy: no half-written, half-recorded file exists.

    `verify` re-reads each recorded copy and compares it to `file_copies.copy_sha256`. If a
    cancel could land between the write and the record, the file would be rewritten with the old
    hash still on the row and this would report MISMATCH - truestill accusing itself again.
    """
    db, root, uuid = _library(tmp_path, 6)

    _run_cancelling_after(root, db, after=2)

    with Catalog(db) as catalog:
        copies = [CopyToVerify.from_row(r) for r in catalog.copies_on_drive(uuid)]
    statuses = {r.status for r in verify_copies(copies, root)}
    assert statuses == {CopyStatus.VERIFIED}, f"a cancelled bake left a bad copy: {statuses}"


def test_what_the_cancelled_bake_did_not_reach_is_still_pending(tmp_path: Path) -> None:
    """Not marked done, so the next run continues rather than skipping them forever.

    This is the same shape as the O2 defect: something recorded as handled that never was. Here
    the cause would be a flag set per run instead of per file.
    """
    db, root, uuid = _library(tmp_path, 6)

    summary = _run_cancelling_after(root, db, after=2)

    with Catalog(db) as catalog:
        pending = catalog.confirmations_to_bake(uuid)
    assert len(pending) == 6 - summary["baked"], "unfinished files were marked as baked"


def test_resuming_after_a_cancel_finishes_the_job(tmp_path: Path) -> None:
    """Cancel keeps what it finished; the next run does the rest and reports Done."""
    db, root, uuid = _library(tmp_path, 6)
    first = _run_cancelling_after(root, db, after=2)

    target = bake_run(root, db)
    assert callable(target)
    second = target(lambda _p: None, threading.Event())

    assert first["baked"] + second["baked"] == 6
    with Catalog(db) as catalog:
        assert catalog.confirmations_to_bake(uuid) == []
    assert second["completeness"].lower().startswith("done.")


def test_progress_ticks_for_every_item_not_only_writes(tmp_path: Path) -> None:
    """A bar that only advances on success stalls on a run of skips and reads as a hang ((oo))."""
    db, root, _uuid = _library(tmp_path, 4)
    target = bake_run(root, db)
    assert callable(target)
    ticks: list[object] = []

    target(ticks.append, threading.Event())

    assert len(ticks) == 4
