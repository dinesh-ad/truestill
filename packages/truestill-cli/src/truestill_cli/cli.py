"""Command-line entry point.

Defaults are inert: with no ``--apply`` the tool analyses the source, resolves duplicates
and prints what it *would* organize, writing nothing to the destination or the catalog.
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
import threading
import time
import uuid
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from contextlib import AbstractContextManager
from dataclasses import replace as _dataclass_replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from truestill_core.app_paths import (
    LEGACY_CATALOG_PATH,
    cache_path_for,
    default_catalog_path,
    standard_catalog_path,
)
from truestill_core.archive_extract import extract_archive_set
from truestill_core.archive_ingest import archives_at, precheck_archives
from truestill_core.catalog import Catalog
from truestill_core.catalog_busy import CATALOG_BUSY_MESSAGE, is_catalog_busy
from truestill_core.catalog_move import CatalogMoveOutcome, move_catalog_to_standard
from truestill_core.catalog_session import open_catalog
from truestill_core.catalog_startup import (
    CatalogPresence,
    db_flag_explicit,
    format_startup_lines,
    inspect_catalog,
)
from truestill_core.categorize import build_rules
from truestill_core.cleanup import (
    CleanupPlan,
    Tier,
    emptied_directories,
    plan_cleanup,
    run_cleanup,
    trash_backend,
)
from truestill_core.decisions import (
    PROBLEM_OUTCOMES,
    Decisions,
    DriveSave,
    RestoreReport,
    SaveOutcome,
    apply_documents,
    gather_decisions,
    merge_onto_drive,
    notice_for,
    read_decisions,
    would_lose,
    write_decisions,
)
from truestill_core.dedup import DedupIndex
from truestill_core.destinations import Destination, LocalDestination, RcloneDestination
from truestill_core.destinations.base import DestinationError
from truestill_core.drive import (
    MARKER_NAME,
    CustodyFreshness,
    DriveGhostError,
    DriveMarker,
    DriveReach,
    create_marker,
    custody_freshness,
    drive_path_hint,
    drive_reach,
    drives_without_a_known_location,
    existing_marker_path,
    ghost_drive_at,
    ghost_drive_refusal,
    locate_drive,
    needs_marker_upgrade,
    path_is_usable_dir,
    reach_of,
    read_marker,
    upgrade_marker,
)
from truestill_core.drive_adoption import (
    AdoptionOffer,
    AdoptionVerdict,
    RecordedDrive,
    inspect_root,
    recorded_drive,
)
from truestill_core.duplicate_explain import describe_split, origin_phrase, split_by_origin
from truestill_core.exif import ExiftoolMissingError, read_metadata
from truestill_core.hash_cache import HashCache
from truestill_core.hashing import (
    DEFAULT_PHASH_THRESHOLD,
    HEIF_AVAILABLE,
    HEIF_EXTENSIONS,
    sha256_file,
)
from truestill_core.insights import (
    capture_span,
    capture_years,
    duplicate_bytes,
    forecast_exact_duplicate_read,
    forecast_lookalike_cost,
    largest_files,
    sizes_for,
)
from truestill_core.layout import (
    DEFAULT_PRESET,
    DEFAULT_TEMPLATE_STRING,
    LAYOUT_EVENT_TEMPLATE_KEY,
    LAYOUT_TEMPLATE_KEY,
    PRESETS,
    LayoutScheme,
    LayoutTemplate,
    Placement,
    TemplateError,
    parse_timeline_template,
    preview_scheme,
    resolve_template,
)
from truestill_core.layout_settings import pin_existing_layout, resolve_scheme
from truestill_core.left_behind import (
    describe_left_behind,
    files_left_in_source,
    will_remain_line,
)
from truestill_core.migrate import (
    ROUTE_SIDE_BIN,
    LabelRoute,
    label_routes,
    plan_migration,
    rederive_rules,
    run_migration,
    undo_migration,
)
from truestill_core.models import (
    ActionResult,
    ActionStatus,
    DateSource,
    Decision,
    DuplicateMatch,
    Event,
    Resolution,
    UnreadableReason,
    date_quality,
    format_inferred_local_shift_line,
    inferred_local_shifts,
    partition_for_report,
    status_label,
    unreadable_label,
)
from truestill_core.organizer import (
    Relocation,
    SourceInventory,
    SourceScan,
    execute,
    heavy_days_for_organize,
    inventory_from_scan,
    plan,
    preflight_for_run,
    resolve,
    scan_source,
    sizes_of_media,
)
from truestill_core.progress import Progress, ProgressCallback
from truestill_core.reclaim import ReclaimPlan, plan_reclaim, run_reclaim
from truestill_core.rescan import RescanReport, reconcile
from truestill_core.scan import DEFAULT_WORKERS
from truestill_core.source_repoint import RepointPlan, plan_repoint
from truestill_core.takeout import (
    IngestContext,
    MetadataWrite,
    TakeoutScan,
    TakeoutSidecar,
    scan_takeout,
)
from truestill_core.undo import UndoError, plan_undo, run_undo
from truestill_core.verify import CopyStatus, CopyToVerify, verify_copies

from truestill_cli import __version__
from truestill_cli.events_review import Prompt, album_prompt, run_event_stage

_SEPARATOR = "=" * 100
_NON_INTERACTIVE_CONFIRM = (
    "error: interactive confirmation is required; this operation cannot run non-interactively."
)

#: Said once, on the run that pins an existing library's layout. It states what was recorded
#: and how to change it, because a settings write the user did not ask for must never be silent.
_PINNED_NOTICE = (
    "Note: this library already contains organized files but had no recorded layout. "
    f"Truestill recorded the current default (`{DEFAULT_PRESET.key}`) as this library's layout "
    "so a future default change cannot silently reshape new files. Run `truestill config` to "
    "review the layout and available presets; after choosing another, preview "
    "`truestill migrate-layout` before moving existing files."
)
_STATUS_PREVIEW = 20  # how many single-copy files `truestill status` lists before eliding

#: Exit code for "another process holds the catalog; nothing to fix, try again shortly".
#:
#: Its own code rather than `1` or `2`, because a script's only reason to read one is to decide
#: what to do next, and this is the single case where the answer is *retry*. `2` is a usage or
#: validation error, which never becomes valid by waiting; `1` is this CLI's "the run finished
#: and something is wrong with the library", and the run did not finish. The precedent is how
#: the codes here are already allocated -- `3` a missing exiftool, `4` an unusable destination
#: -- one per failure family that a caller would act on differently.
CATALOG_BUSY_EXIT = 5


def _parse_tz(value: str) -> timedelta:
    """Parse a ``±HH:MM`` timezone offset into a timedelta."""
    match = re.fullmatch(r"([+-])(\d{2}):?(\d{2})", value.strip())
    if match is None:
        message = f"expected a ±HH:MM offset, got {value!r}"
        raise argparse.ArgumentTypeError(message)
    sign, hours, minutes = match.group(1), int(match.group(2)), int(match.group(3))
    delta = timedelta(hours=hours, minutes=minutes)
    return -delta if sign == "-" else delta


def _typed_confirmation(prompt: str, expected: str) -> bool | None:
    """Ask for an exact word, refusing non-interactive stdin with a clear error.

    Returns:
    - ``True``  : exact word entered
    - ``False`` : entered something else
    - ``None``  : no interactive input available (EOF on read)
    """
    try:
        return input(prompt).strip() == expected
    except EOFError:
        print(f"\n{_NON_INTERACTIVE_CONFIRM}", file=sys.stderr)
        return None


def _add_common_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "destination",
        help="local directory path, or an rclone remote spec with --rclone",
    )
    parser.add_argument("--rclone", action="store_true", help="destination is an rclone remote")
    parser.add_argument(
        "--force-new-identity",
        action="store_true",
        help=(
            "register this folder as a NEW drive even though Truestill recorded a known drive "
            "here. Use only if the folder really is a different place now"
        ),
    )
    parser.add_argument("--apply", action="store_true", help="actually write (default: dry run)")
    parser.add_argument(
        "--db",
        type=Path,
        default=default_catalog_path(),
        help=f"path to the catalog file (default: {default_catalog_path()})",
    )
    parser.add_argument(
        "--phash-threshold",
        type=int,
        default=DEFAULT_PHASH_THRESHOLD,
        metavar="N",
        help=(
            f"expert setting: near-duplicate sensitivity for perceptual hashing "
            f"(default: {DEFAULT_PHASH_THRESHOLD})"
        ),
    )
    parser.add_argument(
        "--by-device", action="store_true", help="name capture folders after the device"
    )
    parser.add_argument(
        "--no-rename", action="store_true", help="keep original filenames (no date prefix)"
    )
    parser.add_argument(
        "--events", action="store_true", help="suggest camera photo groups that you can name"
    )
    parser.add_argument(
        "--no-timestamps", action="store_true", help="do not set mtime from the capture date"
    )
    parser.add_argument(
        "--skip-undated",
        action="store_true",
        help="skip files with no capture date instead of copying them to Undated/",
    )
    parser.add_argument(
        "--pool",
        choices=("thread", "process"),
        default="thread",
        help="expert setting: worker style used during hashing",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=DEFAULT_WORKERS,
        metavar="N",
        help="expert setting: number of hashing workers",
    )
    parser.add_argument(
        "--report", type=Path, metavar="PATH", help="write a full per-file decision report as JSON"
    )


def _add_undo_parser(sub: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """`undo-organize`: reverse a rename-based run, preview first."""
    undo = sub.add_parser(
        "undo-organize",
        help="put files back where they were before reorganize in this same folder (--in-place)",
    )
    undo.add_argument(
        "--db", type=Path, default=default_catalog_path(), help="path to the catalog file"
    )
    undo.add_argument("--run-id", help="which run to reverse (default: the most recent)")
    undo.add_argument("--list", action="store_true", help="list recorded --in-place runs and exit")
    undo.add_argument(
        "--source-root", type=Path, help="where the files came from, if the drive has moved"
    )
    undo.add_argument(
        "--dest-root", type=Path, help="where the library is now, if the drive has moved"
    )
    undo.add_argument(
        "--apply", action="store_true", help="actually move files back (default: preview)"
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="truestill",
        description="Organize, de-duplicate and back up a media library to a pluggable destination.",
    )
    # Declared on the top-level parser so `truestill --version` works with no subcommand,
    # despite subparsers being required -- argparse resolves --version before that check.
    # It is the first thing a bug reporter reaches for; it must never need an argument.
    parser.add_argument("--version", action="version", version=f"truestill {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    organize = sub.add_parser("organize", help="organize a folder of media files")
    organize.add_argument("source", type=Path, help="folder to analyse (searched recursively)")
    organize.add_argument("--all-files", action="store_true", help="include non-media extensions")
    organize.add_argument(
        "--move",
        action="store_true",
        help="remove each source only after the new copy is written and verified (needs --apply)",
    )
    organize.add_argument(
        "--in-place",
        action="store_true",
        help=(
            "reorganize in this same folder by rename (implies --move). Requires source "
            "and destination on one filesystem; refuses rather than falling back to a copy"
        ),
    )
    organize.add_argument(
        "--refresh-metadata",
        action="store_true",
        help=(
            "re-read photo details even when cache says the file is unchanged "
            "(use this after another app edits tags without updating the file date)"
        ),
    )
    _add_common_options(organize)

    ingest = sub.add_parser(
        "ingest",
        help=(
            "rescue + organize photos from a folder or archive "
            "(.zip, .tar, .tgz), recovering dates from any sidecars found"
        ),
    )
    # Deliberately NOT `required=True`: argparse counts the two spellings as separate
    # arguments, so a script passing only the alias would be told `--source` is missing - the
    # alias would parse and then fail, which is worse than not having one. The requirement is
    # enforced after parsing instead, where it can name both spellings.
    ingest.add_argument(
        "--source",
        type=Path,
        metavar="PATH",
        help=(
            "folder of photos, or an archive (.zip, .tar, .tgz) - any one part of a "
            "multi-part download will do, the rest are found beside it"
        ),
    )
    # PERMANENT alias, not a deprecation. `--takeout` named the motivating case rather than the
    # feature, which reads archives from any source - but it shipped, so scripts use it. Keeping
    # it costs ONE LINE and has no maintenance burden: it resolves to the same `dest`, so there
    # is no second code path to keep correct and nothing to test beyond the equivalence.
    # A removal window would buy nothing and would break those scripts on a schedule. Do not
    # tidy this away.
    ingest.add_argument("--takeout", type=Path, dest="source", help=argparse.SUPPRESS)
    ingest.add_argument(
        "--tz",
        type=_parse_tz,
        default=None,
        metavar="±HH:MM",
        help="local offset applied to Takeout's UTC dates (default: treat as UTC)",
    )
    ingest.add_argument(
        "--prefer-takeout-dates",
        action="store_true",
        help="prefer Google Photos capture time over embedded EXIF date fields",
    )
    ingest.add_argument(
        "--map-albums",
        action="store_true",
        help="name Camera events after the album their photos came from",
    )
    # Accepted only so the refusal can explain itself. Without it argparse says
    # "unrecognized arguments", which tells a user with a full drive nothing useful.
    ingest.add_argument("--in-place", action="store_true", help=argparse.SUPPRESS)
    _add_common_options(ingest)

    drives = sub.add_parser(
        "drives", help="list known backup drives, or set up a drive marker file"
    )
    drives.add_argument(
        "--db", type=Path, default=default_catalog_path(), help="path to the catalog file"
    )
    drives.add_argument(
        "--init", type=Path, metavar="ROOT", help="create a drive marker file at ROOT"
    )
    drives.add_argument("--label", help="human label for --init")
    drives.add_argument("--uuid", help="re-attach a known drive id instead of creating a new one")
    drives.add_argument(
        "--adopt-existing",
        action="store_true",
        help=(
            "when --init finds this folder is a drive the catalog already knows, keep that "
            "drive's identity instead of creating a second one"
        ),
    )
    drives.add_argument(
        "--force-new-identity",
        action="store_true",
        help=(
            "create a new drive id even though this folder holds a library the catalog "
            "already knows - correct for a clone, wrong for a drive that simply moved"
        ),
    )
    drives.add_argument(
        "--migrate-marker",
        type=Path,
        metavar="ROOT",
        help=(
            f"write a {MARKER_NAME} for a drive that still carries only a pre-rename "
            "marker, keeping its identity and leaving the old file in place"
        ),
    )

    repoint = sub.add_parser(
        "repoint-sources",
        help="after moving the folder photos were imported from, tell truestill where it went",
    )
    repoint.add_argument("old_root", type=Path, metavar="OLD-ROOT")
    repoint.add_argument("new_root", type=Path, metavar="NEW-ROOT")
    repoint.add_argument("--apply", action="store_true", help="rewrite (default: preview only)")
    repoint.add_argument(
        "--db", type=Path, default=default_catalog_path(), help="path to the catalog file"
    )

    _add_undo_parser(sub)

    restore = sub.add_parser(
        "restore",
        help="restore the decisions a drive is carrying into this catalog",
    )
    restore.add_argument("root", type=Path, metavar="ROOT", help="the drive to read")
    restore.add_argument(
        "--db", type=Path, default=default_catalog_path(), help="path to the catalog file"
    )
    restore.add_argument(
        "--apply", action="store_true", help="actually restore (default: preview only)"
    )
    restore.add_argument(
        "--discard",
        action="store_true",
        help="DESTRUCTIVE: overwrite the drive's decisions with this catalog's",
    )

    where = sub.add_parser("where", help="find which drive(s) hold a file, even when unplugged")
    where.add_argument("term", help="filename / path substring to search for")
    where.add_argument(
        "--db", type=Path, default=default_catalog_path(), help="path to the catalog file"
    )
    where.add_argument(
        "--limit",
        type=int,
        default=Catalog.FIND_PAGE_SIZE,
        help=f"how many matches to show (default {Catalog.FIND_PAGE_SIZE}; 0 for all)",
    )

    analyze = sub.add_parser(
        "analyze",
        help="say what is in a folder, without changing anything (fast; reads names and sizes)",
    )
    analyze.add_argument("path", type=Path, help="the folder to look at")
    analyze.add_argument(
        "--all-files",
        action="store_true",
        help="count every file, not only the ones Truestill recognizes as media",
    )

    verify = sub.add_parser(
        "verify", help="re-check files on a connected drive against the catalog"
    )
    verify.add_argument(
        "path", type=Path, help="the drive's current mount root (must be connected)"
    )
    verify.add_argument(
        "--db", type=Path, default=default_catalog_path(), help="path to the catalog file"
    )
    verify.add_argument("--pool", choices=("thread", "process"), default="thread")
    verify.add_argument("--workers", type=int, default=DEFAULT_WORKERS, metavar="N")

    status = sub.add_parser("status", help="show files that exist on only one drive (3-2-1)")
    status.add_argument(
        "--db", type=Path, default=default_catalog_path(), help="path to the catalog file"
    )

    catalog_cmd = sub.add_parser(
        "catalog", help="show where Truestill keeps its catalog, and optionally move it"
    )
    catalog_cmd.add_argument(
        "--move",
        action="store_true",
        help="copy a catalog still in reports/ to the standard location for this system",
    )

    config = sub.add_parser(
        "config", help="show or change this catalog file's destination folder pattern"
    )
    config.add_argument(
        "--db", type=Path, default=default_catalog_path(), help="path to the catalog file"
    )
    config.add_argument("--set-template", metavar="TEMPLATE", help="set a custom folder pattern")
    config.add_argument(
        "--preset", metavar="NAME", help="set the layout from a saved folder pattern"
    )
    config.add_argument(
        "--preview", action="store_true", help="render sample files without saving anything"
    )

    reclaim = sub.add_parser(
        "reclaim",
        help="free source files that are safely backed up on a connected drive (preview by default)",
    )
    reclaim.add_argument(
        "path", type=Path, help="the backup drive's mount root (must be connected)"
    )
    reclaim.add_argument("--db", type=Path, default=default_catalog_path(), help="SQLite catalog")
    reclaim.add_argument(
        "--apply", action="store_true", help="actually delete sources (default: preview only)"
    )
    reclaim.add_argument(
        "--min-copies",
        type=int,
        default=1,
        metavar="N",
        help="only free content that has at least N backed-up copies (default: 1)",
    )

    migrate = sub.add_parser(
        "migrate-layout",
        help="relocate a connected drive's files to match the current template (preview by default)",
    )
    migrate.add_argument(
        "path", type=Path, help="the drive's current mount root (must be connected)"
    )
    migrate.add_argument("--db", type=Path, default=default_catalog_path(), help="SQLite catalog")
    _add_clean_parser(sub)
    _add_rescan_parser(sub)

    migrate.add_argument(
        "--undo",
        action="store_true",
        help="put the last migration back (preview first, then a typed confirm)",
    )
    migrate.add_argument(
        "--apply", action="store_true", help="actually move files (default: preview only)"
    )

    return parser


def _add_rescan_parser(sub: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    """The `rescan` surface, split out for the reason `_add_clean_parser` is: statement ceiling."""
    rescan = sub.add_parser(
        "rescan",
        help="say whether the catalog still matches what is on a drive (reads only, changes nothing)",
    )
    rescan.add_argument("path", type=Path, help="the connected drive folder")
    rescan.add_argument("--db", type=Path, default=default_catalog_path(), help="SQLite catalog")


#: How many names one section prints before it stops. The count beside it is always the real
#: one - a drive with 30,000 unrecorded files must say 30,000 and show a sample, never show 20
#: and imply that is all there was. Same shape as `left_behind.FOLDER_LIMIT`.
RESCAN_SAMPLE_LIMIT = 20


def _print_rescan_section(title: str, names: Sequence[str], note: str) -> None:
    """One bucket: its real count, a bounded sample, and what the bucket means.

    A bucket with nothing in it prints nothing. Never-silent is about what happened, not about
    what did not - the same rule the skipped-census and duplicate-origin lines already follow.
    """
    if not names:
        return
    print(f"\n  {title}: {len(names)}")
    print(f"      {note}")
    for name in names[:RESCAN_SAMPLE_LIMIT]:
        print(f"      {name}")
    if len(names) > RESCAN_SAMPLE_LIMIT:
        print(f"      ... and {len(names) - RESCAN_SAMPLE_LIMIT} more, not shown")


def _print_rescan(report: RescanReport, root: Path, label: str, elapsed: float) -> None:
    """The whole report, including what it deliberately cannot tell you.

    The closing block is not padding. Every remedy for what this finds lives in work that does
    not exist yet, so a bare count would leave someone holding a number with no next step -
    which is the defect the sidebar's at-risk banner was corrected for.
    """
    print("\n" + "=" * 100)
    print(f"RESCAN  {root}")
    print("=" * 100)
    print(f"  drive              : {label}")
    print(f"  time taken         : {elapsed:.2f} s")
    print(f"  in place           : {len(report.placed)}, where the catalog says they are")

    _print_rescan_section(
        "MOVED",
        [f"{m.recorded}  ->  {'  and  '.join(m.found)}" for m in report.moved],
        "on the drive, but not where the catalog says. Same content, matched by its hash.",
    )
    _print_rescan_section(
        "ON THE DRIVE, NOT IN THE CATALOG",
        list(report.stray),
        "files Truestill has no record of. Copied in by hand, restored, or added since.",
    )
    _print_rescan_section(
        "NOT ACCOUNTED FOR",
        list(report.unaccounted),
        "the catalog names these and they are not on this drive. Could be deleted, could be"
        " on another drive - Truestill does not guess which.",
    )

    if not report.complete:
        print("\n  ! SOME OF THIS DRIVE COULD NOT BE READ, so the list above is incomplete.")
        for folder in report.unreadable_dirs:
            print(f"      folder, could not be opened : {folder}")
        for name in report.unreadable_files[:RESCAN_SAMPLE_LIMIT]:
            print(f"      file, could not be read     : {name}")
        extra = len(report.unreadable_files) - RESCAN_SAMPLE_LIMIT
        if extra > 0:
            print(f"      ... and {extra} more file(s), not shown")
        print("      Anything inside them is counted as NOT ACCOUNTED FOR whether it is there")
        print("      or not, so treat that number as a floor rather than an answer.")

    if report.reconciled:
        print("\n  Everything the catalog records for this drive is where it says it is.")

    print("\nWHAT THIS DOES AND DOES NOT TELL YOU")
    print("  This is a snapshot taken while the drive was being read. A file changed during")
    print("  the read may be described as it was a moment before.")
    print("  It answers WHERE your files are, never whether their contents are still good.")
    print("  Silent damage to a file changes neither its name nor its size, so only")
    print("  'truestill verify' can find it - that reads every byte and this reads none.")
    print("  Nothing was changed: not your files, not the drive, not the catalog.")
    print("  No command repairs any of the above yet. This one only tells you.")


def _rescan_hashes(candidates: dict[str, Path], db: Path) -> tuple[dict[str, str], list[str]]:
    """Identify the candidates by content. Returns ``(relative -> sha256, unreadable)``.

    **The cache is opened read-only, and that is required rather than cautious** (§8): this
    computes SHA-256 and never a perceptual hash, and `perceptual` carries "not an image" and
    "not computed" in one value with no `need_perceptual` to tell them apart. A row written
    here would come back as a hit to a later organize preview and silently switch off
    near-duplicate detection for those files. Reading still takes every hit an earlier full
    run recorded, so nothing is repeated; it simply contributes nothing back.
    """
    identified: dict[str, str] = {}
    unreadable: list[str] = []
    with HashCache.beside_readonly(db) as cache:
        for relative, path in candidates.items():
            try:
                stat = path.stat()
                # SHA-only, so `need_perceptual` stays False - see `_rescan_hashes`.
                cached = cache.get(path, stat.st_size, stat.st_mtime_ns, need_sha=True)
                identified[relative] = (
                    cached.sha256
                    if cached is not None and cached.sha256 is not None
                    else sha256_file(path)
                )
            except OSError:
                # One unreadable file must not cost the whole drive its report.
                unreadable.append(relative)
    return identified, unreadable


def _report_decision_saves(results: tuple[DriveSave, ...], *, upgrade: bool) -> None:
    """The CLI's voice for the decisions backup. Core hands over outcomes and prints nothing (§2).

    **Silence on success, deliberately.** A 1.2 KB write after an operation the user just waited
    seconds for is not news, and the standing signal is a date on the drive rather than a notice
    to dismiss - Lightroom's weekly prompt is what people learned to click through.

    The exception is the **first** write, once per catalog: it says what happened, in one line,
    and never again.
    """
    for result in results:
        if result.outcome in PROBLEM_OUTCOMES:
            print(
                f"note: decisions were not saved to {result.label}: {result.detail}",
                file=sys.stderr,
            )
    if upgrade:
        saved = [r.label for r in results if r.outcome is SaveOutcome.WRITTEN]
        if saved:
            print(f"Saved a copy of your decisions to {', '.join(saved)}.")


def _catalog(db: Path) -> AbstractContextManager[Catalog]:
    """``open_catalog`` with this surface's voice attached.

    Every CLI catalog open goes through here, so the trigger cannot be missed at a sixteenth
    call site - and `test_catalog_opens_go_through_the_session` refuses a bare `Catalog(...)`.
    """
    return open_catalog(db, report=_report_decision_saves)


def _cmd_rescan(args: argparse.Namespace) -> int:
    """Reconcile a drive's recorded locations with what is on it. Reads; writes nothing.

    Exit **1** when anything did not reconcile or anything could not be read, so
    ``truestill rescan X && next_step`` cannot chain past a drive Truestill could not account
    for - the same reason an organize preview that found an unreadable file exits 1.
    """
    root = args.path
    marker = _drive_or_explain(root)
    if marker is None:
        return 2
    if not args.db.is_file():
        # Refused rather than created. `Catalog(db)` would make an empty one, and reconciling a
        # drive against a catalog that has never seen it would report the whole drive as
        # unrecorded - a frightening answer to a question nobody asked.
        print(f"error: no catalog at {args.db}; nothing to reconcile against.", file=sys.stderr)
        return 2

    started = _CLOCK()
    scan = scan_source(root)
    on_disk = {path.relative_to(root).as_posix(): path for path in scan.media}
    with _catalog(args.db) as catalog:
        recorded = {
            str(row["relative"]): str(row["sha256"]) for row in catalog.copies_on_drive(marker.uuid)
        }
    # The PLACED rule: a file where the catalog says it is, is not read. This subtraction is
    # what makes the cost proportional to what changed rather than to the size of the library.
    candidates = {rel: path for rel, path in on_disk.items() if rel not in recorded}
    identified, unreadable_files = _rescan_hashes(candidates, args.db)

    report = reconcile(
        recorded=recorded,
        on_disk=on_disk.keys(),
        identified=identified,
        unreadable_dirs=[p.relative_to(root).as_posix() for p in scan.unreadable_dirs],
        unreadable_files=unreadable_files,
    )
    _print_rescan(report, root, marker.label, _CLOCK() - started)
    return 0 if report.reconciled else 1


def _migrate_marker(root: Path, catalog: Catalog) -> int:
    """Give a legacy-only drive a canonical marker, preserving its identity."""
    if read_marker(root) is None:
        print(f"error: no drive marker at {root}", file=sys.stderr)
        return 2
    if not needs_marker_upgrade(root):
        print(f"{root} already carries {MARKER_NAME}; nothing to do.")
        return 0
    legacy = existing_marker_path(root)
    marker = upgrade_marker(root)
    if marker is None:  # unreachable: read_marker above proved a marker exists
        print(f"error: could not read the drive marker at {root}", file=sys.stderr)
        return 2
    catalog.upsert_drive(uuid=marker.uuid, label=marker.label)
    print(
        f"Wrote {MARKER_NAME} for '{marker.label}' (uuid {marker.uuid}, unchanged).\n"
        f"  {legacy.name if legacy else 'the old marker'} was left in place."
    )
    return 0


def _cmd_drives(args: argparse.Namespace) -> int:
    with _catalog(args.db) as catalog:
        if args.migrate_marker is not None:
            return _migrate_marker(args.migrate_marker, catalog)

        if args.init is not None:
            if not args.label:
                print("error: --init requires --label", file=sys.stderr)
                return 2
            return _init_drive(args, catalog)

        drives = catalog.list_drives()
        if not drives:
            print("No drives known. Initialise one: truestill drives --init <root> --label <name>")
            return 0
        print(
            f"{'LABEL':<20}{'FILES':>8}{'SIZE(MB)':>12}  {'STATUS':<10}"
            f"{'LAST SEEN':<22}LAST VERIFIED"
        )
        connected: list[tuple[Path, str]] = []
        for d in drives:
            size_mb = (d["total_size"] or 0) / 1e6
            # Not a boolean. "unknown" is the ordinary state for a drive this machine has never
            # been pointed at, and printing it as "offline" would tell someone their backup is
            # gone when Truestill simply has no idea where it lives.
            reach = reach_of(catalog, str(d["uuid"]))
            print(
                f"{d['label']:<20}{d['file_count']:>8}{size_mb:>12.1f}  {reach.value:<10}"
                f"{(d['last_seen'] or '-')[:19]:<22}{(d['last_verified'] or 'never')[:19]}"
            )
            if reach is DriveReach.CONNECTED:
                connected.append(
                    (
                        Path(str(catalog.get_setting(drive_path_hint(d["uuid"])))),
                        str(d["label"]),
                    )
                )
        # Gathered ONCE, after the rows: doing it per drive would turn one full catalog read
        # into one per drive, on a screen people open often.
        if connected:
            mine = gather_decisions(catalog, "")
            for root, label in connected:
                _print_drive_notice(root, mine, label)
    return 0


def _recorded_drives(catalog: Catalog) -> list[RecordedDrive]:
    """Every known drive as `drive_adoption` wants it: identity plus where its copies sit.

    A copy is proven against the digest it actually presents: a Takeout-baked copy hashes to its
    own ``copy_sha256`` and not to ``files.sha256``, so matching only the source hash would make
    exactly the baked copies look like content that differs.
    """
    return [
        recorded_drive(
            str(row["uuid"]), str(row["label"]), catalog.copies_on_drive(str(row["uuid"]))
        )
        for row in catalog.list_drives()
    ]


def _print_adoption_refusal(path: Path, offers: list[AdoptionOffer]) -> None:
    """Name the drive this folder already is, and both ways forward. Never choose one."""
    proven = [o for o in offers if o.verdict is AdoptionVerdict.PROVEN]
    differing = [o for o in offers if o.verdict is AdoptionVerdict.CONTENT_DIFFERS]
    if differing and not proven:
        names = ", ".join(f"'{o.label}'" for o in differing)
        print(
            f"error: {path} has the same layout as {names}, but the files there are NOT the "
            "same files.\n"
            "       Nothing was written. This is not that drive; if it really is a new one, "
            "register it with --force-new-identity.",
            file=sys.stderr,
        )
        return
    names = ", ".join(f"'{o.label}'" for o in proven)
    print(
        f"error: {path} already holds the library recorded as {names}.\n"
        f"       Registering it again would create a SECOND drive id for one library, and "
        "Truestill would then\n"
        "       count one copy of your photos as two. Nothing was written.\n"
        "\n"
        "       If this drive moved:      re-run with --adopt-existing\n"
        "       If this is a clone, and\n"
        "       both really exist:        re-run with --force-new-identity",
        file=sys.stderr,
    )
    if len(proven) > 1:
        print(
            "       More than one known drive matches, so --adopt-existing cannot choose. "
            "Pass --uuid <id> to say which.",
            file=sys.stderr,
        )


def _print_drive_notice(root: Path, mine: Decisions, label: str) -> None:
    """Say what a drive is carrying, when there is something to say.

    **Two screens, because neither covers the other.** This is the lost-machine path from
    `--init` and the partial case from the listing; `drives` on an empty catalog iterates zero
    rows and touches no path, so it cannot be the only place. `(acc)` was corrected on 2026-08-09
    to say so.

    Costs one document read at a root the caller already has open - no walk, no scan.
    """
    notice = notice_for(root, mine)
    if notice is None:
        return
    if notice.refusal is not None:
        print(f"\n{notice.refusal}")
        return
    if notice.awaiting_restore:
        sections = ", ".join(s.replace("_", " ") for s in notice.awaiting_restore)
        print(f"\n{label} is carrying decisions this catalog does not have: {sections}.")
        print(f"Look at them, and restore them, with:  truestill restore {root}")


def _init_drive(args: argparse.Namespace, catalog: Catalog) -> int:
    """Register a folder as a drive, refusing to mint a second identity for a known library."""
    offers = (
        []
        if (args.uuid or args.force_new_identity)
        else inspect_root(args.init, _recorded_drives(catalog))
    )
    proven = [o for o in offers if o.verdict is AdoptionVerdict.PROVEN]
    if offers and not args.adopt_existing:
        _print_adoption_refusal(args.init, offers)
        return 2

    adopt: str | None = args.uuid
    label = args.label
    if args.adopt_existing:
        if len(proven) != 1:
            _print_adoption_refusal(args.init, offers)
            if not offers:
                print(
                    f"error: --adopt-existing found no known library at {args.init}. "
                    "Nothing was written.",
                    file=sys.stderr,
                )
            return 2
        # The identity AND the name come from the catalog: this folder *is* that drive, so
        # renaming it here would leave the user's own label behind for no reason.
        adopt, label = proven[0].uuid, proven[0].label

    marker = create_marker(args.init, label, uuid=adopt)
    catalog.upsert_drive(uuid=marker.uuid, label=marker.label)
    catalog.set_setting(drive_path_hint(marker.uuid), str(args.init))
    verb = "re-attached" if adopt else "initialised"
    print(f"Drive '{marker.label}' {verb} at {args.init}  (uuid {marker.uuid}).")
    _print_drive_notice(args.init, gather_decisions(catalog, marker.uuid), "This drive")
    return 0


def _drive_or_explain(path: Path) -> DriveMarker | None:
    """Resolve a drive root, printing a *useful* refusal when the path is not one.

    Pointing at a folder inside a connected drive used to report "connect the drive first",
    which is both wrong and unactionable. Walking up finds the drive and names the correction.
    """
    location = locate_drive(path)
    if location.is_root:
        return location.marker
    if location.is_inside and location.marker is not None:
        print(
            f"error: {path} is a folder inside '{location.marker.label}'.\n"
            f"       Use the drive root instead:  {location.root}",
            file=sys.stderr,
        )
        return None
    if not path_is_usable_dir(path):
        # A path that is not there and a folder that is not a drive are different states with
        # OPPOSITE remedies, and this printed the register suggestion for both. Following it on
        # an unmounted drive is what mints a second identity for a library that already exists
        # (`BACKLOG.md` (aap)) - so the two must never share wording again.
        print(
            f"error: {path} is not there.\n"
            "       If this is an external drive, is it plugged in and mounted? "
            "Check the path, then try again.\n"
            "       Do NOT register the folder again while the drive is disconnected - that "
            "creates a second\n"
            "       drive id for a library you already have.",
            file=sys.stderr,
        )
        return None
    print(
        f"error: {path} isn't a Truestill drive yet.\n"
        f"       Register it with:  truestill drives --init {path}",
        file=sys.stderr,
    )
    return None


def _print_repoint_preview(plan: RepointPlan) -> None:
    """What the rewrite would change, before anything is written."""
    print(_SEPARATOR)
    print("REPOINT SOURCES - PREVIEW")
    print(_SEPARATOR)
    print(f"  recorded under : {plan.old_root}")
    print(f"  would point to : {plan.new_root}")
    print(f"  rows recorded under the old root : {len(plan.rows)}")
    print(f"  found at the new root            : {len(plan.movable)}")
    print(f"  still present at the old root    : {plan.still_present_at_old}")
    print(f"  content proof                    : {plan.proven}/{plan.hashed} sampled files match")
    for row in plan.movable[:_STATUS_PREVIEW]:
        print(f"      {row.old_path}\n        -> {row.new_path}")
    if len(plan.movable) > _STATUS_PREVIEW:
        print(f"  ... and {len(plan.movable) - _STATUS_PREVIEW} more.")
    missing = len(plan.rows) - len(plan.movable)
    if missing:
        # Left pointing where they were, on purpose: a dead path is honest, and a confidently
        # wrong one is what `reclaim` would delete.
        print(f"  {missing} recorded file(s) are not at the new root and will NOT be changed.")


def _cmd_repoint(args: argparse.Namespace) -> int:
    """Rewrite recorded source paths after their folder moved. Preview, then a typed word."""
    old_root, new_root = args.old_root, args.new_root
    if not path_is_usable_dir(new_root):
        print(f"error: {new_root} is not a folder Truestill can read.", file=sys.stderr)
        return 2
    with _catalog(args.db) as catalog:
        recorded = [(source, sha) for source, sha, _perceptual in catalog.seed_rows()]
        plan = plan_repoint(recorded, old_root, new_root)

        if not plan.rows:
            print(f"No catalogued file was recorded under {old_root}. Nothing to repoint.")
            return 0
        _print_repoint_preview(plan)

        if plan.verdict is not AdoptionVerdict.PROVEN:
            # The content at the new root is not the content that was recorded. Refusing is the
            # whole point: `reclaim` deletes `source_path`, and its gate re-hashes the drive
            # COPY, never the source - so a wrong path here is a file deleted unverified.
            print(
                f"\nerror: {new_root} does not hold the files recorded under {old_root}.\n"
                f"       {plan.proven} of {plan.hashed} sampled files matched by content. "
                "Nothing was changed.\n"
                "       Check the folder is the one that moved, not a different copy.",
                file=sys.stderr,
            )
            return 2
        if not args.apply:
            print("\nPreview only. Re-run with --apply to rewrite these paths.")
            return 0

        confirmed = _typed_confirmation(
            f"\nType 'repoint' to rewrite {len(plan.movable)} recorded path(s): ", "repoint"
        )
        if confirmed is None:
            return 2
        if not confirmed:
            print("Aborted. Nothing was changed.")
            return 0
        changed = catalog.repoint_sources([(r.sha256, r.new_path) for r in plan.movable])
        print(f"Repointed {changed} recorded source path(s) to {new_root}.")
    return 0


def _restore_stamp() -> str:
    """Now, in the same shape the documents already carry."""
    return datetime.now(UTC).isoformat()


def _restore_documents_for(root: Path, catalog: object) -> tuple[list[Decisions], str | None]:
    """Every document worth merging: the drive the user named, plus any other reachable drive.

    **The named root is read from the PATH, never from a lookup.** On the machine this command
    exists for the catalog is empty and no drive is registered, so a version that found documents
    by asking the catalog would work for everybody except the person who needs it.

    Other registered drives join in when there are any, because two drives that disagree is the
    case the reconciliation was written for - and on a fresh machine that list is simply empty.
    """
    found = read_decisions(root)
    if found.error is not None:
        return [], found.error
    if found.decisions is None:
        return [], f"no decisions document at {root}"

    documents = [found.decisions]
    seen = {root.resolve()}
    for row in catalog.registered_drives():  # type: ignore[attr-defined]
        uuid = str(row["uuid"])
        hint = catalog.get_setting(drive_path_hint(uuid))  # type: ignore[attr-defined]
        if drive_reach(hint, uuid) is not DriveReach.CONNECTED:
            continue
        other = Path(str(hint)).resolve()
        if other in seen:
            continue
        seen.add(other)
        alongside = read_decisions(other)
        if alongside.decisions is not None:
            documents.append(alongside.decisions)
    return documents, None


def _print_restore_plan(report: RestoreReport, documents: int) -> None:
    """What would come back, and - the half that is easy to leave out - what would not.

    A restore that reports 40 applied and says nothing about 12 corrections it could not place
    lets the user confirm on the good half only.
    """
    print(f"\nRead {documents} decisions document(s).")
    applied = report.applied
    if applied.applied:
        for section, count in sorted(applied.applied.items()):
            print(f"  {count:>4}  {section.replace('_', ' ')}")
    else:
        print("  nothing this catalog does not already have")

    for name in applied.unmatched_events:
        print(f"\n  ! event '{name}' does not match anything here - its photos have changed,")
        print("    so its name is reported rather than guessed at.")
    for section, count in sorted(applied.awaiting_content.items()):
        print(f"\n  ! {count} {section.replace('_', ' ')} are waiting for photos this catalog")
        print("    has not scanned. Plug in the drive holding them, scan, and restore again.")
    for section, count in sorted(applied.already_newer_locally.items()):
        print(f"\n  - {count} {section.replace('_', ' ')} on the drive were older than this")
        print("    machine's and were ignored. Nothing to do.")
    for loss in report.reconciled.superseded:
        print(
            f"\n  - {loss.count} {loss.section.replace('_', ' ')} on {loss.drive_label} were"
            " older and were not used."
        )
    for label in report.reconciled.undated:
        print(f"\n  - {label}'s document carries no date, so it could not overrule any other.")


def _cmd_restore(args: argparse.Namespace) -> int:
    """Put a drive's decisions back into this catalog. **Offers; never restores silently.**"""
    root: Path = args.root
    if not root.is_dir():
        print(f"error: {root} is not a folder.", file=sys.stderr)
        return 2

    with _catalog(args.db) as catalog:
        documents, problem = _restore_documents_for(root, catalog)
        if problem is not None:
            print(f"error: {problem}", file=sys.stderr)
            return 2

        if args.discard:
            return _discard_to_drive(root, catalog, apply=args.apply)

        report = apply_documents(catalog, documents, apply=False)
        _print_restore_plan(report, len(documents))
        if not args.apply:
            print(f"\nPreview only. Restore with:  truestill restore {root} --apply")
            return 0

        if (
            _typed_confirmation("\nType 'restore' to put these decisions back: ", "restore")
            is not True
        ):
            print("Nothing was restored.", file=sys.stderr)
            return 1

        report = apply_documents(catalog, documents, apply=True)
        print(f"\nRestored into {args.db}.")
        return 0


