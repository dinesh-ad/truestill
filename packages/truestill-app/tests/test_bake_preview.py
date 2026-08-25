"""The bake previews before it writes, and the preview writes nothing (§5).

This is the last screen before truestill changes bytes inside a user's photos, and unlike every
other write in the product **it cannot be undone**: `-overwrite_original` replaces the metadata
in place and keeps no sidecar, so the date the file used to carry is gone. The preview therefore
has to carry everything the decision needs *before* it is taken, not afterwards in a report:

* how many files on this drive would be written;
* which confirmed **videos** are excluded, and why - shown, never omitted. A file silently
  missing from a plan is the same defect class as a silently truncated list (F46);
* which **other drives** keep the old date inside them, named, with whether each is reachable
  right now - the O2 partial-by-nature fact, moved in front of the decision;
* that it is irreversible.

**Purity is asserted across two loads.** A single load can hide a lazy first-run write - schema
creation, a settings default, a cleared stale hint - inside the baseline. The catalog is opened
once to settle that, and only then are its bytes recorded.

⚠ **WHAT A BEFORE/AFTER COMPARISON CANNOT SEE: anything already wrong when the baseline was
taken.** `(ahd)` step 1 moved four sentences into core and **paraphrased** them; the comparison
passed, because both sides carried the same wrong words. Reading the originals is what caught it.
So this technique proves a change did not alter behaviour - never that the behaviour was right -
and a move must still be checked against the text it moved, not only against its own output.
"""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

import pytest
from PIL import Image
from truestill_app.service.bake import (
    CONFIRM_WORD,
    VIDEO_EXCLUSION_REASON,
    bake_preview,
)
from truestill_app.service.drive_support import drive_path_hint
from truestill_core.catalog import Catalog
from truestill_core.drive import create_marker
from truestill_core.hashing import sha256_file

pytestmark = pytest.mark.skipif(shutil.which("exiftool") is None, reason="needs exiftool")

CONFIRMED = datetime(2011, 3, 4, 9, 15, 0)
_VIDEO_FIXTURE = (
    Path(__file__).resolve().parents[2] / "truestill-core/tests/fixtures/tiny-1frame.mp4"
)


def _library(tmp_path: Path) -> tuple[Path, Path]:
    """One photo, one video, one confirmed copy on an away drive. All dates confirmed."""
    db = tmp_path / "c.sqlite"
    here = tmp_path / "Everyday"
    here.mkdir()
    marker = create_marker(here, label="Everyday")
    with Catalog(db) as catalog:
        catalog.upsert_drive(uuid=marker.uuid, label=marker.label)
        catalog.upsert_drive(uuid="AWAY", label="Backup 2019")
        for relative, make in (
            ("Camera/2014/a.jpg", lambda p: Image.new("RGB", (48, 32), "navy").save(p)),
            ("Camera/2014/clip.mp4", lambda p: shutil.copy2(_VIDEO_FIXTURE, p)),
        ):
            path = here / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            make(path)
            sha = sha256_file(path)
            catalog.record_uploaded(
                source_path=f"/src/{Path(relative).name}",
                original_name=Path(relative).name,
                sha256=sha,
                copy_sha256=sha,
                perceptual=None,
                size=path.stat().st_size,
                captured_at="2014-08-16T10:46:26",
                category="Camera",
                relative=relative,
                drive_uuid=marker.uuid,
            )
            catalog.record_copy(
                sha256=sha, drive_uuid="AWAY", relative=relative, copy_sha256=sha, size=10
            )
            catalog.confirm_date(sha, CONFIRMED.isoformat(), confirmed_by="test")
    return db, here


# --- purity -----------------------------------------------------------------------------------


def test_the_preview_writes_nothing_to_the_catalog(tmp_path: Path) -> None:
    """§5. Two loads before the baseline, so a lazy first-run write cannot hide inside it."""
    db, here = _library(tmp_path)
    with Catalog(db):  # settle anything the first open does
        pass
    with Catalog(db):
        pass
    before = db.read_bytes()

    bake_preview(here, db)

    assert db.read_bytes() == before, "the bake preview wrote to the catalog"


def test_the_preview_writes_nothing_to_the_drive(tmp_path: Path) -> None:
    """A preview that touched the photos would be the defect the whole feature guards against."""
    db, here = _library(tmp_path)
    before = {p: p.read_bytes() for p in sorted(here.rglob("*")) if p.is_file()}

    bake_preview(here, db)

    assert {p: p.read_bytes() for p in sorted(here.rglob("*")) if p.is_file()} == before


