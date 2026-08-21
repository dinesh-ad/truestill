"""Organize: inventory, preview, run, mode/sidebar prefs, filesystem relationship."""

from __future__ import annotations

import threading
import uuid
from collections import Counter
from pathlib import Path
from typing import Any, Literal, NotRequired, TypedDict, cast

from truestill_core.catalog import Catalog
from truestill_core.catalog_session import open_catalog
from truestill_core.categorize import build_rules
from truestill_core.date_provenance import format_offset
from truestill_core.dedup import DedupIndex
from truestill_core.destinations import LocalDestination
from truestill_core.destinations.base import DestinationError
from truestill_core.drive import (
    DriveGhostError,
    DriveMarker,
    DriveReach,
    create_marker,
    drive_path_hint,
    ghost_drive_at,
    ghost_drive_refusal,
    reach_of,
    read_marker,
)
from truestill_core.duplicate_explain import explain_duplicate, split_by_origin
from truestill_core.event_review import EventDecision, commit, propose
from truestill_core.exif import read_metadata
from truestill_core.hash_cache import HashCache
from truestill_core.hashing import DEFAULT_PHASH_THRESHOLD, HEIF_AVAILABLE, HEIF_EXTENSIONS
from truestill_core.insights import capture_span, duplicate_bytes, largest_files, sizes_for
from truestill_core.layout import LayoutScheme
from truestill_core.layout_settings import pin_existing_layout, resolve_scheme
from truestill_core.models import (
    ActionResult,
    ActionStatus,
    DuplicateOrigin,
    Resolution,
    date_quality,
    format_inferred_local_shift_line,
    inferred_local_shifts,
    partition_for_report,
    status_label,
    unreadable_label,
)
from truestill_core.organizer import (
    Relocation,
    SourceScan,
    discover,
    execute,
    heavy_days_for_organize,
    inventory_source,
    media_kind,
    plan,
    preflight_for_run,
    resolve,
    scan_source,
    skipped_extension_counts,
    write_candidates,
)
from truestill_core.progress import ProgressCallback
from truestill_core.thumbnails import upright_size

from truestill_app.jobs import JobTarget
from truestill_app.service.drives import LIBRARY_PATH_HINT
from truestill_app.service.leftover_cleanup import (
    LeftInSource,
    LeftoverEmptyFolders,
    cleanup_summary_from_results,
    left_in_source_from_results,
)
from truestill_app.service.media_support import media_breakdown
from truestill_app.service.path_probe import nearest_device, unreadable_message
from truestill_app.service.takeout import InferredLocalShiftPayload

ORGANIZE_MODE_KEY = "ui.organize.mode"
ORGANIZE_MODES = frozenset({"copy", "move", "inplace"})
SIDEBAR_COLLAPSED_KEY = "ui.sidebar.collapsed"
TEXT_SIZE_KEY = "ui.text.size"
#: Named steps rather than a number. A free px field invites a value that breaks the layout, and
#: the answer to "how big" already belongs to the browser - this only nudges it. Ordered
#: smallest-first because the stylesheet and the radio group read in the same order.
TEXT_SIZES = ("small", "medium", "large")
DEFAULT_TEXT_SIZE = "medium"


#: How many matches a payload carries. The rest are counted, never dropped silently (F46 /
#: §9): every payload that truncates also states the total, so the API cannot imply a short
#: list is the whole story any more than the screen can. 200 matches the move-preview limit -
#: enough to scan, small enough that a 40,000-file run does not ship a megabyte of JSON.
DUPLICATE_SAMPLE_LIMIT = 200

#: Same idea for unreadable sources. Separate constant rather than a shared one: these are
#: different lists with different failure shapes, and tying them together would mean tuning one
#: could only be done by changing the other.
UNREADABLE_SAMPLE_LIMIT = 200

#: How many photos the result GRID can carry, and much smaller than its neighbours above on
#: purpose. Those are lists a person scans for a name; this one is fetched, decoded and drawn -
#: every entry is an HTTP request and ~23 ms of server-side decode the first time it is seen.
#: 48 is a screenful and a scroll at every panel width the layout produces, and past that the
#: honest answer is a number rather than a mile of scrollbar. Seeing the whole library is a
#: different feature with different machinery (`BACKLOG.md` (abk)), not a bigger constant here.
GRID_SAMPLE_LIMIT = 48


