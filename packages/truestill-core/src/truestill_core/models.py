"""Core data types shared across the organizer.

Category labels are **open-ended strings, not an enum**. The set of folders that a run
produces is discovered from the files themselves: a new messenger, editing app or
camera brand appearing in the library creates its own folder without a code change.
Files whose origin cannot be proven from evidence fall through to :data:`SAVED_LABEL`.

The organizer never mutates its source tree. Every run produces a list of
:class:`Decision` objects first; execution is a separate, explicitly opted-in step.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Any, NamedTuple

from truestill_core.date_provenance import format_offset, parse_offset

#: Folder used when a file carries no usable date evidence at all. Files land here
#: rather than being guessed into a year, so an undated file is always visible as such.
UNDATED_DIRNAME = "Undated"

#: Label for files whose origin cannot be proven -- metadata-stripped social/web saves and
#: anything else with no identifying evidence. Named "Saved" rather than "Unsorted": to a
#: normal user "Unsorted" reads as a failure, whereas these files are genuinely just images
#: saved from apps or the web, whose origin is unknowable by design (platforms strip EXIF).
SAVED_LABEL = "Saved"


def strip_component_tail(value: str) -> str:
    """Trim what a path component may not end with: whitespace, then dots and spaces.

    **One rule, two callers.** `layout._sanitize_value` and `categorize.sanitize_label` both
    have to answer "is this safe as a single path component", and they had different answers:
    the layout one trimmed the tail, the label one did not, because its length cap ran *after*
    its trim (``cleaned[:60].strip()`` drops whitespace but not a dot, so a cut landing on one
    kept it). ENGINEERING_STANDARD.md §4 asks for the duplicated rule to have one home rather
    than a second test, and this is that home -- the two functions stay separate because they
    legitimately differ elsewhere (60 characters vs 255 bytes, ``' '`` vs ``'_'`` as the
    replacement, NFC, a fallback), and only the tail rule was ever shared.

    It matters beyond tidiness: Windows and FAT drop a trailing dot or space when the file is
    created, so ``Trip.`` and ``Trip`` are one directory there and two on ext4 -- the same
    library reading differently on two machines.
    """
    return value.strip().rstrip(" .")


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

    The eight members are the full set the router knows. Values are the historical string
    tokens (unchanged) so comparisons with those literals stay true. This is **not** a
    catalog column - it is in-memory evidence for the current run / re-derive pass only.
    """

    SCREENSHOT_METADATA = "screenshot_metadata"
    SCREENSHOT_NAME = "screenshot_name"
    FILENAME_CONVENTION = "filename_convention"
    SOFTWARE = "software"
    DEVICE = "device"
    CAMERA_FILENAME = "camera_filename"
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

    ``REJECTED_FUTURE`` is the same shape as ``REJECTED_SENTINEL`` and deliberately a
    *different* member: a placeholder date says the device never set its clock, while a future
    date says the clock was wrong or the metadata was edited. Different causes, different
    remedies, so folding them into one count would hide the *why* the never-silent rule exists
    to disclose.

    ``REJECTED_SENTINEL`` is ``NONE`` with a reason: the file *did* carry a date, and it was
    an epoch/container zero (Tier A, ``dates.HARD_SENTINELS``) that we refused. It also lands
    in ``Undated/`` -- the distinction exists purely so the report can say a date was found
    and rejected, rather than leaving the user to assume the file never had one.

    ``REJECTED_EARLY`` completes that set at the other end. A value below
    ``dates._MIN_SANE_YEAR`` used to return ``NONE``, so ``1899:12:31`` was found, refused, and
    reported as "no date evidence" -- the exact silence the two members above exist to prevent,
    surviving because the *ceiling* happened to be guarded by ``REJECTED_FUTURE`` and nobody
    asked about the floor.
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
    REJECTED_FUTURE = "rejected_future"  # only date found was after now -> refused
    REJECTED_EARLY = "rejected_early"  # only date found was below the sanity floor -> refused


#: Date sources trusted enough not to warrant manual review.
_TRUSTED_DATE_SOURCES = frozenset({DateSource.EXIF, DateSource.TAKEOUT, DateSource.INFERRED_LOCAL})

