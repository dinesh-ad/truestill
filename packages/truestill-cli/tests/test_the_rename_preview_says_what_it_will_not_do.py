"""`truestill rename` previews, and says so. `(aix)` stage 1.

⚠ **`(aim)`'s lesson applied BEFORE the defect rather than after it.** A list of moves with no
statement of tense reads as a report of work already done - which is exactly what
*"organized (unique): 3"* did above a run that had not happened. A rename preview that printed
paths and stopped would be the same shape on a new screen.

**And it must not promise `--apply`**, which does not exist yet: advertising a flag nobody built
is `(ail)`'s retired phantom, filed for describing a `find --duplicates` that was never there.
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath

import pytest
from truestill_cli.cli import main
from truestill_core.catalog import Catalog
from truestill_core.hashing import sha256_file


@pytest.fixture
def drive(tmp_path: Path) -> tuple[Path, Path, int]:
    root, db = tmp_path / "drive", tmp_path / "c.sqlite"
    root.mkdir()
    assert main(["drives", "--init", str(root), "--label", "Photos", "--db", str(db)]) == 0
    with Catalog(db) as catalog:
        uuid = next(d["uuid"] for d in catalog.list_drives())
        for name, day in (("a", "15"), ("b", "16")):
            relative = f"Camera/2014/2014-08/2014-08-{day} - Holiday/{name}.jpg"
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(name.encode() * 4)
            catalog.record_uploaded(
                source_path=f"/src/{name}.jpg",
                original_name=PurePosixPath(relative).name,
                sha256=sha256_file(path),
                copy_sha256=sha256_file(path),
                perceptual=None,
                size=4,
                captured_at=f"2014-08-{day}T10:00:00",
                category="Camera",
                relative=relative,
                drive_uuid=uuid,
            )
        trip_id = catalog.create_trip(
            name="Holiday",
            slug="holiday",
            start_date="2014-08-15",
            end_date="2014-08-16",
            days=["2014-08-15", "2014-08-16"],
        )
    return root, db, trip_id


def test_the_preview_states_that_nothing_was_written(
    drive: tuple[Path, Path, int], capsys: pytest.CaptureFixture[str]
) -> None:
    """THE DETECTOR. The tense is the assertion, not the move list."""
    root, db, trip_id = drive
    before = sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file())

    code = main(["rename", str(root), "trip", str(trip_id), "Corsica", "--db", str(db)])

    out = capsys.readouterr().out
    assert code == 0
    assert "Preview only - nothing was written or moved" in out, (
        "a list of moves with no statement of tense reads as work already done"
    )
    assert sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()) == before


def test_the_preview_points_at_the_flag_that_now_exists(
    drive: tuple[Path, Path, int], capsys: pytest.CaptureFixture[str]
) -> None:
    """⚠ **THIS TEST CHANGED WITH STAGE 2, AND CATCHING THAT WAS ITS JOB.**

    In stage 1 it asserted the opposite - that `--apply` was *absent*, because naming a flag
    nobody had built would be `(ail)`'s retired phantom. Stage 2 built it, and this test failed
    on the commit that did, which is a guard reporting a premise it was written to hold rather
    than a guard going stale. The sentence a preview ends with must name what is true **today**.
    """
    root, db, trip_id = drive

    main(["rename", str(root), "trip", str(trip_id), "Corsica", "--db", str(db)])

    out = capsys.readouterr().out
    assert "Re-run with --apply to rename." in out
    assert "not built yet" not in out, "the preview still says applying is unavailable"


def test_a_refusal_reaches_the_user_and_exits_non_zero(
    drive: tuple[Path, Path, int], capsys: pytest.CaptureFixture[str]
) -> None:
    """A refusal is worth nothing if it is not on screen. digiKam's loud failure, on this CLI."""
    root, db, _trip_id = drive

    code = main(["rename", str(root), "trip", "9999", "Corsica", "--db", str(db)])

    assert code == 2
    assert "no trip with that id" in capsys.readouterr().err


def test_the_preview_names_both_the_old_and_the_new_name(
    drive: tuple[Path, Path, int], capsys: pytest.CaptureFixture[str]
) -> None:
    """A user confirming a rename needs to see what it is renaming FROM.

    `(aix)` records why for events specifically: an event is a fixed member set, and the user's
    mental model is "my Corsica photos", so the surface must say which set it means.
    """
    root, db, trip_id = drive

    main(["rename", str(root), "trip", str(trip_id), "Corsica", "--db", str(db)])

    out = capsys.readouterr().out
    assert "'Holiday' -> 'Corsica'" in out