def _discard_to_drive(root: Path, catalog: object, *, apply: bool) -> int:
    """Overwrite the drive's document with this catalog's. **The destructive branch.**

    Closes `(aby)`: a decision deleted on this machine leaves the drive holding something the
    catalog does not, so every later save refuses with WOULD_LOSE and the drive copy quietly
    stops being updated - permanently, because nothing else reconciles the two. This is the user
    saying "mine is right". One forced write, after which the drive matches the catalog and the
    guard has nothing left to fire on. No override flag is stored, so there is no state to go
    stale.
    """
    found = read_decisions(root)
    theirs = found.decisions
    marker = read_marker(root)
    uuid = marker.uuid if marker is not None else ""
    mine = gather_decisions(catalog, uuid)

    losing = would_lose(theirs, mine) if theirs is not None else ()
    if not losing:
        print("\nThis drive holds nothing this catalog is missing. Nothing to discard.")
        return 0

    print(f"\nDISCARD will overwrite the decisions on {root} with this catalog's.")
    print(f"These sections exist there and NOT here, and will be gone: {', '.join(losing)}.")
    if not apply:
        print(f"\nPreview only. Discard with:  truestill restore {root} --discard --apply")
        return 0

    if _typed_confirmation("\nType 'discard' to overwrite the drive: ", "discard") is not True:
        print("The drive was not changed.", file=sys.stderr)
        return 1

    outcome = write_decisions(
        root, merge_onto_drive(theirs, _dataclass_replace(mine, written=_restore_stamp()))
    )
    if not outcome.written:
        print(f"error: {outcome.error}", file=sys.stderr)
        return 2
    print("\nThe drive now matches this catalog.")
    return 0