def test_the_preview_does_not_clear_a_stale_path_hint(tmp_path: Path) -> None:
    """The subtle one: `take_live_path_hint` deletes a dead hint, which is a write.

    Correct on a screen load, wrong here. The preview reads the hint and leaves it alone, even
    when it can see the hint is stale.
    """
    db, here = _library(tmp_path)
    with Catalog(db) as catalog:
        catalog.set_setting(drive_path_hint("AWAY"), str(tmp_path / "gone"))
    with Catalog(db):
        pass
    before = db.read_bytes()

    bake_preview(here, db)

    assert db.read_bytes() == before
    with Catalog(db) as catalog:
        assert catalog.get_setting(drive_path_hint("AWAY")) == str(tmp_path / "gone")


# --- what the plan must show --------------------------------------------------------------


def test_the_preview_counts_what_this_drive_would_get(tmp_path: Path) -> None:
    db, here = _library(tmp_path)

    plan = bake_preview(here, db)

    assert plan["ok"] is True
    assert plan["drive_label"] == "Everyday"
    assert plan["will_write"] == 1  # the photo; the video is excluded below


def test_an_excluded_video_appears_in_the_plan_with_its_reason(tmp_path: Path) -> None:
    """Shown as excluded, never simply absent - the F46 rule applied to a plan."""
    db, here = _library(tmp_path)

    plan = bake_preview(here, db)

    assert plan["videos_skipped"] == 1
    assert plan["videos_reason"] == VIDEO_EXCLUSION_REASON
    assert "video" in plan["videos_reason"].lower()


def test_the_plan_names_the_drives_that_stay_catalog_only(tmp_path: Path) -> None:
    """O2's fact, moved in front of the decision instead of reported after it."""
    db, here = _library(tmp_path)

    plan = bake_preview(here, db)

    assert [d["label"] for d in plan["elsewhere"]] == ["Backup 2019"]
    assert plan["elsewhere"][0]["files"] == 2


def test_an_unreachable_drive_is_marked_not_connected(tmp_path: Path) -> None:
    """Cry-wolf half: a drive with no live hint must not be described as ready to go."""
    db, here = _library(tmp_path)

    plan = bake_preview(here, db)

    assert plan["elsewhere"][0]["connected"] is False


def test_a_reachable_drive_is_marked_connected(tmp_path: Path) -> None:
    """And the other half: a drive that really is plugged in must not be called absent."""
    db, here = _library(tmp_path)
    away = tmp_path / "Backup"
    away.mkdir()
    create_marker(away, label="Backup 2019", uuid="AWAY")
    with Catalog(db) as catalog:
        catalog.set_setting(drive_path_hint("AWAY"), str(away))

    plan = bake_preview(here, db)

    assert plan["elsewhere"][0]["connected"] is True


def test_the_plan_states_that_it_cannot_be_undone(tmp_path: Path) -> None:
    """The fact a user cannot infer: -overwrite_original keeps no sidecar, so the old date goes."""
    db, here = _library(tmp_path)

    plan = bake_preview(here, db)

    note = plan["irreversible"].lower()
    assert "cannot be undone" in note
    assert "not kept" in note


def test_the_confirm_word_is_not_shared_with_another_action(tmp_path: Path) -> None:
    """A word typed from muscle memory on the wrong screen is not a confirmation."""
    db, here = _library(tmp_path)

    plan = bake_preview(here, db)

    assert plan["confirm_word"] == CONFIRM_WORD
    assert CONFIRM_WORD not in {"undo", "clean", "move", "delete", "delete forever"}


def test_the_preview_refuses_during_a_migration_too(tmp_path: Path) -> None:
    """The gate belongs before the plan, not only before the write: a plan computed against a
    drive mid-migration would be offering work it must not do."""
    db, here = _library(tmp_path)
    with Catalog(db) as catalog:
        here_uuid = next(d["uuid"] for d in catalog.list_drives() if d["label"] == "Everyday")
        catalog.start_migration_run("run-1", here_uuid)
        catalog.record_migration_moves([("s", here_uuid, "a", "b", "s", "run-1")])

    plan = bake_preview(here, db)

    assert plan["ok"] is False
    assert plan["code"] == "MigrationUnfinished"
