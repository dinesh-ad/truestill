"""Organize: inventory, preview, run, mode/sidebar prefs, filesystem relationship."""

from __future__ import annotations

import threading
import uuid
from collections import Counter
from pathlib import Path
from typing import Literal, NotRequired, TypedDict, cast

from truestill_core.catalog import Catalog
from truestill_core.categorize import build_rules
from truestill_core.date_provenance import format_offset
from truestill_core.dedup import DedupIndex
from truestill_core.destinations import LocalDestination
from truestill_core.drive import create_marker, read_marker
from truestill_core.duplicate_explain import explain_duplicate
from truestill_core.event_review import EventDecision, commit, propose
from truestill_core.exif import read_metadata
from truestill_core.hash_cache import HashCache
from truestill_core.hashing import DEFAULT_PHASH_THRESHOLD, HEIF_AVAILABLE, HEIF_EXTENSIONS
from truestill_core.insights import capture_span, duplicate_bytes
from truestill_core.layout_settings import pin_existing_layout, resolve_scheme
from truestill_core.models import (
    ActionResult,
    ActionStatus,
    Resolution,
    date_quality,
    format_inferred_local_shift_line,
    inferred_local_shifts,
    partition_for_report,
    status_label,
    unreadable_label,
)
from truestill_core.organizer import (
    EXIFTOOL_BACKUP_LABEL,
    Relocation,
    SourceScan,
    discover,
    execute,
    heavy_days_for_organize,
    inventory_source,
    plan,
    preflight_for_run,
    resolve,
    scan_source,
)
from truestill_core.progress import ProgressCallback

from truestill_app.jobs import JobTarget
from truestill_app.service.drive_support import drive_path_hint
from truestill_app.service.drives import LIBRARY_PATH_HINT
from truestill_app.service.leftover_cleanup import (
    LeftoverEmptyFolders,
    cleanup_summary_from_results,
)
from truestill_app.service.media_support import media_breakdown
from truestill_app.service.path_probe import nearest_device, unreadable_message
from truestill_app.service.takeout import InferredLocalShiftPayload

ORGANIZE_MODE_KEY = "ui.organize.mode"
ORGANIZE_MODES = frozenset({"copy", "move", "inplace"})
SIDEBAR_COLLAPSED_KEY = "ui.sidebar.collapsed"


#: How many matches a payload carries. The rest are counted, never dropped silently (F46 /
#: §9): every payload that truncates also states the total, so the API cannot imply a short
#: list is the whole story any more than the screen can. 200 matches the move-preview limit -
#: enough to scan, small enough that a 40,000-file run does not ship a megabyte of JSON.
DUPLICATE_SAMPLE_LIMIT = 200

#: Same idea for unreadable sources. Separate constant rather than a shared one: these are
#: different lists with different failure shapes, and tying them together would mean tuning one
#: could only be done by changing the other.
UNREADABLE_SAMPLE_LIMIT = 200


class DuplicateSample(TypedDict):
    """One match, named. The field the app used to drop is ``matched_path``."""

    name: str
    matched_path: str
    origin: str
    detail: str
    kept: bool
    distance: NotRequired[int]


class DuplicateReport(TypedDict):
    """Named matches plus the count they were taken from, so truncation is never silent."""

    total: int
    shown: list[DuplicateSample]


class UnreadableSample(TypedDict):
    """One source file truestill could not read, and the wording the user sees for why."""

    name: str
    path: str
    #: Already worded for a person by `models.unreadable_label` - never the raw enum value.
    reason: str


class UnreadableReport(TypedDict):
    """Named unreadable files plus the count they were taken from. Same bargain as above."""

    total: int
    shown: list[UnreadableSample]


def _duplicate_report(resolutions: list[Resolution], *, near: bool) -> DuplicateReport:
    """Name what each skipped or flagged file matched, up to the sample limit.

    The values are already computed by this same job - the engine has always known them, and
    the app threw them away at the payload boundary. Nothing here rescans or re-reads.
    """
    matched = [
        (r, r.near_duplicate if near else r.exact_duplicate)
        for r in resolutions
        if (r.near_duplicate if near else r.exact_duplicate) is not None
    ]
    shown: list[DuplicateSample] = []
    for resolution, match in matched[:DUPLICATE_SAMPLE_LIMIT]:
        assert match is not None  # filtered above; narrows for the type checker
        explanation = explain_duplicate(match)
        sample: DuplicateSample = {
            "name": resolution.decision.source.name,
            "matched_path": explanation.matched_path,
            "origin": explanation.origin,
            "detail": explanation.detail,
            "kept": explanation.kept,
        }
        if match.distance is not None:
            sample["distance"] = match.distance
        shown.append(sample)
    return {"total": len(matched), "shown": shown}


