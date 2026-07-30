"""Re-place an already-organized drive's copies under a new layout template.

The dangerous operation of this whole feature. It obeys three invariants:

* **Copy-only.** It moves *destination copies* recorded in ``file_copies``; source files are
  never touched. A move is a copy-then-remove at the destination, so a byte-identical copy's
  ``copy_sha256`` stays valid and ``verify`` keeps passing.
* **One connected drive at a time.** It relocates only the drive it is handed; other drives'
  copies are left untouched and reported as pending until each is reconnected.
* **Crash-safe and resumable.** Every move is journalled before any file is touched, and each
  move runs copy -> verify -> update-catalog -> remove-old in that order. A run interrupted at
  any point is recovered by replaying the journal on the next invocation.

Per move, the catalog's recorded ``relative`` is the state indicator: it flips from the old to
the new path in a single transaction *after* the new copy is written and verified, and the
journal row (which retains the old path) is cleared only *after* the old copy is removed -- so a
crash between those steps leaves a recoverable orphan, never a lost or unrecorded file.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any
from uuid import uuid4

from truestill_core.catalog import Catalog
from truestill_core.categorize import build_rules, categorize, deterministic_side_bin_labels
from truestill_core.destinations.base import Destination, DestinationError
from truestill_core.exif import ExiftoolMissingError, read_metadata
from truestill_core.layout import (
    EVERYDAY_DAY_THRESHOLD_KEY,
    PATH_LENGTH_WARN,
    TIMELINE_RULE,
    EventNaming,
    LayoutScheme,
    RenderContext,
    classify,
    count_capture_days,
    disambiguate_event_folders,
    everyday_axis_changed,
    everyday_day_reconcile_reason,
    heavy_capture_days,
    normalize_everyday_day_threshold,
)
from truestill_core.progress import Phase, Progress, ProgressCallback

_log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Move:
    """One copy to relocate, from ``old_relative`` to ``new_relative`` on a drive."""

    sha256: str
    old_relative: str
    new_relative: str
    copy_sha256: str | None


@dataclass(frozen=True)
class MigrationPlan:
    """The relocations a template change implies for one drive (pure; nothing is moved)."""

    drive_uuid: str
    moves: list[Move]
    unchanged: int
    warnings: list[str]
    #: Per affected capture day: why Everyday files are moving between month and day folders.
    #: Empty when the threshold axis did not change any path. Never a substitute for ``moves``.
    day_folder_reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class MigrationOutcome:
    """The result of planning (and possibly applying) a migration for one drive."""

    plan: MigrationPlan
    resumed: int  # moves recovered from a prior interrupted run
    migrated: int  # moves applied this run (0 in preview)
    applied: bool


def _parse_dt(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


#: How a label's files are routed when the migration re-renders them.
ROUTE_TIMELINE = "timeline"
ROUTE_SIDE_BIN = "side bin"
ROUTE_AMBIGUOUS = "ambiguous"


@dataclass(frozen=True, slots=True)
class LabelRoute:
    """Where one label's files are headed, and how confident the migration is about it."""

    label: str
    route: str
    files: int
    reason: str
    #: Set when per-file re-derivation resolved the split rather than the label alone.
    resolved_per_file: bool = False

    @property
    def needs_decision(self) -> bool:
        return self.route == ROUTE_AMBIGUOUS


def label_routes(catalog: Catalog, drive_uuid: str) -> list[LabelRoute]:
    """Decide, per distinct label, whether its files belong on the timeline or in a side bin.

    **The migration cannot ask the organizer.** The catalog records a *label*, not the rule that
    produced it (`files.category`), and an organize run routes on the rule -- so this is the
    bridge, and it is only allowed to be certain where the rule chain actually is.

    Certainty comes from `categorize.deterministic_side_bin_labels`: the screenshot rules, the
    messenger conventions and the `Saved` fallback emit labels from a fixed set, so a file
    carrying one of those could not have come from the camera rule. Everything else is
    **ambiguous by construction** - ``Camera`` is the device rule's default label *and* a
    perfectly possible ``Software`` value, and under ``--by-device`` any label at all could be
    hardware. Those are surfaced for a decision, never guessed.

    Pure: reads catalog rows, touches no file. **O(files)** for the tally, **O(labels)** after.
    """
    counts: dict[str, int] = {}
    for row in catalog.copies_for_migration(drive_uuid):
        label = str(row["category"])
        counts[label] = counts.get(label, 0) + 1

    deterministic = deterministic_side_bin_labels()
    routes: list[LabelRoute] = []
    for label, files in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
        if label in deterministic:
            routes.append(
                LabelRoute(
                    label=label,
                    route=ROUTE_SIDE_BIN,
                    files=files,
                    reason="only a screenshot, messenger or fallback rule can produce this label",
                )
            )
        else:
            routes.append(
                LabelRoute(
                    label=label,
                    route=ROUTE_AMBIGUOUS,
                    files=files,
                    reason=(
                        "the camera rule and the software rule can both produce this label "
                        "(and --by-device makes any label possible), so it cannot be decided "
                        "from the catalog alone"
                    ),
                )
            )
    return routes


