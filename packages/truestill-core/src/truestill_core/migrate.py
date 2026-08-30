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
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from pathlib import Path, PurePosixPath
from typing import Any, Final
from uuid import uuid4

from truestill_core.catalog import Catalog
from truestill_core.categorize import build_rules, categorize, deterministic_side_bin_labels
from truestill_core.decisions import document_key_text
from truestill_core.destinations.base import Destination, DestinationError
from truestill_core.drive_unwritable import persists_for_the_run
from truestill_core.events import slugify
from truestill_core.exif import ExiftoolMissingError, read_metadata
from truestill_core.hash_cache import HashCache
from truestill_core.layout import (
    EVERYDAY_DAY_THRESHOLD_KEY,
    PATH_LENGTH_WARN,
    TIMELINE_RULE,
    TIMELINE_RULES,
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
from truestill_core.models import RuleName
from truestill_core.progress import Phase, Progress, ProgressCallback
from truestill_core.run_health import watcher_for
from truestill_core.run_record import RunHeader, build_run_record, record_organize

_log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Move:
    """One copy to relocate, from ``old_relative`` to ``new_relative`` on a drive."""

    sha256: str
    old_relative: str
    new_relative: str
    copy_sha256: str | None
    #: Bytes, from the catalog row the plan was built from - **never a `stat`**. `relocate` is
    #: a `copy2`, so a migration writes every one of these again, and the run watcher needs to
    #: know how big the biggest one still ahead of it is. ``None`` for a legacy row that never
    #: recorded a size; such a file contributes 0 and the absolute floor still applies.
    size: int | None = None


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


#: What a cancelled migration says. **One string, both surfaces** (`IMPLEMENTATION_STANDARDS.md`
#: §9), and it names the way forward because a stopped migration is a RESUMABLE state: the
#: journal keeps every move it did not reach, so re-running finishes the job.
CANCELLED_REASON = (
    "you stopped it. Nothing was left half-moved, and the moves it did not reach are still "
    "recorded - migrate again to finish."
)


class VerificationFailedError(DestinationError):
    """The destination read back cleanly and returned bytes that are not what it was given.

    ⚠ **A TYPE RATHER THAN A MESSAGE, because it is the one failure here with NO CAUSE TO
    CHAIN.** Every other way a move can fail arrives as an `OSError` wrapped by the backend, and
    `drive_unwritable.persists_for_the_run` classifies it from `__cause__`. This one raised
    nothing: `checksum` succeeded and simply disagreed. Classifying it by matching the sentence
    would be exactly what `IMPLEMENTATION_STANDARDS.md` §9 forbids - *"errors are matched on an
    exception name, never on message text"* - so it gets a name.
    """


class MigrationStopKind(StrEnum):
    """Why a migration ended before it reached every move. `(agm)` D1.

    ⚠ **A field rather than a phrase inside the reason**, for `VerificationFailedError`'s reason: a
    surface that must word a user's cancel differently from a failing drive would otherwise parse
    the sentence.
    """

    #: The user asked it to stop. Not a failure and must never read as one.
    CANCELLED = "cancelled"
    #: `run_health` saw the ground move under the run - the disk filling, the device changing.
    GROUND_MOVED = "ground_moved"
    #: A condition that outlives the file: a read-only remount, a failing device, a destination
    #: that does not store what it is handed. `(agi)`'s predicate, plus `VerificationFailedError`.
    COULD_NOT_CONTINUE = "could_not_continue"


@dataclass(frozen=True, slots=True)
class MigrationStop:
    """Why a migration ended early, and how much it never reached. `(agm)` D1.

    ⚠ **`kind` has NO DEFAULT**, the same ruling `undo.UndoStop` carries: defaulting it either
    way is a decision nobody made, and there are few enough construction sites to answer for it.
    """

    kind: MigrationStopKind
    reason: str
    never_attempted: int


@dataclass(frozen=True, slots=True)
class StopWording:
    """What one stop kind is called where a person reads it, and whether it is a fault."""

    #: The headline. A user's own act and a failing drive must never share a word.
    headline: str
    #: True when the run failed to do what it was asked. Decides the CLI's stream and exit code,
    #: and whether a screen paints the outcome as a warning.
    fault: bool


#: ⚠ **ONE WORDING HOME FOR EVERY SURFACE.** `(ahc)`
#:
#: The CLI derived this inline as ``kind is CANCELLED`` and the app screens derived it not at all.
#: A third derivation in JavaScript would have been a second vocabulary in a second language,
#: which is `MIGRATE_CARD_NAME`'s lesson (`test_the_rearrange_card_name.py`: one name, retyped in
#: four places, drifted). So the words live here, the CLI reads them, and the app **service** puts
#: them in the payload - `app.js` renders text it was handed and maps no kinds of its own.
#:
#: ⚠ **A table rather than a derivation**, the reasoning
#: `test_migrate_survives_one_bad_file._WORDING` already gives for its own: a control derived from
#: a display string is one rename away from a stop that stops being reported. Indexing is
#: deliberate too - a member added tomorrow raises `KeyError` here rather than being worded by an
#: `else` nobody wrote for it.
STOP_WORDING: Final[dict[MigrationStopKind, StopWording]] = {
    MigrationStopKind.CANCELLED: StopWording("Cancelled", fault=False),
    MigrationStopKind.GROUND_MOVED: StopWording("Stopped", fault=True),
    MigrationStopKind.COULD_NOT_CONTINUE: StopWording("Stopped", fault=True),
}


@dataclass(frozen=True)
class MigrationOutcome:
    """The result of planning (and possibly applying) a migration for one drive."""

    plan: MigrationPlan
    resumed: int  # moves recovered from a prior interrupted run
    migrated: int  # moves applied this run (0 in preview)
    applied: bool
    #: Why the run stopped short, or ``None`` if it did not.
    #: A field rather than an exception because a migration that stops half-way has **done**
    #: something - `migrated` is the count and the journal makes the rest resumable - and
    #: raising would throw that away along with the reason.
    #: ⚠ **Was a bare `str` until `(agm)`**, which made a cancel and a failing drive one word.
    stopped: MigrationStop | None = None
    #: ``(relative, reason)`` per move this run could not apply and did not stop for.
    #: **Deliberately the shape `undo_migration` already returns** - the forward path was the
    #: outlier against its own undo, which has named its refusals since it was written.
    refused: list[tuple[str, str]] = field(default_factory=list)


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


#: Wraps whatever `ensure_exiftool` said, which already names the tool, its job, and the fix for
#: the situation the reader is in. This adds only the consequence *for this migration*, which
#: the exif layer cannot know.
_UNAVAILABLE_REASON = (
    "Folder names could not be checked against what is stored inside the files, so some were "
    "sorted by their existing label instead. {detail}"
)


@dataclass(frozen=True, slots=True)
class RederivedRules:
    """Re-derived rules, and why the evidence was not read when it was not.

    A bare ``dict`` could not carry the second half, and that is exactly what made the missing
    binary silent: an empty mapping means both *"the evidence disagreed with nothing"* and
    *"there was no evidence to read"*, and only one of those is a problem worth telling someone
    about. §9 asks for a degraded outcome to be counted **and named**; this is the naming.
    """

    #: ``sha256 -> rule``. Empty is an ordinary answer, not necessarily a failure.
    rules: dict[str, str]
    #: A user-facing sentence, or ``""`` when the evidence was read normally. Empty on the
    #: nothing-to-do path too: a migration with no ambiguous label never needed exiftool, and
    #: warning it about one would be crying wolf on every ordinary run.
    unavailable_reason: str = ""


def rederive_rules(
    catalog: Catalog,
    drive_uuid: str,
    drive_root: Path,
    routes: Sequence[LabelRoute],
    *,
    by_device: bool = False,
    cache: HashCache | None = None,
    progress: ProgressCallback | None = None,
    cancel: threading.Event | None = None,
) -> RederivedRules:
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

    ``cache`` makes a repeat preview obey §8's warm-read rule ("a warm second pass must make
    **zero** exiftool subprocess calls"). It was omitted here until 2026-07-31, and the omission
    was priced before it was fixed: five previews of the real 2,224-file Output drive ran
    12.27 / 12.21 / 12.22 / 12.28 / 12.25 s - **spread 1.01x**, because nothing was ever cached.
    Planning itself is 82 ms of that. Passing a cache is safe on a preview for the same reason
    `service.organize_preview` has always done it: the sidecar is not the catalog and not the
    drive, which is exactly what §5's two purity guards assert on. Omitting it is still valid and
    simply re-reads; it can only cost work, never change an answer.

    Returns ``sha256 -> rule``. A file that cannot be read is simply absent, and the caller falls
    back to the per-label decision - never to a guess. A cancelled read returns whatever was
    finished; absent files fall through to the per-label decision the same way.
    """
    ambiguous = {r.label for r in routes if r.needs_decision}
    if not ambiguous:
        return RederivedRules({})

    rows = [r for r in catalog.copies_for_migration(drive_uuid) if str(r["category"]) in ambiguous]
    paths = [drive_root / str(r["relative"]) for r in rows]
    present = [p for p in paths if p.exists()]
    if not present:
        return RederivedRules({})

    try:
        metadata = read_metadata(present, cache=cache, progress=progress, cancel=cancel)
    except ExiftoolMissingError as exc:
        # Without the binary there is no evidence to re-derive from. Returning no rules falls the
        # caller back to the per-label decision, which surfaces the ambiguity for a human --
        # strictly better than failing the whole migration, and never a silent guess.
        #
        # The reason travels with the empty result because the degradation is correct but must
        # not be *quiet*: no rules is indistinguishable from "the evidence said nothing useful",
        # so without this the run reads as "my dates are wrong" rather than "a tool is missing".
        return RederivedRules({}, unavailable_reason=_UNAVAILABLE_REASON.format(detail=exc))
    chain = build_rules(by_device=by_device)
    rules: dict[str, str] = {}
    for row, path in zip(rows, paths, strict=True):
        if path not in metadata:
            continue
        # Categorize against the ORIGINAL filename: the organized copy is renamed
        # `YYYYMMDD_HHMMSS_<original>`, and the screenshot/messenger rules read the name.
        original = str(row["original_name"] or path.name)
        rules[str(row["sha256"])] = categorize(Path(original), metadata[path], chain).rule
    return RederivedRules(rules)


def rule_for_row(
    row: Any, routes: dict[str, str], rules_by_sha: dict[str, str] | None = None
) -> RuleName | str:
    """The rule a migration should route this row by, given a per-label decision."""
    if rules_by_sha:
        rule = rules_by_sha.get(str(row["sha256"]))
        if rule is not None:
            return rule  # the file's own evidence beats any per-label decision
    decided = routes.get(str(row["category"]), ROUTE_SIDE_BIN)
    return TIMELINE_RULE if decided == ROUTE_TIMELINE else RuleName.FALLBACK


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
            if key not in headers and rule in TIMELINE_RULES:
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


def _disambiguated_folders(
    headers: dict[str, tuple[datetime, str, str | None, EventNaming]],
) -> tuple[dict[str, str], list[str]]:
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
    # Both halves are returned, and that is the fix. This used to return the notes alone and
    # drop the folders it had just decided, so the render spelled each event from its own name
    # and every collision landed in one directory while the note said one of them became "(2)".
    return {f.key: f.folder for f in folders}, [f.note for f in folders if f.note]


def _unevented_day_counts(
    rows: list[Any],
    routes: dict[str, str],
    rules_by_sha: dict[str, str] | None,
) -> dict[str, int]:
    """One O(n) pass: capture-day counts for timeline files that are not evented or trip-claimed."""
    unevented_times: list[datetime | None] = []
    for row in rows:
        rule = rule_for_row(row, routes, rules_by_sha)
        if rule not in TIMELINE_RULES:
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
    *,
    header_folders: dict[str, str] | None = None,
) -> tuple[str, str, str | None]:
    """Return ``(current, new_relative, day_key)`` for one migration row.

    ``header_folders`` carries the folder each event/trip was *decided* to use once every header
    on the drive was known - see :func:`_disambiguated_folders`. A same-date name collision can
    only be resolved across the set, never from one row, so the decision has to arrive here
    rather than be recomputed.
    """
    current = str(row["relative"])
    filename = PurePosixPath(current).name
    rule = rule_for_row(row, routes, rules_by_sha)
    # Narrowed rather than silenced: `_parse_dt` returns `datetime | None`, and RenderContext
    # wants `tuple[datetime, str] | None`. An event or trip whose start will not parse has no
    # date to render under, so it is simply not one - which is what the ignores here used to
    # assert without saying (audit F23).
    event: tuple[datetime, str] | None = None
    event_name = None
    if row["event_slug"] and row["event_start"]:
        event_start = _parse_dt(row["event_start"])
        if event_start is not None:
            event = (event_start, str(row["event_slug"]))
            event_name = row["event_name"]
    trip: tuple[datetime, str] | None = None
    trip_name = None
    if row["trip_id"] is not None and rule in TIMELINE_RULES:
        trip_start = _parse_dt(row["trip_start"])
        if trip_start is not None:
            trip = (trip_start, str(row["trip_slug"]))
            trip_name = row["trip_name"]
    captured_at = _parse_dt(row["captured_at"])
    heavy_day = False
    day_key: str | None = None
    if rule in TIMELINE_RULES and trip is None and event is None and captured_at is not None:
        day_key = captured_at.date().isoformat()
        heavy_day = day_key in heavy_days
    # Keyed exactly as `_migration_headers` keyed them; a row whose event dissolved into a trip
    # has no event key by construction, so trip is checked first.
    override = None
    if header_folders:
        if trip is not None:
            override = header_folders.get(f"trip:{row['trip_id']}")
        elif event is not None:
            override = header_folders.get(f"event:{row['event_slug']}|{row['event_start']}")
    directory = scheme.render(
        rule,
        RenderContext(
            category=str(row["category"]),
            captured_at=captured_at,
            event=event,
            event_name=event_name,
            trip=trip,
            trip_name=trip_name,
            heavy_day=heavy_day,
            folder_override=override,
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
    header_folders, header_notes = _disambiguated_folders(headers)

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
            row, scheme, routes, rules_by_sha, heavy_days, header_folders=header_folders
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
            moves.append(
                Move(str(row["sha256"]), current, new_relative, row["copy_sha256"], row["size"])
            )
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


# ══════════════════════════════════════════════════════════════════════════════════════════════
# RENAMING A TRIP OR AN EVENT. `(aix)` stage 1: the plan, and it writes nothing.
#
# 🔑 **IT LIVES HERE BECAUSE A RENAME IS A MIGRATION.** `trips.slug` renders the directory through
# `layout`'s `event_dirname`, so changing a name MOVES PHOTOGRAPHS. The alternative - a catalog
# setter with a lazy folder move - manufactures a divergence nothing can detect: `verify` keys on
# `file_copies.relative`, which a name change does not touch, and `rescan` never reads a slug.
#
# Planning it anywhere else would need `_render_migration_relative` and `_apply_move`, both
# module-private, so the choice is between exporting them and putting the planner beside them.
# Beside them is the one-home answer.
# ══════════════════════════════════════════════════════════════════════════════════════════════


class RenameKind(StrEnum):
    """What is being renamed. Both render through the same folder rule; only the row differs."""

    TRIP = "trip"
    EVENT = "event"


class RenameRefusal(StrEnum):
    """Why a rename will not be attempted. **A loud refusal, never a divergence.**

    digiKam's lesson, adopted deliberately: it answers *"Failed to rename Album"* when Windows
    holds the folder rather than letting the catalog and the disk drift apart. Every member here
    is a condition checked **before** anything moves.
    """

    NO_SUCH_ROW = "no_such_row"
    NOTHING_ON_THIS_DRIVE = "nothing_on_this_drive"
    UNCHANGED = "unchanged"
    EMPTY_NAME = "empty_name"
    NOT_PATH_SAFE = "not_path_safe"
    FOLDER_EXISTS = "folder_exists"


#: ⚠ **ONE WORDING HOME FOR EVERY SURFACE**, which is `STOP_WORDING`'s rule applied to renaming -
#: the same choice `decisions.py` records for restore. The CLI and the app render these; neither
#: re-words a refusal at a call site, because two copies of one sentence drift the first time
#: either is corrected.
RENAME_WORDING: Final[dict[RenameRefusal, str]] = {
    RenameRefusal.NO_SUCH_ROW: "there is no {kind} with that id in this catalog",
    RenameRefusal.NOTHING_ON_THIS_DRIVE: (
        "that {kind} has no photographs on this drive, so there is nothing here to rename"
    ),
    RenameRefusal.UNCHANGED: "that is already the name; nothing would move",
    RenameRefusal.EMPTY_NAME: "a {kind} needs a name; an empty one would leave it unnamed",
    RenameRefusal.NOT_PATH_SAFE: (
        "{name!r} leaves nothing a folder can be named after once illegal characters are removed"
    ),
    RenameRefusal.FOLDER_EXISTS: (
        "another folder is already called {folder!r} on this drive, and renaming into it would "
        "merge two sets of photographs under one name"
    ),
}


def rename_refusal_sentence(refusal: RenameRefusal, **fields: object) -> str:
    """The one rendering of a refusal. Callers pass facts, never prose."""
    return RENAME_WORDING[refusal].format(**fields)


@dataclass(frozen=True)
class RenamePlan:
    """What renaming one trip or event would move. **Pure: nothing is written.**

    ``refusal`` and ``moves`` are mutually exclusive by construction - a refused plan has no
    moves, and a plan with moves has no refusal. ``moves`` may legitimately be empty with no
    refusal when the new name renders the same folder as the old one for every copy, which is
    not the same thing as the name being unchanged.
    """

    kind: RenameKind
    row_id: int
    old_name: str
    new_name: str
    new_slug: str
    moves: tuple[Move, ...] = ()
    refusal: RenameRefusal | None = None
    refusal_detail: str = ""

    @property
    def may_apply(self) -> bool:
        return self.refusal is None and bool(self.moves)


def _renamed_rows(rows: Sequence[Any], kind: RenameKind, row_id: int) -> list[int]:
    """Indices of the rows this rename touches. Row-keyed, never by slug or by day set.

    ⚠ **`(aix)`'s ruling: naming is identity-keyed, renaming is ROW-keyed.** A trip is identified
    by the days it claims and an event by its membership hash, so keying a rename on either would
    inherit that asymmetry - and for an event whose membership changed since it was named, the
    signature no longer matches anything the user is looking at. The row id is stable for both.
    """
    key = "trip_id" if kind is RenameKind.TRIP else "event_id"
    return [i for i, row in enumerate(rows) if row[key] is not None and int(row[key]) == row_id]


class _RenamedRow:
    """One `copies_for_migration` row with a trip's or event's slug and name substituted.

    ⚠ **A wrapper rather than a mutated row**: `sqlite3.Row` is read-only, and the planner must
    see the OLD state for every other row on the drive - a rename re-renders one trip against an
    otherwise unchanged library.
    """

    __slots__ = ("_overrides", "_row")

    def __init__(self, row: Any, overrides: dict[str, object]) -> None:
        self._row = row
        self._overrides = overrides

    def __getitem__(self, key: str) -> Any:
        return self._overrides[key] if key in self._overrides else self._row[key]


def _plan_relatives(
    catalog: Catalog,
    scheme: LayoutScheme,
    rows: list[Any],
    routes: dict[str, str],
    rules_by_sha: dict[str, str] | None,
) -> list[str]:
    """Where every row would live, rendered through the migration path. Pure.

    The same three steps `plan_migration` takes - headers, disambiguation, heavy days - because a
    rename that rendered its folder any other way could disagree with a migration run about the
    same library, which is the drift `(aix)` refuses to introduce.
    """
    headers = _migration_headers(rows, scheme, routes, rules_by_sha)
    header_folders, _notes = _disambiguated_folders(headers)
    threshold = normalize_everyday_day_threshold(catalog.get_setting(EVERYDAY_DAY_THRESHOLD_KEY))
    heavy_days = heavy_capture_days(
        _unevented_day_counts(rows, routes, rules_by_sha), threshold=threshold
    )
    return [
        _render_migration_relative(
            row, scheme, routes, rules_by_sha, heavy_days, header_folders=header_folders
        )[1]
        for row in rows
    ]


def _refused(
    kind: RenameKind,
    row_id: int,
    new_name: str,
    old_name: str,
    refusal: RenameRefusal,
    **fields: object,
) -> RenamePlan:
    """A refused plan: no moves, and the one sentence for this refusal."""
    return RenamePlan(
        kind=kind,
        row_id=row_id,
        old_name=old_name,
        new_name=new_name,
        new_slug="",
        refusal=refusal,
        refusal_detail=rename_refusal_sentence(refusal, kind=kind.value, name=new_name, **fields),
    )


def plan_rename(
    catalog: Catalog,
    drive_uuid: str,
    scheme: LayoutScheme,
    *,
    kind: RenameKind,
    row_id: int,
    new_name: str,
    routes: dict[str, str] | None = None,
    rules_by_sha: dict[str, str] | None = None,
) -> RenamePlan:
    """What renaming one trip or event would move on this drive. **Pure; nothing is written.**

    🔑 **Rendered through the SAME path a migration uses** - the new folder is computed by
    substituting the slug and name into the rows and re-planning - so a renamed library and a
    freshly organized one stay byte-identical under one layout. Re-implementing the folder rule
    here would be a second answer free to disagree with `plan_migration`'s.

    ⚠ **The whole drive is re-planned, not only the renamed rows**, and that is what makes
    `FOLDER_EXISTS` detectable: `_disambiguated_folders` resolves a same-date name collision
    across the SET by appending ``(2)``. Correct for a migration; **wrong for a rename** - a user
    who asks for a name and silently receives ``Name (2)`` was neither refused nor obeyed.
    """
    routes = routes or {}
    rows = list(catalog.copies_for_migration(drive_uuid))
    touched = _renamed_rows(rows, kind, row_id)
    name_key = "trip_name" if kind is RenameKind.TRIP else "event_name"
    old_name = str(rows[touched[0]][name_key] or "") if touched else ""

    cleaned = new_name.strip()
    if not cleaned:
        return _refused(kind, row_id, new_name, old_name, RenameRefusal.EMPTY_NAME)
    if not touched:
        # ⚠ **Asked of the CATALOG, not of this drive's rows.** `copies_for_migration` is
        # drive-scoped, so an id missing from it may not exist at all or may simply live on a
        # drive that is not plugged in - and those need opposite sentences.
        existing = catalog.named_row_name(kind.value, row_id)
        return _refused(
            kind,
            row_id,
            cleaned,
            existing or "",
            RenameRefusal.NOTHING_ON_THIS_DRIVE
            if existing is not None
            else RenameRefusal.NO_SUCH_ROW,
        )
    if cleaned == old_name:
        return _refused(kind, row_id, cleaned, old_name, RenameRefusal.UNCHANGED)

    # ⚠ **`layout` falls back to the slug when a name sanitises to nothing, and that is right for
    # NAMING and wrong for RENAMING.** A user who typed "///" and got their old folder back was
    # not told - which is `(abw)`'s discarded-answer defect arriving in a new place. A rename
    # states a specific intent, so an unusable name refuses instead.
    # ⚠ **The SAME test `layout` applies**, not a stricter one. `layout` asks whether the
    # sanitised name still carries a letter or digit - the sanitiser REPLACES illegal characters
    # rather than dropping them, so `"///"` survives as `"___"`: truthy, and a folder nobody could
    # recognise. `str.isalnum` is Unicode-aware, so a name in any script passes.
    #
    # ⚠ **Deliberately NOT `slugify(name) == ""`, which would refuse a legitimate name.**
    # Measured: `slugify("日本")` is `""` because the slug alphabet is ASCII, so that test would
    # reject a CJK trip name whose NAME-layout folder renders perfectly. That `slugify` degrades
    # a non-Latin name to an empty slug is a real limitation of `events.slugify` and is **not
    # this stage's to fix** - it is recorded in `(aix)` rather than patched here.
    if not any(character.isalnum() for character in cleaned):
        return _refused(kind, row_id, cleaned, old_name, RenameRefusal.NOT_PATH_SAFE)
    new_slug = slugify(cleaned)

    prefix = kind.value
    renamed: list[Any] = list(rows)
    for index in touched:
        renamed[index] = _RenamedRow(
            rows[index], {f"{prefix}_slug": new_slug, f"{prefix}_name": cleaned}
        )

    before = _plan_relatives(catalog, scheme, rows, routes, rules_by_sha)
    after = _plan_relatives(catalog, scheme, renamed, routes, rules_by_sha)

    # ⚠ **Only rows this rename touches may move.** A row the rename did NOT name, whose path
    # changed anyway, means the new folder displaced somebody - a disambiguation suffix landing on
    # a different trip because this one took its folder. That is the collision by another route.
    moved_elsewhere = [
        i for i in range(len(rows)) if i not in set(touched) and before[i] != after[i]
    ]
    if moved_elsewhere:
        return _refused(
            kind,
            row_id,
            cleaned,
            old_name,
            RenameRefusal.FOLDER_EXISTS,
            folder=PurePosixPath(after[touched[0]]).parent.as_posix(),
        )

    # ⚠ **`old_relative` is where the file IS, not where it would render under the old name.**
    # `_plan_relatives` answers *"where would this go"*, and for a library that has not been
    # migrated under the current template those are different paths - planning a move FROM a
    # rendered path would name a source that does not exist on the drive. `plan_migration` takes
    # `current` from the row for the same reason; `before` is used only to detect displacement.
    moves = tuple(
        Move(
            sha256=str(rows[i]["sha256"]),
            old_relative=str(rows[i]["relative"]),
            new_relative=after[i],
            copy_sha256=rows[i]["copy_sha256"],
            size=rows[i]["size"],
        )
        for i in touched
        if str(rows[i]["relative"]) != after[i]
    )
    return RenamePlan(
        kind=kind,
        row_id=row_id,
        old_name=old_name,
        new_name=cleaned,
        new_slug=new_slug,
        moves=moves,
    )


@dataclass(frozen=True)
class RenameOutcome:
    """What applying a rename did, and whether the name actually changed. `(aix)` stage 2"""

    plan: RenamePlan
    resumed: int
    moved: int
    #: ⚠ **The name flipped only if every move completed.** `False` with `moved > 0` is an
    #: interrupted rename: the photographs are partly at their new paths, the catalog still holds
    #: the OLD name, and the journal makes the rest resumable. That state is honest by design -
    #: see `renamed` below.
    renamed: bool
    refused: tuple[tuple[str, str], ...] = ()
    stopped: MigrationStop | None = None


def _document_key(catalog: Catalog, plan: RenamePlan) -> tuple[str, str] | None:
    """This trip's or event's key **in the decisions document's own vocabulary**, or `None`.

    ⚠ **The document keys a trip by its DAY SET and an event by its SIGNATURE** - never by row id,
    which is exactly the asymmetry `service/trips.py`'s `ExistingNames` records: a trip survives
    its membership changing, an event *is* its membership. A rename is row-keyed, so this is the
    join between the two vocabularies and the only place they meet.

    `None` when the row has nothing the document would carry - a trip with no claimed days - which
    leaves the lease unwritten and the publish refused, the conservative direction.
    """
    if plan.kind is RenameKind.TRIP:
        days = sorted(
            day for day, trip_id in catalog.all_trip_days().items() if trip_id == plan.row_id
        )
        return ("trips", document_key_text(tuple(days))) if days else None
    signature = catalog.event_signature(plan.row_id)
    return ("events", document_key_text(signature)) if signature else None


def apply_rename(
    catalog: Catalog,
    destination: Destination,
    drive_uuid: str,
    plan: RenamePlan,
    *,
    progress: ProgressCallback | None = None,
    cancel: threading.Event | None = None,
) -> RenameOutcome:
    """Carry out a planned rename. **The name flips LAST, and that is the whole design.**

    Order, and each step is load-bearing:

    1. **resume** anything a previous interrupted run left pending;
    2. **journal** every move, computed from the NEW slug, before a byte moves;
    3. **apply** each move through `apply_moves`;
    4. **flip `trips.name`/`slug`** - only once every move completed.

    🔑 **At every interruption point the state is honest: the name is the OLD name until every
    photograph is at its new path.** A half-moved folder under the old name is recoverable and
    tells the truth; a new name over a half-moved folder would be the *"worse than no rename at
    all"* case, and this ordering makes it unreachable rather than unlikely.

    ⚠ **It works because `migration_journal.new_relative` is a PATH** - a resumed run reads the
    destination and needs nothing from the row this function has not flipped yet. That dependency
    is recorded on the schema, where someone changing it will meet it.

    ⚠ **RESUME'S LIMIT, stated rather than implied.** `resume_migration` runs from here and from
    `run_migration` - **not from an ordinary catalog open**. So a rename abandoned mid-flight is
    replayed by the next rename or migration on that drive, and until then the drive holds a
    partly-moved folder under its old name. `truestill rescan` reports the moved copies by content
    hash, so it is *discoverable*; nothing surfaces it unprompted, and that is a finding recorded
    in `(aix)` rather than a gap this stage fills.
    """
    if plan.refusal is not None or not plan.moves:
        return RenameOutcome(plan=plan, resumed=0, moved=0, renamed=False)

    resumed = resume_migration(catalog, destination, drive_uuid)
    applied = apply_moves(
        catalog, destination, drive_uuid, plan.moves, progress=progress, cancel=cancel
    )
    # ⚠ **THE FLIP, AND ITS CONDITION IS THE PROPERTY.** Every move, or the name does not change.
    # A partial rename that renamed anyway would put the catalog's name on a folder that does not
    # hold all of its photographs, and the next `plan_rename` would compute its moves from a slug
    # the drive has only half adopted.
    renamed = applied.migrated == len(plan.moves)
    if renamed:
        # ⚠ **The lease is computed BEFORE the flip and describes the OLD state**, because that is
        # what the drive is expected to hold: *"overwrite this key if the drive still says
        # `old_name`"*. Reading it after the flip would lease the value we just wrote, which
        # matches nothing and leaves the document refused - the state stage 2 shipped with.
        key = _document_key(catalog, plan)
        catalog.rename_row(
            plan.kind.value,
            plan.row_id,
            name=plan.new_name,
            slug=plan.new_slug,
            document_key=key,
            expected=plan.old_name,
        )
    return RenameOutcome(
        plan=plan,
        resumed=resumed,
        moved=applied.migrated,
        renamed=renamed,
        refused=applied.refused,
        stopped=applied.stopped,
    )


def _matches(destination: Destination, relative: str, expected_sha: str | None) -> bool:
    """Whether a stored copy exists and (if we know its hash) verifies.

    ⚠ **A READ THAT FAILED IS NOT A HASH THAT DIFFERED, AND THIS USED TO RETURN `False` FOR
    BOTH.** `LocalDestination.checksum` raises `DestinationError(...) from exc` - the `OSError`
    is chained, deliberately, so it can be classified. Catching it here and answering `False`
    **destroyed that chain**: the caller then raised its own bare error, and
    `drive_unwritable.persists_for_the_run`, which walks `__cause__`, answered `False` for
    `EIO` - a failing drive read as a one-file problem, on the command that rewrites every byte
    of the library. Measured before the fix: `__cause__` was `None` and the predicate said
    `False`.

    So the error propagates and the caller decides. This is `path_reach`'s ruling one module
    over (`IMPLEMENTATION_STANDARDS.md` §9): **absent and refused are different answers**, and
    collapsing them loses the one a caller has to act on. Absence itself is unaffected - it is
    answered by `exists` above, which never raised.
    """
    if not destination.exists(relative):
        return False
    if not expected_sha:
        return True  # legacy copy with no recorded hash: existence is the best we can check
    return destination.checksum(relative) == expected_sha


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
        raise VerificationFailedError(message)

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


def _largest_move_ahead(moves: Sequence[Move]) -> list[int]:
    """For each position, the biggest move at or after it. A suffix maximum in one pass.

    The suffix is load-bearing, not tidiness: `RunHealth` reserves twice this, so a plain
    maximum would keep holding back room for a 4 GB video long after it was written and could
    refuse the last few small files on a disk with plenty of space for them.
    """
    suffix = [0] * (len(moves) + 1)
    for index in range(len(moves) - 1, -1, -1):
        suffix[index] = max(suffix[index + 1], moves[index].size or 0)
    return suffix


def _refusal_entries(refused: Sequence[tuple[str, str]]) -> list[dict[str, object]]:
    """Migrate's per-file entries: **the moves it could not apply, and nothing else.** `(agm)`

    ⚠ **Failures-only is a ruling, not a shortcut.** `(afd)` settled that *a failure list is one
    fact, not two thousand*, and the cost side agrees: an every-file entry is ~319-466 B, so a
    33,000-file migration would spend 10-15 MiB of a 64 MiB budget to say "moved" thirty-three
    thousand times - and push a record somebody needs out of it. The successes are already
    answered by `migrated`, and where each file went is `plan.moves`.

    ``relative`` is the move's **destination** path, because that is what `MigrationOutcome.refused`
    records; a refused file has not moved, so it is still at its old path.
    """
    return [
        {"relative": relative, "status": "failed", "detail": reason} for relative, reason in refused
    ]


def _migration_stop_block(stopped: MigrationStop | None) -> dict[str, object] | None:
    """A stop as the record carries it. ``kind`` is kept, `(agl)`'s ruling on the undo side:
    a user's cancel and a failing drive must not be one word to a reader either."""
    if stopped is None:
        return None
    return {
        "kind": str(stopped.kind),
        "never_attempted": stopped.never_attempted,
        "reason": stopped.reason,
    }


def _record_migration(
    catalog: Catalog,
    destination: Destination,
    drive_uuid: str,
    *,
    run_id: str,
    total: int,
    migrated: int,
    refused: Sequence[tuple[str, str]],
    stopped: MigrationStop | None,
) -> None:
    """Write this migration's record. **Never raises; a failure here must not fail the run.**

    `IMPLEMENTATION_STANDARDS.md`'s record rule, and the reason it is a `try` rather than trust:
    `record_organize` returns its errors, but the payload is built here, and a run that moved
    33,000 files must not end in a traceback about its own paperwork.

    ⚠ **Written where a stop cannot skip it** - after the loop, on every applied path, which is
    `(agj)`'s lesson: its record call sat inside the branch that a stop took a different route
    around, so the runs that most needed a record were the ones that never wrote one.

    ⚠ **`run_id` is the one migrate already has** (`uuid4` at the top of `run_migration`), which
    `superseded_record_path` uses to name a demoted detail file. Organize passes none, so its
    records file as ``...-organize-.json.gz``; migrate's carry their id. Nothing a reader sees
    changes for organize, and migrate's superseded records become self-identifying.
    """
    try:
        payload = build_run_record(
            RunHeader(
                kind="migrate",
                source=destination.describe(),
                destination=destination.describe(),
                destination_uuid=drive_uuid,
            ),
            files=_refusal_entries(refused),
            intended_total=total,
            attempted=migrated + len(refused),
            stopped=_migration_stop_block(stopped),
        )
        error = record_organize(catalog.path, payload, run_id=run_id)
        if error is not None:
            _log.warning("could not write the migration run record: %s", error)
    except Exception:  # the record must never fail the run it describes
        _log.warning("could not write the migration run record", exc_info=True)


def _record_undo_migration(
    catalog: Catalog,
    destination: Destination,
    drive_uuid: str,
    *,
    undid_run_id: str,
    total: int,
    outcome: UndoOutcome,
) -> None:
    """Write this reversal's record. **Never raises**, for `_record_migration`'s reason. `(ahi)`

    ⚠ **An undo that leaves no line makes the history lie about the disk.** Every other record
    says a run moved files; without this one a reader sees the migration and not its reversal, so
    the newest thing the history describes is a state the disk is no longer in. That is the one
    absence a run history cannot survive, which is why `(ahi)` ranked this above its two siblings.

    **It carries per-file detail, and that is the opposite of `(agm)`'s bake ruling** - the same
    question answered the other way because the durable store differs. Bake writes a line and no
    detail because `file_copies.date_baked_at` is a **permanent** per-copy timestamp, so which
    copies it wrote outlives every later run. A migration's per-file truth is `migration_journal`,
    and `Catalog.start_migration_run` **deletes the previous run's journal for the drive** -
    retention ONE. So a second migration erases the only other account of what this reversal put
    back, and the record is then the sole durable one.

    ``undid_run_id`` is the run this reversed, named for `RunHeader`'s recorded reason: without it
    a record says *"16 files moved back"* and nothing connects it to the run that moved them.
    Entries are failures-only, matching the forward path's `(afd)` ruling on the same data shape -
    the successes are ``reversed_files`` and where each file returned to is the journal row that
    produced it.
    """
    try:
        payload = build_run_record(
            RunHeader(
                kind="migrate undo",
                source=destination.describe(),
                destination=destination.describe(),
                destination_uuid=drive_uuid,
                undid_run_id=undid_run_id,
            ),
            files=_refusal_entries(outcome.refused),
            intended_total=total,
            attempted=outcome.reversed_files + len(outcome.refused),
            stopped=_migration_stop_block(outcome.stopped),
        )
        error = record_organize(catalog.path, payload)
        if error is not None:
            _log.warning("could not write the undo run record: %s", error)
    except Exception:  # the record must never fail the reversal it describes
        _log.warning("could not write the undo run record", exc_info=True)


@dataclass(frozen=True)
class AppliedMoves:
    """What one journalled batch of relocations did. `(aix)` stage 2

    ⚠ **Extracted from `run_migration` rather than written beside it.** A rename needs exactly
    this - journal, health-watched loop, `(agi)`'s stop policy, close the run - and a second copy
    of it would be free to disagree with the first about when a run stops. `run_migration` is now
    a caller of this, not its owner.
    """

    run_id: str
    migrated: int
    refused: tuple[tuple[str, str], ...]
    stopped: MigrationStop | None


def apply_moves(
    catalog: Catalog,
    destination: Destination,
    drive_uuid: str,
    moves: Sequence[Move],
    *,
    progress: ProgressCallback | None = None,
    cancel: threading.Event | None = None,
) -> AppliedMoves:
    """Journal ``moves``, carry them out, and close the run if every one completed.

    🔑 **THE JOURNAL IS WRITTEN BEFORE THE FIRST BYTE MOVES**, which is `(agk)`'s
    intent-before-the-irreversible-step and what makes an interrupted batch resumable:
    `resume_migration` replays whatever rows are still pending, and `_apply_move` advances each
    from whatever state it is in.

    ⚠ **The run is finished only when every move completed.** A batch that skipped one file has
    moves still pending, so the run stays open for the re-run that clears them - `migrated ==
    total` is not the same question as *"did it finish"*.
    """
    run_id = uuid4().hex
    catalog.start_migration_run(run_id, drive_uuid)
    catalog.record_migration_moves(
        [
            (m.sha256, drive_uuid, m.old_relative, m.new_relative, m.copy_sha256, run_id)
            for m in moves
        ]
    )
    migrated = 0
    total = len(moves)
    # `relocate` is a `copy2`, so this rewrites every byte it touches - and on a mounted cloud
    # drive those bytes pass through the client's LOCAL cache. The device half is already covered
    # and more strictly: every relocate goes through `LocalDestination._make_parent`, which fails
    # closed on a changed `st_dev`.
    health = watcher_for(destination.local_root(), catalog.path)
    ahead = _largest_move_ahead(list(moves))
    written = 0
    stop: tuple[MigrationStopKind, str] | None = None
    refused: list[tuple[str, str]] = []
    for index, move in enumerate(moves):
        if cancel is not None and cancel.is_set():
            stop = (MigrationStopKind.CANCELLED, CANCELLED_REASON)
            break
        if health is not None:
            verdict = health.check(largest_remaining=ahead[index], written_bytes=written)
            if not verdict.ok:
                stop = (MigrationStopKind.GROUND_MOVED, verdict.detail)
                break
        try:
            _apply_move(catalog, destination, drive_uuid, move)
        except DestinationError as exc:
            # ⚠ **`(agi)`'s ruled policy, on the fifth surface and reusing its predicate rather
            # than re-deriving an errno table.** One bad file never aborts a batch; a condition
            # that outlives the file must stop the run, because continuing buys N failures
            # describing one condition. Nothing is lost either way: `_apply_move` removes the old
            # path only after the atomic flip, so a refused move leaves the file where it was and
            # its journal row valid for a re-run.
            refused.append((move.new_relative, str(exc)))
            if persists_for_the_run(exc) or isinstance(exc, VerificationFailedError):
                stop = (MigrationStopKind.COULD_NOT_CONTINUE, str(exc))
                break
            continue
        written += move.size or 0
        migrated += 1
        if progress is not None:
            progress(Progress(migrated, total, Phase.MOVING, PurePosixPath(move.new_relative).name))
    # ⚠ **`migrated == total` is not the same question as "did it finish"** once a move can be
    # refused without stopping: a run that skipped one file has moves still pending, so the run
    # must stay open for the re-run that clears them.
    if migrated == total:
        catalog.finish_migration_run(run_id)
    return AppliedMoves(
        run_id=run_id,
        migrated=migrated,
        refused=tuple(refused),
        stopped=None
        if stop is None
        else MigrationStop(
            kind=stop[0], reason=stop[1], never_attempted=total - migrated - len(refused)
        ),
    )


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

    applied = apply_moves(
        catalog, destination, drive_uuid, plan.moves, progress=progress, cancel=cancel
    )
    run_id, migrated = applied.run_id, applied.migrated
    # `MigrationOutcome.refused` is a list by its own declaration; `AppliedMoves` freezes it
    # because it is a value object. Widened here rather than narrowing the dataclass.
    refused = list(applied.refused)
    stopped = applied.stopped
    total = len(plan.moves)
    _record_migration(
        catalog,
        destination,
        drive_uuid,
        run_id=run_id,
        total=total,
        migrated=migrated,
        refused=refused,
        stopped=stopped,
    )
    return MigrationOutcome(
        plan=plan,
        resumed=resumed,
        migrated=migrated,
        applied=True,
        stopped=stopped,
        refused=refused,
    )


@dataclass(frozen=True, slots=True)
class UndoOutcome:
    """What reversing a migration achieved, and what it refused to touch."""

    reversed_files: int
    #: ``(relative, reason)`` for each move left alone -- never silently overwritten.
    refused: list[tuple[str, str]]
    #: Why the reversal ended early, or ``None``. ⚠ **`(agx)`: this used to RAISE**, and
    #: `reversed_files`/`refused` are locals, so a reversal that put 900 files back and then met
    #: one bad file reported **nothing it did** - `(agj)`'s shape on the half `(agm)` had just
    #: corrected beside it. **The same `MigrationStop` the forward path returns**, deliberately,
    #: because one command reporting its two directions in two vocabularies is what `(afe)` binds
    #: against.
    stopped: MigrationStop | None = None

    @property
    def clean(self) -> bool:
        """Nothing refused **and** nothing stopped.

        ⚠ **The stop belongs here or a stopped reversal reads as a finished one** - the CLI exits
        on this and the screen words itself from it, so omitting it would make the fix report
        success for the failure it exists to surface.
        """
        return not self.refused and self.stopped is None


def _reverse_one(
    catalog: Catalog,
    destination: Destination,
    drive_uuid: str,
    row: Any,
    *,
    apply: bool,
) -> str | None:
    """Put one migrated file back. Returns a refusal reason, or ``None`` if it was reversed.

    **Extracted rather than raising the branch ceiling** - `IMPLEMENTATION_STANDARDS.md`'s answer
    to complexity, and the same move `_stopped_run_exit` and `_apply_the_undo` made. It also gives
    the caller one place to wrap: every read and write for a row happens inside this call, so a
    `DestinationError` from *any* of them lands in one handler.

    ⚠ **Ordering is the forward path's, and it is what makes a refusal safe**: the migrated copy
    is removed only after the restored one has been re-hashed, so there is never an instant with
    zero copies - and every catalog write is downstream of that verify, so a failure leaves the
    catalog naming the path the file is still at.
    """
    new_relative = str(row["new_relative"])
    old_relative = str(row["old_relative"])
    expected = row["copy_sha256"]

    if not destination.exists(new_relative):
        return "the migrated copy is no longer there"
    if expected and destination.checksum(new_relative) != expected:
        return "changed since the migration -- left untouched"
    if not apply:
        return None

    destination.relocate(new_relative, old_relative)
    if not _matches(destination, old_relative, expected):
        message = f"verification failed after putting {old_relative} back"
        raise VerificationFailedError(message)
    catalog.relocate_copy(str(row["sha256"]), drive_uuid, old_relative)
    if old_relative != new_relative:
        destination.remove(new_relative)
    catalog.forget_migration_move(str(row["sha256"]), drive_uuid)
    return None


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
    undone_run_id, rows = record
    total = len(rows)

    refused: list[tuple[str, str]] = []
    stop: tuple[MigrationStopKind, str] | None = None
    done = 0
    processed = 0
    for row in rows:
        if cancel is not None and cancel.is_set():
            # The break was already here and said nothing about why - a reversal that stopped at
            # the user's word looked identical to one that finished. `(agx)`
            stop = (MigrationStopKind.CANCELLED, CANCELLED_REASON)
            break
        # Only what the LOOP needs: the refusal key and the progress label. Everything else the
        # row carries is `_reverse_one`'s business now.
        new_relative = str(row["new_relative"])
        item = PurePosixPath(str(row["old_relative"])).name

        # ⚠ **ONE HANDLER OVER THE WHOLE ROW'S I/O, not just the write half.** `(agm)` stopped
        # `_matches` swallowing `DestinationError`, which gave the pre-check below a second way
        # out: `checksum` on a failing drive escaped `undo_migration` entirely, unclassified,
        # taking the report with it. A handler that covered only the relocate would have left
        # that route open while looking complete.
        # ⚠ **ONE HANDLER OVER THE WHOLE ROW'S I/O, not just the write half.** `(agm)` stopped
        # `_matches` swallowing `DestinationError`, which gave the pre-checks a second way out:
        # `checksum` on a failing drive escaped `undo_migration` entirely, unclassified, taking
        # the report with it. A handler covering only the relocate would leave that route open
        # while looking complete.
        try:
            refusal = _reverse_one(catalog, destination, drive_uuid, row, apply=apply)
        except DestinationError as exc:
            # **The forward path's handler, unchanged** - same predicate, same classification,
            # because this is the other direction of one command and `(agi)`'s rule does not care
            # which way the files are moving. Nothing is lost by refusing: `relocate` is a COPY,
            # so the file is still at `new_relative`, and every catalog write in `_reverse_one`
            # is downstream of the verify, so the catalog still names where it really is.
            refused.append((new_relative, str(exc)))
            processed += 1
            if persists_for_the_run(exc) or isinstance(exc, VerificationFailedError):
                stop = (MigrationStopKind.COULD_NOT_CONTINUE, str(exc))
                break
            if progress is not None:
                progress(Progress(processed, total, Phase.RESTORING, item))
            continue
        if refusal is None:
            done += 1
        else:
            refused.append((new_relative, refusal))
        processed += 1
        if progress is not None:
            progress(Progress(processed, total, Phase.RESTORING, item))

    stopped = (
        None
        if stop is None
        else MigrationStop(kind=stop[0], reason=stop[1], never_attempted=total - processed)
    )
    outcome = UndoOutcome(reversed_files=done, refused=refused, stopped=stopped)
    if apply:
        _record_undo_migration(
            catalog,
            destination,
            drive_uuid,
            undid_run_id=undone_run_id,
            total=total,
            outcome=outcome,
        )
    return outcome
