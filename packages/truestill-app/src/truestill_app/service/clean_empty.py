"""Clean leftover empty folders after move/in-place organize or migration.

Self-contained surface: no Catalog is opened. Depends on ``truestill_core.cleanup``, which
writes the run record beside the catalog path it is handed (`(ahi)`).
Leftover-folder *detection* helpers used by organize/migration stay on the facade;
this module owns the preview/apply endpoints the UI calls.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal, TypedDict

from truestill_core.cleanup import Tier, plan_cleanup, record_cleanup, run_cleanup, trash_backend


class CleanEmptyOccupied(TypedDict):
    relative: str
    contents: list[str]
    #: Whether Truestill could look inside. ⚠ Carried even though no screen reads this list yet:
    #: the payload already shipped the contents, so the day one renders it, it would have
    #: inherited "something is in there" beside an empty list. `(afo)`
    readable: bool


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
    #: The run WORKED and its record did not. `(ahi)`; the same key organize and undo carry.
    record_error: str | None


def clean_empty_preview(path: Path, emptied: list[str]) -> CleanEmptyPreview:
    plan = plan_cleanup(path, emptied)
    backend = trash_backend()
    return {
        "ok": True,
        "path": str(path),
        "backend": backend,
        "removable": [candidate.relative for candidate in plan.removable],
        "occupied": [
            {
                "relative": candidate.relative,
                "contents": list(candidate.contents),
                "readable": candidate.readable,
            }
            for candidate in plan.occupied
        ],
    }


def clean_empty_apply(path: Path, emptied: list[str], db: Path) -> CleanEmptyApply:
    plan = plan_cleanup(path, emptied)
    backend = trash_backend()
    held_junk = any(candidate.tier is Tier.JUNK_ONLY for candidate in plan.removable)
    outcome = run_cleanup(path, plan, apply=True, backend=backend, permanent=False)
    # `(ahi)`: the only account of what this run removed, by name; the core writer is shared with
    # the CLI so the two surfaces cannot describe one cleanup two ways.
    record_error = record_cleanup(db, path, plan, outcome)
    return {
        "ok": True,
        "path": str(path),
        "removed": outcome.removed,
        "discarded": outcome.discarded,
        "held_junk": held_junk,
        "failures": outcome.failures,
        "record_error": record_error,
    }
