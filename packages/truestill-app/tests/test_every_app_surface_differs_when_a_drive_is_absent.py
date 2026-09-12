"""Every surface that names a drive must say something different when that drive is not here.

⚠ **THE ACCEPTANCE CRITERION, AND IT IS THE DEFECT STATED AS A TEST.** Measured on a real
external drive on 2026-09-12: `where` and `status` produced **byte-identical** output with the
drive plugged in and ejected, Find rendered a path on an unplugged drive exactly as it rendered a
reachable one, and Stats showed the absent drive with the MORE recent verification date under a
heading reading *"a verified record of where every file is safe"*.

**No hardware is needed to pin it.** `drive.drive_reach` decides from a remembered path and the
marker at it, so removing the directory makes a drive genuinely `OFFLINE` - the same code path a
pulled USB stick takes. The physical drive proved the defect; this keeps it proved.
"""

from __future__ import annotations

from pathlib import Path

from truestill_app.service import drives as drives_service
from truestill_app.service import stats as stats_service
from truestill_core.catalog import Catalog
from truestill_core.drive import create_marker, drive_path_hint
from truestill_core.hashing import sha256_file

_LIBRARY = "11111111-1111-4111-8111-111111111111"
_EXTERNAL = "22222222-2222-4222-8222-222222222222"


def _record(catalog: Catalog, source: Path, root: Path, uuid: str, label: str, body: bytes) -> str:
    """One file, copied onto ``root`` and recorded as a copy of that drive."""
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(body)
    sha = sha256_file(source)
    copy = root / "Camera" / source.name
    copy.parent.mkdir(parents=True, exist_ok=True)
    copy.write_bytes(body)
    create_marker(root, label, uuid=uuid)
    catalog.upsert_drive(uuid=uuid, label=label)
    catalog.set_setting(drive_path_hint(uuid), str(root))
    catalog.record_uploaded(
        source_path=str(source),
        original_name=source.name,
        sha256=sha,
        copy_sha256=sha,
        perceptual=None,
        size=len(body),
        captured_at=None,
        category="Camera",
        relative=f"Camera/{source.name}",
        drive_uuid=uuid,
    )
    return sha


def _world(tmp_path: Path) -> tuple[Path, Path]:
    """A library that stays, and an external drive that can be taken away.

    ``only.jpg`` is recorded on the external drive ALONE - the file that is in zero reachable
    places once it is unplugged, which is the case no stand-in folder can produce.
    """
    db = tmp_path / "catalog.sqlite"
    library, external = tmp_path / "Library", tmp_path / "AD_2TB"
    with Catalog(db) as catalog:
        shared = b"\xff\xd8shared-bytes"
        _record(catalog, tmp_path / "src/shared.jpg", library, _LIBRARY, "Library", shared)
        _record(catalog, tmp_path / "src/shared2.jpg", external, _EXTERNAL, "AD_2TB", shared)
        _record(catalog, tmp_path / "src/only.jpg", external, _EXTERNAL, "AD_2TB", b"\xff\xd8only")
    return db, external


def _eject(external: Path) -> None:
    """Take the drive away. `drive_reach` reads the marker at the remembered path, so a path that
    is no longer there is OFFLINE by the same code a pulled USB stick takes."""
    for child in sorted(external.rglob("*"), reverse=True):
        child.unlink() if child.is_file() else child.rmdir()
    external.rmdir()


def test_find_says_which_copies_cannot_be_reached(tmp_path: Path) -> None:
    """⚠ **Find's own lede promises it works when the drives are unplugged.** Before this, it
    answered with a path and no way to know the path was unreachable."""
    db, external = _world(tmp_path)

    present = drives_service.where("only.jpg", db)
    _eject(external)
    absent = drives_service.where("only.jpg", db)

    assert present["copies"], "nothing matched, so the comparison below is free"
    assert present["copies"][0]["reach"] == "connected"
    assert absent["copies"][0]["reach"] == "offline"
    assert present["copies"] != absent["copies"], "Find is identical with the drive gone"


def test_the_at_risk_row_says_whether_its_one_copy_can_be_reached(tmp_path: Path) -> None:
    """`(akp)`: the remedy cannot be right without this. A file at risk on a drive that is not
    here needs *connect it*, not *copy your library*."""
    db, external = _world(tmp_path)

    present = drives_service.at_risk(db)
    _eject(external)
    absent = drives_service.at_risk(db)

    assert [r["name"] for r in present] == ["only.jpg"], "the fixture lost its single-copy file"
    assert present[0]["reach"] == "connected"
    assert absent[0]["reach"] == "offline"
    assert present != absent


def test_stats_does_not_show_an_absent_drive_as_present(tmp_path: Path) -> None:
    """The per-drive table rendered the ejected drive identically, and with the more recent
    verification date, so it read as the better-maintained of the two."""
    db, external = _world(tmp_path)

    present = stats_service.library_stats(db)["safety"]["drives"]
    _eject(external)
    absent = stats_service.library_stats(db)["safety"]["drives"]

    def reach_for(rows: list[dict], label: str) -> str:
        return next(str(r["reach"]) for r in rows if r["label"] == label)

    assert reach_for(present, "AD_2TB") == "connected"
    assert reach_for(absent, "AD_2TB") == "offline"
    assert reach_for(absent, "Library") == "connected", "the library was collateral damage"
    assert present != absent


def test_a_drive_that_is_still_there_is_unchanged(tmp_path: Path) -> None:
    """⚠ **The anti-vacuity anchor.** Every assertion above would pass if `reach` were simply
    always `offline`. The library is never ejected, so its verdict must never move."""
    db, external = _world(tmp_path)

    before = [
        r for r in drives_service.where("shared.jpg", db)["copies"] if r["drive"] == "Library"
    ]
    _eject(external)
    after = [r for r in drives_service.where("shared.jpg", db)["copies"] if r["drive"] == "Library"]

    assert before, "the library copy vanished from the fixture"
    assert before == after, "ejecting one drive changed another drive's answer"
    assert before[0]["reach"] == "connected"
