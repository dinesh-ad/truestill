"""Bridge from the web layer to truestill-core. Imports only truestill-core -- never truestill-cli.

Read helpers return plain dicts for JSON; long operations return :data:`JobTarget`s that the
job manager runs on a thread with progress + cancellation. Preview writes nothing (the CLI's
dry-run posture, preserved in the UI).
"""

from __future__ import annotations

import threading
import uuid
from collections import Counter
from collections.abc import Sequence
from datetime import date
from pathlib import Path, PurePosixPath
from typing import Any, Literal, NotRequired, TypedDict, cast

from truestill_core.catalog import Catalog
from truestill_core.categorize import build_rules
from truestill_core.date_provenance import format_offset
from truestill_core.dedup import DedupIndex
from truestill_core.destinations import LocalDestination
from truestill_core.drive import create_marker, read_marker
from truestill_core.event_review import EventDecision, commit, commit_catalog, propose
from truestill_core.events import (
    EventCandidate,
    EventSettings,
    split_candidate,
)
from truestill_core.exif import read_metadata
from truestill_core.hash_cache import HashCache
from truestill_core.hashing import (
    DEFAULT_PHASH_THRESHOLD,
    HEIF_AVAILABLE,
    HEIF_EXTENSIONS,
)
from truestill_core.layout import Placement
from truestill_core.layout_settings import (
    pin_existing_layout,
    resolve_scheme,
)
from truestill_core.migrate import (
    ROUTE_SIDE_BIN,
    label_routes,
    rederive_rules,
    run_migration,
    undo_migration,
)
from truestill_core.models import (
    ActionResult,
    ActionStatus,
    Resolution,
    date_quality,
    format_inferred_local_shift_line,
    inferred_local_shifts,
    status_label,
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
    resolve,
    scan_source,
)
from truestill_core.progress import ProgressCallback
from truestill_core.trip_review import (
    ReviewCard,
    TripDecision,
    TripMergeError,
    assemble_trip_review,
    collapsed_event_cards,
    commit_trips,
    decline_message,
    is_small_event,
    merge_review_cards,
    order_review_cards,
    split_trip,
)

from truestill_app.jobs import JobTarget
from truestill_app.service import backup as _backup
from truestill_app.service import clean_empty as _clean_empty
from truestill_app.service import drive_support as _drive_support
from truestill_app.service import drives as _drives
from truestill_app.service import fs_browse as _fs_browse
from truestill_app.service import leftover_cleanup as _leftover_cleanup
from truestill_app.service import media_support as _media_support
from truestill_app.service import organize_undo as _organize_undo
from truestill_app.service import settings as _settings
from truestill_app.service import stats as _stats
from truestill_app.service import takeout as _takeout
from truestill_app.service import verify as _verify

# Browse (folder picker) lives in its own module; bound here so
# ``from truestill_app.service import fs_dirs`` and ``service.fs_dirs`` stay unchanged.
FsRoot = _fs_browse.FsRoot
FsEntry = _fs_browse.FsEntry
FsDirsOk = _fs_browse.FsDirsOk
FsDirsErr = _fs_browse.FsDirsErr
FsValidateResolved = _fs_browse.FsValidateResolved
FsValidateUnresolved = _fs_browse.FsValidateUnresolved
FsCreateFailed = _fs_browse.FsCreateFailed
FsCreateOk = _fs_browse.FsCreateOk
fs_roots = _fs_browse.fs_roots
fs_dirs = _fs_browse.fs_dirs
fs_create = _fs_browse.fs_create
fs_validate = _fs_browse.fs_validate

# Clean-empty preview/apply; leftover detection helpers stay on this facade.
CleanEmptyOccupied = _clean_empty.CleanEmptyOccupied
CleanEmptyPreview = _clean_empty.CleanEmptyPreview
CleanEmptyApply = _clean_empty.CleanEmptyApply
clean_empty_preview = _clean_empty.clean_empty_preview
clean_empty_apply = _clean_empty.clean_empty_apply

OrganizeUndoSkipped = _organize_undo.OrganizeUndoSkipped
OrganizeUndoStateDisarmed = _organize_undo.OrganizeUndoStateDisarmed
OrganizeUndoStateArmed = _organize_undo.OrganizeUndoStateArmed
OrganizeUndoJobSummary = _organize_undo.OrganizeUndoJobSummary
organize_undo_state = _organize_undo.organize_undo_state
organize_undo = _organize_undo.organize_undo