#: Sources that produced no usable date at all. Excluded from the "approximate date" review
#: list: there is no date to review.
#:
#: The two refusals with a `DateQuality` counter get their own line in a run summary.
#: ``REJECTED_EARLY`` deliberately does **not** have one: `Catalog.stats_date_provenance` groups
#: by whatever ``date_source`` string is stored and `date_explain.explain` renders any of them, so
#: the library's date view surfaces it with no code change, while a run-summary counter would
#: touch both front-ends and `app.js` for a class measured at **0 of 895** real tag readings
#: (`date-resolver-corpus-measurement.md` §4.2). One line to add the day a real library shows one.
_DATELESS_SOURCES = frozenset(
    {
        DateSource.NONE,
        DateSource.REJECTED_SENTINEL,
        DateSource.REJECTED_FUTURE,
        DateSource.REJECTED_EARLY,
    }
)


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

    Five members rather than a boolean because each is a **different next action** for the
    person reading the report: a permission is theirs to fix, an I/O error points at the disk,
    and a file that vanished mid-run was moved by something else and is not a defect at all.

    ``UNDECODABLE`` is the fifth and it is not an I/O failure at all (`(aet)`): the bytes read
    perfectly and an image decoder refused them - a truncated HEIC, a PNG with a malformed `zTXt`
    chunk. Folded into ``OTHER`` it would read *"could not be opened"*, which is false and sends
    the reader to check permissions on a file nothing is wrong with.
    """

    PERMISSION = "permission"  # EACCES/EPERM - the user can fix this
    IO_ERROR = "io_error"  # EIO - points at the disk, not at the permissions
    UNDECODABLE = "undecodable"  # read fine; an image decoder refused the contents - `(aet)`
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
    UnreadableReason.UNDECODABLE: "could be read, but its contents could not be decoded",
}


#: What to do about each read failure. **One remedy per reason, because that is why the reasons
#: exist** - `UnreadableReason`'s own docstring says each member is *"a different next action for
#: the person reading the report"*, and until 2026-08-21 the CLI printed *"fix the permission or
#: check the disk"* for all five. `(aew)`
#:
#: ⚠ Measured on the format corpus: **8 of 8** files named under that sentence were `UNDECODABLE`,
#: where nothing ails the permissions or the disk. That is the same misdirection `(aer)` removed
#: for folders, sitting unfixed on the file side - and `UNDECODABLE` was added by `(aet)` *for*
#: this reason, then rendered under the remedy it was created to escape.
_UNREADABLE_REMEDIES: dict[UnreadableReason, str] = {
    UnreadableReason.PERMISSION: "check the file's permissions and try again",
    UnreadableReason.IO_ERROR: "check the disk; this one points at the hardware, not at you",
    UnreadableReason.MISSING: "nothing to do - it was moved or deleted while the run was reading",
    UnreadableReason.UNDECODABLE: "the file itself is damaged; a copy from another source is the "
    "only fix, and nothing else in the run was affected",
    UnreadableReason.OTHER: "check the file's permissions and the disk, then try again",
}


def unreadable_remedy(reason: UnreadableReason) -> str:
    """What to do about this read failure. Never the raw enum value, never a shared sentence."""
    return _UNREADABLE_REMEDIES.get(reason, _UNREADABLE_REMEDIES[UnreadableReason.OTHER])


def unreadable_label(reason: UnreadableReason) -> str:
    """The user-facing wording for a read failure. Never the raw enum value."""
    return _UNREADABLE_LABELS.get(reason, reason.value)


class FolderSkip(StrEnum):
    """Why a FOLDER was not looked inside. The sibling of :class:`UnreadableReason`. `(aer)`

    ⚠ **The pairing is the lesson.** A file carries a reason **and a count**, because the number
    is known exactly. A folder carries a reason and **never a count**: the walk did not go in, so
    the number of files inside is precisely what is unknown, and stating one would invent it.
    `SourceScan`'s own docstring calls this *"a different kind of fact from every other list
    here"*, which is why folders are not folded into `skipped_extension_counts` - that structure's
    values are counts of files, and a number there meaning *folders* would be two shapes in one
    string.

    Two members rather than a boolean because each is a **different next action**: a hidden folder
    is the user's own naming and they can rename it; an unreadable one is a permission or a disk.
    """

    HIDDEN = "hidden"  # the walk never descended, deliberately - a dot-file is not a photo
    UNREADABLE = "unreadable"  # the walk could not descend


#: Headings, kept here for the reason `_STATUS_LABELS` and `_UNREADABLE_LABELS` are here: §9's
#: "one source of outcome wording". Three surfaces render these and none of them may hold its own
#: copy - the duplication `(aer)` found was this same sentence written twice in one file.
#:
#: ⚠ **A FOLDER IS "OPENED", A FILE IS "READ", AND THE TWO VERBS ARE LOAD-BEARING.** The CLI wrote
#: *"folders that could not be read"* directly above *"files that could not be read: 2"* - one
#: phrase for two facts, one of which carries a count and one of which must never. The browser had
#: it right (*"could not be opened"*) and pins it: `test_unreadable_sources_are_visible.py` asserts
#: the folder block does **not** contain the file phrase, because reusing it invites the count the
#: folder line deliberately withholds. Unifying on the CLI's phrasing would have carried the
#: collision to all three surfaces; the browser lane is what caught it, and `make check` could not.
_FOLDER_SKIP_LABELS: dict[FolderSkip, str] = {
    FolderSkip.HIDDEN: "hidden folders (not looked inside)",
    FolderSkip.UNREADABLE: "folders that could not be opened",
}

#: What to do about it. **Naming a problem without a remedy is half a report**, which is
#: `c027dd3`'s wording and the reason these live beside the labels rather than at a call site.
#: ⚠ **SURFACE-NEUTRAL, and that is a deliberate change from what each surface said.** The CLI
#: wrote *"then run again"* and the browser *"then preview again"*, because one runs and one
#: previews - a real difference that produced three copies of one sentence, two of which said the
#: same thing in different words. *"try again"* is true of both, so one string can serve them and
#: the wording cannot drift by surface.
_FOLDER_SKIP_REMEDIES: dict[FolderSkip, str] = {
    FolderSkip.HIDDEN: "rename it without the leading dot and try again to include what is in it",
    FolderSkip.UNREADABLE: "check the folder's permissions and try again to include what is inside",
}


class UncomparedReason(StrEnum):
    """Why a photograph got no near-duplicate check. The sibling of :class:`FolderSkip`. `(aev)`

    ⚠ **TWO REASONS, NOT ONE, AND THE SECOND ARRIVED WITH `(ahq)`.** A single label was correct
    while the only way to miss the comparison was to fail decoding. `dedup.carries_no_signal` then
    added a file that decoded **perfectly** and is still never compared, and shipping that
    exclusion with no name is the failure `IMPLEMENTATION_STANDARDS.md` §"Never-silent" exists to
    stop: *"A skipped, refused, degraded or unverifiable outcome is counted and named."* Measured
    on one real 10,138-image library, the unnamed group was **97 files**.

    The two are separate members because they are two different FACTS about the file - one could
    not be read, one was read and carries no distinguishing detail. That the remedy happens to be
    identical is not a reason to merge them; the remedy is the same because the consequence is.
    """

    UNDECODABLE = "undecodable"  # a perceptual pass ran and Pillow could not decode the file
    NO_SIGNAL = "no_signal"  # decoded fine, and the hash carries less signal than the threshold


#: What the user is told about a photograph that got no near-duplicate check, and what it cost
#: them. Kept here for the reason `_FOLDER_SKIP_LABELS` is here: §9's "one source of outcome
#: wording", so no surface may hold its own copy.
#:
#: ⚠ **DERIVED FROM THE OUTCOME, NEVER FROM A WARNING**, which is `(aev)`'s whole finding. The
#: entry was filed as *"131 raw Pillow warnings reached the terminal"*; measured on the format
#: corpus, **478 photographs got no near-duplicate check and only 71 of them warned** - while
#: **14 files warned and decoded perfectly well**. Reporting the warnings would have named 71 of
#: 478 and implied the rest were fine. §4's forty-second member: a check measuring the cheaper
#: proxy. The warning is evidence; the CONSEQUENCE is what a person needs.
#:
#: ⚠ **`NO_SIGNAL` SAYS *"too little detail"*, NEVER *"blank"* OR *"failed"*.** The frame may be
#: a perfectly good photograph of fog, a wall or a lens cap; nothing about it is broken, and a
#: word implying damage would send someone looking for a file that is fine.
_UNCOMPARED_LABELS: dict[UncomparedReason, str] = {
    UncomparedReason.UNDECODABLE: "photos whose contents could not be decoded",
    UncomparedReason.NO_SIGNAL: "photos with too little detail to compare",
}

#: **The remedy states what still worked**, because the honest answer here is *nothing is broken
#: and nothing is required of you*. A line that only says what failed reads as data loss.
#:
#: ⚠ **BOTH MEMBERS CARRY THE SAME SENTENCE, DELIBERATELY.** The consequence is identical -
#: the file is organized, and byte-identical copies are still caught by the exact tier - so
#: wording them differently would be drift invented to fill a table. The LABELS differ because
#: the facts differ; the remedies do not because the outcome does not.
_UNCOMPARED_REMEDIES: dict[UncomparedReason, str] = {
    UncomparedReason.UNDECODABLE: (
        "organized normally, and identical copies are still found by content"
    ),
    UncomparedReason.NO_SIGNAL: (
        "organized normally, and identical copies are still found by content"
    ),
}


def uncompared_label(reason: UncomparedReason) -> str:
    """The heading a person reads for this group. Never the raw enum value."""
    return _UNCOMPARED_LABELS[reason]


def uncompared_remedy(reason: UncomparedReason) -> str:
    """What to do about it, in one place, so no surface can word it differently."""
    return _UNCOMPARED_REMEDIES[reason]


def folder_skip_label(reason: FolderSkip) -> str:
    """The heading a person reads for this group. Never the raw enum value."""
    return _FOLDER_SKIP_LABELS.get(reason, reason.value)


def folder_skip_remedy(reason: FolderSkip) -> str:
    """What to do about it, in one place, so no surface can word it differently."""
    return _FOLDER_SKIP_REMEDIES.get(reason, "")


@dataclass(frozen=True, slots=True)
class FileHashes:
    """The two content signals computed for a file, and whether it could be read at all.

    ``sha256`` is ``None`` when the size pre-filter skipped hashing a unique-size file (it
    cannot be an exact duplicate of anything); it is computed lazily if the file is later
    uploaded. ``perceptual`` is ``None`` for non-images **and** for a pass that did not compute
    one, which is why :attr:`perceptual_computed` exists: without it those two are the same
    value, and every reader has to guess which it got.

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
    #: Whether a perceptual pass actually ran. ``perceptual=None`` answers two different
    #: questions - *not an image* and *nobody looked* - and a report that cannot tell them apart
    #: told users their photographs were not images. Defaults to ``True`` because a caller
    #: constructing hashes is stating an answer; the passes that compute only SOME of them say so.
    perceptual_computed: bool = True