def rederive_rules(
    catalog: Catalog,
    drive_uuid: str,
    drive_root: Path,
    routes: Sequence[LabelRoute],
    *,
    by_device: bool = False,
    progress: ProgressCallback | None = None,
    cancel: threading.Event | None = None,
) -> dict[str, str]:
    """Re-read metadata for the **ambiguous labels only** and recover each file's real rule.

    This is the honest answer to a label that could have come from either side: ask the files.
    The copies are on the drive being migrated - which is connected by definition, since the
    migration is about to move them - so the evidence is available, and it is read through the
    same batched reader and the same rule chain an organize run uses.

    **Bounded to ambiguous labels.** Deterministic side-bin labels are never re-read, so a
    library whose only ambiguous label is ``Camera`` pays for its camera files and nothing else.
    Cost is one batched exiftool pass (~2.2 ms/file measured at 12 MP, header reads only) plus
    an O(1) rule evaluation per file: **O(ambiguous files)**, and zero when nothing is ambiguous.

    ``progress`` and ``cancel`` are forwarded to :func:`read_metadata` - that exiftool pass is
    the dominant cost of a migration preview on a slow mount, and silence there is the freeze
    backlog (oo) recorded. Phase stays :attr:`Phase.SCANNING` (the same work organize reports).

    Returns ``sha256 -> rule``. A file that cannot be read is simply absent, and the caller falls
    back to the per-label decision - never to a guess. A cancelled read returns whatever was
    finished; absent files fall through to the per-label decision the same way.
    """
    ambiguous = {r.label for r in routes if r.needs_decision}
    if not ambiguous:
        return {}

    rows = [r for r in catalog.copies_for_migration(drive_uuid) if str(r["category"]) in ambiguous]
    paths = [drive_root / str(r["relative"]) for r in rows]
    present = [p for p in paths if p.exists()]
    if not present:
        return {}

    try:
        metadata = read_metadata(present, progress=progress, cancel=cancel)
    except ExiftoolMissingError:
        # Without the binary there is no evidence to re-derive from. Returning nothing falls the
        # caller back to the per-label decision, which surfaces the ambiguity for a human --
        # strictly better than failing the whole migration, and never a silent guess.
        return {}
    chain = build_rules(by_device=by_device)
    rules: dict[str, str] = {}
    for row, path in zip(rows, paths, strict=True):
        if path not in metadata:
            continue
        # Categorize against the ORIGINAL filename: the organized copy is renamed
        # `YYYYMMDD_HHMMSS_<original>`, and the screenshot/messenger rules read the name.
        original = str(row["original_name"] or path.name)
        rules[str(row["sha256"])] = categorize(Path(original), metadata[path], chain).rule
    return rules


def rule_for_row(
    row: Any, routes: dict[str, str], rules_by_sha: dict[str, str] | None = None
) -> str:
    """The rule a migration should route this row by, given a per-label decision."""
    if rules_by_sha:
        rule = rules_by_sha.get(str(row["sha256"]))
        if rule is not None:
            return rule  # the file's own evidence beats any per-label decision
    decided = routes.get(str(row["category"]), ROUTE_SIDE_BIN)
    return TIMELINE_RULE if decided == ROUTE_TIMELINE else "fallback"


