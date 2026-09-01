"""The surface half of `(aba)`: a moved file must not be written into the catalog as absent.

🔑 **CORE BEING RIGHT IS NOT A GUARD.** `e6ef82c` shipped a correct core predicate with two
surviving mutants because the surface could stop reading it and no test noticed. Here the stakes
are higher than a printed line: `cli.py` carries

    elif result.status is CopyStatus.MISSING and still_here is not None:
        catalog.mark_copy_missing(...)

so a false `MISSING` sets ``missing_at``, which `single_copy_shas` and `custody_floor` both read.
The false alarm would not merely print - it would make the library report itself as less redundant
than it is, and that number is what stands between a user and `reclaim --apply`.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from truestill_cli.cli import main
from truestill_core.catalog import Catalog
from truestill_core.drive import create_marker, drive_path_hint
from truestill_core.hashing import sha256_file

PHOTO = b"a photograph, several bytes long" * 40


def _drive_with_one_recorded_copy(root: Path, db: Path, relative: str) -> str:
    """A registered drive holding one file, recorded at ``relative``."""
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(PHOTO)
    marker = create_marker(root, "Photos")
    sha = sha256_file(path)
    with Catalog(db) as catalog:
        catalog.upsert_drive(uuid=marker.uuid, label=marker.label)
        catalog.set_setting(drive_path_hint(marker.uuid), str(root))
        catalog.record_uploaded(
            source_path=str(path),
            original_name=path.name,
            sha256=sha,
            copy_sha256=sha,
            perceptual=None,
            size=len(PHOTO),
            captured_at=None,
            category="Camera",
            relative=relative,
            drive_uuid=marker.uuid,
        )
    return marker.uuid


def _missing_at(db: Path, uuid: str) -> object:
    with Catalog(db) as catalog:
        row = catalog._conn.execute(
            "SELECT missing_at FROM file_copies WHERE drive_uuid = ?", (uuid,)
        ).fetchone()
    return row["missing_at"]


def test_a_tidied_file_is_reported_moved_and_not_marked_missing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = tmp_path / "drive"
    db = tmp_path / "catalog.sqlite"
    uuid = _drive_with_one_recorded_copy(root, db, "Saved/a.jpg")

    tidied = root / "Trips" / "Wayanad" / "a.jpg"
    tidied.parent.mkdir(parents=True)
    (root / "Saved" / "a.jpg").rename(tidied)

    code = main(["verify", str(root), "--db", str(db)])

    out = capsys.readouterr().out
    assert "MOVED" in out, f"the tidied file was not reported as moved:\n{out}"
    assert "Trips/Wayanad/a.jpg" in out, "the place it was found must be named"
    assert "  MISSING  : 0" in out, f"a tidied file was counted as missing:\n{out}"
    assert _missing_at(db, uuid) is None, (
        "verify wrote missing_at for a file that is still on the drive - the custody claim is "
        "now short by one and nothing will correct it"
    )
    assert code == 0, "a drive that lost nothing must not exit non-zero"


def test_a_vanished_file_is_still_marked_missing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """⚠ **The regression to fear, at the surface.** A real loss must still be recorded."""
    root = tmp_path / "drive"
    db = tmp_path / "catalog.sqlite"
    uuid = _drive_with_one_recorded_copy(root, db, "Saved/a.jpg")

    (root / "Saved" / "a.jpg").unlink()

    code = main(["verify", str(root), "--db", str(db)])

    out = capsys.readouterr().out
    assert "  MISSING  : 1" in out, f"a genuinely lost file was not reported:\n{out}"
    assert _missing_at(db, uuid) is not None, "a real loss must be recorded in the catalog"
    assert code == 1, "a drive that lost a file must exit non-zero"
