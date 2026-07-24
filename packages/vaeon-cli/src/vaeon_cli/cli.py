"""Command-line entry point.

Defaults are inert: with no ``--apply`` the tool analyses the source, resolves duplicates
and prints what it *would* upload, writing nothing to the destination or the catalog.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from vaeon_core.catalog import Catalog
from vaeon_core.categorize import build_rules
from vaeon_core.dedup import DedupIndex
from vaeon_core.destinations import Destination, LocalDestination, RcloneDestination
from vaeon_core.destinations.base import DestinationError
from vaeon_core.exif import ExiftoolMissingError, read_metadata
from vaeon_core.hashing import DEFAULT_PHASH_THRESHOLD
from vaeon_core.models import (
    ActionResult,
    ActionStatus,
    DateSource,
    DuplicateMatch,
    Resolution,
)
from vaeon_core.organizer import discover, execute, plan, resolve
from vaeon_core.scan import DEFAULT_WORKERS

_SEPARATOR = "=" * 100
_DEFAULT_DB = Path("reports/catalog.sqlite")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="vaeon",
        description=(
            "Categorize, date-organize and de-duplicate a media library into "
            "<Label>/YYYY/MM/ at a pluggable destination. Folder labels are derived from "
            "each file's own metadata, not a fixed list."
        ),
    )
    parser.add_argument("source", type=Path, help="folder to analyse (searched recursively)")
    parser.add_argument(
        "destination",
        help="local directory path, or an rclone remote spec with --rclone (e.g. pcloud:Photos/GoogleBackup)",
    )
    parser.add_argument(
        "--rclone",
        action="store_true",
        help="treat destination as an rclone remote spec instead of a local path",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="actually upload and record (default: dry run, nothing is written)",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=_DEFAULT_DB,
        help=f"SQLite catalog for resume/dedup history (default: {_DEFAULT_DB})",
    )
    parser.add_argument(
        "--phash-threshold",
        type=int,
        default=DEFAULT_PHASH_THRESHOLD,
        metavar="N",
        help=f"max Hamming distance for a perceptual duplicate (default: {DEFAULT_PHASH_THRESHOLD})",
    )
    parser.add_argument(
        "--by-device",
        action="store_true",
        help="name capture folders after the device instead of 'Camera'",
    )
    parser.add_argument("--all-files", action="store_true", help="include non-media extensions")
    parser.add_argument(
        "--no-timestamps",
        action="store_true",
        help="do not set the local copy's mtime from the capture date before upload",
    )
    parser.add_argument(
        "--pool",
        choices=("thread", "process"),
        default="thread",
        help="worker pool used for the concurrent hashing scan (default: thread)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=DEFAULT_WORKERS,
        metavar="N",
        help=f"number of hashing workers (default: {DEFAULT_WORKERS}, = CPU count)",
    )
    parser.add_argument(
        "--report", type=Path, metavar="PATH", help="write the full decision report as JSON"
    )
    return parser


def _build_destination(spec: str, *, rclone: bool) -> Destination:
    if rclone:
        return RcloneDestination(spec)
    return LocalDestination(Path(spec))


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
        print(f"\n  MANUAL REVIEW ({len(review)}) - date not from embedded metadata:")
        for resolution in review:
            origin = (
                "filename pattern"
                if resolution.decision.date_source is DateSource.FILENAME
                else "no date evidence"
            )
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


def main(argv: list[str] | None = None) -> int:
    """Run the CLI. Returns a process exit code."""
    args = _build_parser().parse_args(argv)

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

    decisions = plan(files, metadata, build_rules(by_device=args.by_device))

    with Catalog(args.db) as catalog:
        index = DedupIndex.from_catalog_rows(catalog.seed_rows(), args.phash_threshold)
        catalog_sizes = catalog.known_sizes()
        if catalog.count():
            print(f"Catalog {args.db} holds {catalog.count()} previously-processed file(s).\n")

        resolutions = resolve(
            decisions,
            index,
            catalog_sizes=catalog_sizes,
            pool=args.pool,
            workers=args.workers,
        )

        root_label = destination.describe()
        _print_report(resolutions, root_label)
        _print_summary(resolutions)
        if args.report:
            _write_json_report(args.report, resolutions)

        results = execute(
            resolutions,
            destination,
            catalog,
            apply=args.apply,
            set_timestamps=not args.no_timestamps,
        )

    print()
    if not args.apply:
        print(_SEPARATOR)
        print("DRY RUN - nothing was uploaded or recorded. Re-run with --apply to execute.")
        print(_SEPARATOR)
        return 0

    return _print_execution(results)


if __name__ == "__main__":
    raise SystemExit(main())