def _cmd_where(args: argparse.Namespace) -> int:
    with _catalog(args.db) as catalog:
        total = catalog.count_copies(args.term)
        rows = catalog.find_copies(args.term, limit=args.limit or None)
    if not rows:
        print(f"No catalogued copies match '{args.term}'.")
        return 0
    print(f"Copies matching '{args.term}':")
    for r in rows:
        verified = (
            f"verified {r['last_verified'][:19]}" if r["last_verified"] else "not yet verified"
        )
        print(f"  {r['original_name'] or r['relative']}")
        print(f"      drive '{r['drive_label']}'  ->  {r['relative']}   ({verified})")
    if total > len(rows):
        # Never a silent truncation: a search that quietly showed the first N would let someone
        # conclude a file is not on any drive when it is simply further down the list.
        print(f"\n  ... and {total - len(rows)} more. Use --limit to show more.")
    return 0


def _cmd_verify(args: argparse.Namespace) -> int:
    root = args.path
    marker = _drive_or_explain(root)
    if marker is None:
        return 2
    when = _now_iso()
    with _catalog(args.db) as catalog:
        catalog.upsert_drive(uuid=marker.uuid, label=marker.label)
        # Remember where this drive was seen. Without it the CLI has no reachability information
        # at all and `truestill drives` can only ever say "unknown" - which is honest but
        # useless. Written here and at `--init` because those are the two moments the CLI holds
        # a resolved drive root and a catalog at the same time. It is a hint, never identity.
        catalog.set_setting(drive_path_hint(marker.uuid), str(root))
        rows = catalog.copies_on_drive(marker.uuid)
        if not rows:
            print(f"Drive '{marker.label}' has no recorded copies in the catalog.")
            return 0
        copies = [CopyToVerify.from_row(r) for r in rows]
        print(f"Verifying {len(copies)} copies on drive '{marker.label}' ...")
        results = verify_copies(
            copies,
            root,
            pool=args.pool,
            workers=args.workers,
            progress=_progress_printer("verified"),
        )

        counts = Counter(r.status.value for r in results)
        for result in results:
            if result.status is CopyStatus.VERIFIED:
                catalog.mark_copy_verified(
                    sha256=result.copy.sha256, drive_uuid=marker.uuid, when=when
                )
        catalog.set_drive_verified(marker.uuid, when)

    print(_SEPARATOR)
    print(f"VERIFY '{marker.label}'")
    print(_SEPARATOR)
    print(f"  verified : {counts.get('verified', 0)}")
    print(f"  MISSING  : {counts.get('missing', 0)}")
    print(f"  MISMATCH : {counts.get('mismatch', 0)}")
    print(f"  UNREADABLE : {counts.get('unreadable', 0)}")
    # Counted, not merely listed: without this line a drive of unrecorded-hash copies reports
    # four zeros and reads as "nothing happened" (§9).
    print(f"  UNVERIFIABLE : {counts.get('unverifiable', 0)}  (no recorded hash to check against)")
    for result in results:
        if result.status is not CopyStatus.VERIFIED:
            suffix = f" ({result.detail})" if result.detail else ""
            print(f"  {result.status.value.upper():<10} {result.copy.relative}{suffix}")
    print("\n  (read-only: Truestill never repairs; re-copy the source to restore a bad file.)")
    return 1 if (counts.get("missing") or counts.get("mismatch") or counts.get("unreadable")) else 0


def _cmd_catalog(args: argparse.Namespace) -> int:
    """Say where the catalog is, and on ``--move`` copy a legacy one to the standard location.

    Read-only without the flag, because "which catalog am I actually using?" is a question worth
    being able to ask on its own - it is the same thing the startup banner announces.
    """
    # Via app_paths, never platformdirs directly: this must be the location this install would
    # actually use, override included. It is both what gets printed and where --move copies to.
    standard = standard_catalog_path()
    current = default_catalog_path()
    if not args.move:
        print(f"Catalog in use : {current}")
        print(f"Standard place : {standard}")
        print(f"Cache          : {cache_path_for(current)}")
        if current != standard:
            print("\n  This catalog is in the old location. To copy it to the standard place:")
            print("      truestill catalog --move")
        return 0

    result = move_catalog_to_standard(LEGACY_CATALOG_PATH, standard)
    print(result.detail)
    if result.outcome is CatalogMoveOutcome.DESTINATION_EXISTS:
        return 2
    if result.outcome is CatalogMoveOutcome.SYMLINK_REFUSED:
        return 2
    return 0


def _source_root_or_none(given: Path, destination: Path) -> Path | None:
    """A directory the scanner can read, unpacking archives first when that is what was given.

    **Any archive from any source**, not only Google Takeout: every major photo service hands a
    user a ``.zip``, and an old backup, a shared folder or a NAS dump is the same shape. Takeout
    is the motivating case, never the scope - the evidence is tabulated in `SHIPPED.md` `(jj)`.

    **Pointing at one part finds the rest.** Google splits an export across numbered files and a
    folder can straddle two of them, so requiring every part on the command line would make an
    easy mistake catastrophic - the run would succeed and quietly lose the dates in the parts
    that were left out. Siblings are gathered from the same directory instead.

    The archive route **prints the precondition report and refuses on it** before writing
    anything: a missing part, a password, a nested archive or not enough room are all far cheaper
    to learn here than 190 GB into 200.
    """
    if given.is_dir():
        return given
    if not given.is_file():
        print(f"error: not a file or directory: {given}", file=sys.stderr)
        return None

    # archives_at is shared with the app, so "what did the user point at" cannot drift between
    # the two surfaces - only the gesture differs, never the invariant that parts are discovered.
    report = precheck_archives(archives_at(given) or [given], destination)
    print(report.detail)
    if not report.may_proceed:
        return None

    print(f"Unpacking {len(report.archive_set.parts)} archive(s) ...")
    extraction = extract_archive_set(report.archive_set, destination)
    print(f"Unpacked {extraction.files_written:,} files.")
    return extraction.staging_root


