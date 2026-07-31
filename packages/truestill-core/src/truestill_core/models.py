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


@dataclass(frozen=True, slots=True)
class FileHashes:
    """The two content signals computed for a file.

    ``sha256`` is ``None`` when the size pre-filter skipped hashing a unique-size file (it
    cannot be an exact duplicate of anything); it is computed lazily if the file is later
    uploaded. ``perceptual`` is ``None`` for non-images.
    """

    sha256: str | None
    perceptual: str | None


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