class OrganizedTile(TypedDict):
    """One photo the run put into the library, addressed by content for `/api/thumb`.

    ``w``/``h`` are the photograph's shape **as it is seen**, not as it is stored: EXIF
    orientation is already applied, so they agree with the thumbnail `/api/thumb` returns. They
    are `NotRequired` because exiftool cannot read every file, and a layout must cope with a
    photograph whose shape is unknown rather than assume one.
    """

    sha256: str
    name: str
    w: NotRequired[int]
    h: NotRequired[int]


class OrganizedSample(TypedDict):
    """Tiles plus the count they were taken from, so truncation is never silent.

    ``total`` counts **photos**, not organized files: a run of 40 videos organizes 40 things and
    has nothing to show, and a grid saying "and 40 more" over an empty space would be a lie about
    what is missing. Videos and audio are counted in the tally above it, where they belong.
    """

    total: int
    shown: list[OrganizedTile]


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
    #: The split by where the twin is, over **every** match rather than over ``shown``. The
    #: tile renders a number long before anyone opens the list, and a split taken from the
    #: capped sample would read `DUPLICATE_SAMPLE_LIMIT` on a large library and look plausible.
    already_in_library: int
    within_this_batch: int
    unclassified: int


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
    split = split_by_origin(m for _, m in matched if m is not None)
    return {
        "total": len(matched),
        "shown": shown,
        "already_in_library": split.already_in_library,
        "within_this_batch": split.within_this_batch,
        "unclassified": split.unclassified,
    }


class MatchedDrivePayload(TypedDict):
    """One drive that physically holds part of what this preview matched."""

    label: str
    #: Distinct CONTENT held here, so two source files with the same bytes count once.
    files: int
    #: ``connected`` / ``offline`` / ``unknown``, never folded to a boolean: a drive that is not
    #: plugged in is not a drive that is gone, and a drive truestill has never seen on this
    #: computer is neither.
    reach: str
    #: Only for a CONNECTED drive. A remembered path for a drive that is not there is not a
    #: place anything can act on, and offering it would invite exactly that.
    path: str | None


class MatchedDrivesPayload(TypedDict):
    """Where the matched files already are - the fact a pointer at the library needs.

    **`matched_path` could never answer this.** It is `files.source_path`, where content was
    first read from and deliberately never repointed, so it names the user's old folder. Only
    `file_copies`, keyed by ``(sha256, drive_uuid)``, knows where a copy sits.

    Two drives yield two entries. Collapsing to one would answer the two-destination case -
    copied into X, later compared against Y - with a confident wrong drive.
    """

    #: Matches whose twin is in the catalog. `unplaced + sum(drives.files)` need not equal this
    #: when content sits on two drives, which is why both are stated rather than one derived.
    total: int
    drives: list[MatchedDrivePayload]
    #: Matches the catalog knows but has no copy row for - the orphan state a CLI organize used
    #: to leave. Counted rather than dropped, so a zero here is a fact and not an omission.
    unplaced: int


class SizedFilePayload(TypedDict):
    name: str
    bytes: int


class LargestFilesPayload(TypedDict):
    """`{total, shown}` - the cap never changes the count."""

    total: int
    shown: list[SizedFilePayload]


class DuplicateBytesPayload(TypedDict):
    """Reclaimable and near bytes stay apart: a kept near-duplicate saves nothing."""

    reclaimable: int
    near: int


class CaptureSpanPayload(TypedDict):
    oldest: str
    newest: str


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
    #: What a run with these options will actually organize - the one number the
    #: tally card and the confirm control both render. `(abl)`, `(acx)`.
    will_organize: int
    undated: int
    sentinel_rejected: int
    future_rejected: int
    suspect_default: int
    inferred_local_shifts: list[InferredLocalShiftPayload]
    folders: dict[str, int]
    heic_perceptual_skipped: NotRequired[int]
    #: Panel facts. Supplementary by construction - the panel is not rendered on a narrow
    #: window, so nothing here may be needed to finish the task.
    largest_files: LargestFilesPayload
    duplicate_bytes: DuplicateBytesPayload
    capture_span: CaptureSpanPayload | None


