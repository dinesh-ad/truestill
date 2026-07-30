"""Bridge from the web layer to truestill-core. Imports only truestill-core -- never truestill-cli.

Read helpers return plain dicts for JSON; long operations return :data:`JobTarget`s that the
job manager runs on a thread with progress + cancellation. Preview writes nothing (the CLI's
dry-run posture, preserved in the UI).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import threading
import uuid
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path, PurePosixPath
from typing import Any, Literal, TypedDict

from truestill_core.catalog import Catalog
from truestill_core.catalog_startup import inspect_catalog
from truestill_core.categorize import build_rules
from truestill_core.cleanup import (
    emptied_directories,
    plan_cleanup,
    run_cleanup,
    trash_backend,
)
from truestill_core.dates import format_offset
from truestill_core.dedup import DedupIndex
from truestill_core.destinations import LocalDestination
from truestill_core.drive import create_marker, locate_drive, path_is_usable_dir, read_marker
from truestill_core.event_review import EventDecision, commit, propose
from truestill_core.events import (
    EVENT_MIN_FILES_KEY,
    EventCandidate,
    EventSettings,
    InvalidEventSettingsError,
)
from truestill_core.exif import read_metadata
from truestill_core.hash_cache import HashCache
from truestill_core.hashing import (
    DEFAULT_PHASH_THRESHOLD,
    HEIF_AVAILABLE,
    HEIF_EXTENSIONS,
    sha256_file,
)
from truestill_core.layout import (
    DEFAULT_PRESET,
    DEFAULT_TEMPLATE_STRING,
    EVERYDAY_DAY_THRESHOLD_KEY,
    EVERYDAY_DAY_THRESHOLD_MIGRATE_ANCHOR,
    EVERYDAY_DAY_THRESHOLD_MIGRATE_WARNING,
    LAYOUT_TEMPLATE_KEY,
    PRESETS,
    EverydayDaySettings,
    InvalidEverydayDaySettingsError,
    LayoutScheme,
    LayoutTemplate,
    Placement,
    TemplateError,
    effective_layout_string,
    parse_timeline_template,
    pin_existing_layout,
    preview_scheme,
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
    AUDIO_EXTENSIONS,
    IMAGE_EXTENSIONS,
    MEDIA_EXTENSIONS,
    VIDEO_EXTENSIONS,
    Relocation,
    SourceScan,
    discover,
    execute,
    heavy_days_for_organize,
    inventory_source,
    media_kind,
    plan,
    resolve,
    scan_source,
)
from truestill_core.progress import Phase, Progress, ProgressCallback
from truestill_core.takeout import scan_takeout
from truestill_core.trip_review import (
    ReviewCard,
    assemble_trip_review,
    collapsed_event_cards,
    decline_message,
    is_small_event,
)
from truestill_core.undo import UndoError, plan_undo, run_undo
from truestill_core.verify import CopyStatus, CopyToVerify, verify_copies

from truestill_app.jobs import DriveRef, JobTarget


class NotABackupDriveError(ValueError):
    """The path is a real folder, but not a truestill backup drive.

    Typed rather than a bare ValueError so the UI can answer it with the *next step* ("copy
    your library here to make one") instead of restating the failure. The client matches on
    this class name, never on the message text, which would break on any rewording.
    """


class DriveCorrectionPayload(TypedDict):
    error: str
    suggested_root: str | None
    drive_label: str | None
    can_register: bool


def _not_a_drive_message(path: Path) -> str:
    """Say what this path actually is, so the user has something to do about it.

    Three outcomes, three answers. Reporting all of them as "is the drive connected?" asks a
    question whose answer is plainly yes, and leaves someone re-plugging a cable that was never
    loose. The common real case -- naming a folder *inside* a connected drive -- gets a
    correction instead of an error. An unreachable stale hint is a fourth case: ask to browse
    to the current folder; the marker uuid is still the identity.
    """
    if not path_is_usable_dir(path):
        return (
            f"Can't reach '{path}' - it may have moved, been unmounted, or denied access. "
            "Browse to where the drive is now. Identity is the marker on the drive, not this path."
        )
    location = locate_drive(path)
    if location.is_inside and location.marker is not None:
        return (
            f"This is a folder inside '{location.marker.label}'. "
            f"Use the drive root instead: {location.root}"
        )
    return (
        "This folder isn't set up as a backup drive yet. "
        "Copy photos here once and truestill will set it up, "
        "or register this drive first."
    )


def _drive_correction(path: Path) -> DriveCorrectionPayload:
    """The machine-readable half of the same answer, so the UI can offer one-click correction."""
    if not path_is_usable_dir(path):
        # Unreachable: never offer "register this" - registering needs a real folder.
        return {
            "error": _not_a_drive_message(path),
            "suggested_root": None,
            "drive_label": None,
            "can_register": False,
        }
    location = locate_drive(path)
    return {
        "error": _not_a_drive_message(path),
        "suggested_root": str(location.root) if location.is_inside else None,
        "drive_label": location.marker.label if location.marker else None,
        "can_register": location.marker is None,
    }


def drive_ref_for(path: Path) -> DriveRef:
    """Lock identity for a path a job will touch (uuid when marked, else resolved path)."""
    marker = read_marker(path)
    if marker is not None:
        return DriveRef(key=f"uuid:{marker.uuid}", label=marker.label)
    try:
        resolved = str(path.expanduser().resolve())
    except OSError:
        resolved = str(path)
    return DriveRef(key=f"path:{resolved}", label=path.name or resolved)


def _not_a_drive(path: Path) -> NotABackupDriveError:
    return NotABackupDriveError(_not_a_drive_message(path))


#: Remembered paths, for prefilling fields the catalog can already answer. **Hints only.**
#: Drive *identity* is the marker's uuid and never a path (§3.1) -- mount points move between
#: sessions and machines. These exist so a user is never asked to Browse for something we
#: already know, and nothing behind them may ever be trusted as identity.
LIBRARY_PATH_HINT = "path_hint.library"
BACKUP_PATH_HINT = "path_hint.backup"
ORGANIZE_MODE_KEY = "ui.organize.mode"
ORGANIZE_MODES = frozenset({"copy", "move", "inplace"})
SIDEBAR_COLLAPSED_KEY = "ui.sidebar.collapsed"


def reveal_in_file_manager(path: Path) -> dict[str, Any]:
    """Open a folder in the desktop's own file manager.

    A path printed on screen is a dead end: to actually look at the photos a user has to select
    it, copy it and paste it somewhere else. This is the one action that makes a displayed path
    useful.

    **Degrades honestly.** There is no cross-platform way to do this, so the opener is chosen per
    platform (`xdg-open`, `open`, `explorer`); where none exists the caller is told plainly and
    given the path, rather than being left with a button that silently does nothing.

    Only ever opens a directory that already exists, and the path goes into an argument vector
    rather than a shell, so a folder name containing shell metacharacters is just a name. A
    stale/unreachable hint returns the same drive-correction shape as verify - never a raw
    ``OSError``.
    """
    if not path_is_usable_dir(path):
        return {"ok": False, **_drive_correction(path)}
    opener = {"darwin": "open", "win32": "explorer"}.get(sys.platform, "xdg-open")
    if shutil.which(opener) is None:
        return {
            "ok": False,
            "error": (
                f"Can't open a file manager because this machine has no '{opener}'. "
                f"Open the folder yourself: {path}"
            ),
        }
    try:
        subprocess.Popen([opener, str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError as exc:
        return {
            "ok": False,
            "error": f"Couldn't open a file manager ({exc}). Open the folder yourself in your file manager.",
        }
    return {"ok": True, "path": str(path)}


def _drive_path_hint(uuid: str) -> str:
    """Settings key for where a drive was last seen mounted.

    A *hint*, like the others: it lets a drive card offer "Check now" for the right folder
    instead of making the user find it again. Identity remains the marker uuid -- a drive that
    remounts elsewhere is the same drive, and this key is simply stale until it is next seen.
    """
    return f"path_hint.drive.{uuid}"


def _take_live_path_hint(catalog: Catalog, key: str) -> str | None:
    """Return ``key``'s path when it still names a usable directory; otherwise clear it.

    **Failed hints are cleared, not ignored.** A hint is never identity - only a convenience.
    Leaving a dead path in settings would re-stat it on every Backups/library load (slow and
    noisy on locked FUSE). Clearing once stops the re-hit; the next successful attach/verify
    at the real root writes a fresh hint. This is not a custody write: the uuid and
    ``file_copies`` rows are untouched.
    """
    raw = catalog.get_setting(key)
    if raw is None:
        return None
    if path_is_usable_dir(Path(raw)):
        return raw
    catalog.clear_setting(key)
    return None


@dataclass(frozen=True, slots=True)
class DriveAttachment:
    """The result of making a folder usable as a truestill drive."""

    label: str
    registered: bool  # a marker was written now (the folder was not a drive before)
    linked: int  # already-organized files newly attached to this drive
    absent: int  # catalogued files whose copy is not actually on the drive


def attach_drive(path: Path, db: Path, *, write: bool) -> DriveAttachment:
    """Make ``path`` a registered drive, attaching any library already organized into it.

    **Why this exists.** Organizing through the app used to leave its destination unregistered:
    no marker, so no ``file_copies`` rows, so the app could not verify it, could not copy it
    anywhere, and counted it as living in zero places. The whole custody half of the product
    was reachable only by running the CLI's ``drives --init`` first -- a concept a user has no
    reason to have heard of, standing between "I organized my photos" and "make me a backup".

    Two halves, because a folder can be behind in two different ways:

    * **No marker** -- write one, labelled after the folder. A ~100-byte file at the root of a
      folder the user just asked us to fill with copies of their library.
    * **No recorded copies** -- a library organized before its folder was registered has rows
      in ``files`` but none in ``file_copies``. Each is attached only after confirming the copy
      is *actually present*; anything missing is counted and reported, never assumed.

    ``write=False`` reports what would happen and touches nothing, so previews stay pure.
    """
    marker = read_marker(path)
    was_registered = marker is not None
    if marker is None and not write:
        # Report what would happen without doing it: previews write nothing, ever.
        return DriveAttachment(label=path.name or "Library", registered=True, linked=0, absent=0)
    if marker is None:
        marker = create_marker(path, label=path.name or "Library")

    linked = absent = 0
    with Catalog(db) as catalog:
        if write:
            catalog.upsert_drive(uuid=marker.uuid, label=marker.label)
            catalog.set_setting(_drive_path_hint(marker.uuid), str(path))
        known = {row["sha256"] for row in catalog.copies_on_drive(marker.uuid)}
        for row in catalog.organized_files():
            if row["sha256"] in known:
                continue
            if not (path / str(row["relative"])).is_file():
                absent += 1
                continue
            linked += 1
            if write:
                catalog.record_copy(
                    sha256=str(row["sha256"]),
                    drive_uuid=marker.uuid,
                    relative=str(row["relative"]),
                    copy_sha256=row["copy_sha256"],
                    size=row["size"],
                )
    return DriveAttachment(
        label=marker.label, registered=not was_registered, linked=linked, absent=absent
    )


def _now() -> str:
    return datetime.now(UTC).isoformat()


_GB = 1_000_000_000
_MB = 1_000_000


def _gb(n: int) -> str:
    """A human byte size for space messages (GB for anything sizeable, else MB)."""
    return f"{n / _GB:.1f} GB" if n >= _GB else f"{n / _MB:.0f} MB"


def _media_breakdown(names: Any) -> dict[str, Any]:
    """Split a set of file names into photos / videos / audio counts and per-extension formats."""
    plural = {"photo": "photos", "video": "videos", "audio": "audio"}
    counts = {"photos": 0, "videos": 0, "audio": 0}
    fmt: dict[str, Counter[str]] = {"photos": Counter(), "videos": Counter(), "audio": Counter()}
    for name in names:
        kind = media_kind(name)
        if kind is None:
            continue
        group = plural[kind]
        counts[group] += 1
        fmt[group][Path(name).suffix.lower().lstrip(".")] += 1
    return {**counts, "by_format": {g: dict(c.most_common()) for g, c in fmt.items()}}


def _summarize(resolutions: list[Resolution]) -> dict[str, Any]:
    uploads = [r for r in resolutions if r.should_upload]
    near = [r for r in uploads if r.near_duplicate is not None]
    labels = Counter(r.decision.category.label for r in uploads)
    heic = sum(1 for r in resolutions if r.decision.source.suffix.lower() in HEIF_EXTENSIONS)
    breakdown = _media_breakdown([r.decision.source.name for r in resolutions])
    quality = date_quality(uploads)
    shifts = inferred_local_shifts(uploads)
    summary: dict[str, Any] = {
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
        **quality._asdict(),
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
    """Skipped files grouped by extension, so the UI can account for what was not organized."""
    return {
        "documents": dict(Counter(p.suffix.lower() or "(no ext)" for p in scan.documents)),
        "unrecognized": dict(Counter(p.suffix.lower() or "(no ext)" for p in scan.unrecognized)),
    }


def organize_inventory(source: Path) -> dict[str, Any]:
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


def organize_mode_state(db: Path) -> dict[str, Any]:
    with Catalog(db) as catalog:
        saved = _normalize_organize_mode(catalog.get_setting(ORGANIZE_MODE_KEY))
    return {"mode": saved, "modes": sorted(ORGANIZE_MODES)}


def set_organize_mode(mode: object, db: Path) -> dict[str, Any]:
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


def sidebar_state(db: Path) -> dict[str, Any]:
    with Catalog(db) as catalog:
        raw = catalog.get_setting(SIDEBAR_COLLAPSED_KEY)
    return {"collapsed": _normalize_sidebar_collapsed(raw)}


def set_sidebar_collapsed(collapsed: object, db: Path) -> dict[str, Any]:
    saved = _normalize_sidebar_collapsed(collapsed)
    with Catalog(db) as catalog:
        catalog.set_setting(SIDEBAR_COLLAPSED_KEY, "true" if saved else "false")
    return {"ok": True, "collapsed": saved}


def filesystem_relationship(source: Path, destination: Path) -> dict[str, Any]:
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


def _mode_mechanism(source: Path, destination: Path, mode: str) -> dict[str, Any]:
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


def organize_preview(
    source: Path,
    destination: Path,
    db: Path,
    *,
    progress: ProgressCallback | None = None,
    cancel: threading.Event | None = None,
    refresh_metadata: bool = False,
    mode: str = "copy",
) -> dict[str, Any]:
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
    summary = _summarize(resolutions)
    summary["tier"] = "dedup"
    summary["destination_is_drive"] = read_marker(destination) is not None
    summary["skipped"] = _skipped_summary(scan)
    summary["mode"] = mode
    summary["mechanism"] = mechanism
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

    def target(progress: ProgressCallback, cancel: threading.Event) -> dict[str, Any]:
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

    def target(progress: ProgressCallback, cancel: threading.Event) -> dict[str, Any]:
        chosen_mode = _normalize_organize_mode(mode)
        effective_destination = _effective_destination_for_mode(source, destination, chosen_mode)
        mechanism = _mode_mechanism(source, effective_destination, chosen_mode)
        files = discover(source)
        if not files:
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
                moved = sum(1 for row in results if row.status is ActionStatus.MOVED_IN_PLACE)
                if moved:
                    catalog.finish_inplace_run(relocation.run_id)
                else:
                    catalog.discard_inplace_run(relocation.run_id)
        completion = _completion(results, effective_destination)
        completion["mode"] = chosen_mode
        completion["mechanism"] = mechanism
        if chosen_mode in {"move", "inplace"}:
            cleanup = _cleanup_summary_from_results(results, source)
            if cleanup is not None:
                completion["leftover_empty_folders"] = cleanup
        completion["drive_label"] = marker.label
        with Catalog(db) as catalog:
            catalog.set_setting(LIBRARY_PATH_HINT, str(effective_destination))
            # The custody nudge, counted rather than assumed: how much of the library really
            # does exist in only one place right now.
            completion["single_copy"] = catalog.single_copy_count()
        return completion

    return target


def organize_undo_state(db: Path) -> dict[str, Any]:
    """Durable state for undoing rename-based organize runs."""
    with Catalog(db) as catalog:
        try:
            plan = plan_undo(catalog)
        except UndoError:
            return {"ok": True, "armed": False, "restorable": 0, "run_id": None}
    return {
        "ok": True,
        "armed": True,
        "run_id": plan.run_id,
        "status": plan.status,
        "source_root": str(plan.source_root),
        "dest_root": str(plan.dest_root),
        "restorable": plan.restorable,
        "skipped": [
            {
                "relative": item.step.current.name,
                "reason": item.reason.value,
                "detail": item.detail,
            }
            for item in plan.skipped
        ],
    }


def organize_undo(*, db: Path, apply: bool) -> JobTarget:
    """Preview/apply organize undo on a worker thread."""

    def target(progress: ProgressCallback, _cancel: threading.Event) -> dict[str, Any]:
        with Catalog(db) as catalog:
            plan = plan_undo(catalog)
            outcome = run_undo(catalog, plan, apply=apply, progress=progress if apply else None)
            still_armed = catalog.latest_undoable_run() is not None
        return {
            "run_id": plan.run_id,
            "source_root": str(plan.source_root),
            "dest_root": str(plan.dest_root),
            "restorable": plan.restorable,
            "restored": outcome.restored,
            "applied": apply,
            "still_armed": still_armed,
            "skipped": [
                {
                    "relative": item.step.current.name,
                    "reason": item.reason.value,
                    "detail": item.detail,
                }
                for item in outcome.skipped
            ],
        }

    return target


def _cleanup_summary_from_results(
    results: list[ActionResult], source_root: Path
) -> dict[str, Any] | None:
    """Empty-folder leftovers after move/in-place organize, for completion messaging."""
    moved_sources = [
        row.resolution.decision.source
        for row in results
        if row.status in {ActionStatus.MOVED, ActionStatus.MOVED_IN_PLACE}
    ]
    if not moved_sources:
        return None
    old_paths: list[str] = []
    for source in moved_sources:
        try:
            old_paths.append(source.relative_to(source_root).as_posix())
        except ValueError:
            continue
    if not old_paths:
        return None
    return _cleanup_summary_from_old_paths(source_root, old_paths)


def _cleanup_summary_from_old_paths(
    source_root: Path, old_paths: list[str]
) -> dict[str, Any] | None:
    emptied = emptied_directories(old_paths)
    plan = plan_cleanup(source_root, emptied)
    leftovers = [candidate.relative for candidate in plan.removable]
    if not leftovers:
        return None
    return {
        "source_root": str(source_root),
        "emptied": emptied,
        "count": len(leftovers),
        "folders": leftovers,
    }


def clean_empty_preview(path: Path, emptied: list[str]) -> dict[str, Any]:
    plan = plan_cleanup(path, emptied)
    backend = trash_backend()
    return {
        "ok": True,
        "path": str(path),
        "backend": backend,
        "removable": [candidate.relative for candidate in plan.removable],
        "occupied": [
            {"relative": candidate.relative, "contents": list(candidate.contents)}
            for candidate in plan.occupied
        ],
    }


def clean_empty_apply(path: Path, emptied: list[str]) -> dict[str, Any]:
    plan = plan_cleanup(path, emptied)
    backend = trash_backend()
    outcome = run_cleanup(path, plan, apply=True, backend=backend, permanent=False)
    return {
        "ok": True,
        "path": str(path),
        "removed": outcome.removed,
        "trashed": outcome.trashed,
        "deleted": outcome.deleted,
        "failures": outcome.failures,
    }


def _completion(results: list[ActionResult], destination: Path) -> dict[str, Any]:
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


def verify_run(path: Path, db: Path) -> JobTarget | DriveUnavailablePayload:
    """Build a job target that verifies a connected drive's copies against the catalog.

    Soft-fails with the drive-correction payload when the path is unreachable or unmarked,
    matching migration/trips - so a stale hint never becomes a job that dies on ``OSError``.
    """
    marker = read_marker(path)
    if marker is None:
        return {"ok": False, **_drive_correction(path)}

    def target(progress: ProgressCallback, cancel: threading.Event) -> dict[str, Any]:
        with Catalog(db) as catalog:
            catalog.upsert_drive(uuid=marker.uuid, label=marker.label)
            catalog.set_setting(_drive_path_hint(marker.uuid), str(path))
            rows = catalog.copies_on_drive(marker.uuid)
            copies = [
                CopyToVerify(r["sha256"], r["relative"], r["copy_sha256"] or r["sha256"])
                for r in rows
            ]
            results = verify_copies(copies, path, progress=progress, cancel=cancel)
            when = _now()
            for result in results:
                if result.status is CopyStatus.VERIFIED:
                    catalog.mark_copy_verified(
                        sha256=result.copy.sha256, drive_uuid=marker.uuid, when=when
                    )
            catalog.set_drive_verified(marker.uuid, when)
        counts = Counter(r.status.value for r in results)
        return {
            "label": marker.label,
            "verified": counts.get("verified", 0),
            "missing": counts.get("missing", 0),
            "mismatch": counts.get("mismatch", 0),
            "problems": [
                {"status": r.status.value, "relative": r.copy.relative}
                for r in results
                if r.status is not CopyStatus.VERIFIED
            ],
        }

    return target


def list_drives(db: Path) -> list[dict[str, Any]]:
    with Catalog(db) as catalog:
        names_by_drive: dict[str, list[str]] = {}
        for row in catalog.copy_names_by_drive():
            names_by_drive.setdefault(row["drive_uuid"], []).append(row["relative"])
        drives = []
        for d in catalog.list_drives():
            breakdown = _media_breakdown(names_by_drive.get(d["uuid"], []))
            # Live hint only. A dead path is cleared here so the next screen load does not
            # re-stat it; Check now / open-folder are omitted when path is absent.
            path = _take_live_path_hint(catalog, _drive_path_hint(d["uuid"]))
            drives.append(
                {
                    "label": d["label"],
                    "uuid": d["uuid"],
                    "files": d["file_count"],
                    "photos": breakdown["photos"],
                    "videos": breakdown["videos"],
                    "audio": breakdown["audio"],
                    "size": d["total_size"] or 0,
                    "last_seen": d["last_seen"],
                    "last_verified": d["last_verified"],
                    # Where it was last seen, so a card can offer "Check now" for the right
                    # folder. Absent when we have never had a path for it, or the hint was
                    # stale and cleared -- in which case the card states the fact without
                    # offering an action it cannot honour.
                    "path": path,
                }
            )
        return drives


def where(term: str, db: Path, *, page: int = 1) -> dict[str, Any]:
    """One page of search results, plus what the caller needs to render a pager.

    Paged in SQL (`Catalog.find_copies`), so a page costs a page of rows however large the
    library is. The total comes from a separate `COUNT(*)`, which is what makes "page 3 of 12"
    honest rather than "more results, somewhere".
    """
    size = Catalog.FIND_PAGE_SIZE
    page = max(1, page)
    with Catalog(db) as catalog:
        total = catalog.count_copies(term)
        rows = catalog.find_copies(term, limit=size, offset=(page - 1) * size)
        copies = [
            {
                "name": r["original_name"] or r["relative"],
                "drive": r["drive_label"],
                "relative": r["relative"],
                "last_verified": r["last_verified"],
            }
            for r in rows
        ]
    return {
        "copies": copies,
        "total": total,
        "page": page,
        "pages": max(1, -(-total // size)),
        "page_size": size,
    }


def at_risk(db: Path) -> list[dict[str, Any]]:
    with Catalog(db) as catalog:
        return [
            {"name": r["original_name"] or r["sha256"][:12], "drive": r["drive_label"]}
            for r in catalog.single_copy_shas()
        ]


def _format_counts(catalog: Catalog) -> dict[str, int]:
    """Counts by extension from one aggregate SQL pass over catalog names."""
    extensions = sorted({ext.lstrip(".").lower() for ext in MEDIA_EXTENSIONS})
    case_parts: list[str] = []
    params: list[str] = []
    for ext in extensions:
        case_parts.append("WHEN name LIKE ? THEN ?")
        params.extend([f"%.{ext}", ext])
    row_sql = "\n".join(case_parts) if case_parts else "ELSE ''"
    sql = f"""
        WITH named AS (
            SELECT lower(COALESCE(original_name, relative, source_path, '')) AS name
            FROM files
        )
        SELECT ext, COUNT(*) AS count
        FROM (
            SELECT CASE
                {row_sql}
                ELSE ''
            END AS ext
            FROM named
        )
        WHERE ext != ''
        GROUP BY ext
        ORDER BY count DESC, ext
    """
    rows = catalog._conn.execute(sql, params).fetchall()
    return {str(row["ext"]): int(row["count"]) for row in rows}


def library_stats(db: Path) -> dict[str, Any]:
    """Custody-first library stats from catalog-only aggregates.

    Complexity: O(n) aggregate scans over ``files``/``file_copies`` plus grouped rollups for
    years and formats. No file reads, no hashing, no exiftool, and no per-file Python loops.
    """
    with Catalog(db) as catalog:
        summary = catalog.stats_summary()
        year_rows = catalog.stats_by_year()
        drives = catalog.list_drives()
        near_flagged = catalog.stats_near_duplicate_flagged_count()
        undated_samples = catalog.stats_undated_samples(limit=12)
        format_counts = _format_counts(catalog)
        zero_drive_rows = catalog._conn.execute(
            """
            SELECT COALESCE(original_name, sha256) AS name
            FROM files f
            WHERE NOT EXISTS (
                SELECT 1 FROM file_copies fc WHERE fc.sha256 = f.sha256
            )
            ORDER BY processed_at DESC
            LIMIT 12
            """
        ).fetchall()

    image_exts = {ext.lstrip(".").lower() for ext in IMAGE_EXTENSIONS}
    video_exts = {ext.lstrip(".").lower() for ext in VIDEO_EXTENSIONS}
    audio_exts = {ext.lstrip(".").lower() for ext in AUDIO_EXTENSIONS}
    photos = sum(count for ext, count in format_counts.items() if ext in image_exts)
    videos = sum(count for ext, count in format_counts.items() if ext in video_exts)
    audio = sum(count for ext, count in format_counts.items() if ext in audio_exts)

    return {
        "safety": {
            "total_files": int(summary["total_files"]),
            "total_size": int(summary["total_size"] or 0),
            "photos": photos,
            "videos": videos,
            "audio": audio,
            "files_on_two_plus_drives": int(summary["files_on_two_plus_drives"] or 0),
            "files_on_one_drive": int(summary["files_on_one_drive"] or 0),
            "files_on_zero_drives": int(summary["files_on_zero_drives"] or 0),
            "zero_drive_samples": [str(row["name"]) for row in zero_drive_rows],
            "never_verified_files": int(summary["never_verified_files"] or 0),
            "drives": [
                {
                    "label": str(row["label"]),
                    "files": int(row["file_count"] or 0),
                    "size": int(row["total_size"] or 0),
                    "last_verified": row["last_verified"],
                }
                for row in drives
            ],
        },
        "completeness": {
            "undated_files": int(summary["undated_files"] or 0),
            "undated_samples": [
                {
                    "name": str(row["original_name"] or Path(str(row["source_path"])).name),
                    "source_path": str(row["source_path"]),
                    "relative": str(row["relative"]),
                }
                for row in undated_samples
            ],
            "timeline_files": int(summary["timeline_files"] or 0),
            "side_bin_files": int(summary["side_bin_files"] or 0),
            "near_duplicates_flagged": near_flagged,
            # Exact duplicates are intentionally omitted: skipped exact dupes are not persisted
            # in the catalog, and recomputing them would require a fresh source scan.
            "exact_duplicates_found": None,
            "exact_duplicates_omission_reason": (
                "Exact-duplicate skips are not stored in the catalog; computing this would require "
                "a new scan outside the read-only stats contract."
            ),
        },
        "shape": {
            "by_year": [
                {"year": str(row["year"]), "count": int(row["count"])} for row in year_rows
            ],
            "by_format": format_counts,
            "oldest_capture": summary["oldest_capture"],
            "newest_capture": summary["newest_capture"],
        },
        "complexity": "O(n) aggregate SQL over catalog tables; grouped rollups only.",
    }


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


# --- Takeout rescue report (Rescue report screen) -------------------------------------


def ingest_preview(
    takeout: Path,
    destination: Path,  # noqa: ARG001 - kept for API symmetry with organize preview
    db: Path,
    *,
    progress: ProgressCallback | None = None,
    cancel: threading.Event | None = None,
) -> dict[str, Any]:
    """Dry-run Takeout rescue: the honest report the Rescue screen shows before any run.

    Discovery has no progress callback, so the first tick is indeterminate (:attr:`Phase.SCANNING`
    with ``total=0``) rather than a fake count. Metadata and hashing then reuse the same
    callbacks :func:`read_metadata` and :func:`resolve` already expose to organize preview.
    """
    if progress is not None:
        progress(Progress(0, 0, Phase.SCANNING, ""))
    scan = scan_takeout(takeout)
    files = discover(takeout)
    if not files:
        return {"files": 0, "missing_sidecar": 0}
    with Catalog(db) as catalog, HashCache.beside(db) as cache:
        metadata = read_metadata(files, progress=progress, cancel=cancel, cache=cache)
        scheme = resolve_scheme(catalog)
        rules = build_rules()
        heavy = heavy_days_for_organize(catalog, files, metadata, rules, takeout=scan.sidecars)
        decisions = plan(
            files, metadata, rules, takeout=scan.sidecars, scheme=scheme, heavy_days=heavy
        )
        index = DedupIndex.from_catalog_rows(catalog.seed_rows(), DEFAULT_PHASH_THRESHOLD)
        resolutions = resolve(
            decisions,
            index,
            catalog_sizes=catalog.known_sizes(),
            progress=progress,
            cancel=cancel,
            cache=cache,
        )
    uploads = [r for r in resolutions if r.should_upload]
    dups = [r for r in resolutions if not r.should_upload]
    sources = Counter(r.decision.date_source.value for r in uploads)
    reclaimed = sum(_safe_size(r.decision.source) for r in dups)
    return {
        "files": len(resolutions),
        "kept": len(uploads),
        "dup_collapsed": len(dups),
        "reclaimed_mb": round(reclaimed / 1e6, 1),
        "dates_photo_taken": sources.get("takeout", 0),
        "dates_upload_approx": sources.get("takeout_upload", 0),
        "dates_exif": sources.get("exif", 0),
        "undated": sources.get("none", 0),
        **date_quality(uploads)._asdict(),
        "inferred_local_shifts": [
            {
                "name": s.name,
                "before": s.before.strftime("%H:%M:%S"),
                "after": s.after.strftime("%H:%M:%S"),
                "offset": format_offset(s.offset),
                "evidence": s.evidence,
                "line": format_inferred_local_shift_line(s),
            }
            for s in inferred_local_shifts(uploads)
        ],
        "missing_sidecar": len(scan.missing_sidecar),
    }


def ingest_preview_run(takeout: Path, destination: Path, db: Path) -> JobTarget:
    """Takeout rescue preview as a cancellable job - same dry-run, streamed progress."""

    def target(progress: ProgressCallback, cancel: threading.Event) -> dict[str, Any]:
        return ingest_preview(takeout, destination, db, progress=progress, cancel=cancel)

    return target


def _safe_size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


# --- server-side folder picker (Browse) -----------------------------------------------


def fs_roots() -> list[dict[str, str]]:
    """Friendly starting points: Home + common media folders + mounted drives."""
    roots: list[dict[str, str]] = []
    home = Path.home()
    roots.append({"label": "Home", "path": str(home)})
    for name in ("Pictures", "Downloads", "Desktop", "Documents"):
        candidate = home / name
        if candidate.is_dir():
            roots.append({"label": name, "path": str(candidate)})
    for base in ("/media", "/mnt", "/run/media", "/Volumes"):
        root = Path(base)
        if not root.is_dir():
            continue
        try:
            for child in sorted(root.iterdir()):
                if child.is_dir():
                    roots.append({"label": child.name, "path": str(child)})
        except OSError:
            continue
    return roots


def fs_dirs(path_str: str) -> dict[str, Any]:
    """List the immediate sub-directories of ``path`` (or the roots when empty)."""
    if not path_str.strip():
        return {"path": "", "parent": None, "roots": fs_roots(), "entries": []}
    path = Path(path_str).expanduser()
    try:
        path = path.resolve()
    except OSError:
        return {
            "error": "That path could not be read. It may have moved or access may be blocked. Pick another folder.",
            "roots": fs_roots(),
            "entries": [],
        }
    if not path.is_dir():
        return {
            "error": "That path is not a folder. Pick a folder.",
            "roots": fs_roots(),
            "entries": [],
        }
    entries: list[dict[str, str]] = []
    try:
        for child in sorted(path.iterdir(), key=lambda p: p.name.lower()):
            if child.is_dir() and not child.name.startswith("."):
                entries.append({"name": child.name, "path": str(child)})
    except OSError:
        return {
            "error": "That folder could not be read. Check permissions, then try again.",
            "roots": fs_roots(),
            "entries": [],
        }
    parent = str(path.parent) if path.parent != path else None
    return {"path": str(path), "parent": parent, "roots": fs_roots(), "entries": entries}


def fs_create(path_str: str) -> dict[str, Any]:
    """Create a folder (and parents) - for the "Create it?" action on a new backup destination."""
    path = Path(path_str).expanduser()
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return {
            "created": False,
            "error": (
                f"Couldn't create this folder ({exc}). "
                "Choose another location, or create it in your file manager."
            ),
        }
    return {"created": True, **fs_validate(str(path))}


def fs_validate(path_str: str, *, cap: int = 10000) -> dict[str, Any]:
    """Report whether ``path`` is a usable folder and roughly how much media it holds."""
    path = Path(path_str).expanduser()
    try:
        path = path.resolve()
    except OSError:
        return {"exists": False, "is_dir": False, "readable": False, "writable": False, "media": 0}
    is_dir = path.is_dir()
    media = 0
    capped = False
    if is_dir and os.access(path, os.R_OK):
        for child in path.rglob("*"):
            if child.suffix.lower() in MEDIA_EXTENSIONS:
                media += 1
                if media >= cap:
                    capped = True
                    break
    return {
        "exists": path.exists(),
        "is_dir": is_dir,
        "readable": os.access(path, os.R_OK) if path.exists() else False,
        "writable": os.access(path, os.W_OK) if path.exists() else False,
        "is_drive": read_marker(path) is not None,
        "media": media,
        "media_capped": capped,
    }


# --- library custody status (the sidebar's always-true status line) -------------------


def library_status(db: Path, *, explicit_db: bool = False) -> dict[str, Any]:
    """Honest, catalog-driven totals for the custody strip.

    Always names the resolved absolute catalog path. A missing file is first-run (info), not
    an error; an empty file with registered drives is the loud wrong-catalog case.
    """
    # Inspect before Catalog() so a missing path stays will_create (Catalog would create it).
    startup = inspect_catalog(db, explicit_db=explicit_db)
    with Catalog(db) as catalog:
        breakdown = _media_breakdown(catalog.media_names())
        total = catalog.count()
        drives = [d for d in catalog.list_drives() if d["file_count"]]
        single_copy = catalog.single_copy_count()
        total_bytes = sum(d["total_size"] or 0 for d in drives)
        library_path = _take_live_path_hint(catalog, LIBRARY_PATH_HINT)
        backup_path = _take_live_path_hint(catalog, BACKUP_PATH_HINT)
    return {
        "library_path": library_path,
        "backup_path": backup_path,
        "files": total,
        "photos": breakdown["photos"],
        "videos": breakdown["videos"],
        "audio": breakdown["audio"],
        "by_format": breakdown["by_format"],
        "places": len(drives),
        "single_copy": single_copy,
        "bytes": total_bytes,
        "catalog_path": startup.absolute_path,
        "catalog_presence": startup.presence.value,
        "catalog_detail": startup.detail,
        "catalog_tone": startup.tone,
    }


# --- Settings --------------------------------------------------------------------------


class EventSettingsPayload(TypedDict):
    valid: Literal[True]
    min_files: int
    default_min_files: int
    is_default: bool


class InvalidEventSettingsPayload(TypedDict):
    valid: Literal[False]
    error: str


class InvalidEventProposalPayload(TypedDict):
    ok: Literal[False]
    error: str


class EventProposalDriveErrorPayload(DriveCorrectionPayload):
    ok: Literal[False]


class EventProposalSuccessPayload(TypedDict):
    ok: Literal[True]
    uuid: str
    label: str
    cards: list[ReviewCard]
    day_totals: dict[date, int]
    min_files: int
    declines: list[str]


def event_settings(db: Path) -> EventSettings:
    """Read the validated preference once through the catalog's existing settings seam."""
    with Catalog(db) as catalog:
        return EventSettings.from_catalog(catalog)


def event_settings_payload(settings: EventSettings) -> EventSettingsPayload:
    return {
        "valid": True,
        "min_files": settings.min_files,
        "default_min_files": EventSettings().min_files,
        "is_default": settings.is_default,
    }


def invalid_event_settings_payload(error: str) -> InvalidEventSettingsPayload:
    return {"valid": False, "error": error}


def invalid_event_proposal_payload(error: str) -> InvalidEventProposalPayload:
    return {"ok": False, "error": error}


def set_event_settings(min_files: object, db: Path) -> EventSettings:
    """Persist a positive proposal-size floor, rejecting malformed API input without writing."""
    if isinstance(min_files, bool) or not isinstance(min_files, int) or min_files < 1:
        raise InvalidEventSettingsError.submitted()
    settings = EventSettings(min_files=min_files, is_default=False)
    with Catalog(db) as catalog:
        catalog.set_setting(EVENT_MIN_FILES_KEY, str(min_files))
    return settings


class EverydayDaySettingsPayload(TypedDict):
    valid: Literal[True]
    threshold: int
    default_threshold: int
    is_default: bool
    migrate_warning: str | None
    migrate_anchor: str


class InvalidEverydayDaySettingsPayload(TypedDict):
    valid: Literal[False]
    error: str


def everyday_day_settings(db: Path) -> EverydayDaySettings:
    """Read the validated Everyday day-folder threshold through the catalog settings seam."""
    with Catalog(db) as catalog:
        return EverydayDaySettings.from_catalog(catalog)


def everyday_day_settings_payload(
    settings: EverydayDaySettings, *, changed: bool = False
) -> EverydayDaySettingsPayload:
    return {
        "valid": True,
        "threshold": settings.threshold,
        "default_threshold": EverydayDaySettings().threshold,
        "is_default": settings.is_default,
        "migrate_warning": EVERYDAY_DAY_THRESHOLD_MIGRATE_WARNING if changed else None,
        "migrate_anchor": EVERYDAY_DAY_THRESHOLD_MIGRATE_ANCHOR,
    }


def invalid_everyday_day_settings_payload(error: str) -> InvalidEverydayDaySettingsPayload:
    return {"valid": False, "error": error}


def set_everyday_day_settings(threshold: object, db: Path) -> EverydayDaySettingsPayload:
    """Persist the day-folder threshold; warn when the value actually changes (migrate needed)."""
    if isinstance(threshold, bool) or not isinstance(threshold, int) or threshold < 1:
        raise InvalidEverydayDaySettingsError.submitted()
    settings = EverydayDaySettings(threshold=threshold, is_default=False)
    with Catalog(db) as catalog:
        prior = EverydayDaySettings.from_catalog(catalog)
        catalog.set_setting(EVERYDAY_DAY_THRESHOLD_KEY, str(threshold))
    changed = prior.threshold != threshold
    return everyday_day_settings_payload(settings, changed=changed)


# --- layout Settings screen (template + migration) ------------------------------------


def _render_preview(scheme: LayoutScheme) -> list[dict[str, Any]]:
    """The sample rows rendered through a whole scheme, so the preview shows the routing split."""
    return [
        {
            "description": row.description,
            "when": row.context.captured_at.strftime("%Y-%m-%d")
            if row.context.captured_at
            else "undated",
            "path": rendered.path.as_posix(),
            "warnings": list(rendered.warnings),
        }
        for row, rendered in preview_scheme(scheme)
    ]


def layout_state(db: Path) -> dict[str, Any]:
    """What layout is actually in force for this library, plus the presets and a live preview.

    Everything here is derived from `effective_layout_string`, which is **pure** - opening
    Settings must not write a setting, and previewing must not pin a layout. A legacy library
    therefore shows its real (category-first) shape truthfully rather than being shown the new
    default it has not adopted.
    """
    with Catalog(db) as catalog:
        stored = effective_layout_string(catalog)
        scheme = resolve_scheme(catalog)
    return {
        "template": stored or DEFAULT_TEMPLATE_STRING,
        "is_default": stored is None,
        # str -> str, deliberately: the payload is JSON and app.js iterates it. Handing it
        # preset objects would serialize dataclasses into the API. Pinned by a test.
        "presets": {name: p.timeline for name, p in PRESETS.items()},
        "preset_titles": {name: p.title for name, p in PRESETS.items()},
        "default_preset": DEFAULT_PRESET.key,
        "preview": _render_preview(scheme),
    }


def _scheme_for_timeline(template: LayoutTemplate) -> LayoutScheme:
    """A scheme for previewing a typed timeline template: fixed side bin, events appended."""
    return LayoutScheme.of(timeline=template, timeline_evented=template)


def preview_layout(template_str: str) -> dict[str, Any]:
    """Validate a template and render the samples; report the error instead of raising."""
    try:
        template = parse_timeline_template(template_str)
    except TemplateError as exc:
        return {"valid": False, "error": str(exc)}
    return {"valid": True, "preview": _render_preview(_scheme_for_timeline(template))}


def set_layout(template_str: str, db: Path) -> dict[str, Any]:
    """Persist a template after validating it; returns the new :func:`layout_state` or an error."""
    try:
        parse_timeline_template(template_str)
    except TemplateError as exc:
        return {"valid": False, "error": str(exc)}
    with Catalog(db) as catalog:
        catalog.set_setting(LAYOUT_TEMPLATE_KEY, template_str)
    return {"valid": True, **layout_state(db)}


_FREE_SPACE_MARGIN = 1.03  # keep a little headroom so a copy never fills the target drive


def _files_missing_on_target(catalog: Catalog, source_uuid: str, target_uuid: str) -> list[Any]:
    """Copies present on the source drive but not yet on the target -- keyed on per-drive presence,
    not the catalog-global dedup that would wrongly skip a genuine second copy."""
    on_target = {r["sha256"] for r in catalog.copies_on_drive(target_uuid)}
    return [r for r in catalog.copies_on_drive(source_uuid) if r["sha256"] not in on_target]


def backup_preview(source: Path, target: Path, db: Path) -> dict[str, Any]:
    """Preview copying the library from one connected drive to another (writes nothing).

    Reports how many files (and bytes) are missing on the target, and whether the target has room
    -- a disk-full part-way through is the failure this whole feature exists to prevent.
    """
    if not source.is_dir():
        return {
            "ok": False,
            "error": "The From folder was not found. Check the path, then pick an existing folder.",
        }
    if not target.is_dir():
        return {
            "ok": False,
            "error": "The To folder was not found. Check the path, then pick or create a folder.",
        }
    if source.resolve() == target.resolve():
        return {
            "ok": False,
            "error": "From and To point to the same folder. Pick a different destination drive.",
        }
    # Preview writes nothing, so an unregistered folder is *reported* as one that will be
    # registered rather than rejected -- the run does the registering.
    src = attach_drive(source, db, write=False)
    tgt = attach_drive(target, db, write=False)
    src_marker, tgt_marker = read_marker(source), read_marker(target)
    if src_marker is not None and tgt_marker is not None and src_marker.uuid == tgt_marker.uuid:
        return {
            "ok": False,
            "error": "From and To are the same drive. Pick a different backup drive.",
        }
    with Catalog(db) as catalog:
        missing = (
            _files_missing_on_target(catalog, src_marker.uuid, tgt_marker.uuid)
            if src_marker is not None and tgt_marker is not None
            else [dict(r) for r in catalog.organized_files()]
        )
    need = sum(int(r["size"] or 0) for r in missing)
    free = shutil.disk_usage(target).free
    breakdown = _media_breakdown([str(r["relative"]) for r in missing])
    return {
        "ok": True,
        "from": src.label,
        "to": tgt.label,
        "will_register": [d.label for d in (src, tgt) if d.registered],
        "count": len(missing),
        "photos": breakdown["photos"],
        "videos": breakdown["videos"],
        "audio": breakdown["audio"],
        "bytes": need,
        "free": free,
        "enough": free >= need * _FREE_SPACE_MARGIN,
    }


def backup_run(source: Path, target: Path, db: Path) -> JobTarget:
    """Build a job that copies the library to another drive: verify-after-write, record each copy."""

    def target_job(progress: ProgressCallback, cancel: threading.Event) -> dict[str, Any]:
        if not source.is_dir() or not target.is_dir():
            message = "both the 'from' and 'to' folders must exist."
            raise ValueError(message)
        # Register whatever is not yet a drive, and attach a library organized before its
        # folder was registered. Without this the app rejects the very library it just built.
        attach_drive(source, db, write=True)
        attach_drive(target, db, write=True)
        src_marker, tgt_marker = read_marker(source), read_marker(target)
        if src_marker is None or tgt_marker is None:
            raise _not_a_drive(source if src_marker is None else target)
        if src_marker.uuid == tgt_marker.uuid:
            message = "the 'from' and 'to' folders are the same drive."
            raise ValueError(message)
        with Catalog(db) as catalog:
            missing = _files_missing_on_target(catalog, src_marker.uuid, tgt_marker.uuid)
            need = sum(int(r["size"] or 0) for r in missing)
            free = shutil.disk_usage(target).free
            if free < need * _FREE_SPACE_MARGIN:
                message = (
                    f"not enough space on {tgt_marker.label}: needs {_gb(need)}, "
                    f"only {_gb(free)} free."
                )
                raise ValueError(message)
            copied = 0
            copied_names: list[str] = []
            copied_bytes = 0
            for row in missing:
                if cancel.is_set():
                    break
                rel = str(row["relative"])
                dst = target / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source / rel, dst)
                want = row["copy_sha256"] or row["sha256"]
                if sha256_file(dst) != want:  # verify-after-write; a bad copy is never recorded
                    dst.unlink(missing_ok=True)
                    message = f"copy of {rel} did not verify -- stopping to stay safe."
                    raise ValueError(message)
                catalog.record_copy(
                    sha256=str(row["sha256"]),
                    drive_uuid=tgt_marker.uuid,
                    relative=rel,
                    copy_sha256=want,
                    size=int(row["size"] or 0) or None,
                )
                catalog.mark_copy_verified(
                    sha256=str(row["sha256"]), drive_uuid=tgt_marker.uuid, when=_now()
                )
                copied += 1
                copied_names.append(rel)
                copied_bytes += int(row["size"] or 0)
                progress(Progress(copied, len(missing), Phase.COPYING, Path(rel).name))
            catalog.set_setting(BACKUP_PATH_HINT, str(target))
        breakdown = _media_breakdown(copied_names)
        return {
            "copied": copied,
            "to": tgt_marker.label,
            "photos": breakdown["photos"],
            "videos": breakdown["videos"],
            "audio": breakdown["audio"],
            "bytes_copied": copied_bytes,
            # Every copy was re-hashed against the recorded digest before being recorded; a
            # copy that failed that check aborts the run. Saying so is the point of the whole
            # feature, so the completion card gets to say it.
            "verified": True,
            "target_path": str(target),
        }

    return target_job


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
        return {"ok": False, **_drive_correction(path)}
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


