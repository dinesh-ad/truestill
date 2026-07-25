"""Core data types shared across the organizer.

Category labels are **open-ended strings, not an enum**. The set of folders that a run
produces is discovered from the files themselves: a new messenger, editing app or
camera brand appearing in the library creates its own folder without a code change.
Files whose origin cannot be proven from evidence fall through to :data:`SAVED_LABEL`.

The organizer never mutates its source tree. Every run produces a list of
:class:`Decision` objects first; execution is a separate, explicitly opted-in step.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path

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
    """

    EXIF = "exif"
    TAKEOUT = "takeout"  # photoTakenTime -- authoritative capture time
    TAKEOUT_UPLOAD = "takeout_upload"  # creationTime -- upload time, approximate
    FILENAME = "filename"
    NONE = "none"


#: Date sources trusted enough not to warrant manual review.
_TRUSTED_DATE_SOURCES = frozenset({DateSource.EXIF, DateSource.TAKEOUT})


class ActionStatus(StrEnum):
    """Outcome of processing one file."""

    PLANNED = "planned"  # dry run: would upload
    UPLOADED = "uploaded"  # sent to the destination
    RENAMED = "renamed"  # uploaded under a suffixed name to avoid an unrelated collision
    DUPLICATE = "duplicate"  # skipped: matched an existing file (exact or perceptual)
    SKIPPED_UNDATED = "skipped_undated"  # skipped: no capture date and --skip-undated is set
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

    @property
    def needs_review(self) -> bool:
        """True when the date came from an approximate source (not trusted metadata)."""
        return (
            self.date_source not in _TRUSTED_DATE_SOURCES
            and self.date_source is not DateSource.NONE
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
class ActionResult:
    """What actually happened to one file during execution."""

    resolution: Resolution
    status: ActionStatus
    final_relative: Path | None
    detail: str = ""