class DuplicateOrigin(StrEnum):
    """Where a duplicate's twin was found.

    The two values are the tokens `DedupIndex` has always written, so this names an existing
    vocabulary rather than introducing one - nothing compared or displayed changed when it
    arrived. It exists because the distinction is now **counted**, not only described per file,
    and a count keyed on a literal repeated across three modules is a count that can drift into
    the wrong bucket without anything failing.
    """

    #: Matched a file seen earlier in the batch being processed now.
    RUN = "run"
    #: Matched a file a previous run already put in the library.
    CATALOG = "catalog"


@dataclass(frozen=True, slots=True)
class DuplicateMatch:
    """A duplicate finding: what the file matched, how, and how closely."""

    kind: DuplicateKind
    matched_path: str
    #: Where the twin is. A plain ``str`` is still accepted, and deliberately: the display path
    #: promises to survive a token it does not recognise (`duplicate_explain.origin_phrase`),
    #: and a count that meets one must name it rather than drop it.
    origin: DuplicateOrigin | str
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
class CaptureContext:
    """What the file says about the device that made it and where it was made.

    Read during categorisation and the event jump-cut and, until `(kk)`, discarded. Carried on
    the :class:`Decision` rather than re-derived at write time for the reason `date_source` is:
    a second reading could disagree with the placement this same decision produced.

    ``gps_latitude``/``gps_longitude`` are signed decimal degrees - exiftool is asked for them
    with a trailing ``#`` so S and W arrive negative. ``None`` means the file carries no
    location; **0.0 means the equator or the prime meridian and is a real answer.**
    """

    camera_make: str | None = None
    camera_model: str | None = None
    lens_model: str | None = None
    gps_latitude: float | None = None
    gps_longitude: float | None = None

    @classmethod
    def from_metadata(cls, meta: Mapping[str, Any]) -> CaptureContext:
        """Read the five values out of one exiftool result. **O(1)**, no I/O."""
        return cls(
            camera_make=_clean(meta.get("Make")),
            camera_model=_clean(meta.get("Model")),
            lens_model=_clean(meta.get("LensModel")),
            gps_latitude=_coordinate(meta.get("GPSLatitude")),
            gps_longitude=_coordinate(meta.get("GPSLongitude")),
        )