class OrganizeDedupCore(TypedDict):
    """Counts from :func:`_summarize` before preview wraps with tier/mode/skipped."""

    files: int
    photos: int
    videos: int
    audio: int
    by_format: dict[str, dict[str, int]]
    new_unique: int
    near_dup: int
    exact_dup: int
    exact_dup_matches: DuplicateReport
    near_dup_matches: DuplicateReport
    undated: int
    sentinel_rejected: int
    future_rejected: int
    suspect_default: int
    inferred_local_shifts: list[InferredLocalShiftPayload]
    folders: dict[str, int]
    heic_perceptual_skipped: NotRequired[int]


def _summarize(resolutions: list[Resolution]) -> OrganizeDedupCore:
    # Disjoint buckets rather than `should_upload`. An unreadable file has no hash, so it
    # matches nothing and used to be counted as new *and* reported as unreadable - the same
    # photo promised and disowned in one payload. `new_unique + near_dup + exact_dup +
    # unreadable_files.total == files` is asserted by `test_preview_tally_is_disjoint`.
    buckets = partition_for_report(resolutions)
    uploads = buckets.organized
    near = buckets.near_duplicates
    labels = Counter(r.decision.category.label for r in uploads)
    heic = sum(1 for r in resolutions if r.decision.source.suffix.lower() in HEIF_EXTENSIONS)
    breakdown = media_breakdown([r.decision.source.name for r in resolutions])
    quality = date_quality(uploads)
    shifts = inferred_local_shifts(uploads)
    summary: OrganizeDedupCore = {
        "files": len(resolutions),
        "photos": breakdown["photos"],
        "videos": breakdown["videos"],
        "audio": breakdown["audio"],
        "by_format": breakdown["by_format"],
        "new_unique": len(buckets.unique),
        "near_dup": len(near),
        "exact_dup": len(buckets.exact_duplicates),
        # Named, not just counted (§9). The CLI has always printed these; the app dropped them.
        "exact_dup_matches": _duplicate_report(resolutions, near=False),
        "near_dup_matches": _duplicate_report(resolutions, near=True),
        "undated": sum(1 for r in uploads if r.decision.captured_at is None),
        # Never silent: an epoch-zero date that was refused, and a date that may be a dead
        # camera-clock default, are each reported on their own -- never folded into "undated".
        "sentinel_rejected": quality.sentinel_rejected,
        "future_rejected": quality.future_rejected,
        "suspect_default": quality.suspect_default,
        # Informational: videos shifted from UTC CreateDate (names + offsets). Not a defect;
        # not_proven_utc fallthrough is omitted on purpose.
        "inferred_local_shifts": [
            {
                "name": s.name,
                "before": s.before.strftime("%H:%M:%S"),
                "after": s.after.strftime("%H:%M:%S"),
                "offset": format_offset(s.offset),
                "evidence": s.evidence,
                "line": format_inferred_local_shift_line(s),
            }
            for s in shifts
        ],
        "folders": dict(labels.most_common()),
    }
    if heic and not HEIF_AVAILABLE:
        # Never silent: HEIC was exact-deduped but not perceptually hashed.
        summary["heic_perceptual_skipped"] = heic
    return summary


def _unreadable_folders(scan: SourceScan) -> list[str]:
    """Folders that could not be listed, as names. **Never a count of what is inside** - that
    number is exactly what could not be read, so supplying one would invent it."""
    return [str(folder) for folder in scan.unreadable_dirs]


