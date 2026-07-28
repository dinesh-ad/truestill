"""Command-line entry point.

Defaults are inert: with no ``--apply`` the tool analyses the source, resolves duplicates
and prints what it *would* organize, writing nothing to the destination or the catalog.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import uuid
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from truestill_core.catalog import Catalog
from truestill_core.categorize import build_rules
from truestill_core.dedup import DedupIndex
from truestill_core.destinations import Destination, LocalDestination, RcloneDestination
from truestill_core.destinations.base import DestinationError
from truestill_core.drive import (
    MARKER_NAME,
    DriveMarker,
    create_marker,
    existing_marker_path,
    needs_marker_upgrade,
    read_marker,
    upgrade_marker,
)
from truestill_core.exif import ExiftoolMissingError, read_metadata
from truestill_core.hash_cache import HashCache
from truestill_core.hashing import DEFAULT_PHASH_THRESHOLD, HEIF_AVAILABLE, HEIF_EXTENSIONS
from truestill_core.layout import (
    DEFAULT_TEMPLATE_STRING,
    LAYOUT_TEMPLATE_KEY,
    PRESETS,
    SAMPLE_CONTEXTS,
    LayoutTemplate,
    TemplateError,
    pin_existing_layout,
    preview,
    resolve_for,
    resolve_template,
)
from truestill_core.migrate import run_migration
from truestill_core.models import (
    ActionResult,
    ActionStatus,
    DateSource,
    Decision,
    DuplicateMatch,
    Resolution,
    date_quality,
    status_label,
)
from truestill_core.organizer import (
    Relocation,
    SourceScan,
    execute,
    plan,
    resolve,
    scan_source,
)
from truestill_core.progress import Progress, ProgressCallback
from truestill_core.reclaim import plan_reclaim, run_reclaim
from truestill_core.scan import DEFAULT_WORKERS
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
_DEFAULT_DB = Path("reports/catalog.sqlite")

#: Said once, on the run that pins an existing library's layout. It states what was recorded
#: and how to change it, because a settings write the user did not ask for must never be silent.
_PINNED_NOTICE = (
    "Note: this library was organized before truestill's default layout changed, so its "
    "current layout ({category}/{yyyy}/{mm}) has been recorded as its own - new files will "
    "keep landing where the existing ones are. To adopt the new year-first default, run "
    "`truestill config --preset year-first` and then `truestill migrate-layout` (preview first)."
)
_STATUS_PREVIEW = 20  # how many single-copy files `truestill status` lists before eliding


def _parse_tz(value: str) -> timedelta:
    """Parse a ``±HH:MM`` timezone offset into a timedelta."""
    match = re.fullmatch(r"([+-])(\d{2}):?(\d{2})", value.strip())
    if match is None:
        message = f"expected a ±HH:MM offset, got {value!r}"
        raise argparse.ArgumentTypeError(message)
    sign, hours, minutes = match.group(1), int(match.group(2)), int(match.group(3))
    delta = timedelta(hours=hours, minutes=minutes)
    return -delta if sign == "-" else delta


def _add_common_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "destination",
        help="local directory path, or an rclone remote spec with --rclone",
    )
    parser.add_argument("--rclone", action="store_true", help="destination is an rclone remote")
    parser.add_argument("--apply", action="store_true", help="actually write (default: dry run)")
    parser.add_argument(
        "--db", type=Path, default=_DEFAULT_DB, help=f"SQLite catalog (default: {_DEFAULT_DB})"
    )
    parser.add_argument(
        "--phash-threshold",
        type=int,
        default=DEFAULT_PHASH_THRESHOLD,
        metavar="N",
        help=f"max Hamming distance for a perceptual duplicate (default: {DEFAULT_PHASH_THRESHOLD})",
    )
    parser.add_argument(
        "--by-device", action="store_true", help="name capture folders after the device"
    )
    parser.add_argument(
        "--no-rename", action="store_true", help="keep original filenames (no date prefix)"
    )
    parser.add_argument(
        "--events", action="store_true", help="propose Camera event clusters to name"
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
        "--pool", choices=("thread", "process"), default="thread", help="hashing worker pool"
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=DEFAULT_WORKERS,
        metavar="N",
        help="number of hashing workers",
    )
    parser.add_argument(
        "--report", type=Path, metavar="PATH", help="write the full decision report as JSON"
    )


def _add_undo_parser(sub: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """`undo-organize`: reverse a rename-based run, preview first."""
    undo = sub.add_parser(
        "undo-organize", help="put files back where they were before an in-place organize"
    )
    undo.add_argument("--db", type=Path, default=_DEFAULT_DB, help="SQLite catalog")
    undo.add_argument("--run-id", help="which run to reverse (default: the most recent)")
    undo.add_argument("--list", action="store_true", help="list recorded in-place runs and exit")
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
        help="delete each source only after its copy is written and re-verified (needs --apply)",
    )
    organize.add_argument(
        "--in-place",
        action="store_true",
        help=(
            "move files on the drive instead of copying them (implies --move). Requires source "
            "and destination on one filesystem; refuses rather than falling back to a copy"
        ),
    )
    _add_common_options(organize)

    ingest = sub.add_parser(
        "ingest", help="rescue + organize a Google Takeout export (dates from JSON sidecars)"
    )
    ingest.add_argument(
        "--takeout",
        type=Path,
        required=True,
        metavar="DIR",
        help="extracted Google Takeout directory",
    )
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
        help="trust photoTakenTime over embedded EXIF (for dates fixed inside Google Photos)",
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

    drives = sub.add_parser("drives", help="list known backup drives, or init a drive marker")
    drives.add_argument("--db", type=Path, default=_DEFAULT_DB, help="SQLite catalog")
    drives.add_argument("--init", type=Path, metavar="ROOT", help="write a drive marker at ROOT")
    drives.add_argument("--label", help="human label for --init")
    drives.add_argument("--uuid", help="re-attach a known uuid instead of minting a new one")
    drives.add_argument(
        "--migrate-marker",
        type=Path,
        metavar="ROOT",
        help=(
            f"write a {MARKER_NAME} for a drive that still carries only a pre-rename "
            "marker, keeping its identity and leaving the old file in place"
        ),
    )

    _add_undo_parser(sub)

    where = sub.add_parser("where", help="find which drive(s) a file is on (offline)")
    where.add_argument("term", help="filename / path substring to search for")
    where.add_argument("--db", type=Path, default=_DEFAULT_DB, help="SQLite catalog")

    verify = sub.add_parser("verify", help="re-hash a connected drive's copies against the catalog")
    verify.add_argument(
        "path", type=Path, help="the drive's current mount root (must be connected)"
    )
    verify.add_argument("--db", type=Path, default=_DEFAULT_DB, help="SQLite catalog")
    verify.add_argument("--pool", choices=("thread", "process"), default="thread")
    verify.add_argument("--workers", type=int, default=DEFAULT_WORKERS, metavar="N")

    status = sub.add_parser("status", help="report content that exists on only one drive (3-2-1)")
    status.add_argument("--db", type=Path, default=_DEFAULT_DB, help="SQLite catalog")

    config = sub.add_parser(
        "config", help="show or change this catalog's destination folder layout"
    )
    config.add_argument("--db", type=Path, default=_DEFAULT_DB, help="SQLite catalog")
    config.add_argument("--set-template", metavar="TEMPLATE", help="set a custom layout template")
    config.add_argument("--preset", choices=tuple(PRESETS), help="set the layout to a named preset")
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
    reclaim.add_argument("--db", type=Path, default=_DEFAULT_DB, help="SQLite catalog")
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
    migrate.add_argument("--db", type=Path, default=_DEFAULT_DB, help="SQLite catalog")
    migrate.add_argument(
        "--apply", action="store_true", help="actually move files (default: preview only)"
    )

    return parser


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
    with Catalog(args.db) as catalog:
        if args.migrate_marker is not None:
            return _migrate_marker(args.migrate_marker, catalog)

        if args.init is not None:
            if not args.label:
                print("error: --init requires --label", file=sys.stderr)
                return 2
            marker = create_marker(args.init, args.label, uuid=args.uuid)
            catalog.upsert_drive(uuid=marker.uuid, label=marker.label)
            print(f"Drive '{marker.label}' initialised at {args.init}  (uuid {marker.uuid}).")
            return 0

        drives = catalog.list_drives()
        if not drives:
            print("No drives known. Initialise one: truestill drives --init <root> --label <name>")
            return 0
        print(f"{'LABEL':<20}{'FILES':>8}{'SIZE(MB)':>12}  {'LAST SEEN':<22}LAST VERIFIED")
        for d in drives:
            size_mb = (d["total_size"] or 0) / 1e6
            print(
                f"{d['label']:<20}{d['file_count']:>8}{size_mb:>12.1f}  "
                f"{(d['last_seen'] or '-')[:19]:<22}{(d['last_verified'] or 'never')[:19]}"
            )
    return 0


def _cmd_where(args: argparse.Namespace) -> int:
    with Catalog(args.db) as catalog:
        rows = catalog.find_copies(args.term)
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
    return 0


def _cmd_verify(args: argparse.Namespace) -> int:
    root = args.path
    marker = read_marker(root)
    if marker is None:
        print(f"error: no {MARKER_NAME} at {root} -- connect the drive first", file=sys.stderr)
        return 2
    when = _now_iso()
    with Catalog(args.db) as catalog:
        catalog.upsert_drive(uuid=marker.uuid, label=marker.label)
        rows = catalog.copies_on_drive(marker.uuid)
        if not rows:
            print(f"Drive '{marker.label}' has no recorded copies in the catalog.")
            return 0
        copies = [
            CopyToVerify(
                sha256=r["sha256"],
                relative=r["relative"],
                expected_hash=r["copy_sha256"] or r["sha256"],  # NULL -> pre-v6 byte-identical
            )
            for r in rows
        ]
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
    for result in results:
        if result.status is not CopyStatus.VERIFIED:
            print(f"  {result.status.value.upper():<9} {result.copy.relative}")
    print("\n  (read-only: truestill never repairs; re-copy the source to restore a bad file.)")
    return 1 if (counts.get("missing") or counts.get("mismatch")) else 0


def _cmd_status(args: argparse.Namespace) -> int:
    with Catalog(args.db) as catalog:
        singles = catalog.single_copy_shas()
    if not singles:
        print("All catalogued content has at least two drive copies. Nicely redundant.")
        return 0
    print(f"At risk: {len(singles)} file(s) exist on only ONE drive (3-2-1 wants >=2):")
    for r in singles[:_STATUS_PREVIEW]:
        print(f"  {r['original_name'] or r['sha256'][:12]}   only on '{r['drive_label']}'")
    if len(singles) > _STATUS_PREVIEW:
        print(f"  ... and {len(singles) - _STATUS_PREVIEW} more.")
    return 0


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _progress_printer(label: str) -> ProgressCallback:
    """A terminal progress callback: an in-place ``label: done/total`` counter.

    The op's own phase name wins over ``label`` when it has one, so a run that hashes and then
    copies says which it is doing rather than showing one pace for two different jobs.
    """

    def report(update: Progress) -> None:
        end = "\n" if update.done >= update.total else "\r"
        what = update.phase or label
        # Padded so the shorter line of a phase change fully overwrites the longer previous one.
        print(f"  {what}: {update.done}/{update.total}".ljust(60), end=end, flush=True)

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
    phash = resolution.hashes.perceptual or "n/a (not an image)"
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
        lines.append(f"      NEAR-DUP  : looks like {near.matched_path} [{near.origin}{distance}]")
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
        f"      via          : SHA-256, seen this {match.origin}"
    )


def _print_report(resolutions: list[Resolution], root_label: str) -> None:
    uploads = [r for r in resolutions if r.should_upload]
    unique = [r for r in uploads if r.near_duplicate is None]
    near = [r for r in uploads if r.near_duplicate is not None]
    exact = [r for r in resolutions if not r.should_upload]

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
    if quality.suspect_default:
        print(
            f"  {quality.suspect_default} file(s) dated by a suspicious camera-default"
            " timestamp (exact midnight on a known clock-reset day) --"
            " filed by that date, worth a look"
        )


def _print_summary(resolutions: list[Resolution]) -> None:
    uploads = [r for r in resolutions if r.should_upload]
    near = [r for r in uploads if r.near_duplicate is not None]
    exact = [r for r in resolutions if not r.should_upload]
    labels = Counter(r.decision.category.label for r in uploads)
    sources = Counter(r.decision.date_source.value for r in uploads)

    print(_SEPARATOR)
    print("SUMMARY")
    print(_SEPARATOR)
    print(f"  files analysed     : {len(resolutions)}")
    print(f"  organized (unique)  : {len(uploads) - len(near)}")
    print(f"  organized (near-dup): {len(near)}  (kept + flagged for review)")
    print(f"  skipped (exact dup): {len(exact)}")
    print(f"  folders derived    : {len(labels)}")
    for label, count in labels.most_common():
        print(f"      {label:<28} {count}")
    print("  date sources (organized files):")
    for source, count in sources.most_common():
        print(f"      {source:<28} {count}")
    _print_date_quality(uploads)

    review = [r for r in uploads if r.decision.needs_review]
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
    uploads = [r for r in resolutions if r.should_upload]
    duplicates = [r for r in resolutions if not r.should_upload]
    sources = Counter(r.decision.date_source.value for r in uploads)
    reclaimed = sum(_safe_size(r.decision.source) for r in duplicates)

    print(_SEPARATOR)
    print("TAKEOUT RESCUE REPORT")
    print(_SEPARATOR)
    print(f"  media files found                : {len(resolutions)}")
    print(f"  kept (unique)                    : {len(uploads)}")
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
    print(f"  suspicious camera-default dates  : {quality.suspect_default}  (filed, worth a look)")
    print(f"  media without any JSON sidecar   : {len(scan.missing_sidecar)}")
    print(
        "  note: Takeout times are UTC; near midnight a date may shift a day -- pass --tz to correct."
    )


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
    with Catalog(args.db) as catalog, HashCache.beside(args.db) as cache:
        if getattr(args, "apply", False) and pin_existing_layout(catalog):
            print(_PINNED_NOTICE)
        template = resolve_for(catalog)
        decisions = plan(
            files,
            metadata,
            build_rules(by_device=args.by_device),
            rename=not args.no_rename,
            takeout=takeout,
            tz_offset=tz_offset,
            prefer_takeout=prefer_takeout,
            template=template,
        )
        ingest_ctx = _build_ingest_context(decisions, metadata, scan) if scan is not None else None

        index = DedupIndex.from_catalog_rows(catalog.seed_rows(), args.phash_threshold)
        if catalog.count():
            print(f"Catalog {args.db} holds {catalog.count()} previously-processed file(s).\n")

        drive_uuid: str | None = None
        if drive_marker is not None:
            catalog.upsert_drive(uuid=drive_marker.uuid, label=drive_marker.label)
            drive_uuid = drive_marker.uuid
            print(f"Destination is drive '{drive_marker.label}' ({drive_marker.uuid[:8]}...).\n")

        resolutions = resolve(
            decisions,
            index,
            catalog_sizes=catalog.known_sizes(),
            pool=args.pool,
            workers=args.workers,
            progress=_progress_printer("hashing"),
            cache=cache,
        )

        event_ids: dict[str, int] = {}
        if args.events or event_prompt is not None:
            resolutions, event_ids = run_event_stage(
                resolutions,
                metadata,
                catalog,
                apply=args.apply,
                prompt=event_prompt,
                template=template,
            )

        _print_report(resolutions, destination.describe())
        _print_summary(resolutions)
        _print_skipped_undated(resolutions, args.skip_undated)
        _print_heif_note(resolutions)
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

        results = execute(
            resolutions,
            destination,
            catalog,
            apply=args.apply,
            set_timestamps=not args.no_timestamps,
            skip_undated=args.skip_undated,
            move=getattr(args, "move", False),
            relocation=relocation if args.apply else None,
            event_ids=event_ids,
            ingest=ingest_ctx,
            drive_uuid=drive_uuid,
            progress=_progress_printer("moving" if relocation else "copying")
            if args.apply
            else None,
        )

        if relocation is not None and args.apply:
            moved = sum(1 for r in results if r.status is ActionStatus.MOVED_IN_PLACE)
            # A run that renamed nothing leaves no journal row to offer as an undo.
            if moved:
                catalog.finish_inplace_run(relocation.run_id)
            else:
                catalog.discard_inplace_run(relocation.run_id)

    print()
    if not args.apply:
        print(_SEPARATOR)
        print("DRY RUN - nothing was written or recorded. Re-run with --apply to execute.")
        print(_SEPARATOR)
        return 0
    return _print_execution(results)


def _fmt_extensions(paths: list[Path]) -> str:
    counts = Counter(p.suffix.lower() or "(no ext)" for p in paths)
    return ", ".join(f"{ext} x{n}" for ext, n in counts.most_common())


def _print_skipped(scan: SourceScan) -> None:
    """Account for every file that was NOT organized, grouped by extension. Never silent."""
    if not scan.documents and not scan.unrecognized:
        return
    print("\nSkipped (not organized):")
    if scan.documents:
        print(f"  documents: {len(scan.documents)}  ({_fmt_extensions(scan.documents)})")
    if scan.unrecognized:
        print(f"  unrecognized: {len(scan.unrecognized)}  ({_fmt_extensions(scan.unrecognized)})")
        print(
            "    (not recognized as media; some may be video formats truestill does not organize yet)"
        )


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
        metadata = read_metadata(files)
    except ExiftoolMissingError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 3
    try:
        destination = _build_destination(args.destination, rclone=args.rclone)
    except DestinationError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 4
    relocation = _build_relocation(args)
    if relocation is not None and not _confirm_in_place(args, len(files)):
        return 0
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


def _confirm_in_place(args: argparse.Namespace, file_count: int) -> bool:
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
    answer = input("\nType 'move' to proceed (anything else aborts): ").strip()
    if answer != "move":
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
    if not args.takeout.is_dir():
        print(f"error: takeout path is not a directory: {args.takeout}", file=sys.stderr)
        return 2
    print(f"Scanning Takeout export at {args.takeout} ...")
    scan = scan_takeout(args.takeout)
    source_scan = scan_source(args.takeout)
    # A Takeout export's own .json sidecars and .html scaffolding are consumed here, not skipped,
    # so they are excluded from the skipped report -- only genuinely unhandled files are shown.
    _takeout_noise = {".json", ".html", ".htm"}
    skipped = SourceScan(
        media=source_scan.media,
        documents=[p for p in source_scan.documents if p.suffix.lower() not in _takeout_noise],
        unrecognized=source_scan.unrecognized,
    )
    files = source_scan.media
    if not files:
        print(f"No media files found under {args.takeout}")
        _print_skipped(skipped)
        return 0
    print(
        f"Found {len(files)} media file(s); matched {len(scan.sidecars)} sidecar(s), "
        f"{len(scan.missing_sidecar)} without.\n"
    )
    try:
        metadata = read_metadata(files)
    except ExiftoolMissingError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 3
    try:
        destination = _build_destination(args.destination, rclone=args.rclone)
    except DestinationError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 4

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
    """Render the three sample files through ``template`` for the CLI preview."""
    print("Preview:")
    for context, row in zip(SAMPLE_CONTEXTS, preview(template, SAMPLE_CONTEXTS), strict=True):
        when = context.captured_at.strftime("%Y-%m-%d") if context.captured_at else "undated"
        print(f"  {context.category:12} {when:10} -> {row.path.as_posix()}")
        for warning in row.warnings:
            print(f"      ! {warning}")


def _cmd_config(args: argparse.Namespace) -> int:
    target = PRESETS[args.preset].timeline if args.preset else args.set_template

    with Catalog(args.db) as catalog:
        stored = catalog.get_setting(LAYOUT_TEMPLATE_KEY)

        if target is None:  # show (optionally previewing the current template)
            current = stored or DEFAULT_TEMPLATE_STRING
            print(f"Layout template: {current}" + ("" if stored else "  (default)"))
            if args.preview:
                _print_layout_preview(resolve_template(stored))
            print("\nPresets:")
            for name, preset in PRESETS.items():
                print(f"  {name:24} {preset.timeline}")
            return 0

        try:
            template = LayoutTemplate.parse(target)
        except TemplateError as exc:
            print(f"error: invalid template: {exc}", file=sys.stderr)
            return 2

        _print_layout_preview(template)
        if args.preview:
            print("\n(preview only -- not saved)")
            return 0

        catalog.set_setting(LAYOUT_TEMPLATE_KEY, target)
        print(f"\nSaved. New files will be organized as: {target}")
        print("Existing files are left in place (split-era default).")
        return 0


def _cmd_migrate_layout(args: argparse.Namespace) -> int:
    marker = read_marker(args.path)
    if marker is None:
        print(
            f"error: no {MARKER_NAME} at {args.path} -- connect the drive first",
            file=sys.stderr,
        )
        return 2

    destination = LocalDestination(args.path)
    with Catalog(args.db) as catalog:
        catalog.upsert_drive(uuid=marker.uuid, label=marker.label)
        if args.apply and pin_existing_layout(catalog):
            print(_PINNED_NOTICE)
        template = resolve_for(catalog)
        outcome = run_migration(catalog, destination, marker.uuid, template, apply=args.apply)

        plan = outcome.plan
        print(f"Drive '{marker.label}': layout {template.template}")
        if outcome.resumed:
            print(f"Recovered {outcome.resumed} move(s) from an interrupted run.")
        print(f"{len(plan.moves)} file(s) to relocate, {plan.unchanged} already in place.")
        for move in plan.moves[:_STATUS_PREVIEW]:
            print(f"  {move.old_relative}  ->  {move.new_relative}")
        if len(plan.moves) > _STATUS_PREVIEW:
            print(f"  ... and {len(plan.moves) - _STATUS_PREVIEW} more")
        for warning in plan.warnings:
            print(f"  ! {warning}")

        others = [d for d in catalog.list_drives() if d["uuid"] != marker.uuid and d["file_count"]]
        for drive in others:
            print(f"  pending: drive '{drive['label']}' has copies too -- reconnect it and re-run")

        if not args.apply:
            print("\nPreview only. Re-run with --apply to move the files.")
            return 0
        print(f"\nMigrated {outcome.migrated} file(s). Sources were never touched.")
        return 0


def _cmd_undo_organize(args: argparse.Namespace) -> int:
    with Catalog(args.db) as catalog:
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


def _cmd_reclaim(args: argparse.Namespace) -> int:
    marker = read_marker(args.path)
    if marker is None:
        print(
            f"error: no {MARKER_NAME} at {args.path} -- connect the drive first",
            file=sys.stderr,
        )
        return 2
    if args.min_copies < 1:
        print("error: --min-copies must be at least 1", file=sys.stderr)
        return 2

    with Catalog(args.db) as catalog:
        catalog.upsert_drive(uuid=marker.uuid, label=marker.label)
        plan = plan_reclaim(catalog, marker.uuid, args.path, min_copies=args.min_copies)

        n = len(plan.candidates)
        gib = plan.total_bytes / 1e9
        print(f"Drive '{marker.label}': {n} source file(s) safely backed up and re-verified.")
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
            print(
                f"  held back: {plan.below_min_copies} file(s) below --min-copies={args.min_copies}"
            )
        if plan.single_copy:
            print(
                f"  WARNING: {len(plan.single_copy)} file(s) would then exist in only ONE place "
                f"(raise --min-copies to exclude them)"
            )

        if not args.apply:
            print("\nPreview only. Re-run with --apply to delete these sources.")
            return 0
        if n == 0:
            print("\nNothing to reclaim.")
            return 0

        print(f"\nThis PERMANENTLY DELETES {n} source file(s), freeing {gib:.2f} GB.")
        answer = input("Type 'delete' to proceed (anything else aborts): ").strip()
        if answer != "delete":
            print("Aborted -- nothing was deleted.")
            return 0

        outcome = run_reclaim(catalog, marker.uuid, args.path, min_copies=args.min_copies)
        print(f"\nFreed {outcome.deleted} source file(s), {outcome.freed_bytes / 1e9:.2f} GB.")
        if outcome.kept:
            print(f"Kept {outcome.kept} file(s) that failed a final re-verify -- not deleted.")
        return 0


def main(argv: list[str] | None = None) -> int:
    """Run the CLI. Returns a process exit code."""
    args = _build_parser().parse_args(argv)
    dispatch = {
        "organize": _cmd_organize,
        "ingest": _cmd_ingest,
        "drives": _cmd_drives,
        "where": _cmd_where,
        "verify": _cmd_verify,
        "status": _cmd_status,
        "config": _cmd_config,
        "migrate-layout": _cmd_migrate_layout,
        "reclaim": _cmd_reclaim,
        "undo-organize": _cmd_undo_organize,
    }
    return dispatch[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
