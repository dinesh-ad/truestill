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
    # LAST, and that position is the rule rather than an ordering accident (`(acm)`). RIFF
    # `DateCreated` is **date-only**, so it resolves to midnight; a file carrying both it and a
    # real capture time must keep the time. The two AVIs in the corpora are exactly that pair -
    # one has only this, the other has a precise `CreateDate` - so putting it anywhere higher
    # would collapse a known-good 20:52 to 00:00.
    "DateCreated",
)

_TZ_SUFFIX = re.compile(r"[+-]\d{2}:?\d{2}$")

# Filename date conventions, tried in this order.
#   YYYY-MM-DD  Telegram mobile save-to-gallery: photo_2024-01-15_12-30-45.jpg
#   YYYYMMDD    Android/WhatsApp: IMG-20250804-WA0020.jpg, Screenshot_20260721_001427.png
#   DD-MM-YYYY  Telegram Desktop export: photo_1@29-10-2021_09-30-00.jpg
#   a whole run  date AND time with no separator: 2014815120755.jpg (_RUN_TIMESTAMP, last)
_ISO_DATE = re.compile(r"(?<!\d)((?:19|20)\d{2})-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])(?!\d)")
_COMPACT_DATE = re.compile(r"(?<!\d)((?:19|20)\d{2})(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])(?!\d)")
_EURO_DATE = re.compile(r"(?<!\d)(0[1-9]|[12]\d|3[01])-(0[1-9]|1[0-2])-((?:19|20)\d{2})(?!\d)")

#: A digit run that is **entirely** a date and a time, tried last. `2014815120755.jpg`,
#: `ch01_20130704123045.mp4`, `..._BURST20190413181239_COVER.jpg`, `DJI_20230715120000_0001_D.JPG`.
#:
#: **THIS IS TWO REPAIRS AND EITHER ALONE RECOVERS NOTHING. Read this before "simplifying" it.**
#: The shape that motivated it is `2014815120755` = `2014` + `8` + `15` + `120755`:
#:
#: 1. `_COMPACT_DATE`'s ``(?!\d)`` fence refuses it, because the time runs straight on to the date.
#: 2. ``(0[1-9]|1[0-2])`` refuses it, because the month is **one digit**.
#:
#: Relaxing only the fence still fails on the month; relaxing only the month still fails on the
#: fence. Measured on the reference library: **614 files of this one shape, and either repair on
#: its own recovers 0 of them.** Someone will make one of the two, measure no improvement, and
#: conclude the analysis was wrong (`date-resolver-corpus-measurement.md` §2.1).
#:
#: Matching the **whole run** rather than loosening the fence is what keeps this safe: a fence
#: relaxed in place would let an 8-digit window inside a 17-digit Facebook id match. Requiring the
#: run to be exactly ``YYYY + M|MM + D|DD + HHMMSS`` leaves every one of the library's 997
#: correctly-silent names silent - measured, not assumed.
_RUN_TIMESTAMP = re.compile(r"(?<!\d)(\d{12,14})(?!\d)")

#: The floor for :data:`_RUN_TIMESTAMP` only, and deliberately **not** :data:`_MIN_SANE_YEAR`.
#:
#: Justified by what *writes* these names, not by whether a date is plausible: no device wrote a
#: bare ``YYYYMMDDHHMMSS`` filename before 2000. A scanned negative reaches the resolver through
#: EXIF or a separated name (`2013-07-04`), never a bare 14-digit run, so the generous 1900 floor
#: that exists for those users buys nothing here and costs something real.
#:
#: What it costs: a 13-digit **epoch-millisecond** filename can look like this shape once epoch-ms
#: values start with `19` or `20`. Measured over one name per day, 2015-2060: a 1900 floor
#: misreads 300 of 16,436 and can first fire in **2030**; this floor misreads **150** and cannot
#: fire until **2033-05**. Every known epoch-ms convention (`FB_IMG_`, `mmexport`, `wx_camera_`,
#: `line_`) is refused by the messenger list before reaching here - measured 0 false readings - so
#: the residual is a **bare, unprefixed epoch-ms name after 2033-05**. Disclosed, not hidden.
_RUN_MIN_YEAR = 2000


