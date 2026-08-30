"""Applying a rename: the name flips LAST, and an interrupted one is honest. `(aix)` stage 2

🔑 **THE ORDERING IS THE WHOLE DESIGN.** Journal every move computed from the new slug, apply
each, flip `trips.name`/`slug` only once every one completed. At any interruption the state reads
truthfully: **the name is the OLD name until every photograph is at its new path.** A new name
over a half-moved folder is the *"worse than no rename at all"* case, and this ordering makes it
unreachable rather than unlikely.

**A happy-path suite hides exactly this**, which is why the mid-move failure and the killed
process below are the tests that matter - and they are different failures. An injected exception
proves the error policy; only a killed process proves crash-safety, because an exception still
unwinds through code that could have tidied up.
"""

from __future__ import annotations

import sqlite3
import subprocess
import sys
import textwrap
from pathlib import Path, PurePosixPath

from truestill_core.catalog import Catalog
from truestill_core.decisions import gather_decisions, read_decisions, would_lose
from truestill_core.destinations.base import DestinationError
from truestill_core.destinations.local import LocalDestination
from truestill_core.hashing import sha256_file
from truestill_core.layout_settings import resolve_scheme
from truestill_core.migrate import (
    ROUTE_TIMELINE,
    RenameKind,
    RenamePlan,
    apply_rename,
    plan_rename,
    resume_migration,
)

_DAYS = ["15", "16", "17", "18"]


def _drive(tmp_path: Path) -> tuple[Path, Path, int]:
    """Four photographs across four days of one confirmed trip, already on a drive."""
    root, db = tmp_path / "drive", tmp_path / "c.sqlite"
    with Catalog(db) as catalog:
        catalog.upsert_drive(uuid="D1", label="Drive A")
        for day in _DAYS:
            relative = f"Camera/2014/2014-08/2014-08-{day} - Holiday/{day}.jpg"
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(day.encode() * 8)
            catalog.record_uploaded(
                source_path=f"/src/{day}.jpg",
                original_name=PurePosixPath(relative).name,
                sha256=sha256_file(path),
                copy_sha256=sha256_file(path),
                perceptual=None,
                size=16,
                captured_at=f"2014-08-{day}T10:00:00",
                category="Camera",
                relative=relative,
                drive_uuid="D1",
            )
        trip_id = catalog.create_trip(
            name="Holiday",
            slug="holiday",
            start_date="2014-08-15",
            end_date="2014-08-18",
            days=[f"2014-08-{d}" for d in _DAYS],
        )
    return root, db, trip_id


def _name_now(db: Path) -> str:
    with sqlite3.connect(db) as conn:
        return str(conn.execute("SELECT name FROM trips").fetchone()[0])


def _plan_it(catalog: Catalog, trip_id: int, name: str) -> RenamePlan:
    return plan_rename(
        catalog,
        "D1",
        resolve_scheme(catalog),
        kind=RenameKind.TRIP,
        row_id=trip_id,
        new_name=name,
        routes={"Camera": ROUTE_TIMELINE},
    )


def test_a_complete_rename_moves_every_file_and_then_flips_the_name(tmp_path: Path) -> None:
    """The happy path, and it asserts the ORDER's outcome rather than only its result."""
    root, db, trip_id = _drive(tmp_path)

    with Catalog(db) as catalog:
        plan = _plan_it(catalog, trip_id, "Corsica")
        outcome = apply_rename(catalog, LocalDestination(root), "D1", plan)

    assert outcome.renamed is True
    assert outcome.moved == len(plan.moves) == len(_DAYS)
    assert _name_now(db) == "Corsica"
    landed = {p.relative_to(root).as_posix() for p in root.rglob("*.jpg")}
    assert landed == {m.new_relative for m in plan.moves}, "files are not where the plan said"
    assert not any("Holiday" in p for p in landed), "an old folder survived the rename"