EventSettingsPayload = _settings.EventSettingsPayload
InvalidEventSettingsPayload = _settings.InvalidEventSettingsPayload
event_settings = _settings.event_settings
event_settings_payload = _settings.event_settings_payload
invalid_event_settings_payload = _settings.invalid_event_settings_payload
set_event_settings = _settings.set_event_settings
EverydayDaySettingsPayload = _settings.EverydayDaySettingsPayload
InvalidEverydayDaySettingsPayload = _settings.InvalidEverydayDaySettingsPayload
everyday_day_settings = _settings.everyday_day_settings
everyday_day_settings_payload = _settings.everyday_day_settings_payload
invalid_everyday_day_settings_payload = _settings.invalid_everyday_day_settings_payload
set_everyday_day_settings = _settings.set_everyday_day_settings
LayoutPreviewRow = _settings.LayoutPreviewRow
LayoutState = _settings.LayoutState
PreviewLayoutOk = _settings.PreviewLayoutOk
PreviewLayoutErr = _settings.PreviewLayoutErr
SetLayoutOk = _settings.SetLayoutOk
SetLayoutErr = _settings.SetLayoutErr
layout_state = _settings.layout_state
preview_layout = _settings.preview_layout
set_layout = _settings.set_layout

# Takeout rescue; InferredLocalShiftPayload also used by Organize summaries.
InferredLocalShiftPayload = _takeout.InferredLocalShiftPayload
IngestPreviewEmpty = _takeout.IngestPreviewEmpty
IngestPreviewSummary = _takeout.IngestPreviewSummary
ingest_preview = _takeout.ingest_preview
ingest_preview_run = _takeout.ingest_preview_run

# Shared drive/media support - public names for callers; underscored aliases for this facade.
NotABackupDriveError = _drive_support.NotABackupDriveError
DriveCorrectionPayload = _drive_support.DriveCorrectionPayload
DriveUnavailablePayload = _drive_support.DriveUnavailablePayload
drive_ref_for = _drive_support.drive_ref_for
_not_a_drive_message = _drive_support.not_a_drive_message
_drive_correction = _drive_support.drive_correction
_drive_unavailable = _drive_support.drive_unavailable
_not_a_drive = _drive_support.not_a_drive
_drive_path_hint = _drive_support.drive_path_hint
_take_live_path_hint = _drive_support.take_live_path_hint
MediaBreakdown = _media_support.MediaBreakdown
_media_breakdown = _media_support.media_breakdown

LibraryStatsDrive = _stats.LibraryStatsDrive
LibraryStatsSafety = _stats.LibraryStatsSafety
LibraryStatsUndatedSample = _stats.LibraryStatsUndatedSample
LibraryStatsCompleteness = _stats.LibraryStatsCompleteness
LibraryStatsYear = _stats.LibraryStatsYear
LibraryStatsShape = _stats.LibraryStatsShape
LibraryStats = _stats.LibraryStats
library_stats = _stats.library_stats

VerifyProblem = _verify.VerifyProblem
VerifyJobSummary = _verify.VerifyJobSummary
verify_run = _verify.verify_run


LIBRARY_PATH_HINT = _drives.LIBRARY_PATH_HINT
BACKUP_PATH_HINT = _drives.BACKUP_PATH_HINT
RevealOk = _drives.RevealOk
RevealErr = _drives.RevealErr
reveal_in_file_manager = _drives.reveal_in_file_manager
DriveAttachment = _drives.DriveAttachment
attach_drive = _drives.attach_drive
DriveRow = _drives.DriveRow
WhereCopy = _drives.WhereCopy
WhereResult = _drives.WhereResult
AtRiskRow = _drives.AtRiskRow
list_drives = _drives.list_drives
where = _drives.where
at_risk = _drives.at_risk
LibraryStatus = _drives.LibraryStatus
library_status = _drives.library_status

MissingCopy = _backup.MissingCopy
BackupPreviewErr = _backup.BackupPreviewErr
BackupPreviewOk = _backup.BackupPreviewOk
BackupRunSummary = _backup.BackupRunSummary
backup_preview = _backup.backup_preview
backup_run = _backup.backup_run
_files_missing_on_target = _backup._files_missing_on_target