def _migration_headers(
    rows: Sequence[Any],
    scheme: LayoutScheme,
    routes: dict[str, str],
    rules_by_sha: dict[str, str] | None,
) -> dict[str, tuple[datetime, str, str | None, EventNaming]]:
    """One representative row per event and per confirmed trip on this drive, keyed for
    disambiguation. A day claimed by a trip dissolves its event (Stage 2d §2: the trip claims the
    whole day, so every one of the event's own rows -- an event never spans more than one day,
    `events.py` -- is trip-claimed too); such an event is excluded, since none of its rows will
    ever actually render an EVENT_DAY path.

    A trip candidate additionally requires its representative row's own rule to resolve to the
    timeline. `trip_days` is joined day-keyed (any file captured that day, any category), unlike
    `events` (only ever linked to a Camera cluster's own files by construction) -- so, unlike the
    event branch, a trip's day-claim is **not** safe-by-construction against picking a side-binned
    row (a same-day screenshot, say) as the naming representative; §2's own table keeps "Side bin"
    a column separate from "Trip", so an off-timeline row must never decide, or receive, a trip's
    folder. O(rows) for the scan, O(headers) after.
    """
    headers: dict[str, tuple[datetime, str, str | None, EventNaming]] = {}
    for r in rows:
        if r["event_slug"] and r["event_start"] and r["trip_id"] is None:
            key = f"event:{r['event_slug']}|{r['event_start']}"
            if key not in headers:
                start = _parse_dt(r["event_start"])
                assert start is not None
                placement = classify(
                    rule_for_row(r, routes, rules_by_sha),
                    RenderContext(category=str(r["category"]), event=(start, str(r["event_slug"]))),
                )
                headers[key] = (
                    start,
                    str(r["event_slug"]),
                    r["event_name"],
                    scheme.template_for(placement).event_naming,
                )
        if r["trip_id"] is not None:
            key = f"trip:{r['trip_id']}"
            rule = rule_for_row(r, routes, rules_by_sha)
            if key not in headers and rule == TIMELINE_RULE:
                start = _parse_dt(r["trip_start"])
                assert start is not None
                placement = classify(
                    rule,
                    RenderContext(category=str(r["category"]), trip=(start, str(r["trip_slug"]))),
                )
                headers[key] = (
                    start,
                    str(r["trip_slug"]),
                    r["trip_name"],
                    scheme.template_for(placement).event_naming,
                )
    return headers


def _disambiguated_folder_notes(
    headers: dict[str, tuple[datetime, str, str | None, EventNaming]],
) -> list[str]:
    """Group headers by their **resolved naming**, not by event-vs-trip, and disambiguate within
    each group -- an event and a trip that resolve to the same naming land in the same group and
    are cross-checked against each other (backlog ``(mm)``'s Stage 13.4 widening: **decision (a),
    cross-group scoping**, achieved for free by grouping on the naming value rather than on
    `Placement`, since a folder-string collision is only possible between two headers already
    spelled the same way). The one case this does not cover -- `TRIP_DAY` deliberately configured
    with a naming that differs from `EVENT_DAY`'s (13.2's escape hatch; no production caller sets
    it) -- cannot collide on the rendered string in the first place (`READABLE` and `SLUG` produce
    structurally different text), so it is not a silent gap; :data:`_log` alarms it below if it is
    ever actually in play, rather than assuming it away.
    """
    by_naming: dict[EventNaming, list[tuple[str, datetime, str, str | None]]] = {}
    for key, (start, slug, name, naming) in headers.items():
        by_naming.setdefault(naming, []).append((key, start, slug, name))
    if len(by_naming) > 1:
        # Crossed once, on the run that first crosses it -- reaches whoever actually configures a
        # diverging TRIP_DAY naming, not just the person reading this comment.
        _log.warning(
            "events and trips are using %d different folder namings this run -- collisions "
            "between them are not cross-checked (trip-grouping-research.md §13.4)",
            len(by_naming),
        )
    folders = [
        folder
        for naming, group in by_naming.items()
        for folder in disambiguate_event_folders(group, naming=naming)
    ]
    return [f.note for f in folders if f.note]


def _unevented_day_counts(
    rows: list[Any],
    routes: dict[str, str],
    rules_by_sha: dict[str, str] | None,
) -> dict[str, int]:
    """One O(n) pass: capture-day counts for timeline files that are not evented or trip-claimed."""
    unevented_times: list[datetime | None] = []
    for row in rows:
        rule = rule_for_row(row, routes, rules_by_sha)
        if rule != TIMELINE_RULE:
            continue
        if row["trip_id"] is not None:
            continue
        if row["event_slug"] and row["event_start"]:
            continue
        unevented_times.append(_parse_dt(row["captured_at"]))
    return count_capture_days(unevented_times)