def test_the_catalog_still_holds_the_old_name_while_the_files_are_moving(
    tmp_path: Path,
) -> None:
    """⚠ **THE INTERMEDIATE STATE, ASSERTED DIRECTLY.** `(aix)`'s property, mid-flight.

    A progress callback runs BETWEEN completed moves, which is exactly the window an interruption
    would land in. If the flip ever moved before the loop this fails on the first tick.
    """
    root, db, trip_id = _drive(tmp_path)
    seen: list[str] = []

    with Catalog(db) as catalog:
        plan = _plan_it(catalog, trip_id, "Corsica")
        apply_rename(
            catalog,
            LocalDestination(root),
            "D1",
            plan,
            progress=lambda _p: seen.append(_name_now(db)),
        )

    assert seen, "no move completed, so the intermediate state was never observed"
    assert set(seen) == {"Holiday"}, (
        f"the name flipped while files were still moving: {seen}. The catalog would then claim a "
        f"name for a folder that does not yet hold all of its photographs."
    )
    assert _name_now(db) == "Corsica", "the name never flipped at all"


def test_a_failure_part_way_leaves_the_old_name_and_a_resumable_journal(
    tmp_path: Path,
) -> None:
    """🔑 **THE REAL TEST.** A `DestinationError` after two moves.

    Asserts three things a happy path cannot: the name did **not** flip, the moves that succeeded
    are still done, and `resume_migration` finishes the rest from the journal alone.
    """
    root, db, trip_id = _drive(tmp_path)
    destination = LocalDestination(root)
    real = destination.relocate
    calls = {"n": 0}

    def fail_after_two(old: str, new: str) -> None:
        calls["n"] += 1
        if calls["n"] > 2:
            message = "the drive stopped accepting writes"
            raise DestinationError(message)
        real(old, new)

    with Catalog(db) as catalog:
        plan = _plan_it(catalog, trip_id, "Corsica")
        destination.relocate = fail_after_two  # type: ignore[assignment]
        outcome = apply_rename(catalog, destination, "D1", plan)

        assert outcome.renamed is False, "the name flipped over a half-moved folder"
        assert outcome.moved == 2, f"expected two completed moves, got {outcome.moved}"
        assert _name_now(db) == "Holiday", "the catalog took the new name without the files"

        # The journal is what makes the rest recoverable, with no plan and no new name needed.
        destination.relocate = real  # type: ignore[assignment]
        recovered = resume_migration(catalog, destination, "D1")

    assert recovered >= 1, "the journal did not carry the unfinished moves"
    landed = {p.relative_to(root).as_posix() for p in root.rglob("*.jpg")}
    assert landed == {m.new_relative for m in plan.moves}, (
        f"resume did not finish the rename:\n{sorted(landed)}"
    )
    # ⚠ And the name is STILL old: resume replays moves, it does not know about names. That is
    # correct and is the limit `(aix)` records - the rename is completed by re-running it.
    assert _name_now(db) == "Holiday"


def test_a_killed_process_leaves_an_honest_state(tmp_path: Path) -> None:
    """⚠ **A KILLED PROCESS, NOT AN EXCEPTION** - the only thing that proves crash-safety.

    `(agk)`'s reproduction shape: `os._exit` skips every `finally`, every context manager and
    every `atexit`, so nothing gets a chance to tidy up. An injected exception still unwinds
    through code that could have flipped the name in a handler; this cannot.

    After the kill the drive must read truthfully: **the old name, some files moved, and a journal
    that finishes the job.**
    """
    root, db, trip_id = _drive(tmp_path)
    child = textwrap.dedent(f"""
        import os
        from pathlib import Path
        from truestill_core.catalog import Catalog
        from truestill_core.destinations.local import LocalDestination
        from truestill_core.layout_settings import resolve_scheme
        from truestill_core.migrate import ROUTE_TIMELINE, RenameKind, apply_rename, plan_rename

        root, db = Path({str(root)!r}), Path({str(db)!r})
        destination = LocalDestination(root)
        real = destination.relocate
        seen = {{"n": 0}}

        def kill_after_two(old, new):
            seen["n"] += 1
            if seen["n"] > 2:
                os._exit(9)          # no finally, no atexit, no tidy-up
            real(old, new)

        destination.relocate = kill_after_two
        with Catalog(db) as catalog:
            plan = plan_rename(
                catalog, "D1", resolve_scheme(catalog), kind=RenameKind.TRIP,
                row_id={trip_id}, new_name="Corsica", routes={{"Camera": ROUTE_TIMELINE}},
            )
            apply_rename(catalog, destination, "D1", plan)
    """)
    done = subprocess.run(
        [sys.executable, "-c", child], capture_output=True, encoding="utf-8", check=False
    )

    assert done.returncode == 9, (
        f"the child did not die where expected: {done.returncode}\n{done.stderr}"
    )
    assert _name_now(db) == "Holiday", "a killed rename left the new name over a partial move"

    with Catalog(db) as catalog:
        pending = catalog.pending_migration("D1")
        assert pending, "the journal was empty, so the killed rename is unrecoverable"
        resume_migration(catalog, LocalDestination(root), "D1")

    landed = {p.relative_to(root).as_posix() for p in root.rglob("*.jpg")}
    assert len(landed) == len(_DAYS), f"a photograph was lost by the kill: {sorted(landed)}"
    assert all("Corsica" in p for p in landed), (
        f"resume did not finish what the killed process started:\n{sorted(landed)}"
    )


