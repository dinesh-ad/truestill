"""O2: a bake is partial by nature, and the report says so and names what is left.

``copy_sha256`` is **per drive**. Writing a confirmed date into the copy on one drive says
nothing about the copy on another, so after a bake a confirmation is *in the bytes* on one drive
and *catalog-only* on the next. Those are different promises - the first survives leaving
truestill entirely, the second survives only inside it - and a user cannot tell them apart
unless the report distinguishes them.

**The failure mode this guards is a partial run that reads as a finished one.** Listing what
succeeded and staying quiet about the rest is how someone concludes their whole library is done.

**The drives are named, not counted**, the way migrate and reclaim already name a drive they
could not reach. "2 other drives" says there is work left; "Backup 2019 and The Memory Cabinet"
says which two to plug in.

**Nothing picks the rest up automatically**, and the report says so. There is no background
sweep, and a bake writes to user files, so it stays an explicit act - which means the user has
to be told what the act is.
"""

from __future__ import annotations

import shutil
import threading
from datetime import datetime
from pathlib import Path

import pytest
from PIL import Image
from truestill_app.service.bake import bake_run, completeness_line
from truestill_core.catalog import Catalog
from truestill_core.drive import create_marker, read_marker
from truestill_core.hashing import sha256_file

pytestmark = pytest.mark.skipif(shutil.which("exiftool") is None, reason="needs exiftool")

CONFIRMED = datetime(2011, 3, 4, 9, 15, 0)
RELATIVE = "Camera/2014/a.jpg"


def _two_drives(tmp_path: Path) -> tuple[Path, Path, str]:
    """One photo, confirmed, with a copy recorded on two drives. Only the first is connected.

    The second is registered in the catalog but its folder is never handed to the bake - which
    is exactly the ordinary case: a backup drive lives in a drawer.
    """
    db = tmp_path / "c.sqlite"
    connected = tmp_path / "Everyday"
    connected.mkdir()
    here = create_marker(connected, label="Everyday")

    path = connected / RELATIVE
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (48, 32), "navy").save(path)
    sha = sha256_file(path)

    with Catalog(db) as catalog:
        catalog.upsert_drive(uuid=here.uuid, label=here.label)
        catalog.upsert_drive(uuid="AWAY-UUID", label="Backup 2019")
        catalog.record_uploaded(
            source_path="/src/a.jpg",
            original_name="a.jpg",
            sha256=sha,
            copy_sha256=sha,
            perceptual=None,
            size=path.stat().st_size,
            captured_at="2014-08-16T10:46:26",
            category="Camera",
            relative=RELATIVE,
            drive_uuid=here.uuid,
        )
        catalog.record_copy(
            sha256=sha, drive_uuid="AWAY-UUID", relative=RELATIVE, copy_sha256=sha, size=10
        )
        catalog.confirm_date(sha, CONFIRMED.isoformat(), confirmed_by="test")
    return db, connected, sha


def _run(target: object) -> dict:
    assert callable(target), f"bake_run refused: {target}"
    return target(lambda _p: None, threading.Event())


def test_the_report_names_the_drive_that_was_not_connected(tmp_path: Path) -> None:
    """The requirement, directly: named, not counted."""
    db, connected, _sha = _two_drives(tmp_path)

    summary = _run(bake_run(connected, db))

    assert summary["baked"] == 1
    assert [d["label"] for d in summary["awaiting"]] == ["Backup 2019"]
    assert summary["awaiting"][0]["files"] == 1
    assert "Backup 2019" in summary["completeness"]


def test_a_partial_bake_does_not_read_as_a_finished_one(tmp_path: Path) -> None:
    """The sentence a user actually reads must not claim completion while a drive is behind."""
    db, connected, _sha = _two_drives(tmp_path)

    summary = _run(bake_run(connected, db))

    line = summary["completeness"].lower()
    assert line.startswith("partly done"), f"a partial bake announced itself as: {line!r}"
    assert line[:5] != "done."


def test_the_report_says_what_to_do_about_the_other_drive(tmp_path: Path) -> None:
    """Nothing picks these up on its own, so the user must be told the act that does."""
    db, connected, _sha = _two_drives(tmp_path)

    line = _run(bake_run(connected, db))["completeness"].lower()

    assert "connect" in line, "the user is not told what to do"
    assert "again" in line, "the user is not told the action must be repeated per drive"


def test_the_catalog_date_is_described_as_safe_either_way(tmp_path: Path) -> None:
    """The unbaked drive is not a data-loss story, and saying so prevents a needless scare.

    Step 3's record is durable and survives every whole-disk operation. What the other drive
    lacks is the date *inside its files*, which matters only outside truestill.
    """
    db, connected, _sha = _two_drives(tmp_path)

    line = _run(bake_run(connected, db))["completeness"].lower()

    assert "safe in your library" in line


def test_a_fully_baked_library_reads_as_done(tmp_path: Path) -> None:
    """Cry-wolf half: with nothing outstanding, the report must not manufacture a caveat."""
    db, connected, sha = _two_drives(tmp_path)
    with Catalog(db) as catalog:  # the away drive gets baked by some later run
        catalog.record_bake(sha, "AWAY-UUID", copy_sha256="whatever-it-hashed-to")

    summary = _run(bake_run(connected, db))

    assert summary["awaiting"] == []
    assert summary["completeness"].lower().startswith("done.")


def test_baking_one_drive_leaves_the_other_pending(tmp_path: Path) -> None:
    """The defect this exposed: bake state is per (content, drive), not per content.

    With the flag on ``date_confirmations`` - keyed by sha256 - baking the photo here would have
    marked the confirmation handled and the copy on Backup 2019 would never have been offered
    again. It lives on ``file_copies`` beside ``copy_sha256`` for exactly this reason.
    """
    db, connected, _sha = _two_drives(tmp_path)

    _run(bake_run(connected, db))

    with Catalog(db) as catalog:
        assert [str(r["relative"]) for r in catalog.confirmations_to_bake("AWAY-UUID")] == [
            RELATIVE
        ], "the other drive's copy was marked done by a bake that never touched it"
        here = read_marker(connected)
        assert here is not None
        assert catalog.confirmations_to_bake(here.uuid) == [], (
            "the connected drive should have nothing left to bake"
        )


def test_the_wording_lists_several_drives_readably() -> None:
    """Two or more drives must read as a sentence, not a debug dump."""
    line = completeness_line(
        "Everyday",
        3,
        [{"label": "Backup 2019", "files": 2}, {"label": "The Memory Cabinet", "files": 40}],
    )

    assert "Backup 2019 (2 files) and The Memory Cabinet (40 files)" in line


def test_a_single_file_is_not_called_files() -> None:
    """Plural correctness, per (ccc) - the same rule the rest of the app follows."""
    line = completeness_line("Everyday", 1, [{"label": "Backup 2019", "files": 1}])

    assert "(1 file)" in line
    assert "(1 files)" not in line
