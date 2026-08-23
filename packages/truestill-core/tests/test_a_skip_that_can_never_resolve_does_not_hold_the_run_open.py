"""Not every skip is outstanding work. `(agk)` regressions, fixed.

`undo.py`'s own rule for keeping a run open is stated in `run_undo`: a partial reversal stays open
because *"its remaining journal rows are still valid, so once the user resolves whatever blocked
them (an occupied path, a disconnected drive) a second `undo` finishes the job."*

⚠ **`(agk)` added two skip reasons that NO SECOND UNDO CAN EVER RESOLVE**, and the condition
guarding that rule was not updated with them:

* `NEVER_MOVED` - the rename never happened, so the file is already where it belongs;
* `WAS_A_COPY` - the row records a fallback copy, which `organizer._move_source` verified before
  removing the source. Undo reverses renames; there is no rename here to reverse, ever.

**So the discriminator is not "is this a failure".** It is **can re-running undo do any more?** A
run held open on a skip that can never clear is a promise the product cannot keep: the app's
`still_armed` stays true forever, and `latest_undoable_run` keeps offering a reversal that will
never restore another file. That is a wrong state on the recovery path, which is the one path
where a wrong state costs most.

The same split decides the exit code, and the CLI got it wrong in the other direction: it excluded
only `NEVER_MOVED`, so one fallback-copy row made every undo exit 1 and print *"could not be
restored"* about a row describing no rename.
"""

from __future__ import annotations

import random
from pathlib import Path

import pytest
from PIL import Image
from truestill_cli.cli import main
from truestill_core.catalog import Catalog
from truestill_core.undo import (
    SkipClass,
    UndoSkip,
    UndoSkipped,
    UndoStep,
    classify,
    outstanding,
    plan_undo,
    run_undo,
)


def _jpeg(path: Path, *, seed: int) -> None:
    rng = random.Random(seed)
    image = Image.new("RGB", (64, 64))
    image.putdata(
        [(rng.randrange(256), rng.randrange(256), rng.randrange(256)) for _ in range(4096)]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, "JPEG", quality=95)


@pytest.fixture
def reversed_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path, str]:
    """An in-place run of four photos, with one row marked as a fallback copy.

    The `copied` outcome is written through the product's own API, so this cannot describe a row
    the product could not produce - a plain `--move` that falls back for one file leaves exactly
    this.
    """
    lib, db = tmp_path / "lib", tmp_path / "c.sqlite"
    for i in range(4):
        _jpeg(lib / "Old Folder" / f"p{i}.jpg", seed=i)
    assert main(["drives", "--init", str(lib), "--label", "L", "--db", str(db)]) == 0
    monkeypatch.setattr("builtins.input", lambda _="": "move")
    assert main(["organize", str(lib), str(lib), "--in-place", "--apply", "--db", str(db)]) == 0

    with Catalog(db) as catalog:
        run = catalog.latest_undoable_run()
        assert run is not None
        rid = str(run["run_id"])
        rows = catalog.inplace_moves(rid)
        catalog.record_inplace_outcome(
            run_id=rid, old_relative=str(rows[0]["old_relative"]), outcome="copied"
        )
    return lib, db, rid


# --- the run must close ------------------------------------------------------------------------


def test_a_run_whose_only_skips_can_never_resolve_is_closed(
    reversed_run: tuple[Path, Path, str],
) -> None:
    """⚠ **THE HEADLINE.** Before this, one `copied` row left the run `in_progress` forever."""
    _lib, db, rid = reversed_run

    with Catalog(db) as catalog:
        outcome = run_undo(catalog, plan_undo(catalog, rid), apply=True)
        still_armed = catalog.latest_undoable_run()
        status = str(catalog.inplace_run(rid)["status"])  # type: ignore[index]

    assert outcome.restored == 3
    assert [s.reason for s in outcome.skipped] == [UndoSkip.WAS_A_COPY]
    assert status == "undone", "a fully reversed run was left open on a skip that can never clear"
    assert still_armed is None, "the app would keep offering a reversal that can restore nothing"