def _unreadable_files(resolutions: list[Resolution]) -> UnreadableReport:
    """Source files that could not be read, named with the reason for each.

    The sibling of :func:`_unreadable_folders`, and deliberately a different shape. A folder
    carries no count because the number of files inside it is exactly what could not be read;
    a file carries one because the number is known exactly.

    ``{total, shown}`` rather than a bare list, for the reason `_duplicate_report` uses it: a
    tree of readable directories full of unreadable files can produce thousands, and a
    truncated list that does not say it was truncated reads as a complete one.
    """
    named = [r for r in resolutions if r.hashes.unreadable is not None]
    shown: list[UnreadableSample] = []
    for resolution in named[:UNREADABLE_SAMPLE_LIMIT]:
        reason = resolution.hashes.unreadable
        assert reason is not None  # filtered above; narrows for the type checker
        shown.append(
            {
                "name": resolution.decision.source.name,
                "path": str(resolution.decision.source),
                # Worded here, through the one function §9 allows, so the app and the CLI
                # cannot describe the same failure differently.
                "reason": unreadable_label(reason),
            }
        )
    return {"total": len(named), "shown": shown}


def _skipped_summary(scan: SourceScan) -> dict[str, dict[str, int]]:
    """Skipped files for the UI: extension counts, plus a plain exiftool-backup label."""
    backups = {EXIFTOOL_BACKUP_LABEL: len(scan.exiftool_backups)} if scan.exiftool_backups else {}
    return {
        "documents": dict(Counter(p.suffix.lower() or "(no ext)" for p in scan.documents)),
        "unrecognized": dict(Counter(p.suffix.lower() or "(no ext)" for p in scan.unrecognized)),
        "exiftool_backups": backups,
    }


class OrganizeInventory(TypedDict):
    """Cheap walk+size tier before a full dedup preview (backlog tt)."""

    tier: Literal["inventory"]
    files: int
    photos: int
    videos: int
    audio: int
    by_format: dict[str, dict[str, int]]
    total_bytes: int
    skipped: dict[str, dict[str, int]]


def organize_inventory(source: Path) -> OrganizeInventory:
    """Walk + size only - the (tt) progressive-disclosure tier before a full dedup preview.

    Returns immediately after ``inventory_source``: no exiftool, no hashing. Complexity O(n).
    """
    inv = inventory_source(source)
    return {
        "tier": "inventory",
        "files": inv.files,
        "photos": inv.photos,
        "videos": inv.videos,
        "audio": inv.audio,
        "by_format": inv.by_format,
        "total_bytes": inv.total_bytes,
        "skipped": inv.skipped,
    }


def _normalize_organize_mode(mode: object) -> str:
    """Return a supported organize mode, defaulting to copy on missing/invalid values."""
    text = str(mode or "copy").strip().lower()
    return text if text in ORGANIZE_MODES else "copy"


class OrganizeModeState(TypedDict):
    mode: str
    modes: list[str]


class SetOrganizeModeResult(TypedDict):
    ok: Literal[True]
    mode: str


class SidebarState(TypedDict):
    collapsed: bool


class SetSidebarCollapsedResult(TypedDict):
    ok: Literal[True]
    collapsed: bool


def organize_mode_state(db: Path) -> OrganizeModeState:
    with Catalog(db) as catalog:
        saved = _normalize_organize_mode(catalog.get_setting(ORGANIZE_MODE_KEY))
    return {"mode": saved, "modes": sorted(ORGANIZE_MODES)}


def set_organize_mode(mode: object, db: Path) -> SetOrganizeModeResult:
    saved = _normalize_organize_mode(mode)
    with Catalog(db) as catalog:
        catalog.set_setting(ORGANIZE_MODE_KEY, saved)
    return {"ok": True, "mode": saved}


def _normalize_sidebar_collapsed(value: object) -> bool:
    """True only for an explicit collapsed signal; anything else expands."""
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().lower()
    return text in {"1", "true", "yes", "collapsed"}


def sidebar_state(db: Path) -> SidebarState:
    with Catalog(db) as catalog:
        raw = catalog.get_setting(SIDEBAR_COLLAPSED_KEY)
    return {"collapsed": _normalize_sidebar_collapsed(raw)}


def set_sidebar_collapsed(collapsed: object, db: Path) -> SetSidebarCollapsedResult:
    saved = _normalize_sidebar_collapsed(collapsed)
    with Catalog(db) as catalog:
        catalog.set_setting(SIDEBAR_COLLAPSED_KEY, "true" if saved else "false")
    return {"ok": True, "collapsed": saved}


class FilesystemRelationshipOk(TypedDict):
    ok: Literal[True]
    same_filesystem: bool


class FilesystemRelationshipErr(TypedDict):
    ok: Literal[False]
    error: str


