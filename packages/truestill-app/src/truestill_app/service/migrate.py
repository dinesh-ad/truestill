"""Migration: layout preview/apply and migration undo."""

from __future__ import annotations

import threading
from collections.abc import Sequence
from pathlib import Path, PurePosixPath
from typing import Literal, NotRequired, TypedDict

from truestill_core.catalog import Catalog
from truestill_core.destinations import LocalDestination
from truestill_core.drive import read_marker
from truestill_core.hash_cache import HashCache
from truestill_core.layout import Placement
from truestill_core.layout_settings import pin_existing_layout, resolve_scheme
from truestill_core.migrate import (
    ROUTE_SIDE_BIN,
    label_routes,
    rederive_rules,
    run_migration,
    undo_migration,
)
from truestill_core.progress import ProgressCallback

from truestill_app.jobs import JobTarget
from truestill_app.service.drive_support import (
    DriveUnavailablePayload,
    drive_unavailable,
    not_a_drive,
)
from truestill_app.service.leftover_cleanup import (
    LeftoverEmptyFolders,
    cleanup_summary_from_old_paths,
)
from truestill_app.service.trips import NamedEventSelection, NamedTripSelection


def _resolve_migration_routes(
    catalog: Catalog,
    drive_uuid: str,
    path: Path,
    *,
    cache: HashCache | None = None,
    progress: ProgressCallback | None = None,
    cancel: threading.Event | None = None,
) -> tuple[dict[str, str], dict[str, str], str]:
    """Resolve ambiguous labels the same way `truestill migrate-layout` does.

    A `Camera`-labelled row is ambiguous by construction (`label_routes`'s own docstring: it is
    the device rule's default label *and* a possible `Software` value) -- migrate and organize
    are the same placement decision, so they must route through the same seam, never a second
    guess. Without this, `plan_migration`'s conservative default (unmapped -> side bin) fires for
    every `Camera` row, because nothing else in this module ever resolved the ambiguity - the app
    has no `--by-device` equivalent, so re-derivation always runs with the plain device rule.

    ``progress`` / ``cancel`` forward into :func:`rederive_rules` (exiftool) - the silent phase
    that made events/migrate preview look frozen on a network mount (backlog oo). ``cache`` is
    what makes a repeat preview obey 8's warm-read rule; it was missing until 2026-07-31 and cost
    a measured 12.2 s on every preview of a 2,224-file drive (audit F18, PERFORMANCE.md 1.1).
    """
    routes = label_routes(catalog, drive_uuid)
    rederived = rederive_rules(
        catalog, drive_uuid, path, routes, cache=cache, progress=progress, cancel=cancel
    )
    decided = {r.label: (ROUTE_SIDE_BIN if r.needs_decision else r.route) for r in routes}
    return decided, rederived.rules, rederived.unavailable_reason


class MigrationMove(TypedDict):
    old: str
    new: str


class MigrationPreviewOk(TypedDict):
    ok: Literal[True]
    label: str
    template: str
    unchanged: int
    moves: list[MigrationMove]
    warnings: list[str]
    day_folder_reasons: list[str]
    pending_drives: list[str]
    elapsed_seconds: NotRequired[float]


def migration_preview(
    path: Path,
    db: Path,
    *,
    progress: ProgressCallback | None = None,
    cancel: threading.Event | None = None,
) -> MigrationPreviewOk | DriveUnavailablePayload:
    """Preview relocating a connected drive's files to the current template (moves nothing)."""
    marker = read_marker(path)
    if marker is None:
        return drive_unavailable(path)
    with Catalog(db) as catalog, HashCache.beside(db) as cache:
        scheme = resolve_scheme(catalog)
        routes, rules_by_sha, evidence_warning = _resolve_migration_routes(
            catalog, marker.uuid, path, cache=cache, progress=progress, cancel=cancel
        )
        outcome = run_migration(
            catalog,
            LocalDestination(path),
            marker.uuid,
            scheme,
            apply=False,
            routes=routes,
            rules_by_sha=rules_by_sha,
            progress=progress,
            cancel=cancel,
        )
        pending = [
            d["label"]
            for d in catalog.list_drives()
            if d["uuid"] != marker.uuid and d["file_count"]
        ]
    plan = outcome.plan
    return {
        "ok": True,
        "label": marker.label,
        "template": scheme.template_for(Placement.EVERYDAY).template,
        "unchanged": plan.unchanged,
        "moves": [{"old": m.old_relative, "new": m.new_relative} for m in plan.moves],
        "warnings": [*plan.warnings, *([evidence_warning] if evidence_warning else [])],
        "day_folder_reasons": list(plan.day_folder_reasons),
        "pending_drives": pending,
    }


