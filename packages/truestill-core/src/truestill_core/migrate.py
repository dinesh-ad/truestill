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
    PATH_LENGTH_WARN,
    TIMELINE_RULE,
    LayoutScheme,
    RenderContext,
    disambiguate_event_folders,
)
from truestill_core.progress import Phase, Progress, ProgressCallback


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

    Returns ``sha256 -> rule``. A file that cannot be read is simply absent, and the caller falls
    back to the per-label decision - never to a guess.
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
        metadata = read_metadata(present)
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


def plan_migration(
    catalog: Catalog,
    drive_uuid: str,
    scheme: LayoutScheme,
    *,
    routes: dict[str, str] | None = None,
    rules_by_sha: dict[str, str] | None = None,
) -> MigrationPlan:
    """Compute the ``old -> new`` relocations ``scheme`` implies for a drive's copies. Pure.

    Renders through **the same** :meth:`LayoutScheme.render` an organize run uses, so a migrated
    library and a freshly organized one are byte-identical under the same layout. ``routes`` maps
    a label to :data:`ROUTE_TIMELINE` or :data:`ROUTE_SIDE_BIN`; anything unmapped is treated as
    a side bin, which is the conservative direction (a file kept beside the years is findable and
    fixable; one wrongly hoisted onto the timeline is mixed into the photo record).

    Event folders are disambiguated across the whole drive before any path is built, so two
    same-date events whose names collide cannot silently merge into one folder.
    """
    routes = routes or {}
    rows = list(catalog.copies_for_migration(drive_uuid))

    # Every event on this drive is known here, which is the only place a collision *can* be seen.
    events: dict[str, tuple[datetime, str, str | None]] = {}
    for r in rows:
        if r["event_slug"] and r["event_start"]:
            start = _parse_dt(r["event_start"])
            assert start is not None
            events[f"{r['event_slug']}|{r['event_start']}"] = (
                start,
                str(r["event_slug"]),
                r["event_name"],
            )
    folders = disambiguate_event_folders(
        [(key, start, slug, name) for key, (start, slug, name) in events.items()],
        naming=scheme.timeline.event_naming,
    )
    event_notes = [f.note for f in folders if f.note]

    moves: list[Move] = []
    unchanged = 0
    warnings: list[str] = list(event_notes)
    targets: dict[str, str] = {}  # lower(new) -> new, to spot case-insensitive collisions

    for row in rows:
        current = str(row["relative"])
        filename = PurePosixPath(current).name
        event = None
        event_name = None
        if row["event_slug"] and row["event_start"]:
            event = (_parse_dt(row["event_start"]), str(row["event_slug"]))
            event_name = row["event_name"]
        directory = scheme.render(
            rule_for_row(row, routes, rules_by_sha),
            RenderContext(
                category=str(row["category"]),
                captured_at=_parse_dt(row["captured_at"]),
                event=event,  # type: ignore[arg-type]  # start parsed to datetime above
                event_name=event_name,
            ),
        )
        new_relative = (directory / filename).as_posix()
        if new_relative == current:
            unchanged += 1
            continue

        key = new_relative.lower()
        if key in targets:
            warnings.append(f"two files would land at the same path: {new_relative}")
        targets[key] = new_relative
        if len(new_relative) > PATH_LENGTH_WARN:
            warnings.append(f"{new_relative} is near the Windows 260-char limit")
        moves.append(Move(str(row["sha256"]), current, new_relative, row["copy_sha256"]))

    return MigrationPlan(drive_uuid=drive_uuid, moves=moves, unchanged=unchanged, warnings=warnings)


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

    ``progress`` is called ``(done, total)`` per move; ``cancel`` stops the run early (moves
    already completed stay -- the run is resumable). A cancelled run's remaining journal rows are
    picked up by the next invocation.
    """
    resumed = resume_migration(catalog, destination, drive_uuid) if apply else 0
    plan = plan_migration(catalog, drive_uuid, scheme, routes=routes, rules_by_sha=rules_by_sha)
    if not apply:
        return MigrationOutcome(plan=plan, resumed=0, migrated=0, applied=False)

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
) -> UndoOutcome:
    """Put a completed migration back, move by move, with the forward run's safety discipline.

    Walks the newest run's completed moves **in reverse**, so a path freed by one reversal is
    available to the next - the mirror of how the forward run built them up. Each move is
    relocated back, **re-hashed at its old path, and only then is the new copy removed**; a
    failed verify raises and leaves both the file and its journal row intact, so nothing is lost
    and the reversal can be retried.

    Interruption is safe for the same reason the forward run is: a row is dropped only after its
    file is verified back in place, so re-running continues from wherever it stopped.

    **A file that changed since the migration is refused, not clobbered.** If the copy at the new
    path no longer hashes to what the migration recorded, someone edited or replaced it, and
    putting the old path back would discard that work.

    ``O(moves in the run)``, paying the same hash-verify the forward path already pays.
    """
    record = catalog.reversible_migration(drive_uuid)
    if record is None:
        return UndoOutcome(reversed_files=0, refused=[])
    _, rows = record

    refused: list[tuple[str, str]] = []
    done = 0
    for row in rows:
        new_relative = str(row["new_relative"])
        old_relative = str(row["old_relative"])
        expected = row["copy_sha256"]

        if not destination.exists(new_relative):
            refused.append((new_relative, "the migrated copy is no longer there"))
            continue
        if expected and destination.checksum(new_relative) != expected:
            refused.append((new_relative, "changed since the migration -- left untouched"))
            continue
        if not apply:
            done += 1
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
        if progress is not None:
            progress(Progress(done, len(rows), Phase.MOVING, PurePosixPath(old_relative).name))

    return UndoOutcome(reversed_files=done, refused=refused)
