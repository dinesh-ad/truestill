"""The CLI words a stopped undo from its KIND, not from the sentence attached to it. `(agl)`

⚠ **NULL REPORTED FIRST, because it decides how this file is written: the CLI has no way to
produce a cancel today.** `_cmd_undo_organize` calls `run_undo` with a progress printer and no
`cancel` event - there is no Ctrl-C handler that raises one - so `UndoStopKind.CANCELLED` reaches
this surface only through a constructed outcome. Wiring one is a feature, not this entry.

**So why the branch exists at all.** `UndoStop` is now a shared type with two kinds, and `(afu)`
is the recorded cost of a rule that reaches one of two surfaces: its builder went where one caller
could not see it and the app went without a record for five commits. A CLI that ignored `kind`
would word a user's own cancel as a fault the moment anyone wires Ctrl-C, and the person doing
that wiring would have no reason to look here.

**And it is called directly rather than through the command**, because a test that cannot reach a
state through the product is honest about that instead of building scaffolding that implies it
can. `_apply_the_undo` is the whole reporting path; `_cmd_undo_organize` only decides what to hand
it.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest
from truestill_cli.cli import _apply_the_undo
from truestill_core.undo import (
    CANCELLED_REASON,
    UndoOutcome,
    UndoPlan,
    UndoStop,
    UndoStopKind,
)


def _plan(tmp_path: Path) -> UndoPlan:
    return UndoPlan(
        run_id="r1",
        source_root=tmp_path,
        dest_root=tmp_path,
        drive_uuid="D1",
        status="applied",
        steps=[],
        skipped=[],
    )


def _outcome(plan: UndoPlan, *, kind: UndoStopKind, reason: str) -> UndoOutcome:
    return UndoOutcome(
        plan=plan,
        restored=1,
        skipped=[],
        applied=True,
        stopped=UndoStop(kind=kind, reason=reason, never_attempted=3),
    )


def _report(
    tmp_path: Path, outcome: UndoOutcome, capsys: pytest.CaptureFixture[str]
) -> tuple[str, str, int]:
    args = argparse.Namespace(db=tmp_path / "c.sqlite")
    code = _apply_the_undo(args, outcome.plan, outcome)
    captured = capsys.readouterr()
    return captured.out, captured.err, code


def test_a_cancelled_undo_reads_as_a_choice_and_not_as_a_fault(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Cancelled, on stdout, exit 0 - and it names the way forward.

    P24's rule is that the exit code is spent on the right outcome. A cancel is the user doing
    what they meant to; spending `1` on it would make `undo && next_step` refuse to chain after a
    deliberate act, and would tell a script something went wrong.
    """
    plan = _plan(tmp_path)
    out, err, code = _report(
        tmp_path, _outcome(plan, kind=UndoStopKind.CANCELLED, reason=CANCELLED_REASON), capsys
    )

    assert "Cancelled:" in out, "a cancel must not be reported with the word for a fault"
    assert "Stopped:" not in out
    assert "Stopped:" not in err
    assert "3 file(s) were not reached." in out
    assert "undo again" in out, "the user must be told a second undo finishes the job"
    assert err == "", "a cancel is not something that went wrong, so nothing goes to stderr"
    assert code == 0, "a cancelled undo is not a failure"


def test_a_run_that_could_not_continue_still_reads_as_a_fault(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The cry-wolf half: the branch must not swallow the outcome it was already wording.

    ⚠ **Without this, deleting the whole `kind` branch and printing "Cancelled" unconditionally
    would pass the test above.** A read-only remount is the case `(agi)` built the stop for, and
    it belongs on stderr.
    """
    plan = _plan(tmp_path)
    out, err, _code = _report(
        tmp_path,
        _outcome(plan, kind=UndoStopKind.COULD_NOT_CONTINUE, reason="Read-only file system"),
        capsys,
    )

    assert "Stopped: Read-only file system" in err
    assert "Cancelled" not in err
    assert "Cancelled" not in out
