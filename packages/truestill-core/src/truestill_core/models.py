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
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import NamedTuple

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


class DateSource(StrEnum):
    """Where a file's capture date was recovered from, best to worst.

    ``EXIF`` and ``TAKEOUT`` (Google's ``photoTakenTime``) are trusted. ``TAKEOUT_UPLOAD``
    (Google's ``creationTime``, i.e. when it was uploaded) and ``FILENAME`` are approximate
    and flagged for review. ``NONE`` means no date evidence -> ``Undated/``.

    ``REJECTED_SENTINEL`` is ``NONE`` with a reason: the file *did* carry a date, and it was
    an epoch/container zero (Tier A, ``dates.HARD_SENTINELS``) that we refused. It also lands
    in ``Undated/`` -- the distinction exists purely so the report can say a date was found
    and rejected, rather than leaving the user to assume the file never had one.
    """

    EXIF = "exif"
    TAKEOUT = "takeout"  # photoTakenTime -- authoritative capture time
    TAKEOUT_UPLOAD = "takeout_upload"  # creationTime -- upload time, approximate
    FILENAME = "filename"
    NONE = "none"
    REJECTED_SENTINEL = "rejected_sentinel"  # only date found was an epoch zero -> refused


#: Date sources trusted enough not to warrant manual review.
_TRUSTED_DATE_SOURCES = frozenset({DateSource.EXIF, DateSource.TAKEOUT})

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
    rule: str


@dataclass(frozen=True, slots=True)
class Decision:
    """A single file's categorization and placement, before anything is written.

    ``relative`` is backend-independent: it is the path *within* a destination
    (``Camera/2025/08/foo.jpg``), so the same decision can target local disk, pCloud or
    anything else without change.
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


@dataclass(frozen=True, slots=True)
class ActionResult:
    """What actually happened to one file during execution."""

    resolution: Resolution
    status: ActionStatus
    final_relative: Path | None
    detail: str = ""
