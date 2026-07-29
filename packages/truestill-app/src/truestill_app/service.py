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
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any, Literal, TypedDict

from truestill_core.catalog import Catalog
from truestill_core.categorize import build_rules
from truestill_core.dedup import DedupIndex
from truestill_core.destinations import LocalDestination
from truestill_core.drive import create_marker, locate_drive, read_marker
from truestill_core.event_review import EventDecision, commit, propose
from truestill_core.events import (
    EVENT_MIN_FILES_KEY,
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
    LAYOUT_TEMPLATE_KEY,
    PRESETS,
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
)
from truestill_core.models import (
    ActionResult,
    ActionStatus,
    Resolution,
    date_quality,
    status_label,
)
from truestill_core.organizer import (
    MEDIA_EXTENSIONS,
    SourceScan,
    discover,
    execute,
    media_kind,
    plan,
    resolve,
    scan_source,
)
from truestill_core.progress import Phase, Progress, ProgressCallback
from truestill_core.takeout import scan_takeout
from truestill_core.trip_review import ReviewCard, assemble_trip_review, decline_message
from truestill_core.verify import CopyStatus, CopyToVerify, verify_copies

from truestill_app.jobs import JobTarget


class NotABackupDriveError(ValueError):
    """The path is a real folder, but not a truestill backup drive.

    Typed rather than a bare ValueError so the UI can answer it with the *next step* ("copy
    your library here to make one") instead of restating the failure. The client matches on
    this class name, never on the message text, which would break on any rewording.
    """


def _not_a_drive_message(path: Path) -> str:
    """Say what this path actually is, so the user has something to do about it.

    Three outcomes, three answers. Reporting all of them as "is the drive connected?" asks a
    question whose answer is plainly yes, and leaves someone re-plugging a cable that was never
    loose. The common real case -- naming a folder *inside* a connected drive -- gets a
    correction instead of an error.
    """
    location = locate_drive(path)
    if location.is_inside and location.marker is not None:
        return (
            f"This is a folder inside '{location.marker.label}'. "
            f"Use the drive root instead: {location.root}"
        )
    return "This folder isn't a truestill drive yet - register it to start tracking copies here."


def _drive_correction(path: Path) -> dict[str, Any]:
    """The machine-readable half of the same answer, so the UI can offer one-click correction."""
    location = locate_drive(path)
    return {
        "error": _not_a_drive_message(path),
        "suggested_root": str(location.root) if location.is_inside else None,
        "drive_label": location.marker.label if location.marker else None,
        "can_register": location.marker is None,
    }


def _not_a_drive(path: Path) -> NotABackupDriveError:
    return NotABackupDriveError(_not_a_drive_message(path))


#: Remembered paths, for prefilling fields the catalog can already answer. **Hints only.**
#: Drive *identity* is the marker's uuid and never a path (§3.1) -- mount points move between
#: sessions and machines. These exist so a user is never asked to Browse for something we
#: already know, and nothing behind them may ever be trusted as identity.
LIBRARY_PATH_HINT = "path_hint.library"
BACKUP_PATH_HINT = "path_hint.backup"


