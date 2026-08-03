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
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from pathlib import Path, PurePosixPath
from typing import Any

from truestill_core.catalog import Catalog
from truestill_core.categorize import Rule, categorize
from truestill_core.date_provenance import parse_inferred_date_tag
from truestill_core.dates import (
    is_suspect_default,
    parse_exif_datetime,
    resolve_capture_datetime,
)
from truestill_core.dedup import DedupIndex
from truestill_core.destinations.base import CrossDeviceError, Destination, DestinationError
from truestill_core.drive import LEGACY_MARKER_NAMES, MARKER_NAME
from truestill_core.exif import WRITE_BATCH_SIZE, build_metadata_args, write_metadata_batch
from truestill_core.filesystem import DestinationPreflight, sizes_of
from truestill_core.hash_cache import HashCache
from truestill_core.hashing import sha256_file
from truestill_core.layout import (
    DEFAULT_SCHEME,
    EVERYDAY_DAY_THRESHOLD_KEY,
    TIMELINE_RULE,
    TIMELINE_RULES,
    LayoutScheme,
    RenderContext,
    heavy_days_from_captures,
    normalize_everyday_day_threshold,
)
from truestill_core.models import (
    ActionResult,
    ActionStatus,
    CaptureContext,
    CategoryMatch,
    DateSource,
    Decision,
    DuplicateKind,
    Event,
    Resolution,
    RuleName,
    status_label,
)
from truestill_core.naming import dated_filename
from truestill_core.progress import Phase, Progress, ProgressCallback
from truestill_core.run_health import RunHealth, watcher_for
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


#: Plain skipped-report label for exiftool ``*_original`` sidecars (never an extension count).
EXIFTOOL_BACKUP_LABEL = "exiftool backup"

#: Census group for the user's own hidden files. They stay skipped - a dot-file is not a photo -
#: but a skip that is never counted is the `(aac)` defect, and `.picasa.ini` is real user
#: metadata that used to vanish from the report entirely.
HIDDEN_LABEL = "hidden"

#: Census group for Truestill's own drive marker, counted **apart** from the user's hidden
#: files. Folded into their tally it would report a hidden file on every organized drive that
#: the user did not create and cannot act on; dropped, the number would stop matching what
#: ``ls -a`` shows. Snake_case like every other group key - the CLI renders `_` as a space.
TRUESTILL_MARKER_LABEL = "truestill_marker"


@dataclass(frozen=True)
class SourceScan:
    """Everything found under a source, partitioned so nothing is silently dropped.

    ``media`` is what the pipeline organizes; ``documents`` are known non-media files;
    ``exiftool_backups`` are exiftool ``*_original`` sidecars (never primary media, even
    under ``--all-files``); ``unrecognized`` is everything else skipped -- which may
    include video formats truestill does not yet recognize. Skipped lists are surfaced
    in the end-of-run report.

    ``unreadable_dirs`` are folders that could not be **listed**, and they are a different kind
    of fact from every other list here. The others name files truestill decided about; this one
    names a place truestill could not see into, so **the number of files inside is precisely
    what is unknown**. Reporting a count for them would invent the missing number. An unreadable
    *file*, by contrast, stays in ``media`` and surfaces as ``ActionStatus.FAILED`` **on a run**,
    when the copy raises. **Not on a preview**, which attempts no copy: there it yields empty
    hashes and is reported nowhere, and the empty hashes are indistinguishable from the size
    pre-filter's legitimate skip. That gap is `BACKLOG.md` ``(aac)``; this docstring used to
    say "already handled downstream" without naming the path, which read as though it were
    closed.
    """

    media: list[Path]
    documents: list[Path]
    unrecognized: list[Path]
    exiftool_backups: list[Path] = field(default_factory=list)
    unreadable_dirs: list[Path] = field(default_factory=list)
    #: The user's own hidden files - skipped, and now counted rather than dropped.
    hidden: list[Path] = field(default_factory=list)
    #: Truestill's own marker files, kept apart from ``hidden`` so a count of the user's
    #: hidden files never includes one of ours.
    markers: list[Path] = field(default_factory=list)
    #: Hidden folders, **named without a count**. The walk never descends into one, so the
    #: number of files inside is precisely what is unknown - the same rule ``unreadable_dirs``
    #: follows above, and for the same reason: a number here would be invented.
    hidden_dirs: list[Path] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class SourceInventory:
    """Cheap walk + size summary for progressive disclosure (backlog tt).

    No exiftool, no hashing. Complexity: **O(n)** files (one directory walk, one ``stat``
    per media file for ``total_bytes``).
    """

    files: int
    photos: int
    videos: int
    audio: int
    by_format: dict[str, dict[str, int]]
    total_bytes: int
    skipped: dict[str, dict[str, int]]
    #: Folders that could not be **listed**. `scan_source` already finds these and this summary
    #: used to discard them, which made "no files found" and "that folder could not be opened"
    #: the same answer -- `(aac)`'s defect on a cheaper surface. Carried as paths and never as a
    #: count: the number of files inside is exactly what is unknown, so any figure is invented.
    unreadable_dirs: list[Path] = field(default_factory=list)
    #: Hidden folders the walk deliberately did not enter. Same shape and same reason as
    #: ``unreadable_dirs``: a place, never a count. A user with an album in one used to get no
    #: acknowledgement at all that anything had been passed over.
    hidden_dirs: list[Path] = field(default_factory=list)


