"""Video UTC CreateDate ladder and half-hour offset grid (backlog ``(uu)`` / ``(aab)``).

Moved out of ``dates.py`` so capture-date resolution stays the generic chain and this module
owns the video-only evidence ladder. No dating policy lives here beyond the ladder's own
safety bounds.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, NamedTuple

from truestill_core.categorize import is_messenger_filename
from truestill_core.date_provenance import format_inferred_date_tag, parse_offset

#: QuickTime/MP4 container stamps that the spec stores in UTC (cameras often ignore this).
#: Ladder applies only when one of these won and DTO / CreationDate did not.
UTC_CONTAINER_TAGS: frozenset[str] = frozenset({"CreateDate", "MediaCreateDate", "TrackCreateDate"})

#: Video suffixes for the ladder. Duplicated from organizer to avoid an import cycle
#: (organizer imports ``resolve_capture_datetime``).
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

# ---------------------------------------------------------------------------
# Video UTC CreateDate ladder (backlog ``(uu)``)
#
# Safety bounds (pinned; mutation-tested):
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


def is_video(path: Path, metadata: dict[str, Any]) -> bool:
    """True when MIME or suffix says this path is a video."""
    mime = str(metadata.get("MIMEType") or "").lower()
    if mime.startswith("video/"):
        return True
    return path.suffix.lower() in VIDEO_EXTENSIONS


def timezone_from_metadata(metadata: dict[str, Any]) -> timedelta | None:
    """Parse MakerNotes ``TimeZone`` (leading ``±HH:MM``), or None."""
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


class VideoLocalInference(NamedTuple):
    """Winning ladder result ready for the EXIF tier: local wall-clock + provenance tag."""

    local: datetime
    date_tag: str


def try_rung_timezone(metadata: dict[str, Any], create_utc: datetime) -> LadderHit | None:
    """Rung 2: MakerNotes ``TimeZone`` shifts container UTC to camera-local."""
    tz = timezone_from_metadata(metadata)
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


def infer_video_local(
    path: Path,
    metadata: dict[str, Any],
    create_utc: datetime,
    container_tag: str,
) -> VideoLocalInference | None:
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
        return VideoLocalInference(
            local=hit.local,
            date_tag=format_inferred_date_tag(container_tag, evidence, hit.offset),
        )
    return None