def _render_migration_relative(
    row: Any,
    scheme: LayoutScheme,
    routes: dict[str, str],
    rules_by_sha: dict[str, str] | None,
    heavy_days: frozenset[str],
) -> tuple[str, str, str | None]:
    """Return ``(current, new_relative, day_key)`` for one migration row."""
    current = str(row["relative"])
    filename = PurePosixPath(current).name
    rule = rule_for_row(row, routes, rules_by_sha)
    event = None
    event_name = None
    if row["event_slug"] and row["event_start"]:
        event = (_parse_dt(row["event_start"]), str(row["event_slug"]))
        event_name = row["event_name"]
    trip = None
    trip_name = None
    if row["trip_id"] is not None and rule == TIMELINE_RULE:
        trip = (_parse_dt(row["trip_start"]), str(row["trip_slug"]))
        trip_name = row["trip_name"]
    captured_at = _parse_dt(row["captured_at"])
    heavy_day = False
    day_key: str | None = None
    if rule == TIMELINE_RULE and trip is None and event is None and captured_at is not None:
        day_key = captured_at.date().isoformat()
        heavy_day = day_key in heavy_days
    directory = scheme.render(
        rule,
        RenderContext(
            category=str(row["category"]),
            captured_at=captured_at,
            event=event,  # type: ignore[arg-type]
            event_name=event_name,
            trip=trip,  # type: ignore[arg-type]
            trip_name=trip_name,
            heavy_day=heavy_day,
        ),
    )
    return current, (directory / filename).as_posix(), day_key


def plan_migration(
    catalog: Catalog,
    drive_uuid: str,
    scheme: LayoutScheme,
    *,
    routes: dict[str, str] | None = None,
    rules_by_sha: dict[str, str] | None = None,
    progress: ProgressCallback | None = None,
    cancel: threading.Event | None = None,
) -> MigrationPlan:
    """Compute the ``old -> new`` relocations ``scheme`` implies for a drive's copies. Pure.

    Renders through **the same** :meth:`LayoutScheme.render` an organize run uses, so a migrated
    library and a freshly organized one are byte-identical under the same layout. ``routes`` maps
    a label to :data:`ROUTE_TIMELINE` or :data:`ROUTE_SIDE_BIN`; anything unmapped is treated as
    a side bin, which is the conservative direction (a file kept beside the years is findable and
    fixable; one wrongly hoisted onto the timeline is mixed into the photo record).

    Event and trip folders are disambiguated **together**, across the whole drive, before any
    path is built, so a same-date event and a confirmed trip whose header names collide cannot
    silently merge into one folder any more than two events could (Stage 2d, 13.4 -- widens
    backlog ``(mm)`` from event-only to event-and-trip). Each header's naming style comes from
    its **own** placement -- one :func:`classify` lookup per event/trip, in place of the fixed
    :data:`Placement.EVERYDAY` lookup `(mm)` originally replaced -- so a migration spells a
    folder exactly as an organize run would. Same asymptotic cost: O(events + trips) either way,
    since the old code also built its lookup dict in one pass.

    Everyday day-folder density is counted in **one** pass over the rows
    (:func:`_unevented_day_counts`), then each file is an O(1) membership check - never a
    recount per file. ``day_folder_reasons`` names each affected day with its count and the
    threshold.

    ``progress`` fires once per copy with ``total = len(rows)`` known before the loop
    (:attr:`Phase.PLANNING`), distinct from the exif re-derivation phase. ``cancel`` stops the
    walk early; the partial plan is returned and writes nothing (this function is pure).
    """
    routes = routes or {}
    rows = list(catalog.copies_for_migration(drive_uuid))
    headers = _migration_headers(rows, scheme, routes, rules_by_sha)
    header_notes = _disambiguated_folder_notes(headers)

    threshold = normalize_everyday_day_threshold(catalog.get_setting(EVERYDAY_DAY_THRESHOLD_KEY))
    day_counts = _unevented_day_counts(rows, routes, rules_by_sha)
    heavy_days = heavy_capture_days(day_counts, threshold=threshold)

    moves: list[Move] = []
    unchanged = 0
    warnings: list[str] = list(header_notes)
    day_axis: dict[str, bool] = {}
    targets: dict[str, str] = {}
    total = len(rows)

    for index, row in enumerate(rows):
        if cancel is not None and cancel.is_set():
            break
        current, new_relative, day_key = _render_migration_relative(
            row, scheme, routes, rules_by_sha, heavy_days
        )
        filename = PurePosixPath(current).name
        if new_relative == current:
            unchanged += 1
        else:
            key = new_relative.lower()
            if key in targets:
                warnings.append(f"two files would land at the same path: {new_relative}")
            targets[key] = new_relative
            if len(new_relative) > PATH_LENGTH_WARN:
                warnings.append(f"{new_relative} is near the Windows 260-char limit")
            moves.append(Move(str(row["sha256"]), current, new_relative, row["copy_sha256"]))
            axis = everyday_axis_changed(current, new_relative)
            if axis is not None and day_key is not None:
                day_axis[day_key] = axis
        if progress is not None:
            progress(Progress(index + 1, total, Phase.PLANNING, filename))

    day_folder_reasons = tuple(
        everyday_day_reconcile_reason(day, day_counts[day], threshold, to_day_folder=to_day)
        for day, to_day in sorted(day_axis.items())
        if day in day_counts
    )
    return MigrationPlan(
        drive_uuid=drive_uuid,
        moves=moves,
        unchanged=unchanged,
        warnings=warnings,
        day_folder_reasons=day_folder_reasons,
    )