def _clean(value: Any) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text or None


def geo_point(latitude: Any, longitude: Any) -> tuple[float, float] | None:
    """A coordinate pair, or ``None`` unless **both** halves are real numbers.

    One rule, three vocabularies: exiftool hands back ``GPSLatitude``/``GPSLongitude``, the
    catalog stores ``gps_latitude``/``gps_longitude``, and both must reach the same verdict.
    Spelling this out twice is how one of them ends up with the truthiness bug below and the
    other does not - which is exactly the state the trip clustering was in before `(kk)`.
    """
    lat, lon = _coordinate(latitude), _coordinate(longitude)
    return None if lat is None or lon is None else (lat, lon)


def _coordinate(value: Any) -> float | None:
    """A coordinate, or ``None`` when the file carries none.

    **`isinstance`, never truthiness.** exiftool returns integer ``0`` for a photo on the
    equator or the prime meridian, and ``0`` is falsy - so ``if value:`` would silently record
    Null Island as having no location at all. That is the overloaded-sentinel family this repo
    already paid for in `(aac)`, and it is what a later "simplification" would reintroduce.
    `event_review._gps` guards the same value the same way; both must stay.
    """
    return float(value) if isinstance(value, int | float) else None


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
    #: Camera and location as the file reported them, carried here so the write path never
    #: re-reads the file. Defaulted so the decision can be built without one.
    capture: CaptureContext = field(default_factory=CaptureContext)

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

    def will_organize(self, *, skip_undated: bool) -> int:
        """How many files a run with these options **will** put in the library. `(abl)`, `(acx)`.

        The one home for that number, and the reason it is a method here rather than an expression
        at a call site: the app rendered `new_unique + near_dup` in its confirm control while its
        tally card rendered `new_unique` alone under the words *"will be organized"*, so one screen
        stated two different answers to the same question and neither cited the other. A second
        call site is how that happens; there is now one.

        **`skip_undated` is a parameter rather than an assumption**, because it changes the answer
        and a preview that does not receive it promises files the run will not take - measured as
        `(acx)`, where the app's preview endpoint never accepted the flag its own run endpoint did.

        Unreadable files are excluded: they are attempted and fail (`ActionStatus.FAILED`), which
        is why they are their own bucket rather than part of :attr:`organized`, and a preview must
        not promise a file it has already reported it could not read.
        """
        if not skip_undated:
            return len(self.organized)
        return sum(1 for r in self.organized if r.decision.captured_at is not None)

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
    #: Files whose only date was **after now**. Refused -> ``Undated/``. Usually a wrong device
    #: clock or edited metadata, which is why it is counted apart from the placeholder case.
    future_rejected: int
    #: Files dated by a Tier B camera default (exact midnight on a clock-reset day). These
    #: are **filed by that date** -- they may well be right -- and merely flagged for review.
    suspect_default: int


