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
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from pathlib import Path, PurePosixPath
from typing import Any

from truestill_core.catalog import Catalog
from truestill_core.categorize import Rule, categorize
from truestill_core.dates import is_suspect_default, resolve_capture_datetime
from truestill_core.dedup import DedupIndex
from truestill_core.destinations.base import CrossDeviceError, Destination, DestinationError
from truestill_core.exif import WRITE_BATCH_SIZE, build_metadata_args, write_metadata_batch
from truestill_core.hash_cache import HashCache
from truestill_core.hashing import sha256_file
from truestill_core.layout import (
    DEFAULT_SCHEME,
    TIMELINE_RULE,
    LayoutScheme,
    RenderContext,
)
from truestill_core.models import (
    ActionResult,
    ActionStatus,
    CategoryMatch,
    DateSource,
    Decision,
    DuplicateKind,
    Resolution,
    status_label,
)
from truestill_core.naming import dated_filename
from truestill_core.progress import Phase, Progress, ProgressCallback
from truestill_core.scan import DEFAULT_WORKERS, PoolKind, compute_hashes
from truestill_core.takeout import IngestContext, MetadataWrite, TakeoutSidecar

#: Photo extensions (standard + HEIF variants + RAW). RAW is dated by exiftool; perceptual works
#: for the TIFF-based RAW, exact-only otherwise.
IMAGE_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".jpg",
        ".jpeg",
        ".jpe",
        ".jfif",
        ".png",
        ".gif",
        ".bmp",
        ".webp",
        ".tif",
        ".tiff",
        ".heic",
        ".heif",
        ".hif",
        ".avif",
        ".dng",
        ".raw",
        ".cr2",
        ".cr3",
        ".crw",
        ".nef",
        ".nrw",
        ".arw",
        ".sr2",
        ".srf",
        ".srw",
        ".orf",
        ".rw2",
        ".rwl",
        ".raf",
        ".pef",
        ".3fr",
        ".fff",
        ".cap",
        ".iiq",
        ".erf",
        ".mrw",
        ".dcr",
        ".kdc",
        ".x3f",
        ".ari",
        ".gpr",
    }
)

#: Video extensions.
VIDEO_EXTENSIONS: frozenset[str] = frozenset(
    {
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
    }
)

#: Audio extensions (voice notes travel with messenger exports).
AUDIO_EXTENSIONS: frozenset[str] = frozenset(
    {".m4a", ".aac", ".opus", ".ogg", ".mp3", ".wav", ".amr"}
)

#: Extensions treated as media. Anything else is skipped unless the caller opts in.
MEDIA_EXTENSIONS: frozenset[str] = IMAGE_EXTENSIONS | VIDEO_EXTENSIONS | AUDIO_EXTENSIONS


def media_kind(name: str) -> str | None:
    """Classify a path/filename as ``"photo"``, ``"video"``, ``"audio"``, or ``None``."""
    ext = Path(name).suffix.lower()
    if ext in IMAGE_EXTENSIONS:
        return "photo"
    if ext in VIDEO_EXTENSIONS:
        return "video"
    if ext in AUDIO_EXTENSIONS:
        return "audio"
    return None


#: Common document / archive extensions, reported separately from unrecognized files so a
#: skipped ``.pdf`` reads differently from a skipped video format truestill does not yet organize.
DOCUMENT_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".pdf",
        ".doc",
        ".docx",
        ".txt",
        ".rtf",
        ".odt",
        ".pages",
        ".md",
        ".xls",
        ".xlsx",
        ".csv",
        ".ods",
        ".numbers",
        ".ppt",
        ".pptx",
        ".odp",
        ".key",
        ".epub",
        ".mobi",
        ".azw3",
        ".zip",
        ".rar",
        ".7z",
        ".tar",
        ".gz",
        ".json",
        ".xml",
        ".html",
        ".htm",
    }
)


