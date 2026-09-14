"""Restore: the panel over `truestill_core.decisions.apply_documents`.

Puts trip / event / album names and other human decisions from
``.truestill-decisions.json`` back into this catalog. **Not photographs** - that is recover.

⚠ **Confirm is checked here, not only in the browser** (`(ahe)`). The typed word lives in core
(`CONFIRM_WORD`) so the CLI and this panel demand the same string.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Final, Literal, NotRequired, TypedDict

from truestill_core.catalog_session import open_catalog
from truestill_core.decisions import (
    CONFIRM_WORD,
    RestoreReport,
    apply_documents,
    documents_for_restore,
    messages_for_restore,
    record_restore,
    restored_count,
    unconfirmed_reason,
    withheld_count,
)
from truestill_core.progress import ProgressCallback

from truestill_app.jobs import JobTarget

NOT_CONFIRMED: Final = "NotConfirmed"

__all__ = [
    "CONFIRM_WORD",
    "NOT_CONFIRMED",
    "RestoreLine",
    "RestorePreviewErr",
    "RestorePreviewOk",
    "RestoreRefusal",
    "RestoreRunSummary",
    "restore_preview",
    "restore_run",
]


class RestoreLine(TypedDict):
    """One sentence from the restore report, for banners."""

    text: str
    actionable: bool


class RestorePreviewErr(TypedDict):
    ok: Literal[False]
    error: str


class RestorePreviewOk(TypedDict):
    ok: Literal[True]
    path: str
    documents: int
    applied: dict[str, int]
    restored: int
    withheld: int
    summary: str
    lines: list[RestoreLine]
    confirm_word: str


class RestoreRefusal(TypedDict):
    """Missing or wrong typed word. Same shape bake uses so the route can share the 400 path."""

    ok: Literal[False]
    error: str
    code: Literal["NotConfirmed"]
    drive_label: str


class RestoreRunSummary(TypedDict):
    path: str
    applied: dict[str, int]
    restored: int
    withheld: int
    summary: str
    lines: list[RestoreLine]
    finished_clean: bool
    elapsed_seconds: NotRequired[float]


def _lines(report: RestoreReport, *, done: bool) -> tuple[str, list[RestoreLine]]:
    summary, messages = messages_for_restore(report, done=done)
    return summary, [{"text": m.text, "actionable": m.actionable} for m in messages]


def restore_preview(path: Path, db: Path) -> RestorePreviewOk | RestorePreviewErr:
    """What this drive's decisions document would put into the catalog. **Writes nothing.**"""
    if not path.is_dir():
        return {"ok": False, "error": f"{path} is not a folder."}
    with open_catalog(db) as catalog:
        documents, problem = documents_for_restore(path, catalog)
        if problem is not None:
            return {"ok": False, "error": problem}
        named = documents[0].drive_uuid if documents else ""
        report = apply_documents(catalog, documents, apply=False, named_root_uuid=named)
        summary, lines = _lines(report, done=False)
        return {
            "ok": True,
            "path": str(path),
            "documents": len(documents),
            "applied": dict(report.applied.applied),
            "restored": restored_count(report.applied),
            "withheld": withheld_count(report.applied),
            "summary": summary,
            "lines": lines,
            "confirm_word": CONFIRM_WORD,
        }


def restore_run(
    path: Path, db: Path, *, confirmation: str
) -> JobTarget[RestoreRunSummary] | RestoreRefusal:
    """Build a job that applies the drive document into the catalog.

    ⚠ **`confirmation` IS CHECKED HERE, NOT AT THE ROUTE** (`(ahe)`). A request with the wrong
    word never becomes a job.
    """
    unconfirmed_why = unconfirmed_reason(confirmation)
    if unconfirmed_why is not None:
        refused: RestoreRefusal = {
            "ok": False,
            "error": unconfirmed_why,
            "code": NOT_CONFIRMED,
            "drive_label": "",
        }
        return refused

    def target(
        progress: ProgressCallback,  # noqa: ARG001 - JobTarget shape; restore is one apply call
        cancel: threading.Event,  # noqa: ARG001 - same; no per-item loop to honour cancel inside
    ) -> RestoreRunSummary:
        if not path.is_dir():
            message = f"{path} is not a folder."
            raise ValueError(message)
        with open_catalog(db) as catalog:
            documents, problem = documents_for_restore(path, catalog)
            if problem is not None:
                raise ValueError(problem)
            named = documents[0].drive_uuid if documents else ""
            report = apply_documents(catalog, documents, apply=True, named_root_uuid=named)
            restored = restored_count(report.applied)
            withheld = withheld_count(report.applied)
            summary, lines = _lines(report, done=True)
            record_restore(db, root=path, restored=restored, withheld=withheld)
            return {
                "path": str(path),
                "applied": dict(report.applied.applied),
                "restored": restored,
                "withheld": withheld,
                "summary": summary,
                "lines": lines,
                # Withholdings are collision rules working, not a failed write - same split
                # recover makes for skips vs failures.
                "finished_clean": True,
            }

    return target
