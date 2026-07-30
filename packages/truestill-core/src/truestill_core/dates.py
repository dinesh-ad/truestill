"""Capture-date resolution.

Priority, deliberately: embedded metadata first, filename convention second, nothing
third. Filesystem mtime is never consulted -- Google Photos download and Takeout zips
carry the *download* time in the filesystem timestamp, so trusting mtime would file an
entire library under the day it was exported.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, NamedTuple

from truestill_core.categorize import is_messenger_filename
from truestill_core.models import DateSource
from truestill_core.takeout import TakeoutSidecar, local_naive

# ---------------------------------------------------------------------------
# Inferred-local provenance (``DateSource.INFERRED_LOCAL`` / not-proven-UTC)
#
# ``date_tag`` is the durable provenance record a later pass reads. Format:
#
#   {container_tag}|{evidence}[|{offset}]
#
# Field separator is ASCII ``|`` (U+007C). Exiftool tag names use ``Group:Tag`` with a
# colon, never a pipe, so splitting on ``|`` cannot collide with a real tag name we place
# in field 0 or with evidence tokens such as ``TimeZone`` / ``filename:VID_``.
# Evidence tokens that combine signals join with ``+`` inside field 1
# (``GPSDateStamp+filename:VID_``), never with ``|``.
#
# Offset is ``+HH:MM`` / ``-HH:MM`` (half-hour grid). Absent only for the not-proven-UTC form.
#
# Examples:
#   CreateDate|filename:VID_|+05:30
#   CreateDate|TimeZone|+06:30
#   CreateDate|not_proven_utc  (not proven UTC; treated as local - usually correct)
# ---------------------------------------------------------------------------

#: Provenance field separator. Must not appear in container tags or evidence tokens.
INFERRED_DATE_TAG_SEP = "|"

#: Evidence token when a container stamp was left as local digits.
#: Means "not proven to be UTC; treated as local" - **not** a defect. Most cameras that
#: write local into ``CreateDate`` land here correctly; reports must not alarm.
NOT_PROVEN_UTC = "not_proven_utc"

_OFFSET_RE = re.compile(r"^([+-])(\d{2}):(\d{2})$")
_SECONDS_PER_MINUTE = 60
_MINUTES_PER_HOUR = 60
_NOT_PROVEN_FIELD_COUNT = 2
_INFERRED_FIELD_COUNT = 3


class InferredDateTag(NamedTuple):
    """Parsed ``date_tag`` for an inferred-local (or not-proven-UTC) CreateDate decision."""

    container_tag: str
    evidence: str
    offset: timedelta | None  # None iff evidence is :data:`NOT_PROVEN_UTC`


def format_offset(offset: timedelta) -> str:
    """Format a UTC offset as ``+HH:MM`` / ``-HH:MM`` (minute granularity)."""
    total = int(offset.total_seconds())
    if total % _SECONDS_PER_MINUTE != 0:
        message = f"offset must be whole minutes, got {offset!r}"
        raise ValueError(message)
    sign = "+" if total >= 0 else "-"
    total = abs(total)
    hours, minutes = divmod(total // _SECONDS_PER_MINUTE, _MINUTES_PER_HOUR)
    return f"{sign}{hours:02d}:{minutes:02d}"


def parse_offset(text: str) -> timedelta:
    """Parse ``+HH:MM`` / ``-HH:MM`` into a :class:`~datetime.timedelta`."""
    match = _OFFSET_RE.fullmatch(text.strip())
    if match is None:
        message = f"not an offset: {text!r}"
        raise ValueError(message)
    sign, hours_s, minutes_s = match.groups()
    hours, minutes = int(hours_s), int(minutes_s)
    if minutes >= _MINUTES_PER_HOUR:
        message = f"not an offset: {text!r}"
        raise ValueError(message)
    delta = timedelta(hours=hours, minutes=minutes)
    return delta if sign == "+" else -delta


def format_inferred_date_tag(container_tag: str, evidence: str, offset: timedelta) -> str:
    """Build a machine-parseable inferred-local ``date_tag``.

    Round-trips with :func:`parse_inferred_date_tag`. ``container_tag`` and ``evidence``
    must not contain :data:`INFERRED_DATE_TAG_SEP`.
    """
    if INFERRED_DATE_TAG_SEP in container_tag or INFERRED_DATE_TAG_SEP in evidence:
        message = (
            f"provenance fields must not contain {INFERRED_DATE_TAG_SEP!r}: "
            f"{container_tag!r} / {evidence!r}"
        )
        raise ValueError(message)
    if evidence == NOT_PROVEN_UTC:
        message = "use format_not_proven_utc_tag when UTC is not proven"
        raise ValueError(message)
    return (
        f"{container_tag}{INFERRED_DATE_TAG_SEP}{evidence}"
        f"{INFERRED_DATE_TAG_SEP}{format_offset(offset)}"
    )


def format_not_proven_utc_tag(container_tag: str) -> str:
    """Record that a container stamp was **not proven UTC** and was treated as local.

    Form: ``{container_tag}|not_proven_utc``. This is the common, usually-correct path for
    cameras that write local wall-clock into ``CreateDate`` - not a failure flag.
    """
    if INFERRED_DATE_TAG_SEP in container_tag:
        message = f"container_tag must not contain {INFERRED_DATE_TAG_SEP!r}: {container_tag!r}"
        raise ValueError(message)
    return f"{container_tag}{INFERRED_DATE_TAG_SEP}{NOT_PROVEN_UTC}"


def parse_inferred_date_tag(tag: str) -> InferredDateTag | None:
    """Parse an inferred / not-proven-UTC ``date_tag``, or ``None`` if the shape is wrong.

    Accepts ``CreateDate|filename:VID_|+05:30`` and ``CreateDate|not_proven_utc``.
    Plain EXIF tags such as ``CreationDate`` or ``DateTimeOriginal`` return ``None``.
    """
    parts = tag.split(INFERRED_DATE_TAG_SEP)
    if len(parts) == _NOT_PROVEN_FIELD_COUNT:
        container, evidence = parts
        if not container or evidence != NOT_PROVEN_UTC:
            return None
        return InferredDateTag(container, evidence, None)
    if len(parts) == _INFERRED_FIELD_COUNT:
        container, evidence, offset_text = parts
        if not container or not evidence or evidence == NOT_PROVEN_UTC or not offset_text:
            return None
        try:
            offset = parse_offset(offset_text)
        except ValueError:
            return None
        return InferredDateTag(container, evidence, offset)
    return None


#: Metadata tags consulted in order. ``DateTimeOriginal`` is the photo capture time.
#: ``CreationDate`` (Apple's ``com.apple.quicktime.creationdate``) carries a video's local
#: recording moment *with* its UTC offset, so it is preferred over the ``*CreateDate`` family,
#: which the QuickTime spec stores in UTC and which therefore names the wrong wall-clock (and,
#: near midnight, the wrong day/month) for anything shot away from UTC.
#:
#: Single-conversion rule (the osxphotos lesson): ``CreationDate``'s wall-clock is *already*
#: local, so :func:`parse_exif_datetime` simply drops the offset and keeps it -- we never add
#: the offset back on. Re-applying it is the classic double-conversion bug. The UTC ``*Create``
#: tags are a last resort; for videos they may be shifted by the evidence ladder below when
#: stronger evidence proves UTC-ness and supplies an offset.
#: Date-bearing tags this chain **refuses to read, permanently**, and why.
#:
#: These are not "not yet supported" -- they are wrong answers that look like right ones, and an
#: absence is easy to erode back in by someone adding "one more fallback". Named here so the
#: refusal is a decision on the record with a test behind it.
#:
#: * ``ModifyDate`` / ``FileModifyDate`` -- the moment the file was last *edited* or *written*,
#:   never the moment it was taken. A photo cropped in 2024 carries a 2024 ModifyDate beside a
#:   2014 DateTimeOriginal, so reading it silently re-dates edited photos. Worse, it is present
#:   precisely when DateTimeOriginal is absent: probed against the real 2,269-file library, of
#:   the files with no DateTimeOriginal, **every one** carried a ModifyDate. A chain that treats
#:   "any date beats none" would reach for it exactly where it is least trustworthy.
#: * Filesystem mtime is refused by the same reasoning and is already forbidden by §1 -- a
#:   Takeout export, a cloud re-sync or a restore rewrites it, dating a library to the day it
#:   moved. Every comparable organizer falls back to it, and it is their most-reported dating
#:   complaint (`docs/date-layering-gap-check.md`).
REFUSED_DATE_TAGS: frozenset[str] = frozenset({"ModifyDate", "FileModifyDate"})

DATE_TAGS: tuple[str, ...] = (
    "DateTimeOriginal",
    "CreationDate",
    "CreateDate",
    "MediaCreateDate",
    "TrackCreateDate",
)


#: QuickTime/MP4 container stamps that the spec stores in UTC (cameras often ignore this).
#: Ladder applies only when one of these won and DTO / CreationDate did not.
_UTC_CONTAINER_TAGS: frozenset[str] = frozenset(
    {"CreateDate", "MediaCreateDate", "TrackCreateDate"}
)

#: Video suffixes for the ladder. Duplicated from organizer to avoid an import cycle
#: (organizer imports ``resolve_capture_datetime``).
_VIDEO_EXTENSIONS: frozenset[str] = frozenset(
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

# ---------------------------------------------------------------------------
# Video UTC CreateDate ladder (backlog ``(uu)``)
#
# Safety bounds (pinned; mutation-tested in a later commit):
# * Half-hour grid, ±14 h, excluding 0 -- civil zones include half-hours (IST +05:30);
#   ±14 h covers the full civil range (UTC-12 .. UTC+14); offset 0 would re-label a
#   no-op as inferred.
# * Epsilon 3 s -- soak Android clips matched within 1-2 s after duration accounting;
#   3 s allows rounding without admitting a neighbouring half-hour.
# * Unique match only -- two offsets inside epsilon => refuse (never guess).
# ---------------------------------------------------------------------------

#: Match tolerance for filename↔CreateDate(+duration) and GPS↔CreateDate.
FILENAME_OFFSET_EPSILON = timedelta(seconds=3)
GPS_UTC_EPSILON = timedelta(seconds=5)

#: Half-hour steps spanning ±14 h (civil timezone extremes).
FILENAME_OFFSET_STEP = timedelta(minutes=30)
FILENAME_OFFSET_MAX = timedelta(hours=14)

#: Contemporaneous-still corroboration window (rung 5). Never invents an offset.
STILL_CORROBORATION_WINDOW = timedelta(minutes=2)

_DEVICE_LOCAL_TIME = re.compile(
    r"(?P<prefix>VID|IMG)_(?P<ymd>\d{8})_(?P<hms>\d{6})",
    re.IGNORECASE,
)
_DURATION_SECONDS = re.compile(r"^(\d+(?:\.\d+)?)\s*s$", re.IGNORECASE)
_GPS_TIME = re.compile(r"^(\d{1,2}):(\d{2}):(\d{2})")


_DURATION_HMS_PARTS = 3
_DURATION_MS_PARTS = 2
_GPS_TIME_PARTS = 3


def parse_duration(raw: Any) -> timedelta | None:
    """Parse an exiftool ``Duration`` value (``0:02:38``, ``2.52 s``, or numeric seconds)."""
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        if raw < 0:
            return None
        return timedelta(seconds=float(raw))
    text = str(raw).strip()
    if not text:
        return None
    seconds_match = _DURATION_SECONDS.fullmatch(text)
    if seconds_match is not None:
        return timedelta(seconds=float(seconds_match.group(1)))
    parts = text.split(":")
    try:
        if len(parts) == _DURATION_HMS_PARTS:
            hours, minutes, secs = (int(parts[0]), int(parts[1]), float(parts[2]))
            return timedelta(hours=hours, minutes=minutes, seconds=secs)
        if len(parts) == _DURATION_MS_PARTS:
            minutes, secs = int(parts[0]), float(parts[1])
            return timedelta(minutes=minutes, seconds=secs)
    except ValueError:
        return None
    return None


def candidate_filename_offsets() -> tuple[timedelta, ...]:
    """Half-hour offsets in ±14 h, excluding zero (a no-op must not become inferred)."""
    steps = int(FILENAME_OFFSET_MAX / FILENAME_OFFSET_STEP)
    return tuple(i * FILENAME_OFFSET_STEP for i in range(-steps, steps + 1) if i != 0)


def unique_filename_offset(
    create_utc: datetime,
    filename_local: datetime,
    duration: timedelta | None,
    *,
    epsilon: timedelta = FILENAME_OFFSET_EPSILON,
) -> timedelta | None:
    """Return the unique half-hour offset matching filename (+optional duration), or None.

    Accepts offset ``O`` when ``|CreateDate + O - filename| <= epsilon`` (start-stamped
    CreateDate) or ``|CreateDate + O - filename - duration| <= epsilon`` (end-stamped
    CreateDate, Android). Two distinct matches => refuse.
    """
    eps = epsilon.total_seconds()
    hits: set[timedelta] = set()
    for offset in candidate_filename_offsets():
        local_end = create_utc + offset
        if abs((local_end - filename_local).total_seconds()) <= eps:
            hits.add(offset)
        if (
            duration is not None
            and abs((local_end - filename_local - duration).total_seconds()) <= eps
        ):
            hits.add(offset)
    if len(hits) == 1:
        return next(iter(hits))
    return None


def device_filename_local(name: str) -> tuple[datetime, str] | None:
    """Local wall-clock from ``VID_`` / ``IMG_`` ``YYYYMMDD_HHMMSS``, or None.

    Messenger ``-WA`` names are refused (delivery time, not capture). Search anywhere in
    the name so organized prefixes like ``20140817_045424_VID_…`` still match.
    """
    if is_messenger_filename(name):
        return None
    match = _DEVICE_LOCAL_TIME.search(name)
    if match is None:
        return None
    ymd, hms = match.group("ymd"), match.group("hms")
    try:
        when = datetime.strptime(f"{ymd}{hms}", "%Y%m%d%H%M%S")
    except ValueError:
        return None
    prefix = match.group("prefix").upper()
    return when, f"filename:{prefix}_"


def gps_utc_datetime(metadata: dict[str, Any]) -> datetime | None:
    """Combine ``GPSDateStamp`` + ``GPSTimeStamp`` into a naive UTC instant, or None."""
    date_raw = metadata.get("GPSDateStamp")
    time_raw = metadata.get("GPSTimeStamp")
    if date_raw is None or time_raw is None:
        return None
    date_text = str(date_raw).strip().replace("-", ":")
    try:
        day = datetime.strptime(date_text, "%Y:%m:%d")
    except ValueError:
        return None
    if isinstance(time_raw, (list, tuple)) and len(time_raw) >= _GPS_TIME_PARTS:
        hours, minutes, secs = int(time_raw[0]), int(time_raw[1]), float(time_raw[2])
    else:
        time_match = _GPS_TIME.match(str(time_raw).strip())
        if time_match is None:
            return None
        hours = int(time_match.group(1))
        minutes = int(time_match.group(2))
        secs = float(time_match.group(3))
    try:
        return day.replace(hour=hours, minute=minutes, second=int(secs), microsecond=0)
    except ValueError:
        return None


def gps_confirms_utc(
    metadata: dict[str, Any],
    create_utc: datetime,
    *,
    epsilon: timedelta = GPS_UTC_EPSILON,
) -> bool:
    """True when GPS UTC ≈ CreateDate (rung 3). Proves UTC-ness; never supplies an offset."""
    gps = gps_utc_datetime(metadata)
    if gps is None:
        return False
    return abs((gps - create_utc).total_seconds()) <= epsilon.total_seconds()


def stills_corroborate_local(
    local_start: datetime,
    neighbor_stills: Sequence[datetime],
    *,
    window: timedelta = STILL_CORROBORATION_WINDOW,
) -> bool | None:
    """Rung 5: corroborate a *proposed* local start against nearby still capture times.

    Returns ``True`` if any still lies within ``window`` of ``local_start``, ``False`` if
    stills were supplied but none are near, and ``None`` when ``neighbor_stills`` is empty.

    **Never returns or invents an offset.** Callers may refuse on ``False``; they must not
    derive ``O`` from stills alone.
    """
    if not neighbor_stills:
        return None
    bound = window.total_seconds()
    return any(abs((still - local_start).total_seconds()) <= bound for still in neighbor_stills)


_TZ_SUFFIX = re.compile(r"[+-]\d{2}:?\d{2}$")

# Filename date conventions, tried in this order.
#   YYYY-MM-DD  Telegram mobile save-to-gallery: photo_2024-01-15_12-30-45.jpg
#   YYYYMMDD    Android/WhatsApp: IMG-20250804-WA0020.jpg, Screenshot_20260721_001427.png
#   DD-MM-YYYY  Telegram Desktop export: photo_1@29-10-2021_09-30-00.jpg
_ISO_DATE = re.compile(r"(?<!\d)((?:19|20)\d{2})-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])(?!\d)")
_COMPACT_DATE = re.compile(r"(?<!\d)((?:19|20)\d{2})(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])(?!\d)")
_EURO_DATE = re.compile(r"(?<!\d)(0[1-9]|[12]\d|3[01])-(0[1-9]|1[0-2])-((?:19|20)\d{2})(?!\d)")


def parse_exif_datetime(raw: Any) -> datetime | None:
    """Parse an exiftool date string such as ``2026:07:21 00:14:27.753+02:00``.

    Sub-second precision and timezone offsets are discarded: they carry no information
    relevant to which YYYY-MM folder a file belongs in, and dropping them keeps every
    comparison in the same naive local-wall-clock space.
    """
    if raw is None:
        return None

    text = str(raw).strip()
    # exiftool emits all-zero dates for cameras that wrote an empty field.
    if not text or text.startswith("0000"):
        return None

    core = text.split(".", 1)[0].strip()
    core = core.removesuffix("Z").strip()
    core = _TZ_SUFFIX.sub("", core).strip()

    try:
        return datetime.strptime(core, "%Y:%m:%d %H:%M:%S")
    except ValueError:
        return None


def date_from_filename(name: str) -> datetime | None:
    """Recover a date from a filename convention, or return None.

    Returns midnight on the matched day; filename conventions rarely encode a
    trustworthy time, and only the year/month are used for placement anyway.
    """
    iso = _ISO_DATE.search(name)
    if iso:
        return _safe_date(int(iso.group(1)), int(iso.group(2)), int(iso.group(3)))

    compact = _COMPACT_DATE.search(name)
    if compact:
        return _safe_date(int(compact.group(1)), int(compact.group(2)), int(compact.group(3)))

    euro = _EURO_DATE.search(name)
    if euro:
        return _safe_date(int(euro.group(3)), int(euro.group(2)), int(euro.group(1)))

    return None


def _filename_capture_date(name: str) -> datetime | None:
    """A filename date only when the filename plausibly encodes a **capture** date.

    A messenger convention is refused outright. ``IMG-20250804-WA0020.jpg`` carries the day
    WhatsApp *delivered* the file, not the day the photo was taken: forward a 2015 holiday photo
    today and that name says today. Filing by it would silently move a photo years from where it
    belongs, which is worse than `Undated/` -- an honest gap the user can fix beats a confident
    wrong answer (`IMPLEMENTATION_STANDARDS.md` §1, dates are never guessed).

    Screenshot names such as ``Screenshot_20260721_001427.png`` are deliberately still trusted:
    a screenshot's filename stamp *is* its capture moment, written by the device that made it.
    That is why this refuses **messenger conventions** rather than the date patterns themselves -
    the two share a pattern (``YYYYMMDD``) but not a meaning.
    """
    if is_messenger_filename(name):
        return None
    return date_from_filename(name)


def _safe_date(year: int, month: int, day: int) -> datetime | None:
    try:
        return datetime(year, month, day)  # noqa: DTZ001 - naive by design, see module docstring
    except ValueError:
        return None


#: **Tier A - hard sentinels.** Container/epoch zero values that are never a real capture
#: instant: a file carrying one has an *unset* field, not an early date. Rejected at every
#: tier and **independently of the sanity window below** - that independence is the point.
#: The window used to be the only thing rejecting these, so lowering its floor (as we did, to
#: honour genuine scanned-archive dates) would otherwise have quietly re-admitted 1904.
#: Proven necessary by the metadata-chain corpus: naive parsers report these unset fields as
#: real dates, which would misfile clips to 1904/1970 - strictly worse than ``Undated/``.
HARD_SENTINELS: frozenset[datetime] = frozenset(
    {
        datetime(1904, 1, 1, 0, 0, 0),  # noqa: DTZ001 - ISO-BMFF/QuickTime zero epoch
        datetime(1970, 1, 1, 0, 0, 0),  # noqa: DTZ001 - Unix zero epoch
    }
)

#: **Tier B - suspect camera defaults.** The days a camera's clock falls back to when its
#: coin cell dies. Unlike Tier A these **can** be genuine (millennium photos exist), so they
#: are *accepted and counted*, never rejected - the user reviews, we do not guess.
#: **Exact midnight is the discriminator**: a real photo taken at 00:00:00 sharp on one of
#: these days is vanishingly rare next to a reset clock.
SUSPECT_DEFAULT_DAYS: frozenset[tuple[int, int, int]] = frozenset(
    {
        (2000, 1, 1),
        (1999, 12, 31),
        (1980, 1, 1),
    }
)

#: Sources whose dates are a *camera clock* reading, and so can carry a Tier B reset value.
#: ``FILENAME`` is deliberately excluded: :func:`date_from_filename` returns **midnight by
#: construction**, so the exact-midnight test would flag every legitimately filename-dated
#: file on those days. ``TAKEOUT_UPLOAD`` is an upload time, not a camera clock.
_CLOCK_SOURCES = frozenset({DateSource.EXIF, DateSource.TAKEOUT, DateSource.INFERRED_LOCAL})


def is_hard_sentinel(value: datetime) -> bool:
    """True when ``value`` is a container/epoch zero, i.e. an unset field rather than a date."""
    return value in HARD_SENTINELS


def is_suspect_default(value: datetime | None, source: DateSource) -> bool:
    """True when a camera-clock date lands exactly on midnight of a known reset day.

    Accepted, never rejected - callers surface the count so a user can review. See
    :data:`SUSPECT_DEFAULT_DAYS` and :data:`_CLOCK_SOURCES`.
    """
    if value is None or source not in _CLOCK_SOURCES:
        return False
    is_midnight = (value.hour, value.minute, value.second, value.microsecond) == (0, 0, 0, 0)
    return is_midnight and (value.year, value.month, value.day) in SUSPECT_DEFAULT_DAYS


class _EmbeddedDate(NamedTuple):
    """What the embedded-metadata tier found.

    ``saw_sentinel`` is not a detail: it is the difference between "this file has no date"
    and "this file's only date was an epoch zero we refused", which is what lets the report
    tell the user the truth instead of the first, misleading half of it.
    """

    value: datetime | None
    tag: str | None
    saw_sentinel: bool


class _Candidate(NamedTuple):
    """One tier's answer: the date it offers (or ``None``), and how to label it if it wins."""

    value: datetime | None
    source: DateSource
    tag: str | None = None


