"""Clean leftover empty folders after move/in-place organize or migration.

Self-contained surface: no Catalog. Depends only on ``truestill_core.cleanup``.
Leftover-folder *detection* helpers used by organize/migration stay on the facade;
this module owns the preview/apply endpoints the UI calls.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal, TypedDict

from truestill_core.cleanup import plan_cleanup, run_cleanup, trash_backend


class CleanEmptyOccupied(TypedDict):
    relative: str
    contents: list[str]


class CleanEmptyPreview(TypedDict):
    ok: Literal[True]
    path: str
    backend: str | None
    removable: list[str]
    occupied: list[CleanEmptyOccupied]


class CleanEmptyApply(TypedDict):
    ok: Literal[True]
    path: str
    removed: int
    trashed: int
    deleted: int
    failures: list[str]


def clean_empty_preview(path: Path, emptied: list[str]) -> CleanEmptyPreview:
    plan = plan_cleanup(path, emptied)
    backend = trash_backend()
    return {
        "ok": True,
        "path": str(path),
        "backend": backend,
        "removable": [candidate.relative for candidate in plan.removable],
        "occupied": [
            {"relative": candidate.relative, "contents": list(candidate.contents)}
            for candidate in plan.occupied
        ],
    }


def clean_empty_apply(path: Path, emptied: list[str]) -> CleanEmptyApply:
    plan = plan_cleanup(path, emptied)
    backend = trash_backend()
    outcome = run_cleanup(path, plan, apply=True, backend=backend, permanent=False)
    return {
        "ok": True,
        "path": str(path),
        "removed": outcome.removed,
        "trashed": outcome.trashed,
        "deleted": outcome.deleted,
        "failures": outcome.failures,
    }