def _custody_age_line(freshness: CustodyFreshness) -> str:
    """The age of the claim, said ALWAYS rather than only when it is bad.

    Reporting freshness only once it is stale teaches a reader that its absence means fresh,
    which is the same defect one level up. A date that only gets older cannot mislead. `(abg)`.
    """
    if freshness.never_checked:
        names = ", ".join(f"'{n}'" for n in freshness.never_checked)
        return f"Never checked: {names}. Truestill has not looked since the copy was written."
    if freshness.checked_at is None:
        return "Nothing is on a drive yet, so there is nothing to have checked."
    return f"Last checked: {freshness.checked_at[:10]} (the oldest of the drives holding copies)."


def _cmd_status(args: argparse.Namespace) -> int:
    with _catalog(args.db) as catalog:
        singles = catalog.single_copy_shas()
        # The same rule the app's custody strip uses, from core, so the two surfaces cannot drift.
        freshness = custody_freshness([d for d in catalog.list_drives() if d["file_count"]])
    if not singles:
        print("All catalogued content has at least two drive copies. Nicely redundant.")
        print(_custody_age_line(freshness))
        return 0
    print(f"At risk: {len(singles)} file(s) exist on only ONE drive (3-2-1 wants >=2):")
    for r in singles[:_STATUS_PREVIEW]:
        print(f"  {r['original_name'] or r['sha256'][:12]}   only on '{r['drive_label']}'")
    if len(singles) > _STATUS_PREVIEW:
        print(f"  ... and {len(singles) - _STATUS_PREVIEW} more.")
    print(_custody_age_line(freshness))
    return 0


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


#: How often a **non-terminal** run repeats its progress line. On a terminal the counter
#: overwrites itself and costs one line however often it moves; in a file or a pipe every
#: update is kept forever, so the cadence *is* the size of the log. Five seconds is a judgement
#: rather than a measurement - recorded the way `run_health.TICK_SECONDS` is - chosen so an
#: hour-long run leaves a readable ~700 lines instead of one per file.
_PROGRESS_INTERVAL_SECONDS = 5.0

#: The throttle's own clock, **deliberately not `_CLOCK`**. That one is the report's
#: elapsed-time source and tests drive it with a fixture yielding an exact number of readings;
#: a counter borrowing it consumed one of them and broke five unrelated timing tests. Two
#: measurements that have nothing to say to each other should not share one injection point.
_PROGRESS_CLOCK = time.monotonic


def _stderr_is_terminal() -> bool:
    """Whether progress is being watched by a person or captured by something.

    A function rather than a module-level constant so it is asked at the moment it matters and
    can be substituted in a test: the two branches have opposite failure modes and a guard that
    could only ever exercise one of them would be half a guard.
    """
    return sys.stderr.isatty()


def _end_of_tier() -> None:
    """Push a completed tier's report out of the buffer, now rather than at exit.

    **Ordering the writes is not enough.** Python block-buffers stdout when it is not a
    terminal, so a redirected run holds tier 0's census until the buffer fills or the process
    ends - measured before this was written: the redirect file stays *empty* for the whole of
    the slow tier. Analyze's whole promise is that a cheap answer arrives while an expensive one
    is still running, and on the 54-minute run that promise was kept in a buffer.
    """
    sys.stdout.flush()


def _progress_printer(label: str) -> ProgressCallback:
    """A progress callback for one phase of work. **Writes to stderr, never to stdout.**

    Results go to stdout and progress goes to stderr, so ``truestill analyze <path> >
    report.txt`` leaves a clean report while the terminal still shows the run - the split git
    and docker use, and the one the rest of Analyze's streaming rests on.

    The op's own phase name wins over ``label`` when it has one, so a run that hashes and then
    copies says which it is doing rather than showing one pace for two different jobs.

    **The two branches are not cosmetic.** On a terminal, ``\r`` rewrites one line. Written to a
    file it is *stored*, so the same code left one padded 60-column counter per file - **127 KB
    of unreadable scrollback** on a real 32,628-file run. A non-terminal therefore gets no
    carriage return, no padding, and a line only every `_PROGRESS_INTERVAL_SECONDS` or at the
    end: without ``\r`` to overwrite with, one line per file is the same flood in a new shape.
    """
    last = _PROGRESS_CLOCK()

    def report(update: Progress) -> None:
        what = update.phase or label
        done = update.done >= update.total
        if _stderr_is_terminal():
            # Padded so the shorter line of a phase change fully overwrites the longer previous.
            end = "\n" if done else "\r"
            print(
                f"  {what}: {update.done}/{update.total}".ljust(60),
                end=end,
                file=sys.stderr,
                flush=True,
            )
            return
        nonlocal last
        now = _PROGRESS_CLOCK()
        if not done and now - last < _PROGRESS_INTERVAL_SECONDS:
            return
        last = now
        print(f"  {what}: {update.done}/{update.total}", file=sys.stderr, flush=True)

    return report


def _build_destination(spec: str, *, rclone: bool) -> Destination:
    if rclone:
        return RcloneDestination(spec)
    return LocalDestination(Path(spec))


def _local_drive_marker(args: argparse.Namespace) -> DriveMarker | None:
    """Drive identity of a local destination, if it carries a ``.truestill-drive.json`` marker.

    rclone remotes are always-online cloud, not drives-in-a-drawer, so drive tracking is scoped
    to local destinations. A local root without a marker is fine -- copies just aren't tracked
    per-drive until `truestill drives init` is run there.
    """
    if args.rclone:
        return None
    return read_marker(Path(args.destination))


def _short_sha(sha256: str | None) -> str:
    return f"{sha256[:16]}..." if sha256 else "(not hashed: unique size)"


def _format_new(resolution: Resolution, root_label: str) -> str:
    decision = resolution.decision
    when = decision.captured_at.strftime("%Y-%m-%d %H:%M:%S") if decision.captured_at else "-"
    # Only sources that name a metadata tag get a `tag=` part. Falling back to the source
    # name printed it twice ("source=none, tag=none"), which reads as a second, corroborating
    # piece of evidence when it is just the same word again.
    origin = (
        f"source={decision.date_source.value}"
        if decision.date_tag is None
        else f"source={decision.date_source.value}, tag={decision.date_tag}"
    )
    flag = "  <-- REVIEW" if decision.needs_review else ""
    # Three states, not two. `perceptual is None` used to render "not an image" whatever the
    # reason, so a run that never hashed the pixels told a user their photograph was not one -
    # 392 of 403 JPEGs on a real library. The fingerprint, the honest absence, or the honest
    # "we did not look".
    hashes = resolution.hashes
    if hashes.perceptual:
        phash = hashes.perceptual
    elif hashes.perceptual_computed:
        phash = "n/a (not an image)"
    else:
        phash = "not compared for look-alikes"
    lines = [
        f"  {decision.source.name}",
        (
            f"      category : {decision.category.label}  "
            f"[{decision.category.confidence.value} confidence, rule={decision.category.rule}]"
        ),
        f"      why      : {decision.category.reason}",
        f"      date     : {when}  ({origin}){flag}",
        f"      sha256   : {_short_sha(resolution.hashes.sha256)}    dhash: {phash}",
    ]
    if resolution.near_duplicate is not None:
        near = resolution.near_duplicate
        distance = f", distance={near.distance}" if near.distance is not None else ""
        # Origin wording comes from the shared home so the CLI and the app cannot describe the
        # same match differently (ENGINEERING_STANDARD.md §4); the report's own layout stays.
        lines.append(
            f"      NEAR-DUP  : looks like {near.matched_path} "
            f"[{origin_phrase(near.origin)}{distance}]"
        )
        lines.append("                  organized anyway (kept, not dropped) - review manually")
    lines.append(f"      -> {root_label}/{decision.relative.as_posix()}")
    return "\n".join(lines)


def _format_exact(resolution: Resolution) -> str:
    match = resolution.exact_duplicate
    if match is None:  # pragma: no cover - only called for exact duplicates
        return f"  {resolution.decision.source.name}  [not a duplicate]"
    return (
        f"  {resolution.decision.source.name}  [SKIP: exact duplicate]\n"
        f"      identical to : {match.matched_path}\n"
        f"      via          : SHA-256, {origin_phrase(match.origin)}"
    )


def _print_duplicate_origins(resolutions: Iterable[Resolution], indent: str = "  ") -> None:
    """Name where the skipped duplicates' twins are, beneath whatever counted them.

    Printed on every surface that shows a duplicate count, because a person meets that number
    in three places and one of them saying less than the others is how a report stops being
    trusted. The phrases come from `duplicate_explain`, so the tally and the per-file line
    cannot describe the same match in two vocabularies.
    """
    matches = [r.exact_duplicate for r in resolutions if r.exact_duplicate is not None]
    for line in describe_split(split_by_origin(matches)):
        print(f"{indent}{line}")


def _has_move_semantics(args: argparse.Namespace, relocation: Relocation | None) -> bool:
    """Whether this run takes the originals. ``--in-place`` is a move that never leaves the
    drive, so it reaches the same answer through `relocation` rather than through the flag."""
    return bool(getattr(args, "move", False)) or relocation is not None


def _print_will_remain(
    args: argparse.Namespace, relocation: Relocation | None, resolutions: list[Resolution]
) -> None:
    """What a move preview says about the files it will not take. Nothing, when there are none.

    Counted over every match rather than a sample, and only over the catalog origin: a twin
    found earlier in this same batch will still be moved in by this run, so it is not a file
    that stays behind.
    """
    if not _has_move_semantics(args, relocation):
        return
    matches = [r.exact_duplicate for r in resolutions if r.exact_duplicate is not None]
    line = will_remain_line(split_by_origin(matches).already_in_library)
    if line is not None:
        print(f"\n  {line}")


def _print_left_in_source(
    args: argparse.Namespace, relocation: Relocation | None, results: list[ActionResult]
) -> None:
    """What the move left in the source, after the fact. Nothing, when it left nothing."""
    if not _has_move_semantics(args, relocation):
        return
    for line in describe_left_behind(files_left_in_source(results, args.source)):
        print(f"  {line}")


def _print_report(resolutions: list[Resolution], root_label: str) -> None:
    # Disjoint buckets, not `should_upload`: an unreadable file has no hash, so it matches
    # nothing and would otherwise be listed under "NEW UNIQUE - would be organized" while the
    # block below says Truestill could not read it. `_print_unreadable` names them instead.
    buckets = partition_for_report(resolutions)
    unique = buckets.unique
    near = buckets.near_duplicates
    exact = buckets.exact_duplicates

    print(_SEPARATOR)
    print(f"NEW UNIQUE ({len(unique)}) - would be organized")
    print(_SEPARATOR)
    for resolution in unique:
        print(_format_new(resolution, root_label))
        print()

    print(_SEPARATOR)
    print(f"NEAR-DUPLICATES ({len(near)}) - KEPT and flagged for your review")
    print(_SEPARATOR)
    if not near:
        print("  (none)")
    for resolution in near:
        print(_format_new(resolution, root_label))
        print()

    print(_SEPARATOR)
    print(f"EXACT DUPLICATES ({len(exact)}) - skipped, not organized")
    _print_duplicate_origins(exact)
    print(_SEPARATOR)
    if not exact:
        print("  (none)")
    for resolution in exact:
        print(_format_exact(resolution))
        print()


def _print_skipped_undated(resolutions: list[Resolution], skip_undated: bool) -> None:
    """Name every undateable file that --skip-undated left behind. Never silent."""
    if not skip_undated:
        return
    undated = [r for r in resolutions if r.should_upload and r.decision.captured_at is None]
    if not undated:
        return
    print(f"\n  SKIPPED (undated -- not copied, --skip-undated): {len(undated)}")
    for r in undated:
        print(f"      {r.decision.source.name}")


def _print_heif_note(resolutions: list[Resolution]) -> None:
    """If HEIC/HEIF files were seen but pillow-heif is unavailable, say so -- never silent."""
    if HEIF_AVAILABLE:
        return
    heic = [r for r in resolutions if r.decision.source.suffix.lower() in HEIF_EXTENSIONS]
    if heic:
        print(
            f"\n  NOTE: {len(heic)} HEIC/HEIF file(s) were exact-deduplicated but NOT perceptually "
            "hashed -- pillow-heif is unavailable, so near-duplicate detection was skipped for them."
        )


def _print_date_quality(uploads: list[Resolution]) -> None:
    """Disclose the two date-quality signals. Each prints only when non-zero, and neither is
    ever folded into the plain 'undated' count -- that is the whole point of counting them."""
    quality = date_quality(uploads)
    if quality.sentinel_rejected:
        print(
            f"  {quality.sentinel_rejected} file(s) carried only a placeholder date"
            " (1904/1970 epoch zero); it was refused and they went to Undated/"
        )
    if quality.future_rejected:
        print(
            f"  {quality.future_rejected} file(s) claimed a capture date in the future;"
            " it was refused and they went to Undated/ (a wrong device clock, or edited"
            " metadata -- the original date cannot be recovered)"
        )
    if quality.suspect_default:
        print(
            f"  {quality.suspect_default} file(s) dated by a suspicious camera-default"
            " timestamp (exact midnight on a known clock-reset day) --"
            " filed by that date, worth a look"
        )


def _print_inferred_local_shifts(uploads: list[Resolution]) -> None:
    """Name each video shifted from UTC CreateDate - never a count alone.

    ``not_proven_utc`` fallthrough is EXIF and is not listed (usually correct local digits).
    """
    shifts = inferred_local_shifts(uploads)
    if not shifts:
        return
    print(f"  {len(shifts)} video(s) shifted from UTC CreateDate:")
    for shift in shifts:
        print(f"      {format_inferred_local_shift_line(shift)}")


def _print_preflight(
    resolutions: list[Resolution], destination: Destination, *, skip_undated: bool
) -> None:
    """Say up front when the destination cannot hold this run.

    Printed during a **preview**, where nothing is written and the refusal would be pointless:
    a plan that reads as clean and then fails on ``--apply`` moves the discovery to after the
    user has already committed. ``execute`` refuses the apply itself, from the same answer, so
    this is a second reading rather than a second check.
    """
    preflight = preflight_for_run(resolutions, destination, skip_undated=skip_undated)
    if preflight.may_proceed:
        return
    print(f"\n{_SEPARATOR}")
    print("THIS DESTINATION CANNOT HOLD THIS RUN")
    print(_SEPARATOR)
    print(f"  {preflight.detail()}")


#: Largest files named before the list elides. Small on purpose: this answers "what is eating
#: the space", which the top handful settles; a longer list is a file manager's job.
_LARGEST_PREVIEW = 5


def _print_capture_timeline(resolutions: list[Resolution]) -> None:
    """The date range and a per-year count. Printed even when empty, so it can be added up.

    **Counts, not bars.** A real library spans three orders of magnitude between its quietest
    and busiest year, so a linear bar saturates on one year and says nothing, and a log bar
    makes a visual claim about proportion that is not true. Aligned numbers answer the question
    a timeline is actually asked - which years do I have, and how much - without decorating it.
    Rendered as a compact `YYYY x N` sequence in the same idiom as the format census, wrapped
    rather than one line per year, because twenty lines of two numbers is not a summary.
    """
    span = capture_span(resolutions)
    years = capture_years(resolutions)
    if span is None:
        print("  capture dates      : none of these files carries a capture date")
    else:
        print(
            f"  capture dates      : {span.oldest.date().isoformat()} "
            f"to {span.newest.date().isoformat()}"
        )
    entries = [f"{year} x{count:,}" for year, count in years.by_year.items()]
    for line in _wrapped(entries, width=_EXTENSION_LINE_BUDGET):
        print(f"      {line}")
    # Never folded into a year: a file with no date belongs to none of them, and dropping it
    # would make the histogram disagree with the file count.
    print(f"      undated x{years.undated:,}")