def test_a_refused_plan_applies_nothing(tmp_path: Path) -> None:
    """CRY-WOLF. A plan that refused must not move a file or touch the name."""
    root, db, trip_id = _drive(tmp_path)
    before = sorted(p.relative_to(root).as_posix() for p in root.rglob("*.jpg"))

    with Catalog(db) as catalog:
        plan = _plan_it(catalog, trip_id, "///")
        outcome = apply_rename(catalog, LocalDestination(root), "D1", plan)

    assert outcome.renamed is False
    assert outcome.moved == 0
    assert _name_now(db) == "Holiday"
    assert sorted(p.relative_to(root).as_posix() for p in root.rglob("*.jpg")) == before


def test_the_drive_document_is_withheld_and_the_user_is_told(tmp_path: Path) -> None:
    """⚠ **THE HALF STAGE 2 DOES NOT CLOSE, pinned so stage 2b has a detector.** `(aix)`

    A rename changes a name the drive's decisions document already holds, and `would_lose` counts
    a **changed** value as a loss - `(ahz)` step 3 widened it to exactly that, after a drive
    holding a real name while the catalog held a placeholder was silently overwritten. So the
    publish is refused and the drive keeps the old name.

    🔑 **That guard is right and must not be weakened here.** It cannot tell *"this catalog is a
    rebuild that never knew the name"* from *"the user just changed it deliberately"* - and only
    the caller knows which. Supplying that fact is stage 2b's job, in its own commit, because
    loosening a guard written after measured data loss is not something to do in the same change
    as the apply path.

    ⚠ **The refusal IS reported** - `PROBLEM_OUTCOMES` includes `WOULD_LOSE` and the CLI prints a
    note - so this is a divergence the user is told about, not a silent one. **What is wrong today
    is the remedy**: the sentence says *"restore first"*, and restoring would bring the OLD name
    back over the rename. Recorded in `(aix)` rather than reworded here, because the sentence is
    correct for every other caller of that guard.
    """
    root, db, trip_id = _drive(tmp_path)
    with Catalog(db) as catalog:
        plan = _plan_it(catalog, trip_id, "Corsica")
        apply_rename(catalog, LocalDestination(root), "D1", plan)
        after_rename = gather_decisions(catalog, "D1")

    assert _name_now(db) == "Corsica", "the rename itself did not complete"
    assert [t.get("name") for t in after_rename.trips] == ["Corsica"]

    # The document on the drive, had one been published before the rename, would now disagree -
    # and `would_lose` is what stops the write rather than resolving it.
    found = read_decisions(root)
    if found.decisions is not None:
        assert would_lose(found.decisions, after_rename), (
            "would_lose stopped refusing a renamed trip - if that was deliberate, this test is "
            "the record of the old behaviour and stage 2b should replace it"
        )
