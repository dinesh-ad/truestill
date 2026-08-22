"""Clean leftover empty folders after move/in-place organize or migration.

Self-contained surface: no Catalog. Depends only on ``truestill_core.cleanup``.
Leftover-folder *detection* helpers used by organize/migration stay on the facade;
this module owns the preview/apply endpoints the UI calls.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal, TypedDict

from truestill_core.cleanup import Tier, plan_cleanup, run_cleanup, trash_backend


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
    #: ⚠ ``trashed``/``deleted`` were removed on 2026-08-22 and this is a **breaking payload
    #: change**, free only because `(adz)` says no users exist yet - the window closes at the
    #: first tag. They counted folders, and no folder is trashed any more: the contents go to the
    #: trash and the folder goes to ``rmdir``. `(afj)`
    ok: Literal[True]
    path: str
    removed: int
    discarded: int
    #: Whether any removable folder held junk, so a surface can say where that junk went without
    #: a counter for a recoverable thing. See `CleanupOutcome`.
    held_junk: bool
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
    held_junk = any(candidate.tier is Tier.JUNK_ONLY for candidate in plan.removable)
    outcome = run_cleanup(path, plan, apply=True, backend=backend, permanent=False)
    return {
        "ok": True,
        "path": str(path),
        "removed": outcome.removed,
        "discarded": outcome.discarded,
        "held_junk": held_junk,
        "failures": outcome.failures,
    }
