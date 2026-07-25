"""Pipeline stages: discover -> plan -> resolve (dedup) -> execute.

Each stage is a plain function so they compose and test in isolation:

* **discover** -- find media files under a source tree.
* **plan** -- categorize and place each file (pure; no I/O beyond metadata already read).
* **resolve** -- hash each file and decide new-vs-duplicate against the dedup index.
* **execute** -- upload the genuinely-new files to a :class:`Destination`, recording each
  in the catalog. Defaults to a dry run; ``apply=True`` is the only writing path.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import threading
from collections.abc import Iterable, Sequence
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path, PurePosixPath
from typing import Any

from vaeon_core.catalog import Catalog
from vaeon_core.categorize import Rule, categorize
from vaeon_core.dates import resolve_capture_datetime
from vaeon_core.dedup import DedupIndex
from vaeon_core.destinations.base import Destination, DestinationError
from vaeon_core.exif import write_metadata
from vaeon_core.hashing import sha256_file
from vaeon_core.layout import DEFAULT_TEMPLATE, RenderContext
from vaeon_core.models import (
    ActionResult,
    ActionStatus,
    CategoryMatch,
    DateSource,
    Decision,
    DuplicateKind,
    Resolution,
)
from vaeon_core.naming import dated_filename
from vaeon_core.progress import ProgressCallback
from vaeon_core.scan import DEFAULT_WORKERS, PoolKind, compute_hashes
from vaeon_core.takeout import IngestContext, MetadataWrite, TakeoutSidecar

#: Extensions treated as media. Anything else is skipped unless the caller opts in.
MEDIA_EXTENSIONS: frozenset[str] = frozenset(
    {
        # images
        ".jpg",
        ".jpeg",
        ".png",
        ".gif",
        ".bmp",
        ".webp",
        ".tif",
        ".tiff",
        ".heic",
        ".heif",
        ".avif",
        ".dng",
        ".raw",
        ".cr2",
        ".cr3",
        ".nef",
        ".arw",
        ".orf",
        ".rw2",
        ".raf",
        ".srw",
        # video
        ".mp4",
        ".mov",
        ".m4v",
        ".3gp",
        ".3g2",
        ".avi",
        ".mkv",
        ".webm",
        ".mpg",
        ".mpeg",
        ".wmv",
        ".flv",
        ".mts",
        ".m2ts",
        # audio (voice notes travel with messenger exports)
        ".m4a",
        ".aac",
        ".opus",
        ".ogg",
        ".mp3",
        ".wav",
        ".amr",
    }
)


def discover(source: Path, *, all_files: bool = False) -> list[Path]:
    """Return media files under ``source``, sorted, skipping hidden paths."""
    found: list[Path] = []
    for path in sorted(source.rglob("*")):
        if not path.is_file():
            continue
        if any(part.startswith(".") for part in path.relative_to(source).parts):
            continue
        if all_files or path.suffix.lower() in MEDIA_EXTENSIONS:
            found.append(path)
    return found


def build_relative(label: str, captured_at: datetime | None, filename: str) -> PurePosixPath:
    """Return the destination-relative path for a non-event file, ``<Label>/YYYY/MM/<filename>``.

    Renders through the active :data:`~vaeon_core.layout.DEFAULT_TEMPLATE`; undated files land in
    ``<Label>/Undated/`` so the category survives even when the date does not.
    """
    directory = DEFAULT_TEMPLATE.render(RenderContext(category=label, captured_at=captured_at))
    return directory / filename


def build_destination(root: Path, label: str, captured_at: datetime | None, filename: str) -> Path:
    """Absolute local path for a file. Convenience for local previews and tests."""
    return root / build_relative(label, captured_at, filename)


def plan(
    files: Sequence[Path],
    metadata: dict[Path, dict[str, Any]],
    rules: tuple[Rule, ...] | None = None,
    *,
    rename: bool = True,
    takeout: dict[Path, TakeoutSidecar] | None = None,
    tz_offset: timedelta | None = None,
    prefer_takeout: bool = False,
) -> list[Decision]:
    """Produce one :class:`Decision` per file. Touches nothing on disk.

    With ``rename`` (the default) the destination copy is named
    ``YYYYMMDD_HHMMSS_<original>`` from the same date evidence used for placement; the
    original source file is never touched. ``takeout`` supplies rescued sidecar dates (Takeout
    ingestion); ``tz_offset``/``prefer_takeout`` control how those interact with EXIF.
    """
    takeout = takeout or {}
    decisions: list[Decision] = []
    for path in files:
        meta = metadata.get(path, {})
        category: CategoryMatch = categorize(path, meta, rules)
        captured_at, date_source, date_tag = resolve_capture_datetime(
            path,
            meta,
            takeout=takeout.get(path),
            tz_offset=tz_offset,
            prefer_takeout=prefer_takeout,
        )
        new_name = dated_filename(
            path.name,
            captured_at,
            time_known=date_source is DateSource.EXIF,
            enabled=rename,
        )
        decisions.append(
            Decision(
                source=path,
                category=category,
                captured_at=captured_at,
                date_source=date_source,
                date_tag=date_tag,
                relative=Path(build_relative(category.label, captured_at, new_name)),
            )
        )
    return decisions


def resolve(
    decisions: Iterable[Decision],
    index: DedupIndex,
    *,
    catalog_sizes: frozenset[int] = frozenset(),
    pool: PoolKind = "thread",
    workers: int = DEFAULT_WORKERS,
    progress: ProgressCallback | None = None,
    cancel: threading.Event | None = None,
) -> list[Resolution]:
    """Hash each file (concurrently) and classify it, updating ``index`` as it goes.

    Hashing is a parallel pass with a size pre-filter (see :mod:`vaeon.scan`); the dedup
    classification that follows is sequential because it is order-dependent. Exact (SHA-256)
    is checked before perceptual (dHash). By policy the two tiers differ: an exact duplicate
    is skipped and *not* indexed (its hash is already known); a perceptual near-duplicate is
    uploaded anyway and *is* indexed, so every member of a look-alike cluster is flagged
    pairwise and none is ever silently dropped.
    """
    decision_list = list(decisions)
    hashes = compute_hashes(
        [d.source for d in decision_list],
        catalog_sizes=catalog_sizes,
        pool=pool,
        workers=workers,
        progress=progress,
        cancel=cancel,
    )

    resolutions: list[Resolution] = []
    for decision in decision_list:
        file_hashes = hashes[decision.source]
        match = index.check(file_hashes.sha256, file_hashes.perceptual)

        exact = match if match is not None and match.kind is DuplicateKind.EXACT else None
        near = match if match is not None and match.kind is DuplicateKind.PERCEPTUAL else None

        if exact is None:
            # Uploaded files (unique or near-dup) go into the index so later files compare
            # against them too; exact duplicates are already represented by their twin.
            index.register(str(decision.source), file_hashes.sha256, file_hashes.perceptual)

        resolutions.append(
            Resolution(
                decision=decision,
                hashes=file_hashes,
                exact_duplicate=exact,
                near_duplicate=near,
            )
        )
    return resolutions


def apply_events(
    resolutions: Sequence[Resolution],
    assignments: dict[str, tuple[datetime, str]],
) -> list[Resolution]:
    """Rewrite named-event members into ``<Label>/YYYY/MM/YYYYMMDD_slug/`` folders.

    ``assignments`` maps a member's source path (``str``) to its event's ``(start, slug)``.
    The event's *start* month is used for the whole event, so a cluster that straddles a
    month boundary lands together under the start month rather than being split. Files not
    in a named event are returned unchanged.
    """
    if not assignments:
        return list(resolutions)

    updated: list[Resolution] = []
    for resolution in resolutions:
        assignment = assignments.get(str(resolution.decision.source))
        if assignment is None:
            updated.append(resolution)
            continue
        start, slug = assignment
        label = resolution.decision.category.label
        filename = resolution.decision.relative.name
        directory = DEFAULT_TEMPLATE.render(
            RenderContext(
                category=label,
                captured_at=resolution.decision.captured_at,
                event=(start, slug),
            )
        )
        new_relative = Path(directory / filename)
        new_decision = replace(resolution.decision, relative=new_relative)
        updated.append(replace(resolution, decision=new_decision))
    return updated


def _free_relative(destination: Destination, relative: str) -> tuple[str, bool]:
    """Return a relative path that does not collide at ``destination``.

    Content identity is already handled by dedup, so a collision here means a *different*
    file happens to share the same category/date/name (e.g. two distinct ``IMG_0001.jpg``).
    Such a file is suffixed rather than overwriting the incumbent -- never lose data.
    """
    if not destination.exists(relative):
        return relative, False
    posix = PurePosixPath(relative)
    index = 1
    while True:
        candidate = str(posix.with_name(f"{posix.stem}_{index}{posix.suffix}"))
        if not destination.exists(candidate):
            return candidate, True
        index += 1


def _safe_size(path: Path) -> int | None:
    try:
        return path.stat().st_size
    except OSError:
        return None


def _apply_timestamp(source: Path, captured_at: datetime | None) -> None:
    """Set the local source copy's mtime to the capture date.

    Both destination backends preserve source mtime on transfer, so stamping the staged
    copy is what makes the capture date reach the destination. This mutates only the local
    staging copy -- never a phone or Google Photos original.
    """
    if captured_at is None:
        return
    stamp = captured_at.timestamp()
    os.utime(source, (stamp, stamp))


def _upload_with_metadata_write(
    decision: Decision,
    write: MetadataWrite,
    final_relative: str,
    destination: Destination,
    *,
    set_timestamps: bool,
) -> str:
    """Stage a copy, bake rescued metadata in, upload it, and return the copy's SHA-256.

    The source is never modified: the metadata write happens on a temporary staged copy, so
    the invariant "originals are untouched" holds even though the uploaded copy now differs
    (by metadata only, losslessly) from the source.
    """
    with tempfile.TemporaryDirectory(prefix="vaeon-ingest-") as tmp:
        staged = Path(tmp) / decision.relative.name
        shutil.copy2(decision.source, staged)
        write_metadata(
            staged,
            taken_at_local=write.taken_at_local,
            gps=write.gps,
            description=write.description,
        )
        if set_timestamps:
            _apply_timestamp(staged, decision.captured_at)
        copy_sha = sha256_file(staged)
        destination.upload(staged, final_relative)
    return copy_sha


def _aggregate_albums(
    resolutions: Sequence[Resolution], ingest: IngestContext
) -> dict[str, set[str]]:
    """Union album membership across byte-identical copies, keyed by source SHA-256."""
    by_sha: dict[str, set[str]] = {}
    for resolution in resolutions:
        sha = resolution.hashes.sha256
        album = ingest.albums.get(str(resolution.decision.source))
        if sha is not None and album is not None:
            by_sha.setdefault(sha, set()).add(album)
    return by_sha


def execute(
    resolutions: Iterable[Resolution],
    destination: Destination,
    catalog: Catalog | None = None,
    *,
    apply: bool = False,
    set_timestamps: bool = True,
    event_ids: dict[str, int] | None = None,
    ingest: IngestContext | None = None,
    drive_uuid: str | None = None,
    progress: ProgressCallback | None = None,
    cancel: threading.Event | None = None,
) -> list[ActionResult]:
    """Upload genuinely-new files; skip duplicates. ``apply=False`` reports only.

    ``event_ids`` maps a source path to its assigned event. ``ingest`` (Takeout only) requests
    baking rescued metadata into copies and records album membership; when absent, the copy is
    byte-identical to the source and ``copy_sha256`` equals the source hash. ``drive_uuid``, when
    the destination is an identified drive, records each copy's location in the catalog.
    ``progress`` is called ``(done, total)`` per file; ``cancel`` stops the run early (already-
    uploaded files stay -- the run is resumable).
    """
    resolutions = list(resolutions)
    results: list[ActionResult] = []
    events = event_ids or {}
    ingest = ingest or IngestContext()
    albums_by_sha = _aggregate_albums(resolutions, ingest)
    total = len(resolutions)

    for done, resolution in enumerate(resolutions, start=1):
        if cancel is not None and cancel.is_set():
            break
        if progress is not None:
            progress(done, total)
        decision = resolution.decision
        relative = decision.relative.as_posix()

        if resolution.exact_duplicate is not None:
            match = resolution.exact_duplicate
            detail = f"exact match of {match.matched_path} [{match.origin}]"
            results.append(ActionResult(resolution, ActionStatus.DUPLICATE, None, detail))
            continue

        if not apply:
            results.append(ActionResult(resolution, ActionStatus.PLANNED, decision.relative))
            continue

        try:
            final_relative, renamed = _free_relative(destination, relative)
            # Source hash is the dedup identity; computed now for any unique-size file the
            # scan skipped, since the file is being read for upload anyway.
            source_sha = resolution.hashes.sha256 or sha256_file(decision.source)

            write = ingest.writes.get(str(decision.source))
            if write is not None and write.has_content:
                copy_sha = _upload_with_metadata_write(
                    decision, write, final_relative, destination, set_timestamps=set_timestamps
                )
            else:
                if set_timestamps:
                    _apply_timestamp(decision.source, decision.captured_at)
                destination.upload(decision.source, final_relative)
                copy_sha = source_sha  # byte-identical copy

            if catalog is not None:
                album_set = set(albums_by_sha.get(source_sha, set()))
                own_album = ingest.albums.get(str(decision.source))
                if own_album is not None:
                    album_set.add(own_album)
                catalog.record_uploaded(
                    source_path=str(decision.source),
                    original_name=decision.source.name,
                    sha256=source_sha,
                    copy_sha256=copy_sha,
                    perceptual=resolution.hashes.perceptual,
                    size=_safe_size(decision.source),
                    captured_at=decision.captured_at.isoformat() if decision.captured_at else None,
                    category=decision.category.label,
                    relative=final_relative,
                    event_id=events.get(str(decision.source)),
                    albums=sorted(album_set),
                    drive_uuid=drive_uuid,
                )

            status = ActionStatus.RENAMED if renamed else ActionStatus.UPLOADED
            notes = []
            if renamed:
                notes.append("suffixed to avoid an unrelated name collision")
            if resolution.near_duplicate is not None:
                near = resolution.near_duplicate
                distance = f", distance={near.distance}" if near.distance is not None else ""
                notes.append(f"near-duplicate of {near.matched_path} [{near.origin}{distance}]")
            results.append(ActionResult(resolution, status, Path(final_relative), "; ".join(notes)))

        except (OSError, DestinationError) as exc:
            results.append(ActionResult(resolution, ActionStatus.FAILED, None, str(exc)))

    return results