def _matches(destination: Destination, relative: str, expected_sha: str | None) -> bool:
    """Whether a stored copy exists and (if we know its hash) verifies."""
    if not destination.exists(relative):
        return False
    if not expected_sha:
        return True  # legacy copy with no recorded hash: existence is the best we can check
    try:
        return destination.checksum(relative) == expected_sha
    except DestinationError:
        return False


def _apply_move(catalog: Catalog, destination: Destination, drive_uuid: str, move: Move) -> None:
    """Advance one move to completion from whatever state it is in (idempotent)."""
    current = catalog.copy_relative(move.sha256, drive_uuid)
    if current is None:  # copy no longer tracked; nothing to do but forget the journal row
        catalog.complete_migration_move(move.sha256, drive_uuid)
        return

    if current == move.new_relative:  # catalog already flipped; only the old orphan may remain
        if move.old_relative != move.new_relative:
            destination.remove(move.old_relative)
        catalog.complete_migration_move(move.sha256, drive_uuid)
        return

    # Catalog still points at the old path: write and verify the new copy first.
    if not _matches(destination, move.new_relative, move.copy_sha256):
        destination.relocate(move.old_relative, move.new_relative)
    if not _matches(destination, move.new_relative, move.copy_sha256):
        message = f"verification failed after relocating to {move.new_relative}"
        raise DestinationError(message)

    catalog.relocate_copy(move.sha256, drive_uuid, move.new_relative)  # the atomic flip
    if move.old_relative != move.new_relative:
        destination.remove(move.old_relative)
    catalog.complete_migration_move(move.sha256, drive_uuid)


def resume_migration(catalog: Catalog, destination: Destination, drive_uuid: str) -> int:
    """Replay any journalled moves left by an interrupted run. Returns how many were recovered."""
    pending = catalog.pending_migration(drive_uuid)
    for row in pending:
        move = Move(
            sha256=str(row["sha256"]),
            old_relative=str(row["old_relative"]),
            new_relative=str(row["new_relative"]),
            copy_sha256=row["copy_sha256"],
        )
        _apply_move(catalog, destination, drive_uuid, move)
    return len(pending)


def run_migration(
    catalog: Catalog,
    destination: Destination,
    drive_uuid: str,
    scheme: LayoutScheme,
    *,
    apply: bool,
    routes: dict[str, str] | None = None,
    rules_by_sha: dict[str, str] | None = None,
    progress: ProgressCallback | None = None,
    cancel: threading.Event | None = None,
) -> MigrationOutcome:
    """Resume any interrupted run, plan the relocations, and (if ``apply``) carry them out.

    Progress covers **both** paths: the planning pass (:attr:`Phase.PLANNING`, every copy) always
    ticks, including a dry-run preview - silence on that walk is the multi-minute freeze backlog
    (oo) recorded. On apply, each completed move then ticks :attr:`Phase.MOVING`. ``cancel``
    stops whichever phase is running; a cancelled apply leaves completed moves in place (the
    journal is resumable) and never opens a run if planning itself was cancelled.
    """
    resumed = resume_migration(catalog, destination, drive_uuid) if apply else 0
    plan = plan_migration(
        catalog,
        drive_uuid,
        scheme,
        routes=routes,
        rules_by_sha=rules_by_sha,
        progress=progress,
        cancel=cancel,
    )
    if not apply or (cancel is not None and cancel.is_set()):
        return MigrationOutcome(
            plan=plan, resumed=0 if not apply else resumed, migrated=0, applied=False
        )

    run_id = uuid4().hex
    catalog.start_migration_run(run_id, drive_uuid)
    catalog.record_migration_moves(
        [
            (m.sha256, drive_uuid, m.old_relative, m.new_relative, m.copy_sha256, run_id)
            for m in plan.moves
        ]
    )
    migrated = 0
    total = len(plan.moves)
    for move in plan.moves:
        if cancel is not None and cancel.is_set():
            break
        _apply_move(catalog, destination, drive_uuid, move)
        migrated += 1
        if progress is not None:
            progress(Progress(migrated, total, Phase.MOVING, PurePosixPath(move.new_relative).name))
    if migrated == total:
        catalog.finish_migration_run(run_id)
    return MigrationOutcome(plan=plan, resumed=resumed, migrated=migrated, applied=True)