def _local(value: datetime | None, tz_offset: timedelta | None) -> datetime | None:
    """A sidecar's UTC epoch as local wall-clock, or ``None`` when absent.

    Centralizes the single-conversion rule: every sidecar time passes through
    :func:`~truestill_core.takeout.local_naive` exactly once, here.
    """
    return None if value is None else local_naive(value, tz_offset)


def _is_video(path: Path, metadata: dict[str, Any]) -> bool:
    mime = str(metadata.get("MIMEType") or "").lower()
    if mime.startswith("video/"):
        return True
    return path.suffix.lower() in _VIDEO_EXTENSIONS


def _timezone_from_metadata(metadata: dict[str, Any]) -> timedelta | None:
    raw = metadata.get("TimeZone")
    if raw is None:
        return None
    text = str(raw).strip()
    # Canon sometimes appends a city name; take the leading ±HH:MM.
    match = re.match(r"([+-]\d{2}:\d{2})", text)
    if match is None:
        return None
    try:
        return parse_offset(match.group(1))
    except ValueError:
        return None


class LadderHit(NamedTuple):
    """Typed result of one video-UTC ladder rung: local wall-clock + offset + evidence token."""

    local: datetime
    offset: timedelta
    evidence: str


def try_rung_timezone(metadata: dict[str, Any], create_utc: datetime) -> LadderHit | None:
    """Rung 2: MakerNotes ``TimeZone`` shifts container UTC to camera-local."""
    tz = _timezone_from_metadata(metadata)
    if tz is None:
        return None
    return LadderHit(local=create_utc + tz, offset=tz, evidence="TimeZone")