def _print_duplicate_space(resolutions: list[Resolution], sizes: dict[Path, int]) -> None:
    """What duplicates cost, with reclaimable space kept strictly apart from look-alikes.

    A near-duplicate is **kept** - uploaded and flagged for review - so no operation returns
    its bytes. Calling them saved would promise space that never arrives, which is why the two
    lines are worded differently rather than summed.
    """
    counted = duplicate_bytes(resolutions, sizes)
    print(
        f"  identical copies   : {counted.exact_files:,} file(s), "
        f"{counted.reclaimable_bytes:,} bytes not copied"
    )
    print(
        f"  look-alikes        : {counted.near_files:,} file(s), "
        f"{counted.near_bytes:,} bytes (kept and flagged, not removed)"
    )


def _print_largest(sizes: dict[Path, int]) -> None:
    """The biggest files, capped, with the total exact."""
    listed = largest_files(sizes, limit=_LARGEST_PREVIEW)
    if not listed.shown:
        return
    print(f"  largest files      : {listed.total:,} sized")
    for entry in listed.shown:
        print(f"      {entry.size / 1e6:>10,.1f} MB  {entry.path.name}")
    hidden = listed.total - len(listed.shown)
    if hidden:
        print(f"      ... and {hidden:,} more")


def _wrapped(entries: list[str], *, width: int) -> list[str]:
    """Join ``entries`` into lines no wider than ``width``. Never drops one."""
    lines: list[str] = []
    current: list[str] = []
    used = 0
    for entry in entries:
        if current and used + len(entry) + 2 > width:
            lines.append(", ".join(current))
            current, used = [], 0
        current.append(entry)
        used += len(entry) + 2
    if current:
        lines.append(", ".join(current))
    return lines


def _print_summary(resolutions: list[Resolution]) -> None:
    buckets = partition_for_report(resolutions)
    organized = buckets.organized
    labels = Counter(r.decision.category.label for r in organized)
    sources = Counter(r.decision.date_source.value for r in organized)

    print(_SEPARATOR)
    print("SUMMARY")
    print(_SEPARATOR)
    # These four must sum to `files analysed`. The buckets are disjoint by construction
    # (`partition_for_report`) and the sum is asserted by `test_summary_tally_is_disjoint`;
    # the zero case still prints, because a law a reader cannot add up is not on screen.
    print(f"  files analysed     : {len(resolutions)}")
    print(f"  organized (unique)  : {len(buckets.unique)}")
    print(f"  organized (near-dup): {len(buckets.near_duplicates)}  (kept + flagged for review)")
    print(f"  skipped (exact dup): {len(buckets.exact_duplicates)}")
    print(f"  could not be read  : {len(buckets.unreadable)}")
    print(f"  folders derived    : {len(labels)}")
    for label, count in labels.most_common():
        print(f"      {label:<28} {count}")
    print("  date sources (organized files):")
    for source, count in sources.most_common():
        print(f"      {source:<28} {count}")
    _print_date_quality(organized)
    _print_inferred_local_shifts(organized)
    # Sized once, here, and shared by both blocks below: one stat pass rather than two.
    sizes = sizes_for(resolutions)
    _print_capture_timeline(organized)
    _print_duplicate_space(resolutions, sizes)
    _print_largest(sizes)

    review = [r for r in organized if r.decision.needs_review]
    if review:
        print(f"\n  MANUAL REVIEW ({len(review)}) - date from an approximate source:")
        origin_labels = {
            DateSource.FILENAME: "filename pattern",
            DateSource.TAKEOUT_UPLOAD: "upload time (approximate)",
        }
        for resolution in review:
            origin = origin_labels.get(resolution.decision.date_source, "approximate")
            print(f"      {resolution.decision.source.name}  [{origin}]")


def _match_json(match: DuplicateMatch | None) -> dict[str, object] | None:
    if match is None:
        return None
    return {
        "kind": match.kind.value,
        "matched_path": match.matched_path,
        "origin": match.origin,
        "distance": match.distance,
    }


def _write_json_report(path: Path, resolutions: list[Resolution]) -> None:
    payload = [
        {
            "source": str(r.decision.source),
            "relative": r.decision.relative.as_posix(),
            "category": r.decision.category.label,
            "confidence": r.decision.category.confidence.value,
            "rule": r.decision.category.rule,
            "reason": r.decision.category.reason,
            "captured_at": r.decision.captured_at.isoformat() if r.decision.captured_at else None,
            "date_source": r.decision.date_source.value,
            "date_tag": r.decision.date_tag,
            "needs_review": r.decision.needs_review,
            "sha256": r.hashes.sha256,
            "perceptual": r.hashes.perceptual,
            "should_upload": r.should_upload,
            "is_unique": r.is_unique,
            "exact_duplicate": _match_json(r.exact_duplicate),
            "near_duplicate": _match_json(r.near_duplicate),
        }
        for r in resolutions
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"\n  JSON report written to {path}")


def _print_mechanism_split(results: list[ActionResult]) -> None:
    """State how files actually got there: renamed in place, or copied across devices.

    A run can legitimately do both -- a source folder spanning two filesystems renames what it
    can and copies the rest -- and the difference decides how much space was used and what is
    undoable. Reporting only the total would hide both.
    """
    renamed = sum(1 for r in results if r.status is ActionStatus.MOVED_IN_PLACE)
    copied = sum(1 for r in results if r.status in (ActionStatus.MOVED, ActionStatus.MOVE_KEPT))
    already = sum(1 for r in results if r.status is ActionStatus.ALREADY_PLACED)
    if not renamed and not already:
        return
    parts = []
    if renamed:
        parts.append(f"{renamed} moved by rename (no bytes copied)")
    if copied:
        parts.append(f"{copied} copied across devices")
    if already:
        parts.append(f"{already} already in place")
    print(f"  {' · '.join(parts)}")
    if renamed:
        print("  Reverse this run with: truestill undo-organize")


def _print_execution(results: list[ActionResult]) -> int:
    # Human wording, shared with the app: 'uploaded' is backend vocabulary for an event
    # that did not happen on a local disk, and never reaches a user.
    outcomes = Counter(status_label(result.status) for result in results)
    print(_SEPARATOR)
    print("EXECUTED")
    print(_SEPARATOR)
    for status, count in outcomes.most_common():
        print(f"  {count:>7}  {status}")
    _print_duplicate_origins((r.resolution for r in results), indent="           ")
    _print_mechanism_split(results)

    kept = [r for r in results if r.status is ActionStatus.MOVE_KEPT]
    for k in kept:
        print(f"  MOVE KEPT: {k.resolution.decision.source.name}: {k.detail}", file=sys.stderr)

    failures = [r for r in results if r.status is ActionStatus.FAILED]
    for failure in failures:
        print(
            f"  FAILED: {failure.resolution.decision.source.name}: {failure.detail}",
            file=sys.stderr,
        )
    return 1 if failures else 0


def _build_ingest_context(
    decisions: list[Decision], metadata: dict[Path, dict[str, Any]], scan: TakeoutScan
) -> IngestContext:
    """Bake plan: write a rescued date into a copy only when it lacks a good embedded one;
    add sidecar GPS only when the file has none; always carry a description."""
    writes: dict[str, MetadataWrite] = {}
    for decision in decisions:
        sidecar = scan.sidecars.get(decision.source)
        if sidecar is None:
            continue
        from_takeout = decision.date_source in (DateSource.TAKEOUT, DateSource.TAKEOUT_UPLOAD)
        taken = decision.captured_at if from_takeout else None
        has_exif_gps = "GPSLatitude" in metadata.get(decision.source, {})
        gps = sidecar.gps if (sidecar.gps is not None and not has_exif_gps) else None
        write = MetadataWrite(taken_at_local=taken, gps=gps, description=sidecar.description)
        if write.has_content:
            writes[str(decision.source)] = write
    albums = {str(path): name for path, name in scan.albums.items()}
    return IngestContext(writes=writes, albums=albums)


def _safe_size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


def _print_ingest_report(resolutions: list[Resolution], scan: TakeoutScan) -> None:
    # `ingest` shares `_run_pipeline`, so it already prints the unreadable block - which made it
    # carry the identical contradiction: a file named as unreadable and counted as kept.
    buckets = partition_for_report(resolutions)
    uploads = buckets.organized
    duplicates = buckets.exact_duplicates
    sources = Counter(r.decision.date_source.value for r in uploads)
    reclaimed = sum(_safe_size(r.decision.source) for r in duplicates)

    print(_SEPARATOR)
    print("TAKEOUT RESCUE REPORT")
    print(_SEPARATOR)
    print(f"  media files found                : {len(resolutions)}")
    print(f"  kept (unique)                    : {len(uploads)}")
    print(f"  could not be read                : {len(buckets.unreadable)}")
    print(
        f"  album duplicate copies collapsed : {len(duplicates)}  (~{reclaimed / 1e6:.1f} MB reclaimed)"
    )
    print(f"  dates recovered (photoTakenTime) : {sources.get(DateSource.TAKEOUT.value, 0)}")
    print(f"  dates approximate (upload time)  : {sources.get(DateSource.TAKEOUT_UPLOAD.value, 0)}")
    print(f"  dates from embedded EXIF         : {sources.get(DateSource.EXIF.value, 0)}")
    print(f"  dates from filename              : {sources.get(DateSource.FILENAME.value, 0)}")
    print(f"  still undated                    : {sources.get(DateSource.NONE.value, 0)}")
    quality = date_quality(uploads)
    print(
        f"  placeholder date refused         : {quality.sentinel_rejected}"
        "  (epoch zero -> Undated/)"
    )
    print(
        f"  future date refused              : {quality.future_rejected}  (after today -> Undated/)"
    )
    print(f"  suspicious camera-default dates  : {quality.suspect_default}  (filed, worth a look)")
    shifts = inferred_local_shifts(uploads)
    if shifts:
        print(f"  videos shifted from UTC CreateDate: {len(shifts)}")
        for shift in shifts:
            print(f"      {format_inferred_local_shift_line(shift)}")
    print(f"  media without any JSON sidecar   : {len(scan.missing_sidecar)}")
    print(
        "  note: Takeout times are UTC; near midnight a date may shift a day -- pass --tz to correct."
    )


def _register_destination(
    args: argparse.Namespace, marker: DriveMarker | None
) -> DriveMarker | None:
    """Give the destination a drive identity before the run, so the run's own files attach.

    **The gap this closes.** Until 2026-08-05 the CLI read a marker and never created one, so
    organizing into an ordinary folder wrote `files` rows with **no** `file_copies` row: in the
    dedup index, so a re-run skips those files forever, and outside custody, so `verify`,
    `status` and `where` cannot see them. The app has done the opposite since the bug it
    replaced - `service/organize.py` does `read_marker(dest) or create_marker(dest, ...)` with a
    comment saying that doing it afterwards "would leave the run's own files unattached". Same
    operation, two custody outcomes, decided by which surface the user picked.

    `IMPLEMENTATION_STANDARDS.md` §3.1 already sanctions the creation - it "happens automatically
    where the user's action already implies it", and names the organize destination.

    **Gated on ``--apply``**, so a preview registers nothing; that is why no opt-out flag was
    added rather than one being argued for. **rclone destinations are excluded**, for the reason
    `_local_drive_marker` gives: always-online cloud is not a drive-in-a-drawer.

    An existing marker is returned untouched - re-minting a uuid would orphan every copy already
    recorded against the old one (§3.1).
    """
    if marker is not None or not getattr(args, "apply", False) or args.rclone:
        return marker
    root = Path(args.destination)
    with _catalog(args.db) as catalog:
        drives = [(str(d["uuid"]), str(d["label"])) for d in catalog.list_drives()]
        ghost = ghost_drive_at(root, catalog, drives)
        if ghost is not None and not getattr(args, "force_new_identity", False):
            raise DriveGhostError(ghost_drive_refusal(ghost))
        unplaced = drives_without_a_known_location(catalog, drives)
    if unplaced and not _confirm_new_drive(unplaced, root):
        cancelled = "Registration cancelled. Nothing was written and no drive was registered."
        raise DriveGhostError(cancelled)
    created = create_marker(root, label=root.name or "Library")
    with _catalog(args.db) as catalog:
        # Record WHERE, not just that it happened. Five other sites write this hint and this one
        # did not, which is why a CLI-only user accumulates drives whose location is unknown -
        # and why nothing could tell an unmounted mountpoint from a new folder.
        catalog.set_setting(drive_path_hint(created.uuid), str(root))
    print(f"Registered '{created.label}' as a drive so its copies can be verified.")
    return created


def _confirm_new_drive(unplaced: tuple[str, ...], root: Path) -> bool:
    """Ask before minting a SECOND identity while known drives have no recorded location.

    **A confirm rather than a refusal**, deliberately. With no recorded path there is no way to
    tell an empty folder that is one of those drives from an empty folder that is new, so
    refusing would block legitimate work. The friction lands once, on a first ``--apply``, and it
    shrinks by itself: every registration from now on records where it happened.
    """
    named = ", ".join(f"'{label}'" for label in unplaced)
    print(_SEPARATOR)
    print("REGISTERING A NEW DRIVE")
    print(_SEPARATOR)
    print(f"  {root} will be registered as a new drive.")
    print(f"  Truestill already knows {named} but has no record of where it is.")
    print("  If this folder IS one of them and it is simply not mounted, stop: writing here")
    print("  would put files on this computer's disk, and they would DISAPPEAR from view when")
    print("  the drive came back - while still using the space.")
    return _typed_confirmation("\nType 'new' if this really is a new drive: ", "new") is True


def _registered_or_refused(
    args: argparse.Namespace, marker: DriveMarker | None, catalog: Catalog
) -> tuple[DriveMarker | None, str | None] | int:
    """The destination's drive identity and uuid, or the exit code to return.

    Shaped like `_destination_or_exit` and for the same reason: the refusal is an actionable
    sentence rather than a traceback (ENGINEERING_STANDARD 4), and doing the upsert here keeps
    `_run_pipeline` under its branch ceiling rather than raising the ceiling.
    """
    try:
        resolved = _register_destination(args, marker)
    except DriveGhostError as refusal:
        # Exit 4 is this repo's "unusable destination", alongside 3 for a missing exiftool.
        print(f"error: {refusal}", file=sys.stderr)
        return 4
    if resolved is None:
        return None, None
    catalog.upsert_drive(uuid=resolved.uuid, label=resolved.label)
    print(f"Destination is drive '{resolved.label}' ({resolved.uuid[:8]}...).\n")
    return resolved, resolved.uuid


