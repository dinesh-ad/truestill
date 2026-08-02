"""Core data types shared across the organizer.

Category labels are **open-ended strings, not an enum**. The set of folders that a run
produces is discovered from the files themselves: a new messenger, editing app or
camera brand appearing in the library creates its own folder without a code change.
Files whose origin cannot be proven from evidence fall through to :data:`SAVED_LABEL`.

The organizer never mutates its source tree. Every run produces a list of
:class:`Decision` objects first; execution is a separate, explicitly opted-in step.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import NamedTuple

from truestill_core.date_provenance import format_offset, parse_offset

#: Folder used when a file carries no usable date evidence at all. Files land here
#: rather than being guessed into a year, so an undated file is always visible as such.
UNDATED_DIRNAME = "Undated"

#: Label for files whose origin cannot be proven -- metadata-stripped social/web saves and
#: anything else with no identifying evidence. Named "Saved" rather than "Unsorted": to a
#: normal user "Unsorted" reads as a failure, whereas these files are genuinely just images
#: saved from apps or the web, whose origin is unknowable by design (platforms strip EXIF).
SAVED_LABEL = "Saved"


class Confidence(StrEnum):
    """How strong the evidence behind a category label is.

    ``HIGH``   embedded metadata said so outright (e.g. a screenshot marker tag).
    ``MEDIUM`` a filename convention matched, or device metadata was present.
    ``LOW``    the label was derived from a free-text field and may be noisy.
    """

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class RuleName(StrEnum):
    """Which categorization rule produced a :class:`CategoryMatch`.

    The seven members are the full set the router knows. Values are the historical string
    tokens (unchanged) so comparisons with those literals stay true. This is **not** a
    catalog column - it is in-memory evidence for the current run / re-derive pass only.
    """

    SCREENSHOT_METADATA = "screenshot_metadata"
    SCREENSHOT_NAME = "screenshot_name"
    FILENAME_CONVENTION = "filename_convention"
    SOFTWARE = "software"
    DEVICE = "device"
    SAVED_HEURISTIC = "saved_heuristic"
    FALLBACK = "fallback"


class DateSource(StrEnum):
    """Where a file's capture date was recovered from, best to worst.

    ``HUMAN_CONFIRMED`` is above all of them and is never machine-derived; see
    :meth:`truestill_core.catalog.Catalog.confirm_date`.
    ``EXIF`` and ``TAKEOUT`` (Google's ``photoTakenTime``) are trusted. ``TAKEOUT_UPLOAD``
    (Google's ``creationTime``, i.e. when it was uploaded) and ``FILENAME`` are approximate
    and flagged for review. ``NONE`` means no date evidence -> ``Undated/``.

    ``INFERRED_LOCAL`` is a UTC container stamp (QuickTime ``CreateDate`` family) shifted to
    local wall-clock by corroborating evidence (MakerNotes ``TimeZone``, filename+duration,
    etc.). Distinct from raw ``EXIF``: the digits were converted, and ``date_tag`` records
    how. See :func:`truestill_core.dates.format_inferred_date_tag`.

    ``REJECTED_SENTINEL`` is ``NONE`` with a reason: the file *did* carry a date, and it was
    an epoch/container zero (Tier A, ``dates.HARD_SENTINELS``) that we refused. It also lands
    in ``Undated/`` -- the distinction exists purely so the report can say a date was found
    and rejected, rather than leaving the user to assume the file never had one.
    """

    #: A person told truestill this date. Outranks every machine tier, permanently: the
    #: resolver never overrides it and no later evidence demotes it. Stored in
    #: ``date_confirmations``, which survives the operations that rewrite ``files``.
    HUMAN_CONFIRMED = "human_confirmed"
    EXIF = "exif"
    TAKEOUT = "takeout"  # photoTakenTime -- authoritative capture time
    TAKEOUT_UPLOAD = "takeout_upload"  # creationTime -- upload time, approximate
    INFERRED_LOCAL = "inferred_local"  # UTC CreateDate shifted by proven offset
    FILENAME = "filename"
    NONE = "none"
    REJECTED_SENTINEL = "rejected_sentinel"  # only date found was an epoch zero -> refused


#: Date sources trusted enough not to warrant manual review.
_TRUSTED_DATE_SOURCES = frozenset({DateSource.EXIF, DateSource.TAKEOUT, DateSource.INFERRED_LOCAL})

#: Sources that produced no usable date at all. Excluded from the "approximate date" review
#: list: there is no date to review, and both are reported on their own line instead.
_DATELESS_SOURCES = frozenset({DateSource.NONE, DateSource.REJECTED_SENTINEL})


class ActionStatus(StrEnum):
    """Outcome of processing one file."""

    PLANNED = "planned"  # dry run: would upload
    UPLOADED = "uploaded"  # sent to the destination
    RENAMED = "renamed"  # uploaded under a suffixed name to avoid an unrelated collision
    DUPLICATE = "duplicate"  # skipped: matched an existing file (exact or perceptual)
    SKIPPED_UNDATED = "skipped_undated"  # skipped: no capture date and --skip-undated is set
    MOVED = "moved"  # uploaded, verified at the destination, and the source deleted (--move)
    MOVE_KEPT = "move_kept"  # uploaded, but verify/delete failed so the source was kept (--move)
    MOVED_IN_PLACE = "moved_in_place"  # renamed within one filesystem: no bytes rewritten
    ALREADY_PLACED = "already_placed"  # in-place re-run: the file is already at its target
    FAILED = "failed"


class DuplicateKind(StrEnum):
    """Which detection tier flagged a file as a duplicate."""

    EXACT = "exact"  # identical bytes (SHA-256)
    PERCEPTUAL = "perceptual"  # visually the same image (dHash within threshold)


class UnreadableReason(StrEnum):
    """Why a source file could not be read, when truestill tried and failed.

    **Not another ``None``.** Every ``None`` in :class:`FileHashes` records a hash that was
    *correctly* not computed - the size pre-filter's skip, a video with no perceptual hash.
    This records one that was wanted and could not be had, which is the distinction the scan
    used to destroy (`BACKLOG.md` ``(aac)``).

    Four members rather than a boolean because each is a **different next action** for the
    person reading the report: a permission is theirs to fix, an I/O error points at the disk,
    and a file that vanished mid-run was moved by something else and is not a defect at all.
    """

    PERMISSION = "permission"  # EACCES/EPERM - the user can fix this
    IO_ERROR = "io_error"  # EIO - points at the disk, not at the permissions
    MISSING = "missing"  # ENOENT - vanished between the walk and the read
    OTHER = "other"  # named rather than folded into one of the three above


#: User-facing wording for a read failure, kept here for the reason `_STATUS_LABELS` is here:
#: §9's "one source of outcome wording" rule. The CLI and the app both render through
#: :func:`unreadable_label`, so the two surfaces cannot drift, and no ``errno`` name or raw
#: enum value ever reaches a user.
_UNREADABLE_LABELS: dict[UnreadableReason, str] = {
    UnreadableReason.PERMISSION: "permission denied",
    UnreadableReason.IO_ERROR: "input/output error",
    UnreadableReason.MISSING: "disappeared during the scan",
    UnreadableReason.OTHER: "could not be opened",
}


def unreadable_label(reason: UnreadableReason) -> str:
    """The user-facing wording for a read failure. Never the raw enum value."""
    return _UNREADABLE_LABELS.get(reason, reason.value)


@dataclass(frozen=True, slots=True)
class FileHashes:
    """The two content signals computed for a file, and whether it could be read at all.

    ``sha256`` is ``None`` when the size pre-filter skipped hashing a unique-size file (it
    cannot be an exact duplicate of anything); it is computed lazily if the file is later
    uploaded. ``perceptual`` is ``None`` for non-images.

    ``unreadable`` is what tells those apart from a failure. Both of the fields above are
    ``None`` for a file that could not be read, and that collision is what made an unreadable
    source **invisible in a preview** - indistinguishable from the pre-filter's legitimate
    skip. It is ``None`` for every readable file, so the ordinary case is untouched, and it is
    never persisted: `HashCache.put` writes the two hashes only, and `scan._run_hash_jobs`
    already declines to cache a file with neither.
    """

    sha256: str | None
    perceptual: str | None
    unreadable: UnreadableReason | None = None


@dataclass(frozen=True, slots=True)
class DuplicateMatch:
    """A duplicate finding: what the file matched, how, and how closely."""

    kind: DuplicateKind
    matched_path: str
    origin: str  # "run" (earlier this run) or "catalog" (a previous run)
    distance: int | None = None  # Hamming distance for perceptual matches; None for exact


@dataclass(frozen=True, slots=True)
class CategoryMatch:
    """A derived folder label plus the evidence that produced it."""

    label: str
    reason: str
    confidence: Confidence
    rule: RuleName


@dataclass(frozen=True, slots=True)
class Event:
    """One named event, carried as a single value through placement and catalog link.

    Replaces the parallel-collections anti-pattern of three dicts keyed by source path
    (``assignments: (start, slug)``, ``names``, ``event_ids``) that had to be kept in sync by
    hand. Each new need had been adding another array instead of changing the type of the
    existing one - which is exactly how human names became a third dict, and how the audit's
    F1 (missing event names on disk) shipped. With one object, a member cannot have a slug
    without its id, or an id without its start; a forgotten name field is unrepresentable as
    "present in one map and absent in another."

    ``name`` is optional on purpose: a remembered event with no usable name still renders its
    slug folder (``YYYYMMDD_<slug>``), matching :func:`truestill_core.layout.event_folder`.
    ``start`` is the cluster's full timestamp, not a calendar day - day events are not days
    (``BACKLOG.md`` ``(ll)``): the same date can hold several clusters, and a day key would
    collapse them.
    """

    start: datetime
    slug: str
    name: str | None
    id: int


@dataclass(frozen=True, slots=True)
class Decision:
    """A single file's categorization and placement, before anything is written.

    ``relative`` is backend-independent: it is the path *within* a destination
    (``Camera/2025/08/foo.jpg``), so the same decision can target local disk, a cloud remote
    or anything else without change.
    """

    source: Path
    category: CategoryMatch
    captured_at: datetime | None
    date_source: DateSource
    date_tag: str | None
    relative: Path
    #: Tier B: the date is exactly midnight on a known camera-clock reset day, so it may be a
    #: dead-battery default rather than a capture time. The file is still placed by that date
    #: -- these can be genuine -- and counted in the report for the user to review.
    #: See ``dates.is_suspect_default``.
    suspect_default: bool = False
    #: UTC container stamp (CreateDate family digits) before an ``INFERRED_LOCAL`` shift.
    #: None for every other source. Used by the never-silent report so it can name
    #: ``before -> after`` without re-opening the file.
    inferred_from: datetime | None = None

    @property
    def needs_review(self) -> bool:
        """True when the date came from an approximate source (not trusted metadata)."""
        return (
            self.date_source not in _TRUSTED_DATE_SOURCES
            and self.date_source not in _DATELESS_SOURCES
        )


@dataclass(frozen=True, slots=True)
class Resolution:
    """A decision plus its content hashes and duplicate verdict.

    The two tiers are handled differently, by policy:

    * ``exact_duplicate`` -- byte-identical to a known file. **Skipped**; keeping a second
      identical copy gains nothing, and there is no quality to lose.
    * ``near_duplicate`` -- perceptually the same image as a known file but different bytes
      (e.g. a recompressed copy). **Still uploaded**, only flagged, so an original can
      never be silently dropped in favour of a lower-quality look-alike.
    """

    decision: Decision
    hashes: FileHashes
    exact_duplicate: DuplicateMatch | None
    near_duplicate: DuplicateMatch | None

    @property
    def should_upload(self) -> bool:
        """Everything except an exact duplicate is uploaded."""
        return self.exact_duplicate is None

    @property
    def is_unique(self) -> bool:
        """New content with no exact or perceptual match anywhere."""
        return self.exact_duplicate is None and self.near_duplicate is None


@dataclass(frozen=True, slots=True)
class ReportBuckets:
    """Every scanned file in **exactly one** bucket, so a report's numbers can be added up.

    The preview used to say two contradictory things about the same file: *"organized (unique):
    5"* and *"files that could not be read: 2"*, where the 5 included both. A file that could
    not be read has no hash, so it matches nothing, so it read as new.

    Buckets are disjoint **and** exhaustive - :attr:`total` equals the number of resolutions
    partitioned - which is the property worth having rather than the one corrected number: a
    category added later that forgets to be disjoint fails the conservation test instead of
    quietly double-counting.
    """

    unreadable: list[Resolution]
    exact_duplicates: list[Resolution]
    near_duplicates: list[Resolution]
    unique: list[Resolution]

    @property
    def organized(self) -> list[Resolution]:
        """What a run will actually put in the library. Replaces filtering on `should_upload`."""
        return self.unique + self.near_duplicates

    @property
    def total(self) -> int:
        return (
            len(self.unreadable)
            + len(self.exact_duplicates)
            + len(self.near_duplicates)
            + len(self.unique)
        )


def partition_for_report(resolutions: Iterable[Resolution]) -> ReportBuckets:
    """Split resolutions into the four disjoint buckets a report may count. **O(n)**.

    **Unreadable is tested first, and that ordering is the load-bearing part.** An unreadable
    file usually has no hashes and could only ever be "unique" - but a *cache hit* gives it real
    ones (`HashCache` keys on size and mtime, and `stat` succeeds on a file whose bytes cannot be
    read), so it can genuinely match the exact or perceptual tier. Reporting it as *"identical to
    a kept file, will skip"* would describe a file truestill could not read this time, and being
    unable to read it is the fact the user needs. This is the distinction AWS DataSync draws
    between a *skipped success* and a *skipped error*.

    **This is deliberately not `Resolution.should_upload`, and must not be folded into it.**
    That property drives the *plan*, not the report: `organizer.preflight_for_run` sizes the
    destination with it, and on a run an unreadable file **is** attempted - the copy is tried and
    raises, which is what surfaces it as `ActionStatus.FAILED`. Teaching `should_upload` about
    readability would under-size the destination and delete the run's only report of the file.
    The plan still attempts it; only the tally stops promising it. Pinned by
    `test_report_buckets.py`.
    """
    unreadable: list[Resolution] = []
    exact_duplicates: list[Resolution] = []
    near_duplicates: list[Resolution] = []
    unique: list[Resolution] = []
    for resolution in resolutions:
        if resolution.hashes.unreadable is not None:
            unreadable.append(resolution)
        elif resolution.exact_duplicate is not None:
            exact_duplicates.append(resolution)
        elif resolution.near_duplicate is not None:
            near_duplicates.append(resolution)
        else:
            unique.append(resolution)
    return ReportBuckets(unreadable, exact_duplicates, near_duplicates, unique)


#: Human wording for each outcome, shared by the CLI report and the app so the two surfaces
#: cannot describe the same run differently.
#:
#: **"uploaded" never reaches a user.** It is honest *inside* the code -- `Destination.upload`
#: covers rclone remotes, where an upload is exactly what happens -- but as a word shown to
#: someone organizing photos on their own disk it is backend vocabulary describing an event
#: that did not occur, and it quietly contradicts the promise that files never leave the
#: machine. "Organized" is true of every backend, so one word serves both.
_STATUS_LABELS: dict[ActionStatus, str] = {
    ActionStatus.PLANNED: "would be organized",
    ActionStatus.UPLOADED: "organized",
    ActionStatus.RENAMED: "organized (renamed to avoid a name clash)",
    ActionStatus.DUPLICATE: "duplicate, skipped",
    ActionStatus.SKIPPED_UNDATED: "skipped, no date",
    ActionStatus.MOVED: "moved",
    ActionStatus.MOVED_IN_PLACE: "moved on the drive",
    ActionStatus.MOVE_KEPT: "kept, move not completed",
    ActionStatus.ALREADY_PLACED: "already in place",
    ActionStatus.FAILED: "failed",
}


def status_label(status: ActionStatus) -> str:
    """The user-facing wording for an outcome. Never the raw enum value."""
    return _STATUS_LABELS.get(status, status.value)


class DateQuality(NamedTuple):
    """The two date-quality signals a run must disclose, counted over the files it kept.

    Both are deliberately separate from the plain "undated" tally: folding either into it
    would tell the user *how many* files lack a good date while hiding *why*, which is the
    failure mode the never-silent rule exists to prevent.
    """

    #: Files whose only date was a Tier A epoch zero. Refused -> they went to ``Undated/``.
    sentinel_rejected: int
    #: Files dated by a Tier B camera default (exact midnight on a clock-reset day). These
    #: are **filed by that date** -- they may well be right -- and merely flagged for review.
    suspect_default: int


def date_quality(resolutions: Iterable[Resolution]) -> DateQuality:
    """Count both signals in a single pass.

    Shared by the CLI and the app so the two front-ends can never drift into reporting
    different numbers for the same run.
    """
    sentinel = suspect = 0
    for resolution in resolutions:
        decision = resolution.decision
        if decision.date_source is DateSource.REJECTED_SENTINEL:
            sentinel += 1
        if decision.suspect_default:
            suspect += 1
    return DateQuality(sentinel_rejected=sentinel, suspect_default=suspect)


class InferredLocalShift(NamedTuple):
    """One video whose UTC CreateDate was shifted to local wall-clock.

    Informational disclosure - not a defect. ``not_proven_utc`` files are never listed here.
    """

    name: str
    before: datetime
    after: datetime
    offset: timedelta
    evidence: str  # short human label: "filename", "TimeZone", …


def _evidence_report_label(evidence: str) -> str:
    """Map a provenance evidence token to the short report label."""
    # Combined tokens put the offset source last (``GPSDateStamp+filename:VID_``).
    primary = evidence.rsplit("+", 1)[-1]
    if primary.startswith("filename:"):
        return "filename"
    if primary == "TimeZone":
        return "TimeZone"
    return primary


_INFERRED_TAG_FIELDS = 3


def inferred_local_shifts(resolutions: Iterable[Resolution]) -> tuple[InferredLocalShift, ...]:
    """Videos shifted from UTC CreateDate this run, named with before/after/offset.

    Shared by CLI and app. Empty when nothing was inferred. Does **not** include
    ``not_proven_utc`` fallthrough (those stay EXIF and are usually correct).
    """
    shifts: list[InferredLocalShift] = []
    for resolution in resolutions:
        decision = resolution.decision
        if decision.date_source is not DateSource.INFERRED_LOCAL:
            continue
        if decision.captured_at is None or decision.inferred_from is None or not decision.date_tag:
            continue
        parts = decision.date_tag.split("|")
        if len(parts) != _INFERRED_TAG_FIELDS:
            continue
        try:
            offset = parse_offset(parts[2])
        except ValueError:
            continue
        shifts.append(
            InferredLocalShift(
                name=decision.source.name,
                before=decision.inferred_from,
                after=decision.captured_at,
                offset=offset,
                evidence=_evidence_report_label(parts[1]),
            )
        )
    return tuple(shifts)


def format_inferred_local_shift_line(shift: InferredLocalShift) -> str:
    """``VID_….mp4  04:54:24 -> 10:21:45  (+05:30, filename)``."""
    return (
        f"{shift.name}  {shift.before.strftime('%H:%M:%S')} -> "
        f"{shift.after.strftime('%H:%M:%S')}  "
        f"({format_offset(shift.offset)}, {shift.evidence})"
    )


@dataclass(frozen=True, slots=True)
class ActionResult:
    """What actually happened to one file during execution."""

    resolution: Resolution
    status: ActionStatus
    final_relative: Path | None
    detail: str = ""