def is_exiftool_original_backup(path: Path | str) -> bool:
    """True when the name is an exiftool sidecar ``{live_filename}_original``.

    Exiftool appends ``_original`` to the *full* filename (``holiday.jpg_original``,
    ``clip.mp4_original``, ``notes.txt_original``) - any extension, not only JPEG.
    A legitimate user file ``vacation_original.jpg`` ends with ``.jpg`` and is **not**
    a backup: the stem may contain ``_original``, but the name does not *end* with
    ``_original`` after the extension.
    """
    name = Path(path).name
    if not name.endswith("_original"):
        return False
    live = name[: -len("_original")]
    if not live:
        return False
    # The live name must look like a real file (has a non-empty, non-dot-only suffix).
    suffix = Path(live).suffix
    return len(suffix) > 1


def scan_source(source: Path, *, all_files: bool = False) -> SourceScan:
    """Walk ``source`` once, partitioning files into media / documents / unrecognized.

    Hidden paths are skipped. Exiftool ``*_original`` sidecars are refused as primary
    media at this door - including under ``--all-files`` - so every caller inherits the
    refusal. With ``all_files`` every *other* file is treated as media (the
    ``--all-files`` escape hatch).
    """
    media: list[Path] = []
    documents: list[Path] = []
    unrecognized: list[Path] = []
    exiftool_backups: list[Path] = []
    unreadable_dirs: list[Path] = []
    hidden: list[Path] = []
    markers: list[Path] = []
    hidden_dirs: list[Path] = []

    def _note_unreadable(error: OSError) -> None:
        """A folder that could not be listed. **Never raises** - one locked folder must not
        cost the whole run, the same rule every other partial failure here follows."""
        if error.filename is not None:
            unreadable_dirs.append(Path(error.filename))

    # `Path.walk` rather than `rglob` because **rglob swallows the permission error by design**:
    # an unlisted subtree simply did not appear, so files that are really there were never seen,
    # counted or mentioned. `walk` hands them to `on_error` instead. (§4 already prefers `walk`
    # for dir-shaped traversal.) Hidden directories are pruned in place so the walk does not
    # descend into them at all, which is also why an unreadable *hidden* folder is not reported:
    # it was never in scope.
    #
    # **Complexity: O(entries)** - one pass, unchanged - plus the same terminal sort `rglob`
    # already paid for. `walk` yields per directory, so the sort is what keeps the global
    # ordering the reports and golden tests depend on.
    for dirpath, dirnames, filenames in source.walk(on_error=_note_unreadable):
        kept: list[str] = []
        for name in dirnames:
            if name.startswith("."):
                # Named, then pruned. The walk still does not go in - reporting the folder is
                # free, counting what is inside would mean descending `.git` on every scan -
                # so this records a place that was skipped, never a number for it.
                hidden_dirs.append(dirpath / name)
            else:
                kept.append(name)
        dirnames[:] = kept
        for filename in filenames:
            if filename.startswith("."):
                # Ours or theirs: the distinction is the whole reason both lists exist.
                target = markers if filename in _MARKER_NAMES else hidden
                target.append(dirpath / filename)
                continue
            path = dirpath / filename
            if not path.is_file():
                continue
            if is_exiftool_original_backup(path):
                exiftool_backups.append(path)
                continue
            ext = path.suffix.lower()
            if all_files or ext in MEDIA_EXTENSIONS:
                media.append(path)
            elif ext in DOCUMENT_EXTENSIONS:
                documents.append(path)
            else:
                unrecognized.append(path)
    return SourceScan(
        media=sorted(media),
        documents=sorted(documents),
        unrecognized=sorted(unrecognized),
        exiftool_backups=sorted(exiftool_backups),
        unreadable_dirs=sorted(unreadable_dirs),
        hidden=sorted(hidden),
        markers=sorted(markers),
        hidden_dirs=sorted(hidden_dirs),
    )


def discover(source: Path, *, all_files: bool = False) -> list[Path]:
    """Return media files under ``source``, sorted, skipping hidden paths."""
    return scan_source(source, all_files=all_files).media