def _summarize(resolutions: list[Resolution], *, skip_undated: bool = False) -> OrganizeDedupCore:
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
    facts = _library_facts(resolutions, uploads)
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
        # THE NUMBER THE SCREEN PROMISES, computed once in core. `(abl)`: the tally card rendered
        # `new_unique` under the words "will be organized" while the confirm control rendered
        # `new_unique + near_dup`, so the card and the button disagreed by `near_dup` on any
        # folder with a look-alike. `(acx)`: with `skip_undated` the run takes fewer still, and
        # this endpoint did not even accept the flag. Both surfaces render THIS field.
        "will_organize": buckets.will_organize(skip_undated=skip_undated),
        # LIBRARY FACTS for the panel. `capture_span` and `duplicate_bytes` reached only a
        # finished run; `largest_files` reached only the CLI. One `stat` pass serves all three,
        # measured in PERFORMANCE.md at ~0.3 s per 2,064 files against ~231 s for exiftool on
        # the same preview.
        "largest_files": facts[0],
        "duplicate_bytes": facts[1],
        "capture_span": facts[2],
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


_LARGEST_SHOWN = 5


def _library_facts(
    resolutions: list[Resolution], uploads: list[Resolution]
) -> tuple[LargestFilesPayload, DuplicateBytesPayload, CaptureSpanPayload | None]:
    """Panel facts: biggest files, duplicate bytes, and the capture span.

    `capture_span` is over what would be ORGANIZED, matching the run's own reading - a skipped
    duplicate must not widen the range the library covers.
    """
    sizes = sizes_for(resolutions)
    counted = duplicate_bytes(resolutions, sizes)
    largest = largest_files(sizes, limit=_LARGEST_SHOWN)
    span = capture_span(uploads)
    biggest: LargestFilesPayload = {
        "total": largest.total,
        "shown": [{"name": f.path.name, "bytes": f.size} for f in largest.shown],
    }
    # Reclaimable and near bytes stay separate: truestill KEEPS a near-duplicate, so those
    # bytes are never saved and `DuplicateBytes` refuses to imply they are.
    bytes_split: DuplicateBytesPayload = {
        "reclaimable": counted.reclaimable_bytes,
        "near": counted.near_bytes,
    }
    window: CaptureSpanPayload | None = (
        {"oldest": span.oldest.isoformat(), "newest": span.newest.isoformat()} if span else None
    )
    return biggest, bytes_split, window


def _matched_drives(catalog: Catalog, resolutions: list[Resolution]) -> MatchedDrivesPayload:
    """Where the catalog-matched files physically live. Two queries, plus one marker read a drive.

    **Only ``CATALOG`` matches are looked up.** A twin found earlier in this same batch is not in
    the library yet, so attributing it to a drive would claim a copy that is not there.

    **Everything here counts distinct CONTENT, not matched files**, and the payload says so. Two
    source files with the same bytes are one copy on the drive, and reporting two would say the
    library holds more than it does. The *file* counts a person reads come from
    ``exact_dup_matches``; this answers only "where is it".

    **Complexity:** ``O(m log n)`` index seeks over `file_copies` for *m* distinct hashes, twice -
    once for the per-drive counts and once for which hashes are placed at all. Both ride the
    primary key's own index (`Catalog.drives_holding`), so no index is added. Then one
    `read_marker` per drive NAMED, which is a handful of paths rather than a per-file cost.
    """
    shas = list(
        dict.fromkeys(
            r.hashes.sha256
            for r in resolutions
            if r.exact_duplicate is not None
            and r.exact_duplicate.origin == DuplicateOrigin.CATALOG
            and r.hashes.sha256 is not None
        )
    )
    if not shas:
        return {"total": 0, "drives": [], "unplaced": 0}
    drives: list[MatchedDrivePayload] = []
    for holding in catalog.drives_holding(shas):
        reach = reach_of(catalog, holding.drive_uuid)
        hint = catalog.get_setting(drive_path_hint(holding.drive_uuid))
        drives.append(
            {
                "label": holding.label,
                "files": holding.files,
                "reach": reach.value,
                # A remembered path for a drive that is not there is not a place anything can
                # act on, and offering it would invite exactly that.
                "path": hint if reach is DriveReach.CONNECTED else None,
            }
        )
    return {
        "total": len(shas),
        "drives": drives,
        # The orphan state a CLI organize used to leave: a `files` row with no `file_copies`
        # row. Counted rather than dropped - silence would make the parts stop summing.
        "unplaced": len(shas) - len(catalog.placed_shas(shas)),
    }


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
    """Skipped files for the UI. **A thin alias, deliberately not a second implementation.**

    This was a verbatim copy of `organizer.skipped_extension_counts` until 2026-08-04, and a
    group added to one would have left the other silently short - the drift that
    `test_layout_scheme.ALL_RULES` and `check_product_name.SUBCOMMANDS` each produced once
    already. Kept as a named function because the payload builder reads better for it, and
    because deleting the name would be a change to this module's shape rather than to its
    behaviour.
    """
    return skipped_extension_counts(scan)


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
    #: Folders the walk could not list. `SourceInventory` has carried these all along and this
    #: payload dropped them, so "Look inside" could answer *Nothing to organize here* about a
    #: folder it had failed to open - the same conflation `(aac)` closed on the dedup tier.
    #: No unreadable *files* at this tier: a walk never opens one, so none is known.
    unreadable_folders: list[str]


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
        "unreadable_folders": [str(folder) for folder in inv.unreadable_dirs],
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
    with open_catalog(db) as catalog:
        saved = _normalize_organize_mode(catalog.get_setting(ORGANIZE_MODE_KEY))
    return {"mode": saved, "modes": sorted(ORGANIZE_MODES)}