@dataclass(frozen=True)
class SourceScan:
    """Everything found under a source, partitioned so nothing is silently dropped.

    ``media`` is what the pipeline organizes; ``documents`` are known non-media files;
    ``unrecognized`` is everything else skipped -- which may include video formats truestill does
    not yet recognize. The two skipped lists are surfaced in the end-of-run report.
    """

    media: list[Path]
    documents: list[Path]
    unrecognized: list[Path]


def scan_source(source: Path, *, all_files: bool = False) -> SourceScan:
    """Walk ``source`` once, partitioning files into media / documents / unrecognized.

    Hidden paths are skipped. With ``all_files`` every file is treated as media (the
    ``--all-files`` escape hatch), so both skipped lists are empty.
    """
    media: list[Path] = []
    documents: list[Path] = []
    unrecognized: list[Path] = []
    for path in sorted(source.rglob("*")):
        if not path.is_file():
            continue
        if any(part.startswith(".") for part in path.relative_to(source).parts):
            continue
        ext = path.suffix.lower()
        if all_files or ext in MEDIA_EXTENSIONS:
            media.append(path)
        elif ext in DOCUMENT_EXTENSIONS:
            documents.append(path)
        else:
            unrecognized.append(path)
    return SourceScan(media=media, documents=documents, unrecognized=unrecognized)


def discover(source: Path, *, all_files: bool = False) -> list[Path]:
    """Return media files under ``source``, sorted, skipping hidden paths."""
    return scan_source(source, all_files=all_files).media


def build_relative(
    label: str,
    captured_at: datetime | None,
    filename: str,
    *,
    rule: str = TIMELINE_RULE,
    scheme: LayoutScheme = DEFAULT_SCHEME,
) -> PurePosixPath:
    """Return the destination-relative path for a non-event file.

    The file is **routed on its rule**, not on its label: the one rule that produces camera
    photos goes to the timeline, every other rule to a labelled side bin. Label routing would
    break ``--by-device``, where the label is the hardware name rather than ``Camera``.

    There is deliberately no template-only path. A scheme is always present -- a library that
    has chosen nothing gets :data:`DEFAULT_SCHEME` -- so routing cannot be silently skipped,
    which is exactly what an optional ``scheme`` parameter allowed.
    """
    return scheme.render(rule, RenderContext(category=label, captured_at=captured_at)) / filename


def build_destination(
    root: Path,
    label: str,
    captured_at: datetime | None,
    filename: str,
    *,
    rule: str,
    scheme: LayoutScheme = DEFAULT_SCHEME,
) -> Path:
    """Absolute local path for a file. Convenience for local previews and tests.

    ``rule`` is required rather than defaulted: routing keys on it, so a caller that omitted it
    would silently get timeline placement for a screenshot or a WhatsApp image.
    """
    return root / build_relative(label, captured_at, filename, rule=rule, scheme=scheme)