def reveal_in_file_manager(path: Path) -> dict[str, Any]:
    """Open a folder in the desktop's own file manager.

    A path printed on screen is a dead end: to actually look at the photos a user has to select
    it, copy it and paste it somewhere else. This is the one action that makes a displayed path
    useful.

    **Degrades honestly.** There is no cross-platform way to do this, so the opener is chosen per
    platform (`xdg-open`, `open`, `explorer`); where none exists the caller is told plainly and
    given the path, rather than being left with a button that silently does nothing.

    Only ever opens a directory that already exists, and the path goes into an argument vector
    rather than a shell, so a folder name containing shell metacharacters is just a name.
    """
    if not path.is_dir():
        return {"ok": False, "error": f"{path} is not a folder that exists."}
    opener = {"darwin": "open", "win32": "explorer"}.get(sys.platform, "xdg-open")
    if shutil.which(opener) is None:
        return {
            "ok": False,
            "error": f"This machine has no '{opener}', so truestill cannot open a file manager. "
            f"The folder is: {path}",
        }
    try:
        subprocess.Popen([opener, str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError as exc:
        return {"ok": False, "error": f"Could not open a file manager: {exc}"}
    return {"ok": True, "path": str(path)}


def _drive_path_hint(uuid: str) -> str:
    """Settings key for where a drive was last seen mounted.

    A *hint*, like the others: it lets a drive card offer "Check now" for the right folder
    instead of making the user find it again. Identity remains the marker uuid -- a drive that
    remounts elsewhere is the same drive, and this key is simply stale until it is next seen.
    """
    return f"path_hint.drive.{uuid}"


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


def organize_preview(
    source: Path,
    destination: Path,
    db: Path,
    *,
    progress: ProgressCallback | None = None,
    cancel: threading.Event | None = None,
) -> dict[str, Any]:
    """Plan + dedup with no writes -- the dry-run summary the UI shows before a real run.

    Reports progress through the same phases the real run does, because it does the same
    work: reading metadata, then hashing. On a large library this is the **first** long wait
    a user ever experiences with truestill, which makes it the worst possible place to look
    like nothing is happening.
    """
    scan = scan_source(source)
    files = scan.media
    if not files:
        return {"files": 0, "folders": {}, "skipped": _skipped_summary(scan)}
    metadata = read_metadata(files, progress=progress, cancel=cancel)
    with Catalog(db) as catalog, HashCache.beside(db) as cache:
        scheme = resolve_scheme(catalog)
        decisions = plan(files, metadata, build_rules(), scheme=scheme)
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
    summary["destination_is_drive"] = read_marker(destination) is not None
    summary["skipped"] = _skipped_summary(scan)
    return summary


def organize_preview_run(source: Path, destination: Path, db: Path) -> JobTarget:
    """The preview as a cancellable background job, so it can report progress like the rest.

    Still a dry run in every respect: this writes nothing to the destination or the catalog.
    Only *how* the answer is delivered changed.
    """

    def target(progress: ProgressCallback, cancel: threading.Event) -> dict[str, Any]:
        return organize_preview(source, destination, db, progress=progress, cancel=cancel)

    return target


def organize_run(
    source: Path, destination: Path, db: Path, *, skip_undated: bool = False
) -> JobTarget:
    """Build a job target that runs the real organize (progress across hashing then copying)."""

    def target(progress: ProgressCallback, cancel: threading.Event) -> dict[str, Any]:
        files = discover(source)
        if not files:
            return _completion([], destination)
        metadata = read_metadata(files, progress=progress)
        with Catalog(db) as catalog, HashCache.beside(db) as cache:
            pin_existing_layout(catalog)
            scheme = resolve_scheme(catalog)
            decisions = plan(files, metadata, build_rules(), scheme=scheme)
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
            marker = read_marker(destination) or create_marker(
                destination, label=destination.name or "Library"
            )
            catalog.upsert_drive(uuid=marker.uuid, label=marker.label)
            # Remember where it was seen, so its card can offer to check it.
            catalog.set_setting(_drive_path_hint(marker.uuid), str(destination))
            drive_uuid = marker.uuid
            results = execute(
                resolutions,
                LocalDestination(destination),
                catalog,
                apply=True,
                skip_undated=skip_undated,
                progress=progress,
                cancel=cancel,
                drive_uuid=drive_uuid,
            )
        completion = _completion(results, destination)
        completion["drive_label"] = marker.label
        with Catalog(db) as catalog:
            catalog.set_setting(LIBRARY_PATH_HINT, str(destination))
            # The custody nudge, counted rather than assumed: how much of the library really
            # does exist in only one place right now.
            completion["single_copy"] = catalog.single_copy_count()
        return completion

    return target


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


def verify_run(path: Path, db: Path) -> JobTarget:
    """Build a job target that verifies a connected drive's copies against the catalog."""

    def target(progress: ProgressCallback, cancel: threading.Event) -> dict[str, Any]:
        marker = read_marker(path)
        if marker is None:
            raise _not_a_drive(path)
        with Catalog(db) as catalog:
            catalog.upsert_drive(uuid=marker.uuid, label=marker.label)
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
                    # folder. Absent when we have never had a path for it -- in which case the
                    # card states the fact without offering an action it cannot honour.
                    "path": catalog.get_setting(_drive_path_hint(d["uuid"])),
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


# --- event review (used by the Event review screen; merge/split are UI-only) ----------


def plan_resolve(source: Path, db: Path) -> tuple[list[Resolution], dict[Path, dict[str, Any]]]:
    """Plan + dedup a source (no writes), returning resolutions and metadata for clustering."""
    files = discover(source)
    if not files:
        return [], {}
    metadata = read_metadata(files)
    with Catalog(db) as catalog:
        scheme = resolve_scheme(catalog)
        decisions = plan(files, metadata, build_rules(), scheme=scheme)
        index = DedupIndex.from_catalog_rows(catalog.seed_rows(), DEFAULT_PHASH_THRESHOLD)
        resolutions = resolve(decisions, index, catalog_sizes=catalog.known_sizes())
    return resolutions, metadata


def cluster_json(cluster: Any) -> dict[str, Any]:
    """Serialise an EventCandidate for the review UI."""
    centroid = cluster.gps_centroid()
    return {
        "start": cluster.start.isoformat(),
        "end": cluster.end.isoformat(),
        "count": cluster.count,
        "location": list(centroid) if centroid else None,
    }


def review_card_json(card: ReviewCard) -> dict[str, Any]:
    """Serialise one assembled review card (Stage 2d, 13.3b) - a multi-day trip or a standalone
    day-event - for the review UI. ``kind`` ("trip" | "event") is the label the screen shows;
    a standalone-day event keeps using :func:`cluster_json` unchanged, so its identity (a
    signature over member SHA-256s) is untouched by this stage.
    """
    if card.trip is not None:
        return {
            "kind": card.kind,
            "start": card.trip.start_date.isoformat(),
            "end": card.trip.end_date.isoformat(),
            "count": sum(card.trip.days.values()),
            "days": [
                {"date": day.isoformat(), "count": count}
                for day, count in sorted(card.trip.days.items())
            ],
        }
    assert card.event is not None
    return {**cluster_json(card.event), "kind": card.kind}


# --- Takeout rescue report (Rescue report screen) -------------------------------------


def ingest_preview(takeout: Path, destination: Path, db: Path) -> dict[str, Any]:  # noqa: ARG001
    """Dry-run Takeout rescue: the honest report the Rescue screen shows before any run."""
    scan = scan_takeout(takeout)
    files = discover(takeout)
    if not files:
        return {"files": 0, "missing_sidecar": 0}
    metadata = read_metadata(files)
    with Catalog(db) as catalog:
        scheme = resolve_scheme(catalog)
        decisions = plan(files, metadata, build_rules(), takeout=scan.sidecars, scheme=scheme)
        index = DedupIndex.from_catalog_rows(catalog.seed_rows(), DEFAULT_PHASH_THRESHOLD)
        resolutions = resolve(decisions, index, catalog_sizes=catalog.known_sizes())
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
        "missing_sidecar": len(scan.missing_sidecar),
    }


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
        return {"error": "that path could not be read", "roots": fs_roots(), "entries": []}
    if not path.is_dir():
        return {"error": "not a folder", "roots": fs_roots(), "entries": []}
    entries: list[dict[str, str]] = []
    try:
        for child in sorted(path.iterdir(), key=lambda p: p.name.lower()):
            if child.is_dir() and not child.name.startswith("."):
                entries.append({"name": child.name, "path": str(child)})
    except OSError:
        return {"error": "that folder could not be read", "roots": fs_roots(), "entries": []}
    parent = str(path.parent) if path.parent != path else None
    return {"path": str(path), "parent": parent, "roots": fs_roots(), "entries": entries}


def fs_create(path_str: str) -> dict[str, Any]:
    """Create a folder (and parents) - for the "Create it?" action on a new backup destination."""
    path = Path(path_str).expanduser()
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return {"created": False, "error": str(exc)}
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


def library_status(db: Path) -> dict[str, Any]:
    """Honest, catalog-driven totals for the custody strip. Zeros when the catalog is empty."""
    with Catalog(db) as catalog:
        breakdown = _media_breakdown(catalog.media_names())
        total = catalog.count()
        drives = [d for d in catalog.list_drives() if d["file_count"]]
        single_copy = catalog.single_copy_count()
        total_bytes = sum(d["total_size"] or 0 for d in drives)
        # Prefill hints, so no screen asks a user to Browse for a path we already know.
        # Hints only: drive identity is the marker uuid, never a path.
        library_path = catalog.get_setting(LIBRARY_PATH_HINT)
        backup_path = catalog.get_setting(BACKUP_PATH_HINT)
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
        return {"ok": False, "error": "the 'from' folder does not exist."}
    if not target.is_dir():
        return {"ok": False, "error": "the 'to' folder does not exist."}
    if source.resolve() == target.resolve():
        return {"ok": False, "error": "the 'from' and 'to' folders are the same folder."}
    # Preview writes nothing, so an unregistered folder is *reported* as one that will be
    # registered rather than rejected -- the run does the registering.
    src = attach_drive(source, db, write=False)
    tgt = attach_drive(target, db, write=False)
    src_marker, tgt_marker = read_marker(source), read_marker(target)
    if src_marker is not None and tgt_marker is not None and src_marker.uuid == tgt_marker.uuid:
        return {"ok": False, "error": "the 'from' and 'to' drives are the same drive."}
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


def propose_events(path: Path, db: Path) -> dict[str, Any]:
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
        "declines": [decline_message(decline) for decline in review.declines],
    }