def set_organize_mode(mode: object, db: Path) -> SetOrganizeModeResult:
    saved = _normalize_organize_mode(mode)
    with open_catalog(db) as catalog:
        catalog.set_setting(ORGANIZE_MODE_KEY, saved)
    return {"ok": True, "mode": saved}


def _normalize_sidebar_collapsed(value: object) -> bool:
    """True only for an explicit collapsed signal; anything else expands."""
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().lower()
    return text in {"1", "true", "yes", "collapsed"}


def sidebar_state(db: Path) -> SidebarState:
    with open_catalog(db) as catalog:
        raw = catalog.get_setting(SIDEBAR_COLLAPSED_KEY)
    return {"collapsed": _normalize_sidebar_collapsed(raw)}


def set_sidebar_collapsed(collapsed: object, db: Path) -> SetSidebarCollapsedResult:
    saved = _normalize_sidebar_collapsed(collapsed)
    with open_catalog(db) as catalog:
        catalog.set_setting(SIDEBAR_COLLAPSED_KEY, "true" if saved else "false")
    return {"ok": True, "collapsed": saved}


class TextSizeState(TypedDict):
    size: str


class SetTextSizeResult(TypedDict):
    ok: Literal[True]
    size: str


def _normalize_text_size(value: object) -> str:
    """Anything unrecognised is ``medium``, which declares no root size at all.

    Total by construction, on both directions of the wire. A stored value is user data by the
    time it is read back - a hand-edited catalog, a downgrade, a step that no longer exists -
    and an unknown one written onto the root element would be an invalid ``font-size`` the
    browser drops silently, leaving a page that looks like the setting was ignored.
    """
    text = str(value if isinstance(value, str) else "").strip().lower()
    return text if text in TEXT_SIZES else DEFAULT_TEXT_SIZE


def text_size_state(db: Path) -> TextSizeState:
    with open_catalog(db) as catalog:
        raw = catalog.get_setting(TEXT_SIZE_KEY)
    return {"size": _normalize_text_size(raw)}


def set_text_size(size: object, db: Path) -> SetTextSizeResult:
    saved = _normalize_text_size(size)
    with open_catalog(db) as catalog:
        catalog.set_setting(TEXT_SIZE_KEY, saved)
    return {"ok": True, "size": saved}


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
    #: WHERE the matched files already are. `matched_path` names where content was first read
    #: from and never where it now lives, so nothing else in this payload can answer it.
    matched_drives: MatchedDrivesPayload
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
    skip_undated: bool = False,
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
    with open_catalog(db) as catalog, HashCache.beside(db) as cache:
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
        # Inside the open catalog, because it asks the catalog. Two index seeks over the
        # matched hashes; the preview has just hashed every file, so this is not the cost.
        matched_drives = _matched_drives(catalog, resolutions)
    core = _summarize(resolutions, skip_undated=skip_undated)
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
            "matched_drives": matched_drives,
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
    skip_undated: bool = False,
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
            skip_undated=skip_undated,
            refresh_metadata=refresh_metadata,
            mode=mode,
        )

    return target


