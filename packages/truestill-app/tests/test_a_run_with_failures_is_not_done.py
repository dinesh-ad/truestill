"""A run that finished and left the library unclean does not report "done". `(aiq)`

**Measured before it was fixed.** Soak twelve's app half drove `organize` onto a drive that
vanished mid-run: **1,130 of 1,324 files failed** and the terminal event was
``{"type": "done", "status": "done", ...}``. The screen showed a warn banner and the word *Done*.

🔑 **The defect was the SOURCE of the status, not its value.** `jobs.py` derived it from control
flow - ``"cancelled" if cancel.is_set() else "done"`` - so it asked *did the target return*, never
*what did it return*. A run that completes having failed most of its work returns perfectly well.

**Two states were measured to be too few, twice, in the field.** BackInTime ignored `rsync`'s exit
23, switched to treating it as an error, and then every snapshot reported failure; their remedy was
*"Introduce a new snapshot result state 'Warning'"* (#1587). Proxmox reached *"Backup job finished
with errors"* independently. The trap runs both ways: success hides the shortfall, blanket failure
teaches people to ignore the status.

⚠ **THE LINE IS THE CLI's.** `truestill` already exits **1** for this state, and `_cmd_verify`
returns 1 on ``missing or mismatch or unreadable`` - a *finding* rather than work it could not do.
So this makes the app say what the CLI has always said, rather than inventing a third meaning.
"""

from __future__ import annotations

import time

import pytest
from truestill_app.jobs import (
    FINISHED_CLEAN,
    STATUS_CANCELLED,
    STATUS_COMPLETED_WITH_ERRORS,
    STATUS_DONE,
    DriveRef,
    JobManager,
    _terminal_status,
)
from truestill_app.service.backup import BackupRunSummary
from truestill_app.service.bake import BakeSummary
from truestill_app.service.migrate import MigrationApplySummary, UndoJobSummary
from truestill_app.service.organize import CompletionBase
from truestill_app.service.organize_undo import OrganizeUndoJobSummary
from truestill_app.service.rename import RenameRunPayload
from truestill_app.service.verify import VerifyJobSummary

TOKEN = "t"


def test_a_clean_run_is_done() -> None:
    assert _terminal_status({FINISHED_CLEAN: True}, cancelled=False) == STATUS_DONE


def test_a_run_that_left_the_library_unclean_is_not_done() -> None:
    """⚠ THE DETECTOR. Against the old derivation this returned "done"."""
    assert (
        _terminal_status({FINISHED_CLEAN: False}, cancelled=False) == STATUS_COMPLETED_WITH_ERRORS
    )


def test_cancelled_wins_over_unclean() -> None:
    """Why it ends is the more specific fact, and the one the person knows they caused."""
    assert _terminal_status({FINISHED_CLEAN: False}, cancelled=True) == STATUS_CANCELLED


def test_a_summary_that_says_nothing_is_done() -> None:
    """A preview computes and returns; there is no partial state for it to be in."""
    assert _terminal_status({"previewed": 3}, cancelled=False) == STATUS_DONE
    assert _terminal_status(None, cancelled=False) == STATUS_DONE


def test_only_an_explicit_false_is_unclean() -> None:
    """A truthy-but-not-True value must not be read as a verdict either way."""
    assert _terminal_status({FINISHED_CLEAN: None}, cancelled=False) == STATUS_DONE


#: Every job shape that mutates something and can therefore finish unclean, with what
#: "unclean" means for it. **The table is the point**: `jobs.py` cannot know any of these, which
#: is why the service declares and this census exists.
_MUTATING_SHAPES = [
    pytest.param(CompletionBase, "failed, or MOVE_KEPT", id="organize"),
    pytest.param(BackupRunSummary, "a copy that failed", id="backup"),
    pytest.param(BakeSummary, "a date it could not write", id="bake"),
    pytest.param(VerifyJobSummary, "missing / mismatch / unreadable", id="verify"),
    pytest.param(MigrationApplySummary, "stopped, or refused moves", id="migrate-apply"),
    pytest.param(UndoJobSummary, "stopped, or refused reversals", id="migrate-undo"),
    pytest.param(OrganizeUndoJobSummary, "stopped, skipped, or no record", id="organize-undo"),
    pytest.param(RenameRunPayload, "an interrupted rename", id="rename"),
]


@pytest.mark.parametrize(("shape", "meaning"), _MUTATING_SHAPES)
def test_every_mutating_shape_declares_its_own_verdict(shape: type, meaning: str) -> None:
    """A new mutating shape that forgets the key silently reports "done" for ever.

    That is the failure being fixed, one layer up - so it is guarded rather than trusted to
    review. `jobs.py` treats an absent key as clean, which is right for a preview and wrong for
    anything that writes.

    ⚠ **THIS GUARDS THE DECLARATION; MYPY GUARDS THE CONSTRUCTION, and the split was found by a
    surviving mutation rather than reasoned out.** Deleting the runtime
    ``"finished_clean": ...`` from `organize._completion` while leaving the annotation in place
    **passed this file** - a green run against a shape that no longer says anything. It fails
    `mypy` with two errors, because the key is **required** rather than `NotRequired`, so every
    construction site must set it. Both halves are proved by mutation; neither alone is enough,
    and a reader who sees only this test would over-trust it.
    """
    assert FINISHED_CLEAN in shape.__annotations__, (
        f"{shape.__name__} can finish unclean ({meaning}) and does not say so, "
        f"so jobs.py will report it as {STATUS_DONE!r}"
    )


def _drain_terminal(mgr: JobManager, job_id: str, *, timeout: float = 5.0) -> dict[str, object]:
    """The terminal event as a browser would receive it, off the real queue."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        job = mgr.get(job_id)
        assert job is not None
        if job.terminal is not None:
            return dict(job.terminal)
        time.sleep(0.01)
    pytest.fail(f"job {job_id} never reached a terminal state")


@pytest.mark.parametrize(
    ("summary", "expected"),
    [
        ({"organized": 185, "failed": 1130, FINISHED_CLEAN: False}, STATUS_COMPLETED_WITH_ERRORS),
        ({"organized": 1324, "failed": 0, FINISHED_CLEAN: True}, STATUS_DONE),
        ({"previewed": 3}, STATUS_DONE),
    ],
    ids=["the-measured-run", "a-clean-run", "a-preview"],
)
def test_the_terminal_event_itself_carries_the_status(
    summary: dict[str, object], expected: str
) -> None:
    """⚠ THE WIRE, driven through the real `JobManager`, because a unit test cannot see the event.

    The first case is soak twelve's measurement to the file: **1,130 failed of 1,324**, the run
    returning normally, and the event that reached the browser saying ``done``.
    """
    mgr = JobManager()
    job_id = mgr.start(
        lambda _progress, _cancel: summary,
        drives=[DriveRef(key="uuid:A", label="Drive A")],
        operation="organize",
        mutating=True,
    )
    assert isinstance(job_id, str)

    terminal = _drain_terminal(mgr, job_id)

    assert terminal["type"] == "done", "a returning target must not become an error event"
    assert terminal["status"] == expected