def try_rung_filename_duration(
    path: Path, metadata: dict[str, Any], create_utc: datetime
) -> LadderHit | None:
    """Rung 4: unique half-hour match of filename local (+duration) against CreateDate."""
    device = device_filename_local(path.name)
    if device is None:
        return None
    filename_local, fn_evidence = device
    duration = parse_duration(metadata.get("Duration"))
    offset = unique_filename_offset(create_utc, filename_local, duration)
    if offset is None:
        return None
    return LadderHit(local=filename_local, offset=offset, evidence=fn_evidence)


def _infer_video_local(
    path: Path,
    metadata: dict[str, Any],
    create_utc: datetime,
    container_tag: str,
) -> _Candidate | None:
    """Apply the video UTC ladder as an ordered sequence of named rung attempts.

    Rung 1 (CreationDate) wins earlier in ``DATE_TAGS`` and never reaches here.
    Rung 3 (GPS) only enriches evidence - it never invents an offset.
    Rung 5 (stills) is a separate corroboration helper and is not called here.
    """
    gps_ok = gps_confirms_utc(metadata, create_utc)
    for hit in (
        try_rung_timezone(metadata, create_utc),
        try_rung_filename_duration(path, metadata, create_utc),
    ):
        if hit is None:
            continue
        evidence = f"GPSDateStamp+{hit.evidence}" if gps_ok else hit.evidence
        return _Candidate(
            hit.local,
            DateSource.INFERRED_LOCAL,
            format_inferred_date_tag(container_tag, evidence, hit.offset),
        )
    return None