def plan(
    files: Sequence[Path],
    metadata: dict[Path, dict[str, Any]],
    rules: tuple[Rule, ...] | None = None,
    *,
    rename: bool = True,
    takeout: dict[Path, TakeoutSidecar] | None = None,
    tz_offset: timedelta | None = None,
    prefer_takeout: bool = False,
    scheme: LayoutScheme = DEFAULT_SCHEME,
) -> list[Decision]:
    """Produce one :class:`Decision` per file. Touches nothing on disk.

    With ``rename`` (the default) the destination copy is named
    ``YYYYMMDD_HHMMSS_<original>`` from the same date evidence used for placement; the
    original source file is never touched. ``takeout`` supplies rescued sidecar dates (Takeout
    ingestion); ``tz_offset``/``prefer_takeout`` control how those interact with EXIF.
    ``template`` is the destination layout (the catalog's, or the default).
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
                suspect_default=is_suspect_default(captured_at, date_source),
                relative=Path(
                    build_relative(
                        category.label,
                        captured_at,
                        new_name,
                        rule=category.rule,
                        scheme=scheme,
                    )
                ),
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
    cache: HashCache | None = None,
) -> list[Resolution]:
    """Hash each file (concurrently) and classify it, updating ``index`` as it goes.

    Hashing is a parallel pass with a size pre-filter (see :mod:`truestill.scan`); the dedup
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
        cache=cache,
    )

    resolutions: list[Resolution] = []
    for decision in decision_list:
        # A cancelled hashing pass returns only what it finished, so a decision may have no
        # entry. Stop cleanly at the first gap and return the partial result: cancelling is a
        # normal, supported outcome, and it must not surface as a KeyError on a file path.
        file_hashes = hashes.get(decision.source)
        if file_hashes is None:
            break
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
    *,
    scheme: LayoutScheme = DEFAULT_SCHEME,
    names: dict[str, str] | None = None,
) -> list[Resolution]:
    """Rewrite named-event members into their event folder (default ``<Label>/YYYY/MM/slug/``).

    ``assignments`` maps a member's source path (``str``) to its event's ``(start, slug)``.
    The event's *start* month is used for the whole event, so a cluster that straddles a
    month boundary lands together under the start month rather than being split. Files not
    in a named event are returned unchanged. ``template`` is the destination layout.
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
        context = RenderContext(
            category=label,
            captured_at=resolution.decision.captured_at,
            event=(start, slug),
            event_name=names.get(str(resolution.decision.source)) if names else None,
        )
        directory = scheme.render(resolution.decision.category.rule, context)
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
    final_relative: str,
    destination: Destination,
    *,
    baker: _MetadataBaker,
    set_timestamps: bool,
) -> str:
    """Take the baked copy, upload it, and return the copy's SHA-256.

    The source is never modified: the metadata write happens on a temporary staged copy, so
    the invariant "originals are untouched" holds even though the uploaded copy now differs
    (by metadata only, losslessly) from the source. Staging and baking belong to
    :class:`_MetadataBaker`, which does both a chunk at a time.
    """
    staged = baker.staged_copy_of(decision)
    if set_timestamps:
        _apply_timestamp(staged, decision.captured_at)
    copy_sha = sha256_file(staged)
    destination.upload(staged, final_relative)
    staged.unlink(missing_ok=True)  # released as soon as it is safe: a chunk is 100 files of disk
    return copy_sha


class MetadataBakeError(OSError):
    """A staged copy's metadata write could not be confirmed, so it was never uploaded.

    An ``OSError`` so it joins the failure path `execute` already has: the file is recorded
    FAILED and named in the report, rather than counted as organized without the metadata it
    was supposed to have gained.
    """

    def __init__(self, source: Path) -> None:
        super().__init__(
            f"could not write rescued metadata into {source.name} "
            "(exiftool did not confirm the write); the original is untouched"
        )


def _bake_queue(
    resolutions: Sequence[Resolution], ingest: IngestContext, *, skip_undated: bool
) -> list[tuple[Decision, MetadataWrite]]:
    """The files `execute` will bake, in the order it will ask for them.

    Mirrors the loop's own skips so the baker never stages a file that is about to be passed
    over -- staging costs a full copy, and paying for one that is discarded is the kind of
    waste that only shows up at Takeout scale.
    """
    queue: list[tuple[Decision, MetadataWrite]] = []
    for resolution in resolutions:
        decision = resolution.decision
        if resolution.exact_duplicate is not None:
            continue
        if skip_undated and decision.captured_at is None:
            continue
        write = ingest.writes.get(str(decision.source))
        if write is not None and write.has_content:
            queue.append((decision, write))
    return queue


class _MetadataBaker:
    """Bakes rescued metadata into staged copies a chunk at a time, in execution order.

    One exiftool process per file costs ~225 ms of startup -- measured -- which is ~6 hours on
    a 100k-file Takeout for work that takes minutes. This stages the next
    :data:`WRITE_BATCH_SIZE` files that need baking and bakes them in a single process, so the
    caller still asks for one file at a time and still gets it in the order it asked.

    Chunked rather than all-at-once because staged copies occupy real disk: the peak footprint
    is one chunk, not one ingest. And staged rather than in-place because **the source is never
    modified** -- which is also why a batch dying part-way through cannot leave a user's file
    half-written. The worst case is a temp file nobody uploads.
    """

    def __init__(self, queue: list[tuple[Decision, MetadataWrite]]) -> None:
        self._queue = queue
        self._next = 0
        self._ready: dict[Path, Path] = {}
        self._failed: set[Path] = set()
        self._tmp: tempfile.TemporaryDirectory[str] | None = None

    def staged_copy_of(self, decision: Decision) -> Path:
        """The baked copy of ``decision.source``, baking the next chunk if it is not ready yet."""
        while (
            decision.source not in self._ready
            and decision.source not in self._failed
            and self._next < len(self._queue)
        ):
            # Normally one chunk; the loop exists so that a caller which skips a queued file
            # advances past it rather than reaching for something that was never staged.
            self._bake_next_chunk()
        if decision.source in self._failed:
            self._failed.discard(decision.source)
            raise MetadataBakeError(decision.source)
        return self._ready.pop(decision.source)

    def _bake_next_chunk(self) -> None:
        # The previous chunk has been fully consumed by the time we get here (the caller walks
        # the same order), so its staging directory can go.
        self.close()
        chunk = self._queue[self._next : self._next + WRITE_BATCH_SIZE]
        self._next += len(chunk)
        if not chunk:
            return
        self._tmp = tempfile.TemporaryDirectory(prefix="truestill-ingest-")
        root = Path(self._tmp.name)

        items: list[tuple[Path, list[str]]] = []
        for index, (decision, write) in enumerate(chunk):
            # Indexed name: two sources in one chunk can share a basename, and one silently
            # overwriting the other would upload the wrong bytes.
            staged = root / f"{index}-{decision.relative.name}"
            shutil.copy2(decision.source, staged)
            self._ready[decision.source] = staged
            args = build_metadata_args(
                taken_at_local=write.taken_at_local,
                gps=write.gps,
                description=write.description,
            )
            if args:
                items.append((staged, args))

        verdicts = write_metadata_batch(items)
        for decision, _ in chunk:
            staged = self._ready[decision.source]
            if not verdicts.get(staged, True):
                # Unconfirmed is failed, never assumed fine: this file is reported as failed
                # rather than uploaded with the metadata it was supposed to have gained.
                self._failed.add(decision.source)
                del self._ready[decision.source]

    def close(self) -> None:
        if self._tmp is not None:
            self._tmp.cleanup()
            self._tmp = None
        self._ready.clear()


@dataclass(frozen=True, slots=True)
class Relocation:
    """Context for moving files in by rename rather than copying them.

    Present whenever the run has move semantics and the destination can adopt files. It is not
    a mode switch: the rename is attempted, and ``require_rename`` only decides what a
    cross-device answer means -- a fallback to the verified copy path (plain ``--move``), or a
    refusal (``--in-place``, where the user has told us they have no room for a copy).

    The journal attaches to the mechanism, not the flag: every rename is recorded, so two users
    who performed the same operation have the same undo rights however they spelled it.
    """

    run_id: str
    source_root: Path
    dest_root: Path
    require_rename: bool = False

    def old_relative(self, source: Path) -> str:
        """``source`` relative to the run's source root, for the journal (remount-safe)."""
        try:
            return source.relative_to(self.source_root).as_posix()
        except ValueError:
            return source.as_posix()  # outside the root (rare); absolute still undoes correctly