def filesystem_relationship(
    source: Path, destination: Path
) -> FilesystemRelationshipOk | FilesystemRelationshipErr:
    """Whether source and destination roots are on the same filesystem.

    A destination that does not exist yet is answered from the parent it would be created in -
    that is the common first-run case, not a failure. The one unanswerable case is a folder the
    OS refuses to describe, and it is reported as that rather than walked past.
    """
    src, dst = nearest_device(source), nearest_device(destination)
    for probe in (src, dst):
        if probe.blocked_at is not None:
            return {"ok": False, "error": unreadable_message(probe.blocked_at)}
    return {"ok": True, "same_filesystem": src.device_id == dst.device_id}


def _effective_destination_for_mode(source: Path, destination: Path, mode: str) -> Path:
    return source if mode == "inplace" else destination


def _device_id(path: Path) -> int | None:
    """The device ``path`` sits on, or ``None`` when a folder refused to be described."""
    return nearest_device(path).device_id


class ModeMechanism(TypedDict):
    """How an organize mode will copy or rename on this source/destination pair."""

    same_filesystem: bool
    reversible: bool
    uses_rename: bool
    requires_destination: bool


def _mode_mechanism(source: Path, destination: Path, mode: str) -> ModeMechanism:
    """Mechanism briefing used by preview/run messaging and confirm gating."""
    same_filesystem = False
    src_dev = _device_id(source)
    dst_dev = _device_id(destination)
    if src_dev is not None and dst_dev is not None:
        same_filesystem = src_dev == dst_dev
    if mode == "copy":
        return {
            "same_filesystem": same_filesystem,
            "reversible": False,
            "uses_rename": False,
            "requires_destination": True,
        }
    if mode == "move":
        return {
            "same_filesystem": same_filesystem,
            "reversible": same_filesystem,
            "uses_rename": same_filesystem,
            "requires_destination": True,
        }
    return {
        "same_filesystem": same_filesystem,
        "reversible": same_filesystem,
        "uses_rename": True,
        "requires_destination": False,
    }


class OrganizePreviewEmpty(TypedDict):
    """No media in source: short dedup-tier reply (no photo/video tallies)."""

    tier: Literal["dedup"]
    files: int
    folders: dict[str, int]
    skipped: dict[str, dict[str, int]]
    #: Named folders that could not be listed. Present here too: "no media found" is exactly
    #: the answer a user must not receive when the reason is that a folder could not be opened.
    unreadable_folders: list[str]
    #: **No `unreadable_files` here, on purpose.** An unreadable *file* was still found by the
    #: walk and classified by its extension, so it is in `scan.media` and this branch - reached
    #: only when `scan.media` is empty - cannot have one. Its sibling above is present precisely
    #: because the opposite is true of a folder: an unlistable one is *why* nothing was found.
    mode: str
    mechanism: ModeMechanism


class DestinationLimit(TypedDict):
    """What the destination cannot hold, stated before the button that would start the run.

    Present only when the run would fail: a plan that reads as clean and then fails on Organize
    moves the discovery to after the user has committed, which on the app is the worse moment
    because the confirm control is right there.
    """

    #: The sentence a user reads. Names the offending files rather than counting them.
    detail: str
    #: The filesystem as the OS reports it (``vfat``), or ``None`` where it cannot be told.
    filesystem: str | None
    #: How many files are too large. Zero when the problem is free space rather than a limit.
    oversized: int


class OrganizePreviewSummary(OrganizeDedupCore):
    """Full dedup preview after :func:`_summarize`, plus mode/skipped wrappers."""

    tier: Literal["dedup"]
    destination_is_drive: bool
    skipped: dict[str, dict[str, int]]
    #: Folders that could not be listed, **named, without a file count** - the number inside is
    #: exactly what could not be read. Distinct from `skipped`, which counts files truestill
    #: decided about.
    unreadable_folders: list[str]
    #: Source files that could not be read, named with a reason each. Its sibling above carries
    #: no count on purpose; this one does, because for a file the number is known exactly.
    unreadable_files: UnreadableReport
    mode: str
    mechanism: ModeMechanism
    elapsed_seconds: NotRequired[float]
    #: Absent whenever the destination can hold the run, so an ordinary preview is unchanged.
    destination_limit: NotRequired[DestinationLimit]