def _approve_registration(destination: Path, catalog: Catalog) -> None:
    """Settle whether this destination MAY become a drive. Writes nothing. `(aek)`

    **Refuses to mint a SECOND identity over a known drive's ghost.** An unmounted mountpoint is
    an ordinary empty directory: it has no marker, and absence is exactly what made both
    surfaces register a new drive for a library the catalog already knows - while the files went
    onto this computer's disk. The app registers here as well as the CLI, so a refusal on one
    surface only is the drift §4 names; the discriminating rule lives in core and both call it.

    **The half that stays early**, matching `cli._approve_registration`: this is the answer a user
    needs before a full hashing pass, while the marker WRITE waits for the space check.

    **Complexity: O(drives)** - one settings read per registered drive, a handful.
    """
    if read_marker(destination) is not None:
        return
    drives = [(str(d["uuid"]), str(d["label"])) for d in catalog.list_drives()]
    ghost = ghost_drive_at(destination, catalog, drives)
    if ghost is not None:
        raise DriveGhostError(ghost_drive_refusal(ghost))


def _scope_to_marker(destination: Path, catalog: Catalog) -> dict[str, str]:
    """What this destination already holds, for `(aei)`'s per-destination dedup.

    ⚠ **Read from the MARKER, not from registration**, which is what lets `(aek)` move the marker
    write behind the space check without restoring `(aei)`. A destination that has an identity has
    it before anything here runs; one that does not provably holds no recorded copies, and `{}` is
    exactly what a freshly minted uuid would have returned.

    The app always writes to a local drive - there is no rclone path here - so
    `organizer._scope_to_destination`'s catalog-global `None` case never applies. Returning `None`
    here would make organize dedupe against the whole catalog and copy nothing onto a second
    drive, which is `(aei)` itself.
    """
    existing = read_marker(destination)
    if existing is None:
        return {}
    return {str(r["sha256"]): str(r["relative"]) for r in catalog.copies_on_drive(existing.uuid)}


def _reapply_named_events(
    resolutions: list[Resolution],
    metadata: dict[Path, dict[str, Any]],
    catalog: Catalog,
    scheme: LayoutScheme,
) -> list[Resolution]:
    """Re-apply *already-named* trips whose cluster recurs in this source.

    So a fresh import lands its camera files under the same event folder, matched by signature.
    Only saved events are applied - unnamed clusters are left untouched, never auto-skipped, so
    they stay reviewable in the Trips screen later.
    """
    saved = [
        EventDecision(cluster, None)
        for cluster in propose(resolutions, metadata)
        if catalog.event_by_signature(cluster.signature) is not None
    ]
    if not saved:
        return resolutions
    return commit(resolutions, saved, catalog, scheme=scheme).resolutions


def _refuse_if_it_cannot_hold(resolutions: list[Resolution], destination: Path) -> None:
    """Stop before registering a destination that cannot hold the run. `(aek)`

    The marker write is the first thing this product puts on a new drive, so on a full disk it
    failed before the run reached the sentence that explains a full disk - a sentence the product
    already had. Read through `_destination_limit`, which reads `preflight_for_run`, which is the
    same answer `execute` refuses on: a third reading of one function, never a third check.

    :raises DestinationError: the destination cannot hold what this run would write.
    """
    limit = _destination_limit(resolutions, destination)
    if limit is not None:
        raise DestinationError(limit["detail"])


def _register_destination(catalog: Catalog, destination: Path) -> DriveMarker:
    """Give the destination a drive identity and remember where it was seen. Returns the marker.

    ⚠ **Still before any COPY**, which is the older constraint - an identity minted afterwards
    leaves the run's own files unattached.

    ⚠ **But AFTER the space check since `(aek)`, and `(aei)` is not restored by that.** This used
    to run before `resolve`, because `(aei)` made the destination's identity an INPUT to the dedup
    decision rather than only a label for recording. What that requires is the *identity*, not the
    *write*: a destination that already has a marker has it before anything here runs, and one
    that does not scopes to `{}` either way - a freshly minted uuid holds no recorded copies, and
    neither does a folder with no marker at all. So the decision stays early and only the write
    moves. Pinned by `test_dedup_scope_survives_the_registration_move.py`.

    :raises DriveWriteError: the drive would not accept its marker.
    """
    marker = read_marker(destination) or create_marker(
        destination, label=destination.name or "Library"
    )
    catalog.upsert_drive(uuid=marker.uuid, label=marker.label)
    # Remember where it was seen, so its card can offer to check it.
    catalog.set_setting(drive_path_hint(marker.uuid), str(destination))
    return marker