def _exif_tier(path: Path, metadata: dict[str, Any], embedded: _EmbeddedDate) -> _Candidate:
    """EXIF tier, with the video CreateDate ladder when a UTC-container tag won."""
    if embedded.value is None or embedded.tag is None:
        return _Candidate(None, DateSource.EXIF, None)
    if embedded.tag in _UTC_CONTAINER_TAGS and _is_video(path, metadata):
        inferred = _infer_video_local(path, metadata, embedded.value, embedded.tag)
        if inferred is not None:
            return inferred
        return _Candidate(
            embedded.value,
            DateSource.EXIF,
            format_not_proven_utc_tag(embedded.tag),
        )
    return _Candidate(embedded.value, DateSource.EXIF, embedded.tag)


def _embedded_datetime(metadata: dict[str, Any]) -> _EmbeddedDate:
    """First parseable, sane embedded date with the tag that supplied it.

    One pass over :data:`DATE_TAGS` (5 entries, ordered by trust); the first usable hit wins.
    """
    saw_sentinel = False
    for tag in DATE_TAGS:
        parsed = parse_exif_datetime(metadata.get(tag))
        if parsed is None:
            continue
        if is_hard_sentinel(parsed):
            saw_sentinel = True
            continue
        if _MIN_SANE_YEAR <= parsed.year <= _MAX_SANE_YEAR:
            return _EmbeddedDate(parsed, tag, saw_sentinel)
    return _EmbeddedDate(None, None, saw_sentinel)