def date_quality(resolutions: Iterable[Resolution]) -> DateQuality:
    """Count both signals in a single pass.

    Shared by the CLI and the app so the two front-ends can never drift into reporting
    different numbers for the same run.
    """
    sentinel = suspect = future = 0
    for resolution in resolutions:
        decision = resolution.decision
        if decision.date_source is DateSource.REJECTED_SENTINEL:
            sentinel += 1
        if decision.date_source is DateSource.REJECTED_FUTURE:
            future += 1
        if decision.suspect_default:
            suspect += 1
    return DateQuality(sentinel_rejected=sentinel, future_rejected=future, suspect_default=suspect)


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
    #: The content id this outcome was recorded under, when one was established.
    #:
    #: **Not a duplicate of ``resolution.hashes.sha256``, and that is the reason it exists.**
    #: The scan's size pre-filter skips hashing a file whose size is unique - it cannot be an
    #: exact duplicate of anything - so a resolution can reach execution with ``sha256`` unset.
    #: ``execute`` then computes it, because the file is being read for upload anyway, writes it
    #: to the catalog, and until now dropped it: the catalog knew the content id and the RESULT
    #: did not. Any surface answering "which files did this run place" from results alone saw a
    #: hole exactly the size of the unique-size files, and the first one to ask - the organize
    #: result grid - drew two photos for a run of four.
    sha256: str | None = None