def migration_preview(
    path: Path,
    db: Path,
    *,
    progress: ProgressCallback | None = None,
    cancel: threading.Event | None = None,
) -> dict[str, Any]:
    """Preview relocating a connected drive's files to the current template (moves nothing)."""
    marker = read_marker(path)
    if marker is None:
        return {"ok": False, **_drive_correction(path)}
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
        return {"ok": False, **_drive_correction(path)}

    def target(progress: ProgressCallback, cancel: threading.Event) -> dict[str, Any]:
        return migration_preview(path, db, progress=progress, cancel=cancel)

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


class AppliedReviewGroupPayload(TypedDict):
    kind: Literal["trip", "event"]
    name: str
    start: str
    end: str
    path: str


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

    def target(progress: ProgressCallback, cancel: threading.Event) -> dict[str, Any]:
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
                        "path": str(PurePosixPath(relative).parent),
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
                        "path": str(PurePosixPath(relative).parent.parent),
                    }
                )
            leftovers = _cleanup_summary_from_old_paths(
                path, catalog.migrated_old_paths(marker.uuid)
            )
        result: dict[str, Any] = {
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


class DriveUnavailablePayload(TypedDict):
    """Connected-drive gate failed: same correction shape migration preview already returns."""

    ok: Literal[False]
    error: str
    suggested_root: str | None
    drive_label: str | None
    can_register: bool


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


def migration_armed_state(path: Path, db: Path) -> ArmedStatePayload | DriveUnavailablePayload:
    """Read-only: does this connected drive still have a reversible migration record?

    Answers from ``catalog.reversible_migration`` only. Never upserts the drive, never touches
    the journal - a tab reload must be able to ask this without changing anything.
    """
    marker = read_marker(path)
    if marker is None:
        return {"ok": False, **_drive_correction(path)}
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
        return {"ok": False, **_drive_correction(path)}

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