def _bytes_of(paths: Sequence[Path]) -> int:
    """Sum ``st_size`` for ``paths``. Unreadable entries contribute 0."""
    total = 0
    for path in paths:
        try:
            total += path.stat().st_size
        except OSError:
            continue
    return total


#: Truestill's own hidden filenames, **imported rather than retyped**. `drive` owns them, and a
#: second hand-kept copy is the failure this repo has now hit twice - `test_layout_scheme`'s
#: `ALL_RULES` and `check_product_name`'s `SUBCOMMANDS` both silently stopped covering the thing
#: that had changed.
_MARKER_NAMES: frozenset[str] = frozenset({MARKER_NAME, *LEGACY_MARKER_NAMES})


def skipped_extension_counts(scan: SourceScan) -> dict[str, dict[str, int]]:
    """Per-extension counts for every group of files a scan did **not** treat as media.

    **One home, called by both surfaces.** The app kept a verbatim copy of this function until
    2026-08-04; adding a group to one of them would have left the other silently short, which is
    the same drift `ALL_RULES` and `SUBCOMMANDS` produced. Two copies of a vocabulary is one
    copy too many.

    A group with nothing in it is **absent**, not zero: never-silent is about what happened, not
    about what did not, and an ordinary folder should not sprout a row explaining that it has no
    hidden files.
    """
    by_extension = {
        "documents": scan.documents,
        "unrecognized": scan.unrecognized,
    }
    groups = {
        name: dict(Counter(p.suffix.lower() or "(no ext)" for p in paths))
        for name, paths in by_extension.items()
    }
    # **Hidden files are counted by NAME, not by extension**, and the difference is the whole
    # value of the row. `.DS_Store` has no suffix at all by `Path`'s rules, so an extension
    # census reports `(no ext) x1` and teaches nobody anything; the names are what a user
    # recognises, and `.picasa.ini` being their own Picasa metadata is the case that matters.
    # The `._IMG_*` AppleDouble family is the one that could sprawl, and the census renderer
    # already bounds by count *and* width and says how many of the hidden ones were seen once.
    groups[HIDDEN_LABEL] = dict(Counter(p.name for p in scan.hidden))
    # These two are counted by NAME rather than by extension: "exiftool backup" and the marker
    # are what the file *is*, and `.json x1` would name the format instead of the fact.
    # The GROUP key is `exiftool_backups`; `EXIFTOOL_BACKUP_LABEL` is the row inside it. They
    # are different strings on purpose - the group name is a payload key the app and its
    # browser tests read, the label is the plain wording a person sees - and collapsing them
    # renamed the key under three call sites before the existing tests caught it.
    groups["exiftool_backups"] = (
        {EXIFTOOL_BACKUP_LABEL: len(scan.exiftool_backups)} if scan.exiftool_backups else {}
    )
    groups[TRUESTILL_MARKER_LABEL] = dict(Counter(p.name for p in scan.markers))
    return groups


#: Kept as the private name three call sites already import.
_skipped_extension_counts = skipped_extension_counts


def _media_format_breakdown(
    paths: Sequence[Path],
) -> tuple[dict[str, int], dict[str, dict[str, int]]]:
    """Photo / video / audio counts and per-extension tallies from path suffixes only."""
    counts = {"photos": 0, "videos": 0, "audio": 0}
    plural = {"photo": "photos", "video": "videos", "audio": "audio"}
    fmt: dict[str, Counter[str]] = {
        "photos": Counter(),
        "videos": Counter(),
        "audio": Counter(),
    }
    for path in paths:
        kind = media_kind(path.name)
        if kind is None:
            continue
        group = plural[kind]
        counts[group] += 1
        fmt[group][path.suffix.lower().lstrip(".") or "(no ext)"] += 1
    return counts, {g: dict(c.most_common()) for g, c in fmt.items()}


def inventory_source(source: Path, *, all_files: bool = False) -> SourceInventory:
    """Return counts by type/extension and total media bytes, with no metadata or hashing.

    Size comes from a **dedicated ``stat`` pass over media** after :func:`scan_source`, not
    from surfacing ``scan._sizes`` inside ``compute_hashes``: inventory must stay off the
    expensive path, and ``scan_source`` stays a partition-only walk reused by discover /
    organize. Profile evidence (``docs/preview-performance-profile.md``): that ``stat`` pass
    is ~0.3 s on a cloud FUSE mount for 2,064 files against ~231 s for exiftool - near-free
    relative to the full preview.
    """
    scan = scan_source(source, all_files=all_files)
    return inventory_from_scan(scan, sizes_of_media(scan.media))


def sizes_of_media(paths: Sequence[Path]) -> dict[Path, int]:
    """One ``stat`` per media file. Unreadable entries are omitted rather than raising."""
    found: dict[Path, int] = {}
    for path in paths:
        try:
            found[path] = path.stat().st_size
        except OSError:
            continue
    return found


