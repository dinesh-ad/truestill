"""A migration counts and names a bad file, and stops only for a condition that outlives it.

`(agi)`'s ruled policy arriving on the **fifth** surface and the fourth to get it: *"one bad file
never aborts a batch"* (`ENGINEERING_STANDARD.md` §4 Errors), and a condition that will hit the
next file too must stop the run. `organizer.execute`, `service/backup.py` and `undo.run_undo` all
call `persists_for_the_run`; `migrate.run_migration` did not.

⚠ **THE ROOT CAUSE WAS A DISCARDED `__cause__`, NOT A MISSING TRY/EXCEPT.** `_matches` caught the
`DestinationError` that `LocalDestination.checksum` raises **with its `OSError` chained**
(`destinations/local.py:258`, `from exc`) and returned a bare `False`. So by the time
`_apply_move` raised *"verification failed after relocating to ..."* there was nothing left to
classify, and `drive_unwritable.persists_for_the_run` - which walks `__cause__` looking for an
`OSError` - answered `False` for a **failing drive**. Adding a `try/except` around `_apply_move`
without repairing that chain would have produced a handler that classified every I/O failure as a
one-file problem, which is the `(agi)` defect wearing a fix.

⚠ **AND ONE FAILURE GENUINELY HAS NO CAUSE TO CHAIN**: the destination is readable and simply
returns bytes that are not what was written. `VerificationFailedError` names it, so it is classified by
**type** rather than by matching the message text - `IMPLEMENTATION_STANDARDS.md` §9's rule about
matching on an exception name.
"""

from __future__ import annotations

import errno
import threading
from dataclasses import MISSING, fields
from pathlib import Path, PurePosixPath
from typing import Final

import pytest
from truestill_cli.cli import _report_migration_shortfall
from truestill_core.catalog import Catalog
from truestill_core.destinations.base import DestinationError
from truestill_core.destinations.local import LocalDestination
from truestill_core.drive_unwritable import persists_for_the_run
from truestill_core.hashing import sha256_file
from truestill_core.layout import LayoutScheme, LayoutTemplate
from truestill_core.migrate import (
    CANCELLED_REASON,
    MigrationOutcome,
    MigrationPlan,
    MigrationStop,
    MigrationStopKind,
    run_migration,
)
from truestill_core.progress import Phase, Progress, ProgressCallback
from truestill_core.undo import UndoStop

_DDL = "{category}/{yyyy}"  # drops the month the default adds -> every dated file must move


def _scheme() -> LayoutScheme:
    parsed = LayoutTemplate.parse(_DDL)
    return LayoutScheme.of(timeline=parsed, timeline_evented=parsed, side_bin=parsed)


def _seed(catalog: Catalog, root: Path, count: int) -> None:
    catalog.upsert_drive(uuid="D1", label="Drive A")
    for index in range(count):
        relative = f"Camera/2023/08/p{index}.jpg"
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(f"content-{index}".encode())
        catalog.record_uploaded(
            source_path=f"/src/p{index}.jpg",
            original_name=f"p{index}.jpg",
            sha256=sha256_file(path),
            copy_sha256=sha256_file(path),
            perceptual=None,
            size=path.stat().st_size,
            captured_at="2023-08-20T14:30:00",
            category="Camera",
            relative=relative,
            drive_uuid="D1",
        )


class _RaisesOnChecksum(LocalDestination):
    """A drive whose reads fail. The `OSError` is chained exactly as the real backend chains it."""

    def __init__(self, root: Path, *, code: int, only: str | None = None) -> None:
        super().__init__(root)
        self._code = code
        self._only = only

    def checksum(self, relative_path: str) -> str:
        hit = self._only is None or PurePosixPath(relative_path).name == self._only
        if hit:
            reason = OSError(self._code, "injected")
            message = f"cannot checksum {relative_path!r}: {reason}"
            raise DestinationError(message) from reason
        return super().checksum(relative_path)


class _ReturnsWrongBytes(LocalDestination):
    """A drive that reads fine and stores something other than what it was given."""

    def checksum(self, _relative_path: str) -> str:
        return "0" * 64


# --- the property -------------------------------------------------------------------------


