"""Command-line entry point.

Defaults are inert: with no ``--apply`` the tool analyses the source, resolves duplicates
and prints what it *would* upload, writing nothing to the destination or the catalog.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from vaeon_core.catalog import Catalog
from vaeon_core.categorize import build_rules
from vaeon_core.dedup import DedupIndex
from vaeon_core.destinations import Destination, LocalDestination, RcloneDestination
from vaeon_core.destinations.base import DestinationError
from vaeon_core.drive import DriveMarker, create_marker, read_marker
from vaeon_core.exif import ExiftoolMissingError, read_metadata
from vaeon_core.hashing import DEFAULT_PHASH_THRESHOLD
from vaeon_core.layout import (
    DEFAULT_TEMPLATE_STRING,
    LAYOUT_TEMPLATE_KEY,
    PRESETS,
    SAMPLE_CONTEXTS,
    LayoutTemplate,
    TemplateError,
    preview,
    resolve_template,
)
from vaeon_core.migrate import run_migration
from vaeon_core.models import (
    ActionResult,
    ActionStatus,
    DateSource,
    Decision,
    DuplicateMatch,
    Resolution,
)
from vaeon_core.organizer import discover, execute, plan, resolve
from vaeon_core.progress import ProgressCallback
from vaeon_core.scan import DEFAULT_WORKERS
from vaeon_core.takeout import (
    IngestContext,
    MetadataWrite,
    TakeoutScan,
    TakeoutSidecar,
    scan_takeout,
)
from vaeon_core.verify import CopyStatus, CopyToVerify, verify_copies

from vaeon_cli.events_review import Prompt, album_prompt, run_event_stage

_SEPARATOR = "=" * 100
_DEFAULT_DB = Path("reports/catalog.sqlite")
_STATUS_PREVIEW = 20  # how many single-copy files `vaeon status` lists before eliding


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


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="vaeon",
        description="Organize, de-duplicate and back up a media library to a pluggable destination.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    organize = sub.add_parser("organize", help="organize a folder of media files")
    organize.add_argument("source", type=Path, help="folder to analyse (searched recursively)")
    organize.add_argument("--all-files", action="store_true", help="include non-media extensions")
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
    _add_common_options(ingest)

    drives = sub.add_parser("drives", help="list known backup drives, or init a drive marker")
    drives.add_argument("--db", type=Path, default=_DEFAULT_DB, help="SQLite catalog")
    drives.add_argument("--init", type=Path, metavar="ROOT", help="write a drive marker at ROOT")
    drives.add_argument("--label", help="human label for --init")
    drives.add_argument("--uuid", help="re-attach a known uuid instead of minting a new one")

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


def _cmd_drives(args: argparse.Namespace) -> int:
    with Catalog(args.db) as catalog:
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
            print("No drives known. Initialise one: vaeon drives --init <root> --label <name>")
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
        print(f"error: no .vaeon-drive.json at {root} -- connect the drive first", file=sys.stderr)
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
    print("\n  (read-only: vaeon never repairs; re-copy the source to restore a bad file.)")
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
    """A terminal progress callback: an in-place ``label: done/total`` counter."""

    def report(done: int, total: int) -> None:
        end = "\n" if done >= total else "\r"
        print(f"  {label}: {done}/{total}", end=end, flush=True)

    return report


def _build_destination(spec: str, *, rclone: bool) -> Destination:
    if rclone:
        return RcloneDestination(spec)
    return LocalDestination(Path(spec))


def _local_drive_marker(args: argparse.Namespace) -> DriveMarker | None:
    """Drive identity of a local destination, if it carries a ``.vaeon-drive.json`` marker.

    rclone remotes are always-online cloud, not drives-in-a-drawer, so drive tracking is scoped
    to local destinations. A local root without a marker is fine -- copies just aren't tracked
    per-drive until `vaeon drives init` is run there.
    """
    if args.rclone:
        return None
    return read_marker(Path(args.destination))


def _short_sha(sha256: str | None) -> str:
    return f"{sha256[:16]}..." if sha256 else "(not hashed: unique size)"


def _format_new(resolution: Resolution, root_label: str) -> str:
    decision = resolution.decision
    when = decision.captured_at.strftime("%Y-%m-%d %H:%M:%S") if decision.captured_at else "-"
    tag = decision.date_tag or decision.date_source.value
    flag = "  <-- REVIEW" if decision.needs_review else ""
    phash = resolution.hashes.perceptual or "n/a (not an image)"
    lines = [
        f"  {decision.source.name}",
        (
            f"      category : {decision.category.label}  "
            f"[{decision.category.confidence.value} confidence, rule={decision.category.rule}]"
        ),
        f"      why      : {decision.category.reason}",
        f"      date     : {when}  (source={decision.date_source.value}, tag={tag}){flag}",
        f"      sha256   : {_short_sha(resolution.hashes.sha256)}    dhash: {phash}",
    ]
    if resolution.near_duplicate is not None:
        near = resolution.near_duplicate
        distance = f", distance={near.distance}" if near.distance is not None else ""
        lines.append(f"      NEAR-DUP  : looks like {near.matched_path} [{near.origin}{distance}]")
        lines.append("                  uploaded anyway (kept, not dropped) - review manually")
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
    print(f"NEW UNIQUE ({len(unique)}) - would be uploaded")
    print(_SEPARATOR)
    for resolution in unique:
        print(_format_new(resolution, root_label))
        print()

    print(_SEPARATOR)
    print(f"NEAR-DUPLICATES ({len(near)}) - UPLOADED and flagged for your review")
    print(_SEPARATOR)
    if not near:
        print("  (none)")
    for resolution in near:
        print(_format_new(resolution, root_label))
        print()

    print(_SEPARATOR)
    print(f"EXACT DUPLICATES ({len(exact)}) - skipped, not uploaded")
    print(_SEPARATOR)
    if not exact:
        print("  (none)")
    for resolution in exact:
        print(_format_exact(resolution))
        print()


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
    print(f"  uploaded (unique)  : {len(uploads) - len(near)}")
    print(f"  uploaded (near-dup): {len(near)}  (kept + flagged for review)")
    print(f"  skipped (exact dup): {len(exact)}")
    print(f"  folders derived    : {len(labels)}")
    for label, count in labels.most_common():
        print(f"      {label:<28} {count}")
    print("  date sources (uploaded files):")
    for source, count in sources.most_common():
        print(f"      {source:<28} {count}")

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


def _print_execution(results: list[ActionResult]) -> int:
    outcomes = Counter(result.status.value for result in results)
    print(_SEPARATOR)
    print("EXECUTED")
    print(_SEPARATOR)
    for status, count in outcomes.most_common():
        print(f"  {status:<12} {count}")

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
) -> int:
    with Catalog(args.db) as catalog:
        template = resolve_template(catalog.get_setting(LAYOUT_TEMPLATE_KEY))
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
        if scan is not None:
            _print_ingest_report(resolutions, scan)
        if args.report:
            _write_json_report(args.report, resolutions)

        results = execute(
            resolutions,
            destination,
            catalog,
            apply=args.apply,
            set_timestamps=not args.no_timestamps,
            event_ids=event_ids,
            ingest=ingest_ctx,
            drive_uuid=drive_uuid,
            progress=_progress_printer("copying") if args.apply else None,
        )

    print()
    if not args.apply:
        print(_SEPARATOR)
        print("DRY RUN - nothing was uploaded or recorded. Re-run with --apply to execute.")
        print(_SEPARATOR)
        return 0
    return _print_execution(results)


def _cmd_organize(args: argparse.Namespace) -> int:
    if not args.source.is_dir():
        print(f"error: source is not a directory: {args.source}", file=sys.stderr)
        return 2
    files = discover(args.source, all_files=args.all_files)
    if not files:
        print(f"No media files found under {args.source}")
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
    return _run_pipeline(args, files, metadata, destination, drive_marker=_local_drive_marker(args))


def _cmd_ingest(args: argparse.Namespace) -> int:
    if not args.takeout.is_dir():
        print(f"error: takeout path is not a directory: {args.takeout}", file=sys.stderr)
        return 2
    print(f"Scanning Takeout export at {args.takeout} ...")
    scan = scan_takeout(args.takeout)
    files = discover(args.takeout)
    if not files:
        print(f"No media files found under {args.takeout}")
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

    return _run_pipeline(
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


def _print_layout_preview(template: LayoutTemplate) -> None:
    """Render the three sample files through ``template`` for the CLI preview."""
    print("Preview:")
    for context, row in zip(SAMPLE_CONTEXTS, preview(template, SAMPLE_CONTEXTS), strict=True):
        when = context.captured_at.strftime("%Y-%m-%d") if context.captured_at else "undated"
        print(f"  {context.category:12} {when:10} -> {row.path.as_posix()}")
        for warning in row.warnings:
            print(f"      ! {warning}")


def _cmd_config(args: argparse.Namespace) -> int:
    target = PRESETS[args.preset] if args.preset else args.set_template

    with Catalog(args.db) as catalog:
        stored = catalog.get_setting(LAYOUT_TEMPLATE_KEY)

        if target is None:  # show (optionally previewing the current template)
            current = stored or DEFAULT_TEMPLATE_STRING
            print(f"Layout template: {current}" + ("" if stored else "  (default)"))
            if args.preview:
                _print_layout_preview(resolve_template(stored))
            print("\nPresets:")
            for name, tmpl in PRESETS.items():
                print(f"  {name:24} {tmpl}")
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
            f"error: no .vaeon-drive.json at {args.path} -- connect the drive first",
            file=sys.stderr,
        )
        return 2

    destination = LocalDestination(args.path)
    with Catalog(args.db) as catalog:
        catalog.upsert_drive(uuid=marker.uuid, label=marker.label)
        template = resolve_template(catalog.get_setting(LAYOUT_TEMPLATE_KEY))
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
    }
    return dispatch[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