def _run_pipeline(
    args: argparse.Namespace,
    files: list[Path],
    metadata: dict[Path, dict[str, Any]],
    destination: Destination,
    *,
    takeout: dict[Path, TakeoutSidecar] | None = None,
    tz_offset: timedelta | None = None,
    prefer_takeout: bool = False,
    scan: TakeoutScan | None = None,
    event_prompt: Prompt | None = None,
    drive_marker: DriveMarker | None = None,
    relocation: Relocation | None = None,
) -> int:
    with _catalog(args.db) as catalog, HashCache.beside(args.db) as cache:
        if getattr(args, "apply", False) and pin_existing_layout(catalog):
            print(_PINNED_NOTICE)
        scheme = resolve_scheme(catalog)
        rules = build_rules(by_device=args.by_device)
        heavy = heavy_days_for_organize(
            catalog,
            files,
            metadata,
            rules,
            takeout=takeout,
            tz_offset=tz_offset,
            prefer_takeout=prefer_takeout,
        )
        decisions = plan(
            files,
            metadata,
            rules,
            rename=not args.no_rename,
            takeout=takeout,
            tz_offset=tz_offset,
            prefer_takeout=prefer_takeout,
            scheme=scheme,
            heavy_days=heavy,
        )
        ingest_ctx = _build_ingest_context(decisions, metadata, scan) if scan is not None else None

        index = DedupIndex.from_catalog_rows(catalog.seed_rows(), args.phash_threshold)
        if catalog.count():
            print(f"Catalog {args.db} holds {catalog.count()} previously-processed file(s).\n")

        resolved = _registered_or_refused(args, drive_marker, catalog)
        if isinstance(resolved, int):
            return resolved
        drive_marker, drive_uuid = resolved

        resolutions = resolve(
            decisions,
            index,
            catalog_sizes=catalog.known_sizes(),
            pool=args.pool,
            workers=args.workers,
            progress=_progress_printer("hashing"),
            cache=cache,
        )

        events: dict[str, Event] = {}
        if args.events or event_prompt is not None:
            resolutions, events = run_event_stage(
                resolutions,
                metadata,
                catalog,
                apply=args.apply,
                prompt=event_prompt,
                scheme=scheme,
            )

        _print_report(resolutions, destination.describe())
        _print_summary(resolutions)
        _print_skipped_undated(resolutions, args.skip_undated)
        _print_heif_note(resolutions)
        _print_preflight(resolutions, destination, skip_undated=args.skip_undated)
        if scan is not None:
            _print_ingest_report(resolutions, scan)
        if args.report:
            _write_json_report(args.report, resolutions)

        if relocation is not None and args.apply:
            catalog.start_inplace_run(
                run_id=relocation.run_id,
                source_root=str(relocation.source_root),
                dest_root=str(relocation.dest_root),
                drive_uuid=drive_uuid,
            )

        try:
            results = execute(
                resolutions,
                destination,
                catalog,
                apply=args.apply,
                set_timestamps=not args.no_timestamps,
                skip_undated=args.skip_undated,
                move=getattr(args, "move", False),
                relocation=relocation if args.apply else None,
                events=events,
                ingest=ingest_ctx,
                drive_uuid=drive_uuid,
                progress=_progress_printer("moving" if relocation else "copying")
                if args.apply
                else None,
            )
        except DestinationError as exc:
            # A destination that cannot hold the run refuses before the first byte. That is a
            # user-facing answer, not a crash: it names the files and exits like every other
            # destination problem (code 4), rather than showing a traceback.
            print(f"error: {exc}", file=sys.stderr)
            return 4

        if relocation is not None and args.apply:
            moved = sum(1 for r in results if r.status is ActionStatus.MOVED_IN_PLACE)
            # A run that renamed nothing leaves no journal row to offer as an undo.
            if moved:
                catalog.finish_inplace_run(relocation.run_id)
            else:
                catalog.discard_inplace_run(relocation.run_id)

    print()
    if not args.apply:
        # Nothing was copied, so nothing can have FAILED: a preview names every unreadable
        # source, or no one does.
        unreadable = _print_unreadable(resolutions)
        # What a move will NOT take, stated before the user commits to it and above the DRY RUN
        # banner so it is read as part of the plan. A move only: a copy leaves every original
        # where it is by definition, so there is nothing the user did not already ask for.
        _print_will_remain(args, relocation, resolutions)
        print(_SEPARATOR)
        print("DRY RUN - nothing was written or recorded. Re-run with --apply to execute.")
        print(_SEPARATOR)
        # A preview's job is to predict the run. The run will exit 1 on these files through
        # `ActionStatus.FAILED`, so predicting them with a 0 would make `organize && next_step`
        # chain past a library Truestill could not fully account for. Code 1 is already this
        # CLI's "finished, but something is wrong" (verify, organize, reclaim all use it).
        return 1 if unreadable else 0
    code = _print_execution(results)
    # And what it left, after the fact. The result answers a different question from the
    # preview - not what will happen, but what to do now - and it is the only place the files
    # still sitting in the source are explained at all: the empty-folder offer that follows
    # names the folders the move DID empty and is silent about these by construction.
    _print_left_in_source(args, relocation, results)
    failed = frozenset(
        r.resolution.decision.source for r in results if r.status is ActionStatus.FAILED
    )
    # Whatever FAILED has already been named above; this catches the rest - most often an
    # unreadable file whose cached hashes made it an exact duplicate, so it was never copied
    # and never failed, and would otherwise be the one file nobody mentions.
    named = _print_unreadable(resolutions, failed)
    return code or (1 if named else 0)


def _fmt_extensions(paths: list[Path]) -> str:
    counts = Counter(p.suffix.lower() or "(no ext)" for p in paths)
    return ", ".join(f"{ext} x{n}" for ext, n in counts.most_common())


def _print_unreadable(
    resolutions: Sequence[Resolution], failed: frozenset[Path] = frozenset()
) -> int:
    """Name the source files that could not be read. Returns how many were named.

    **Printed from the resolutions rather than from the scan**, because that is the one place
    both surfaces meet: a preview and a run reach it through the same `_run_pipeline`, so the
    two cannot describe the same library differently. `scan_source` never opens a file and so
    has no opinion to offer here - its `unreadable_dirs` is a different fact, gathered by the
    walk itself.

    ``failed`` is the set of sources that already produced an `ActionStatus.FAILED`, which only
    a run can have. Those are subtracted: `_print_execution` has already named them with the
    real ``OSError`` text, and that is the better line of the two - later, and more specific.
    On a preview the set is empty, so a preview names every one.
    """
    named = [
        r
        for r in resolutions
        if r.hashes.unreadable is not None and r.decision.source not in failed
    ]
    if not named:
        return 0
    print("\nFiles that could not be read:")
    # A count here, and deliberately NONE on the "folders that could not be read" line above.
    # For a folder the number of files inside is exactly what could not be read, so printing
    # one would invent the missing figure; for a file the number is known exactly. The
    # asymmetry is the point, not an oversight - do not "make these consistent".
    print(f"  files that could not be read: {len(named)}")
    for resolution in named[:_STATUS_PREVIEW]:
        reason: UnreadableReason | None = resolution.hashes.unreadable
        assert reason is not None  # filtered above; narrows for the type checker
        print(f"      {resolution.decision.source.name}  ({unreadable_label(reason)})")
    if len(named) > _STATUS_PREVIEW:
        print(f"  ... and {len(named) - _STATUS_PREVIEW} more.")
    print("    (not organized; fix the permission or check the disk, then run again)")
    return len(named)


def _print_skipped(scan: SourceScan) -> None:
    """Account for every file that was NOT organized, grouped by kind. Never silent."""
    if not (scan.documents or scan.unrecognized or scan.exiftool_backups or scan.unreadable_dirs):
        return
    print("\nSkipped (not organized):")
    if scan.documents:
        print(f"  documents: {len(scan.documents)}  ({_fmt_extensions(scan.documents)})")
    if scan.unrecognized:
        print(f"  unrecognized: {len(scan.unrecognized)}  ({_fmt_extensions(scan.unrecognized)})")
        print(
            "    (not recognized as media; some may be video formats Truestill does not organize yet)"
        )
    if scan.exiftool_backups:
        print(f"  exiftool backup: {len(scan.exiftool_backups)}")
    if scan.unreadable_dirs:
        # Folders, named - and deliberately WITHOUT a file count. The number inside is exactly
        # what could not be read, so printing one would invent the missing figure. Every other
        # line above counts files Truestill decided about; this one names places it could not
        # see into.
        print(f"  folders that could not be read: {len(scan.unreadable_dirs)}")
        for folder in scan.unreadable_dirs:
            print(f"      {folder}  (contents unknown)")
        print("    (check the folder's permissions, then run again to include what is inside)")


#: What tier 0 deliberately does not know, and what would answer each today. Named rather than
#: rendered as zero: nothing looked, so "0 duplicates" would not be a finding but the absence of
#: one - `(aac)`'s rule applied to a whole tier instead of a single file.
#: How many extensions one census line names before it elides the rest. Chosen to keep a census
#: line inside about two 80-column terminal lines, which is the constraint a real library
#: actually broke: 279 unrecognized files carried 200+ distinct one-off extensions (truncated
#: transfer artefacts) and printing them all buried the rest of the report.
_EXTENSION_PREVIEW = 12

#: Below this, a files-per-second figure describes interpreter startup and the page cache rather
#: than the source, so it is withheld rather than shown. Same accurate-or-absent rule the
#: progress display already applies to time remaining: a number that swings teaches a user to
#: distrust the whole display.
#: And a width bound alongside the count, because a count alone does not bound a line: the real
#: library's artefacts were ~25 characters each, so twelve of them still overflowed. Roughly two
#: 80-column lines, leaving room for the label and the elision note.
_EXTENSION_LINE_BUDGET = 120

_RATE_FLOOR_SECONDS = 1.0

_SECONDS_PER_MINUTE = 60

#: The clock the analyze report times itself with, named so a test can inject one rather than
#: sleep. An intermittent gate is worse than none.
_CLOCK = time.monotonic


def _format_extension_census(counts: Mapping[str, int]) -> str:
    """``ext xN`` for the most common extensions, then how many were elided.

    **Only the enumeration is capped; the caller's total is untouched.** A cap that also
    changed a count would be the tally-conservation defect in a new place.

    Ordered by count so the informative entries survive - ``.db x32`` says something, one
    ``.us0130646897127380003-31`` does not - with the name as a tie-break so the same source
    renders identically on every platform.

    The note counts how many elided extensions were seen **once**, and stops there. The real
    library's tail looked like truncated transfers, but this report cannot know that, and a
    census that guesses at causes is worth less than one that counts.
    """
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    shown: list[str] = []
    width = 0
    for ext, n in ranked[:_EXTENSION_PREVIEW]:
        entry = f"{ext} x{n:,}"
        # Two bounds, tighter wins. A count alone does not bound the line: the artefacts that
        # caused this are ~25 characters each, so twelve of them still overflow a terminal.
        if shown and width + len(entry) + 2 > _EXTENSION_LINE_BUDGET:
            break
        shown.append(entry)
        width += len(entry) + 2
    listed = ", ".join(shown)
    hidden = ranked[len(shown) :]
    if not hidden:
        return listed
    singletons = sum(1 for _ext, n in hidden if n == 1)
    tail = f", and {len(hidden):,} more"
    if singletons:
        tail += f" ({singletons:,} seen once each)"
    return listed + tail


def _format_duration(seconds: float) -> str:
    """A wall time that reads naturally at both ends of this command's range."""
    if seconds < 1:
        return f"{seconds:.2f} s"
    if seconds < _SECONDS_PER_MINUTE:
        return f"{seconds:.1f} s"
    minutes, rest = divmod(int(seconds), _SECONDS_PER_MINUTE)
    return f"{minutes} min {rest} s"


_NOT_YET_ANALYSED = (
    ("dates", "the capture-date range, and how many files carry no trustworthy date"),
    ("duplicates", "identical copies, and the space they waste"),
    ("look-alikes", "the same photo at a different size or quality (decodes every image)"),
)


def _rate_note(files: int, elapsed: float) -> str:
    """`` (N files/second)``, or nothing when the run was too short for that to mean anything.

    The rate is what separates a slow *mount* from a large *library*, which is the distinction
    a user needs before committing to the expensive tiers. Below `_RATE_FLOOR_SECONDS` it
    separates nothing, so it is not printed. This is an observation about one run on one
    source, never a benchmark - `PERFORMANCE.md` owns those and their method.
    """
    if elapsed < _RATE_FLOOR_SECONDS or not files:
        return ""
    return f"  ({round(files / elapsed):,} files/second)"


def _print_inventory(inventory: SourceInventory, source: Path, elapsed: float) -> None:
    """The tier-0 census.

    Kind counts are printed with an ``other`` line whenever they do not add up to the file
    count, rather than only when it looks tidy: three numbers a reader cannot sum are worse
    than four that they can, and under ``--all-files`` the source legitimately holds files
    that belong to no media kind.
    """
    print(_SEPARATOR)
    print(f"ANALYZE  {source}")
    print(_SEPARATOR)
    print(f"  files found        : {inventory.files:,}")
    print(
        f"  total size         : {inventory.total_bytes / 1e9:.2f} GB "
        f"({inventory.total_bytes:,} bytes)"
    )
    print(f"  photos             : {inventory.photos:,}")
    print(f"  videos             : {inventory.videos:,}")
    print(f"  audio              : {inventory.audio:,}")
    other = inventory.files - (inventory.photos + inventory.videos + inventory.audio)
    if other:
        print(f"  other              : {other:,}  (counted, but not a photo, video or audio file)")

    print(
        f"  time taken         : {_format_duration(elapsed)}{_rate_note(inventory.files, elapsed)}"
    )

    for group in ("photos", "videos", "audio"):
        formats = inventory.by_format.get(group) or {}
        if formats:
            print(f"      {group:<10} {_format_extension_census(formats)}")


def _print_inventory_skipped(inventory: SourceInventory) -> None:
    """Account for what was NOT counted as media. Never silent.

    Mirrors `_print_skipped`, which does this from a `SourceScan` on the organize surface. It
    cannot be reused directly: this tier keeps counts rather than the path lists that one
    formats, deliberately, so a 33,000-file census never builds a per-file structure.
    """
    groups = {name: counts for name, counts in inventory.skipped.items() if counts}
    if not groups and not inventory.unreadable_dirs and not inventory.hidden_dirs:
        return
    print("\nSkipped (not counted as media):")
    for name, counts in groups.items():
        total = sum(counts.values())
        print(f"  {name.replace('_', ' ')}: {total:,}  ({_format_extension_census(counts)})")
    if inventory.hidden_dirs:
        # The same rule as unreadable folders below, for the same reason: the walk never went
        # in, so the number of photos inside is exactly what is unknown. A user with an album
        # in a hidden folder used to see nothing at all - not a count, not a name.
        print(f"  hidden folders (not looked inside): {len(inventory.hidden_dirs):,}")
        for folder in inventory.hidden_dirs[:_STATUS_PREVIEW]:
            print(f"      {folder}  (contents unknown)")
        if len(inventory.hidden_dirs) > _STATUS_PREVIEW:
            print(f"      ... and {len(inventory.hidden_dirs) - _STATUS_PREVIEW:,} more.")
        print("    (rename one without the leading dot, then run again to include what is in it)")
    if inventory.unreadable_dirs:
        # Named, and deliberately WITHOUT a file count: the number inside is exactly what could
        # not be read, so stating one would invent the missing figure.
        print(f"  folders that could not be read: {len(inventory.unreadable_dirs):,}")
        for folder in inventory.unreadable_dirs:
            print(f"      {folder}  (contents unknown)")
        print("    (check the folder's permissions, then run again to include what is inside)")


def _print_not_yet_analysed(*, deep_done: bool) -> None:
    """State the shape of the answer this report does not contain.

    ``deep_done`` narrows it to the one tier that genuinely did not run. Listing dates and
    duplicates here after reporting them would be the mirror of the defect this block exists
    to prevent: saying a measured thing was not measured.
    """
    remaining = [
        entry for entry in _NOT_YET_ANALYSED if not (deep_done and entry[0] != "look-alikes")
    ]
    print("\nNOT YET ANALYSED")
    for name, description in remaining:
        print(f"      {name:<12} {description}")
    print("  No number is shown for those above because none has been measured -- a zero here")
    print("  would mean 'none found', and nothing has looked yet.")
    if not deep_done:
        print("\n  To find duplicates and check dates today, preview an organize run:")
        print("      truestill organize <folder> --destination <folder>")


def _print_forecast(inventory: SourceInventory, sizes: dict[Path, int]) -> None:
    """Say what is about to run and what it will cost, before the wait rather than after.

    The identical-copy forecast is free: the size pre-filter is a pure function of the size
    census tier 0 already has, so a user can decide whether to wait **before** waiting. That is
    the entire argument for the forecast existing, and it is why this prints here.

    **There is deliberately no time estimate here, and it is not an oversight.** The obvious
    signal is tier 0's own measured throughput, and it cannot carry the claim: tier 0 measures
    ``stat`` calls against directory metadata, while this tier reads file *contents* over the
    same mount. Those are not slow and fast versions of one thing. A FUSE client that serves
    directory listings from its local cache - which is the common case - gives a fast tier 0 on
    an arbitrarily slow link, so the correlation is not merely weak, it can be **absent or
    inverted**: the faster the cache, the more confident and more wrong the estimate.

    The scale is on the record. Measured on a 32,628-file, 192 GB encrypted cloud mount, tier 0
    took 21 s while the expensive tiers moved 29.4 GB at ~9 MB/s over 53 minutes - and the
    maintainer's own advance projection from a 5 GB sample of *content reads*, a far better
    predictor than a stat rate, still spanned **3.6x to 36x**. A forecast built on the weaker
    signal would be worse than that tenfold spread, and a wrong time estimate is worse than
    none: it is the number a user plans their evening around.

    This is the accurate-or-absent rule `_rate_note` already follows, where a files-per-second
    figure is withheld below a second because it would describe interpreter startup rather than
    the source. `docs/PERFORMANCE.md` §5.2 records the measurement itself.
    """
    duplicates = forecast_exact_duplicate_read(sizes)
    print(
        f"\n  Checking for identical copies -- needs to read "
        f"{duplicates.bytes_to_read / 1e9:.2f} GB of your {duplicates.total_bytes / 1e9:.2f} GB "
        f"({duplicates.colliding_files:,} of {duplicates.files:,} files could have a twin)."
    )
    if duplicates.bytes_to_read:
        # **Deliberately not a time estimate.** See `_print_forecast`'s docstring for why tier
        # 0's rate cannot honestly predict this one. What IS honest is the contrast, which is
        # the thing a user actually needs to know: the fast answer above stays fast on any
        # mount, and this one scales with the connection.
        print(
            "  The census above was quick because it read folder listings; this reads the "
            "files themselves, so how long it takes depends on your disk or connection."
        )
    photos = inventory.by_format.get("photos") or {}
    lookalikes = forecast_lookalike_cost(photos)
    if lookalikes.materially_slower:
        # Actionable only here: the user can still decide not to wait. Their own proportion,
        # never a general claim -- see `insights.forecast_lookalike_cost`.
        print(
            f"  Note: {lookalikes.slow_share:.0%} of your photos are HEIC, which decode far "
            f"slower than JPEG. Looking for look-alikes on this library would be much slower "
            f"still; that check is not part of this report."
        )
    print("  Press Ctrl-C to stop and keep everything above.")