def _open_organize_run(
    catalog: Catalog,
    drive_uuid: str,
    resolutions: list[Resolution],
    on_destination: dict[str, str],
) -> None:
    """Record that this organize has STARTED, before the first byte. `(aem)`.

    ⚠ After the process dies the intended total cannot be reconstructed: a restart's own total
    correctly excludes what already landed, so the number exists only in this row.

    `intended_total` is what the drive will **hold** when the run finishes - current holdings plus
    what this run adds - not what it writes. The write count differs across a restart; the target
    does not. Both halves are already in hand and cost nothing.
    """
    catalog.start_organize_run(
        drive_uuid=drive_uuid,
        run_id=uuid.uuid4().hex,
        intended_total=len(on_destination) + len(write_candidates(resolutions, skip_undated=False)),
    )


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
        with open_catalog(db) as catalog, HashCache.beside(db) as cache:
            metadata = read_metadata(files, progress=progress, cache=cache, force=refresh_metadata)
            pin_existing_layout(catalog)
            scheme = resolve_scheme(catalog)
            rules = build_rules()
            heavy = heavy_days_for_organize(catalog, files, metadata, rules)
            decisions = plan(files, metadata, rules, scheme=scheme, heavy_days=heavy)
            # Settle whether this folder MAY become a drive, before the expensive pass. Writes
            # nothing; the marker itself waits for the space check below. `(aek)`
            _approve_registration(effective_destination, catalog)

            index = DedupIndex.from_catalog_rows(catalog.seed_rows(), DEFAULT_PHASH_THRESHOLD)
            on_destination = _scope_to_marker(effective_destination, catalog)
            resolutions = resolve(
                decisions,
                index,
                catalog_sizes=catalog.known_sizes(),
                progress=progress,
                cancel=cancel,
                cache=cache,
                on_destination=on_destination,
            )
            _refuse_if_it_cannot_hold(resolutions, effective_destination)
            marker = _register_destination(catalog, effective_destination)
            drive_uuid = marker.uuid
            _open_organize_run(catalog, drive_uuid, resolutions, on_destination)
            resolutions = _reapply_named_events(resolutions, metadata, catalog, scheme)
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
            # An OPTIMISATION, never a correctness requirement: a crash between the last file and
            # this line leaves the row open, and `unfinished_organize_run` derives the answer from
            # what the drive holds, so that case still reads as complete. `(aem)`.
            catalog.finish_organize_run(drive_uuid)
            if relocation is not None:
                moved = sum(1 for r in results if r.status is ActionStatus.MOVED_IN_PLACE)
                if moved:
                    catalog.finish_inplace_run(relocation.run_id)
                else:
                    catalog.discard_inplace_run(relocation.run_id)
        base = _completion(results, effective_destination, metadata)
        leftover: LeftoverEmptyFolders | None = None
        # The two halves of what a move left behind, gated together on the mode. A copy leaves
        # every original where it is by definition, so neither is news there.
        left_behind: LeftInSource | None = None
        if chosen_mode in {"move", "inplace"}:
            leftover = cleanup_summary_from_results(results, source)
            left_behind = left_in_source_from_results(results, source)
        with open_catalog(db) as catalog:
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
        if left_behind is not None:
            done["left_in_source"] = left_behind
        return done

    return target


class CompletionBase(TypedDict):
    """The keys :func:`_completion` itself returns (organize-only).

    ⚠ **THIS SAID "17 KEYS" UNTIL 2026-08-20 AND THERE WERE 19**, because `duplicate_matches` and
    `organized_sample` were added afterwards and **no test asserts the count**. The stale number
    was repeated in four places and became a recorded constraint: `(adx)` gap 1 scoped its own
    work around *"a 17-key payload pinned by two e2e tests"*, and `(aem)` was planned around the
    same obstacle before it was priced.

    **Priced, it is not an obstacle at all.** `test_server.py` asserts `set(summary) >= {...}` - a
    **superset** check that has already silently absorbed three additions. The e2e files that
    touch this payload **author their own partial summaries** (one passes 15 of 19) and assert on
    rendered text; none reads the server payload or its key set. `app.js` reads named fields, the
    React island types it `Record[str, unknown]` "opaque here on purpose", and the cancel path
    already ships a 20th key through the same renderer.

    **The count is deliberately not restated here.** A number that can drift by two while four
    documents repeat it is a number that wants a guard or no mention; the class is the truth.
    `ENGINEERING_STANDARD.md` §4's fifty-sixth member, in the direction of a *constraint* inherited
    as fact rather than a *rule* applied unevenly.
    """

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
    #: The photos this run put into the library, for the result grid. Capped; see
    #: `GRID_SAMPLE_LIMIT`. Present on every run, empty-shown when the run organized no photos.
    organized_sample: OrganizedSample