def parse_exif_datetime(raw: Any) -> datetime | None:
    """Parse an exiftool date string such as ``2026:07:21 00:14:27.753+02:00``.

    Sub-second precision and timezone offsets are discarded: they carry no information
    relevant to which YYYY-MM folder a file belongs in, and dropping them keeps every
    comparison in the same naive local-wall-clock space.
    """
    if raw is None:
        return None

    # NUL is stripped from the EDGES because `str.strip()` does not remove it - it is not
    # whitespace in Python - so a reader that hands back EXIF's 20th byte would otherwise cost
    # the file its date entirely. Edges only, deliberately: an *embedded* NUL still refuses
    # rather than being spliced into a plausible-looking string. No NUL-bearing value appeared
    # in the 895 real tag readings measured, so this hardens measured parser behaviour rather
    # than a field anyone has seen (`date-resolver-corpus-measurement.md` §4.1).
    text = str(raw).strip().strip("\x00").strip()
    # exiftool emits all-zero dates for cameras that wrote an empty field.
    if not text or text.startswith("0000"):
        return None

    core = text.split(".", 1)[0].strip()
    core = core.removesuffix("Z").strip()
    core = _TZ_SUFFIX.sub("", core).strip()

    try:
        return datetime.strptime(core, "%Y:%m:%d %H:%M:%S")
    except ValueError:
        return _parse_uncommon(text)


#: A trailing zone abbreviation some writers append after the offset: `...+02:00 DST`.
_DST_TAIL = re.compile(r"\s+[A-Z]{2,4}$")
#: Fractional seconds, and **only** where they follow a real clock. The EXIF path above strips on
#: the first `.` in the whole string, which is why it cannot be reused here: `2008.07.10 15:16:55`
#: would become `2008`.
_FRACTION = re.compile(r"(?<=:\d\d)\.\d+")
#: Year-first numeric date, optional numeric time. `/` is admitted **because the year leads** -
#: that is what makes it unambiguous, and `12/29/93` cannot match this at all.
_UNCOMMON = re.compile(
    r"^(\d{4})[:.\-/](\d{1,2})[:.\-/](\d{1,2})(?:[ T]+(\d{1,2}):(\d{2})(?::(\d{2}))?)?$"
)
#: A bare `YYYYMMDD`, which some scanners write into a date tag whole.
_UNCOMMON_COMPACT = re.compile(r"^(\d{4})(\d{2})(\d{2})$")


def _parse_uncommon(text: str) -> datetime | None:
    """Date forms the wild contains that EXIF does not spell. `(add)`, measured across 1,077 real
    tag readings in three corpora.

    **Reached only after the EXIF spelling fails, so nothing that parses today changes.** That
    ordering is the whole safety argument and is why this is an addition rather than a rewrite.

    **What is deliberately NOT here, and why each is a separate ruling:**

    * ``12/29/93 13:52:11`` (12 readings), ``12/5/95 10:44 PM``, ``2/5/14``, ``12/09/14``,
      ``02-Aug-99`` - **ambiguous.** Reading them needs a US-or-EU choice, which is exactly the
      wrong-answer class `date-resolver-corpus-measurement.md` §3.2 exists to avoid. §1: dates are
      never guessed, and `Undated/` is the honest answer.
    * ``Tue Dec 14 09:54:11 2004`` (4 readings), ``Monday, September 11, 2000, 2:45:40 PM`` -
      **locale-dependent.** `%a`/`%b` resolve against `LC_TIME`, so these parse on an English
      machine and fail on a French one: the same file landing in a different folder depending on
      the computer reading it, which is the failure this project exists not to have. Five readings
      do not buy a hand-rolled English month table.

    Everything accepted here is numeric and **year-first**, so no reading of it is in question.
    """
    body = _DST_TAIL.sub("", text).strip()
    body = body.removesuffix("Z").strip()
    body = _TZ_SUFFIX.sub("", body).strip()
    body = _FRACTION.sub("", body).strip()

    # Two patterns rather than one with optional separators, deliberately: making the separators
    # optional would let a SEVEN-digit run split as `2002`+`09`+`4`, inventing a reading of a
    # number that is not a date. The compact form must be exactly eight digits or nothing.
    clock: tuple[int, int, int] = (0, 0, 0)
    if (match := _UNCOMMON.match(body)) is not None:
        clock = (int(match.group(4) or 0), int(match.group(5) or 0), int(match.group(6) or 0))
    elif (match := _UNCOMMON_COMPACT.match(body)) is None:
        return None
    year, month, day = (int(g) for g in match.group(1, 2, 3))
    try:
        return datetime(year, month, day, *clock)  # noqa: DTZ001 - naive local, see module doc
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

    return _date_from_timestamp_run(name)