def test_a_failing_drive_stops_the_run_instead_of_failing_every_file(tmp_path: Path) -> None:
    """⚠ **FAILS BEFORE THE FIX** - the bare `DestinationError` escaped `run_migration`."""
    root = tmp_path / "drive"
    with Catalog(tmp_path / "c.sqlite") as catalog:
        _seed(catalog, root, 4)
        outcome = run_migration(
            catalog, _RaisesOnChecksum(root, code=errno.EIO), "D1", _scheme(), apply=True
        )

    assert outcome.stopped is not None, "a failing drive must stop the run, not raise past it"
    assert outcome.stopped.kind is MigrationStopKind.COULD_NOT_CONTINUE
    assert outcome.migrated == 0
    assert len(outcome.refused) == 1, "the file it died on is named once, not four times"
    assert outcome.stopped.never_attempted == 3


def test_one_bad_file_is_counted_and_named_and_the_rest_still_move(tmp_path: Path) -> None:
    """§4 Errors: one bad file never aborts a batch. `ENOENT` is one file somebody moved."""
    root = tmp_path / "drive"
    with Catalog(tmp_path / "c.sqlite") as catalog:
        _seed(catalog, root, 4)
        outcome = run_migration(
            catalog,
            _RaisesOnChecksum(root, code=errno.ENOENT, only="p1.jpg"),
            "D1",
            _scheme(),
            apply=True,
        )

    assert outcome.stopped is None, "a single vanished file is not a reason to stop"
    assert outcome.migrated == 3
    assert [name for name, _reason in outcome.refused] == ["Camera/2023/p1.jpg"]
    assert outcome.refused[0][1], "a refusal without a reason is a silent skip"


def test_a_destination_that_stores_wrong_bytes_stops_the_run(tmp_path: Path) -> None:
    """The failure with **no cause to chain**, and the reason `VerificationFailedError` has a name.

    Nothing raised: the drive read back cleanly and returned a hash that is not what was written.
    That is a statement about the destination, not about this file - every remaining file would
    be written to the same place - so it is persistent by classification rather than by counting
    strikes. See the module docstring for why a threshold was considered and refused.
    """
    root = tmp_path / "drive"
    with Catalog(tmp_path / "c.sqlite") as catalog:
        _seed(catalog, root, 4)
        outcome = run_migration(catalog, _ReturnsWrongBytes(root), "D1", _scheme(), apply=True)

    assert outcome.stopped is not None
    assert outcome.stopped.kind is MigrationStopKind.COULD_NOT_CONTINUE
    assert outcome.migrated == 0
    assert len(outcome.refused) == 1, "it stops on the first one rather than proving it four times"


def test_the_cause_survives_matches_so_a_failing_drive_can_be_classified(tmp_path: Path) -> None:
    """The root cause, asserted directly rather than only through its consequence.

    `_matches` returned `False` for *"could not be read"* and for *"does not match"* alike, and
    `persists_for_the_run` walks `__cause__`. With the chain broken it answered `False` for
    `EIO`; the run then continued into a drive that had already given up.
    """
    root = tmp_path / "drive"
    root.mkdir()
    (root / "a.jpg").write_bytes(b"x")
    destination = _RaisesOnChecksum(root, code=errno.EIO)

    with pytest.raises(DestinationError) as caught:
        destination.checksum("a.jpg")

    assert persists_for_the_run(caught.value), (
        "the chained OSError must survive to be classified - a bare False here is the defect"
    )


# --- cry-wolf -----------------------------------------------------------------------------


def test_a_clean_migration_moves_everything_and_stops_nothing(tmp_path: Path) -> None:
    """The half that goes red if the handler fires on a healthy run."""
    root = tmp_path / "drive"
    with Catalog(tmp_path / "c.sqlite") as catalog:
        _seed(catalog, root, 4)
        outcome = run_migration(catalog, LocalDestination(root), "D1", _scheme(), apply=True)

    assert outcome.migrated == 4
    assert outcome.stopped is None
    assert outcome.refused == []
    assert catalog_is_drained(tmp_path / "c.sqlite")


def catalog_is_drained(db: Path) -> bool:
    with Catalog(db) as catalog:
        return catalog.pending_migration("D1") == []