def _print_deep(resolutions: list[Resolution], sizes: dict[Path, int]) -> None:
    """Tier 1 and tier 2a, once both have completed over every file."""
    print()
    _print_capture_timeline(resolutions)
    counted = duplicate_bytes(resolutions, sizes)
    print(
        f"  identical copies   : {counted.exact_files:,} file(s), "
        f"{counted.reclaimable_bytes:,} bytes that need not be copied"
    )
    # Analyze seeds no catalog rows, so every match it can find is inside this folder.
    # An unqualified count here reads as "you already have these", which is the opposite.
    _print_duplicate_origins(resolutions, indent="                       ")


def _analyze_deep(
    files: list[Path], inventory: SourceInventory, sizes: dict[Path, int]
) -> list[Resolution] | None:
    """Run tiers 1 and 2a, or ``None`` if the user interrupted.

    **A read-only cache, and that is not optional.** Skipping the perceptual hash means the
    rows this pass could write would be indistinguishable from genuine ones later;
    `compute_hashes` refuses the writable pairing outright. Reading still helps: hashes an
    earlier organize recorded are reused.
    """
    _print_forecast(inventory, sizes)
    _end_of_tier()
    cancel = threading.Event()
    try:
        with HashCache.beside_readonly(default_catalog_path()) as cache:
            metadata = read_metadata(
                files, cache=cache, cancel=cancel, progress=_progress_printer("reading dates")
            )
            decisions = plan(files, metadata, build_rules())
            index = DedupIndex(DEFAULT_PHASH_THRESHOLD)
            return resolve(
                decisions,
                index,
                cache=cache,
                perceptual=False,
                cancel=cancel,
                progress=_progress_printer("checking for identical copies"),
            )
    except KeyboardInterrupt:
        cancel.set()
        return None


def _cmd_analyze(args: argparse.Namespace) -> int:
    """Tier 0 of Analyze: what is in this folder, from the directory walk alone.

    Needs a folder and nothing else -- no destination, no catalog, no registered drive. That is
    the point rather than an oversight: the audience is someone who has never organized
    anything, and any further requirement would put the free answer behind the paid journey.
    """
    if not args.path.is_dir():
        print(f"error: not a folder: {args.path}", file=sys.stderr)
        return 2
    started = _CLOCK()
    scan = scan_source(args.path, all_files=args.all_files)
    sizes = sizes_of_media(scan.media)
    inventory = inventory_from_scan(scan, sizes)
    elapsed = _CLOCK() - started
    _print_inventory(inventory, args.path, elapsed)
    _print_inventory_skipped(inventory)
    _end_of_tier()

    # The census is on screen before anything expensive begins: a user who wanted only that
    # has it in under a second and can stop. Sequential printing, not the streamed payload of
    # `(r)` commit 3b.
    resolutions = _analyze_deep(scan.media, inventory, sizes) if scan.media else []
    if resolutions is None:
        print("\n  Stopped. Everything above is complete; dates and identical copies were not")
        print("  finished, so no number is shown for them -- a partial count would be wrong")
        print("  rather than incomplete, since an unscanned file may be the twin of a scanned one.")
        return 0
    if resolutions:
        _print_deep(resolutions, sizes)
        _end_of_tier()
    _print_not_yet_analysed(deep_done=bool(resolutions))
    # Worded this way because "writes nothing" would be FALSE and a user who checked would find
    # it out: the hash-cache sidecar is written by the expensive tiers, and `Catalog(db)` creates
    # an empty catalog on a machine that has never run truestill. Neither is a photo and neither
    # is the library, which is what this sentence promises and can keep. Do not shorten it.
    print("\n  Analyze never changes your photos and never adds anything to your library.")
    return 0


def _destination_or_exit(args: argparse.Namespace) -> Destination | int:
    """The destination, or the exit code to return. Shared by organize and ingest (audit F34).

    The only block those two commands duplicated verbatim. Returning the code rather than
    raising keeps both call sites' `return` shape unchanged.
    """
    try:
        return _build_destination(args.destination, rclone=args.rclone)
    except DestinationError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 4


def _cmd_organize(args: argparse.Namespace) -> int:
    if not args.source.is_dir():
        print(f"error: source is not a directory: {args.source}", file=sys.stderr)
        return 2
    scan = scan_source(args.source, all_files=args.all_files)
    files = scan.media
    if not files:
        print(f"No media files found under {args.source}")
        _print_skipped(scan)
        return 0
    print(f"Analysing {len(files)} file(s) under {args.source} ...\n")
    try:
        with HashCache.beside(args.db) as cache:
            metadata = read_metadata(
                files, cache=cache, force=bool(getattr(args, "refresh_metadata", False))
            )
    except ExiftoolMissingError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 3
    destination = _destination_or_exit(args)
    if isinstance(destination, int):
        return destination
    relocation = _build_relocation(args)
    if relocation is not None:
        confirmed = _confirm_in_place(args, len(files))
        if confirmed is not True:
            return 2 if confirmed is None else 0
    code = _run_pipeline(
        args,
        files,
        metadata,
        destination,
        drive_marker=_local_drive_marker(args),
        relocation=relocation,
    )
    _print_skipped(scan)
    return code


def _build_relocation(args: argparse.Namespace) -> Relocation | None:
    """A relocation context whenever the run has move semantics on a local destination.

    Deliberately built for plain ``--move`` too, not just ``--in-place``: the rename is a
    strictly better way to satisfy what ``--move`` already promises, and the journal has to
    follow the *mechanism* so that two users who performed the same operation have the same
    undo rights however they spelled it. ``--in-place`` only raises the stakes of a
    cross-device answer from "fall back" to "refuse".
    """
    if args.rclone or not (args.move or args.in_place):
        return None
    return Relocation(
        run_id=uuid.uuid4().hex,
        source_root=args.source,
        dest_root=Path(args.destination),
        require_rename=args.in_place,
    )


def _confirm_in_place(args: argparse.Namespace, file_count: int) -> bool | None:
    """State plainly what in-place does, then require the word before any file moves."""
    if not args.in_place:
        return True
    print(_SEPARATOR)
    print("IN-PLACE - files will be MOVED on this drive, not copied.")
    print(_SEPARATOR)
    print(f"  {file_count} file(s) under {args.source}")
    print(f"  will be moved into {args.destination}")
    print("  Originals will NOT remain in their current locations.")
    print("  Space needed: ~0 bytes (nothing is copied)")
    print("  Reversible:   truestill undo-organize  restores every file to where it is now")
    print("  Empty folders left behind are reported, never deleted.")
    if not args.apply:
        print("\nPreview only. Re-run with --apply to move these files.")
        return True
    confirmed = _typed_confirmation("\nType 'move' to proceed (anything else aborts): ", "move")
    if confirmed is None:
        return None
    if not confirmed:
        print("Aborted. Nothing was moved.")
        return False
    return True


def _cmd_ingest(args: argparse.Namespace) -> int:
    if args.in_place:
        # Not an arbitrary restriction: Takeout rescue bakes recovered dates into the copy, so
        # the written file differs from the source. That is a rewrite, and a rewrite is not a
        # rename -- there is no version of it that needs no space.
        print(
            "error: --in-place cannot be used with ingest.\n"
            "  Takeout rescue writes recovered dates into each copy, so the file that lands is\n"
            "  not byte-identical to the source and cannot be moved by rename.\n"
            "  Ingest to a destination with room, then organize --in-place afterwards.",
            file=sys.stderr,
        )
        return 2
    if args.source is None:
        print(
            "error: ingest needs a source. Pass --source <folder or archive>.",
            file=sys.stderr,
        )
        return 2
    source_root = _source_root_or_none(args.source, args.destination)
    if source_root is None:
        return 2
    print(f"Scanning {source_root} ...")
    scan = scan_takeout(source_root)
    source_scan = scan_source(source_root)
    # A Takeout export's own .json sidecars and .html scaffolding are consumed here, not skipped,
    # so they are excluded from the skipped report -- only genuinely unhandled files are shown.
    _takeout_noise = {".json", ".html", ".htm"}
    skipped = SourceScan(
        media=source_scan.media,
        documents=[p for p in source_scan.documents if p.suffix.lower() not in _takeout_noise],
        unrecognized=source_scan.unrecognized,
        exiftool_backups=source_scan.exiftool_backups,
        unreadable_dirs=source_scan.unreadable_dirs,
    )
    files = source_scan.media
    if not files:
        print(f"No media files found under {source_root}")
        _print_skipped(skipped)
        return 0
    print(
        f"Found {len(files)} media file(s); matched {len(scan.sidecars)} sidecar(s), "
        f"{len(scan.missing_sidecar)} without.\n"
    )
    try:
        # Cached like the organize path above: an ingest re-run over the same export is the
        # normal way people recover from a partial run, and exiftool is the dominant cost of it.
        with HashCache.beside(args.db) as cache:
            metadata = read_metadata(files, cache=cache)
    except ExiftoolMissingError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 3
    destination = _destination_or_exit(args)
    if isinstance(destination, int):
        return destination

    event_prompt = None
    if args.map_albums:
        event_prompt = album_prompt({str(p): n for p, n in scan.albums.items()})

    code = _run_pipeline(
        args,
        files,
        metadata,
        destination,
        takeout=scan.sidecars,
        tz_offset=args.tz,
        prefer_takeout=args.prefer_takeout_dates,
        scan=scan,
        event_prompt=event_prompt,
        drive_marker=_local_drive_marker(args),
    )
    _print_skipped(skipped)
    return code


def _print_layout_preview(template: LayoutTemplate) -> None:
    """Render the sample files through ``template``, showing the routing split."""
    _print_scheme_preview(LayoutScheme.of(timeline=template, timeline_evented=template))


def _print_scheme_preview(scheme: LayoutScheme) -> None:
    print("Preview:")
    for row, rendered in preview_scheme(scheme):
        when = row.context.captured_at.strftime("%Y-%m-%d") if row.context.captured_at else ""
        print(f"  {row.description:16} {when:10} -> {rendered.path.as_posix()}")
        for warning in rendered.warnings:
            print(f"      ! {warning}")


def _print_presets() -> None:
    """The shipped layouts, with what each one actually produces."""
    print("Presets:")
    for name, preset in PRESETS.items():
        default = "  (default)" if name == DEFAULT_PRESET.key else ""
        print(f"  {name:18} {preset.title}{default}")
        print(f"  {'':18}   photos: {preset.timeline}")
        if preset.timeline_evented != preset.timeline:
            print(f"  {'':18}   events: {preset.timeline_evented}/<event>")


def _cmd_config(args: argparse.Namespace) -> int:
    if args.preset is not None and args.preset not in PRESETS:
        # Never a silent no-op and never a bare traceback: name what was wrong and show every
        # option, because a user who mistyped a preset has no other way to discover the set.
        print(f"error: unknown preset {args.preset!r}", file=sys.stderr)
        print(f"available presets: {', '.join(PRESETS)}", file=sys.stderr)
        return 2

    target = PRESETS[args.preset].timeline if args.preset else args.set_template
    evented = PRESETS[args.preset].timeline_evented if args.preset else None

    with _catalog(args.db) as catalog:
        stored = catalog.get_setting(LAYOUT_TEMPLATE_KEY)

        if target is None:  # show (optionally previewing the current template)
            current = stored or DEFAULT_TEMPLATE_STRING
            print(f"Layout template: {current}" + ("" if stored else "  (default)"))
            if args.preview:
                _print_layout_preview(resolve_template(stored))
            print()
            _print_presets()
            return 0

        try:
            template = parse_timeline_template(target)
        except TemplateError as exc:
            print(f"error: invalid template: {exc}", file=sys.stderr)
            return 2

        _print_layout_preview(template)
        if args.preview:
            print("\n(preview only -- not saved)")
            return 0

        catalog.set_setting(LAYOUT_TEMPLATE_KEY, target)
        if evented is not None and evented != target:
            catalog.set_setting(LAYOUT_EVENT_TEMPLATE_KEY, evented)
        else:
            catalog.clear_setting(LAYOUT_EVENT_TEMPLATE_KEY)
        print(f"\nSaved. New files will be organized as: {target}")
        print("Existing files are left in place (split-era default).")
        return 0


#: Windows' classic maximum for a full path. The check that matters is the ABSOLUTE one -- a
#: relative path well under the limit still breaks under a deep mount point.
MAX_PATH = 260


