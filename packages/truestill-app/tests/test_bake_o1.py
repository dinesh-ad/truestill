"""O1: a baked file verifies clean, and videos keep their date without being written.

**The worst failure this feature can have is a tool telling a user their photo is damaged
because it edited it.** `verify` re-reads each copy and compares it to `file_copies.copy_sha256`;
a bake that rewrites the bytes without updating that value in the same breath produces exactly
that lie, on a file truestill itself rewrote. So the central test here is not "did the bake
write something" - it is **confirm a date, bake it, run the real verify, assert clean**.

The read-back is the other half. The recorded hash comes from the file **on the drive** after
the write, never from a staged copy (which is not the file verify re-reads) and never from
exiftool's report (which says a write was accepted, not what the bytes now hash to).

**Videos are excluded and say so.** They keep the step-3 catalog record - the durable half that
already works - and are counted separately with a reason, rather than silently passed over.
"""

from __future__ import annotations

import shutil
import threading
from datetime import datetime
from pathlib import Path

import pytest
from PIL import Image
from truestill_app.service.bake import VIDEO_EXCLUSION_REASON, bake_run
from truestill_core.catalog import Catalog
from truestill_core.drive import create_marker
from truestill_core.exif import read_metadata
from truestill_core.hashing import sha256_file
from truestill_core.verify import CopyStatus, CopyToVerify, verify_copies

pytestmark = pytest.mark.skipif(shutil.which("exiftool") is None, reason="needs exiftool")

CONFIRMED = datetime(2011, 3, 4, 9, 15, 0)
_VIDEO_FIXTURE = (
    Path(__file__).resolve().parents[2] / "truestill-core/tests/fixtures/tiny-1frame.mp4"
)


def _jpeg(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (48, 32), "navy").save(path)


def _library(tmp_path: Path, *, with_video: bool = False) -> tuple[Path, Path, str, dict[str, str]]:
    """A registered drive holding one photo (and optionally one video), both confirmed."""
    db, root = tmp_path / "c.sqlite", tmp_path / "drive"
    root.mkdir()
    marker = create_marker(root, label="Memory Drive")
    shas: dict[str, str] = {}
    files = [("Camera/2014/a.jpg", _jpeg)]
    if with_video:
        files.append(("Camera/2014/clip.mp4", lambda p: shutil.copy2(_VIDEO_FIXTURE, p)))

    with Catalog(db) as catalog:
        catalog.upsert_drive(uuid=marker.uuid, label=marker.label)
        for relative, make in files:
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            make(path)
            sha = sha256_file(path)
            shas[relative] = sha
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
            catalog.confirm_date(sha, CONFIRMED.isoformat(), confirmed_by="test")
    return db, root, marker.uuid, shas


def _run(target: object) -> dict:
    assert callable(target), f"bake_run refused: {target}"
    return target(lambda _p: None, threading.Event())


def _verify(db: Path, root: Path, drive_uuid: str) -> dict[str, CopyStatus]:
    with Catalog(db) as catalog:
        copies = [CopyToVerify.from_row(r) for r in catalog.copies_on_drive(drive_uuid)]
    return {r.copy.relative: r.status for r in verify_copies(copies, root)}


# --- O1 ---------------------------------------------------------------------------------------


def test_a_baked_file_verifies_clean(tmp_path: Path) -> None:
    """The obligation, end to end. This failing means truestill accuses itself of corruption."""
    db, root, drive_uuid, _shas = _library(tmp_path)

    summary = _run(bake_run(root, db))

    assert summary["baked"] == 1
    assert _verify(db, root, drive_uuid) == {"Camera/2014/a.jpg": CopyStatus.VERIFIED}


def test_the_bake_actually_rewrote_the_file(tmp_path: Path) -> None:
    """Anti-vacuity: a bake that wrote nothing would also verify clean.

    Without this, `test_a_baked_file_verifies_clean` passes against a no-op implementation -
    the file is unchanged, so of course it still matches its recorded hash.
    """
    db, root, _uuid, shas = _library(tmp_path)
    before = shas["Camera/2014/a.jpg"]

    _run(bake_run(root, db))

    assert sha256_file(root / "Camera/2014/a.jpg") != before, "the bake changed no bytes"