#: EXIF dates outside this range are treated as a reset/garbage clock, so a Takeout date
#: (if any) is preferred over them even in the default EXIF-wins mode. The floor is 1900,
#: not the film era's start: scanned negatives and slides carry genuine early dates, and
#: sending them to ``Undated/`` was a silent data-quality loss. Tier A above is what keeps
#: the epoch sentinels out, so this floor is free to be generous.
_MIN_SANE_YEAR = 1900
_MAX_SANE_YEAR = 2100


def resolve_capture_datetime(
    path: Path,
    metadata: dict[str, Any],
    *,
    takeout: TakeoutSidecar | None = None,
    tz_offset: timedelta | None = None,
    prefer_takeout: bool = False,
) -> tuple[datetime | None, DateSource, str | None]:
    """Return ``(datetime, source, tag)`` for a file.

    Priority (default): sane embedded EXIF -> Takeout ``photoTakenTime`` -> Takeout
    ``creationTime`` (approximate) -> filename convention -> none. ``prefer_takeout`` flips
    the first two, for libraries whose dates were fixed inside Google Photos but whose
    embedded EXIF stayed wrong. Takeout times are converted from UTC to local exactly once.

    For videos whose winning embedded tag is a UTC container stamp (``CreateDate`` family),
    an evidence ladder may shift to local wall-clock (``DateSource.INFERRED_LOCAL``). With
    no proof of UTC, the digits stay as local and ``date_tag`` records
    ``{tag}|not_proven_utc`` (usually correct - not a defect).

    **Tier A sentinels are refused at every tier**, not just the EXIF one - a zero-epoch is
    not a date whichever field produced it. When the chain exhausts *because* a sentinel was
    refused, the source is :attr:`DateSource.REJECTED_SENTINEL` rather than
    :attr:`DateSource.NONE`, so a report can say "a date was found and refused" instead of
    silently implying the file never had one. Tier B (suspect camera defaults) does not
    appear here at all: those dates are **accepted**, and callers flag them via
    :func:`is_suspect_default`.
    """
    embedded = _embedded_datetime(metadata)
    exif_tier = _exif_tier(path, metadata, embedded)
    taken_tier = _Candidate(
        _local(takeout.taken_at if takeout else None, tz_offset), DateSource.TAKEOUT
    )

    # The tier order *is* the policy, so it reads as ordered data rather than nested branches.
    # Every tier is evaluated up front; the two that can be skipped cost ~2.6 us combined
    # (measured: 1.44 us for a no-match filename scan, 1.13 us for a tz shift), against a
    # per-file budget dominated by hashing in the milliseconds. Not worth lazy plumbing.
    tiers: tuple[_Candidate, ...] = (
        (taken_tier, exif_tier) if prefer_takeout else (exif_tier, taken_tier)
    ) + (
        _Candidate(
            _local(takeout.created_at if takeout else None, tz_offset),
            DateSource.TAKEOUT_UPLOAD,
        ),
        _Candidate(_filename_capture_date(path.name), DateSource.FILENAME),
    )

    saw_sentinel = embedded.saw_sentinel
    for tier in tiers:
        if tier.value is None:
            continue
        if is_hard_sentinel(tier.value):  # Tier A applies to every tier, not just EXIF
            saw_sentinel = True
            continue
        return tier.value, tier.source, tier.tag

    return None, (DateSource.REJECTED_SENTINEL if saw_sentinel else DateSource.NONE), None
