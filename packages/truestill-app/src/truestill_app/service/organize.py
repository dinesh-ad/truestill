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
from truestill_core.event_review import EventDecision, commit, propose
from truestill_core.exif import read_metadata
from truestill_core.hash_cache import HashCache
from truestill_core.hashing import DEFAULT_PHASH_THRESHOLD, HEIF_AVAILABLE, HEIF_EXTENSIONS
from truestill_core.layout_settings import pin_existing_layout, resolve_scheme
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
    breakdown = media_breakdown([r.decision.source.name for r in resolutions])
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
    breakdown = media_breakdown(names)
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
