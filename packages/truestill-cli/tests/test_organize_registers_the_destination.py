"""`truestill organize --apply` puts what it writes into custody, like the app already does.

**The gap.** `cli.py` read a drive marker and never created one, so organizing into an ordinary
folder recorded a `files` row with **no** `file_copies` row: in the dedup index, so a re-run
skips the file forever, and absent from custody, so `verify`, `status` and `where` cannot see it.
The app has done the opposite since the bug it replaced - `service/organize.py` does
`read_marker(dest) or create_marker(dest, ...)` **before** the run, with a comment saying that
doing it afterwards "would leave the run's own files unattached".

Same operation, two custody outcomes, decided by which surface the user happened to pick. Found
on the maintainer's own catalog, where 31 rows from July 2026 sit in `files` with no copy - see
`BACKLOG.md`.

`IMPLEMENTATION_STANDARDS.md` §3.1 already sanctions the creation: it "happens automatically
where the user's action already implies it", and names the organize destination. The CLI was the
outlier, not the app.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from PIL import Image
from truestill_cli.cli import main
from truestill_core.catalog import Catalog
from truestill_core.drive import MARKER_NAME, read_marker

_EXIFTOOL = pytest.mark.skipif(shutil.which("exiftool") is None, reason="exiftool not installed")


def _source(tmp_path: Path, count: int = 2) -> Path:
    src = tmp_path / "src"
    src.mkdir()
    for i in range(count):
        Image.new("RGB", (32, 32), (i + 1, 2, 3)).save(src / f"photo{i}.jpg", "JPEG")
    return src


def _orphans(db: Path) -> int:
    """`files` rows with no `file_copies` row - recorded, but invisible to custody."""
    with Catalog(db) as catalog:
        row = catalog.custody_floor()
        return int(row["no_copy"])


@_EXIFTOOL
def test_organizing_into_a_plain_folder_records_the_copies(tmp_path: Path) -> None:
    """The defect, stated as its consequence rather than as a missing call."""
    src = _source(tmp_path)
    dest = tmp_path / "plain-folder"
    db = tmp_path / "c.sqlite"

    assert main(["organize", str(src), str(dest), "--apply", "--db", str(db)]) == 0

    assert _orphans(db) == 0, (
        "files were recorded with no copy row: dedup will skip them on a re-run and verify, "
        "status and where cannot see them"
    )
    with Catalog(db) as catalog:
        assert catalog.count() == 2
        assert len(catalog.list_drives()) == 1


@_EXIFTOOL
def test_the_destination_gets_a_marker_so_it_can_be_verified(tmp_path: Path) -> None:
    """Registering is what makes the folder verifiable - §3.1's own reason for the automatic
    creation. Asserted through `verify`, which is the capability that was missing."""
    src = _source(tmp_path)
    dest = tmp_path / "plain-folder"
    db = tmp_path / "c.sqlite"

    main(["organize", str(src), str(dest), "--apply", "--db", str(db)])

    assert (dest / MARKER_NAME).exists(), "the destination was not registered"
    assert main(["verify", str(dest), "--db", str(db)]) == 0


@_EXIFTOOL
def test_a_preview_registers_nothing(tmp_path: Path) -> None:
    """Dry-run purity, and the reason no opt-out flag was added.

    A user trying Truestill against a scratch folder gets a marker only if they asked for the
    write. Without `--apply` nothing is created, nothing is recorded, and the folder is left
    exactly as it was - which is the same bargain every other write path here makes.
    """
    src = _source(tmp_path)
    dest = tmp_path / "scratch"
    db = tmp_path / "c.sqlite"

    assert main(["organize", str(src), str(dest), "--db", str(db)]) == 0

    assert not (dest / MARKER_NAME).exists(), "a preview registered the destination"
    with Catalog(db) as catalog:
        assert catalog.count() == 0


@_EXIFTOOL
def test_an_existing_marker_is_reused_and_its_identity_is_untouched(tmp_path: Path) -> None:
    """Re-registering would orphan every copy already recorded against the old uuid.

    §3.1: identity is the marker uuid, and re-minting one would "orphan every recorded copy in
    `file_copies` and under-report the custody count". The cry-wolf half of the change: it must
    create where there is nothing, and keep its hands off where there is something.
    """
    src = _source(tmp_path)
    dest = tmp_path / "driveA"
    db = tmp_path / "c.sqlite"

    main(["drives", "--init", str(dest), "--label", "Drive A", "--db", str(db)])
    before = read_marker(dest)
    assert before is not None

    main(["organize", str(src), str(dest), "--apply", "--db", str(db)])

    after = read_marker(dest)
    assert after is not None
    assert after.uuid == before.uuid, "the marker was re-minted; every recorded copy is orphaned"
    assert after.label == before.label == "Drive A", "the user's label was overwritten"