def migration_preview_run(path: Path, db: Path) -> JobTarget | DriveUnavailablePayload:
    """Migration preview as a cancellable job - streams rederive + plan progress (backlog oo).

    Soft-fails with the drive-correction payload when the path is not a connected drive, matching
    :func:`migration_undo`, so the UI never starts a job for "not a drive".
    """
    marker = read_marker(path)
    if marker is None:
        return drive_unavailable(path)

    def target(progress: ProgressCallback, cancel: threading.Event) -> MigrationPreviewOk:
        result = migration_preview(path, db, progress=progress, cancel=cancel)
        if result["ok"] is not True:
            # The gate above ran at REQUEST time; this runs later on a worker thread, and
            # migration_preview re-reads the marker itself - so a drive unplugged in between
            # makes it return the soft-fail payload it is designed to return. This was an
            # `assert`, which narrowed the union for mypy and, when the narrowing turned out
            # false, converted that payload into an AssertionError: no message, not in the UI's
            # FRIENDLY_ERRORS, rendered as an empty banner. Raising the same typed error the
            # sibling paths raise (migration_apply, backup_run) gets the user a next step, and
            # unlike an assert it cannot be stripped by `python -O` (audit F20).
            raise not_a_drive(path)
        return result

    return target


class AppliedReviewGroupPayload(TypedDict):
    kind: Literal["trip", "event"]
    name: str
    start: str
    end: str
    path: str


class MigrationApplySummary(TypedDict):
    """Migration / events-apply-to-disk job summary.

    Shares :class:`LeftoverEmptyFolders` with organize -- not :class:`CompletionBase`.
    ``elapsed_seconds`` is injected by ``jobs.py`` (same boundary as organize).
    """

    label: str
    migrated: int
    resumed: int
    leftover_empty_folders: NotRequired[LeftoverEmptyFolders]
    groups: NotRequired[list[AppliedReviewGroupPayload]]
    elapsed_seconds: NotRequired[float]


def _reveal_folder_on_drive(drive_root: Path, relative: str, *, up: int) -> Path:
    """Absolute folder for a reveal link, from a drive-relative ``file_copies.relative``.

    ``file_copies.relative`` is never an absolute path. Returning its parent alone made
    ``/api/reveal`` resolve against the server process cwd ((qq)); join to the connected
    drive mount first. ``up`` is 1 for an event day folder, 2 for a trip header folder.
    """
    folder = PurePosixPath(relative)
    for _ in range(up):
        folder = folder.parent
    return drive_root / folder