def test_a_preview_neither_stops_nor_refuses(tmp_path: Path) -> None:
    """A preview never enters the loop, so it can report neither - and must not invent them."""
    root = tmp_path / "drive"
    with Catalog(tmp_path / "c.sqlite") as catalog:
        _seed(catalog, root, 4)
        outcome = run_migration(catalog, _ReturnsWrongBytes(root), "D1", _scheme(), apply=False)

    assert outcome.applied is False
    assert outcome.stopped is None
    assert outcome.refused == []


# --- the re-run, which is what the ruling rests on -----------------------------------------


class _FailsUntilCleared(LocalDestination):
    """A drive that fails one named file until the flag is cleared, then behaves.

    Models the only thing that makes *stop* safer than *abort*: the condition is **transient in
    the user's hands** - they reconnect the drive, clear the path, free the space - and run again.
    """

    def __init__(self, root: Path, *, only: str) -> None:
        super().__init__(root)
        self._only = only
        self.failing = True

    def checksum(self, relative_path: str) -> str:
        if self.failing and PurePosixPath(relative_path).name == self._only:
            reason = OSError(errno.ENOENT, "injected")
            message = f"cannot checksum {relative_path!r}: {reason}"
            raise DestinationError(message) from reason
        return super().checksum(relative_path)


def test_a_second_migration_finishes_what_a_refusal_left(tmp_path: Path) -> None:
    """⚠ **THIS PINS THE RULING `(agm)` RESTS ON**, and it is the reason this file exists.

    The ruling is *stop and report, never abort*, and its whole justification is one sentence:
    **"the journal keeps those moves and a re-run clears them."** That sentence was written into
    `run_migration`'s loop as a comment and asserted nowhere - so the argument for the policy was
    the one thing nothing checked. `ENGINEERING_STANDARD.md` §4 requires an idempotency/re-run
    test *"wherever state is touched"*, and this touches the journal, the catalog and the disk.

    ⚠ **Named as a ruling test on purpose.** A later reader seeing three migrations in one
    function will read it as redundant with the idempotency test in `test_migrate.py` and delete
    it. That one proves a **clean** re-run changes nothing; this proves a **refused** one
    converges, which is a different claim and the load-bearing one.
    """
    root = tmp_path / "drive"
    db = tmp_path / "c.sqlite"
    destination = _FailsUntilCleared(root, only="p1.jpg")
    with Catalog(db) as catalog:
        _seed(catalog, root, 4)
        first = run_migration(catalog, destination, "D1", _scheme(), apply=True)

    assert first.migrated == 3
    assert len(first.refused) == 1
    with Catalog(db) as catalog:
        assert catalog.pending_migration("D1"), (
            "a refused move must stay in the journal, or the re-run has nothing to work from"
        )

    destination.failing = False
    with Catalog(db) as catalog:
        second = run_migration(catalog, destination, "D1", _scheme(), apply=True)

    assert second.refused == [], "the second pass had nothing left to refuse"
    # ⚠ **The re-run finishes it through `resumed`, not `migrated`, and that is the mechanism
    # the ruling names.** By the second pass the plan is empty - every file is already at its
    # target path as far as `plan_migration` can see - so the only thing that can finish the
    # refused move is `resume_migration` reading the journal row the first run left. A test
    # asserting `migrated` would have been asserting the wrong half of the claim.
    assert second.resumed == 1, "the pending journal row is what the second run picks up"
    assert second.migrated == 0, "and it needs no new plan to do it"
    for index in range(4):
        assert (root / f"Camera/2023/p{index}.jpg").exists(), f"p{index} never arrived"
        assert not (root / f"Camera/2023/08/p{index}.jpg").exists(), f"p{index} left an orphan"
    assert catalog_is_drained(db), "and the journal drains once nothing is outstanding"


