"""An interrupted copy-mode organize leaves a record, so a half-library cannot read as a whole one.

`(aem)`, found by the first soak. A `kill -9` mid-organize left **340 of 4,105** files. Between the
kill and the restart::

    D3   340   611.4   connected   2026-08-20T09:03:48   never

and `status` reported normally. ⚠ **Nothing said a run had been interrupted.** The catalog was
internally consistent and therefore serene - 340 rows, 340 complete files, agreeing exactly - and
indistinguishable from a small library that is finished.

**This is the one surface of `(aej)` that no wording could repair.** The other three printed
something other than what they held; here the fact did not exist. Three run-shaped tables exist -
`inplace_runs`, `migration_runs`, `reclaim_journal` - and all three attach to a different mechanism.
A plain copy opened nothing.

⚠ **`intended_total` is what the DRIVE WILL HOLD when the run completes, not what this run will
write**, and that distinction is what makes the crash window closeable::

                        writes this run     drive holds after
    first run                 4,105              4,105
    restart after a kill      3,765              4,105

Recording *"files this run will write"* gives two denominators and nothing lines up across the
restart. Recording *"what the drive will hold"* gives 4,105 both times.

**And "interrupted" is DERIVED, never read from a status column**: a record exists AND the drive
holds fewer than `intended_total`. So a crash between the last file and the close reads as
**complete**, which is correct - the close is an optimisation, not a correctness requirement. That
is `migrate`'s own immunity to the same window, where the report is driven by pending journal rows
rather than by a flag.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from truestill_core.catalog import Catalog
from truestill_core.dedup import DedupIndex
from truestill_core.destinations import LocalDestination
from truestill_core.exif import read_metadata
from truestill_core.organizer import discover, execute, plan, resolve, write_candidates

_DRIVE = "drive-under-test"


def _organize(source: Path, out: Path, db: Path, *, stop_after: int | None = None) -> None:
    """One organize run into a registered drive, optionally abandoned part-way.

    `stop_after` models the kill: the run records its intent, writes that many files, and then
    simply stops - no close, exactly as a `SIGKILL` leaves it.
    """
    files = discover(source)
    metadata = read_metadata(files)
    decisions = plan(files, metadata)
    with Catalog(db) as catalog:
        catalog.upsert_drive(uuid=_DRIVE, label="D")
        on_destination = {
            str(r["sha256"]): str(r["relative"]) for r in catalog.copies_on_drive(_DRIVE)
        }
        index = DedupIndex.from_catalog_rows(catalog.seed_rows(), threshold=10)
        resolutions = resolve(
            decisions, index, catalog_sizes=catalog.known_sizes(), on_destination=on_destination
        )
        # The two halves of the denominator, both already in hand: what the drive holds now, and
        # what this run intends to add. Their sum is stable across a restart.
        catalog.start_organize_run(
            drive_uuid=_DRIVE,
            run_id=f"run-{stop_after}",
            intended_total=len(on_destination)
            + len(write_candidates(resolutions, skip_undated=False)),
        )
        if stop_after is not None:
            resolutions = resolutions[:stop_after]
        execute(resolutions, LocalDestination(out), catalog, apply=True, drive_uuid=_DRIVE)
        if stop_after is None:
            catalog.finish_organize_run(_DRIVE)


def _sources(root: Path, gradient_png: Path, count: int) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    for n in range(count):
        target = root / f"photo{n}.png"
        shutil.copy(gradient_png, target)
        # Distinct bytes, so none is deduplicated away and the counts are the counts.
        with target.open("ab") as handle:
            handle.write(f"{n}".encode())
    return root


def test_an_interrupted_run_is_reported_as_interrupted(tmp_path: Path, gradient_png: Path) -> None:
    """⚠ THE REGRESSION, IN THE SOAK'S SHAPE. Today there is nothing to report.

    Six files intended, two written, then the process dies. The drive must not read as a complete
    two-file library.
    """
    source = _sources(tmp_path / "src", gradient_png, 6)
    db = tmp_path / "c.sqlite"

    _organize(source, tmp_path / "D", db, stop_after=2)

    with Catalog(db) as catalog:
        run = catalog.unfinished_organize_run(_DRIVE)

    assert run is not None, (
        "a run was interrupted after writing 2 of 6 files and the catalog holds no record of it. "
        "340 rows are then indistinguishable from a finished 340-file library. `(aem)`."
    )
    assert run["intended_total"] == 6, f"the denominator is wrong: {dict(run)}"
    assert run["achieved"] == 2, f"the numerator is wrong: {dict(run)}"


def test_the_denominator_survives_the_restart(tmp_path: Path, gradient_png: Path) -> None:
    """⚠ THE REASON `intended_total` IS TARGET HOLDINGS AND NOT THIS RUN'S WRITES.

    The restart's own intended write count is 4, not 6, because the two already on the drive are
    correctly excluded. Recorded as target holdings, both runs record **6** and the numbers line
    up across the interruption.
    """
    source = _sources(tmp_path / "src", gradient_png, 6)
    db = tmp_path / "c.sqlite"

    _organize(source, tmp_path / "D", db, stop_after=2)
    with Catalog(db) as catalog:
        first = catalog.unfinished_organize_run(_DRIVE)["intended_total"]

    _organize(source, tmp_path / "D", db)
    with Catalog(db) as catalog:
        assert catalog.unfinished_organize_run(_DRIVE) is None, (
            "a completed run still reads as open"
        )

    assert first == 6, "the killed run's denominator must be the drive's target, not its writes"


def test_a_crash_between_the_last_file_and_the_close_reads_as_complete(
    tmp_path: Path, gradient_png: Path
) -> None:
    """⚠ THE WINDOW A START-WRITE DESIGN GETS WRONG IF NOBODY THINKS ABOUT IT.

    The record is opened before the first byte and closed after the last. A crash in between
    leaves `completed_at` NULL on a run that actually finished - and reporting that as interrupted
    would be a false alarm on every unlucky exit.

    **So the reading is derived, never taken from the flag**: the drive holds everything the run
    intended, so the run finished, whatever the row says. This is `migrate`'s immunity to its own
    identical window, where `resume_migration` reports `len(pending)` rather than a status.
    """
    source = _sources(tmp_path / "src", gradient_png, 3)
    db = tmp_path / "c.sqlite"

    # Every file written, and the close deliberately never happens.
    _organize(source, tmp_path / "D", db, stop_after=3)

    with Catalog(db) as catalog:
        assert catalog.unfinished_organize_run(_DRIVE) is None, (
            "a run that wrote everything it intended was reported as interrupted because its "
            "close was lost. The close must be an optimisation, not a correctness requirement."
        )


def test_a_second_run_supersedes_rather_than_accumulating(
    tmp_path: Path, gradient_png: Path
) -> None:
    """One row per drive, on `start_migration_run`'s bound: *"exactly one run's worth ... always
    the newest"*. Growth is bounded without a timer, and it answers how long an open row stays
    believable - it is replaced by the next run against that drive."""
    source = _sources(tmp_path / "src", gradient_png, 6)
    db = tmp_path / "c.sqlite"

    _organize(source, tmp_path / "D", db, stop_after=1)
    _organize(source, tmp_path / "D", db, stop_after=2)

    with Catalog(db) as catalog:
        rows = list(catalog._conn.execute("SELECT COUNT(*) AS n FROM organize_runs"))
    assert rows[0]["n"] == 1, "interrupted runs accumulated one row per attempt"


def test_an_ordinary_completed_run_reports_nothing_unusual(
    tmp_path: Path, gradient_png: Path
) -> None:
    """⚠ THE CRY-WOLF HALF. A small library that simply IS three files must not be called
    interrupted - which is the whole failure mode this entry is about, inverted."""
    source = _sources(tmp_path / "src", gradient_png, 3)
    db = tmp_path / "c.sqlite"

    _organize(source, tmp_path / "D", db)

    with Catalog(db) as catalog:
        assert catalog.unfinished_organize_run(_DRIVE) is None


def test_a_completed_run_does_not_become_interrupted_when_files_are_deleted_later(
    tmp_path: Path, gradient_png: Path
) -> None:
    """⚠ A BUG IN THIS DESIGN, FOUND BY MUTATION AFTER IT WAS BUILT, AND IT IS THE SOAK'S S5.

    Deriving "interrupted" purely from `achieved < intended_total` is right for the crash window
    and **wrong afterwards**: a run that completed correctly begins claiming it was interrupted the
    moment a file is deleted by hand, because `achieved` falls for a reason that has nothing to do
    with the run. The soak deleted seven organized files precisely to test verify; that scenario
    would have made every finished drive start lying.

    So a **closed** run is finished whatever the drive holds now, and the derivation covers only
    the open case. Both conditions are load-bearing and neither is redundant - which mutation is
    what proved: replacing the derivation with the flag alone survived every test, because no
    fixture had a closed run whose holdings later fell.
    """
    source = _sources(tmp_path / "src", gradient_png, 3)
    db = tmp_path / "c.sqlite"

    _organize(source, tmp_path / "D", db)
    with Catalog(db) as catalog:
        assert catalog.unfinished_organize_run(_DRIVE) is None, "a completed run reads as open"
        # A file leaves the drive afterwards - deleted by hand, or found missing by a verify.
        doomed = catalog._conn.execute(
            "SELECT sha256 FROM file_copies WHERE drive_uuid = ?", (_DRIVE,)
        ).fetchone()["sha256"]
        catalog._conn.execute(
            "DELETE FROM file_copies WHERE drive_uuid = ? AND sha256 = ?", (_DRIVE, doomed)
        )
        catalog._conn.commit()

        assert catalog.unfinished_organize_run(_DRIVE) is None, (
            "a run that FINISHED now claims it was interrupted, because a file was deleted after "
            "it. The run's completion is a fact about the run, not about what the drive holds "
            "today."
        )