def migration_apply(
    path: Path,
    db: Path,
    named_events: Sequence[NamedEventSelection] | None = None,
    named_trips: Sequence[NamedTripSelection] | None = None,
) -> JobTarget:
    """Build a job target that relocates a connected drive's files under the current template.

    ``named_events`` (each an ``{"event_id", "name", "start", "end"}`` dict) and ``named_trips``
    (each a ``{"trip_id", "name", "start", "end"}`` dict), both from a just-completed Trips &
    events naming session, are optional and change nothing about the migration itself - a
    confirmed trip reaches this same path, through the same `RenderContext.trip` seam an event
    already used (Stage 2d, 13.4). When given, the result also reports each named item's **real**
    destination folder - looked up from the catalog after the migration has actually placed the
    files there, never guessed or rendered ahead of time - the data a "reveal in file manager" row
    needs (13.3a). A plain Settings-screen migration, which has no session to report on, omits
    both and is unaffected.
    """

    def target(progress: ProgressCallback, cancel: threading.Event) -> MigrationApplySummary:
        marker = read_marker(path)
        if marker is None:
            raise not_a_drive(path)
        with Catalog(db) as catalog, HashCache.beside(db) as cache:
            catalog.upsert_drive(uuid=marker.uuid, label=marker.label)
            pin_existing_layout(catalog)
            scheme = resolve_scheme(catalog)
            routes, rules_by_sha, _evidence_warning = _resolve_migration_routes(
                catalog, marker.uuid, path, cache=cache, progress=progress, cancel=cancel
            )
            outcome = run_migration(
                catalog,
                LocalDestination(path),
                marker.uuid,
                scheme,
                apply=True,
                routes=routes,
                rules_by_sha=rules_by_sha,
                progress=progress,
                cancel=cancel,
            )
            groups: list[AppliedReviewGroupPayload] = []
            for event in named_events or ():
                relative = catalog.sample_relative_for_event(event["event_id"], marker.uuid)
                if relative is None:
                    continue  # nothing of this event landed on this drive -- nothing to reveal
                groups.append(
                    {
                        "kind": "event",
                        "name": event["name"],
                        "start": event["start"],
                        "end": event["end"],
                        "path": str(_reveal_folder_on_drive(path, relative, up=1)),
                    }
                )
            for trip in named_trips or ():
                relative = catalog.sample_relative_for_trip(trip["trip_id"], marker.uuid)
                if relative is None:
                    continue  # nothing of this trip landed on this drive -- nothing to reveal
                # Two levels up, not one: a trip's own header folder holds every one of its days
                # (`layout._trip_segments`), so the reveal row should open that, not one day's.
                groups.append(
                    {
                        "kind": "trip",
                        "name": trip["name"],
                        "start": trip["start"],
                        "end": trip["end"],
                        "path": str(_reveal_folder_on_drive(path, relative, up=2)),
                    }
                )
            leftovers = cleanup_summary_from_old_paths(
                path, catalog.migrated_old_paths(marker.uuid)
            )
        result: MigrationApplySummary = {
            "label": marker.label,
            "migrated": outcome.migrated,
            "resumed": outcome.resumed,
        }
        if leftovers is not None:
            result["leftover_empty_folders"] = leftovers
        if groups:
            result["groups"] = groups
        return result

    return target


class ArmedStatePayload(TypedDict):
    """Whether the drive still has a reversible migration journal (backlog pp)."""

    ok: Literal[True]
    armed: bool
    file_count: int
    run_id: str | None


class UndoRefusalPayload(TypedDict):
    relative: str
    reason: str


class UndoJobSummary(TypedDict):
    label: str
    reversed_files: int
    refused: list[UndoRefusalPayload]
    run_id: str | None
    applied: bool
    elapsed_seconds: NotRequired[float]


def migration_armed_state(path: Path, db: Path) -> ArmedStatePayload | DriveUnavailablePayload:
    """Read-only: does this connected drive still have a reversible migration record?

    Answers from ``catalog.reversible_migration`` only. Never upserts the drive, never touches
    the journal - a tab reload must be able to ask this without changing anything.
    """
    marker = read_marker(path)
    if marker is None:
        return drive_unavailable(path)
    with Catalog(db) as catalog:
        record = catalog.reversible_migration(marker.uuid)
    if record is None:
        return {"ok": True, "armed": False, "file_count": 0, "run_id": None}
    run_id, rows = record
    return {"ok": True, "armed": True, "file_count": len(rows), "run_id": run_id}


def migration_undo(path: Path, db: Path, *, apply: bool) -> JobTarget | DriveUnavailablePayload:
    """Preview or apply the last migration's reversal as a cancellable, progress-streaming job.

    Reuses ``undo_migration`` directly - no parallel journal. Soft-fails with the same drive
    correction as migration preview when the path is not a connected drive, so the UI never
    sees a bare job error for "folder inside the drive" / "not a drive yet".
    """
    marker = read_marker(path)
    if marker is None:
        return drive_unavailable(path)

    def target(progress: ProgressCallback, cancel: threading.Event) -> UndoJobSummary:
        with Catalog(db) as catalog:
            record = catalog.reversible_migration(marker.uuid)
            run_id = record[0] if record is not None else None
            outcome = undo_migration(
                catalog,
                LocalDestination(path),
                marker.uuid,
                apply=apply,
                progress=progress,
                cancel=cancel,
            )
        return {
            "label": marker.label,
            "reversed_files": outcome.reversed_files,
            "refused": [
                {"relative": relative, "reason": reason} for relative, reason in outcome.refused
            ],
            "run_id": run_id,
            "applied": apply,
        }

    return target