def _resolve_migration_routes(
    catalog: Catalog, drive_uuid: str, path: Path
) -> tuple[dict[str, str], dict[str, str]]:
    """Resolve ambiguous labels the same way `truestill migrate-layout` does.

    A `Camera`-labelled row is ambiguous by construction (`label_routes`'s own docstring: it is
    the device rule's default label *and* a possible `Software` value) -- migrate and organize
    are the same placement decision, so they must route through the same seam, never a second
    guess. Without this, `plan_migration`'s conservative default (unmapped -> side bin) fires for
    every `Camera` row, because nothing else in this module ever resolved the ambiguity - the app
    has no `--by-device` equivalent, so re-derivation always runs with the plain device rule.
    """
    routes = label_routes(catalog, drive_uuid)
    rules_by_sha = rederive_rules(catalog, drive_uuid, path, routes)
    decided = {r.label: (ROUTE_SIDE_BIN if r.needs_decision else r.route) for r in routes}
    return decided, rules_by_sha


def migration_preview(path: Path, db: Path) -> dict[str, Any]:
    """Preview relocating a connected drive's files to the current template (moves nothing)."""
    marker = read_marker(path)
    if marker is None:
        return {"ok": False, **_drive_correction(path)}
    with Catalog(db) as catalog:
        scheme = resolve_scheme(catalog)
        routes, rules_by_sha = _resolve_migration_routes(catalog, marker.uuid, path)
        outcome = run_migration(
            catalog,
            LocalDestination(path),
            marker.uuid,
            scheme,
            apply=False,
            routes=routes,
            rules_by_sha=rules_by_sha,
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
        "pending_drives": pending,
    }


def migration_apply(
    path: Path,
    db: Path,
    named_events: Sequence[dict[str, Any]] | None = None,
    named_trips: Sequence[dict[str, Any]] | None = None,
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
            routes, rules_by_sha = _resolve_migration_routes(catalog, marker.uuid, path)
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
            trips = []
            for event in named_events or ():
                relative = catalog.sample_relative_for_event(event["event_id"], marker.uuid)
                if relative is None:
                    continue  # nothing of this event landed on this drive -- nothing to reveal
                trips.append(
                    {
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
                trips.append(
                    {
                        "name": trip["name"],
                        "start": trip["start"],
                        "end": trip["end"],
                        "path": str(PurePosixPath(relative).parent.parent),
                    }
                )
        result: dict[str, Any] = {
            "label": marker.label,
            "migrated": outcome.migrated,
            "resumed": outcome.resumed,
        }
        if trips:
            result["trips"] = trips
        return result

    return target
