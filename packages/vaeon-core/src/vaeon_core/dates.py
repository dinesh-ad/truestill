"""Capture-date resolution.

Priority, deliberately: embedded metadata first, filename convention second, nothing
third. Filesystem mtime is never consulted -- Google Photos download and Takeout zips
carry the *download* time in the filesystem timestamp, so trusting mtime would file an
entire library under the day it was exported.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from vaeon_core.models import DateSource
from vaeon_core.takeout import TakeoutSidecar, local_naive

#: Metadata tags consulted in order. ``DateTimeOriginal`` is the photo capture time.
#: ``CreationDate`` (Apple's ``com.apple.quicktime.creationdate``) carries a video's local
#: recording moment *with* its UTC offset, so it is preferred over the ``*CreateDate`` family,
#: which the QuickTime spec stores in UTC and which therefore names the wrong wall-clock (and,
#: near midnight, the wrong day/month) for anything shot away from UTC.
#:
#: Single-conversion rule (the osxphotos lesson): ``CreationDate``'s wall-clock is *already*
#: local, so :func:`parse_exif_datetime` simply drops the offset and keeps it -- we never add
#: the offset back on. Re-applying it is the classic double-conversion bug. The UTC ``*Create``
#: tags are a last resort only, kept as-is; we do not try to convert them using another tag's
#: offset (that guesses a zone the file never recorded).
DATE_TAGS: tuple[str, ...] = (
    "DateTimeOriginal",
    "CreationDate",
    "CreateDate",
    "MediaCreateDate",
    "TrackCreateDate",
)

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


def _safe_date(year: int, month: int, day: int) -> datetime | None:
    try:
        return datetime(year, month, day)  # noqa: DTZ001 - naive by design, see module docstring
    except ValueError:
        return None


def _exif_datetime(metadata: dict[str, Any]) -> tuple[datetime, str] | None:
    """First parseable, sane embedded date, with the tag that supplied it."""
    for tag in DATE_TAGS:
        parsed = parse_exif_datetime(metadata.get(tag))
        if parsed is not None and _MIN_SANE_YEAR <= parsed.year <= _MAX_SANE_YEAR:
            return parsed, tag
    return None


#: EXIF dates outside this range are treated as a reset/garbage clock, so a Takeout date
#: (if any) is preferred over them even in the default EXIF-wins mode.
_MIN_SANE_YEAR = 1990
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
    """
    exif = _exif_datetime(metadata)
    taken = (
        local_naive(takeout.taken_at, tz_offset)
        if takeout is not None and takeout.taken_at is not None
        else None
    )

    if prefer_takeout:
        if taken is not None:
            return taken, DateSource.TAKEOUT, None
        if exif is not None:
            return exif[0], DateSource.EXIF, exif[1]
    else:
        if exif is not None:
            return exif[0], DateSource.EXIF, exif[1]
        if taken is not None:
            return taken, DateSource.TAKEOUT, None

    if takeout is not None and takeout.created_at is not None:
        return local_naive(takeout.created_at, tz_offset), DateSource.TAKEOUT_UPLOAD, None

    from_name = date_from_filename(path.name)
    if from_name is not None:
        return from_name, DateSource.FILENAME, None

    return None, DateSource.NONE, None
