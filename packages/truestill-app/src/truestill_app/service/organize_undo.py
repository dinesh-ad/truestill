"""Organize-undo: durable state and preview/apply for rename-based organize runs.

Self-contained surface: Catalog + ``truestill_core.undo`` only.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Literal, NotRequired, TypedDict

from truestill_core.catalog_session import open_catalog
from truestill_core.progress import ProgressCallback
from truestill_core.run_record import record_undo
from truestill_core.undo import UndoError, plan_undo, run_undo

from truestill_app.jobs import JobTarget


class OrganizeUndoSkipped(TypedDict):
    relative: str
    reason: str
    detail: str


class OrganizeUndoStopped(TypedDict):
    """Why the reversal ended early, or absent entirely when it did not. `(agl)`

    ⚠ **`kind` rather than a phrase inside `reason`.** `app.js` must word a cancel differently
    from a failing drive, and `IMPLEMENTATION_STANDARDS.md` §9 forbids deciding that by matching
    message text. `reason` is the sentence a person reads; `kind` is what code branches on.
    """

    kind: str
    reason: str
    never_attempted: int


class OrganizeUndoStateDisarmed(TypedDict):
    ok: Literal[True]
    armed: Literal[False]
    restorable: int
    run_id: None


class OrganizeUndoStateArmed(TypedDict):
    ok: Literal[True]
    armed: Literal[True]
    run_id: str
    status: str
    source_root: str
    dest_root: str
    restorable: int
    skipped: list[OrganizeUndoSkipped]


class OrganizeUndoJobSummary(TypedDict):
    run_id: str
    source_root: str
    dest_root: str
    restorable: int
    restored: int
    applied: bool
    still_armed: bool
    #: The record's own failure, surfaced rather than swallowed - `(acc)`'s shape is a
    #: document written by something nobody can see, whose absence nobody is told about.
    record_error: str | None
    #: ⚠ **Absent from this payload until `(agl)`, so an undo stopped by a read-only remount
    #: reported as an ordinary short run** - `(afw)` built `UndoStop` and no app surface read it.
    #: Never-silent applies to a run's own ending, not only to its files.
    stopped: OrganizeUndoStopped | None
    skipped: list[OrganizeUndoSkipped]
    elapsed_seconds: NotRequired[float]


def organize_undo_state(db: Path) -> OrganizeUndoStateDisarmed | OrganizeUndoStateArmed:
    """Durable state for undoing rename-based organize runs."""
    with open_catalog(db) as catalog:
        try:
            plan = plan_undo(catalog)
        except UndoError:
            return {"ok": True, "armed": False, "restorable": 0, "run_id": None}
    return {
        "ok": True,
        "armed": True,
        "run_id": plan.run_id,
        "status": plan.status,
        "source_root": str(plan.source_root),
        "dest_root": str(plan.dest_root),
        "restorable": plan.restorable,
        "skipped": [
            {
                "relative": item.step.current.name,
                "reason": item.reason.value,
                "detail": item.detail,
            }
            for item in plan.skipped
        ],
    }


def organize_undo(*, db: Path, apply: bool) -> JobTarget:
    """Preview/apply organize undo on a worker thread."""

    def target(progress: ProgressCallback, cancel: threading.Event) -> OrganizeUndoJobSummary:
        with open_catalog(db) as catalog:
            plan = plan_undo(catalog)
            # ⚠ **The event was named `_cancel` and dropped until `(agl)`.** `jobs.py` sets
            # `status = "cancelled"` from the event alone, so the job reported cancelled and
            # `app.js` rendered *"Restored N file(s) before you stopped it"* while every
            # remaining file went back. Every other `JobTarget` in this package already handed
            # its event on; this was the only one that did not.
            outcome = run_undo(
                catalog,
                plan,
                apply=apply,
                progress=progress if apply else None,
                cancel=cancel if apply else None,
            )
            still_armed = catalog.latest_undoable_run() is not None
        # ⚠ **Only an APPLIED reversal writes one.** A preview moves nothing, so a record of it
        # would be a document about a run that did not happen - and it would supersede the record
        # of one that did. `(afw)`
        record_error = record_undo(db, plan, outcome) if apply else None
        return {
            "run_id": plan.run_id,
            "source_root": str(plan.source_root),
            "dest_root": str(plan.dest_root),
            "restorable": plan.restorable,
            "restored": outcome.restored,
            "applied": apply,
            "still_armed": still_armed,
            "record_error": record_error,
            "stopped": (
                None
                if outcome.stopped is None
                else {
                    "kind": outcome.stopped.kind.value,
                    "reason": outcome.stopped.reason,
                    "never_attempted": outcome.stopped.never_attempted,
                }
            ),
            "skipped": [
                {
                    "relative": item.step.current.name,
                    "reason": item.reason.value,
                    "detail": item.detail,
                }
                for item in outcome.skipped
            ],
        }

    return target