LeftoverEmptyFolders = _leftover_cleanup.LeftoverEmptyFolders
_cleanup_summary_from_results = _leftover_cleanup.cleanup_summary_from_results
_cleanup_summary_from_old_paths = _leftover_cleanup.cleanup_summary_from_old_paths

#: Remembered paths, for prefilling fields the catalog can already answer. **Hints only.**
#: Drive *identity* is the marker's uuid and never a path (§3.1) -- mount points move between
#: sessions and machines. These exist so a user is never asked to Browse for something we
#: already know, and nothing behind them may ever be trusted as identity.
ORGANIZE_MODE_KEY = "ui.organize.mode"
ORGANIZE_MODES = frozenset({"copy", "move", "inplace"})
SIDEBAR_COLLAPSED_KEY = "ui.sidebar.collapsed"


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
    undated: int
    sentinel_rejected: int
    suspect_default: int
    inferred_local_shifts: list[InferredLocalShiftPayload]
    folders: dict[str, int]
    heic_perceptual_skipped: NotRequired[int]


def _summarize(resolutions: list[Resolution]) -> OrganizeDedupCore:
    uploads = [r for r in resolutions if r.should_upload]
    near = [r for r in uploads if r.near_duplicate is not None]
    labels = Counter(r.decision.category.label for r in uploads)
    heic = sum(1 for r in resolutions if r.decision.source.suffix.lower() in HEIF_EXTENSIONS)
    breakdown = _media_breakdown([r.decision.source.name for r in resolutions])
    quality = date_quality(uploads)
    shifts = inferred_local_shifts(uploads)
    summary: OrganizeDedupCore = {
        "files": len(resolutions),
        "photos": breakdown["photos"],
        "videos": breakdown["videos"],
        "audio": breakdown["audio"],
        "by_format": breakdown["by_format"],
        "new_unique": len(uploads) - len(near),
        "near_dup": len(near),
        "exact_dup": len(resolutions) - len(uploads),
        "undated": sum(1 for r in uploads if r.decision.captured_at is None),
        # Never silent: an epoch-zero date that was refused, and a date that may be a dead
        # camera-clock default, are each reported on their own -- never folded into "undated".
        "sentinel_rejected": quality.sentinel_rejected,
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
    """Whether source and destination roots are on the same filesystem."""
    if _device_id(source) is None:
        return {
            "ok": False,
            "error": "The source folder was not found. Check the path, then pick an existing folder.",
        }
    if _device_id(destination) is None:
        return {
            "ok": False,
            "error": "The organized folder was not found. Check the path, then pick or create a folder.",
        }
    same_filesystem = _device_id(source) == _device_id(destination)
    return {"ok": True, "same_filesystem": same_filesystem}


def _effective_destination_for_mode(source: Path, destination: Path, mode: str) -> Path:
    return source if mode == "inplace" else destination


def _device_id(path: Path) -> int | None:
    probe = path
    while True:
        if probe.exists():
            try:
                return probe.stat().st_dev
            except OSError:
                return None
        if probe.parent == probe:
            return None
        probe = probe.parent


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
    mode: str
    mechanism: ModeMechanism


class OrganizePreviewSummary(OrganizeDedupCore):
    """Full dedup preview after :func:`_summarize`, plus mode/skipped wrappers."""

    tier: Literal["dedup"]
    destination_is_drive: bool
    skipped: dict[str, dict[str, int]]
    mode: str
    mechanism: ModeMechanism
    elapsed_seconds: NotRequired[float]


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
    return cast(
        OrganizePreviewSummary,
        {
            **core,
            "tier": "dedup",
            "destination_is_drive": read_marker(destination) is not None,
            "skipped": _skipped_summary(scan),
            "mode": mode,
            "mechanism": mechanism,
        },
    )


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
            catalog.set_setting(_drive_path_hint(marker.uuid), str(effective_destination))
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
            leftover = _cleanup_summary_from_results(results, source)
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
    near_dup: int
    bytes_near_dup: int
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
    dates = [
        r.resolution.decision.captured_at
        for r in organized
        if r.resolution.decision.captured_at is not None
    ]
    labels = Counter(r.resolution.decision.category.label for r in organized)
    names = [r.resolution.decision.source.name for r in organized]
    breakdown = _media_breakdown(names)
    return {
        "outcomes": dict(Counter(status_label(r.status) for r in results)),
        "organized": len(organized),
        "photos": breakdown["photos"],
        "videos": breakdown["videos"],
        "audio": breakdown["audio"],
        "bytes_organized": sum(_result_size(r, destination) for r in organized),
        "duplicates": len(duplicates),
        "bytes_saved": sum(_result_size(r, destination) for r in duplicates),
        "near_dup": len(near),
        "bytes_near_dup": sum(_result_size(r, destination) for r in near),
        "folders": dict(labels.most_common()),
        # None rather than a placeholder year: an undated batch has no range, and inventing
        # one would be exactly the "computed for effect" the honesty rule forbids.
        "oldest": min(dates).isoformat() if dates else None,
        "newest": max(dates).isoformat() if dates else None,
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


# --- event review (used by the Event review screen; merge/split are UI-only) ----------


def plan_resolve(source: Path, db: Path) -> tuple[list[Resolution], dict[Path, dict[str, Any]]]:
    """Plan + dedup a source (no writes), returning resolutions and metadata for clustering."""
    files = discover(source)
    if not files:
        return [], {}
    metadata = read_metadata(files)
    with Catalog(db) as catalog:
        scheme = resolve_scheme(catalog)
        rules = build_rules()
        heavy = heavy_days_for_organize(catalog, files, metadata, rules)
        decisions = plan(files, metadata, rules, scheme=scheme, heavy_days=heavy)
        index = DedupIndex.from_catalog_rows(catalog.seed_rows(), DEFAULT_PHASH_THRESHOLD)
        resolutions = resolve(decisions, index, catalog_sizes=catalog.known_sizes())
    return resolutions, metadata


class ReviewDayPayload(TypedDict):
    date: str
    count: int


class ReviewCardPayload(TypedDict):
    kind: Literal["trip", "event"]
    start: str
    end: str
    count: int
    active_days: int
    days: list[ReviewDayPayload]
    location: list[float] | None
    collapsed: bool


class CollapsedEventSummaryPayload(TypedDict):
    count: int
    min_photos: int
    max_photos: int
    start: str
    end: str


class ReviewCardsPayload(TypedDict):
    session: str
    cards: list[ReviewCardPayload]
    collapsed: CollapsedEventSummaryPayload | None


class ProposedReviewCardsPayload(ReviewCardsPayload):
    ok: Literal[True]
    label: str
    declines: list[str]


def _event_location(cluster: EventCandidate) -> list[float] | None:
    centroid = cluster.gps_centroid()
    return list(centroid) if centroid else None


def review_card_json(card: ReviewCard, min_files: int) -> ReviewCardPayload:
    """Serialise one assembled review card (Stage 2d, 13.3b) - a multi-day trip or a standalone
    day-event - for the review UI. ``kind`` ("trip" | "event") is the label the screen shows;
    serialisation does not alter either card's persisted identity.
    """
    if card.trip is not None:
        return {
            "kind": card.kind,
            "start": card.trip.start_date.isoformat(),
            "end": card.trip.end_date.isoformat(),
            "count": card.count,
            "active_days": len(card.trip.days),
            "days": [
                {"date": day.isoformat(), "count": count}
                for day, count in sorted(card.trip.days.items())
            ],
            "location": None,
            "collapsed": False,
        }
    assert card.event is not None
    return {
        "kind": card.kind,
        "start": card.event.start.isoformat(),
        "end": card.event.end.isoformat(),
        "count": card.count,
        "active_days": 1,
        "days": [],
        "location": _event_location(card.event),
        "collapsed": is_small_event(card, min_files),
    }


def collapsed_event_summary(
    cards: Sequence[ReviewCard], min_files: int
) -> CollapsedEventSummaryPayload | None:
    """Summarise every hidden event so expanding is optional, not required for confidence."""
    collapsed = collapsed_event_cards(cards, min_files)
    if not collapsed:
        return None
    counts = [card.count for card in collapsed]
    return {
        "count": len(collapsed),
        "min_photos": min(counts),
        "max_photos": max(counts),
        "start": min(card.start for card in collapsed).isoformat(),
        "end": max(card.end for card in collapsed).isoformat(),
    }


def review_cards_payload(
    session: str, cards: Sequence[ReviewCard], min_files: int
) -> ReviewCardsPayload:
    return {
        "session": session,
        "cards": [review_card_json(card, min_files) for card in cards],
        "collapsed": collapsed_event_summary(cards, min_files),
    }


def proposed_review_cards_payload(
    session: str,
    cards: Sequence[ReviewCard],
    min_files: int,
    label: str,
    declines: list[str],
) -> ProposedReviewCardsPayload:
    return {
        **review_cards_payload(session, cards, min_files),
        "ok": True,
        "label": label,
        "declines": declines,
    }


# --- Trip proposal payloads (Trips surface; settings prefs live in settings.py) --------


class InvalidEventProposalPayload(TypedDict):
    ok: Literal[False]
    error: str


# Same shape as the connected-drive soft-refuse (drive_support.DriveUnavailablePayload).
EventProposalDriveErrorPayload = DriveUnavailablePayload


class EventProposalSuccessPayload(TypedDict):
    ok: Literal[True]
    uuid: str
    label: str
    cards: list[ReviewCard]
    day_totals: dict[date, int]
    min_files: int
    declines: list[str]


def invalid_event_proposal_payload(error: str) -> InvalidEventProposalPayload:
    return {"ok": False, "error": error}


def propose_events(
    path: Path, db: Path
) -> EventProposalSuccessPayload | EventProposalDriveErrorPayload:
    """Assemble trips and standalone day-events from an already-organized connected drive.

    Stage 2d, 13.3b's inversion: a genuine multi-day run assembles into ONE card; a standalone
    active day still renders as its own (unchanged) day-event card. Returns the drive uuid + the
    assembled review cards (the caller keeps them, and ``day_totals``, in a session for
    merge/split/name), or an error when the path is not a connected truestill drive.

    A decline is named and explained (§3f), never folded into silence: each carries the exact
    message detection's own ruling requires.
    """
    marker = read_marker(path)
    if marker is None:
        return _drive_unavailable(path)
    with Catalog(db) as catalog:
        settings = EventSettings.from_catalog(catalog)
        review = assemble_trip_review(
            catalog,
            marker.uuid,
            min_files=settings.min_files,
        )
    return {
        "ok": True,
        "uuid": marker.uuid,
        "label": marker.label,
        "cards": review.cards,
        "day_totals": review.day_totals,
        "min_files": settings.min_files,
        "declines": [decline_message(decline) for decline in review.declines],
    }


class MergeReviewCardsResult(TypedDict):
    """Outcome of :func:`merge_event_review_cards` - either new cards or a refusal message."""

    cards: NotRequired[list[ReviewCard]]
    error: NotRequired[str]


def merge_event_review_cards(
    cards: list[ReviewCard],
    day_totals: dict[date, int],
    indices: list[int],
) -> MergeReviewCardsResult:
    """Combine selected review cards into one trip, or refuse with the §3e/§3f message.

    Domain work for the Trips screen's Merge control - lives in service so ``server.py`` stays
    a transport shim (§2 sole-bridge rule; audit F7).
    """
    chosen = [cards[i] for i in indices]
    rest = [card for j, card in enumerate(cards) if j not in set(indices)]
    try:
        merged = merge_review_cards(chosen, day_totals)
    except TripMergeError as exc:
        return {"error": str(exc)}
    return {"cards": order_review_cards([ReviewCard(trip=merged), *rest])}


def split_event_review_card(
    cards: list[ReviewCard],
    index: int,
    *,
    at: int | None = None,
    after_day: str | None = None,
) -> list[ReviewCard]:
    """Split one review card into two and re-order the session list.

    An event splits by file count; a trip splits at a day boundary. Domain work for the Trips
    screen's Split control (§2; audit F7).
    """
    card = cards[index]
    if card.event is not None:
        if at is None:
            message = "event split requires at"
            raise ValueError(message)
        first_event, second_event = split_candidate(card.event, at)
        new_cards = [ReviewCard(event=first_event), ReviewCard(event=second_event)]
    else:
        if after_day is None:
            message = "trip split requires after_day"
            raise ValueError(message)
        assert card.trip is not None
        first_trip, second_trip = split_trip(card.trip, date.fromisoformat(after_day))
        new_cards = [ReviewCard(trip=first_trip), ReviewCard(trip=second_trip)]
    return order_review_cards([*cards[:index], *new_cards, *cards[index + 1 :]])


def _resolve_migration_routes(
    catalog: Catalog,
    drive_uuid: str,
    path: Path,
    *,
    progress: ProgressCallback | None = None,
    cancel: threading.Event | None = None,
) -> tuple[dict[str, str], dict[str, str]]:
    """Resolve ambiguous labels the same way `truestill migrate-layout` does.

    A `Camera`-labelled row is ambiguous by construction (`label_routes`'s own docstring: it is
    the device rule's default label *and* a possible `Software` value) -- migrate and organize
    are the same placement decision, so they must route through the same seam, never a second
    guess. Without this, `plan_migration`'s conservative default (unmapped -> side bin) fires for
    every `Camera` row, because nothing else in this module ever resolved the ambiguity - the app
    has no `--by-device` equivalent, so re-derivation always runs with the plain device rule.

    ``progress`` / ``cancel`` forward into :func:`rederive_rules` (exiftool) - the silent phase
    that made events/migrate preview look frozen on a network mount (backlog oo).
    """
    routes = label_routes(catalog, drive_uuid)
    rules_by_sha = rederive_rules(
        catalog, drive_uuid, path, routes, progress=progress, cancel=cancel
    )
    decided = {r.label: (ROUTE_SIDE_BIN if r.needs_decision else r.route) for r in routes}
    return decided, rules_by_sha


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
        return _drive_unavailable(path)
    with Catalog(db) as catalog:
        scheme = resolve_scheme(catalog)
        routes, rules_by_sha = _resolve_migration_routes(
            catalog, marker.uuid, path, progress=progress, cancel=cancel
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
        "warnings": plan.warnings,
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
        return _drive_unavailable(path)

    def target(progress: ProgressCallback, cancel: threading.Event) -> MigrationPreviewOk:
        result = migration_preview(path, db, progress=progress, cancel=cancel)
        assert result["ok"] is True  # marker gated above; soft-fail already returned
        return result

    return target


class NamedEventSelection(TypedDict):
    event_id: int
    name: str
    start: str
    end: str


class NamedTripSelection(TypedDict):
    trip_id: int
    name: str
    start: str
    end: str


class ApplyReviewNamesResult(TypedDict):
    events: int
    trips: int
    named_events: list[NamedEventSelection]
    named_trips: list[NamedTripSelection]


def apply_event_review_names(
    db: Path,
    cards: list[ReviewCard],
    names: list[str | None],
) -> ApplyReviewNamesResult:
    """Persist named trips and events to the catalog (Save names). No files move.

    Domain work for the Trips screen's apply step - catalog writes belong in service, not the
    HTTP layer (§2; audit F7).
    """
    with Catalog(db) as catalog:
        event_decisions = [
            EventDecision(card.event, name)
            for card, name in zip(cards, names, strict=True)
            if card.event is not None
        ]
        named_events_count = commit_catalog(catalog, event_decisions)

        trip_decisions = [
            TripDecision(card.trip, name)
            for card, name in zip(cards, names, strict=True)
            if card.trip is not None
        ]
        named_trips_count = commit_trips(catalog, trip_decisions)

        named_events: list[NamedEventSelection] = []
        for card, name in zip(cards, names, strict=True):
            if card.event is None or not name or not name.strip():
                continue
            existing = catalog.event_by_signature(card.event.signature)
            if existing is None:
                continue
            named_events.append(
                {
                    "event_id": int(existing["id"]),
                    "name": str(existing["name"]),
                    "start": card.event.start.isoformat(),
                    "end": card.event.end.isoformat(),
                }
            )
        named_trips: list[NamedTripSelection] = []
        for card, name in zip(cards, names, strict=True):
            if card.trip is None or not name or not name.strip():
                continue
            first_day = min(card.trip.days)
            trip_id = catalog.trip_for_day(first_day.isoformat())
            if trip_id is None:
                continue
            named_trips.append(
                {
                    "trip_id": trip_id,
                    "name": name.strip(),
                    "start": first_day.isoformat(),
                    "end": max(card.trip.days).isoformat(),
                }
            )
    return {
        "events": named_events_count,
        "trips": named_trips_count,
        "named_events": named_events,
        "named_trips": named_trips,
    }


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
            raise _not_a_drive(path)
        with Catalog(db) as catalog:
            catalog.upsert_drive(uuid=marker.uuid, label=marker.label)
            pin_existing_layout(catalog)
            scheme = resolve_scheme(catalog)
            routes, rules_by_sha = _resolve_migration_routes(
                catalog, marker.uuid, path, progress=progress, cancel=cancel
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
            leftovers = _cleanup_summary_from_old_paths(
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
        return _drive_unavailable(path)
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
        return _drive_unavailable(path)

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
