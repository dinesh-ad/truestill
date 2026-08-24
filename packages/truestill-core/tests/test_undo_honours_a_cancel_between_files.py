"""A cancelled undo stops BETWEEN files, and never mid-file. `(agl)`

**Ruled option (c) from the field**: the cancel is accepted, honoured between files, never
mid-file - the in-flight restore completes, then the run stops and reports. Option (b), declaring
undo uninterruptible, was refused: every system handling irreplaceable data accepts the cancel and
*defines what it means*. Oracle's tape library states cancellation "is not immediate" and completes
the in-progress operation before returning the tape to its source cell; IBM Spectrum Protect names
the interrupted state a **restartable restore session** and locks the file space until it is
restarted or explicitly cancelled; SQL Server's ``RESTORE WITH RESTART`` states plainly that there
is no resume. The counter-example is Windows Explorer's unresponsive Cancel on a stalled copy - a
documented complaint, and what it costs is that users stop trusting the operation.

⚠ **THE DEFECT WAS NOT THAT THE CANCEL DID NOTHING - IT WAS THAT THE SCREEN SAID IT DID.**
`jobs.py` sets ``status = "cancelled"`` from the event alone, whatever the target did, and
`app.js`'s undo `onCancelled` renders *"Restored N file(s) before you stopped it."* Every word of
that sentence was shown while the run went on to reverse every remaining file. That is
`IMPLEMENTATION_STANDARDS.md` §9's *"a cancelled run says cancelled"* inverted: the run said
cancelled and was not.

⚠ **Why the check sits at the TOP of the loop and nowhere else.** `run_undo` corrects the catalog
*after* each rename succeeds, so its docstring's guarantee - *"an interruption leaves the catalog
describing exactly the files that actually moved back"* - holds only if a stop can never land
between the two. The top of the loop is the one boundary where the pair is either wholly done or
wholly unstarted, and it is the same place `migrate.run_migration` and `migrate.undo_migration`
put theirs. `test_a_cancel_never_leaves_a_file_half_restored` is what pins it rather than the
comment.
"""

from __future__ import annotations

import json
import random
import threading
from pathlib import Path

import pytest
from PIL import Image
from truestill_cli.cli import main
from truestill_core.app_paths import record_path_for
from truestill_core.catalog import Catalog
from truestill_core.hashing import sha256_file
from truestill_core.progress import Progress
from truestill_core.run_record import record_undo
from truestill_core.undo import (
    UndoStep,
    UndoStopKind,
    outstanding,
    plan_undo,
    run_undo,
)

FILES = 4


def _jpeg(path: Path, *, seed: int) -> None:
    rng = random.Random(seed)
    image = Image.new("RGB", (64, 64))
    image.putdata(
        [(rng.randrange(256), rng.randrange(256), rng.randrange(256)) for _ in range(4096)]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, "JPEG", quality=95)


