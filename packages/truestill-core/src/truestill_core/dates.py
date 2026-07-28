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
from typing import Any, NamedTuple

from truestill_core.categorize import is_messenger_filename
from truestill_core.models import DateSource
from truestill_core.takeout import TakeoutSidecar, local_naive

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
_CLOCK_SOURCES = frozenset({DateSource.EXIF, DateSource.TAKEOUT})


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

    **Tier A sentinels are refused at every tier**, not just the EXIF one - a zero-epoch is
    not a date whichever field produced it. When the chain exhausts *because* a sentinel was
    refused, the source is :attr:`DateSource.REJECTED_SENTINEL` rather than
    :attr:`DateSource.NONE`, so a report can say "a date was found and refused" instead of
    silently implying the file never had one. Tier B (suspect camera defaults) does not
    appear here at all: those dates are **accepted**, and callers flag them via
    :func:`is_suspect_default`.
    """
    embedded = _embedded_datetime(metadata)
    exif_tier = _Candidate(embedded.value, DateSource.EXIF, embedded.tag)
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
