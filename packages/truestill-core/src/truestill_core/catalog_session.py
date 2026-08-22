"""Opening a catalog the way a surface should: decisions reach the drives when the work is done.

**Why not at each call site.** `truestill-cli` opens a catalog at 15 places and `truestill-app`
at 41, and a trigger written at each of them drifts the moment a sixteenth is added. A missed one
is invisible: the decision saves locally and simply never leaves, which is the failure this whole
feature exists to prevent, arriving through the feature's own wiring.

**Why not inside `Catalog`.** Storage does not do drive I/O, and a save fired by `Catalog.__exit__`
would fire in tests too - 1,200 of them open catalogs. Keeping the trigger here means tests use
bare `Catalog(...)` and **cannot** write to a drive. §4 asks for impossible rather than unlikely,
and this is impossible by construction rather than by anyone remembering.

**Coarse on purpose.** The catalog reports that *something* was written, not that a decision was.
A refresh after `organize` or `rescan` costs about 1.2 KB and keeps the drive's `written` stamp
current, which is what the staleness line reads.

**Core prints nothing** (`IMPLEMENTATION_STANDARDS` §2): outcomes are handed to `report` and the
surface decides. The CLI prints failures; the app stores them for its drive card.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Protocol

from truestill_core.catalog import Catalog
from truestill_core.catalog_backup import BackupOutcome
from truestill_core.decisions import (
    PROBLEM_OUTCOMES,
    DriveSave,
    SaveOutcome,
    ensure_decisions_on_drives,
    save_decisions_to_reachable_drives,
)

#: Per-drive record of a save that did not happen, so it outlives the command that produced it.
#: A line printed after a command is gone the moment the user scrolls, and a backup nobody can
#: see is one nobody has. Machine-local: the `decisions.` prefix never reaches a document.
PROBLEM_KEY_PREFIX = "decisions.problem."


class SaveReport(Protocol):
    """How a surface is told what happened to the drives.

    ``upgrade`` separates the once-per-catalog first write from the ordinary one, because they
    deserve different words: the first is worth a line, and every one after it is not.
    """

    def __call__(self, results: tuple[DriveSave, ...], *, upgrade: bool) -> None: ...


class BackupReport(Protocol):
    """How a surface is told what happened to the pre-upgrade catalog copy. `(ady)`

    Called at most once per catalog per release - only an open that actually runs a migration
    produces an outcome at all - so a surface may say something on failure without becoming
    noise.
    """

    def __call__(self, outcome: BackupOutcome) -> None: ...


def problem_key(drive_uuid: str) -> str:
    return f"{PROBLEM_KEY_PREFIX}{drive_uuid}"


def _record(catalog: Catalog, results: tuple[DriveSave, ...]) -> None:
    """Keep the drives that could not be saved, and forget the ones that since were.

    A stale problem is its own defect - it reports decisions as unsaved when they are saved - so
    a success clears it. `UNREACHABLE` clears nothing: a drive in a drawer has not resolved
    anything, and last time's reason is still the last thing known.
    """
    for result in results:
        key = problem_key(result.uuid)
        if result.outcome in PROBLEM_OUTCOMES:
            catalog.set_setting(key, result.detail)
        elif result.outcome is SaveOutcome.WRITTEN and catalog.get_setting(key):
            catalog.clear_setting(key)


def _refresh(
    catalog: Catalog,
    results: tuple[DriveSave, ...],
    report: SaveReport | None,
    *,
    upgrade: bool,
) -> None:
    _record(catalog, results)
    if report is not None:
        report(results, upgrade=upgrade)
    # The recording above is itself a write. Without this the catalog would look dirty because it
    # was saved, and the next check would save it again for the same reason.
    catalog.mark_clean()


@contextmanager
def open_catalog(
    db: Path,
    *,
    report: SaveReport | None = None,
    backup_report: BackupReport | None = None,
) -> Iterator[Catalog]:
    """A catalog whose decisions reach every reachable drive when the work finishes.

    **The upgrade write happens first, before the body runs.** Existing users have decisions and
    no drive copy, and the one most at risk has a finished library and has stopped naming things,
    so the ordinary trigger never fires for them. Running it on entry also means a user whose
    first command after upgrading is a risky one is protected *before* it, not after - the body
    is the part that might raise.

    **Only a clean exit saves.** A command that failed part way through is not a moment to
    publish its catalog to every drive the user owns.
    """
    with Catalog(db) as catalog:
        # ⚠ **A failed pre-upgrade copy must not be silent.** `Catalog` records the outcome and
        # prints nothing (§2); this is the one seam every CLI open already goes through, so the
        # report cannot be missed at a twenty-third call site - the same argument that put the
        # decisions trigger here. `(ady)`
        if backup_report is not None and catalog.pre_migration_backup is not None:
            backup_report(catalog.pre_migration_backup)

        # A freshly opened catalog is never dirty: schema migrations commit directly on the
        # connection rather than through `_tx`. A defensive `mark_clean()` here was written and
        # then deleted, because a mutation that removed it killed no test - it could not.
        first = ensure_decisions_on_drives(catalog)
        if first is not None:
            _refresh(catalog, first, report, upgrade=True)

        yield catalog

        if catalog.dirty:
            # Before the decisions gather, so the gather is planned with current statistics.
            catalog.refresh_statistics_if_stale()
            results = save_decisions_to_reachable_drives(catalog)
            _refresh(catalog, results, report, upgrade=False)