def _date_from_timestamp_run(name: str) -> datetime | None:
    """A day from a digit run that is entirely ``YYYY + M|MM + D|DD + HHMMSS``, or ``None``.

    **Two valid readings refuse rather than pick one.** ``2014121120755`` is both 2014-01-21 and
    2014-12-01 - one digit short of deciding - and §1 says dates are never guessed. `Undated/` is
    an honest gap a user can fix; a coin-flip month is a day that never happened.

    Returns midnight like the rest of the tier (see :func:`date_from_filename`), even though these
    names *do* carry a time. Keeping one rule for the whole tier is why `is_suspect_default` can
    exclude ``FILENAME`` wholesale; the discarded time is recorded in
    `date-resolver-corpus-measurement.md` §6 rather than half-used here.
    """
    days: set[datetime] = set()
    for run in _RUN_TIMESTAMP.findall(name):
        for month_width in (1, 2):
            for day_width in (1, 2):
                if len(run) != 4 + month_width + day_width + 6:
                    continue
                cut = 4 + month_width
                end = cut + day_width
                day = _safe_date(int(run[:4]), int(run[4:cut]), int(run[cut:end]))
                if day is None or day.year < _RUN_MIN_YEAR or day.year > _MAX_SANE_YEAR:
                    continue
                # The trailing six digits must be a real wall clock, or this run is not a
                # timestamp at all - it is the cheapest evidence separating one from a serial.
                hour, minute, second = (int(run[end:][i : i + 2]) for i in (0, 2, 4))
                if hour < 24 and minute < 60 and second < 60:  # noqa: PLR2004 - a clock
                    days.add(day)
    return days.pop() if len(days) == 1 else None


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
    #: A value parsed, was neither sentinel nor future, and fell outside the sanity window.
    #: Same job as the two above: the difference between "no date" and "a date we refused".
    saw_early: bool = False


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
    saw_early = False
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
            return _EmbeddedDate(parsed, tag, saw_sentinel, saw_future, saw_early)
        # Outside the window. Only the FLOOR can reach this today - `is_future` above refuses
        # anything past `now`, which is well below `_MAX_SANE_YEAR`. The ceiling half is kept
        # rather than removed because it is the guard that survives if `FUTURE_TOLERANCE` ever
        # changes, and a dead branch that is the fallback for a live one is not dead code.
        saw_early = True
    return _EmbeddedDate(None, None, saw_sentinel, saw_future, saw_early)


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
#: **TWO days, and the first of them is not slack - it is the width of the world.** The gap
#: between where a photo is TAKEN and where it is IMPORTED is at most **26 hours**: UTC+14
#: (Kiritimati) to UTC-12 (Baker Island). A photo taken moments ago on one side carries a local
#: wall clock up to 26 hours ahead of the importing computer's naive `datetime.now()`, which is
#: the only machine-clock reading anywhere in this chain. **Do not trim this below 26 hours.**
#:
#: Measured rather than reasoned (P41, 2026-08-10): at one day, a photo taken in Kiritimati and
#: imported on a UTC-12 machine went to ``Undated/`` as ``REJECTED_FUTURE``, while the same file
#: imported on UTC+14 or UTC+05:30 landed correctly. That is a folder decided by the importing
#: computer's clock rather than by the photograph - the failure this project exists not to have,
#: and the one Adobe's own date-folder bug has had open since 2011.
#:
#: The second day is the original allowance and its reasoning is unchanged: clock skew is
#: ordinary - a camera minutes fast, a device that never adjusted for travel - and refusing those
#: would send correctly-dated photos to ``Undated/``, which is both worse and far commoner than
#: accepting a date a few hours out. Two days remains tight enough to catch the case this was
#: written for: a library reporting a range ending in **2051**.
FUTURE_TOLERANCE = timedelta(days=2)


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
    # No tier loop counterpart: the sanity window is an embedded-tier rule. A filename date
    # cannot be below the floor (`_ISO_DATE`/`_EURO_DATE` require `19|20`, `_RUN_TIMESTAMP` a
    # tighter floor still), and a Takeout epoch zero is caught as a sentinel.
    saw_early = embedded.saw_early
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

    # Precedence: future > sentinel > early > none. `early` is last **so that every case which
    # already had an answer keeps it byte-identical** - this member exists to name a silence, not
    # to re-label refusals that were already named.
    if saw_future:
        return None, DateSource.REJECTED_FUTURE, None
    if saw_sentinel:
        return None, DateSource.REJECTED_SENTINEL, None
    if saw_early:
        return None, DateSource.REJECTED_EARLY, None
    return None, DateSource.NONE, None
