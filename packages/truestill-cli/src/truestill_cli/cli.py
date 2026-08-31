"""Command-line entry point.

Defaults are inert: with no ``--apply`` the tool analyses the source, resolves duplicates
and prints what it *would* organize, writing nothing to the destination or the catalog.
"""

from __future__ import annotations

import argparse
import re
import sqlite3
import sys
import threading
import time
import uuid
from collections import Counter
from collections.abc import Callable, Iterable, Mapping, Sequence
from contextlib import AbstractContextManager
from dataclasses import fields
from dataclasses import replace as _dataclass_replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from truestill_core import decode_noise
from truestill_core.app_paths import (
    LEGACY_CATALOG_PATH,
    cache_path_for,
    default_catalog_path,
    record_path_for,
    resolve_catalog_choice,
)
from truestill_core.archive_extract import extract_archive_set
from truestill_core.archive_ingest import archives_at, precheck_archives
from truestill_core.backup import (
    BackupPair,
    BackupStoppedError,
    _files_missing_on_target,
    _gb,
    copy_to_drive,
)
from truestill_core.bake import (
    CONFIRM_WORD,
    IRREVERSIBLE_NOTE,
    VIDEO_EXCLUSION_REASON,
    BakePlan,
    bake_confirmed_dates,
    bake_plan,
    migration_unfinished,
    migration_unfinished_message,
    nothing_to_write_reason,
)
from truestill_core.catalog import Catalog
from truestill_core.catalog_backup import BackupOutcome
from truestill_core.catalog_busy import (
    CATALOG_BUSY_MESSAGE,
    CatalogUnwritableError,
    catalog_unwritable_message,
    is_catalog_busy,
    is_catalog_unwritable,
)
from truestill_core.catalog_move import CatalogMoveOutcome, move_catalog_to_standard
from truestill_core.catalog_session import open_catalog
from truestill_core.catalog_startup import (
    CATALOG_UNUSABLE_EXIT,
    CatalogUnusableError,
    db_flag_explicit,
    format_startup_lines,
    inspect_catalog,
    refuse_unusable_catalog,
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
    REPORT_FIELD_EXCEPTIONS,
    REPORT_FIELD_NOTE,
    RESTORE_WORDING,
    ApplyReport,
    Decisions,
    DriveSave,
    RestoreNote,
    RestoreReport,
    SaveOutcome,
    apply_documents,
    drive_holdings,
    gather_decisions,
    merge_onto_drive,
    nothing_applied_note,
    notice_for,
    read_decisions,
    render_swaps,
    restored_count,
    superseded_note,
    unmatched_events_note,
    withheld_count,
    write_decisions,
)
from truestill_core.dedup import DedupIndex, credible_copies
from truestill_core.destinations import Destination, LocalDestination, RcloneDestination
from truestill_core.destinations.base import DestinationError
from truestill_core.drive import (
    MARKER_NAME,
    CustodyFreshness,
    CustodyTier,
    DriveGhostError,
    DriveMarker,
    DriveReach,
    DriveWriteError,
    GhostDrive,
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
    remember_drive_path,
    second_location_for,
    upgrade_marker,
    was_ever_checked,
)
from truestill_core.drive_adoption import (
    AdoptionOffer,
    AdoptionVerdict,
    RecordedDrive,
    inspect_root,
    recorded_drive,
)
from truestill_core.drive_lock import DriveBusyError, lock_for
from truestill_core.duplicate_explain import describe_split, origin_phrase, split_by_origin
from truestill_core.exif import ExiftoolMissingError, read_metadata
from truestill_core.filesystem import DestinationPreflight
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
    STOP_WORDING,
    LabelRoute,
    MigrationStop,
    RenameKind,
    RenameOutcome,
    RenamePlan,
    apply_rename,
    label_routes,
    plan_migration,
    plan_rename,
    rederive_rules,
    run_migration,
    undo_migration,
)
from truestill_core.models import (
    ActionResult,
    ActionStatus,
    DateSource,
    Decision,
    Event,
    Resolution,
    UnreadableReason,
    date_quality,
    format_inferred_local_shift_line,
    inferred_local_shifts,
    partition_for_report,
    status_label,
    unreadable_label,
    unreadable_remedy,
)
from truestill_core.organizer import (
    Relocation,
    RunStoppedError,
    SkippedFolderGroup,
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
    skipped_extension_counts,
    skipped_folder_groups,
    uncompared_photos,
    write_candidates,
)
from truestill_core.progress import Progress, ProgressCallback
from truestill_core.reclaim import ReclaimPlan, plan_reclaim, run_reclaim
from truestill_core.rescan import RescanReport, reconcile
from truestill_core.run_record import (
    RunHeader,
    build_run_record,
    files_from_resolutions,
    record_organize,
    record_undo,
    stop_block,
    write_run_record,
)
from truestill_core.safe_copy import STAGING_SUFFIX
from truestill_core.scan import DEFAULT_WORKERS
from truestill_core.selfcheck import (
    core_findings,
    is_complete,
    not_checked_finding,
    render,
)
from truestill_core.source_repoint import RepointPlan, plan_repoint
from truestill_core.takeout import (
    IngestContext,
    MetadataWrite,
    TakeoutScan,
    TakeoutSidecar,
    scan_takeout,
)
from truestill_core.undo import (
    SkipClass,
    UndoError,
    UndoOutcome,
    UndoPlan,
    UndoStopKind,
    classify,
    outstanding,
    plan_undo,
    run_undo,
)
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
#: How many items any capped list names before eliding the rest. ⚠ **Six sites share it**, so
#: it is not `status`'s - it was documented as that until 2026-08-22 while five other lists
#: already borrowed it, which is how a shared constant reads as one command's setting.
_STATUS_PREVIEW = 20

#: Exit code for "another process holds the catalog; nothing to fix, try again shortly".
#:
#: Its own code rather than `1` or `2`, because a script's only reason to read one is to decide
#: what to do next, and this is the single case where the answer is *retry*. `2` is a usage or
#: validation error, which never becomes valid by waiting; `1` is this CLI's "the run finished
#: and something is wrong with the library", and the run did not finish. The precedent is how
#: the codes here are already allocated -- `3` a missing exiftool, `4` an unusable destination
#: -- one per failure family that a caller would act on differently.
CATALOG_BUSY_EXIT = 5

#: `undo-organize` alone: its drive is not in `args`. The run's `dest_root` comes out of the
#: catalog, so the lock is taken inside the handler once the plan is built. Declared here rather
#: than omitted, so the completeness guard still forces an answer. `(aaw)`
_LOCKED_IN_HANDLER = "<in handler>"

#: A catalog write that failed for a reason retrying cannot fix. Distinct from
#: `CATALOG_BUSY_EXIT` because the two send the user somewhere different, and distinct from a
#: plain `1` because a script that sees this knows the library may hold files the catalog does
#: not: `truestill rescan` is the follow-up, not a re-run. `(afe)`
CATALOG_UNWRITABLE_EXIT = 7

#: Another live process is mutating this drive. `(aaw)`
#:
#: Distinct from `CATALOG_BUSY_EXIT` on purpose: both mean *wait*, but a script that retries a
#: busy drive must not also retry a catalog it cannot write, and the two are told apart only by
#: the code. A refusal here always names a **live** holder - the lock is kernel-enforced, so a
#: crashed process leaves nothing to force past.
DRIVE_BUSY_EXIT = 8