def test_a_second_migration_finishes_what_a_stop_left(tmp_path: Path) -> None:
    """The same convergence after the run stopped rather than skipped one file.

    A stop leaves moves **never attempted**, not merely refused, so this is the wider half: the
    journal must carry rows the first run never looked at.
    """
    root = tmp_path / "drive"
    db = tmp_path / "c.sqlite"
    destination = _FailsUntilCleared(root, only="p0.jpg")
    with Catalog(db) as catalog:
        _seed(catalog, root, 4)
        # ENOENT on the FIRST file is a refusal, not a stop; force the stop with EIO instead.
        stopped = run_migration(
            catalog, _RaisesOnChecksum(root, code=errno.EIO), "D1", _scheme(), apply=True
        )
        assert stopped.stopped is not None, "fixture check: this run must have stopped"
        assert stopped.migrated == 0

    destination.failing = False
    with Catalog(db) as catalog:
        after = run_migration(catalog, destination, "D1", _scheme(), apply=True)

    assert after.resumed == 4, "every move the stop never reached is recovered from the journal"
    assert after.stopped is None
    for index in range(4):
        assert (root / f"Camera/2023/p{index}.jpg").exists(), f"p{index} never arrived"
    assert catalog_is_drained(db), "and the journal drains once the work is done"


def test_a_refused_move_stays_in_the_journal_for_the_re_run(tmp_path: Path) -> None:
    """A refused move keeps its journal row, which is what makes the re-run above possible.

    ⚠ **THIS ASSERTS THE JOURNAL, NOT THE RUN RECORD, AND THE DIFFERENCE WAS FOUND BY A
    MUTATION.** The first draft was called *"a refusal keeps the run open"* and aimed at
    `run_migration`'s close condition (`if migrated == total: finish_migration_run(...)`).
    Mutating that condition to `migrated + len(refused) == total` - closing a run that still had
    refused work - **killed nothing**, and the mutant was valid.

    The reason is a null worth recording: **`migration_runs.completed_at` is written and never
    read.** `finish_migration_run` is its only writer (`catalog.py:1471`) and the sole query over
    that table is `SELECT run_id ... ORDER BY started_at DESC LIMIT 1` (`catalog.py:1481`), which
    does not look at it. So the close condition has no observable behaviour today and no honest
    test can pin it without inventing a reader.

    What **is** observable is the per-move `migration_journal.completed_at`, set by
    `complete_migration_move` and filtered by `pending_migration` - and that is the thing the
    ruling actually depends on, so it is what this asserts.
    """
    root = tmp_path / "drive"
    db = tmp_path / "c.sqlite"
    with Catalog(db) as catalog:
        _seed(catalog, root, 4)
        run_migration(
            catalog,
            _RaisesOnChecksum(root, code=errno.ENOENT, only="p1.jpg"),
            "D1",
            _scheme(),
            apply=True,
        )

    with Catalog(db) as catalog:
        pending = [str(row["new_relative"]) for row in catalog.pending_migration("D1")]

    assert pending == ["Camera/2023/p1.jpg"], (
        "the refused move must keep its journal row - it is the only record of work left"
    )


# --- the cancel, which had no test at all --------------------------------------------------


def _cancel_on_first_move(cancel: threading.Event) -> ProgressCallback:
    """Trip the event on the first **MOVING** tick, never on the planning walk.

    ⚠ **A blunt `lambda _p: cancel.set()` does NOT test what it looks like it tests**, learned by
    writing one: `progress` covers both phases, so it fires during `Phase.PLANNING` first, and
    `run_migration` then returns `applied=False` at its pre-loop check without opening a run at
    all. That is correct and documented behaviour - *"never opens a run if planning itself was
    cancelled"* - but it is a different property, and a test aimed at the loop that silently
    exercised the planning guard would have proved nothing about the loop.
    """

    def on_progress(progress: Progress) -> None:
        if progress.phase == Phase.MOVING:
            cancel.set()

    return on_progress