def _destination_limit(resolutions: list[Resolution], destination: Path) -> DestinationLimit | None:
    """The destination's own refusal, or ``None`` when it can hold the run.

    Reads the same answer `execute` refuses on, through the same function - a preview that
    disagreed with the run it precedes would be worse than no preview at all.
    """
    preflight = preflight_for_run(resolutions, LocalDestination(destination))
    if preflight.may_proceed:
        return None
    return {
        "detail": preflight.detail(),
        "filesystem": preflight.facts.filesystem,
        "oversized": len(preflight.oversized),
    }


def organize_preview(
    source: Path,
    destination: Path,
    db: Path,
    *,
    progress: ProgressCallback | None = None,
    cancel: threading.Event | None = None,
    refresh_metadata: bool = False,
    mode: str = "copy",
) -> OrganizePreviewEmpty | OrganizePreviewSummary:
    """Plan + dedup with no writes -- the dry-run summary the UI shows before a real run.

    Reports progress through the same phases the real run does, because it does the same
    work: reading metadata, then hashing. On a large library this is the **first** long wait
    a user ever experiences with truestill, which makes it the worst possible place to look
    like nothing is happening.

    ``refresh_metadata`` forces a fresh exiftool pass (bypasses the sidecar metadata cache)
    for tools that edit tags without bumping mtime.
    """
    mode = _normalize_organize_mode(mode)
    destination = _effective_destination_for_mode(source, destination, mode)
    mechanism = _mode_mechanism(source, destination, mode)
    scan = scan_source(source)
    files = scan.media
    if not files:
        return {
            "tier": "dedup",
            "files": 0,
            "folders": {},
            "skipped": _skipped_summary(scan),
            "unreadable_folders": _unreadable_folders(scan),
            "mode": mode,
            "mechanism": mechanism,
        }
    with Catalog(db) as catalog, HashCache.beside(db) as cache:
        metadata = read_metadata(
            files, progress=progress, cancel=cancel, cache=cache, force=refresh_metadata
        )
        scheme = resolve_scheme(catalog)
        rules = build_rules()
        heavy = heavy_days_for_organize(catalog, files, metadata, rules)
        decisions = plan(files, metadata, rules, scheme=scheme, heavy_days=heavy)
        index = DedupIndex.from_catalog_rows(catalog.seed_rows(), DEFAULT_PHASH_THRESHOLD)
        resolutions = resolve(
            decisions,
            index,
            catalog_sizes=catalog.known_sizes(),
            progress=progress,
            cancel=cancel,
            cache=cache,
        )
    core = _summarize(resolutions)
    # TypedDict ** spread cannot prove NotRequired keys; build then cast (mypy strict).
    summary = cast(
        OrganizePreviewSummary,
        {
            **core,
            "tier": "dedup",
            "destination_is_drive": read_marker(destination) is not None,
            "skipped": _skipped_summary(scan),
            "unreadable_folders": _unreadable_folders(scan),
            "unreadable_files": _unreadable_files(resolutions),
            "mode": mode,
            "mechanism": mechanism,
        },
    )
    limit = _destination_limit(resolutions, destination)
    if limit is not None:
        summary["destination_limit"] = limit
    return summary


def organize_preview_run(
    source: Path,
    destination: Path,
    db: Path,
    *,
    refresh_metadata: bool = False,
    mode: str = "copy",
) -> JobTarget:
    """The preview as a cancellable background job, so it can report progress like the rest.

    Still a dry run in every respect: this writes nothing to the destination or the catalog.
    Only *how* the answer is delivered changed.
    """

    def target(
        progress: ProgressCallback, cancel: threading.Event
    ) -> OrganizePreviewEmpty | OrganizePreviewSummary:
        return organize_preview(
            source,
            destination,
            db,
            progress=progress,
            cancel=cancel,
            refresh_metadata=refresh_metadata,
            mode=mode,
        )

    return target