# argparse publishes no non-private, non-generic type for a subparsers action, so `sub` cannot
# be annotated without either the ignore below or a lie (audit F23).
def _add_clean_parser(sub: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    """The `clean-empty` surface, split out because `build_parser` is at its statement ceiling."""
    clean = sub.add_parser(
        "clean-empty",
        help="remove the empty folders a layout migration left behind (preview by default)",
    )
    clean.add_argument("path", type=Path, help="the connected drive folder")
    clean.add_argument("--db", type=Path, default=default_catalog_path(), help="SQLite catalog")
    clean.add_argument(
        "--apply", action="store_true", help="actually remove them (default: preview only)"
    )
    clean.add_argument(
        "--permanent",
        action="store_true",
        help="where the trash refuses (cloud/network mounts), delete outright instead of "
        "reporting -- requires its own confirmation",
    )


def _print_cleanup_plan(plan: CleanupPlan, backend: str | None, *, permanent: bool) -> None:
    """Show all three tiers with full paths, and say plainly where removals go.

    ``permanent`` arrived on 2026-08-04 with the refusal change, and it is not decoration: with
    no backend and no flag, the answer to "where would these go" became **nowhere**, and the
    sentence here still said "PERMANENTLY". A plan that describes a removal the run can no
    longer perform is the same defect class as the outcome wording §9 exists for, one step
    earlier.
    """
    empties = [c for c in plan.removable if c.tier is Tier.EMPTY]
    junk = [c for c in plan.removable if c.tier is Tier.JUNK_ONLY]

    print(f"REMOVABLE - empty ({len(empties)}):")
    for candidate in empties[:_STATUS_PREVIEW]:
        print(f"  {candidate.relative}")
    if len(empties) > _STATUS_PREVIEW:
        print(f"  ... and {len(empties) - _STATUS_PREVIEW} more")

    print(f"\nREMOVABLE - only OS junk ({len(junk)}), removed with the folder:")
    for candidate in junk:
        print(f"  {candidate.relative}   [{', '.join(candidate.contents)}]")

    print(f"\nLEFT ALONE - something is in there ({len(plan.occupied)}):")
    for candidate in plan.occupied:
        print(f"  {candidate.relative}   [{', '.join(candidate.contents)}]")

    if not plan.removable:
        return
    if backend is None and not permanent:
        print(
            f"\n{len(plan.removable)} folder(s) COULD NOT be removed: this machine has no trash"
            "\nTruestill can use, and Truestill will not delete a folder outright without being"
            "\nasked. Each one is reported and left exactly where it is."
            "\n  If you want them gone anyway, re-run with --permanent, which asks for a"
            "\n  different word because it cannot be undone."
        )
        return
    where = (
        f"to the trash (via {backend}) -- recoverable"
        if backend
        else "PERMANENTLY -- this machine has no trash Truestill can use"
    )
    print(f"\n{len(plan.removable)} folder(s) would be removed {where}.")
    if backend:
        print("  Note: trash can be refused on network or cloud-mounted drives; any refusal is")
        if permanent:
            print("  where --permanent applies, and that folder is deleted outright instead.")
        else:
            print("  reported and that folder is left in place rather than deleted outright.")


def _offer_cleanup(catalog: Catalog, drive_uuid: str, path: Path) -> None:
    """Mention the empty skeleton a migration just left. **Offered, never done.**

    The typed word the migration asked for authorised a relocation; silently widening it to
    include deletions is exactly the scope creep copy-only forbids. So this prints a command.
    """
    leftovers = plan_cleanup(path, emptied_directories(catalog.migrated_old_paths(drive_uuid)))
    if not leftovers.removable:
        return
    print(
        f"\n{len(leftovers.removable)} folder(s) are now empty. Review and remove them with:"
        f"\n  truestill clean-empty {path}"
    )


def _confirm_cleanup(count: int, *, permanent: bool) -> bool | None:
    """Ask for the word that matches the removal being requested.

    Two removals, two questions, two words. `clean` was given for a recoverable removal; reusing
    it for an irreversible one would silently stretch an answer the user gave to a smaller ask.
    Irreversibility is stated **before** the prompt, never discovered after it.
    """
    if not permanent:
        return _typed_confirmation(f"\nType 'clean' to remove {count} folder(s): ", "clean")
    print(
        "\n--permanent: where the trash refuses OR is unavailable, folders will be DELETED"
        "\nOUTRIGHT and are NOT recoverable. Removal uses rmdir, so a folder that is no longer"
        "\nempty cannot be removed even if it is listed above."
    )
    return _typed_confirmation(
        f"\nType 'delete forever' to remove {count} folder(s): ", "delete forever"
    )


def _cmd_clean_empty(args: argparse.Namespace) -> int:
    """Remove the folder skeleton a migration left, after showing exactly what will go."""
    marker = _drive_or_explain(args.path)
    if marker is None:
        return 2

    with _catalog(args.db) as catalog:
        emptied = emptied_directories(catalog.migrated_old_paths(marker.uuid))
    if not emptied:
        print(f"Drive '{marker.label}': no migration leftovers recorded. Nothing to clean.")
        return 0

    plan = plan_cleanup(args.path, emptied)
    backend = trash_backend()

    print(f"Drive '{marker.label}': {len(plan.candidates)} folder(s) the migration emptied.\n")
    _print_cleanup_plan(plan, backend, permanent=args.permanent)
    if not plan.removable:
        print("\nNothing to remove.")
        return 0

    if not args.apply:
        print("\nPreview only. Nothing was removed. Re-run with --apply to remove them.")
        return 0

    confirmed = _confirm_cleanup(len(plan.removable), permanent=args.permanent)
    if confirmed is not True:
        print("Aborted. Nothing was removed.")
        return 0

    outcome = run_cleanup(args.path, plan, apply=True, permanent=args.permanent)
    parts = []
    if outcome.trashed:
        parts.append(f"{outcome.trashed} to the trash")
    if outcome.deleted:
        parts.append(f"{outcome.deleted} deleted permanently")
    print(f"\nRemoved {outcome.removed} folder(s)" + (f" ({', '.join(parts)})." if parts else "."))
    for failure in outcome.failures:
        print(f"  ! {failure}")
    return 0


def _cmd_migrate_undo(args: argparse.Namespace, marker: DriveMarker) -> int:
    """Put a completed migration back. Preview first, then the same typed word as the forward."""
    destination = LocalDestination(args.path)
    with _catalog(args.db) as catalog:
        outcome = undo_migration(catalog, destination, marker.uuid, apply=False)
        record = catalog.reversible_migration(marker.uuid)
        if record is None:
            print(f"Drive '{marker.label}': no reversible migration exists for this drive.")
            return 0

        print(f"Drive '{marker.label}': {len(record[1])} file(s) from the last migration.")
        print(f"  {outcome.reversed_files} can be put back.")
        for relative, reason in outcome.refused:
            print(f"  ! {relative}: {reason}")

        if not args.apply:
            print("\nPreview only. Nothing was moved. Re-run with --apply to put them back.")
            return 0

        confirmed = _typed_confirmation(
            f"\nType 'undo' to put {outcome.reversed_files} file(s) back: ", "undo"
        )
        if confirmed is not True:
            print("Aborted. Nothing was moved.")
            return 0

        applied = undo_migration(catalog, destination, marker.uuid, apply=True)
        print(f"\nPut {applied.reversed_files} file(s) back.")
        for relative, reason in applied.refused:
            print(f"  ! {relative}: {reason}")
        return 0


def _print_routing(routes: list[LabelRoute], rules_by_sha: dict[str, str]) -> bool:
    """Show where each label's files are headed. Returns whether anything is still undecided."""
    print("\nRouting, by label:")
    undecided = False
    for route in routes:
        if route.needs_decision and rules_by_sha:
            print(f"  {route.label:20} {route.files:>6} file(s)  resolved per file (re-read)")
            continue
        if route.needs_decision:
            undecided = True
            print(f"  {route.label:20} {route.files:>6} file(s)  ⚠ AMBIGUOUS -- {route.reason}")
            continue
        print(f"  {route.label:20} {route.files:>6} file(s)  -> {route.route}")
    return undecided


def _print_day_folder_reasons(reasons: Sequence[str]) -> None:
    if not reasons:
        return
    print("\nEveryday day-folder changes:")
    for reason in reasons:
        print(f"  {reason}")


def _print_migration_plan_preview(plan: Any, mount: Path) -> None:
    """Relocate count, Everyday day-folder reasons, sample moves, path length, warnings."""
    print(f"\n{len(plan.moves)} file(s) to relocate, {plan.unchanged} already in place.")
    # Reasons before the path list so Everyday month↔day moves are never a bare list.
    _print_day_folder_reasons(plan.day_folder_reasons)
    for move in plan.moves[:_STATUS_PREVIEW]:
        print(f"  {move.old_relative}  ->  {move.new_relative}")
    if len(plan.moves) > _STATUS_PREVIEW:
        print(f"  ... and {len(plan.moves) - _STATUS_PREVIEW} more")

    # The absolute check, not the relative one: the mount point is part of every path.
    root_len = len(str(mount).rstrip("/")) + 1
    longest = max((m.new_relative for m in plan.moves), key=len, default="")
    if longest:
        worst = root_len + len(longest)
        flag = "  ⚠ OVER THE LIMIT" if worst > MAX_PATH else ""
        print(
            f"\nLongest path: {worst} chars of {MAX_PATH} (mount {root_len} + {len(longest)}){flag}"
        )
        print(f"  {longest}")

    for warning in plan.warnings:
        print(f"  ! {warning}")


def _cmd_migrate_layout(args: argparse.Namespace) -> int:
    marker = _drive_or_explain(args.path)
    if marker is None:
        return 2

    destination = LocalDestination(args.path)
    if args.undo:
        return _cmd_migrate_undo(args, marker)

    with _catalog(args.db) as catalog:
        # NOTE: the drive is deliberately NOT upserted here. Refreshing its label is a write, and
        # everything before the confirm has to be a read -- a preview that already touched the
        # catalog is not a preview. It is registered on the apply path instead.
        scheme = resolve_scheme(catalog)

        # Everything up to the confirm is PURE: it reads the catalog and (for ambiguous labels
        # only) reads file metadata. Nothing is written and nothing is moved.
        routes = label_routes(catalog, marker.uuid)
        with HashCache.beside(args.db) as cache:
            rederived = rederive_rules(
                catalog,
                marker.uuid,
                args.path,
                routes,
                by_device=getattr(args, "by_device", False),
                cache=cache,
            )
        rules_by_sha = rederived.rules
        if rederived.unavailable_reason:
            # Before the plan, not after: this changes how to read every routing line below it.
            print(f"warning: {rederived.unavailable_reason}", file=sys.stderr)
        decided = {r.label: (ROUTE_SIDE_BIN if r.needs_decision else r.route) for r in routes}
        plan = plan_migration(
            catalog, marker.uuid, scheme, routes=decided, rules_by_sha=rules_by_sha
        )

        print(f"Drive '{marker.label}': layout {scheme.template_for(Placement.EVERYDAY).template}")
        undecided = _print_routing(routes, rules_by_sha)
        _print_migration_plan_preview(plan, args.path)

        others = [d for d in catalog.list_drives() if d["uuid"] != marker.uuid and d["file_count"]]
        for drive in others:
            print(f"  pending: drive '{drive['label']}' has copies too -- reconnect it and re-run")

        if not args.apply:
            print("\nPreview only. Nothing was moved. Re-run with --apply to move the files.")
            return 0
        if undecided:
            print(
                "\nRefusing to move: some labels could not be routed and were not re-read "
                "(are the files on this drive?). Nothing was moved.",
                file=sys.stderr,
            )
            return 2

        # An explicit word, never a default-yes and never a bare Enter. Absent it, the terminal
        # state of this command is "previewed, nothing moved".
        confirmed = _typed_confirmation(
            f"\nType 'move' to relocate {len(plan.moves)} file(s) (anything else aborts): ", "move"
        )
        if confirmed is not True:
            print("Aborted. Nothing was moved.")
            return 0

        catalog.upsert_drive(uuid=marker.uuid, label=marker.label)
        if pin_existing_layout(catalog):
            print(_PINNED_NOTICE)
        outcome = run_migration(
            catalog,
            destination,
            marker.uuid,
            scheme,
            apply=True,
            routes=decided,
            rules_by_sha=rules_by_sha,
        )
        if outcome.resumed:
            print(f"Recovered {outcome.resumed} move(s) from an interrupted run.")
        print(f"\nMigrated {outcome.migrated} file(s). Sources were never touched.")
        _offer_cleanup(catalog, marker.uuid, args.path)
        return 0


def _cmd_undo_organize(args: argparse.Namespace) -> int:
    with _catalog(args.db) as catalog:
        if args.list:
            runs = catalog.inplace_runs()
            if not runs:
                print("No in-place organize runs recorded.")
                return 0
            print(f"{'run id':<34}{'when':<28}{'files':>7}  status")
            for row in runs:
                print(
                    f"{row['run_id']:<34}{row['started_at']:<28}{row['moves']:>7}  {row['status']}"
                )
            return 0

        try:
            plan = plan_undo(
                catalog,
                args.run_id,
                source_root=args.source_root,
                dest_root=args.dest_root,
            )
        except UndoError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2

        print(f"Run {plan.run_id} ({plan.status})")
        print(f"  moved into : {plan.dest_root}")
        print(f"  came from  : {plan.source_root}")
        print(f"  restorable : {plan.restorable} file(s)")
        for skip in plan.skipped:
            print(f"  cannot restore: {skip.step.current.name} -- {skip.detail}", file=sys.stderr)

        if not args.apply:
            print("\nPreview only. Re-run with --apply to move these files back.")
            return 0
        if not plan.steps:
            print("\nNothing to restore.")
            return 0

        outcome = run_undo(catalog, plan, apply=True, progress=_progress_printer("restoring"))
        print(f"\nRestored {outcome.restored} file(s) to their original locations.")
        if outcome.skipped:
            print(
                f"  {len(outcome.skipped)} file(s) could not be restored; the run stays open so "
                "you can re-run undo once they are resolved.",
                file=sys.stderr,
            )
        return 1 if outcome.skipped else 0


def _print_reclaim_plan(plan: ReclaimPlan, *, label: str, min_copies: int) -> None:
    """Summarize a reclaim plan. Missing sources go to stderr; calm empty is handled by caller."""
    n = len(plan.candidates)
    gib = plan.total_bytes / 1e9
    print(f"Drive '{label}': {n} source file(s) safely backed up and re-verified.")
    print(f"  reclaimable: {n} file(s), {gib:.2f} GB would be freed")
    if plan.unverified:
        print(f"  skipped: {plan.unverified} copy(ies) failed re-verification (source kept)")
    if plan.organized_in_place:
        # Never silent: these look reclaimable and are the one case where reclaiming
        # would destroy the only copy, so say so rather than quietly omitting them.
        print(
            f"  skipped: {plan.organized_in_place} file(s) organized in place -- the source "
            "IS the copy on this drive, so freeing it would delete the only one"
        )
    if plan.below_min_copies:
        print(f"  held back: {plan.below_min_copies} file(s) below --min-copies={min_copies}")
    if plan.missing_sources:
        print(
            f"  noted: {plan.missing_sources} recorded source(s) no longer exist at their "
            "catalog path (they may have moved, or were already freed).",
            file=sys.stderr,
        )
        for example in plan.missing_examples:
            print(f"    e.g. {example}", file=sys.stderr)
    if plan.single_copy:
        print(
            f"  WARNING: {len(plan.single_copy)} file(s) would then exist in only ONE place "
            f"(raise --min-copies to exclude them)"
        )


def _cmd_reclaim(args: argparse.Namespace) -> int:
    marker = _drive_or_explain(args.path)
    if marker is None:
        return 2
    if args.min_copies < 1:
        print("error: --min-copies must be at least 1", file=sys.stderr)
        return 2

    with _catalog(args.db) as catalog:
        catalog.upsert_drive(uuid=marker.uuid, label=marker.label)
        plan = plan_reclaim(catalog, marker.uuid, args.path, min_copies=args.min_copies)
        _print_reclaim_plan(plan, label=marker.label, min_copies=args.min_copies)

        n = len(plan.candidates)
        if n == 0:
            # Calm empty is normal. Stale paths already spoke on stderr; do not urge --apply.
            if not plan.missing_sources:
                print("\nNothing to reclaim.")
            return 0
        if not args.apply:
            print("\nPreview only. Re-run with --apply to delete these sources.")
            return 0

        gib = plan.total_bytes / 1e9
        print(f"\nThis PERMANENTLY DELETES {n} source file(s), freeing {gib:.2f} GB.")
        confirmed = _typed_confirmation(
            "Type 'delete' to proceed (anything else aborts): ", "delete"
        )
        if confirmed is not True:
            print("Aborted -- nothing was deleted.")
            return 0

        outcome = run_reclaim(catalog, marker.uuid, args.path, min_copies=args.min_copies)
        print(f"\nFreed {outcome.deleted} source file(s), {outcome.freed_bytes / 1e9:.2f} GB.")
        if outcome.kept:
            print(f"Kept {outcome.kept} file(s) that failed a final re-verify -- not deleted.")
        return 0


def main(argv: list[str] | None = None) -> int:
    """Run the CLI. Returns a process exit code.

    The one seam that converts a held catalog into a refusal. It sits here, around every
    subcommand at once, because the lock can be met anywhere a command touches the catalog --
    at the startup banner, on the first write, or a thousand files into a run -- and a handler
    per mutating command would be seven copies of one rule, which is the duplication
    ENGINEERING_STANDARD.md §4 records as this repo's recurring defect. Read-only commands pass
    through it harmlessly: they cannot raise this in the first place, since SQLite blocks only
    a second *writer*.

    Anything that is not a busy catalog keeps its traceback. That is the point of the check
    rather than the point of the message: `OperationalError` also covers a disk I/O error and a
    corrupt schema, and answering those with "wait for the other operation to finish" would
    send someone to wait out a fault that never clears.
    """
    try:
        return _dispatch(argv)
    except sqlite3.Error as exc:
        if not is_catalog_busy(exc):
            raise
        print(f"error: {CATALOG_BUSY_MESSAGE}", file=sys.stderr)
        return CATALOG_BUSY_EXIT


def _dispatch(argv: list[str] | None) -> int:
    argv_list = list(argv) if argv is not None else sys.argv[1:]
    args = _build_parser().parse_args(argv_list)
    if hasattr(args, "db"):
        info = inspect_catalog(args.db, explicit_db=db_flag_explicit(argv_list))
        for line in format_startup_lines(info):
            # empty_with_drives is the only loud case; first-run stays on stdout.
            stream = (
                sys.stderr if info.presence is CatalogPresence.EMPTY_WITH_DRIVES else sys.stdout
            )
            print(line, file=stream, flush=True)
    dispatch = {
        "analyze": _cmd_analyze,
        "organize": _cmd_organize,
        "ingest": _cmd_ingest,
        "drives": _cmd_drives,
        "where": _cmd_where,
        "restore": _cmd_restore,
        "verify": _cmd_verify,
        "status": _cmd_status,
        "catalog": _cmd_catalog,
        "config": _cmd_config,
        "clean-empty": _cmd_clean_empty,
        "rescan": _cmd_rescan,
        "migrate-layout": _cmd_migrate_layout,
        "reclaim": _cmd_reclaim,
        "undo-organize": _cmd_undo_organize,
        "repoint-sources": _cmd_repoint,
    }
    return dispatch[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