def test_the_recorded_hash_is_the_file_on_the_drive(tmp_path: Path) -> None:
    """The read-back binding, asserted directly rather than inferred from verify passing."""
    db, root, drive_uuid, shas = _library(tmp_path)

    _run(bake_run(root, db))

    on_drive = sha256_file(root / "Camera/2014/a.jpg")
    with Catalog(db) as catalog:
        rows = {r["relative"]: r["copy_sha256"] for r in catalog.copies_on_drive(drive_uuid)}
    assert rows["Camera/2014/a.jpg"] == on_drive
    assert rows["Camera/2014/a.jpg"] != shas["Camera/2014/a.jpg"], "the pre-bake hash was kept"


def test_the_confirmed_date_is_what_landed_in_the_file(tmp_path: Path) -> None:
    """The point of the whole feature: the user's date is now in the bytes, readable by anything."""
    db, root, _uuid, _shas = _library(tmp_path)

    _run(bake_run(root, db))

    meta = read_metadata([root / "Camera/2014/a.jpg"])
    assert (
        meta[root / "Camera/2014/a.jpg"]
        .get("DateTimeOriginal", "")
        .startswith("2011:03:04 09:15:00")
    )


def test_a_second_bake_does_nothing(tmp_path: Path) -> None:
    """``baked_at`` makes the run resumable and idempotent - a re-run must not rewrite files."""
    db, root, _uuid, _shas = _library(tmp_path)
    _run(bake_run(root, db))
    after_first = sha256_file(root / "Camera/2014/a.jpg")

    second = _run(bake_run(root, db))

    assert second["baked"] == 0
    assert sha256_file(root / "Camera/2014/a.jpg") == after_first


# --- videos: excluded, counted, explained ------------------------------------------------------


def test_a_video_keeps_its_date_and_is_not_written(tmp_path: Path) -> None:
    """Excluded from the bake, **not** from the feature: the catalog record is the durable half."""
    db, root, _uuid, _shas = _library(tmp_path, with_video=True)
    video = root / "Camera/2014/clip.mp4"
    before = sha256_file(video)

    summary = _run(bake_run(root, db))

    assert summary["videos_skipped"] == 1
    assert summary["baked"] == 1, "the photo beside it must still be baked"
    assert sha256_file(video) == before, "the video was written to"
    with Catalog(db) as catalog:
        assert catalog.confirmed_date(_shas["Camera/2014/clip.mp4"]) == CONFIRMED.isoformat()
        assert catalog.find_by_sha256(_shas["Camera/2014/clip.mp4"])["captured_at"] == (
            CONFIRMED.isoformat()
        ), "step 3's durability must be untouched by the exclusion"


def test_the_video_exclusion_is_stated_not_silent(tmp_path: Path) -> None:
    """§9: a skipped outcome is counted **and named**, with a reason a user can act on."""
    db, root, _uuid, _shas = _library(tmp_path, with_video=True)

    summary = _run(bake_run(root, db))

    assert summary["videos_reason"] == VIDEO_EXCLUSION_REASON
    reason = summary["videos_reason"].lower()
    assert "date" in reason
    assert "video" in reason
    for jargon in ("atom", "makernote", "exiftool", "quicktime"):
        assert jargon not in reason, f"backend vocabulary reached the user: {jargon!r}"


def test_a_video_is_never_recorded_as_baked(tmp_path: Path) -> None:
    """It must stay pending, so lifting the exclusion later picks it up rather than skipping it."""
    db, root, _uuid, _shas = _library(tmp_path, with_video=True)

    _run(bake_run(root, db))

    with Catalog(db) as catalog:
        still_pending = [str(r["relative"]) for r in catalog.confirmations_to_bake(_uuid)]
    assert still_pending == ["Camera/2014/clip.mp4"]