def organize_run(
    source: Path,
    destination: Path,
    db: Path,
    *,
    skip_undated: bool = False,
    refresh_metadata: bool = False,
    mode: str = "copy",
) -> JobTarget:
    """Build a job target that runs the real organize (progress across hashing then copying)."""

    def target(
        progress: ProgressCallback, cancel: threading.Event
    ) -> CompletionBase | OrganizeDoneSummary:
        chosen_mode = _normalize_organize_mode(mode)
        effective_destination = _effective_destination_for_mode(source, destination, chosen_mode)
        mechanism = _mode_mechanism(source, effective_destination, chosen_mode)
        files = discover(source)
        if not files:
            # Empty source: CompletionBase only -- no mode/mechanism/drive_label/single_copy.
            # OrganizeDoneSummary is the with-files path below.
            return _completion([], effective_destination)
        with Catalog(db) as catalog, HashCache.beside(db) as cache:
            metadata = read_metadata(files, progress=progress, cache=cache, force=refresh_metadata)
            pin_existing_layout(catalog)
            scheme = resolve_scheme(catalog)
            rules = build_rules()
            heavy = heavy_days_for_organize(catalog, files, metadata, rules)
            decisions = plan(files, metadata, rules, scheme=scheme, heavy_days=heavy)
            index = DedupIndex.from_catalog_rows(catalog.seed_rows(), DEFAULT_PHASH_THRESHOLD)
            resolutions = resolve(
                decisions,
                index,
                catalog_sizes=catalog.known_sizes(),
                progress=progress,
                cancel=cancel,
                cache=cache,
            )
            # Apply any *already-named* trips whose cluster recurs in this source, so a fresh
            # import lands its camera files under the same event folder (matched by signature).
            # Only saved events are applied -- unnamed clusters are left untouched (never
            # auto-skipped), so they stay reviewable in the Trips screen later.
            saved = [
                EventDecision(c, None)
                for c in propose(resolutions, metadata)
                if catalog.event_by_signature(c.signature) is not None
            ]
            if saved:
                resolutions = commit(resolutions, saved, catalog, scheme=scheme).resolutions
            # Register the destination *before* writing anything, so every copy is recorded
            # against it. Doing this afterwards would leave the run's own files unattached --
            # which is exactly the bug this replaced.
            marker = read_marker(effective_destination) or create_marker(
                effective_destination, label=effective_destination.name or "Library"
            )
            catalog.upsert_drive(uuid=marker.uuid, label=marker.label)
            # Remember where it was seen, so its card can offer to check it.
            catalog.set_setting(drive_path_hint(marker.uuid), str(effective_destination))
            drive_uuid = marker.uuid
            relocation = None
            if chosen_mode in {"move", "inplace"} and mechanism["uses_rename"]:
                relocation = Relocation(
                    run_id=uuid.uuid4().hex,
                    source_root=source,
                    dest_root=effective_destination,
                    require_rename=chosen_mode == "inplace",
                )
                catalog.start_inplace_run(
                    run_id=relocation.run_id,
                    source_root=str(relocation.source_root),
                    dest_root=str(relocation.dest_root),
                    drive_uuid=drive_uuid,
                )
            results = execute(
                resolutions,
                LocalDestination(effective_destination),
                catalog,
                apply=True,
                skip_undated=skip_undated,
                move=chosen_mode in {"move", "inplace"},
                relocation=relocation,
                progress=progress,
                cancel=cancel,
                drive_uuid=drive_uuid,
            )
            if relocation is not None:
                moved = sum(1 for r in results if r.status is ActionStatus.MOVED_IN_PLACE)
                if moved:
                    catalog.finish_inplace_run(relocation.run_id)
                else:
                    catalog.discard_inplace_run(relocation.run_id)
        base = _completion(results, effective_destination)
        leftover: LeftoverEmptyFolders | None = None
        if chosen_mode in {"move", "inplace"}:
            leftover = cleanup_summary_from_results(results, source)
        with Catalog(db) as catalog:
            catalog.set_setting(LIBRARY_PATH_HINT, str(effective_destination))
            # The custody nudge, counted rather than assumed: how much of the library really
            # does exist in only one place right now.
            single_copy = catalog.single_copy_count()
        # TypedDict ** spread cannot prove NotRequired keys; build then cast (mypy strict).
        done = cast(
            OrganizeDoneSummary,
            {
                **base,
                "mode": chosen_mode,
                "mechanism": mechanism,
                "drive_label": marker.label,
                "single_copy": single_copy,
            },
        )
        if leftover is not None:
            done["leftover_empty_folders"] = leftover
        return done

    return target


class CompletionBase(TypedDict):
    """The 17 keys :func:`_completion` itself returns (organize-only)."""

    outcomes: dict[str, int]
    organized: int
    photos: int
    videos: int
    audio: int
    bytes_organized: int
    duplicates: int
    bytes_saved: int
    duplicate_matches: DuplicateReport
    near_dup: int
    bytes_near_dup: int
    near_dup_matches: DuplicateReport
    folders: dict[str, int]
    oldest: str | None
    newest: str | None
    moved_in_place: int
    moved_by_copy: int
    failed: int


