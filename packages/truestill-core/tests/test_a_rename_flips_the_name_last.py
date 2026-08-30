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
from truestill_core.decisions import (
    gather_decisions,
    read_decisions,
    would_lose,
    write_decisions,
)
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


def test_the_drive_document_now_takes_the_new_name(tmp_path: Path) -> None:
    """⚠ **THE HALF STAGE 2 COULD NOT CLOSE, CLOSED IN 2b - and this test replaces the one that
    pinned the old behaviour.** `(aix)`

    Stage 2 left a rename that moved every photograph and flipped the catalog, while the drive's
    own document kept the OLD name and the user was told *"restore first"* - a remedy that would
    have brought the old name back over their rename. `would_lose` was right to refuse: `(ahz)`
    step 3 counts a **changed** value as a loss, written after a drive holding a real name was
    overwritten by a catalog holding a placeholder.

    🔑 **The guard is NOT weakened. It is given the one fact it lacked**: a per-key lease naming
    the value the renamer expects to find, so the write is a compare-and-swap rather than a force.
    `test_a_rename_leases_the_drive_document.py` is where that mechanism is pinned, including the
    rebuild that is still refused. This test is the end-to-end shape only.

    ⚠ **THE TEST IT REPLACES PASSED VACUOUSLY.** It guarded `would_lose` behind
    ``if found.decisions is not None`` and nothing in the file ever wrote a document, so the
    assertion never executed - it would have stayed green through stage 2b either way.
    `ENGINEERING_STANDARD.md` §4's fifty-fourth member: an instrument silent in the case it exists
    for. This one writes the document first, so the assertion is reached.
    """
    root, db, trip_id = _drive(tmp_path)
    with Catalog(db) as catalog:
        write_decisions(root, gather_decisions(catalog, "D1"))  # the drive, before the rename
        before = read_decisions(root).decisions
    assert before is not None, "no document was published, so this test proves nothing"
    assert [t.get("name") for t in before.trips] == ["Holiday"], (
        "the fixture did not publish a document holding the old name, so this proves nothing"
    )

    with Catalog(db) as catalog:
        apply_rename(catalog, LocalDestination(root), "D1", _plan_it(catalog, trip_id, "Corsica"))
        after, leases = gather_decisions(catalog, "D1"), catalog.authored_decisions()

    assert _name_now(db) == "Corsica", "the rename itself did not complete"
    assert would_lose(before, after, authored=leases) == (), (
        "the drive still refuses the user's own rename - stage 2b did not reach this path"
    )
    # ⚠ And without the lease it is still refused, which is the guard proving it never went away.
    assert would_lose(before, after) == ("trips",), "(ahz) step 3 stopped biting"