@dataclass(frozen=True, slots=True)
class UndoOutcome:
    """What reversing a migration achieved, and what it refused to touch."""

    reversed_files: int
    #: ``(relative, reason)`` for each move left alone -- never silently overwritten.
    refused: list[tuple[str, str]]

    @property
    def clean(self) -> bool:
        return not self.refused


def undo_migration(
    catalog: Catalog,
    destination: Destination,
    drive_uuid: str,
    *,
    apply: bool,
    progress: ProgressCallback | None = None,
    cancel: threading.Event | None = None,
) -> UndoOutcome:
    """Put a completed migration back, move by move, with the forward run's safety discipline.

    Walks the newest run's completed moves **in reverse**, so a path freed by one reversal is
    available to the next - the mirror of how the forward run built them up. Each move is
    relocated back, **re-hashed at its old path, and only then is the new copy removed**; a
    failed verify raises and leaves both the file and its journal row intact, so nothing is lost
    and the reversal can be retried.

    Interruption is safe for the same reason the forward run is: a row is dropped only after its
    file is verified back in place, so re-running continues from wherever it stopped.
    ``cancel`` stops the walk early the same way; remaining journal rows stay for a resume.

    **A file that changed since the migration is refused, not clobbered.** If the copy at the new
    path no longer hashes to what the migration recorded, someone edited or replaced it, and
    putting the old path back would discard that work.

    Progress fires on **every** row of the walk - preview and apply alike - so a multi-thousand
    file check over a slow mount is never a silent freeze. Refused rows are reported in
    ``UndoOutcome.refused`` and still tick the counter.

    ``O(moves in the run)``, paying the same hash-verify the forward path already pays.
    """
    record = catalog.reversible_migration(drive_uuid)
    if record is None:
        return UndoOutcome(reversed_files=0, refused=[])
    _, rows = record
    total = len(rows)

    refused: list[tuple[str, str]] = []
    done = 0
    processed = 0
    for row in rows:
        if cancel is not None and cancel.is_set():
            break
        new_relative = str(row["new_relative"])
        old_relative = str(row["old_relative"])
        expected = row["copy_sha256"]
        item = PurePosixPath(old_relative).name

        if not destination.exists(new_relative):
            refused.append((new_relative, "the migrated copy is no longer there"))
            processed += 1
            if progress is not None:
                progress(Progress(processed, total, Phase.RESTORING, item))
            continue
        if expected and destination.checksum(new_relative) != expected:
            refused.append((new_relative, "changed since the migration -- left untouched"))
            processed += 1
            if progress is not None:
                progress(Progress(processed, total, Phase.RESTORING, item))
            continue
        if not apply:
            done += 1
            processed += 1
            if progress is not None:
                progress(Progress(processed, total, Phase.RESTORING, item))
            continue

        destination.relocate(new_relative, old_relative)
        if not _matches(destination, old_relative, expected):
            message = f"verification failed after putting {old_relative} back"
            raise DestinationError(message)
        catalog.relocate_copy(str(row["sha256"]), drive_uuid, old_relative)
        # Mirror the forward path exactly: the migrated copy is removed only after the restored
        # one has been re-hashed, so there is never an instant with zero copies.
        if old_relative != new_relative:
            destination.remove(new_relative)
        catalog.forget_migration_move(str(row["sha256"]), drive_uuid)
        done += 1
        processed += 1
        if progress is not None:
            progress(Progress(processed, total, Phase.RESTORING, item))

    return UndoOutcome(reversed_files=done, refused=refused)