def _already_at_target(source: Path, dest_root: Path, relative: str) -> bool:
    """Whether ``source`` is already the file at ``relative`` -- an in-place re-run no-op.

    Must be checked *before* collision resolution: ``_free_relative`` sees the file sitting at
    its own target, calls the path taken, and would suffix the file to ``name_1.ext`` -- a
    re-run quietly renaming an already-organized library. With a live catalog dedup catches
    this first; on a fresh catalog this is the only thing that does.
    """
    try:
        return (dest_root / relative).samefile(source)
    except OSError:
        return False


def _adopt_or_copy(
    source: Path, destination: Destination, final_relative: str, relocation: Relocation | None
) -> bool:
    """Place ``source`` at ``final_relative``. Returns whether it moved by rename.

    The kernel decides, not ``st_dev``: a rename is attempted and its refusal is trusted.
    A cross-device answer either falls back to the copy path or propagates, depending on
    whether the caller promised the user no copy would be made.
    """
    if relocation is None:
        destination.upload(source, final_relative)
        return False
    try:
        destination.adopt(source, final_relative)
    except CrossDeviceError:
        if relocation.require_rename:
            raise
        destination.upload(source, final_relative)
        return False
    return True


def _move_source(
    source: Path, destination: Destination, final_relative: str, copy_sha: str
) -> tuple[ActionStatus, str]:
    """Delete a source only after its destination copy re-verifies. Never deletes on doubt.

    Ordering guarantees no window with zero copies: the copy is already written and recorded;
    here we re-hash it and delete the source only if it matches. Any failure keeps the source.
    """
    try:
        verified = destination.checksum(final_relative) == copy_sha
    except (DestinationError, OSError):
        return ActionStatus.MOVE_KEPT, "could not verify destination copy -- source kept"
    if not verified:
        return ActionStatus.MOVE_KEPT, "destination copy failed re-verification -- source kept"
    try:
        source.unlink()
    except OSError as exc:
        return ActionStatus.MOVE_KEPT, f"copy verified but source delete failed ({exc}) -- kept"
    return ActionStatus.MOVED, "source removed (copy verified)"


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
    skip_undated: bool = False,
    move: bool = False,
    relocation: Relocation | None = None,
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

    ``relocation`` turns the write into a **move by rename** where the filesystem allows it:
    no bytes are rewritten, the operation is atomic per file, and ``copy_sha256`` equals the
    source hash by definition. Every such move is journalled so the run can be reversed with
    ``undo``. A cross-device destination falls back to the verified copy-then-delete path
    unless the caller required the rename, in which case it is reported as a failure rather
    than silently consuming space the user said they did not have.
    """
    resolutions = list(resolutions)
    results: list[ActionResult] = []
    #: Live outcome counts, sent with each tick so a summary fills in as the run happens
    #: rather than appearing all at once at the end.
    tally: Counter[str] = Counter()

    def record(result: ActionResult) -> None:
        """Append an outcome and keep the live tally in step -- one place, so a new status
        can never be added to the loop and quietly go uncounted in the UI."""
        results.append(result)
        tally[status_label(result.status)] += 1

    events = event_ids or {}
    ingest = ingest or IngestContext()
    baker = _MetadataBaker(
        _bake_queue(resolutions, ingest, skip_undated=skip_undated) if apply else []
    )
    albums_by_sha = _aggregate_albums(resolutions, ingest)
    total = len(resolutions)

    for done, resolution in enumerate(resolutions, start=1):
        if cancel is not None and cancel.is_set():
            break
        decision = resolution.decision
        relative = decision.relative.as_posix()
        if progress is not None:
            # Reported before the work, not after: the item named is the one being handled
            # right now, which is what keeps a long single file from looking like a freeze.
            phase = Phase.MOVING if relocation is not None else Phase.ORGANIZING
            progress(Progress(done, total, phase, decision.source.name, dict(tally)))

        if resolution.exact_duplicate is not None:
            match = resolution.exact_duplicate
            detail = f"exact match of {match.matched_path} [{match.origin}]"
            record(ActionResult(resolution, ActionStatus.DUPLICATE, None, detail))
            continue

        if skip_undated and decision.captured_at is None:
            # Undateable and the caller opted out of the Undated/ bucket. Not written, not
            # recorded -- surfaced as its own status so the report can count and name it.
            detail = "no capture date; skipped (--skip-undated)"
            record(ActionResult(resolution, ActionStatus.SKIPPED_UNDATED, None, detail))
            continue

        if not apply:
            record(ActionResult(resolution, ActionStatus.PLANNED, decision.relative))
            continue

        try:
            write = ingest.writes.get(str(decision.source))
            bakes_metadata = write is not None and write.has_content

            # An in-place re-run finds files already at their targets. Checked before collision
            # resolution, which would otherwise read "occupied" and suffix the file.
            if (
                relocation is not None
                and not bakes_metadata
                and _already_at_target(decision.source, relocation.dest_root, relative)
            ):
                detail = "already organized at this path"
                record(
                    ActionResult(resolution, ActionStatus.ALREADY_PLACED, decision.relative, detail)
                )
                continue

            final_relative, renamed = _free_relative(destination, relative)
            # Source hash is the dedup identity; computed now for any unique-size file the
            # scan skipped, since the file is being read for upload anyway.
            source_sha = resolution.hashes.sha256 or sha256_file(decision.source)
            size = _safe_size(decision.source)  # read before any move: the old path then vanishes
            moved_in_place = False

            if bakes_metadata:
                copy_sha = _upload_with_metadata_write(
                    decision,
                    final_relative,
                    destination,
                    baker=baker,
                    set_timestamps=set_timestamps,
                )
            else:
                if set_timestamps:
                    _apply_timestamp(decision.source, decision.captured_at)
                copy_sha = source_sha  # byte-identical either way: a rename rewrites nothing
                moved_in_place = _adopt_or_copy(
                    decision.source, destination, final_relative, relocation
                )

            if catalog is not None:
                album_set = set(albums_by_sha.get(source_sha, set()))
                own_album = ingest.albums.get(str(decision.source))
                if own_album is not None:
                    album_set.add(own_album)
                # After a rename the content *is* the organized copy, so the truthful source
                # path is where it now lives -- `where` and `status` must not cite a ghost.
                # reclaim._is_the_copy_itself is what keeps that honesty from being dangerous.
                recorded_source = (
                    str(relocation.dest_root / final_relative)
                    if moved_in_place and relocation is not None
                    else str(decision.source)
                )
                catalog.record_uploaded(
                    source_path=recorded_source,
                    original_name=decision.source.name,
                    sha256=source_sha,
                    copy_sha256=copy_sha,
                    perceptual=resolution.hashes.perceptual,
                    size=size,
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
            if moved_in_place and relocation is not None:
                # The move already happened, atomically, and rewrote nothing -- there is no
                # copy to verify and no window in which zero copies existed. Journalling it
                # here (after the rename, before anything else) is what makes it undoable.
                status = ActionStatus.MOVED_IN_PLACE
                notes.append("moved on the drive (no bytes copied)")
                if catalog is not None:
                    catalog.record_inplace_move(
                        run_id=relocation.run_id,
                        sha256=source_sha,
                        old_relative=relocation.old_relative(decision.source),
                        new_relative=final_relative,
                    )
            elif move:
                # Copy-only exception: delete the source, but ONLY after the just-written copy
                # re-verifies. A failed verify keeps the source; a crash before this leaves both.
                status, note = _move_source(decision.source, destination, final_relative, copy_sha)
                notes.append(note)
            record(ActionResult(resolution, status, Path(final_relative), "; ".join(notes)))

        except (OSError, DestinationError) as exc:
            record(ActionResult(resolution, ActionStatus.FAILED, None, str(exc)))

    baker.close()
    return results