#: The drive-lock policy for **every** subcommand, and the value is the `args` attribute naming
#: the drive. `(aaw)`
#:
#: ⚠ **EVERY COMMAND DECLARES, AND THERE IS NO DEFAULT**, which is the whole point of the table.
#: Defaulting to unlocked means the next mutating command silently skips the lock; defaulting to
#: locked means a read-only command starts refusing with nobody deciding. A command missing here
#: raises `KeyError` in `_dispatch` and fails
#: `test_every_command_declares_whether_it_locks_a_drive` before that can reach anyone.
#:
#: ⚠ **NOT derived from the command name or from an `operation` string.** A string used as a
#: control is one rename away from a lock that stops firing.
#:
#: `None` means *this command does not mutate files on a drive*. Locking is **only** taken under
#: `--apply`: a preview writes nothing, and a stale preview is not data loss, while making
#: previews refuse would be new behaviour on a path that works today.
_LOCKS_DRIVE_AT: dict[str, str | None] = {
    "analyze": None,  # reads a folder, writes nothing anywhere
    "organize": "destination",
    "ingest": "destination",
    "drives": None,  # catalog rows and the marker; SQLite serialises the first, `(aap)` the second
    "where": None,  # a query
    "restore": None,  # writes catalog rows from a drive's document, never files onto the drive
    "verify": None,  # reads and stamps; a stale stamp is not a lost file
    "status": None,  # a query
    "self-check": None,  # inspects this install, never a library
    "catalog": None,  # catalog-only
    "config": None,  # settings rows
    "backup": "target",  # writes into the target drive; `(ahf)`
    "bake": "path",  # writes bytes inside the user's files; `(ahd)`
    "clean-empty": "path",
    "rescan": None,  # reports; `(abn)` is that nothing acts on it yet
    "migrate-layout": "path",
    # ⚠ **`"path"` since stage 2**, which was the condition the stage-1 note set: the apply moves
    # files on the drive, so it is held for the duration like every other mutating command. `(aix)`
    "rename": "path",
    "reclaim": "path",
    "undo-organize": _LOCKED_IN_HANDLER,
    "repoint-sources": None,  # rewrites `source_path` rows, touches no drive
}


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
        "--report",
        type=Path,
        metavar="PATH",
        # It no longer decides WHETHER a record exists - only where it goes. `(afl)`
        help="write this run's record here instead of beside the catalog",
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

    sub.add_parser(
        "self-check", help="report what this installation of Truestill actually contains"
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

    # `(aix)` stage 1. Preview only - there is no `--apply` yet, and the handler says so rather
    # than advertising a flag that does not exist.
    rename = sub.add_parser(
        "rename",
        help="show what renaming a trip or event would move (preview only; nothing is written)",
    )
    rename.add_argument("path", type=Path, help="the drive's mount root (must be connected)")
    rename.add_argument("kind", choices=[k.value for k in RenameKind], help="trip or event")
    rename.add_argument("id", type=int, help="its catalog row id")
    rename.add_argument("name", help="the new name")
    rename.add_argument("--db", type=Path, default=default_catalog_path(), help="SQLite catalog")
    rename.add_argument(
        "--apply", action="store_true", help="actually move the files (default: preview only)"
    )

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

    _print_rescan_section(
        "LEFT BEHIND BY TRUESTILL",
        list(report.debris),
        "a run was interrupted while writing these - a disk that filled, a drive pulled out,"
        " the process killed. They are not your photos: delete them."
        " Their names end in .partial.",
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


def _report_pre_upgrade_copy(outcome: BackupOutcome) -> None:
    """The CLI's voice for the copy taken before a schema upgrade. `(ady)`

    **Silence on success**, like the decisions save above and for the same reason: the upgrade
    worked and the copy is where it always is. A user who wants it can be told where by
    ``truestill catalog``.

    **A failure is said, once, on stderr** - the copy is a safety net the user did not ask for
    and cannot see, so the one moment it is absent is the one moment it is worth a line. It is a
    note rather than an error because the upgrade itself succeeded: reporting it as a failure
    would send someone looking for damage that is not there.
    """
    if not outcome.taken:
        print(f"note: {outcome.error}", file=sys.stderr)


def _catalog(db: Path) -> AbstractContextManager[Catalog]:
    """``open_catalog`` with this surface's voice attached.

    Every CLI catalog open goes through here, so the trigger cannot be missed at a sixteenth
    call site - and `test_catalog_opens_go_through_the_session` refuses a bare `Catalog(...)`.
    """
    return open_catalog(db, report=_report_decision_saves, backup_report=_report_pre_upgrade_copy)


def _cmd_rescan(args: argparse.Namespace) -> int:
    """Reconcile a drive's recorded locations with what is on it. Reads; writes nothing.

    Exit **1** when anything did not reconcile or anything could not be read, so
    ``truestill rescan X && next_step`` cannot chain past a drive Truestill could not account
    for - the same reason an organize preview that found an unreadable file exits 1.
    """
    root = args.path
    marker = _drive_or_explain(root, args.db)
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

    # `(acz)`: staging gave a survivor a safe name and, with it, moved the seam that found the
    # original defect. `(abu)` was caught because rescan reported the leftover as STRAY - true
    # only while it wore a media extension. A `.partial` lands in `scan.unrecognized` instead, so
    # rescan never saw it again. Picked out by the one suffix Truestill itself writes.
    debris = [
        path.relative_to(root).as_posix()
        for path in scan.unrecognized
        if path.name.endswith(STAGING_SUFFIX)
    ]
    report = reconcile(
        recorded=recorded,
        on_disk=on_disk.keys(),
        identified=identified,
        unreadable_dirs=[p.relative_to(root).as_posix() for p in scan.unreadable_dirs],
        unreadable_files=unreadable_files,
        debris=debris,
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
    try:
        marker = upgrade_marker(root)
    except DriveWriteError as refusal:
        # A legacy drive that will not take its canonical marker keeps working - the old name is
        # still read (§3.1). So this reports and stops rather than implying identity was lost.
        print(f"error: {refusal}", file=sys.stderr)
        return 4
    if marker is None:  # unreachable: read_marker above proved a marker exists
        print(f"error: could not read the drive marker at {root}", file=sys.stderr)
        return 2
    catalog.upsert_drive(uuid=marker.uuid, label=marker.label)
    print(
        f"Wrote {MARKER_NAME} for '{marker.label}' (uuid {marker.uuid}, unchanged).\n"
        f"  {legacy.name if legacy else 'the old marker'} was left in place."
    )
    return 0


def _verification_state(drive: Any) -> str:
    """What a check has established about this drive - and the three states are three states.

    ⚠ **A NULL `drives.last_verified` MEANS TWO DIFFERENT THINGS, and this used to render both as
    the word "never".** `refresh_drive_verified` leaves it NULL unless *every* copy is confirmed,
    so the drive cannot claim a date it has not earned - `(abg)` Stage 2, and that rule is right
    and unchanged. But NULL is a claim-SUPPRESSION flag covering *"missing, unreadable,
    unverifiable and not reached before the user cancelled"*; it is not a statement that nothing
    ever happened. The field answers *"may I reassure?"*, and this line was asking it *"what
    happened?"*.

    Measured by the first soak: seven files deleted by hand, `verify` reported `MISSING 7` and
    named all seven, and sixteen seconds later this column said **never** - beside the `LAST SEEN`
    timestamp of that very run.

    **That is the FALSE EMPTY**, and it is a trust defect rather than a cosmetic one: a
    no-results state rendered as a first-use state. A reader who catches an empty state
    contradicting itself stops believing empty states generally - so the cost is not this row, it
    is that *"never"* stops being actionable on the drives where it is true and urgent. Hence the
    cry-wolf half: a drive nothing has looked at still says **never**, and must.

    `confirmed_count` is the discriminator and `missing_count` alone could not be: a copy can be
    unconfirmed without being missing.
    """
    if drive["last_verified"]:
        return str(drive["last_verified"])[:19]
    # ⚠ THE RULE MOVED TO CORE AND THIS READS IT (`(aes)`). It was written here, correctly, by
    # `(aej)` - and being written at ONE call site is what let `custody_freshness` and the app's
    # safety table go on saying "never" about a drive this cell already knew had been checked.
    # §4's fifty-sixth member: a rule applied locally reads as settled while the surfaces it never
    # reached disagree in silence. One predicate now, four readers.
    return "checked, gaps" if was_ever_checked(drive) else "never"


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
            f"{'LABEL':<20}{'FILES':>8}{'NOT FOUND':>10}{'SIZE(MB)':>12}  {'STATUS':<10}"
            f"{'LAST SEEN':<22}LAST VERIFIED"
        )
        connected: list[tuple[Path, str]] = []
        for d in drives:
            size_mb = (d["total_size"] or 0) / 1e6
            # Not a boolean. "unknown" is the ordinary state for a drive this machine has never
            # been pointed at, and printing it as "offline" would tell someone their backup is
            # gone when Truestill simply has no idea where it lives.
            reach = reach_of(catalog, str(d["uuid"]))
            missing = d["missing_count"] or 0
            interrupted = catalog.unfinished_organize_run(str(d["uuid"]))
            print(
                f"{d['label']:<20}{d['file_count']:>8}{(str(missing) if missing else '-'):>10}"
                f"{size_mb:>12.1f}  {reach.value:<10}"
                f"{(d['last_seen'] or '-')[:19]:<22}{_verification_state(d)}"
            )
            if interrupted is not None:
                # ⚠ Its own line, not a column: this is not a property of the drive, it is a
                # statement about a run that did not finish - and it needs a denominator to mean
                # anything. `(aem)`.
                print(
                    f"    ⚠ a run was interrupted: "
                    f"{interrupted['achieved']:,} of {interrupted['intended_total']:,} files "
                    f"arrived. Run organize again to finish it."
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


def _say_if_two_places(catalog: Catalog, marker: DriveMarker, root: Path) -> None:
    """Report a second live path for this identity, BEFORE anything overwrites the evidence.

    ⚠ **Call order is the whole contract.** `upsert_drive` refreshes ``last_seen`` and the hint
    write replaces the remembered path - two statements that destroy both halves of the evidence,
    and in `_cmd_verify` they sit five lines apart. Everything this needs must be read first.

    Silent unless the remembered path still answers with the same uuid. `(adx)`.
    """
    note = second_location_for(catalog, uuid=marker.uuid, label=marker.label, here=root)
    if note is not None:
        print(note, file=sys.stderr)


def _print_adoption_refusal(path: Path, offers: list[AdoptionOffer]) -> None:
    """Name the drive this folder already is, and both ways forward. Never choose one."""
    proven = [o for o in offers if o.verdict is AdoptionVerdict.PROVEN]
    differing = [o for o in offers if o.verdict is AdoptionVerdict.CONTENT_DIFFERS]
    unreadable = [o for o in offers if o.verdict is AdoptionVerdict.UNREADABLE]
    # ⚠ FIRST, and not only for tidiness: with neither a proven nor a differing offer this
    # function fell through to the block below and printed "already holds the library recorded
    # as ." - a nameless sentence offering `--adopt-existing`, which cannot work because
    # `_init_drive` requires exactly one proven match. An unreadable sample is precisely that
    # state, so the branch is required by the change rather than added alongside it. `(afn)`
    if unreadable and not (proven or differing):
        worst = max(unreadable, key=lambda o: o.refused)
        names = ", ".join(f"'{o.label}'" for o in unreadable)
        print(
            f"error: {path} could not be read well enough to say whether it is a drive "
            "Truestill already knows.\n"
            f"       {worst.refused} of {worst.sampled} sampled files would not open, so this "
            f"folder may be {names}\n"
            "       with an unreadable mount, or somewhere new. Registering it now could give "
            "one library two\n"
            "       drive ids, and Truestill would then count one copy of your photos as two. "
            "Nothing was written.\n"
            "\n"
            "       If the drive is not fully mounted, or a folder is\n"
            "       still syncing:            fix that and run again\n"
            "       If this really is a new place:\n"
            "                                 re-run with --force-new-identity",
            file=sys.stderr,
        )
        return
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
    # ⚠ THE CONTENT GUARD BELOW CANNOT SEE AN EMPTY MOUNTPOINT, WHICH IS THE WHOLE OF `(afc)`.
    # `_adoption_offers` samples FILES to recognise a folder that HOLDS a known library; an
    # unmounted mountpoint holds nothing, so it passes - the door `ghost_drive_at`'s docstring
    # names as the one `(aap)`'s content-based guard is blind to. This asks the other question:
    # is this path RECORDED as a known drive's home? `--force-new-identity` is the escape, and it
    # is the same escape the organize path already offers.
    ghost = ghost_drive_at(
        args.init, catalog, [(str(d["uuid"]), str(d["label"])) for d in catalog.list_drives()]
    )
    if ghost is not None and not args.force_new_identity:
        print(f"error: {ghost_drive_refusal(ghost)}", file=sys.stderr)
        return 2
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

    try:
        marker = create_marker(args.init, label, uuid=adopt)
    except DriveWriteError as refusal:
        print(f"error: {refusal}", file=sys.stderr)
        return 4
    _say_if_two_places(catalog, marker, args.init)
    catalog.upsert_drive(uuid=marker.uuid, label=marker.label)
    remember_drive_path(catalog, marker.uuid, args.init)
    verb = "re-attached" if adopt else "initialised"
    print(f"Drive '{marker.label}' {verb} at {args.init}  (uuid {marker.uuid}).")
    _print_drive_notice(args.init, gather_decisions(catalog, marker.uuid), "This drive")
    return 0


def _drive_or_explain(path: Path, db: Path | None = None) -> DriveMarker | None:
    """Resolve a drive root, printing a *useful* refusal when the path is not one.

    Pointing at a folder inside a connected drive used to report "connect the drive first",
    which is both wrong and unactionable. Walking up finds the drive and names the correction.

    ``db`` is optional so a caller with no catalog still gets every other refusal; without it the
    ghost check below cannot run, and the message falls back to naming both readings.
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
    # ⚠ THE PATH IS THERE AND CARRIES NO MARKER, WHICH IS TWO STATES, NOT ONE. `(afc)`
    # A cleanly unmounted mountpoint is byte-for-byte an ordinary empty directory - measured:
    # `os.path.ismount` is False, `st_dev` equals the parent's, and it is absent from
    # `/proc/mounts`, because the state exists only while the mount does. So the filesystem
    # cannot answer this and no amount of probing will make it. **Only a recorded expectation
    # discriminates**, which is `ghost_drive_at`'s conclusion and the reason administrators
    # protect mountpoints with `chattr +i` by hand.
    ghost = _ghost_at(path, db)
    if ghost is not None:
        print(f"error: {ghost_drive_refusal(ghost)}", file=sys.stderr)
        return None
    # ⚠ NOTHING WAS EVER RECORDED HERE, so both readings are live and the product does not know
    # which. `drive.py:145` calls that the normal state for a CLI-only user, so it cannot be
    # refused - and it must not be instructed either, which is what cost a drive in soak three.
    # Both readings, and what the wrong guess costs.
    print(
        f"error: {path} is not a Truestill drive.\n"
        f"       If this folder is new, register it:  "
        f"truestill drives --init {path} --label <name>\n"
        f"       If this is where a drive should be mounted, connect it first - registering an\n"
        f"       empty mountpoint creates a second drive id for a library you already have.",
        file=sys.stderr,
    )
    return None


def _ghost_at(path: Path, db: Path | None) -> GhostDrive | None:
    """The drive this path is recorded as, when no marker is there. ``None`` when unknowable.

    ⚠ **Opens the catalog read-only and only to ask**, so a resolver stays a resolver. It answers
    ``None`` when there is no catalog yet, which is right: a first run has recorded no
    expectation and so has none to violate.
    """
    if db is None or not db.is_file():
        return None
    # Through the session wrapper like every other surface open (`(adw)`'s guard): the decisions
    # trigger must not be bypassable, and a read-only question is no exception - a probe that
    # skipped it would be the one call site where the drive copy silently stops moving.
    with _catalog(db) as catalog:
        drives = [(str(d["uuid"]), str(d["label"])) for d in catalog.list_drives()]
        return ghost_drive_at(path, catalog, drives)


def remember_drive_root(catalog: Catalog, marker: DriveMarker, root: Path) -> None:
    """Record where this drive was just seen. `(afc)` half E.

    ⚠ **A guard that reads a hint is only as good as how often the hint is written**, and this is
    the whole of why `(afc)` was reachable: five CLI commands resolve a drive root and only two
    recorded it, so a CLI-only user accumulated drives whose location was unknown - and an
    unmounted mountpoint could not be told from a new folder. `cli.py` already said so at the one
    site that was fixed in isolation; this is that note applied everywhere.

    A **hint, never identity** (§3.1): a drive that remounts elsewhere is the same drive, and this
    key is simply stale until something sees it again.
    """
    remember_drive_path(catalog, marker.uuid, root)


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

        if plan.verdict is AdoptionVerdict.UNREADABLE:
            # ⚠ The refusal was already correct here - `source_repoint` treats an empty offer
            # list as NO_MATCH and stops - but the REASON it gave was wrong: "0 of 0 sampled
            # files matched by content" describes a mismatch, when nothing was compared. `(afn)`
            print(
                f"\nerror: {new_root} could not be read well enough to prove it holds the files "
                f"recorded under {old_root}.\n"
                "       Nothing was changed. Check the folder is fully mounted and readable, "
                "then run again.",
                file=sys.stderr,
            )
            return 2
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
    case the reconciliation was written for.

    ⚠ **THEY JOIN IN; THEY DO NOT OUTRANK.** This said *"on a fresh machine that list is simply
    empty"* until 2026-08-26, and `(ahz)` falsified it: recovering from a lost catalog by
    re-organizing REGISTERS the recovery folder as a drive and publishes a document to it seconds
    later, so on exactly the machine this command exists for the list is **not** empty - it holds
    a document derived from the very drive the user is restoring from, with a fresher stamp.
    Since `(ahz)`, the named root claims its own keys and the others fill only what it does not
    carry. Reading them is still right; letting them win was not.
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


def _note(note: RestoreNote) -> str:
    """The words for one note. The CLI holds no sentences of its own - `RESTORE_WORDING` does."""
    return RESTORE_WORDING[note].text


def _say(note: RestoreNote, **fields: object) -> None:
    """Print one note, with the marker its `actionable` flag decides.

    ⚠ **The marker is DERIVED, not typed at each site.** A real loss printed with the `-` used for
    "nothing to do" is reassurance where a warning belongs, and that is how it read before. `(aia)`
    """
    wording = RESTORE_WORDING[note]
    marker = "!" if wording.actionable else "-"
    print(f"\n  {marker} {wording.text.format(**fields)}")


def _print_omissions(applied: ApplyReport) -> None:
    """Every field `ApplyReport` computes that is not the restored half. **Looped, never listed.**

    🔑 **The loop IS the fix.** `not_applied`, `conflicting_trips` and `trips_without_days` were
    computed and printed by nobody, because this function named five fields and there were eight.
    Naming eight would produce the ninth omission. So the DERIVED inventory - the dataclass's own
    fields - is walked, and the DECLARATION - `REPORT_FIELD_NOTE` plus `REPORT_FIELD_EXCEPTIONS` -
    is indexed. `ENGINEERING_STANDARD.md` §4's seventy-second member, and a field in neither table
    raises `KeyError` here rather than being silently unprinted. `(ahx)`
    """
    for field in fields(applied):
        if field.name in REPORT_FIELD_EXCEPTIONS:
            continue
        note = REPORT_FIELD_NOTE[field.name]
        value = getattr(applied, field.name)
        if isinstance(value, dict):
            for section, count in sorted(value.items()):
                _say(note, count=count, section=section.replace("_", " "))
        else:
            for name in value:
                _say(note, name=name, section=str(name).replace("_", " "))


def _print_restore_plan(report: RestoreReport, documents: int) -> None:
    """What would come back, and - the half that is easy to leave out - what would not.

    A restore that reports 40 applied and says nothing about 12 corrections it could not place
    lets the user confirm on the good half only.

    ⚠ **THE PROMISE ABOVE WAS BROKEN BY THIS FUNCTION FOR AS LONG AS IT EXISTED**, which is why it
    is kept rather than softened: three fields were computed and printed by nobody. It is true as
    written because `_print_omissions` LOOPS the report's fields instead of naming them, and
    `test_every_report_field_reaches_the_reader` fails if one is neither worded nor a declared
    exception. `(ahx)`
    """
    print(f"\nRead {documents} decisions document(s).")
    applied = report.applied
    if applied.applied:
        for section, count in sorted(applied.applied.items()):
            print(f"  {count:>4}  {section.replace('_', ' ')}")
    else:
        print(f"  {_note(nothing_applied_note(applied))}")

    for name in applied.created_events:
        _say(RestoreNote.EVENT_CREATED, name=name)
    note = unmatched_events_note(applied)
    for name in applied.unmatched_events:
        _say(note, name=name)
    _print_omissions(applied)
    for loss in report.reconciled.superseded:
        _say(
            superseded_note(loss),
            count=loss.count,
            section=loss.section.replace("_", " "),
            label=loss.drive_label,
            swaps=render_swaps(loss.swaps),
        )
    # ⚠ **Only documents with nothing superseded are listed here.** An undated document that also
    # lost a value already said so through `LOST_UNDATED`, and printing both is how one drive got
    # two contradicting lines in one output. `(aia)`
    said = {loss.drive_label for loss in report.reconciled.superseded}
    for label in report.reconciled.undated:
        if label not in said:
            print(f"\n  - {label}'s document carries no date, so it could not overrule any other.")
    _print_restore_summary(applied, RestoreNote.SUMMARY_PREVIEW)


def _print_restore_summary(applied: ApplyReport, note: RestoreNote) -> None:
    """Both halves in one sentence, **including the zeroes**. `(ahx)`

    Taken from the one place the industry gets this right: IBM's `CPF3773` reports *"&1 objects
    restored. &2 not restored"* in a single message. A count of successes with no count of
    omissions beside it is what let `RSTOBJ` restore 74 of 75 and say *"74 restored"* - IBM's own
    manual notes the user *"is not notified that 1 object was not restored"*. Printing the second
    number always, zero included, makes that silence structurally impossible: a zero the reader
    sees is the difference between "nothing was left out" and "nobody looked".
    """
    _say(note, restored=restored_count(applied), withheld=withheld_count(applied))


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

        # ⚠ **Which document the user NAMED, carried into the merge for reporting.**
        # `_restore_documents_for` returns the named root first and every other document is found
        # through a stored hint - a distinction the merge has never had, so a hint-found document
        # overruling the drive the user typed reads exactly like any other loss. `(ahz)` step 1.
        # Positional convention is not relied on: the uuid is taken here and passed by name.
        named = documents[0].drive_uuid if documents else ""
        report = apply_documents(catalog, documents, apply=False, named_root_uuid=named)
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

        # ⚠ **The apply-time report was computed here and DISCARDED**, so the user saw the
        # preview's numbers and then the word "Restored" with nothing behind it. Measured: the two
        # reports are IDENTICAL in the ordinary case, so this is not a corrected number - it is
        # that the omissions are unchanged by applying and were never said at the moment they
        # became permanent. `(ahx)`
        report = apply_documents(catalog, documents, apply=True, named_root_uuid=named)
        print(f"\nRestored into {args.db}.")
        _print_restore_summary(report.applied, RestoreNote.SUMMARY_DONE)
        _print_omissions(report.applied)
        return 0


def _discard_to_drive(root: Path, catalog: object, *, apply: bool) -> int:
    """Overwrite the drive's document with this catalog's. **The destructive branch.**

    Closes `(aby)`: a decision deleted on this machine leaves the drive holding something the
    catalog does not, so every later save refuses with WOULD_LOSE and the drive copy quietly
    stops being updated - permanently, because nothing else reconciles the two. This is the user
    saying "mine is right". One forced write, after which the drive matches the catalog and the
    guard has nothing left to fire on. No override flag is stored, so there is no state to go
    stale.

    ⚠ **AND SINCE `(ahz)` STEP 3 IT CAN REACH A CASE IT COULD NOT BEFORE.** `would_lose` now counts
    a name REGRESSION under an unchanged identity, so this branch is offered where the drive holds
    the user's own name and the catalog holds a placeholder - the exact state a rebuilt catalog
    produces. Running it there destroys the last copy of that name. **That is still the right
    command for `(aby)`'s case and the wrong one here**, and nothing in the code can tell them
    apart: both are "the drive and the catalog disagree". So the preview names the values on both
    sides, and the two kinds are worded apart - a user who reads *"names 1 events differently:
    'Morning Market' -> 'placeholder B'"* can see which is theirs, where *"holds events this
    catalog does not"* told them nothing.
    """
    found = read_decisions(root)
    theirs = found.decisions
    marker = read_marker(root)
    uuid = marker.uuid if marker is not None else ""
    mine = gather_decisions(catalog, uuid)

    holdings = drive_holdings(theirs, mine) if theirs is not None else ()
    if not holdings:
        print("\nThis drive holds nothing this catalog is missing. Nothing to discard.")
        return 0

    print(f"\nDISCARD will overwrite the decisions on {root} with this catalog's.")
    # ⚠ **Two facts, worded apart.** A section can be here because the drive holds something this
    # catalog never had, or because it NAMES something differently - and since `(ahz)` widened
    # `would_lose`, the second is reachable. Printing "the drive holds events this catalog does
    # not" about a rename would be false, and it is the one sentence a user reads before agreeing
    # to overwrite the last copy of their own names.
    gone = [h.section.replace("_", " ") for h in holdings if h.missing]
    if gone:
        print(RESTORE_WORDING[RestoreNote.DRIVE_HOLDS_MORE].text.format(sections=", ".join(gone)))
    for holds in holdings:
        if holds.changed:
            print(
                "\n"
                + RESTORE_WORDING[RestoreNote.DRIVE_NAMES_DIFFERENTLY].text.format(
                    count=len(holds.changed),
                    section=holds.section.replace("_", " "),
                    swaps=render_swaps(holds.changed),
                )
            )
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
    print(f"\n{RESTORE_WORDING[RestoreNote.DRIVE_WRITTEN].text}")
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
    marker = _drive_or_explain(root, args.db)
    if marker is None:
        return 2
    when = _now_iso()
    with _catalog(args.db) as catalog:
        _say_if_two_places(catalog, marker, root)
        catalog.upsert_drive(uuid=marker.uuid, label=marker.label)
        # Remember where this drive was seen. Without it the CLI has no reachability information
        # at all and `truestill drives` can only ever say "unknown" - which is honest but
        # useless. Written here and at `--init` because those are the two moments the CLI holds
        # a resolved drive root and a catalog at the same time. It is a hint, never identity.
        remember_drive_path(catalog, marker.uuid, root)
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
        # The app's `service/verify.py` carries the reasoning for all three lines; this surface
        # must not drift from it. In short: a check dates the claim only for what it confirmed,
        # only MISSING is an absence, and the marker is re-read so a drive pulled out mid-run
        # cannot leave its remaining copies recorded as gone. `(abg)`.
        still_here = read_marker(root)
        for result in results:
            if result.status is CopyStatus.VERIFIED:
                catalog.mark_copy_verified(
                    sha256=result.copy.sha256, drive_uuid=marker.uuid, when=when
                )
            elif result.status is CopyStatus.MISSING and still_here is not None:
                catalog.mark_copy_missing(
                    sha256=result.copy.sha256, drive_uuid=marker.uuid, when=when
                )
        catalog.refresh_drive_verified(marker.uuid)

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
    #
    # ⚠ ONE VALUE, NOT TWO. There used to be a second call here - `standard_catalog_path()`, "where
    # the catalog belongs" - compared against this one to decide whether to offer a move. `(adw)`
    # retired the legacy lookup, which was the only state in which the two could differ, so the
    # comparison became vacuous and its only remaining input was string shape: a symlink in the
    # data directory made it fire on a catalog sitting exactly where it belongs. `(aeb)`.
    current = default_catalog_path()
    if not args.move:
        print(f"Catalog in use : {current}")
        print(f"Cache          : {cache_path_for(current)}")
        return 0

    result = move_catalog_to_standard(LEGACY_CATALOG_PATH, current)
    print(result.detail)
    if result.outcome is CatalogMoveOutcome.DESTINATION_EXISTS:
        return 2
    if result.outcome is CatalogMoveOutcome.SYMLINK_REFUSED:
        return 2
    return 0


def _source_root_or_none(given: Path, destination: Path | None) -> Path | None:
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

    ⚠ **``destination`` is ``None`` for an rclone remote**, the convention `_shas_on_destination`
    already uses for the same reason: a remote has no local filesystem to stage into, ask for free
    space, or read a per-file size limit from. The archive route needs all three, so it refuses -
    and the refusal is here rather than deeper because `extract_archive_set` would otherwise
    unpack into a local directory *named after the remote*. `(ahp)`
    """
    if given.is_dir():
        return given
    if not given.is_file():
        print(f"error: not a file or directory: {given}", file=sys.stderr)
        return None

    if destination is None:
        print(
            "error: an archive cannot be ingested to an rclone remote.\n"
            "       Unpacking needs a local folder with room for the extracted files.\n"
            "       Ingest to a local destination first, then copy it up.",
            file=sys.stderr,
        )
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


def _custody_age_lines(freshness: CustodyFreshness, route: str | None) -> list[str]:
    """The age of the claim and what it now MEANS, said ALWAYS rather than only when it is bad.

    Reporting freshness only once it is stale teaches a reader that its absence means fresh,
    which is the same defect one level up. A date that only gets older cannot mislead. `(abg)`.

    **Two things can be true at once, and both are said.** A place that has never been checked
    and a place checked 34 days ago are different claims, and a library can hold both - it is
    the shape of the maintainer's own. Stage 1 reported only the first, because its single date
    went `None` the moment anything was unchecked; `dated_at` carries the second. Never-checked
    LEADS, ordered by strength of evidence rather than severity: *no* evidence precedes *old*
    evidence.

    ⚠ **The date is never replaced by the age.** `abg.md:280` - a date that only gets older
    cannot mislead, and a bare *"34 days ago"* is not such a value. What legitimately changes
    with time is the tier; the date stays beside it.
    """
    lines: list[str] = []
    if freshness.never_checked:
        names = ", ".join(f"'{n}'" for n in freshness.never_checked)
        lines.append(
            f"Never checked: {names}. Truestill has not looked since the copy was written."
        )
    if freshness.dated_at is None:
        if not lines:
            lines.append("Nothing is on a drive yet, so there is nothing to have checked.")
        return lines + ([route] if route else [])
    day, days = freshness.dated_at[:10], freshness.dated_days
    if freshness.tier is CustodyTier.FRESH:
        lines.append(f"Last checked: {day} (the oldest of the drives holding copies).")
        # A fresh claim is offered no remedy of its own: there is nothing to remedy, and a
        # standing prompt on a healthy library is the nagging this entry exists to avoid. But a
        # never-checked place beside it is still unanswered, so the route survives for THAT.
        return lines + ([route] if route and freshness.never_checked else [])
    if freshness.tier is CustodyTier.SOFTENING:
        lines.append(
            f"Last checked: {day}, {_plural(days, 'day')} ago - long enough that this counts "
            "copies rather than confirms them."
        )
    else:
        lines.append(
            f"Last checked: {day}, {_plural(days, 'day')} ago. The copies still count; nothing "
            "has confirmed them since."
        )
    return lines + ([route] if route else [])


def _plural(n: int | None, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def _recheck_route(catalog: Catalog, holding: list[Any]) -> str | None:
    """How to re-check, named only when it can actually be followed.

    ⚠ **`(adx)` gap 2 is naming a remedy the reader cannot reach**, and `truestill verify` takes
    a required path that must be a connected drive root. So a real path is printed only for a
    drive whose reach is CONNECTED; otherwise the line says what to connect, which is the step
    that is actually available. A bare `truestill verify` would be the same defect reworded.

    **Reach is a filesystem read and the claim is catalog-derived** (`abg.md:203-207`), so this
    runs only when a route is being offered and its answer never feeds anything the claim
    states - it decides whether an ACTION is honest, nothing more.
    """
    # **The route follows the same lead rule as the wording.** Never-checked leads the claim, so
    # when one exists the route is about THAT drive - if it is not connected, the answer is to
    # connect it, not to offer a different drive that happens to be plugged in. Re-checking a
    # fresh drive because it is reachable would be a real path, a working command, and no answer
    # at all to the sentence above it. Only when nothing is unchecked does the route fall to the
    # oldest dated place.
    never = [d for d in holding if not d["last_verified"]]
    candidates = never or sorted(holding, key=lambda d: str(d["last_verified"]))
    if not candidates:
        return None
    for drive in candidates:
        uuid = str(drive["uuid"])
        hint = catalog.get_setting(drive_path_hint(uuid))
        if hint and drive_reach(hint, uuid) is DriveReach.CONNECTED:
            return f"  Re-check: truestill verify {hint}"
    return (
        f"  Re-check: connect '{candidates[0]['label']}', then run truestill verify on its folder."
    )


#: What `truestill self-check` cannot see, and where to see it. `truestill-cli` depends on
#: `truestill-core` alone (`IMPLEMENTATION_STANDARDS.md` §2), so the app's bundled typefaces are
#: genuinely out of reach here - and taking a dependency on the app to complete one command's
#: output would trade a boundary worth keeping for a sentence.
_APP_ASSETS_CHECKER = "truestill-app --self-check"


def _cmd_self_check(_args: argparse.Namespace) -> int:
    """Report what this install contains - the part core can answer for, and say which part it cannot.

    **The omission is stated, never left silent, and that is the whole design of this command.**
    A reader who sees nothing about the fonts will conclude the fonts are fine; "not checked here"
    is a third thing, distinct from a pass and distinct from silence, and it is rendered with its
    own mark and repeated in the closing line so it cannot be skimmed past.

    Exits non-zero when something core CAN see is degraded or missing. A surface that was not
    checked never fails the command - claiming a failure it did not observe would be the same
    dishonesty in the other direction.
    """
    findings = [
        *core_findings(),
        not_checked_finding("app fonts", _APP_ASSETS_CHECKER),
    ]
    for line in render(findings):
        print(line)
    return 0 if is_complete(findings) else 1


def _cmd_status(args: argparse.Namespace) -> int:
    with _catalog(args.db) as catalog:
        singles = catalog.single_copy_shas()
        # The same rule the app's custody strip uses, from core, so the two surfaces cannot drift.
        # That is why `(acr)`'s unambiguous naming arrives here without this line asking for it.
        registered = catalog.list_drives()
        holding = [d for d in registered if d["file_count"]]
        freshness = custody_freshness(catalog, holding, registered)
        # Inside the catalog block because the route needs a settings read, and only computed
        # when one is being offered: a fresh claim leaves `truestill status` touching no disk.
        route = (
            _recheck_route(catalog, holding)
            if freshness.never_checked or freshness.tier is not CustodyTier.FRESH
            else None
        )
    age = _custody_age_lines(freshness, route)
    if not singles:
        print("All catalogued content has at least two drive copies. Nicely redundant.")
        print("\n".join(age))
        return 0
    print(f"At risk: {len(singles)} file(s) exist on only ONE drive (3-2-1 wants >=2):")
    for r in singles[:_STATUS_PREVIEW]:
        print(f"  {r['original_name'] or r['sha256'][:12]}   only on '{r['drive_label']}'")
    if len(singles) > _STATUS_PREVIEW:
        print(f"  ... and {len(singles) - _STATUS_PREVIEW} more.")
    print("\n".join(age))
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


def _shas_on_destination(
    args: argparse.Namespace,
    drive_uuid: str | None,
    catalog: Catalog,
    destination: Destination,
) -> dict[str, str] | None:
    """What this destination already holds, for `(aei)`'s per-destination dedup.

    Three answers, and the difference between the last two is the whole point - see
    `organizer._scope_to_destination`:

    * **rclone** -> ``None``. Drive tracking is scoped to local destinations on purpose
      (`_local_drive_marker`), so a remote has no drive identity and `file_copies` can say
      nothing about it. Asking a per-drive question anyway would re-copy the whole remote every
      run. The catalog-global answer is the only one available and stays correct: an rclone
      remote is one always-online destination, which is the case global dedup actually fits.
    * **local, registered** -> sha -> the relative path recorded on that drive, which also
      lets the skip line name where the copy actually is.
    * **local, no marker** -> ``{}``. It provably holds no recorded copies. ⚠ This is
      the branch a PREVIEW takes on a fresh folder, because registration is gated on ``--apply``.
      Returning ``None`` here would make a preview predict "already in your library" for files
      the run then copies - a preview disagreeing with its own run, which is worse than the bug
      this fixes.
    """
    if args.rclone:
        return None
    if drive_uuid is None:
        return {}
    rows = catalog.copies_on_drive(drive_uuid)
    # ⚠ **A row is a claim; the destination is asked whether it is still true.** `(aja)`: an
    # interrupted run leaves rows for copies the medium never took, and skipping on that row is
    # how the re-run - the obvious remedy - repairs nothing. The stat this costs is the one
    # `sizes()` already does; see `dedup.credible_copies`.
    return credible_copies(
        {str(r["sha256"]): str(r["relative"]) for r in rows},
        sizes=destination.sizes(),
        expected={str(r["sha256"]): (None if r["size"] is None else int(r["size"])) for r in rows},
    )


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
        f"      already here : {match.matched_path}\n"
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


def _print_report(resolutions: list[Resolution], root_label: str, *, listing: bool) -> None:
    """The plan, file by file - the argument for what this run is about to do.

    ⚠ **Printed only while there is still a decision to make.** This block and `_print_execution`
    are two different documents that this one function served as one: a decision sheet read before
    typing a word, and a listing scrolled past after the run was already authorised. Under
    `--apply` the decision is made, so the argument is not read - it is **7 lines per file**,
    measured, which is 105,585 lines on a 15,082-file library standing between the user and the
    result they asked for.

    ⚠ **`listing=False` prints NOTHING, and that is deliberate rather than unfinished.** Every
    count these three headers carried is in `_print_summary` two lines below; the duplicate origins
    are in `_print_execution`; and every file - with what actually **happened** to it rather than
    what was planned - is in the record named at the end of the run. A compact tally here would be
    a second copy of `_print_summary`'s, which is the `(abl)` shape this file has already paid for
    once: two blocks of one report, free to disagree. `(afm)`
    """
    if not listing:
        return
    # Disjoint buckets, not `should_upload`: an unreadable file has no hash, so it matches
    # nothing and would otherwise be listed under "NEW UNIQUE - would be organized" while the
    # block below says Truestill could not read it. `_print_unreadable` names them instead.
    buckets = partition_for_report(resolutions)
    unique = buckets.unique
    near = buckets.near_duplicates
    exact = buckets.exact_duplicates

    print(_SEPARATOR)
    # NOT "would be organized": near-duplicates below are organized too, so this header claimed
    # the whole organized set while listing part of it. `(abl)`, the CLI twin of the app's tally
    # row. Note `_print_summary` has always been honest about this pair - "organized (unique)" /
    # "organized (near-dup)" - so the two blocks of this same report disagreed with each other.
    print(f"NEW UNIQUE ({len(unique)}) - no match in your library")
    print(_SEPARATOR)
    for resolution in unique:
        print(_format_new(resolution, root_label))
        print()

    print(_SEPARATOR)
    print(f"NEAR-DUPLICATES ({len(near)}) - ORGANIZED TOO, and listed here for review")
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


def _print_skipped_undated(
    resolutions: list[Resolution], skip_undated: bool, *, listing: bool
) -> None:
    """Name every undateable file that --skip-undated left behind. Never silent.

    ⚠ **Never silent, but not always here.** Under `--apply` each of these files carries an
    `ActionStatus.SKIPPED_UNDATED` result with its reason, so it is counted by `_print_execution`
    and named in the record. Under a preview **no record is written**, so this block is the only
    copy there is and it prints in full however long it runs. That asymmetry is the whole of
    `(afm)`: what may be dropped is what something else still holds. `(afd)`'s cap was
    uncomfortable precisely because the elided lines were the only copy.
    """
    if not listing or not skip_undated:
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


def _print_preflight(preflight: DestinationPreflight) -> None:
    """Say up front when the destination cannot hold this run.

    Printed during a **preview**, where nothing is written and the refusal would be pointless:
    a plan that reads as clean and then fails on ``--apply`` moves the discovery to after the
    user has already committed. ``execute`` refuses the apply itself, from the same answer, so
    this is a second reading rather than a second check.

    ⚠ **Takes the answer rather than computing it** (`(aek)`). `_run_pipeline` needs the same
    verdict to decide whether the destination may be registered at all, and two calls would be two
    `stat` passes over every write candidate - ~600 us each on a FUSE library
    (`PERFORMANCE.md` §3.1), which is the whole tier-0 budget again. One reading, three readers.
    """
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


def _print_summary(resolutions: list[Resolution], *, skip_undated: bool, apply: bool) -> None:
    """The plan's own tally. **A plan, and under ``--apply`` it says so.** `(aim)`

    ⚠ **This block is printed BEFORE `execute` runs, on every path including `--apply`**, and its
    rows are past participles. `(abl)` called them *"always been honest"* and they are - of a
    preview, which is the only document anyone read them as. The moment `--apply` prints them
    above a run that has not happened, they are a plan wearing an outcome's tense.

    🔑 **The identical defect was fixed one artifact over and never reached the screen.** `(afl)`
    deleted the plan-time *run record* write, and the comment that replaced it in
    `_print_run_reports` is the whole argument: *"it answered 'what would happen', the record
    answers 'what happened', and one file cannot honestly be both."*

    **Retensed, not recounted, and not suppressed.** The numbers are right for what they are, and
    `(afm)` kept these counts under `--apply` deliberately - *"the moment is the same, the document
    is not"* - because this is the last thing on screen before a long copy starts. So the header
    names the document and `EXECUTED` is pointed at by name.

    **Both flags are required and neither has a default**, for the reason
    `ReportBuckets.will_organize`'s docstring gives about its own: they change the answer, and a
    default is an assumption a second caller would inherit silently.

    ⚠ **THE TENSE IS A HUMAN READ AND NOTHING GUARDS IT.** A test can assert this header string is
    present; that pins a string, not honesty - the next person to reword the block can satisfy it
    and put the defect straight back. Said here so no one infers from a green suite that it is
    covered. See `test_the_screen_accounts_for_every_file.py`.
    """
    buckets = partition_for_report(resolutions)
    organized = buckets.organized
    labels = Counter(r.decision.category.label for r in organized)
    sources = Counter(r.decision.date_source.value for r in organized)

    print(_SEPARATOR)
    print("SUMMARY - the plan. What happened is in EXECUTED, below." if apply else "SUMMARY")
    print(_SEPARATOR)
    # These four must sum to `files analysed`. The buckets are disjoint by construction
    # (`partition_for_report`) and the sum is asserted by `test_summary_tally_is_disjoint`;
    # the zero case still prints, because a law a reader cannot add up is not on screen.
    print(f"  files analysed     : {len(resolutions)}")
    print(f"  organized (unique)  : {len(buckets.unique)}")
    print(f"  organized (near-dup): {len(buckets.near_duplicates)}  (kept + flagged for review)")
    print(f"  skipped (exact dup): {len(buckets.exact_duplicates)}")
    print(f"  could not be read  : {len(buckets.unreadable)}")
    # ⚠ **A FIFTH ROW BESIDE THE FOUR, NEVER A SUBTRACTION INSIDE THEM.** `(acx)` is live on this
    # surface: `--skip-undated` leaves undated files in `buckets.unique`, so the four rows above
    # promise files the run will not take. The correction is NOT to subtract them from `unique` -
    # those four are pinned to sum to `files analysed` by `test_summary_tally_is_disjoint`, and
    # taking undated out of one of them would repair `(acx)`'s law by breaking `(aac)`'s.
    # `will_organize` is their sum minus undated, so it belongs beside them as its own line.
    #
    # **`ReportBuckets.will_organize` is "the one home for that number" and the whole of
    # `truestill-cli` had never called it** - the only production caller was the app, which is
    # why `(acx)` was fixed there and left standing here.
    print(f"  to organize        : {buckets.will_organize(skip_undated=skip_undated)}")
    print(f"  folders derived    : {len(labels)}")
    for label, count in labels.most_common():
        print(f"      {label:<28} {count}")
    # ⚠ EVERY LINE FROM HERE TO `_print_capture_timeline` DESCRIBES THE **ORGANIZED** SET, WHICH
    # CAN BE EMPTY WHILE `files analysed` IS IN THE THOUSANDS - a re-run of an already-organized
    # folder is exactly that. Describing an empty set produced a sentence that was false about
    # the files a reader had just seen counted, and that contradicted the line below it:
    #
    #     capture dates      : none of these files carries a capture date
    #         undated x0
    #
    # `capture_span` returns None both for "no file had a date" and for "there were no files",
    # and the empty case took the first branch's wording. Say what is true - nothing was
    # organized - and make no claim about the dates of no files. `(aej)`.
    if not organized:
        print("  no files were organized, so there is nothing here to describe.")
    else:
        print("  date sources (organized files):")
        for source, count in sources.most_common():
            print(f"      {source:<28} {count}")
        _print_date_quality(organized)
        _print_inferred_local_shifts(organized)
    # Sized once, here, and shared by both blocks below: one stat pass rather than two.
    sizes = sizes_for(resolutions)
    if organized:
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


#: Quoted fragments in a failure detail are the per-file parts - the source path, the destination
#: path. Removing them leaves the REASON, which is what a reader needs counted.
_QUOTED = re.compile(r"""(['"]).*?\1""")


def _reason_key(detail: str) -> str:
    """A detail with its per-file parts removed, so identical failures collapse to one reason.

    ⚠ **An approximation over a string, and it is one because `detail` is a string.** Measured
    2026-08-22: 2,096 failures from one refused destination carry 2,096 *distinct* details,
    because each names its own source and target - so counting them verbatim would report 2,096
    reasons for one fact. Stripping quoted fragments collapses them correctly and keeps genuinely
    different causes apart, because the part that differs between `[Errno 13]` and `[Errno 28]`
    is not quoted.

    **The exact key belongs to `(aep)`**, which asks whether `detail` should be structured rather
    than free text. Until it is, this is text normalisation and is labelled as such rather than
    presented as a taxonomy.
    """
    return " ".join(_QUOTED.sub("", detail).split())


def _print_capped(results: list[ActionResult], *, label: str) -> None:
    """Name the first `_STATUS_PREVIEW` results, then say how many more and how many reasons.

    ⚠ **Both of these lists were uncapped until 2026-08-22, and this is one fix for two sites**
    because they were the same six lines twice. Measured on a real library: a destination that
    refused after ten files produced **2,096 `FAILED` lines from ONE reason** - a fact printed
    2,096 times, next to an `EXECUTED` summary that already said `2096  failed`. `(afd)`

    **On `stderr`, and it stays there.** clig.dev is explicit that errors and messaging belong on
    `stderr` - moving a failure report to `stdout` would feed it into whatever the user piped the
    run into. What clig also says is *"don't treat `stderr` like a log file, at least not by
    default"*, and 2,096 lines is exactly that. **The stream was never the defect; the volume
    was**, which is why `organize ... > log.txt` did not help: the flood was on the other stream.
    """
    if not results:
        return
    for result in results[:_STATUS_PREVIEW]:
        print(
            f"  {label}: {result.resolution.decision.source.name}: {result.detail}",
            file=sys.stderr,
        )
    if len(results) <= _STATUS_PREVIEW:
        return
    reasons = len({_reason_key(r.detail or "") for r in results})
    # "all the same reason" is the common case and the one worth saying plainly; a mixed tail
    # needs its own count or the elision hides that the failures were not one fact.
    tail = "all the same reason" if reasons == 1 else f"{reasons} distinct reasons in total"
    print(
        f"  ... and {len(results) - _STATUS_PREVIEW:,} more {label} ({tail}).",
        file=sys.stderr,
    )


def _print_unnameable(results: list[ActionResult]) -> int:
    """Name every file whose organized name will not fit, in a preview. Returns how many. `(aid)`

    Silent when there are none, like the other never-silent blocks: this reports what happened,
    and *"no file had this problem"* is not an event. Under `--apply` the same results reach
    `_print_execution`'s `FAILED` list instead, so the sentence has one producer and two homes -
    `layout.explain_name_too_long` - rather than two wordings.
    """
    named = [r for r in results if r.name_too_long]
    if not named:
        return 0
    print(f"\n  NAMES TOO LONG FOR THE DESTINATION ({len(named)}):")
    for result in named[:_STATUS_PREVIEW]:
        print(f"      {result.resolution.decision.source.name}: {result.detail}")
    if len(named) > _STATUS_PREVIEW:
        print(f"      ... and {len(named) - _STATUS_PREVIEW:,} more.")
    return len(named)


def _print_execution(results: list[ActionResult], resolutions: list[Resolution]) -> int:
    """What the run actually did. **The outcome document, and the only one.** `(aim)`

    ``resolutions`` is here for one line: the files that produced no `ActionResult` at all. A stop
    leaves them absent from ``results`` entirely, so every status row below can be true while the
    block still accounts for fewer files than `SUMMARY` analysed.
    """
    # Human wording, shared with the app: 'uploaded' is backend vocabulary for an event
    # that did not happen on a local disk, and never reaches a user.
    outcomes = Counter(status_label(result.status) for result in results)
    print(_SEPARATOR)
    print("EXECUTED")
    print(_SEPARATOR)
    for status, count in outcomes.most_common():
        print(f"  {count:>7}  {status}")
    # ⚠ **THE DIVERGENCE IS NAMED, NOT LEFT TO SUBTRACTION**, and this is the only number on
    # screen that says a run did not reach every file it planned to. `run_record.stop_block`
    # already derives it and already returns `None` when there is nothing to say, so this reads
    # its answer rather than computing a second one - two subtractions of the same fact are free
    # to disagree, which is `(afm)`'s ruling one level down.
    #
    # ⚠ **The COUNT only; the reason is deliberately not reprinted.** `stop_block` carries one,
    # but it is the last `FAILED` detail - already on screen in the `FAILED` block below and in
    # the `error:` line above. `(afm)` again: *a second copy of a number is free to disagree with
    # the first*, and that goes for a sentence too. Same reason there is no "planned N, did M,
    # difference K" line: the difference has one home and this is it.
    stopped = stop_block(resolutions, results)
    if stopped is not None:
        # Same vocabulary as the run record's own per-file status, so a reader moving between the
        # screen and `last-run.json` meets one word for one idea (`run_record.files_from_resolutions`).
        print(f"  {stopped['never_attempted']:>7}  not attempted")
    _print_duplicate_origins((r.resolution for r in results), indent="           ")
    _print_mechanism_split(results)

    # ⚠ **`(aie)`'s fix must not be a SILENT one.** Keeping a file whose `copystat` was refused is
    # right; keeping it quietly would trade a false failure for an invisible degradation - and the
    # condition belongs to the **mount**, so it does not happen to one file, it happens to every
    # file of the run. `_print_capped` is reused rather than reinvented because `(afd)`'s cap is
    # exactly what this needs: 500 identical lines would be that defect again. Selected on
    # `metadata_ok`, never by matching the prose in `detail`.
    _print_capped([r for r in results if not r.metadata_ok], label="METADATA NOT SET")
    _print_capped([r for r in results if r.status is ActionStatus.MOVE_KEPT], label="MOVE KEPT")
    failures = [r for r in results if r.status is ActionStatus.FAILED]
    _print_capped(failures, label="FAILED")
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
    # `uploads` is `buckets.organized` - unique AND near-duplicates - so "(unique)" named less
    # than the number counted. The inverse of `(abl)`'s defect, found while checking it.
    print(f"  kept (unique + look-alikes)      : {len(uploads)}")
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


def _registration_wanted(args: argparse.Namespace, marker: DriveMarker | None) -> bool:
    """Whether this run must mint an identity for its destination.

    **Gated on ``--apply``**, so a preview registers nothing; that is why no opt-out flag was
    added rather than one being argued for. **rclone destinations are excluded**, for the reason
    `_local_drive_marker` gives: always-online cloud is not a drive-in-a-drawer.

    An existing marker means nothing is written - re-minting a uuid would orphan every copy
    already recorded against the old one (§3.1).
    """
    return marker is None and bool(getattr(args, "apply", False)) and not args.rclone


def _approve_registration(args: argparse.Namespace, marker: DriveMarker | None) -> None:
    """Settle whether this destination MAY become a drive. Writes nothing. `(aek)`

    **The half that must stay early.** A ghost refusal and the typed `new` confirm are the answers
    a user needs before anything expensive happens; asking them after the hashing pass would make
    someone who pointed at an unmounted mountpoint wait out a full read of their library to be
    told so. So the decision keeps its place and only the WRITE moves behind the space check.
    """
    if not _registration_wanted(args, marker):
        return
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


def _register_destination(
    args: argparse.Namespace, marker: DriveMarker | None
) -> DriveMarker | None:
    """Give the destination a drive identity, so the run's own files attach.

    **The gap this closes.** Until 2026-08-05 the CLI read a marker and never created one, so
    organizing into an ordinary folder wrote `files` rows with **no** `file_copies` row: in the
    dedup index, so a re-run skips those files forever, and outside custody, so `verify`,
    `status` and `where` cannot see them. The app has done the opposite since the bug it
    replaced - `service/organize.py` does `read_marker(dest) or create_marker(dest, ...)` with a
    comment saying that doing it afterwards "would leave the run's own files unattached". Same
    operation, two custody outcomes, decided by which surface the user picked.

    `IMPLEMENTATION_STANDARDS.md` §3.1 already sanctions the creation - it "happens automatically
    where the user's action already implies it", and names the organize destination.

    ⚠ **Called AFTER the preflight, and that ordering is `(aek)`.** This is the first thing the
    product wrote to a new drive, so on a full disk it raised before the run reached the sentence
    that explains a full disk - which it already had, and already words correctly. The approval
    above runs early; this runs once the destination has been shown able to hold the work.

    ⚠ **And it must still stay ahead of the first COPY**, which is the older constraint and the
    reason this is a move rather than a deletion: an identity minted afterwards leaves the run's
    own files unattached.

    :raises DriveWriteError: the drive would not accept its marker. Deliberately propagated to
        `_registered_or_refused`, which already turns `DriveGhostError` into exit 4 and words this
        the same way - both are *this destination cannot be used*.
    """
    if not _registration_wanted(args, marker):
        return marker
    root = Path(args.destination)
    created = create_marker(root, label=root.name or "Library")
    with _catalog(args.db) as catalog:
        # Structurally silent today: `created` carries a freshly minted uuid, so there is no
        # remembered path to disagree with. Called anyway so a future change that reuses an
        # existing identity here cannot bypass the check - the guard enumerates this site.
        _say_if_two_places(catalog, created, root)
        # Record WHERE, not just that it happened. Five other sites write this hint and this one
        # did not, which is why a CLI-only user accumulates drives whose location is unknown -
        # and why nothing could tell an unmounted mountpoint from a new folder.
        remember_drive_path(catalog, created.uuid, root)
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


def _approved_or_refused(args: argparse.Namespace, marker: DriveMarker | None) -> int | None:
    """``None`` when the destination may be registered, or the exit code to return.

    Shaped like `_destination_or_exit` and for the same reason: the refusal is an actionable
    sentence rather than a traceback (ENGINEERING_STANDARD 4).
    """
    try:
        _approve_registration(args, marker)
    except DriveGhostError as refusal:
        # Exit 4 is this repo's "unusable destination", alongside 3 for a missing exiftool.
        print(f"error: {refusal}", file=sys.stderr)
        return 4
    return None


def _print_run_reports(
    args: argparse.Namespace,
    resolutions: list[Resolution],
    destination: Destination,
    preflight: DestinationPreflight,
    scan: TakeoutScan | None,
) -> None:
    """Everything this run says about what it found, before it is allowed to write anything.

    One unit because it is one moment - the plan, while the user can still stop it - and keeping it
    here holds `_run_pipeline` under its branch ceiling rather than raising the ceiling to fit
    `(aek)`'s gate in.

    ⚠ **"While the user can still stop it" is the whole of `(afm)`, and it was not true of every
    line here.** Under `--apply` the user has already stopped considering; the per-file argument is
    printed to someone who has decided, at 7 lines a file. So the two per-file listings take
    `listing=not args.apply` and the counts stay unconditional - the moment is the same, the
    document is not.
    """
    _print_report(resolutions, destination.describe(), listing=not args.apply)
    _print_summary(resolutions, skip_undated=args.skip_undated, apply=args.apply)
    _print_skipped_undated(resolutions, args.skip_undated, listing=not args.apply)
    _print_heif_note(resolutions)
    _print_preflight(preflight)
    if scan is not None:
        _print_ingest_report(resolutions, scan)
    # ⚠ The plan report used to be written HERE, before execution. It is gone rather than moved:
    # it answered "what would happen", the record answers "what happened", and one file cannot
    # honestly be both. A preview therefore writes nothing at all now - which also makes the
    # DRY RUN banner's "nothing was written or recorded" true, where it was not before. `(afl)`


def _record_the_run(
    args: argparse.Namespace,
    resolutions: list[Resolution],
    results: list[ActionResult],
    *,
    stopped: dict[str, object] | None = None,
) -> None:
    """Write the record and name it. **Automatic, because opt-in gets it wrong for one user.**

    ⚠ The user who most needs the record is the one who did not know to ask for it - which is why
    `--report` stops deciding *whether* a record exists and now only says *where* it goes.

    ⚠ **Written AFTER execution, so a hard kill between the last file and this loses it.** The
    design survives a stop and not a `SIGKILL`. Stated rather than assumed; `organize_runs` covers
    the killed run from the other side (`(aem)`), and per-file writes are their own performance
    question. `(afl)`
    """
    path = args.report if getattr(args, "report", None) else record_path_for(args.db)
    payload = build_run_record(
        RunHeader(kind="organize", source=str(args.source), destination=str(args.destination)),
        files=files_from_resolutions(resolutions, results),
        intended_total=len(resolutions),
        attempted=len(results),
        stopped=stopped if stopped is not None else stop_block(resolutions, results),
    )
    # ⚠ **`record_organize`, not `write_run_record`**: every run needs its index line, or a
    # superseded record can be pruned with nothing left saying the run happened. `--report PATH`
    # still says only WHERE the detail goes, so a custom path skips the history entirely - which
    # is what a caller asking for a one-off report has asked for.
    error = (
        write_run_record(path, payload)
        if getattr(args, "report", None)
        else record_organize(args.db, payload)
    )
    if error is not None:
        # The run itself succeeded or failed on its own terms; the paperwork must not restate it.
        print(f"\n  Could not write the run record to {path}: {error}", file=sys.stderr)
        return
    print(f"\n  This run is recorded in {path}")


def _stopped_run_exit(
    args: argparse.Namespace,
    resolutions: list[Resolution],
    exc: RunStoppedError | DestinationError,
) -> int:
    """Record what the run managed, say what stopped it, and give the exit code. `(agj)`

    ⚠ **TWO STOPS THAT ARE NOT VARIANTS OF EACH OTHER, kept side by side so the difference is
    visible rather than twenty lines apart.**

    * `DestinationError` is a refusal **before the first byte** - `execute` has not started, so
      `results` really is empty and every file really was never attempted.
    * `RunStoppedError` is a stop **mid-run**. Passing the same hardcoded block here wrote a
      record claiming a run that had already copied files attempted none of them: **a false
      custody record, which is worse than no record.** `stop_block` needs no help deriving the
      reason, because `(agi)` records the offending file as `FAILED` with it *before* re-raising.

    One handler rather than two also keeps `_run_pipeline` under its branch ceiling, which
    `IMPLEMENTATION_STANDARDS.md` answers by extracting rather than by raising the limit.

    🔑 **AND UNTIL 2026-08-30 THIS PRINTED NO OUTCOMES AT ALL, WHICH DEFEATED `(agi)` AT THE ONE
    SURFACE THE USER LOOKS AT.** `(agi)` records the offending file as `FAILED` *before*
    re-raising, precisely so the reason survives the stop; `(agj)` then built `RunStoppedError`
    around carrying `results` out of the dying frame. Both arrived here and stopped. The screen
    got the plan's `organized (unique): 3`, one `error:` line and exit 4 - **the plan number was
    the only count on it** - while `last-run.json` held `attempted: 1`, one `failed` and two
    `not attempted`. Measured on both raising routes before this line was written. `(aim)`

    **So the block prints here too, and the exit code is still the stop's.** `_print_execution`
    returns 1-on-failures for the ordinary path; a stopped run is `4` - *this destination cannot
    be used* - and that answer does not change because the block above it now exists.
    """
    # ⚠ Before the `error:` line and before any re-raise: what landed is true whatever stopped the
    # run, including when what stopped it was a defect of ours. On the `DestinationError` arm this
    # is an empty block plus "N not attempted", which is exactly what happened - `execute` refused
    # before the first byte, so nothing was tried and the block says so rather than being absent.
    results = exc.results if isinstance(exc, RunStoppedError) else []
    _print_execution(results, resolutions)
    if isinstance(exc, RunStoppedError):
        _record_the_run(args, resolutions, exc.results)
        if not isinstance(exc.__cause__, OSError | DestinationError):
            # A defect of ours, not an answer about the destination. The paperwork is written -
            # that is this function's whole job - and the traceback is left standing rather than
            # dressed up as a user-facing refusal wearing a destination exit code.
            raise exc
    else:
        _record_the_run(
            args,
            resolutions,
            [],
            stopped={"never_attempted": len(resolutions), "reason": str(exc)},
        )
    print(f"error: {exc}", file=sys.stderr)
    return 4


def _registered_or_refused(
    args: argparse.Namespace,
    marker: DriveMarker | None,
    catalog: Catalog,
    destination: Destination,
    preflight: DestinationPreflight,
) -> tuple[DriveMarker | None, str | None] | int:
    """The destination's drive identity and uuid, or the exit code to return.

    Doing the upsert here keeps `_run_pipeline` under its branch ceiling rather than raising it.

    ⚠ **THE SPACE CHECK IS PART OF THE REFUSAL, AND ITS POSITION IS `(aek)`.** Registering writes
    the marker - the first thing this product ever puts on a new drive - so on a full disk that
    write raised a `pathlib` traceback a few steps from a copy path that reports the same errno per
    file, and the run died before reaching the sentence that explains a full disk. The product
    already had that sentence and it was already right; only the order was wrong.

    **Not a second check.** `preflight_for_run` is the one function that decides, and its own
    docstring calls the report and the refusal *"two readings of its answer"*. This is a third
    reading of the SAME object `_print_run_reports` just printed - no extra `stat` pass - and
    `execute` still refuses on its own, so core keeps the one home a third surface inherits.

    `DriveWriteError` joins `DriveGhostError` on the same exit code because they are the same
    answer to the user - *this destination cannot be used*. Ordering cannot cover a read-only
    drive, one unplugged mid-write, or one that fills between the check and the write, so the
    typed refusal is what carries those.
    """
    if args.apply and not preflight.may_proceed:
        message = f"{destination.describe()} cannot hold this run. {preflight.detail()}"
        print(f"error: {message}", file=sys.stderr)
        return 4
    try:
        resolved = _register_destination(args, marker)
    except (DriveGhostError, DriveWriteError) as refusal:
        print(f"error: {refusal}", file=sys.stderr)
        return 4
    if resolved is None:
        return None, None
    catalog.upsert_drive(uuid=resolved.uuid, label=resolved.label)
    print(f"Destination is drive '{resolved.label}' ({resolved.uuid[:8]}...).\n")
    return resolved, resolved.uuid


def _open_organize_run(
    catalog: Catalog,
    args: argparse.Namespace,
    drive_uuid: str | None,
    resolutions: list[Resolution],
    on_destination: dict[str, str] | None,
) -> None:
    """Record that a copy-mode organize has STARTED, before the first byte. `(aem)`.

    ⚠ **After the process dies the intended total cannot be reconstructed**, because the restart's
    own total correctly excludes what already landed - so 4,105 exists only in this row.

    `intended_total` is **what the drive will HOLD when this run finishes** - current holdings plus
    what this run adds - not what the run writes. The write count differs across a restart (4,105
    then 3,765) and cannot be compared; the target is 4,105 both times.

    Both halves are already in hand and cost nothing: `on_destination` was computed for `(aei)`'s
    per-destination dedup, and `write_candidates` for the preflight, which has already paid for
    the stats it gathered.
    """
    if drive_uuid is None or not args.apply:
        return
    catalog.start_organize_run(
        drive_uuid=drive_uuid,
        run_id=uuid.uuid4().hex,
        intended_total=len(on_destination or {})
        + len(write_candidates(resolutions, skip_undated=args.skip_undated)),
    )


def _close_organize_run(catalog: Catalog, args: argparse.Namespace, drive_uuid: str | None) -> None:
    """Close the run opened by :func:`_open_organize_run`.

    ⚠ **An optimisation, never a correctness requirement.** A crash between the last file and this
    call leaves the row open on a run that actually finished; `unfinished_organize_run` derives the
    answer from what the drive HOLDS, so that case still reads as complete. `migrate` is immune to
    its own identical window the same way, by reporting pending journal rows rather than a status.
    """
    if drive_uuid is None or not args.apply:
        return
    catalog.finish_organize_run(drive_uuid)


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
    #: Folders this run emptied and could offer to clean, counted inside the catalog block and
    #: printed after the report. Zero unless a completed in-place run left some. `(afi)`
    emptied_folders = 0
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

        refusal = _approved_or_refused(args, drive_marker)
        if refusal is not None:
            return refusal

        # ⚠ FROM THE MARKER, never from registration. `(aei)` requires the destination's identity
        # to be an INPUT to the dedup decision, and `(aek)` moves the marker WRITE behind the
        # space check - so the uuid has to come from something that is true before either.
        # It is: `_local_drive_marker` already read it off disk before this pipeline started.
        #
        # The three branches are unchanged by that move, which is what makes it safe:
        #   marked   -> the real uuid, so `file_copies` answers for real
        #   unmarked -> None -> `{}`, which is what a freshly minted uuid would also return,
        #               because a brand-new drive holds no recorded copies
        #   rclone   -> None from `_shas_on_destination` itself, catalog-global as before
        # Pinned by `test_dedup_scope_comes_from_the_marker.py`.
        drive_uuid = drive_marker.uuid if drive_marker is not None else None
        on_destination = _shas_on_destination(args, drive_uuid, catalog, destination)
        resolutions = resolve(
            decisions,
            index,
            catalog_sizes=catalog.known_sizes(),
            pool=args.pool,
            workers=args.workers,
            progress=_progress_printer("hashing"),
            cache=cache,
            on_destination=on_destination,
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

        preflight = preflight_for_run(resolutions, destination, skip_undated=args.skip_undated)
        _print_run_reports(args, resolutions, destination, preflight, scan)

        resolved = _registered_or_refused(args, drive_marker, catalog, destination, preflight)
        if isinstance(resolved, int):
            return resolved
        drive_marker, drive_uuid = resolved

        if relocation is not None and args.apply:
            catalog.start_inplace_run(
                run_id=relocation.run_id,
                source_root=str(relocation.source_root),
                dest_root=str(relocation.dest_root),
                drive_uuid=drive_uuid,
            )

        _open_organize_run(catalog, args, drive_uuid, resolutions, on_destination)

        results: list[ActionResult] = []
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
        except (RunStoppedError, DestinationError) as exc:
            return _stopped_run_exit(args, resolutions, exc)

        _close_organize_run(catalog, args, drive_uuid)
        if relocation is not None and args.apply:
            moved = sum(1 for r in results if r.status is ActionStatus.MOVED_IN_PLACE)
            # A run that renamed nothing leaves no journal row to offer as an undo.
            if moved:
                catalog.finish_inplace_run(relocation.run_id)
                # ⚠ Counted HERE and printed after the report, because the catalog closes with
                # this block and the journal has to be FINISHED before it is read - the line
                # above is what makes these rows visible. `(afi)`
                emptied_folders = _emptied_folder_count(catalog, drive_uuid, Path(args.destination))
            else:
                catalog.discard_inplace_run(relocation.run_id)

    print()
    if not args.apply:
        # Nothing was copied, so nothing can have FAILED: a preview names every unreadable
        # source, or no one does.
        unreadable = _print_unreadable(resolutions)
        # ⚠ **A PREVIEW PREDICTS THE RUN, and this is the one refusal it can predict exactly.**
        # `execute` decides it at composition time for `apply` and preview alike, so the answer
        # here is the answer the run will give. `IMPLEMENTATION_STANDARDS.md` makes the exit code
        # part of that rule: predicting `0` for a run that will exit `1` chains `organize &&
        # next_step` past a library Truestill could not account for. `(aid)`
        unnameable = _print_unnameable(results)
        _print_uncompared(resolutions, args.phash_threshold)
        _print_suppressed_noise()
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
        return 1 if unreadable or unnameable else 0
    code = _print_execution(results, resolutions)
    _record_the_run(args, resolutions, results)
    # ⚠ The banner this run printed says "Empty folders left behind are reported, never deleted",
    # and until 2026-08-22 nothing here reported them: `_offer_cleanup` was wired into
    # `migrate-layout` alone, and the comment below claimed an offer "follows" that did not
    # exist on this path. `(afi)`
    if emptied_folders:
        print(
            f"\n{emptied_folders} folder(s) are now empty. Review and remove them with:"
            f"\n  truestill clean-empty {args.destination}"
        )
    # And what it left, after the fact. The result answers a different question from the
    # preview - not what will happen, but what to do now - and it is the only place the files
    # still sitting in the source are explained at all: the empty-folder offer above names the
    # folders the move DID empty and is silent about these by construction.
    _print_left_in_source(args, relocation, results)
    failed = frozenset(
        r.resolution.decision.source for r in results if r.status is ActionStatus.FAILED
    )
    # Whatever FAILED has already been named above; this catches the rest - most often an
    # unreadable file whose cached hashes made it an exact duplicate, so it was never copied
    # and never failed, and would otherwise be the one file nobody mentions.
    named = _print_unreadable(resolutions, failed)
    _print_uncompared(resolutions, args.phash_threshold)
    _print_suppressed_noise()
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
    # ⚠ THE HEADING NAMES THE CONSEQUENCE, NOT ONE OF THE FIVE CAUSES. `(aew)` It read "Files
    # that could not be read" and sat directly above rows saying *"could be read, but its
    # contents could not be decoded"* - a heading contradicting its own list, which is what
    # `UNDECODABLE` arriving in `(aet)` did to a sentence written when there were four reasons.
    # "Not organized" is true of all five and is the fact the user acts on.
    print("\nFiles that were not organized:")
    # A count here, and deliberately NONE on the "could not be OPENED" folder line above.
    # For a folder the number of files inside is exactly what could not be read, so printing
    # one would invent the missing figure; for a file the number is known exactly. The
    # asymmetry is the point, not an oversight - do not "make these consistent".
    # ⚠ The verbs differ for that reason and `(aer)` restored it: this line and the folder one
    # both said "could not be read" until 2026-08-21, one phrase for the counted fact and the
    # uncountable one. `models._FOLDER_SKIP_LABELS` carries the argument.
    print(f"  files not organized: {len(named):,}")
    # ⚠ GROUPED BY REASON, BECAUSE THE REMEDY IS PER REASON. `(aew)` This printed one sentence -
    # "fix the permission or check the disk" - under every file whatever the reason, and on the
    # format corpus 8 of 8 named files were UNDECODABLE, where neither the permission nor the
    # disk is at fault. `UnreadableReason` splits its members precisely because each is *"a
    # different next action"*; rendering them under one remedy threw that away at the last step.
    by_reason: dict[UnreadableReason, list[str]] = {}
    for resolution in named:
        reason = resolution.hashes.unreadable
        assert reason is not None  # filtered above; narrows for the type checker
        by_reason.setdefault(reason, []).append(resolution.decision.source.name)
    for reason, names in by_reason.items():
        print(f"    {unreadable_label(reason)}: {len(names):,}")
        for name in names[:_STATUS_PREVIEW]:
            print(f"      {name}")
        if len(names) > _STATUS_PREVIEW:
            print(f"      ... and {len(names) - _STATUS_PREVIEW:,} more.")
        print(f"    (not organized; {unreadable_remedy(reason)})")
    return len(named)


def _print_uncompared(resolutions: Sequence[Resolution], phash_threshold: int) -> None:
    """Photos that were organized but never compared for near-duplicates. `(aev)`

    ⚠ **COUNTED, unlike the folder block above.** These files were held and read; the number is
    known exactly. A folder the walk never entered is the opposite case, and the two lines sit in
    the same report on purpose - see `organizer.UncomparedPhotos`.

    ⚠ **ONE HEADING, N GROUPS, and the threshold is the RUN\'s.** `(ahq)` added a second reason a
    file lands here - a hash carrying no distinguishing signal - and `--phash-threshold` decides
    how many qualify, so reading the default would report a number this run did not apply.
    """
    groups = uncompared_photos(resolutions, phash_threshold=phash_threshold)
    if not groups:
        return
    print("\nNot compared for near-duplicates:")
    for group in groups:
        print(f"  {group.label}: {group.total:,}")
        for name in group.files:
            print(f"      {name}")
        if group.total > len(group.files):
            print(f"      ... and {group.total - len(group.files):,} more.")
        print(f"    ({group.remedy})")


def _print_suppressed_noise() -> None:
    """How much image-library output was kept out of this run's own output. `(aev)`

    ⚠ **SAID RATHER THAN SWALLOWED.** Discarding silently would make a run over damaged files
    look identical to a clean one - §4's fifty-fourth member, an instrument silent in the case it
    exists for. The two numbers stay apart because they are removed by two different mechanisms
    and the C half is the larger: 133 warnings against ~598 decoder lines in one corpus run.

    **Counted rather than shown, for one measured reason: the lines name no file.** They say
    `Fax3Decode2D: Bad code word at line 1003 of strip 0` and `tempfile.tif`. There is nothing in
    them to route to a person, which is why `_print_uncompared` above - derived from the decode
    outcome - is the line that carries the actual meaning.
    """
    noise = decode_noise.snapshot()
    if not noise:
        return
    print(
        f"  ({noise.total:,} diagnostic lines from the image libraries were not shown: "
        f"{noise.warnings:,} warnings and {noise.decoder_lines:,} from the decoders. "
        f"They name no file.)"
    )


def _print_folder_groups(groups: Sequence[SkippedFolderGroup]) -> None:
    """Folders the walk did not enter, one block per reason. Shared by both CLI reports. `(aer)`

    ⚠ **NAMED, NEVER COUNTED**, and the count that IS printed counts **folders** rather than the
    files inside them. `c027dd3`: the walk never descends into a hidden or unreadable folder, so
    the number of files inside is precisely what is unknown and any figure would be invented. Do
    not "improve" `.MyAlbum (contents unknown)` into a file count - the type carries no such
    number, so doing it means changing `SkippedFolderGroup`.

    **The label and the remedy arrive already worded**, from `models`. Neither report holds its own
    mapping: the unreadable remedy used to be written verbatim in both of them, which is §9's
    one-source rule broken in the very area `(aer)` was about.
    """
    for group in groups:
        print(f"  {group.label}: {group.total:,}")
        for folder in group.folders:
            print(f"      {folder}  (contents unknown)")
        if group.total > len(group.folders):
            print(f"      ... and {group.total - len(group.folders):,} more.")
        print(f"    ({group.remedy})")


def _print_skipped(scan: SourceScan) -> None:
    """Account for every file that was NOT organized, grouped by kind. Never silent.

    ⚠ **RENDERS THE CENSUS**, which is what `(aer)` changed. This read four `SourceScan` fields
    directly and so never mentioned `hidden` or `truestill_marker` - groups the census has carried
    since `c027dd3`, and which the other two surfaces have shown all along. A real `.picasa.ini`
    and an 18-photo `.MyAlbum` therefore vanished from an organize report that said *success*,
    while `analyze` named both. One renderer had simply never joined the shared home.
    """
    groups = {name: counts for name, counts in skipped_extension_counts(scan).items() if counts}
    folders = skipped_folder_groups(scan)
    if not groups and not folders:
        return
    print("\nSkipped (not organized):")
    for name, counts in groups.items():
        total = sum(counts.values())
        print(f"  {name.replace('_', ' ')}: {total:,}  ({_format_extension_census(counts)})")
        if name == "unrecognized":
            print(
                "    (not recognized as media; some may be video formats Truestill does not organize yet)"
            )
    _print_folder_groups(folders)


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
    folders = skipped_folder_groups(inventory)
    if not groups and not folders:
        return
    print("\nSkipped (not counted as media):")
    for name, counts in groups.items():
        total = sum(counts.values())
        print(f"  {name.replace('_', ' ')}: {total:,}  ({_format_extension_census(counts)})")
    # ⚠ THE SAME BLOCK THE ORGANIZE REPORT PRINTS, from the same groups. `(aer)`: the unreadable
    # remedy used to be written verbatim here AND in `_print_skipped`, and this report capped its
    # hidden list at 20 while that one printed its unreadable list uncapped - one sentence in two
    # places and one list with two behaviours, both in §9's one-source territory.
    _print_folder_groups(skipped_folder_groups(inventory))


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
    # ⚠ `destination` is declared WITHOUT `type=Path` on purpose - it is a local path *or* an
    # rclone spec (`cli.py:373`) - so the conversion belongs here, where which one it is is known.
    # Passing the raw `str` was `(ahp)`: every archive ingest died in `facts_for`.
    source_root = _source_root_or_none(args.source, None if args.rclone else Path(args.destination))
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
    backup = sub.add_parser(
        "backup",
        help="copy the library to a second registered drive (preview by default)",
    )
    backup.add_argument("source", type=Path, help="the drive holding the library")
    backup.add_argument("target", type=Path, help="the drive to copy it to")
    backup.add_argument("--db", type=Path, default=default_catalog_path(), help="SQLite catalog")
    backup.add_argument(
        "--apply", action="store_true", help="actually copy (default: preview only)"
    )

    bake = sub.add_parser(
        "bake",
        help="write confirmed dates into the files on a drive (preview by default)",
    )
    bake.add_argument("path", type=Path, help="the connected drive folder")
    bake.add_argument("--db", type=Path, default=default_catalog_path(), help="SQLite catalog")
    bake.add_argument(
        "--apply", action="store_true", help="actually write them (default: preview only)"
    )

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

    ⚠ **And the same defect recurred one layer along**: the `rmdir` guarantee was stated only under
    `--permanent`, a flag that does not choose the path. It is stated here now, for every run,
    because it is true of every folder on every path. `(afj)`
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

    # ⚠ SPLIT, because one heading could not be true of both. A folder that refused was printed
    # under "something is in there" beside an empty bracket - the heading claiming contents, the
    # bracket claiming none, and the truth being that Truestill could not look. `(afo)`
    held = [c for c in plan.occupied if c.readable]
    unopened = [c for c in plan.occupied if not c.readable]
    print(f"\nLEFT ALONE - something is in there ({len(held)}):")
    for candidate in held:
        print(f"  {candidate.relative}   [{', '.join(candidate.contents)}]")
    if unopened:
        # `(aer)`'s wording for exactly this, rather than a fourth phrase for one fact: the
        # scan report says "folders that could not be opened" and `cli.py` prints
        # "folder, could not be opened". No bracket: there are no contents to name, and an
        # empty one reads as a claim that there are none.
        print(f"\nLEFT ALONE - could not be opened ({len(unopened)}):")
        for candidate in unopened:
            print(f"  {candidate.relative}")

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
    print(f"\n{len(plan.removable)} folder(s) will be removed.")
    if empties:
        one = len(empties) == 1
        print(
            f"  {len(empties)} {'is' if one else 'are'} empty - "
            f"nothing in {'it' if one else 'them'}, so nothing to recover."
        )
    # ⚠ SCOPED TO THE JUNK TIER ON PURPOSE. Said of the whole plan it would read as a promise
    # about folders that never had anything in them to trash.
    if junk:
        holds = "holds" if len(junk) == 1 else "hold"
        print(
            f"  {len(junk)} {holds} only OS junk; the junk goes to the trash first (recoverable)."
            if backend
            else f"  {len(junk)} {holds} only OS junk, which will be removed outright."
        )
    # ⚠ PRINTED UNCONDITIONALLY, AND THAT IS THE FIX. This sentence lived in the `--permanent`
    # block until 2026-08-22, keyed on a flag that does not select the path: `run_cleanup` always
    # tries the trash first and `permanent` only changes what happens when it refuses. So with the
    # flag set and a working trash the sentence was false for every folder, and the default run -
    # the one where every folder went whole - said nothing at all. `(afj)`
    print(
        "\nThe folder itself is removed outright, not moved to the trash. Removal uses rmdir,"
        "\nso a folder that is no longer empty when the removal runs is left alone and reported."
    )
    if backend and junk:
        print(
            "  Trash can be refused on network or cloud-mounted drives; any refusal is "
            + (
                "where --permanent applies,\n  and that junk is removed outright instead."
                if permanent
                else "reported and that\n  folder is left in place."
            )
        )


def _emptied_folder_count(catalog: Catalog, drive_uuid: str | None, path: Path) -> int:
    """How many folders this drive's completed migrations emptied and left removable.

    Shares `_offer_cleanup`'s two calls rather than its printing, because `organize` has to count
    while the catalog is open and speak after its report, and `migrate-layout` can do both at
    once. ``None`` for the drive means an unregistered destination, which has no journal to read.
    """
    if drive_uuid is None:
        return 0
    return len(
        plan_cleanup(path, emptied_directories(catalog.migrated_old_paths(drive_uuid))).removable
    )


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

    ⚠ **`clean` still covers the folder itself, even though the folder is now removed outright.**
    What is lost is a directory entry for a folder that was empty or held only OS junk -- the junk
    is recoverable and a folder can be made again. `delete forever` has to mean *content is gone
    with no way back*; spending it on a directory entry devalues it for the case where it is the
    honest word, which is the cry-wolf failure the whole vocabulary exists to avoid. `(afj)`
    """
    if not permanent:
        return _typed_confirmation(f"\nType 'clean' to remove {count} folder(s): ", "clean")
    # The rmdir guarantee is NOT restated here - it is printed for every run by
    # `_print_cleanup_plan`, because it holds on every path. What is specific to this flag is the
    # junk, which is the only thing `--permanent` changes the fate of. `(afj)`
    print(
        "\n--permanent: where the trash refuses OR is unavailable, any OS junk in these folders"
        "\nis removed OUTRIGHT and is NOT recoverable."
    )
    return _typed_confirmation(
        f"\nType 'delete forever' to remove {count} folder(s): ", "delete forever"
    )


def _cmd_backup(args: argparse.Namespace) -> int:
    """Copy the library to a second drive, verifying every file after it lands. `(ahf)` stage 2.

    **Preview unless `--apply`**, the shape `migrate-layout` and `clean-empty` use.

    ⚠ **BOTH FOLDERS MUST ALREADY BE REGISTERED DRIVES, and this REFUSES rather than registering
    them.** The app auto-attaches, which is right for a screen where the user just chose a folder
    and can see what happened. On a terminal it would make one command do two things and the
    second silently: **registering is a distinct act with its own guard** - `(agr)` part 1's ghost
    refusal - and a command that mints a drive id as a side effect of backing up is how a ghost
    drive gets created from a shell. `_drive_or_explain` already refuses with the remedy, naming
    `truestill drives --init <path>`, so there is no second wording to keep in step.
    """
    source = _drive_or_explain(args.source, args.db)
    if source is None:
        return 2
    target = _drive_or_explain(args.target, args.db)
    if target is None:
        return 2
    if source.uuid == target.uuid:
        print("error: the 'from' and 'to' folders are the same drive.", file=sys.stderr)
        return 2

    with _catalog(args.db) as catalog:
        missing = _files_missing_on_target(catalog, source.uuid, target.uuid)
    need = sum(int(r.size or 0) for r in missing)
    print(
        f"From '{source.label}' to '{target.label}': {len(missing)} file(s) to copy, {_gb(need)}."
    )
    # ⚠ **What it does NOT do, and it costs a sentence.** The reassurance a person wants before
    # letting a tool touch a second drive is that the first one is not at risk - and a backup
    # that only ever adds is a different promise from one that mirrors.
    print(
        "       Copies only. Nothing on either drive is deleted or changed, and the files\n"
        "       it copies are read from the source and left exactly as they are."
    )
    if not missing:
        # ⚠ **THIS SAID *"every file is already on that drive"* UNTIL 2026-08-25, AND IT
        # OVER-CLAIMED.** `_files_missing_on_target` compares `file_copies` ROWS, and a file the
        # catalog never recorded - under a folder an attach could not open, or on a drive
        # registered with `drives --init`, which writes a marker and does not walk - has no row
        # and is therefore not "already on that drive". It was never looked for. `(abm)`
        # ⚠ **The CLI cannot name those folders here**: it deliberately does not attach
        # (`a command that mints a drive id as a side effect of backing up` is refused above), so
        # it points at the command that CAN. `truestill rescan` walks and names them.
        print(
            f"\nNothing to copy - every file this catalog records on '{source.label}' is "
            f"already on '{target.label}'."
        )
        print(
            "       That is a comparison of records, not a fresh look at the drive. To check "
            f"what\n       is really there:  truestill rescan {args.source}"
        )
        return 0
    if not args.apply:
        print("\nPreview only. Nothing was copied. Re-run with --apply to make the backup.")
        return 0

    try:
        outcome = copy_to_drive(
            BackupPair(
                source=args.source,
                source_marker=source,
                target=args.target,
                target_marker=target,
            ),
            args.db,
            progress=_progress_printer("copying"),
            cancel=threading.Event(),
        )
    except BackupStoppedError as exc:
        # ⚠ **The arm that was missing, and its absence is `(ajd)`.** Only `ValueError` was caught
        # here, so a drive that vanished mid-copy reached the user as a Python traceback while
        # `organize` answered the identical accident with a sentence and a count. What landed is
        # printed FIRST, because a stop that reports nothing is the worse defect - `organize`'s own
        # handler calls that "a false custody record, which is worse than no record".
        _end_of_tier()
        print(f"\n{exc.copied:>9,}  copied before the run stopped")
        if exc.failures:
            print(f"{len(exc.failures):>9,}  failed")
        print(f"error: {exc.detail}", file=sys.stderr)
        print(
            f"       {len(missing) - exc.copied:,} file(s) were not attempted. Re-run the same "
            "command\n       when the drive is back: it copies only what is still missing.",
            file=sys.stderr,
        )
        return 4
    except ValueError as exc:
        _end_of_tier()
        print(f"error: {exc}", file=sys.stderr)
        return 4
    _end_of_tier()

    print(f"\nCopied {outcome.copied} file(s), {_gb(outcome.bytes_copied)}.")
    for relative, why in outcome.failures:
        print(f"  failed: {relative} -- {why}", file=sys.stderr)
    if outcome.failures:
        # ⚠ Not 0. A run that copied some and failed others is not a success, and reporting one
        # would be BackInTime #1587's shape - a per-file failure visible only if someone reads
        # the scrollback. The files that DID copy are recorded and a re-run resumes.
        print(f"error: {len(outcome.failures)} file(s) could not be copied.", file=sys.stderr)
        return 1
    return 0


def _print_bake_plan(plan: BakePlan) -> None:
    """What a bake would do, before it is asked for. Every exclusion named, never omitted."""
    print(f"Drive '{plan.drive_label}': {plan.will_write} file(s) would have the date written in.")
    if plan.videos_skipped:
        print(f"  {plan.videos_skipped} video(s) left alone. {VIDEO_EXCLUSION_REASON}")
    if plan.absent:
        print(f"  {plan.absent} file(s) the catalog expects here could not be found on this drive.")
    for line in plan.elsewhere:
        where = "connected now" if line["connected"] else "not connected"
        print(
            f"  {line['label']} ({line['files']} file(s), {where}) still has the old date inside."
        )


def _cmd_bake(args: argparse.Namespace) -> int:
    """Write confirmed dates into the copies on a drive. **Preview unless `--apply`.**

    `(ahd)` step 2. The engine is `truestill_core.bake`; this is the terminal's panel over it,
    the same relationship `truestill_app.service.bake` has to the same functions.

    ⚠ **A CLI bake writes only dates confirmed ELSEWHERE.** There is no `confirm` subcommand -
    confirming is review-shaped and is app-only by recorded deferral - so the input is whatever
    the app recorded or `truestill restore` brought back from a drive's document. When there is
    nothing, :data:`NOTHING_CONFIRMED_NOTE` says so and says where confirmations come from,
    rather than reporting "nothing to do" and leaving the user to guess why.
    """
    marker = _drive_or_explain(args.path, args.db)
    if marker is None:
        return 2
    with _catalog(args.db) as catalog:
        if migration_unfinished(catalog, marker.uuid):
            print(f"error: {migration_unfinished_message(marker.label)}", file=sys.stderr)
            return 2

    plan = bake_plan(args.path, args.db, marker)
    nothing = nothing_to_write_reason(plan)
    if nothing is not None:
        print(nothing)
        if plan.elsewhere:
            _print_bake_plan(plan)
        return 0

    _print_bake_plan(plan)
    if not args.apply:
        print("\nPreview only. Nothing was written. Re-run with --apply to set the dates.")
        return 0

    # The warning comes BEFORE the prompt on purpose: it is the thing to read before typing, not
    # an explanation offered after the decision. The app's screen orders it the same way.
    print(f"\n{IRREVERSIBLE_NOTE}")
    confirmed = _typed_confirmation(
        f"\nType '{CONFIRM_WORD}' to proceed (anything else aborts): ", CONFIRM_WORD
    )
    if confirmed is not True:
        print("Aborted -- nothing was written.")
        return 0

    outcome = bake_confirmed_dates(
        args.path,
        args.db,
        marker,
        confirmation=CONFIRM_WORD,
        progress=_progress_printer("updating"),
        cancel=threading.Event(),
    )
    _end_of_tier()
    print(f"\n{outcome.completeness}")
    if outcome.videos_skipped:
        print(f"{outcome.videos_skipped} video(s) left alone.")
    if outcome.absent:
        print(f"{outcome.absent} file(s) were not found on this drive.")
    if outcome.refused is not None:
        print(f"error: {outcome.refused}", file=sys.stderr)
        return 4
    if outcome.failed:
        print(f"error: {outcome.failed} file(s) could not be updated.", file=sys.stderr)
        return 1
    return 0


def _cmd_clean_empty(args: argparse.Namespace) -> int:
    """Remove the folder skeleton a migration left, after showing exactly what will go."""
    marker = _drive_or_explain(args.path, args.db)
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
    print(f"\nRemoved {outcome.removed} folder(s).")
    # Prose, not a counter: "look in the trash" does not depend on how many there were, while a
    # discard cannot be undone and is therefore worth a number. `(afj)`
    if outcome.discarded:
        print(f"  {outcome.discarded} OS junk file(s) were removed outright, not recoverable.")
    elif outcome.removed and any(c.tier is Tier.JUNK_ONLY for c in plan.removable):
        print("  The OS junk they held is in the trash.")
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
        # ⚠ **The same reporter as the forward path** (`(agx)`). This printed its refusals and
        # returned **0** whatever happened - the defect `(agm)` fixed one direction of, still
        # live in the other. `(afe)` binds the two halves of one command, and two reporters is
        # how they drift apart again.
        return _report_migration_shortfall(applied.stopped, applied.refused)


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


def _report_migration_shortfall(
    stopped: MigrationStop | None, refused: list[tuple[str, str]]
) -> int:
    """Say what a migration did not do, and spend the exit code on it. `(agm)` D1.

    ⚠ **THIS SURFACE RETURNED `0` AFTER EVERY RUN.** `(agi)`'s ground watcher has set
    `MigrationOutcome.stopped` since it shipped, and neither the CLI nor the app read it - so a
    migration stopped because the disk was filling printed *"Migrated N file(s)"* and exited
    **success**, on the command that rewrites every byte of the library. That is
    `IMPLEMENTATION_STANDARDS.md` §9 never-silent, and it is `(agl)`'s defect one module over.

    **Worded from `kind`, never from the reason text** (§9 again): a cancel is the user's own act
    and goes to stdout with `0`, because `undo-organize` already spends the code that way for the
    same reason. The other two are the run failing to do what it was asked, and take `4` - the
    destination code `_stopped_run_exit` already uses for a run the destination stopped.
    """
    for relative, reason in refused:
        print(f"  refused: {relative} -- {reason}", file=sys.stderr)
    if stopped is None:
        # A refusal that did not stop the run still means the plan is unfinished: the journal
        # keeps those moves and a re-run clears them, so the code says there is work left.
        return 1 if refused else 0
    # `(ahc)`: read from the one table rather than deriving `kind is CANCELLED` here. The app
    # screens needed the same decision and were about to derive it a third time, in JavaScript.
    wording = STOP_WORDING[stopped.kind]
    print(
        f"  {wording.headline}: {stopped.reason}\n"
        f"  {stopped.never_attempted} move(s) were not reached.",
        file=sys.stderr if wording.fault else sys.stdout,
    )
    return 4 if wording.fault else 0


def _apply_the_rename(
    args: argparse.Namespace, marker: DriveMarker, plan: RenamePlan
) -> RenameOutcome:
    """Open the catalog again for the write half, so the preview above stays a pure read.

    Extracted rather than inlined because `_cmd_rename` is at its branch ceiling, which
    `IMPLEMENTATION_STANDARDS.md` answers by extracting rather than by raising the limit.
    """
    with _catalog(args.db) as catalog:
        catalog.upsert_drive(uuid=marker.uuid, label=marker.label)
        return apply_rename(
            catalog,
            LocalDestination(args.path),
            marker.uuid,
            plan,
            progress=_progress_printer("moving"),
        )


def _cmd_rename(args: argparse.Namespace) -> int:
    """`rename`: what renaming a trip or event would move. **Stage 1 previews only.** `(aix)`

    ⚠ **The preview says what it will NOT do**, which is `(aim)`'s lesson applied before the
    defect rather than after it: a list of moves with no statement of tense reads as a report of
    work already done. There is no `--apply` yet, so this says so plainly rather than implying an
    apply exists.
    """
    marker = _drive_or_explain(args.path, args.db)
    if marker is None:
        return 2

    with _catalog(args.db) as catalog:
        scheme = resolve_scheme(catalog)
        routes = label_routes(catalog, marker.uuid)
        with HashCache.beside(args.db) as cache:
            rederived = rederive_rules(
                catalog, marker.uuid, args.path, routes, by_device=False, cache=cache
            )
        decided = {r.label: (ROUTE_SIDE_BIN if r.needs_decision else r.route) for r in routes}
        plan = plan_rename(
            catalog,
            marker.uuid,
            scheme,
            kind=RenameKind(args.kind),
            row_id=args.id,
            new_name=args.name,
            routes=decided,
            rules_by_sha=rederived.rules,
        )

    if plan.refusal is not None:
        print(f"error: {plan.refusal_detail}", file=sys.stderr)
        return 2

    print(f"Rename {plan.kind.value} {plan.row_id}: {plan.old_name!r} -> {plan.new_name!r}")
    if not plan.moves:
        print("  nothing would move: the new name renders the same folder.")
        return 0
    print(f"  {len(plan.moves)} file(s) would move:")
    for move in plan.moves[:_STATUS_PREVIEW]:
        print(f"      {move.old_relative}")
        print(f"   -> {move.new_relative}")
    if len(plan.moves) > _STATUS_PREVIEW:
        print(f"      ... and {len(plan.moves) - _STATUS_PREVIEW:,} more.")
    if not args.apply:
        print("\nPreview only - nothing was written or moved. Re-run with --apply to rename.")
        return 0

    outcome = _apply_the_rename(args, marker, plan)
    if outcome.stopped is not None:
        print(f"error: {outcome.stopped.reason}", file=sys.stderr)
    for relative, reason in outcome.refused[:_STATUS_PREVIEW]:
        print(f"  REFUSED: {relative}: {reason}", file=sys.stderr)
    # ⚠ **The two outcomes are worded apart because they are different states.** A rename that
    # moved files without flipping the name is not a failed rename - it is a resumable one, and
    # the photographs are safe at whichever path each reached. Saying "renamed" would be false and
    # saying "failed" would be alarming about files that are fine.
    if outcome.renamed:
        print(f"\nRenamed. {outcome.moved} file(s) moved.")
        return 0
    print(
        f"\n{outcome.moved} of {len(plan.moves)} file(s) moved; the name is still "
        f"{plan.old_name!r}. Nothing is lost - re-run this to finish it."
    )
    return 1


def _cmd_migrate_layout(args: argparse.Namespace) -> int:
    marker = _drive_or_explain(args.path, args.db)
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
        _say_if_two_places(catalog, marker, args.path)
        # `(afc)` half E, beside the drive write for the reason `_cmd_reclaim` states: past the
        # typed confirmation, so an ABORTED run stays byte-identical. It was briefly one gate
        # earlier and `test_without_the_typed_confirm_nothing_moves` caught it.
        remember_drive_root(catalog, marker, args.path)
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
        code = _report_migration_shortfall(outcome.stopped, outcome.refused)
        _offer_cleanup(catalog, marker.uuid, args.path)
        return code


def _apply_the_undo(args: argparse.Namespace, plan: UndoPlan, outcome: UndoOutcome) -> int:
    """Record the reversal and report it. `(afw)`

    **Lifted out of `_cmd_undo_organize` so that stays under its branch ceiling**, which
    `IMPLEMENTATION_STANDARDS.md` answers by extracting rather than by raising the limit - the
    same move `_stopped_run_exit` made on the organize side.

    ⚠ **THE LOCK DELIBERATELY STAYS IN THE CALLER.**
    `test_every_command_declares_whether_it_locks_a_drive.py` reads the declaring function's own
    calls, so lifting `lock_for` out to here would make a command that declares
    `_LOCKED_IN_HANDLER` look as though it never locks. **Extracting around a guard until the
    guard stops seeing the thing it guards is how a guard dies quietly** - and this one exists
    because `(aaw)` found two processes overwriting each other's photographs.
    """
    # ⚠ **The record, and undo is the fourth surface to get one.** `IMPLEMENTATION_STANDARDS`
    # requires it of *a run that changes the library*, and undo moves the user's files just as
    # organize does. Its own failure must never fail the reversal, so the error is printed
    # rather than raised - `decisions.write_decisions`'s rule.
    record_error = record_undo(args.db, plan, outcome)
    if record_error is not None:
        print(f"\n  Could not write the run record: {record_error}", file=sys.stderr)
    print(f"\nRestored {outcome.restored} file(s) to their original locations.")
    if outcome.stopped is not None:
        # ⚠ **Worded from `kind`, never from the reason text** (`(agl)`). A cancel is the user's
        # own act and must not read as a fault; `IMPLEMENTATION_STANDARDS.md` §9 is why the
        # branch keys on the enum rather than on the sentence. **stdout for a cancel, stderr for
        # a fault**: the first is a reported outcome, the second is the run telling you something
        # went wrong, and `analyze`'s split is the precedent.
        cancelled = outcome.stopped.kind is UndoStopKind.CANCELLED
        print(
            f"  {'Cancelled' if cancelled else 'Stopped'}: {outcome.stopped.reason}\n"
            f"  {outcome.stopped.never_attempted} file(s) were not reached.",
            file=sys.stdout if cancelled else sys.stderr,
        )
    # ⚠ **A file that was never moved is not one that could not be restored** (`(agk)`).
    # Since the journal records intent, an interrupted run leaves rows for renames that
    # never happened; calling those failures would make every such run report a problem it
    # does not have, and would spend the exit code on it.
    #
    # ⚠ **`undo.outstanding`, not a filter written here.** This listed one reason by hand and
    # missed `WAS_A_COPY`, so a fallback-copy row made a clean undo exit 1. The exit code and
    # `run_undo`'s close condition are two readings of one question and must not drift.
    unresolved = outstanding(outcome.skipped)
    never = len(outcome.skipped) - len(unresolved)
    if never:
        print(f"  {never} file(s) had nothing to undo; no further undo can change them.")
    if unresolved:
        print(
            f"  {len(unresolved)} file(s) could not be restored; the run stays open so "
            "you can re-run undo once they are resolved.",
            file=sys.stderr,
        )
    return 1 if unresolved else 0


def _cmd_undo_organize(args: argparse.Namespace) -> int:
    with _catalog(args.db) as catalog:
        if args.list:
            runs = catalog.inplace_runs()
            if not runs:
                print("No in-place organize runs recorded.")
                return 0
            # ⚠ **"intended", not "files", since `(agk)`.** The journal is an intent log: a row
            # is written before the rename is attempted, so a count of rows is what the run set
            # out to do. `renamed` is what is confirmed, and anything unconfirmed is reported as
            # **unknown** rather than folded into either - because a crash between the rename and
            # the write-back leaves that state over a file which really did move, and only
            # `undo-organize` (which reconciles against the disk) can settle it.
            print(f"{'run id':<34}{'when':<28}{'intended':>9}{'renamed':>9}{'unknown':>9}  status")
            for row in runs:
                unknown = f"{row['unknown']:>9}" if row["unknown"] else f"{'-':>9}"
                print(
                    f"{row['run_id']:<34}{row['started_at']:<28}{row['intended']:>9}"
                    f"{row['renamed']:>9}{unknown}  {row['status']}"
                )
            if any(r["unknown"] for r in runs):
                print(
                    "\n  'unknown' means the outcome was never recorded - which is NOT the same "
                    "as nothing having happened.\n  Run 'truestill undo-organize --run-id ID' to "
                    "see what is actually on the drive."
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
            if classify(skip.reason) is SkipClass.NOTHING_TO_DO:
                # Not a refusal: there is nothing to put back, and no second undo will
                # change that. Said on stdout with the rest of the plan rather than on stderr
                # with the problems. `(agk)`
                # "not moved yet" was written for `NEVER_MOVED` alone and is false of
                # `WAS_A_COPY`, which WAS moved - by the copy path, which needs no undo row. The
                # label states the shared fact; the detail says which of the two this is.
                print(f"  nothing to undo: {skip.step.original.name} -- {skip.detail}")
                continue
            print(f"  cannot restore: {skip.step.current.name} -- {skip.detail}", file=sys.stderr)

        if not args.apply:
            print("\nPreview only. Re-run with --apply to move these files back.")
            return 0
        if not plan.steps:
            print("\nNothing to restore.")
            return 0

        # ⚠ **The one command whose drive is not in `args`** - it comes out of the run's record,
        # so the lock is taken here rather than in `_run_holding_the_drive`. Declared as
        # `_LOCKED_IN_HANDLER` there so the completeness guard still forces an answer. `(aaw)`
        try:
            with lock_for(Path(plan.dest_root), operation="undo-organize"):
                outcome = run_undo(
                    catalog, plan, apply=True, progress=_progress_printer("restoring")
                )
        except DriveBusyError as busy:
            print(f"error: {busy}", file=sys.stderr)
            return DRIVE_BUSY_EXIT
        return _apply_the_undo(args, plan, outcome)


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
    marker = _drive_or_explain(args.path, args.db)
    if marker is None:
        return 2
    if args.min_copies < 1:
        print("error: --min-copies must be at least 1", file=sys.stderr)
        return 2

    with _catalog(args.db) as catalog:
        catalog.upsert_drive(uuid=marker.uuid, label=marker.label)
        # The hint is a drive's ONLY uuid-to-path memory and it is overwritten in place, so the
        # moment before destroying it is the only moment a second location can be observed.
        # `(adx)` gap 1; pinned by `test_every_hint_write_checks_for_a_second_place`.
        _say_if_two_places(catalog, marker, args.path)
        # ⚠ `(afc)` half E, and the rule for WHERE is "wherever the command already writes drive
        # facts" - the line above. A command that merely previews must not gain a side effect:
        # `test_a_preview_moves_nothing_and_writes_nothing` asserts the catalog file is
        # byte-identical after a migrate preview, and a location hint is still a write. Reclaim
        # already upserts here, so recording costs nothing new; migrate's preview does not, so it
        # records past its apply gate instead.
        remember_drive_root(catalog, marker, args.path)
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
        # ⚠ **THE STRONGEST AUTHORISATION IN THE PRODUCT, AND IT WAS THE WEAKEST UNTIL
        # 2026-08-22.** This removes the user's own photographs, permanently; `clean-empty
        # --permanent` removes folders Truestill itself emptied, after their junk went to the
        # trash. Measured, the second had six lines and `delete forever` while this had three
        # lines and `delete`. The ceremony was inverted relative to the stakes. `(afh)`
        print(
            f"\nThis deletes {n} ORIGINAL file(s) from this computer, freeing {gib:.2f} GB."
            f"\n\n  These are your originals, not spare copies. Each one is deleted only after its"
            f"\n  content is re-read on '{marker.label}' and matches - but once it is gone, that"
            f"\n  drive is the only place it exists."
            "\n\n  They do NOT go to the trash, and this CANNOT BE UNDONE."
        )
        # The phrase names WHAT IS LOST rather than that the loss is permanent. `delete forever`
        # says "no way back", which a reclaim user is unlikely to doubt; what they may doubt is
        # whether these are spares. It is also two words nobody types by habit, and it retires
        # `delete` - the weakest-looking word in the product, guarding its strongest act.
        confirmed = _typed_confirmation(
            "\nType 'delete originals' to proceed (anything else aborts): ", "delete originals"
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

    A catalog failure that is **not** busy gets its own refusal rather than the busy one, because
    the two send the user somewhere different: "wait for the other operation to finish" is
    useless advice about a read-only folder or a full disk.

    ⚠ **A third case joined the two on 2026-08-22, and a bug still keeps its traceback.** This
    handler used to re-raise everything that was not busy, so a catalog that went unwritable
    mid-run reached the terminal as a `sqlite3.OperationalError` stack -- §9's exact prohibition,
    and measured: an `organize` whose catalog directory turned read-only ended in a traceback out
    of `finish_organize_run`, *after* the per-file write path had already been made safe. Guarding
    the write loop alone left every other catalog write in the command uncovered, which is why
    the rule belongs at the one seam that sees them all. What did **not** change is the last arm:
    `SELECT * FROM no_such_table` is a bug of ours, not a condition of the user's, and it still
    raises. `(afe)`

    ⚠ **`CatalogUnwritableError` is caught beside `sqlite3.Error` because not every unwritable
    catalog is a SQLite failure.** `Catalog.__init__` creates the catalog's parent directory
    before connecting; on a read-only or full disk that `mkdir` raises `PermissionError`, which
    is not a `sqlite3.Error` and used to walk straight past this handler. `(aen)`
    """
    try:
        return _dispatch(argv)
    except CatalogUnusableError:
        # Nothing printed here on purpose: the startup banner has already put the whole
        # explanation on stderr, and a second copy of it would read as two problems. `(adr)`.
        return CATALOG_UNUSABLE_EXIT
    except (sqlite3.Error, CatalogUnwritableError) as exc:
        if is_catalog_busy(exc):
            print(f"error: {CATALOG_BUSY_MESSAGE}", file=sys.stderr)
            return CATALOG_BUSY_EXIT
        if not is_catalog_unwritable(exc):
            raise
        print(f"error: {catalog_unwritable_message(exc)}", file=sys.stderr)
        return CATALOG_UNWRITABLE_EXIT


def _dispatch(argv: list[str] | None) -> int:
    argv_list = list(argv) if argv is not None else sys.argv[1:]
    args = _build_parser().parse_args(argv_list)
    if hasattr(args, "db"):
        explicit = db_flag_explicit(argv_list)
        info = inspect_catalog(args.db, explicit_db=explicit)
        # The choice is only meaningful when nobody named a path - with `--db` the user already
        # knows which catalog they asked for, and explaining the default would be noise. `(adv)`.
        for line in format_startup_lines(info, None if explicit else resolve_catalog_choice()):
            # ROUTED BY TONE, not by presence. `alert` was `empty_with_drives` alone when this
            # was written, so the two readings agreed and the narrower one got written down;
            # `(adr)`'s zero-byte state is the second alert and would have gone to stdout. The
            # tone field already answers "is this loud" for every state there will ever be.
            stream = sys.stderr if info.tone == "alert" else sys.stdout
            print(line, file=stream, flush=True)
        # AHEAD OF THE DISPATCH TABLE, so every subcommand is covered by one refusal rather
        # than seventeen. The banner above has already printed the reason, which is why the
        # handler in `main` returns the code without saying anything further. `(adr)`.
        refuse_unusable_catalog(info)
    dispatch = {
        "analyze": _cmd_analyze,
        "organize": _cmd_organize,
        "ingest": _cmd_ingest,
        "drives": _cmd_drives,
        "where": _cmd_where,
        "restore": _cmd_restore,
        "verify": _cmd_verify,
        "status": _cmd_status,
        "self-check": _cmd_self_check,
        "catalog": _cmd_catalog,
        "config": _cmd_config,
        "backup": _cmd_backup,
        "bake": _cmd_bake,
        "clean-empty": _cmd_clean_empty,
        "rescan": _cmd_rescan,
        "migrate-layout": _cmd_migrate_layout,
        "rename": _cmd_rename,
        "reclaim": _cmd_reclaim,
        "undo-organize": _cmd_undo_organize,
        "repoint-sources": _cmd_repoint,
    }
    return _run_holding_the_drive(dispatch[args.command], args)


def _run_holding_the_drive(
    handler: Callable[[argparse.Namespace], int], args: argparse.Namespace
) -> int:
    """Run ``handler`` with this drive held against other processes, where that applies. `(aaw)`

    **One place rather than seven**, for the reason `refuse_unusable_catalog` is called ahead of
    the dispatch table: a rule enforced at each call site is a rule the eighth call site forgets.

    ⚠ **Only under `--apply`.** A preview writes nothing, and a preview that is slightly out of
    date because someone else is organizing is not data loss - while making `truestill organize`
    fail rather than report, because a background apply is running, would be a worse product than
    the race it prevents.
    """
    where = _LOCKS_DRIVE_AT[args.command]  # KeyError: an undeclared command, caught by its test
    if where is None or where == _LOCKED_IN_HANDLER or not getattr(args, "apply", False):
        return handler(args)
    try:
        # `Path(...)` because the parsers disagree: some declare `type=Path` and some take
        # the string straight from `argparse`. Normalising here beats seventeen declarations.
        with lock_for(Path(getattr(args, where)), operation=args.command):
            return handler(args)
    except DriveBusyError as busy:
        print(f"error: {busy}", file=sys.stderr)
        return DRIVE_BUSY_EXIT


if __name__ == "__main__":
    raise SystemExit(main())