@pytest.fixture
def organized(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    """A library organized in place, so there is a run to undo."""
    lib, db = tmp_path / "lib", tmp_path / "c.sqlite"
    for i in range(FILES):
        _jpeg(lib / "Old Folder" / f"p{i}.jpg", seed=i)
    assert main(["drives", "--init", str(lib), "--label", "L", "--db", str(db)]) == 0
    monkeypatch.setattr("builtins.input", lambda _="": "move")
    assert main(["organize", str(lib), str(lib), "--in-place", "--apply", "--db", str(db)]) == 0
    return lib, db


def _cancel_after_first(cancel: threading.Event) -> object:
    """A progress callback that trips the event once one file is genuinely back.

    Progress fires **after** the rename and the catalog correction, so this reproduces the real
    interleaving: the event is set while the loop is between files, exactly as a second thread
    setting it from `/api/jobs/{id}/cancel` would.
    """

    def on_progress(_progress: Progress) -> None:
        cancel.set()

    return on_progress


def _steps(db: Path) -> list[UndoStep]:
    """The plan's steps, read once so a test can check the disk after the catalog is closed."""
    with Catalog(db) as catalog:
        return list(plan_undo(catalog).steps)


# --- the property -------------------------------------------------------------------------


def test_a_cancel_stops_the_run_between_files(organized: tuple[Path, Path]) -> None:
    """⚠ **FAILS BEFORE THE FIX** - the run reversed every file with the cancel already set."""
    _lib, db = organized
    cancel = threading.Event()
    with Catalog(db) as catalog:
        plan = plan_undo(catalog)
        assert plan.restorable == FILES, "fixture check: every file should be restorable"
        outcome = run_undo(
            catalog, plan, apply=True, cancel=cancel, progress=_cancel_after_first(cancel)
        )

    assert outcome.restored == 1, (
        f"the cancel was accepted and the run kept going: {outcome.restored} of {FILES} restored"
    )
    assert outcome.stopped is not None, "a run that stopped must say so"
    assert outcome.stopped.kind is UndoStopKind.CANCELLED
    assert outcome.stopped.never_attempted == FILES - 1


def test_a_cancel_never_leaves_a_file_half_restored(organized: tuple[Path, Path]) -> None:
    """The in-flight restore completes. Every file is at exactly one of its two paths.

    ⚠ **Both directions, because either alone passes for the wrong reason**: *neither* path
    existing is a lost file, and *both* existing is a duplicated one. The content is hashed at
    whichever path holds it, so a truncated or swapped file cannot pass as intact.
    """
    _lib, db = organized
    cancel = threading.Event()
    steps = _steps(db)
    with Catalog(db) as catalog:
        plan = plan_undo(catalog)
        run_undo(catalog, plan, apply=True, cancel=cancel, progress=_cancel_after_first(cancel))

    for step in steps:
        here, there = step.current.exists(), step.original.exists()
        assert here != there, (
            f"{step.original.name} is at {'both' if here else 'neither'} path after a cancel"
        )
        landed = step.current if here else step.original
        assert sha256_file(landed) == step.sha256, f"{landed} is not the file the row describes"


def test_a_cancel_leaves_the_catalog_describing_exactly_what_moved_back(
    organized: tuple[Path, Path],
) -> None:
    """The other half of "half-restored", and the disk alone cannot see it.

    ⚠ **WRITTEN BECAUSE A MUTATION SURVIVED.** Moving the cancel check down one line - after the
    rename, before `catalog.forget_organized` - passed every other test in this file: the file is
    at exactly one path, hashes correctly, and nothing on disk looks wrong. What it breaks is
    `run_undo`'s stated guarantee, *"the catalog describ[es] exactly the files that actually moved
    back"*: the file is home and the catalog still calls it organized on this drive, so `verify`
    would look for it at a path nothing occupies and the record undercounts what was reversed.

    So the assertion is the **agreement** between three views - the counter, the disk, and
    `file_copies` - rather than any one of them.
    """
    _lib, db = organized
    cancel = threading.Event()
    steps = _steps(db)
    with Catalog(db) as catalog:
        plan = plan_undo(catalog)
        outcome = run_undo(
            catalog, plan, apply=True, cancel=cancel, progress=_cancel_after_first(cancel)
        )
        held = {str(row["relative"]) for row in catalog.copies_on_drive(str(plan.drive_uuid))}

    home = [step for step in steps if step.original.exists()]
    assert outcome.restored == len(home), (
        f"the run counted {outcome.restored} restored and {len(home)} file(s) are actually home"
    )
    for step in home:
        relative = step.current.relative_to(plan.dest_root).as_posix()
        assert relative not in held, (
            f"{relative} was put back and the catalog still records a copy there"
        )
    for step in steps:
        if step.original.exists():
            continue
        relative = step.current.relative_to(plan.dest_root).as_posix()
        assert relative in held, f"{relative} was never reached and the catalog forgot it anyway"


def test_a_cancelled_undo_leaves_the_run_armed_so_a_second_undo_finishes_it(
    organized: tuple[Path, Path],
) -> None:
    """`(agk)`'s recovery property, under a cancel exactly as under a crash.

    IBM's restartable session is a named state; ours is `latest_undoable_run` still answering
    after the stop, and a second pass putting the rest back.

    ⚠ **The second pass does NOT close the run, and that is PRE-EXISTING rather than something
    the cancel introduced.** Measured with no cancel involved at all - restore one file by hand,
    then run a normal undo: the remaining three go back, and the already-restored row replans as
    `MOVED_AWAY`, which is `RESOLVABLE`, which is `outstanding`, which withholds
    `finish_inplace_run`. `run_undo`'s own comment promises only that *"a second undo finishes
    the job"* - putting the files back - and that is what is asserted here. Whether a run whose
    files are all home should close is a ruling about `SkipClass`, not a defect in this wiring.
    """
    _lib, db = organized
    cancel = threading.Event()
    steps = _steps(db)
    with Catalog(db) as catalog:
        first = run_undo(
            catalog,
            plan_undo(catalog),
            apply=True,
            cancel=cancel,
            progress=_cancel_after_first(cancel),
        )
        assert catalog.latest_undoable_run() is not None, "a stopped run must stay armed"

    with Catalog(db) as catalog:
        second = run_undo(catalog, plan_undo(catalog), apply=True)

    assert first.restored == 1, "the first pass stopped after the file it was in the middle of"
    assert second.restored == FILES - 1, "the second pass put back exactly what was left"
    for step in steps:
        assert step.original.exists(), f"{step.original.name} never came back"
        assert not step.current.exists(), f"{step.original.name} is still at the organized path"


def test_a_cancel_is_not_a_failure(organized: tuple[Path, Path]) -> None:
    """A cancelled undo is the user's choice. Nothing may report it as work that went wrong.

    `outstanding` decides both the exit code and whether the run closes, so a cancel leaking into
    it would spend the exit code on a deliberate act - P24's rule about which outcome the code is
    for.
    """
    _lib, db = organized
    cancel = threading.Event()
    with Catalog(db) as catalog:
        plan = plan_undo(catalog)
        outcome = run_undo(
            catalog, plan, apply=True, cancel=cancel, progress=_cancel_after_first(cancel)
        )

    assert outcome.skipped == plan.skipped, "a cancel invents no per-file skip"
    assert not outstanding(outcome.skipped), "a cancel is not outstanding work on any file"


def test_the_record_says_the_user_stopped_it_rather_than_that_it_failed(
    organized: tuple[Path, Path],
) -> None:
    """`(afw)`'s record is read weeks later, so it must not blur the two ways a run can end.

    ⚠ **WRITTEN BECAUSE A MUTATION SURVIVED**: hard-coding the block's ``kind`` to
    ``could_not_continue`` passed every record test in the tree. The record is the artefact a
    person consults when they no longer remember what happened - *"stopped"* alone leaves their
    own cancel indistinguishable from a failing drive, which is the `(afa)` shape (several facts
    sharing one word) in the document built to prevent it.
    """
    _lib, db = organized
    cancel = threading.Event()
    with Catalog(db) as catalog:
        plan = plan_undo(catalog)
        outcome = run_undo(
            catalog, plan, apply=True, cancel=cancel, progress=_cancel_after_first(cancel)
        )
    assert record_undo(db, plan, outcome) is None, "the record must write cleanly"

    payload = json.loads(record_path_for(db).read_text(encoding="utf-8"))
    stopped = payload["run"]["stopped"]

    assert stopped is not None, "a record of a stopped run must carry the stop"
    assert stopped["kind"] == UndoStopKind.CANCELLED.value, (
        f"the record calls the user's own cancel {stopped['kind']!r}"
    )
    assert stopped["never_attempted"] == FILES - 1
    assert "undo again" in stopped["reason"], "the record must name the way forward, not just stop"


# --- cry-wolf -----------------------------------------------------------------------------


def test_an_uncancelled_undo_still_restores_everything(organized: tuple[Path, Path]) -> None:
    """The half that would go red if the check fired on an untripped event."""
    _lib, db = organized
    steps = _steps(db)
    with Catalog(db) as catalog:
        outcome = run_undo(catalog, plan_undo(catalog), apply=True, cancel=threading.Event())
        assert catalog.latest_undoable_run() is None, "a complete reversal closes the run"

    assert outcome.restored == FILES
    assert outcome.stopped is None, "nothing stopped this run"
    for step in steps:
        assert step.original.exists()


def test_no_cancel_argument_at_all_is_still_a_complete_reversal(
    organized: tuple[Path, Path],
) -> None:
    """`cancel` defaults to `None`; the CLI passes nothing and must be unaffected."""
    _lib, db = organized
    with Catalog(db) as catalog:
        outcome = run_undo(catalog, plan_undo(catalog), apply=True)

    assert outcome.restored == FILES
    assert outcome.stopped is None