class OrganizeDoneSummary(CompletionBase):
    """Organize job summary after :func:`organize_run` enriches :class:`CompletionBase`.

    ``leftover_empty_folders`` appears only for move/inplace runs that left empty folders.
    ``elapsed_seconds`` is injected by ``jobs.py`` on every dict done-event (documented
    boundary -- JobTarget is heterogeneous, so jobs cannot type-guarantee the key on every
    summary TypedDict).

    ``cancelled`` is added by the UI only (``{ ...summary, cancelled: true }``) and must
    never appear in this server-side type.
    """

    mode: str
    mechanism: ModeMechanism
    drive_label: str
    single_copy: int
    leftover_empty_folders: NotRequired[LeftoverEmptyFolders]
    elapsed_seconds: NotRequired[float]


def _completion(results: list[ActionResult], destination: Path) -> CompletionBase:
    """The story of a finished organize, built only from what the run actually did.

    Every number here is counted from the results -- nothing is estimated, rounded up for
    effect, or inferred. The custody strip's honesty rule applies to the payoff moment too:
    a run that organized little should say so plainly rather than find a flattering framing.
    """
    organized = [r for r in results if r.status in _ORGANIZED_STATUSES]
    duplicates = [r for r in results if r.status is ActionStatus.DUPLICATE]
    near = [r for r in organized if r.resolution.near_duplicate is not None]
    # Bytes and the date range come from `truestill_core.insights` so a *preview* can state
    # them too -- they used to be computed here and were therefore unreachable from anywhere
    # but a finished run. Selection stays here, where the run's statuses live: the span is over
    # what the run ORGANIZED, so a skipped duplicate's date must not widen it.
    sizes = {r.resolution.decision.source: _result_size(r, destination) for r in results}
    counted = duplicate_bytes([r.resolution for r in results], sizes)
    span = capture_span([r.resolution for r in organized])
    labels = Counter(r.resolution.decision.category.label for r in organized)
    names = [r.resolution.decision.source.name for r in organized]
    breakdown = media_breakdown(names)
    return {
        "outcomes": dict(Counter(status_label(r.status) for r in results)),
        "organized": len(organized),
        "photos": breakdown["photos"],
        "videos": breakdown["videos"],
        "audio": breakdown["audio"],
        "bytes_organized": sum(_result_size(r, destination) for r in organized),
        "duplicates": len(duplicates),
        "bytes_saved": counted.reclaimable_bytes,
        # What each skipped file matched. The count alone was the §9 gap: "identical to a kept
        # file" without saying which kept file is the complaint the CLI never had.
        "duplicate_matches": _duplicate_report([r.resolution for r in duplicates], near=False),
        "near_dup": len(near),
        "bytes_near_dup": counted.near_bytes,
        "near_dup_matches": _duplicate_report([r.resolution for r in near], near=True),
        "folders": dict(labels.most_common()),
        # None rather than a placeholder year: an undated batch has no range, and inventing
        # one would be exactly the "computed for effect" the honesty rule forbids.
        "oldest": span.oldest.isoformat() if span else None,
        "newest": span.newest.isoformat() if span else None,
        "moved_in_place": sum(1 for r in results if r.status is ActionStatus.MOVED_IN_PLACE),
        "moved_by_copy": sum(1 for r in results if r.status is ActionStatus.MOVED),
        "failed": sum(1 for r in results if r.status is ActionStatus.FAILED),
    }


#: Outcomes that put a file into the library. `RENAMED` is one of them -- it was organized,
#: just under a suffixed name to avoid an unrelated clash.
_ORGANIZED_STATUSES = frozenset(
    {
        ActionStatus.UPLOADED,
        ActionStatus.RENAMED,
        ActionStatus.MOVED,
        ActionStatus.MOVED_IN_PLACE,
    }
)


def _result_size(result: ActionResult, destination: Path) -> int:
    """Size of what this outcome produced, measured where the file actually ended up.

    The destination is checked first: after a move or an in-place rename the source path no
    longer exists, so sizing by source would silently report 0 bytes organized for exactly
    the runs that moved the most data.
    """
    for candidate in (
        destination / result.final_relative if result.final_relative else None,
        result.resolution.decision.source,
    ):
        if candidate is None:
            continue
        try:
            size: int = candidate.stat().st_size
        except OSError:
            continue
        return size
    return 0