def test_a_cancel_stops_between_moves_and_says_the_user_did_it(tmp_path: Path) -> None:
    """`run_migration` accepted a `cancel` and **nothing had ever exercised it**.

    Checked rather than assumed: no test in the tree passed `cancel=` to `run_migration` - the
    only neighbouring hit was `undo_migration`'s. `(agm)` then gave this path a new kind and new
    user-facing wording, both unproven. The event is tripped from `progress`, which fires after a
    move completes, so it lands between moves exactly as a cancel from another thread would.
    """
    root = tmp_path / "drive"
    db = tmp_path / "c.sqlite"
    cancel = threading.Event()
    with Catalog(db) as catalog:
        _seed(catalog, root, 4)
        outcome = run_migration(
            catalog,
            LocalDestination(root),
            "D1",
            _scheme(),
            apply=True,
            cancel=cancel,
            progress=_cancel_on_first_move(cancel),
        )

    assert outcome.applied is True, "the run reached the apply phase before it was stopped"
    assert outcome.migrated == 1, "the move in flight completes; the next one does not start"
    assert outcome.stopped is not None
    assert outcome.stopped.kind is MigrationStopKind.CANCELLED
    assert outcome.stopped.reason == CANCELLED_REASON, "one string, both surfaces"
    assert "migrate again" in outcome.stopped.reason, "a stop must name the way forward"
    assert outcome.stopped.never_attempted == 3
    assert not catalog_is_drained(db), "a cancelled run stays open so a re-run finishes it"


def test_a_cancel_leaves_every_file_at_exactly_one_path(tmp_path: Path) -> None:
    """No move is interrupted part-way. The disk half of the same guarantee."""
    root = tmp_path / "drive"
    cancel = threading.Event()
    with Catalog(tmp_path / "c.sqlite") as catalog:
        _seed(catalog, root, 4)
        run_migration(
            catalog,
            LocalDestination(root),
            "D1",
            _scheme(),
            apply=True,
            cancel=cancel,
            progress=_cancel_on_first_move(cancel),
        )

    for index in range(4):
        old = root / f"Camera/2023/08/p{index}.jpg"
        new = root / f"Camera/2023/p{index}.jpg"
        assert old.exists() != new.exists(), (
            f"p{index} is at {'both' if old.exists() else 'neither'} path after a cancel"
        )


# --- the errno the predicate names first ---------------------------------------------------


def test_a_read_only_remount_stops_the_run(tmp_path: Path) -> None:
    """`EROFS` - the first condition `drive_unwritable.persists_for_the_run` names, and the
    likeliest in practice: a user protecting a drive mid-recovery remounts it read-only.

    ⚠ **A COVERAGE FINDING ABOUT THE MODULE, NOT ONLY ABOUT `(agm)`**: before this file existed,
    **no migrate test used any errno at all** - checked against `19999ed`. The repo's own errno
    vocabulary is far wider (`ENOSPC`, `EACCES`, `EROFS`, `EXDEV`, `EFBIG`, `ENAMETOOLONG`), so
    the gap was this module's, not the harness's.
    """
    root = tmp_path / "drive"
    with Catalog(tmp_path / "c.sqlite") as catalog:
        _seed(catalog, root, 4)
        outcome = run_migration(
            catalog, _RaisesOnChecksum(root, code=errno.EROFS), "D1", _scheme(), apply=True
        )

    assert outcome.stopped is not None, "a read-only mount stays read-only for the whole run"
    assert outcome.stopped.kind is MigrationStopKind.COULD_NOT_CONTINUE
    assert outcome.migrated == 0


def test_a_permission_error_on_one_file_does_not_stop_the_run(tmp_path: Path) -> None:
    """The cry-wolf half of the errno split: `EACCES` and `EROFS` share `Unwritable.REFUSED`.

    `persists_for_the_run` separates them by reading the errno itself - a read-only mount is the
    run's problem, one file's permissions are one file's - so a guard that only tried `EROFS`
    would pass for an implementation that stopped on the whole `REFUSED` class.
    """
    root = tmp_path / "drive"
    with Catalog(tmp_path / "c.sqlite") as catalog:
        _seed(catalog, root, 4)
        outcome = run_migration(
            catalog,
            _RaisesOnChecksum(root, code=errno.EACCES, only="p1.jpg"),
            "D1",
            _scheme(),
            apply=True,
        )

    assert outcome.stopped is None, "one file's permissions are not the run's problem"
    assert outcome.migrated == 3
    assert len(outcome.refused) == 1


# --- exhaustiveness: a member nobody worded ------------------------------------------------