def test_a_run_with_a_skip_the_user_can_resolve_stays_open(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """⚠ **CRY-WOLF HALF ONE.** A close condition that fired on *any* outcome would satisfy the
    row above and retire the re-run that `undo.py`'s own comment promises - the user plugs the
    drive back in, runs undo again, and it says the run is already undone."""
    lib, db = tmp_path / "lib", tmp_path / "c.sqlite"
    for i in range(3):
        _jpeg(lib / "Old Folder" / f"p{i}.jpg", seed=i)
    assert main(["drives", "--init", str(lib), "--label", "L", "--db", str(db)]) == 0
    monkeypatch.setattr("builtins.input", lambda _="": "move")
    assert main(["organize", str(lib), str(lib), "--in-place", "--apply", "--db", str(db)]) == 0

    with Catalog(db) as catalog:
        run = catalog.latest_undoable_run()
        assert run is not None
        rid = str(run["run_id"])
        plan = plan_undo(catalog, rid)
        # One file is taken somewhere else before the reversal: ORIGIN_OCCUPIED's real shape,
        # and something the user can fix and re-run.
        plan.steps[0].original.parent.mkdir(parents=True, exist_ok=True)
        plan.steps[0].original.write_bytes(b"something else lives here now")
        outcome = run_undo(catalog, plan, apply=True)
        status = str(catalog.inplace_run(rid)["status"])  # type: ignore[index]

    assert outcome.skipped
    assert status != "undone", "a run with outstanding work was closed and cannot be re-run"


# --- the exit code -------------------------------------------------------------------------


def test_the_cli_does_not_spend_the_exit_code_on_a_skip_that_is_not_work(
    reversed_run: tuple[Path, Path, str], capsys: pytest.CaptureFixture[str]
) -> None:
    """⚠ The other half of the same mistake, in the other direction. The CLI excluded only
    `NEVER_MOVED`, so one fallback-copy row made a clean undo exit 1."""
    _lib, db, _rid = reversed_run

    code = main(["undo-organize", "--db", str(db), "--apply"])
    captured = capsys.readouterr()

    assert code == 0, "a clean undo reported failure over a row that describes no rename"
    assert "could not be restored" not in captured.err + captured.out


def test_the_cli_still_reports_a_real_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """⚠ **CRY-WOLF HALF TWO.** A filter that excluded everything would satisfy the row above and
    make undo incapable of reporting that it left files displaced - which is `(afa)`'s shape on
    the one command a user reaches for when something has already gone wrong."""
    lib, db = tmp_path / "lib", tmp_path / "c.sqlite"
    for i in range(3):
        _jpeg(lib / "Old Folder" / f"p{i}.jpg", seed=i)
    assert main(["drives", "--init", str(lib), "--label", "L", "--db", str(db)]) == 0
    monkeypatch.setattr("builtins.input", lambda _="": "move")
    assert main(["organize", str(lib), str(lib), "--in-place", "--apply", "--db", str(db)]) == 0
    with Catalog(db) as catalog:
        run = catalog.latest_undoable_run()
        assert run is not None
        plan = plan_undo(catalog, str(run["run_id"]))
    plan.steps[0].original.parent.mkdir(parents=True, exist_ok=True)
    plan.steps[0].original.write_bytes(b"occupied")

    code = main(["undo-organize", "--db", str(db), "--apply"])
    captured = capsys.readouterr()

    assert code == 1, "undo left a file displaced and said so with a success code"
    assert "could not be restored" in captured.err


# --- one classification, in one place ----------------------------------------------------------


def test_every_skip_reason_is_classified() -> None:
    """⚠ **Exhaustive by construction, because nothing type-checks a dict.**

    A new `UndoSkip` member with no class would fall through whichever default `classify` has, and
    the two behaviours that hang off it - the exit code and whether the run closes - would both be
    decided by an omission. `IMPLEMENTATION_STANDARDS.md`'s `assert_never` precedent, applied to a
    mapping rather than a match.
    """
    unclassified = [reason for reason in UndoSkip if classify(reason) is None]

    assert not unclassified, f"these skip reasons have no class: {unclassified}"


@pytest.mark.parametrize(
    ("reason", "expected"),
    [
        (UndoSkip.NEVER_MOVED, SkipClass.NOTHING_TO_DO),
        (UndoSkip.WAS_A_COPY, SkipClass.NOTHING_TO_DO),
        (UndoSkip.MOVED_AWAY, SkipClass.RESOLVABLE),
        (UndoSkip.ORIGIN_OCCUPIED, SkipClass.RESOLVABLE),
        (UndoSkip.NOT_THE_SAME_FILE, SkipClass.RESOLVABLE),
        (UndoSkip.FAILED, SkipClass.COULD_NOT),
        (UndoSkip.UNREADABLE, SkipClass.COULD_NOT),
    ],
)
def test_the_classification_itself(reason: UndoSkip, expected: SkipClass) -> None:
    """⚠ **CRY-WOLF HALF THREE.** A classifier answering `NOTHING_TO_DO` for everything closes
    every run and never spends the exit code, which passes both headline rows above and is the
    worst possible answer on the recovery path."""
    assert classify(reason) is expected


def test_outstanding_is_the_one_definition_both_behaviours_use() -> None:
    """The exit code and the close condition must not drift apart.

    They are two readings of one question - *can re-running undo do any more?* - and the CLI
    derived its own answer inline until this. Two copies of a rule is how they disagree.
    """
    step = UndoStep(sha256="a" * 64, current=Path("x"), original=Path("y"))
    every = [UndoSkipped(step, reason, "") for reason in UndoSkip]

    kept = {item.reason for item in outstanding(every)}

    assert kept == {r for r in UndoSkip if classify(r) is not SkipClass.NOTHING_TO_DO}
