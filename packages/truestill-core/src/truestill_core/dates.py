"""Capture-date resolution.

Priority, deliberately: embedded metadata first, filename convention second, nothing
third. Filesystem mtime is never consulted -- Google Photos download and Takeout zips
carry the *download* time in the filesystem timestamp, so trusting mtime would file an
entire library under the day it was exported.

Video UTC CreateDate ladder and offset grid live in :mod:`truestill_core.video_utc`.
Inferred-local ``date_tag`` wire format lives in :mod:`truestill_core.date_provenance`.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, NamedTuple

from truestill_core.categorize import is_messenger_filename
from truestill_core.date_provenance import format_not_proven_utc_tag
from truestill_core.models import DateSource
from truestill_core.takeout import TakeoutSidecar, local_naive
from truestill_core.video_utc import UTC_CONTAINER_TAGS, infer_video_local, is_video

#: Metadata tags consulted in order. ``DateTimeOriginal`` is the photo capture time.
#: ``CreationDate`` (Apple's ``com.apple.quicktime.creationdate``) carries a video's local
#: recording moment *with* its UTC offset, so it is preferred over the ``*CreateDate`` family,
#: which the QuickTime spec stores in UTC and which therefore names the wrong wall-clock (and,
#: near midnight, the wrong day/month) for anything shot away from UTC.
#:
#: Single-conversion rule (the osxphotos lesson): ``CreationDate``'s wall-clock is *already*
#: local, so :func:`parse_exif_datetime` simply drops the offset and keeps it -- we never add
#: the offset back on. Re-applying it is the classic double-conversion bug. The UTC ``*Create``
#: tags are a last resort; for videos they may be shifted by the evidence ladder in
#: :mod:`truestill_core.video_utc` when stronger evidence proves UTC-ness and supplies an
#: offset.
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
    saw_future: bool = False


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


def _exif_tier(path: Path, metadata: dict[str, Any], embedded: _EmbeddedDate) -> _Candidate:
    """EXIF tier, with the video CreateDate ladder when a UTC-container tag won."""
    if embedded.value is None or embedded.tag is None:
        return _Candidate(None, DateSource.EXIF, None)
    if embedded.tag in UTC_CONTAINER_TAGS and is_video(path, metadata):
        inferred = infer_video_local(path, metadata, embedded.value, embedded.tag)
        if inferred is not None:
            return _Candidate(inferred.local, DateSource.INFERRED_LOCAL, inferred.date_tag)
        return _Candidate(
            embedded.value,
            DateSource.EXIF,
            format_not_proven_utc_tag(embedded.tag),
        )
    return _Candidate(embedded.value, DateSource.EXIF, embedded.tag)


def _embedded_datetime(metadata: dict[str, Any], *, now: datetime) -> _EmbeddedDate:
    """First parseable, sane, not-yet-happened embedded date with the tag that supplied it.

    One pass over :data:`DATE_TAGS` (5 entries, ordered by trust); the first usable hit wins.

    **The future check is here as well as in the tier loop, and both are needed.** This one
    lets a valid ``CreateDate`` win when ``DateTimeOriginal`` is impossible - the fall-through
    *within* the embedded tier. The loop's copy covers the tiers this function never sees, the
    Takeout timestamp and the filename. The sentinel check is duplicated for exactly the same
    reason and has been since it was written.
    """
    saw_sentinel = False
    saw_future = False
    for tag in DATE_TAGS:
        parsed = parse_exif_datetime(metadata.get(tag))
        if parsed is None:
            continue
        if is_hard_sentinel(parsed):
            saw_sentinel = True
            continue
        if is_future(parsed, now=now):
            saw_future = True
            continue
        if _MIN_SANE_YEAR <= parsed.year <= _MAX_SANE_YEAR:
            return _EmbeddedDate(parsed, tag, saw_sentinel, saw_future)
    return _EmbeddedDate(None, None, saw_sentinel, saw_future)


#: **The floor and the ceiling are deliberately asymmetric, and tidying them into symmetry
#: would be a regression.** The ceiling is now `now` (see :data:`FUTURE_TOLERANCE`), which is
#: *logically* impossible to exceed: no photograph was taken after this moment, for anyone,
#: ever, so it needs no year and it stays correct forever. The floor is only *improbable*, and
#: for one real group of users it is wrong: someone scanning family negatives sets
#: `DateTimeOriginal` to when the shutter fired - 1962 - which is exactly the distinction
#: `DateTimeDigitized` exists to draw. Refusing a future date costs nothing, because the value
#: was impossible; refusing an early one discards a **true** date belonging to the users who
#: curated theirs most carefully. Tier A already catches the zeroed-clock cases a tighter floor
#: would find, so tightening it would buy nothing and risk that. Ruled 2026-08-03.
#:
#: EXIF dates outside this range are treated as a reset/garbage clock, so a Takeout date
#: (if any) is preferred over them even in the default EXIF-wins mode. The floor is 1900,
#: not the film era's start: scanned negatives and slides carry genuine early dates, and
#: sending them to ``Undated/`` was a silent data-quality loss. Tier A above is what keeps
#: the epoch sentinels out, so this floor is free to be generous.
_MIN_SANE_YEAR = 1900
_MAX_SANE_YEAR = 2100

#: How far ahead of "now" a capture date may sit before it is refused as impossible.
#:
#: **A day, and the asymmetry is deliberate.** Clock skew is ordinary - a camera minutes fast, a
#: timezone-unaware stamp read as UTC when the shooter was ahead of it, a device that never
#: adjusted for travel. Refusing those would send correctly-dated photos to ``Undated/``, which
#: is both worse and far commoner than accepting a date a few hours out. A day is generous
#: enough that no real photo is refused, and tight enough to catch the case this was written
#: for: a library reporting a range ending in **2051**.
FUTURE_TOLERANCE = timedelta(days=1)


def is_future(value: datetime, *, now: datetime) -> bool:
    """Whether ``value`` claims a capture instant that has not happened yet.

    Impossible evidence, not merely improbable. No library can recover a date someone
    overwrote, so the only honest response is to refuse it and let the chain fall through -
    the same principle the messenger sent-date rule already applies.
    """
    return value > now + FUTURE_TOLERANCE


def resolve_capture_datetime(  # noqa: PLR0913 - each argument is a distinct evidence source
    path: Path,
    metadata: dict[str, Any],
    *,
    takeout: TakeoutSidecar | None = None,
    tz_offset: timedelta | None = None,
    prefer_takeout: bool = False,
    now: datetime | None = None,
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
    # Naive local, deliberately, and `DTZ005` is suppressed for that reason rather than
    # silenced: every EXIF datetime in this module is naive local wall-clock, so an aware
    # `datetime.now(UTC)` could not be compared with one without raising. The comparison is
    # local-to-local, which is what a camera clock actually records.
    moment = now if now is not None else datetime.now()  # noqa: DTZ005 - naive local by design
    embedded = _embedded_datetime(metadata, now=moment)
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
    saw_future = embedded.saw_future
    for tier in tiers:
        if tier.value is None:
            continue
        if is_hard_sentinel(tier.value):  # Tier A applies to every tier, not just EXIF
            saw_sentinel = True
            continue
        if is_future(tier.value, now=moment):
            # Beside the sentinel check for the same reason it is here rather than inside
            # `_embedded_datetime`: a filename like `20510301_...` and a Takeout timestamp can
            # both be in the future, and the old plausibility band reached neither.
            saw_future = True
            continue
        return tier.value, tier.source, tier.tag

    if saw_future:
        return None, DateSource.REJECTED_FUTURE, None
    return None, (DateSource.REJECTED_SENTINEL if saw_sentinel else DateSource.NONE), None