class OrganizeDoneSummary(CompletionBase):
    """Organize job summary after :func:`organize_run` enriches :class:`CompletionBase`.

    ``leftover_empty_folders`` appears only for move/inplace runs that left empty folders, and
    ``left_in_source`` only for move/inplace runs that left files behind - the two halves of
    what the move left, and absent rather than zero when there is nothing to say.
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
    left_in_source: NotRequired[LeftInSource]
    elapsed_seconds: NotRequired[float]


def _tile(result: ActionResult, metadata: dict[Path, dict[str, Any]] | None) -> OrganizedTile:
    """One grid entry. ``w``/``h`` are omitted rather than guessed when the shape is unknown."""
    tile: OrganizedTile = {
        "sha256": cast("str", result.sha256),
        "name": result.resolution.decision.source.name,
    }
    shape = _tile_shape(metadata, result.resolution.decision.source)
    if shape:
        tile["w"], tile["h"] = shape["w"], shape["h"]
    return tile


def _tile_shape(metadata: dict[Path, dict[str, Any]] | None, source: Path) -> dict[str, int]:
    """``{"w": ..., "h": ...}`` as the photograph is SEEN, or ``{}`` when it cannot be read.

    **Free.** `read_metadata` already ran for this file and already asked for `ImageWidth`,
    `ImageHeight` and `Orientation`; this reads three keys out of a dict that is still in scope.
    No decode, no second pass, and a warm re-run serves them from `HashCache` with no exiftool
    call at all.

    ⚠ **The orientation swap is the whole point of the function.** `ImageWidth`/`ImageHeight` are
    the STORED dimensions, and `thumbnails.render` applies `exif_transpose`, so on the 31.7% of a
    real corpus that carries a transposing tag the stored pair describes a shape the thumbnail is
    not. `upright_size` is imported from `thumbnails` rather than reimplemented here so the
    payload and the pixels cannot drift apart - one rule, two callers.

    Absent rather than guessed when exiftool read nothing: a layout can lay out an unknown shape
    honestly, and cannot recover from a confident wrong one.
    """
    tags = (metadata or {}).get(source, {})
    try:
        stored_w, stored_h = int(tags["ImageWidth"]), int(tags["ImageHeight"])
    except (KeyError, TypeError, ValueError):
        return {}
    if stored_w <= 0 or stored_h <= 0:
        return {}
    orientation = tags.get("Orientation")
    width, height = upright_size(
        stored_w, stored_h, orientation if isinstance(orientation, int) else None
    )
    return {"w": width, "h": height}


def _completion(
    results: list[ActionResult],
    destination: Path,
    metadata: dict[Path, dict[str, Any]] | None = None,
) -> CompletionBase:
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
    # Photos only, and only those the run established a content id for. `ActionResult.sha256`
    # rather than `resolution.hashes.sha256`: the second is unset for a unique-size file the
    # scan's pre-filter skipped hashing, which is HALF a typical run, and reading it here drew
    # two tiles for four organized photos. A tile with no id is excluded from `total` as well as
    # from the list - counting one would make "and N more" promise something unaddressable.
    photos = [
        r
        for r in organized
        if media_kind(r.resolution.decision.source.name) == "photo" and r.sha256 is not None
    ]
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
        # Run order, not "the best 48": any other ordering would be a judgement about which of a
        # user's photos matter, made with no evidence, on the screen that exists to show them
        # what they have. First-seen is the only order the run actually knows.
        "organized_sample": {
            "total": len(photos),
            "shown": [_tile(r, metadata) for r in photos[:GRID_SAMPLE_LIMIT]],
        },
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
