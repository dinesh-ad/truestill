"""Organize-undo: durable state and preview/apply for rename-based organize runs.

Self-contained surface: Catalog + ``truestill_core.undo`` only.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Literal, NotRequired, TypedDict

from truestill_core.catalog import Catalog
from truestill_core.progress import ProgressCallback
from truestill_core.undo import UndoError, plan_undo, run_undo

from truestill_app.jobs import JobTarget


class OrganizeUndoSkipped(TypedDict):
    relative: str
    reason: str
    detail: str


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
    skipped: list[OrganizeUndoSkipped]
    elapsed_seconds: NotRequired[float]


def organize_undo_state(db: Path) -> OrganizeUndoStateDisarmed | OrganizeUndoStateArmed:
    """Durable state for undoing rename-based organize runs."""
    with Catalog(db) as catalog:
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

    def target(progress: ProgressCallback, _cancel: threading.Event) -> OrganizeUndoJobSummary:
        with Catalog(db) as catalog:
            plan = plan_undo(catalog)
            outcome = run_undo(catalog, plan, apply=apply, progress=progress if apply else None)
            still_armed = catalog.latest_undoable_run() is not None
        return {
            "run_id": plan.run_id,
            "source_root": str(plan.source_root),
            "dest_root": str(plan.dest_root),
            "restorable": plan.restorable,
            "restored": outcome.restored,
            "applied": apply,
            "still_armed": still_armed,
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