#: Every `MigrationStopKind`, with the decision each one carries on the CLI: is it the user's own
#: act, and what exit code does it spend. **A table, not a derivation** - the same reasoning
#: `test_every_job_declares_whether_it_mutates` gives for its own: a control derived from a
#: display string is one rename away from a lock that stops firing.
_WORDING: Final[dict[MigrationStopKind, tuple[bool, int]]] = {
    MigrationStopKind.CANCELLED: (True, 0),
    MigrationStopKind.GROUND_MOVED: (False, 4),
    MigrationStopKind.COULD_NOT_CONTINUE: (False, 4),
}


def test_every_stop_kind_has_a_recorded_wording_decision() -> None:
    """⚠ **AIMED AT AN ADDED MEMBER, WHICH IS THE ACTUAL DEFECT SHAPE.**

    `_report_migration_shortfall` branches `kind is CANCELLED` and words **everything else**
    "Stopped" with exit 4. So a fourth member added tomorrow - a quota stop, a lock stop - is
    worded and exit-coded by an `else` nobody wrote it for: **decided by omission**, which is
    what `undo.SkipClass`'s `_CLASS_OF` guard exists to prevent one module over.

    ⚠ **A renamed member is NOT what this catches, and the difference matters.** A rename breaks
    the table by `KeyError` at the reference and every other test in this file goes red anyway;
    an *addition* is silently absorbed. So the assertion is over `MigrationStopKind` itself -
    membership in the enum, checked against the table - never the reverse. Hard-coding the three
    names instead would restate the implementation and fail on a rename while still missing the
    thing this is for.
    """
    unworded = [kind for kind in MigrationStopKind if kind not in _WORDING]

    assert not unworded, (
        f"these stop kinds have no recorded wording: {unworded}. A new member currently falls "
        "through `_report_migration_shortfall`'s else - worded 'Stopped' and exit 4 - which is a "
        "decision nobody made. Add its row here and its branch there, deliberately."
    )


@pytest.mark.parametrize(("kind", "expected"), sorted(_WORDING.items()))
def test_each_stop_kind_is_worded_as_its_table_row_says(
    kind: MigrationStopKind, expected: tuple[bool, int], capsys: pytest.CaptureFixture[str]
) -> None:
    """The table is read, not merely written - otherwise the guard above is bookkeeping.

    §4's anti-vacuity rule: a table nothing consults proves that the table exists.
    """
    is_cancel, exit_code = expected
    outcome = MigrationOutcome(
        plan=MigrationPlan(drive_uuid="D1", moves=[], unchanged=0, warnings=[]),
        resumed=0,
        migrated=1,
        applied=True,
        stopped=MigrationStop(kind=kind, reason="because", never_attempted=2),
    )

    # The reporter takes the two facts it needs rather than a whole outcome, because it now
    # serves BOTH directions of one command - `undo_migration` returns an `UndoOutcome` and the
    # two types share only the stop and the refusals. `(agx)`
    assert _report_migration_shortfall(outcome.stopped, outcome.refused) == exit_code
    captured = capsys.readouterr()
    assert ("Cancelled:" in captured.out) is is_cancel
    assert (captured.err == "") is is_cancel, "only a fault goes to stderr"


def test_a_stop_kind_must_be_chosen_rather_than_defaulted() -> None:
    """⚠ **`kind` HAS NO DEFAULT - claimed in the docstring of BOTH stop types and pinned in
    NEITHER until now.**

    Found by auditing `(agm)`'s own diff for claims no test checks (`ENGINEERING_STANDARD.md`
    §4's seventieth member turned on my own work). `MigrationStop` and `undo.UndoStop` both say
    it; the repo already has the pattern for exactly this rule -
    `test_every_job_declares_whether_it_mutates` asserts `jobs.start`'s `mutating` never gains
    one - and neither stop type was covered by it.

    A default is a decision nobody made: to `COULD_NOT_CONTINUE` makes a future cancel read as a
    failure, to `CANCELLED` makes a failing device read as the user's choice. Both are wrong and
    both are silent.
    """
    for stop_type in (MigrationStop, UndoStop):
        kind = fields(stop_type)[0]
        assert kind.name == "kind", f"{stop_type.__name__}'s first field is no longer `kind`"
        defaulted = kind.default is not MISSING or kind.default_factory is not MISSING
        assert not defaulted, (
            f"{stop_type.__name__}.kind gained a default. Every construction site must answer "
            "for it - a defaulted kind words one outcome as another, silently."
        )