def inventory_from_scan(scan: SourceScan, sizes: Mapping[Path, int]) -> SourceInventory:
    """The census, from a walk and a size map the caller already has.

    Split out so a caller that needs the **per-file** sizes -- Analyze, to forecast what the
    duplicate check will read -- does not pay for a second ``stat`` pass over the whole source
    to get them. `inventory_source` remains the one-call form.
    """
    counts, by_format = _media_format_breakdown(scan.media)
    return SourceInventory(
        files=len(scan.media),
        photos=counts["photos"],
        videos=counts["videos"],
        audio=counts["audio"],
        by_format=by_format,
        total_bytes=sum(sizes.values()),
        skipped=skipped_extension_counts(scan),
        unreadable_dirs=list(scan.unreadable_dirs),
        hidden_dirs=list(scan.hidden_dirs),
    )


def build_relative(
    label: str,
    captured_at: datetime | None,
    filename: str,
    *,
    rule: RuleName | str = TIMELINE_RULE,
    scheme: LayoutScheme = DEFAULT_SCHEME,
    heavy_day: bool = False,
) -> PurePosixPath:
    """Return the destination-relative path for a non-event file.

    The file is **routed on its rule**, not on its label: the one rule that produces camera
    photos goes to the timeline, every other rule to a labelled side bin. Label routing would
    break ``--by-device``, where the label is the hardware name rather than ``Camera``.

    ``heavy_day`` is the caller-computed Everyday density flag
    (`docs/adaptive-day-folder-research.md`); this function does not count.

    There is deliberately no template-only path. A scheme is always present -- a library that
    has chosen nothing gets :data:`DEFAULT_SCHEME` -- so routing cannot be silently skipped,
    which is exactly what an optional ``scheme`` parameter allowed.
    """
    return (
        scheme.render(
            rule,
            RenderContext(category=label, captured_at=captured_at, heavy_day=heavy_day),
        )
        / filename
    )


def build_destination(
    root: Path,
    label: str,
    captured_at: datetime | None,
    filename: str,
    *,
    rule: str,
    scheme: LayoutScheme = DEFAULT_SCHEME,
    heavy_day: bool = False,
) -> Path:
    """Absolute local path for a file. Convenience for local previews and tests.

    ``rule`` is required rather than defaulted: routing keys on it, so a caller that omitted it
    would silently get timeline placement for a screenshot or a WhatsApp image.
    """
    return root / build_relative(
        label, captured_at, filename, rule=rule, scheme=scheme, heavy_day=heavy_day
    )


