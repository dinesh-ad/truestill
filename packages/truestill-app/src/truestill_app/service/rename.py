"""Renaming a trip or an event, from the app. `(aix)` stage 3

**The engine already exists and this module adds none of it.** `migrate.plan_rename` computes what
would move and `migrate.apply_rename` carries it out, both shipped in stages 1 and 2 and both
already the CLI's path. What was missing was a route.

🔑 **PREVIEW BEFORE COMMIT, which is what every tool that moves files on a rename does.** Bulk
Rename Utility's preview pane *"reveals what new file names will appear before making any
changes"*; Finder shows the new name before you confirm; Perforce's Rename/Move *"is not complete
until you submit the changelist"*. **Not a confirmation dialog** - HIG guidance warns against
unnecessary ones, and a dialog asking *"are you sure?"* over an unseen change is exactly the
question a preview answers better.

⚠ **BOTH HALVES ARE JOBS, and the preview being one is a correction rather than a default.**
`plan_rename` itself only reads the catalog, so the preview looked like a plain request - and it
was written as one. It is not: the plan has to render the new path through **the same route
resolution migrate uses** (`_resolve_migration_routes`), and that re-reads metadata for ambiguous
labels. `migration_preview_run` is a job for exactly this reason, its own note naming *"the silent
phase that made events/migrate preview look frozen on a network mount"*.

🔑 **AND ROUTE RESOLUTION IS NOT OPTIONAL - THIS WAS A MEASURED DEFECT, NOT A TIDINESS RULE.**
Without it every `Camera`-labelled row is ambiguous by construction, `plan_migration`'s
conservative default fires, and the rename rendered
``Camera/2015/2015-06/`` - **dropping the trip folder entirely**, which is the opposite of what a
rename does. `_resolve_migration_routes`'s own docstring is the rule: organize and migrate are one
placement decision and must route through one seam, never a second guess. A rename is that same
decision with one slug substituted.

The apply adds `mutating=True`, recorded in `test_every_job_declares_whether_it_mutates.py`.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import TypedDict

from truestill_core.catalog import Catalog
from truestill_core.catalog_session import open_catalog
from truestill_core.destinations import LocalDestination
from truestill_core.drive import read_marker
from truestill_core.hash_cache import HashCache
from truestill_core.layout_settings import pin_existing_layout, resolve_scheme
from truestill_core.migrate import (
    RENAME_WORDING,
    RenameKind,
    RenamePlan,
    apply_rename,
    plan_rename,
)
from truestill_core.progress import ProgressCallback

from truestill_app.jobs import JobTarget
from truestill_app.service.drive_support import (
    DriveUnavailablePayload,
    drive_unavailable,
    not_a_drive,
)
from truestill_app.service.migrate import (
    MigrationStopPayload,
    _resolve_migration_routes,
    stop_payload,
)


class RenamePreviewPayload(TypedDict):
    """What renaming this row would do. **Every key here is read by the card it is delivered to.**

    ⚠ **A refusal is an OUTCOME, not an error.** It arrives as a completed job carrying
    ``refusal``, never as a failure - `(agk)`/P24's ruling that a status is spent on what actually
    happened. *"Another folder is already called that"* is a true fact about the user's drive.

    ⚠ **It carried `kind`, `row_id` and a five-move `sample` and the card rendered none of them.**
    The request already knows which row it asked about, and the change worth showing is the folder
    pair - so a per-file list would be detail beside the answer rather than the answer. Removed
    rather than declared dead: `(ahl)`'s guard is what found them.
    """

    #: How many photographs would move. **The number the screen leads with**, because it is the
    #: cost of the action - a rename of 2,000 files is not the same decision as one of 3.
    moves: int
    #: Which folder the photographs live in now, and which they would live in. Rendered as the
    #: headline of the preview because it is the change in one line.
    old_folder: str | None
    new_folder: str | None
    #: `None` when the rename may proceed. Otherwise **core's own sentence**, never re-worded
    #: here - `RENAME_WORDING` is the one home, the same one the CLI renders. `(afe)` is the shape
    #: where a refusal the CLI shows and the app swallows becomes a silent divergence.
    refusal: str | None


class RenameRunPayload(TypedDict):
    """What the rename actually did. **Every key here is read by the screen it is delivered to.**

    Deliberately narrower than the outcome it is built from: `kind`, `row_id` and `resumed` are in
    `RenameOutcome` and are not here, because nothing on the card renders them and a payload key
    no surface reads is what `(ahl)`'s guard exists to catch. The request already knows which row
    it asked about.
    """

    moved: int
    #: ⚠ **False with ``moved > 0`` is an INTERRUPTED rename, not a failure of nerve.** The name
    #: flips only after every photograph has arrived (`(aix)` stage 2), so this being False means
    #: the catalog still holds the old name over a partly-moved folder - which is the honest
    #: state, and the journal makes the rest resumable.
    renamed: bool
    #: The name the row holds NOW. Reads back from the catalog rather than assuming the request
    #: succeeded, so an interrupted rename shows the user the old name because that is what is
    #: true. `(afm)`: a second copy of a fact is free to disagree with the first.
    name_now: str | None
    stopped: MigrationStopPayload | None


_KINDS: dict[str, RenameKind] = {"trip": RenameKind.TRIP, "event": RenameKind.EVENT}


def _folder_of(relative: str) -> str:
    """The folder a copy lives in, POSIX, as the catalog stores it. `(ais)`"""
    return PurePosixPath(relative).parent.as_posix()


def _refusal_sentence(plan: RenamePlan, kind: str) -> str | None:
    """Core's wording for this refusal, filled in. **Never a sentence written here.**

    `plan.refusal_detail` is what `plan_rename` already rendered from `RENAME_WORDING`; this
    prefers it and falls back to the template only if a future refusal arrives without one, so a
    new member of the enum cannot reach a screen as an empty string.
    """
    if plan.refusal is None:
        return None
    if plan.refusal_detail:
        return plan.refusal_detail
    return RENAME_WORDING[plan.refusal].format(kind=kind, name=plan.new_name, folder="")


@dataclass(frozen=True, slots=True)
class _Ask:
    """One rename request: **which drive, which row, what to call it.**

    A value rather than five parameters - `IMPLEMENTATION_STANDARDS.md`'s complexity rule answered
    by naming the group, the same move `run_record.RunHeader` records for itself. It also keeps
    ``drive_uuid`` beside ``path``, which is the pair that must not drift: the uuid is
    authoritative and the path is where it was found.
    """

    path: Path
    drive_uuid: str
    kind: str
    row_id: int
    new_name: str


def _plan_in(
    catalog: Catalog,
    ask: _Ask,
    *,
    cache: HashCache | None,
    progress: ProgressCallback | None,
    cancel: threading.Event | None,
) -> RenamePlan:
    """Plan the rename against an open catalog. **Writes nothing.**

    ⚠ **Routes come from `_resolve_migration_routes`, migrate's own seam.** Skipping it renders
    the new path without the trip folder - see this module's docstring for the measurement.
    """
    pin_existing_layout(catalog)
    routes, rules_by_sha, _warning = _resolve_migration_routes(
        catalog, ask.drive_uuid, ask.path, cache=cache, progress=progress, cancel=cancel
    )
    return plan_rename(
        catalog,
        ask.drive_uuid,
        resolve_scheme(catalog),
        kind=_KINDS[ask.kind],
        row_id=ask.row_id,
        new_name=ask.new_name,
        routes=routes,
        rules_by_sha=rules_by_sha,
    )


def rename_preview(
    path: Path, db: Path, *, kind: str, row_id: int, new_name: str
) -> JobTarget[RenamePreviewPayload] | DriveUnavailablePayload:
    """What renaming this trip or event would move. **Nothing is written.**

    A job, not a plain request: route resolution re-reads metadata. See the module docstring.
    """
    if read_marker(path) is None:
        return drive_unavailable(path, db)

    def target(progress: ProgressCallback, cancel: threading.Event) -> RenamePreviewPayload:
        marker = read_marker(path)
        if marker is None:
            raise not_a_drive(path, db)
        with open_catalog(db) as catalog, HashCache.beside(db) as cache:
            catalog.upsert_drive(uuid=marker.uuid, label=marker.label)
            plan = _plan_in(
                catalog,
                _Ask(path, marker.uuid, kind, row_id, new_name),
                cache=cache,
                progress=progress,
                cancel=cancel,
            )
        return {
            "moves": len(plan.moves),
            "old_folder": _folder_of(plan.moves[0].old_relative) if plan.moves else None,
            "new_folder": _folder_of(plan.moves[0].new_relative) if plan.moves else None,
            "refusal": _refusal_sentence(plan, kind),
        }

    return target


def rename_run(
    path: Path, db: Path, *, kind: str, row_id: int, new_name: str
) -> JobTarget[RenameRunPayload] | DriveUnavailablePayload:
    """Carry the rename out, as a drive job. **Moves the user's photographs.**

    ⚠ **THE SAME CORE ENTRY THE CLI USES, and that is load-bearing rather than tidy.**
    `apply_rename` is what records the `authored_decisions` lease in the same transaction as the
    name flip (`(aix)` stage 2b), and the lease is what lets the drive's decisions document take
    the new name while `(ahz)` step 3 keeps refusing a rebuilt catalog. **A second apply path here
    would skip the lease, and the rename would silently stop surviving a catalog rebuild** - the
    exact loss `(ahz)` was written after. There is no app-side apply, by design.
    """
    if read_marker(path) is None:
        return drive_unavailable(path, db)

    def target(progress: ProgressCallback, cancel: threading.Event) -> RenameRunPayload:
        marker = read_marker(path)
        if marker is None:
            raise not_a_drive(path, db)
        with open_catalog(db) as catalog, HashCache.beside(db) as cache:
            catalog.upsert_drive(uuid=marker.uuid, label=marker.label)
            plan = _plan_in(
                catalog,
                _Ask(path, marker.uuid, kind, row_id, new_name),
                cache=cache,
                progress=progress,
                cancel=cancel,
            )
            outcome = apply_rename(
                catalog,
                LocalDestination(path),
                marker.uuid,
                plan,
                progress=progress,
                cancel=cancel,
            )
            return {
                "moved": outcome.moved,
                "renamed": outcome.renamed,
                "name_now": catalog.named_row_name(kind, row_id),
                "stopped": stop_payload(outcome.stopped) if outcome.stopped else None,
            }

    return target