def heavy_days_for_organize(
    catalog: Catalog,
    files: Sequence[Path],
    metadata: dict[Path, dict[str, Any]],
    rules: tuple[Rule, ...] | None = None,
    *,
    takeout: dict[Path, TakeoutSidecar] | None = None,
    tz_offset: timedelta | None = None,
    prefer_takeout: bool = False,
) -> frozenset[str]:
    """ISO days over the Everyday threshold for this organize run (catalog and source).

    One categorize/date pass over ``files`` plus the catalog's unevented Camera captures, then a
    single :func:`count_capture_days` - not a per-file recount. Threshold comes from the catalog
    setting (default 40).
    """
    takeout = takeout or {}
    threshold = normalize_everyday_day_threshold(catalog.get_setting(EVERYDAY_DAY_THRESHOLD_KEY))
    incoming: list[datetime | None] = []
    for path in files:
        meta = metadata.get(path, {})
        category = categorize(path, meta, rules)
        if category.rule not in TIMELINE_RULES:
            continue
        captured_at, _, _ = resolve_capture_datetime(
            path,
            meta,
            takeout=takeout.get(path),
            tz_offset=tz_offset,
            prefer_takeout=prefer_takeout,
        )
        incoming.append(captured_at)
    return heavy_days_from_captures(
        catalog.unevented_timeline_captured_ats(),
        incoming,
        threshold=threshold,
    )


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
    heavy_days: frozenset[str] | None = None,
) -> list[Decision]:
    """Produce one :class:`Decision` per file. Touches nothing on disk.

    With ``rename`` (the default) the destination copy is named
    ``YYYYMMDD_HHMMSS_<original>`` from the same date evidence used for placement; the
    original source file is never touched. ``takeout`` supplies rescued sidecar dates (Takeout
    ingestion); ``tz_offset``/``prefer_takeout`` control how those interact with EXIF.
    ``heavy_days`` is the ISO-day set already computed by the caller (catalog and this run);
    event membership is applied later and wins over a heavy-day flag at render time.
    """
    takeout = takeout or {}
    heavy = heavy_days or frozenset()
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
        inferred_from = None
        if date_source is DateSource.INFERRED_LOCAL and date_tag:
            parsed = parse_inferred_date_tag(date_tag)
            if parsed is not None:
                inferred_from = parse_exif_datetime(meta.get(parsed.container_tag))
        new_name = dated_filename(
            path.name,
            captured_at,
            time_known=date_source in (DateSource.EXIF, DateSource.INFERRED_LOCAL),
            enabled=rename,
        )
        day_key = captured_at.date().isoformat() if captured_at is not None else None
        heavy_day = category.rule in TIMELINE_RULES and day_key is not None and day_key in heavy
        decisions.append(
            Decision(
                source=path,
                category=category,
                captured_at=captured_at,
                date_source=date_source,
                date_tag=date_tag,
                suspect_default=is_suspect_default(captured_at, date_source),
                inferred_from=inferred_from,
                capture=CaptureContext.from_metadata(meta),
                relative=Path(
                    build_relative(
                        category.label,
                        captured_at,
                        new_name,
                        rule=category.rule,
                        scheme=scheme,
                        heavy_day=heavy_day,
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
    perceptual: bool = True,
) -> list[Resolution]:
    """Hash each file (concurrently) and classify it, updating ``index`` as it goes.

    ``perceptual=False`` is Analyze's tier 2a: exact duplicates only, reading just the
    size-colliding minority instead of decoding every image. It requires a read-only cache -
    `compute_hashes` refuses the writable pairing, because a partially-hashed row cannot be
    told from a genuine one later.

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
        perceptual=perceptual,
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
    events: dict[str, Event],
    *,
    scheme: LayoutScheme = DEFAULT_SCHEME,
) -> list[Resolution]:
    """Rewrite named-event members through the scheme's event placement.

    With the default scheme and a recorded human name, the folder is
    ``YYYY/YYYY-MM/YYYY-MM-DD - Name/``. With no name (or an unusable one), the slug form
    ``YYYYMMDD_<slug>/`` - identical to the pre-``Event`` optional-names path.

    ``events`` maps a member's source path (``str``) to its :class:`Event`. The event's
    *start* month is used for the whole event, so a cluster that straddles a month boundary
    lands together under the start month rather than being split. Files not in a named event
    are returned unchanged.
    """
    if not events:
        return list(resolutions)

    updated: list[Resolution] = []
    for resolution in resolutions:
        event = events.get(str(resolution.decision.source))
        if event is None:
            updated.append(resolution)
            continue
        label = resolution.decision.category.label
        filename = resolution.decision.relative.name
        context = RenderContext(
            category=label,
            captured_at=resolution.decision.captured_at,
            event=(event.start, event.slug),
            event_name=event.name,
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
    """Set a staged or adopted local file's mtime to the capture date.

    A pure copy is stamped through :meth:`Destination.set_timestamp` after upload. This helper
    is only for a temporary metadata-bake copy or a file being adopted/relocated, where ownership
    is transferring to the destination.
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


def _upload_copy(
    source: Path,
    destination: Destination,
    final_relative: str,
    captured_at: datetime | None,
    *,
    set_timestamps: bool,
) -> None:
    """Upload a pure copy, stamping the destination. **The source is not written to at all.**

    This used to snapshot the source's atime and mtime and put both back afterwards, "so a copy
    does not invalidate the path+size+mtime hash-cache key". That was wrong in both directions,
    and both were measured:

    * Reading advances **atime** and never **mtime** (ext4/relatime: atime moved, mtime did
      not), so the restore fired on essentially every file of every run - and **atime is not in
      the cache key**. `hash_cache` keys on path + size + ``mtime_ns``. The write could not
      protect the thing its own comment named.
    * When **mtime** does differ, nothing here caused it: `copy2` reads the source and writes
      the destination. It means the file changed underneath the run, and stamping the old value
      back would make a **stale** cache row look valid - the next run would serve a hash for
      content that no longer matches. In the only case where the condition could honestly be
      true, the restore was actively harmful.

    The source is usually a camera card, and FAT32/exFAT have no journal: every metadata write
    to one is an unjournalled directory-entry update. Once per file per run, for no benefit, is
    not a tidy no-op.
    """
    destination.upload(source, final_relative)
    if set_timestamps and captured_at is not None:
        destination.set_timestamp(final_relative, captured_at)


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


def _write_organized_bytes(
    decision: Decision,
    *,
    destination: Destination,
    final_relative: str,
    source_sha: str,
    baker: _MetadataBaker,
    set_timestamps: bool,
    bakes_metadata: bool,
    relocation: Relocation | None,
) -> tuple[str, bool]:
    """Bake (if needed) and write bytes to ``final_relative``.

    Returns ``(copy_sha, moved_in_place)``. Order is intentional: bake/write happen before any
    catalog or journal mutation.
    """
    if bakes_metadata:
        copy_sha = _upload_with_metadata_write(
            decision,
            final_relative,
            destination,
            baker=baker,
            set_timestamps=set_timestamps,
        )
        return copy_sha, False
    if relocation is None:
        _upload_copy(
            decision.source,
            destination,
            final_relative,
            decision.captured_at,
            set_timestamps=set_timestamps,
        )
        return source_sha, False
    # Relocation transfers ownership of this inode. Stamp it before the attempted
    # adopt so a rename and the verified cross-device fallback preserve the date.
    if set_timestamps:
        _apply_timestamp(decision.source, decision.captured_at)
    # byte-identical either way: a rename rewrites nothing
    moved_in_place = _adopt_or_copy(decision.source, destination, final_relative, relocation)
    return source_sha, moved_in_place


def _record_organized_file(
    resolution: Resolution,
    *,
    catalog: Catalog,
    ingest: IngestContext,
    albums_by_sha: dict[str, set[str]],
    by_source: dict[str, Event],
    source_sha: str,
    copy_sha: str,
    size: int | None,
    final_relative: str,
    moved_in_place: bool,
    relocation: Relocation | None,
    drive_uuid: str | None,
) -> None:
    """Persist the organized copy in the catalog. Runs only after a successful write."""
    decision = resolution.decision
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
        event_id=(
            by_source[str(decision.source)].id if str(decision.source) in by_source else None
        ),
        albums=sorted(album_set),
        drive_uuid=drive_uuid,
        # The resolver's own verdict, not a second opinion computed here: a re-derivation at
        # write time could disagree with the placement this same decision produced. The capture
        # context rides the same way, and for the same reason - the file is not re-opened here.
        date_source=decision.date_source.value,
        date_tag=decision.date_tag,
        capture=decision.capture,
    )


def _journal_or_delete_source(
    decision: Decision,
    *,
    destination: Destination,
    catalog: Catalog | None,
    relocation: Relocation | None,
    move: bool,
    source_sha: str,
    copy_sha: str,
    final_relative: str,
    moved_in_place: bool,
    renamed: bool,
    resolution: Resolution,
) -> ActionResult:
    """Journal an in-place rename, or verify-and-delete under ``--move``, then build the result.

    Journal / delete run only after catalog recording. Never reorder above a write or catalog
    upsert.
    """
    status = ActionStatus.RENAMED if renamed else ActionStatus.UPLOADED
    notes: list[str] = []
    if renamed:
        notes.append("suffixed to avoid an unrelated name collision")
    if resolution.near_duplicate is not None:
        near = resolution.near_duplicate
        distance = f", distance={near.distance}" if near.distance is not None else ""
        notes.append(f"near-duplicate of {near.matched_path} [{near.origin}{distance}]")
    if moved_in_place and relocation is not None:
        # The move already happened and rewrote nothing -- there is no copy to verify and no
        # window in which another process could observe zero copies. Journalling it here (after
        # the rename, before anything else) is what makes it undoable, and on a filesystem that
        # journals nothing (FAT32, exFAT) that journal is also the only thing standing between a
        # power cut and an orphaned entry -- see `LocalDestination.adopt`.
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
    return ActionResult(resolution, status, Path(final_relative), "; ".join(notes))


def _execute_one_write(
    resolution: Resolution,
    *,
    destination: Destination,
    catalog: Catalog | None,
    set_timestamps: bool,
    move: bool,
    relocation: Relocation | None,
    by_source: dict[str, Event],
    ingest: IngestContext,
    albums_by_sha: dict[str, set[str]],
    baker: _MetadataBaker,
    drive_uuid: str | None,
) -> ActionResult:
    """One file's write path: already-placed check, then bake/write -> catalog -> journal/delete.

    Raises ``OSError`` / ``DestinationError`` for the caller's existing failure boundary.
    """
    decision = resolution.decision
    relative = decision.relative.as_posix()
    write = ingest.writes.get(str(decision.source))
    bakes_metadata = write is not None and write.has_content

    # An in-place re-run finds files already at their targets. Checked before collision
    # resolution, which would otherwise read "occupied" and suffix the file.
    if (
        relocation is not None
        and not bakes_metadata
        and _already_at_target(decision.source, relocation.dest_root, relative)
    ):
        return ActionResult(
            resolution,
            ActionStatus.ALREADY_PLACED,
            decision.relative,
            "already organized at this path",
        )

    final_relative, renamed = _free_relative(destination, relative)
    # Source hash is the dedup identity; computed now for any unique-size file the
    # scan skipped, since the file is being read for upload anyway.
    source_sha = resolution.hashes.sha256 or sha256_file(decision.source)
    size = _safe_size(decision.source)  # read before any move: the old path then vanishes

    copy_sha, moved_in_place = _write_organized_bytes(
        decision,
        destination=destination,
        final_relative=final_relative,
        source_sha=source_sha,
        baker=baker,
        set_timestamps=set_timestamps,
        bakes_metadata=bakes_metadata,
        relocation=relocation,
    )

    if catalog is not None:
        _record_organized_file(
            resolution,
            catalog=catalog,
            ingest=ingest,
            albums_by_sha=albums_by_sha,
            by_source=by_source,
            source_sha=source_sha,
            copy_sha=copy_sha,
            size=size,
            final_relative=final_relative,
            moved_in_place=moved_in_place,
            relocation=relocation,
            drive_uuid=drive_uuid,
        )

    return _journal_or_delete_source(
        decision,
        destination=destination,
        catalog=catalog,
        relocation=relocation,
        move=move,
        source_sha=source_sha,
        copy_sha=copy_sha,
        final_relative=final_relative,
        moved_in_place=moved_in_place,
        renamed=renamed,
        resolution=resolution,
    )


def preflight_for_run(
    resolutions: Sequence[Resolution],
    destination: Destination,
    *,
    skip_undated: bool = False,
) -> DestinationPreflight:
    """Whether ``destination`` can physically hold what this run would write.

    Only files that would actually be **written** are counted: an exact duplicate is never
    copied, and refusing a run over a duplicate's size would block work that would have
    succeeded. Complexity: one ``stat`` per candidate, against a hashing pass that has already
    read every one of them end to end.

    Exposed rather than kept private because a *preview* has to say the same thing without
    raising: a plan that reads as clean and then fails on ``--apply`` moves the discovery to
    after the user has committed. One function decides which files count; the report and the
    refusal are two readings of its answer, not two implementations of it.
    """
    return destination.preflight(sizes_of(write_candidates(resolutions, skip_undated=skip_undated)))


def write_candidates(resolutions: Sequence[Resolution], *, skip_undated: bool) -> list[Path]:
    """The sources a run would actually write. One predicate, because three places ask.

    A preview sizes them, the refusal sizes them, and a run in progress needs to know how big
    the largest one still ahead of it is. Three copies of "would this be written" is how the
    preflight and the run come to disagree about what the run is.
    """
    return [
        r.decision.source
        for r in resolutions
        if r.should_upload and not (skip_undated and r.decision.captured_at is None)
    ]


def _refuse_impossible_destination(
    resolutions: Sequence[Resolution],
    destination: Destination,
    *,
    skip_undated: bool,
) -> dict[Path, int]:
    """Refuse, before the first byte, work this destination cannot physically hold.

    **Returns the sizes it gathered**, because it has already paid for them: one ``stat`` per
    candidate, which on a FUSE-mounted library is ~600 us each and the entire tier-0 budget
    again if a second pass asks for the same numbers (`PERFORMANCE.md` §3.1). The run watcher
    needs exactly this map and must not go and get its own.

    **Why here and not in the callers.** The CLI and the app both call :func:`execute`, so a
    check placed in either is a check the other silently lacks -- which is exactly how backup's
    free-space check ended up app-only, leaving the CLI to fill a drive and fail at the end.
    One home means a third surface cannot be added without it.

    **Why refuse rather than skip.** Skipping the files that will not fit produces a library
    quietly missing the 4K footage the user cared most about, reported as a success. Naming them
    and stopping leaves the decision where it belongs.
    """
    sized = sizes_of(write_candidates(resolutions, skip_undated=skip_undated))
    preflight = destination.preflight(sized)
    if not preflight.may_proceed:
        message = f"{destination.describe()} cannot hold this run. {preflight.detail()}"
        raise DestinationError(message)
    return dict(sized)


#: Statuses whose file really had its bytes copied. `MOVED_IN_PLACE` and `ALREADY_PLACED` are
#: deliberately absent: a rename writes nothing, and counting one would put a number in the
#: disk-filling message that no disk ever saw.
_BYTES_WRITTEN_STATUSES = frozenset(
    {
        ActionStatus.UPLOADED,
        ActionStatus.RENAMED,
        ActionStatus.MOVED,
        ActionStatus.MOVE_KEPT,
    }
)


@dataclass(slots=True)
class _GroundWatch:
    """The watcher, the sizes it needs, and what the run has written so far.

    One object rather than three locals in `execute`, so the three cannot be built in the wrong
    order or one of them left unbound on a path that later reads it - `sizes` was exactly that,
    assigned only under ``apply`` and read from inside the write branch.
    """

    health: RunHealth | None
    #: For each position, the biggest file at or after it this run would write.
    largest_ahead: list[int]
    sizes: dict[Path, int]
    written: int = 0


def _ground_watch(
    resolutions: Sequence[Resolution],
    destination: Destination,
    catalog: Catalog | None,
    *,
    apply: bool,
    skip_undated: bool,
) -> _GroundWatch:
    """Refuse an impossible destination, then set up the watch over what remains.

    The refusal and the watch share one ``stat`` pass, which is the reason they are built
    together: the numbers are the same numbers, and paying for them twice on a FUSE library
    costs the whole tier-0 budget again (`PERFORMANCE.md` §3.1).
    """
    if not apply:
        return _GroundWatch(health=None, largest_ahead=[], sizes={})
    sizes = _refuse_impossible_destination(resolutions, destination, skip_undated=skip_undated)
    health = watcher_for(destination.local_root(), catalog.path if catalog else None)
    ahead = _largest_still_ahead(resolutions, sizes) if health is not None else []
    return _GroundWatch(health=health, largest_ahead=ahead, sizes=sizes)


def _health_stop(
    health: RunHealth, resolution: Resolution, *, ahead: int, written: int
) -> ActionResult | None:
    """The run's verdict on the ground beneath it, as a result to record, or ``None``.

    **Asked after the skips and immediately before the write.** A duplicate and an undated skip
    put nothing on the drive, so stopping a run whose remaining work writes nothing would be
    the cry-wolf this guard is most at risk of.

    **Reported as `FAILED` rather than as a new `ActionStatus`.** Nothing type-checks
    exhaustiveness over that enum - there is no ``assert_never`` for it - so a new member is a
    set of call sites that must be found by hand, in `_STATUS_LABELS`, in both surfaces'
    counters and in the organized-status sets. `FAILED` already carries exactly what is true
    here: this file is not in your library, and this is the message. Both surfaces already show
    that message prominently and exit non-zero on it.

    **The honest limit:** the files after this one are unattempted and therefore absent from
    the results, which is the shape `cancel` has always had. The wording carries the remedy -
    the run is resumable and says so.
    """
    verdict = health.check(largest_remaining=ahead, written_bytes=written)
    if verdict.ok:
        return None
    return ActionResult(resolution, ActionStatus.FAILED, None, verdict.detail)


def _largest_still_ahead(resolutions: Sequence[Resolution], sizes: Mapping[Path, int]) -> list[int]:
    """For each position, the biggest file at or after it that this run would write.

    A suffix maximum, computed once in one backward pass, because the alternative is a scan of
    the remainder per file - quadratic on the libraries this guard exists for. ``sizes`` holds
    only write candidates, so anything skipped contributes 0 and falls out for free.
    """
    suffix = [0] * (len(resolutions) + 1)
    for index in range(len(resolutions) - 1, -1, -1):
        suffix[index] = max(suffix[index + 1], sizes.get(resolutions[index].decision.source, 0))
    return suffix


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
    events: dict[str, Event] | None = None,
    ingest: IngestContext | None = None,
    drive_uuid: str | None = None,
    progress: ProgressCallback | None = None,
    cancel: threading.Event | None = None,
) -> list[ActionResult]:
    """Upload genuinely-new files; skip duplicates. ``apply=False`` reports only.

    ``events`` maps a source path to its :class:`Event` (catalog id travels on the object).
    ``ingest`` (Takeout only) requests baking rescued metadata into copies and records album
    membership; when absent, the copy is byte-identical to the source and ``copy_sha256`` equals
    the source hash. ``drive_uuid``, when the destination is an identified drive, records each
    copy's location in the catalog. ``progress`` is called ``(done, total)`` per file; ``cancel``
    stops the run early (already-uploaded files stay -- the run is resumable).

    ``relocation`` turns the write into a **move by rename** where the filesystem allows it:
    no bytes are rewritten, the operation is atomic per file against concurrent observers, and
    ``copy_sha256`` equals the source hash by definition. Atomicity across a *power cut* needs a
    journalling filesystem; on FAT32/exFAT the ``inplace_moves`` journal is what makes such a run
    recoverable, not the rename (see `LocalDestination.adopt`). Every such move is journalled so the run can be reversed with
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

    ground = _ground_watch(
        resolutions, destination, catalog, apply=apply, skip_undated=skip_undated
    )

    by_source = events or {}
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

        if ground.health is not None:
            stop = _health_stop(
                ground.health,
                resolution,
                ahead=ground.largest_ahead[done - 1],
                written=ground.written,
            )
            if stop is not None:
                record(stop)
                break

        try:
            record(
                _execute_one_write(
                    resolution,
                    destination=destination,
                    catalog=catalog,
                    set_timestamps=set_timestamps,
                    move=move,
                    relocation=relocation,
                    by_source=by_source,
                    ingest=ingest,
                    albums_by_sha=albums_by_sha,
                    baker=baker,
                    drive_uuid=drive_uuid,
                )
            )
            if results[-1].status in _BYTES_WRITTEN_STATUSES:
                ground.written += ground.sizes.get(decision.source, 0)
        except (OSError, DestinationError) as exc:
            record(ActionResult(resolution, ActionStatus.FAILED, None, str(exc)))

    baker.close()
    return results
