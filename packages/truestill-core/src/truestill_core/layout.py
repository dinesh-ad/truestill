"""The destination folder layout and its one routing/rendering seam.

A :class:`LayoutTemplate` parses and renders one tokenized path. A :class:`LayoutScheme` owns
the templates for ordinary timeline files, named events, trips and labelled side bins, while
``classify`` selects the placement from categorization evidence. Planning, previews, organize
and migration all use that same seam.

Grammar is ``/``-separated literal segments plus ``{token}`` placeholders:

* ``{category}`` is the derived label (``Camera``, ``WhatsApp``, ...). The low-level grammar
  accepts it for the fixed side-bin template; user-supplied timeline templates reject it.
* ``{yyyy} {yy} {mm} {mon} {month} {dd}`` derive from capture time, or from an event/trip start
  when rendering the shared parent.
* ``{event}`` explicitly places a named-event folder; without it, event and trip levels append
  through the render seam.

Undated files collapse all date-derived segments to one ``Undated`` folder. Event and trip
members stay consolidated under their start period rather than splitting at a month boundary.
The default sends ordinary Camera files to ``YYYY/YYYY-MM/YYYY-MM - Everyday/``, named events
to ``YYYY/YYYY-MM/YYYY-MM-DD - Name/``, heavy un-evented days to
``YYYY/YYYY-MM/YYYY-MM-DD - Everyday/``, and non-camera sources to
``<Label>/YYYY/YYYY-MM/`` side bins.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from pathlib import PurePosixPath
from typing import Protocol, Self, assert_never

from truestill_core.events import event_dirname
from truestill_core.models import UNDATED_DIRNAME


class CatalogLike(Protocol):
    """The slice of `Catalog` the pin needs, so layout does not import the catalog module."""

    def get_setting(self, key: str) -> str | None: ...
    def set_setting(self, key: str, value: str) -> None: ...
    def has_placed_files(self) -> bool: ...


_TOKEN = re.compile(r"\{([a-z_]+)\}")

#: Date tokens and their strftime codes. A segment mentioning any of these is "date-derived".
_DATE_TOKENS: dict[str, str] = {
    "yyyy": "%Y",
    "yy": "%y",
    "mm": "%m",
    "mon": "%b",
    "month": "%B",
    "dd": "%d",
}
_NON_DATE_TOKENS: frozenset[str] = frozenset({"category", "event"})

#: Every token the v1 grammar accepts.
KNOWN_TOKENS: frozenset[str] = frozenset(_DATE_TOKENS) | _NON_DATE_TOKENS

#: The un-evented timeline of the default layout - the year first, months that name themselves,
#: and an ``Everyday`` bucket so ordinary photos do not sit loose among a month's event folders.
#: The category-first predecessor and the evidence for this shape are recorded in
#: `docs/default-layout-research.md`.
DEFAULT_TEMPLATE_STRING = "{yyyy}/{yyyy}-{mm}/{yyyy}-{mm} - Everyday"

#: Heavy un-evented days (backlog ``(gg)``): same year/month parents, but a dated Everyday
#: folder instead of the monthly bucket. Product shape, not a user DSL branch -
#: `docs/adaptive-day-folder-research.md`.
DEFAULT_DAY_BUCKET_TEMPLATE_STRING = "{yyyy}/{yyyy}-{mm}/{yyyy}-{mm}-{dd} - Everyday"

#: Catalog settings key for the Everyday day-folder threshold. Missing/invalid →
#: :data:`DEFAULT_EVERYDAY_DAY_THRESHOLD`.
EVERYDAY_DAY_THRESHOLD_KEY = "layout.everyday_day_threshold"

#: Default: days with more un-evented timeline photos than this get :data:`Placement.DAY_BUCKET`.
#: Researched in `docs/adaptive-day-folder-research.md` (OnePoll/Mixbook ~23/occasion; ~20/day).
DEFAULT_EVERYDAY_DAY_THRESHOLD = 40

#: The catalog settings key under which a library's chosen timeline template is persisted.
LAYOUT_TEMPLATE_KEY = "layout_template"

#: The evented timeline template, when it differs from the un-evented one (the "Year / Event"
#: preset puts an event under the year but an ordinary photo under the month). Absent means
#: "same as the timeline", which is true of every other layout and of every legacy library.
#: A second key rather than a structured value keeps every already-stored template readable
#: exactly as it was written.
LAYOUT_EVENT_TEMPLATE_KEY = "layout_event_template"

#: Characters illegal in a path *component* on Windows (and thus banned for portability),
#: minus ``/`` which is our segment separator. ``_VALUE`` also bans ``/`` so a token value
#: can never inject an extra directory level.
_LITERAL_ILLEGAL = re.compile(r'[<>:"\\|?*\x00-\x1f]')
_VALUE_ILLEGAL = re.compile(r'[<>:"/\\|?*\x00-\x1f]')

#: Windows reserved device names (case-insensitive, reserved even with an extension).
_WIN_RESERVED: frozenset[str] = frozenset(
    {"con", "prn", "aux", "nul"}
    | {f"com{i}" for i in range(1, 10)}
    | {f"lpt{i}" for i in range(1, 10)}
)

#: A rendered relative path longer than this (before the drive root) earns a preview warning;
#: Windows' classic limit is 260 and we leave headroom for the destination root and filename.
PATH_LENGTH_WARN = 200


class EventNaming(StrEnum):
    """How a named event's folder is spelled."""

    #: ``2014-08-20 - Goa Trip`` - readable when the folder is copied away from its parents.
    READABLE = "readable"
    #: ``20140820_goa-trip`` - used when an event has no human name recorded.
    SLUG = "slug"


#: Longest event *name* allowed in a folder, in **bytes** -- deliberately far below
#: :data:`MAX_COMPONENT_BYTES`, because the name shares its component with a date prefix and a
#: separator, and a 255-byte trip name is a worse outcome than a shortened one.
MAX_EVENT_NAME = 60


def event_folder(
    start: datetime, slug: str, name: str | None, naming: EventNaming, notes: list[str]
) -> str:
    """The event folder name, path-safe by construction.

    ``name`` is user input that becomes a directory, so it gets exactly what a template literal
    gets: illegal characters replaced, trailing dots and spaces trimmed, Windows reserved names
    defused, length bounded. Everything it changes is appended to ``notes`` - which is what makes
    it **visible at preview time** rather than discovered later on the filesystem
    (`IMPLEMENTATION_STANDARDS.md` §9, never-silent).
    """
    if naming is EventNaming.SLUG or not name:
        return event_dirname(start, slug)
    cleaned = _truncate_bytes(_sanitize_value(name), MAX_EVENT_NAME).strip().rstrip(" .")
    if cleaned != name:
        notes.append(f"event name {name!r} was adjusted to {cleaned!r} to be path-safe")
    # "Usable" means it still carries a letter or digit. Emptiness is not the test: the
    # sanitizer *replaces* illegal characters rather than dropping them, so a name of "///"
    # survives as "___" -- truthy, and a folder nobody could recognise as their trip.
    if not any(character.isalnum() for character in cleaned):
        notes.append(f"event name {name!r} left nothing usable; used the slug instead")
        return event_dirname(start, slug)
    folder = f"{start:%Y-%m-%d} - {cleaned}"
    if _is_reserved(folder):
        folder = f"_{folder}"
        notes.append(f"event folder {folder!r} avoided a Windows reserved name")
    return folder


@dataclass(frozen=True, slots=True)
class EventFolder:
    """One event's folder name, after collision handling."""

    key: str  #: the caller's identifier for this event (a slug, a signature, a row id)
    folder: str
    note: str | None = None  #: set when the name had to be disambiguated


def disambiguate_event_folders(
    entries: Sequence[tuple[str, datetime, str, str | None]],
    naming: EventNaming = EventNaming.READABLE,
) -> list[EventFolder]:
    """Render event folders and make same-date name collisions distinguishable.

    Two events on one date whose names sanitize to the same string -- ``Goa Trip`` and
    ``Goa/Trip``, or ``Goa Trip`` and ``goa trip`` on a case-insensitive filesystem -- render one
    folder name, and their files would merge silently. That is **truestill's own constraint, not
    the filesystem's**: it was created by making event folders human-readable, so it is
    truestill's job to detect it *before* anything is written.

    Later collisions get a ``(2)``, ``(3)`` suffix and a note. A numeric suffix rather than a
    hash on purpose: it keeps the name the user chose and admits the clash, where a hash would
    destroy the readability this whole change exists to deliver.

    ``entries`` is ``(key, start, slug, name)``. **O(m)** across *m* events - one pass, one dict.
    """
    seen: dict[str, int] = {}
    out: list[EventFolder] = []
    for key, start, slug, name in entries:
        notes: list[str] = []
        folder = event_folder(start, slug, name, naming, notes)
        # Case-insensitively, because two folders differing only in case collide on APFS/NTFS.
        marker = folder.casefold()
        count = seen.get(marker, 0) + 1
        seen[marker] = count
        note = notes[0] if notes else None
        if count > 1:
            disambiguated = f"{folder} ({count})"
            out.append(
                EventFolder(
                    key=key,
                    folder=disambiguated,
                    note=(
                        f"another event on {start:%Y-%m-%d} already uses {folder!r}; "
                        f"this one becomes {disambiguated!r}"
                    ),
                )
            )
            continue
        out.append(EventFolder(key=key, folder=folder, note=note))
    return out


class TemplateError(ValueError):
    """Raised when a layout template is malformed or references an unknown token."""


def _is_reserved(component: str) -> bool:
    """Whether a path component is a Windows reserved device name (stem, case-insensitive)."""
    stem = component.split(".", 1)[0].strip().lower()
    return stem in _WIN_RESERVED


#: Every filesystem in play (ext4, APFS, NTFS) caps a path component at 255 **bytes**, not
#: characters -- a distinction that only shows up on non-Latin names, where one character can
#: cost four bytes. See `docs/filename-safety-research.md`.
MAX_COMPONENT_BYTES = 255


def _truncate_bytes(value: str, limit: int) -> str:
    """Shorten ``value`` to at most ``limit`` UTF-8 bytes, never splitting a character.

    Slicing encoded bytes blindly would leave an invalid trailing sequence, which surfaces as a
    mangled name or an OS error rather than a clean shortening.
    """
    encoded = value.encode("utf-8")
    if len(encoded) <= limit:
        return value
    return encoded[:limit].decode("utf-8", errors="ignore")


def _sanitize_value(value: str) -> str:
    """Make a rendered token value safe as a single path component (never raises).

    Illegal characters (incl. ``/`` and ``\\``) become ``_`` so a value cannot inject a
    directory level; trailing dots/spaces are trimmed (Windows silently drops them, so ``Trip.``
    and ``Trip`` would otherwise be the same directory under two names); the result is
    normalized to **NFC** so a name typed on macOS and the same name typed on Linux produce one
    directory rather than two that look identical; and it is capped at
    :data:`MAX_COMPONENT_BYTES`.
    """
    cleaned = _VALUE_ILLEGAL.sub("_", value).strip().rstrip(" .")
    cleaned = unicodedata.normalize("NFC", cleaned)
    return _truncate_bytes(cleaned, MAX_COMPONENT_BYTES).strip().rstrip(" .")


def resolve_template(stored: str | None) -> LayoutTemplate:
    """The active template: the stored one if a catalog has set it, else the default."""
    return LayoutTemplate.parse(stored) if stored else DEFAULT_TEMPLATE


def pin_existing_layout(catalog: CatalogLike) -> bool:
    """Write down a library's current layout before a default change could move it.

    A layout is only ever persisted when a user explicitly sets one, so a library organized
    with the defaults stores nothing and renders through whatever :data:`DEFAULT_TEMPLATE` is
    at the time. Changing that constant would therefore silently re-shape the **next** run of
    every existing library - new files in the new structure, the existing tree in the old one,
    no prompt and no migration. That is exactly the split the "new default applies forward,
    migration offered never forced" rule exists to prevent, and the rule needs a mechanism.

    The trigger is deliberately narrow: **files have already been placed, and no layout is
    stored.** A library that has only ever been scanned or previewed has nothing on disk to
    protect and receives the new default like any fresh library
    (`catalog.has_placed_files` documents why that signal, and not "the catalog has rows").

    Returns whether it pinned, so the caller can announce it once. Idempotent: a catalog that
    already stores a layout - pinned or chosen - is never touched again.
    """
    if catalog.get_setting(LAYOUT_TEMPLATE_KEY) is not None:
        return False
    if not catalog.has_placed_files():
        return False
    catalog.set_setting(LAYOUT_TEMPLATE_KEY, DEFAULT_TEMPLATE_STRING)
    if DEFAULT_PRESET.timeline_evented != DEFAULT_PRESET.timeline:
        catalog.set_setting(LAYOUT_EVENT_TEMPLATE_KEY, DEFAULT_PRESET.timeline_evented)
    return True


def effective_layout_string(catalog: CatalogLike) -> str | None:
    """The layout in force right now - **pure, never writes.**

    Nothing stored means the default is in force, and `resolve_scheme` falls back to the whole
    :data:`DEFAULT_SCHEME` rather than to a single string -- the default's evented and un-evented
    shapes differ, and a string cannot carry that. Returning a string here instead would silently
    flatten events into the `Everyday` bucket, which is exactly what it did when tried.

    Pure. Previews run on read-only paths where writing a setting would break the dry-run
    invariant (`IMPLEMENTATION_STANDARDS.md` §5), so a preview cannot pin -- and if it resolved
    differently from the run that follows, the plan a user approved would not be the plan that
    executed.
    """
    return catalog.get_setting(LAYOUT_TEMPLATE_KEY)


@dataclass(frozen=True)
class RenderContext:
    """Everything :meth:`LayoutTemplate.render` needs about one file."""

    category: str
    captured_at: datetime | None = None
    #: ``(start, slug)`` when the file belongs to a named event, else ``None``.
    event: tuple[datetime, str] | None = None
    #: The event's human name (``events.name``). `slugify` casefolds and hyphenates, so a
    #: readable folder cannot be rebuilt from the slug - the name has to travel with it.
    event_name: str | None = None
    #: ``(start, slug)`` when the file's *day* belongs to a confirmed trip, else ``None``. A trip
    #: day claims every photo taken that day (`trip-grouping-research.md` §2), so this takes
    #: precedence over ``event`` at the router (`classify`) - a caller does not need to also
    #: clear ``event`` for a trip-claimed day, but should not rely on that; the two are mutually
    #: exclusive in intent.
    trip: tuple[datetime, str] | None = None
    #: The trip's human name. Same reasoning as ``event_name`` - `slugify` is lossy.
    trip_name: str | None = None
    #: True when the caller has already counted this capture day as over the Everyday
    #: day-folder threshold (`docs/adaptive-day-folder-research.md`). Set **outside**
    #: :func:`classify` after one day-count pass - the router itself never counts or opens a
    #: catalog.
    heavy_day: bool = False

    @property
    def date(self) -> datetime | None:
        """The date the tokens resolve from: a trip's start, else an event's, else capture.

        A trip or event that spans a month (or, for a trip, several) boundary still files under
        its own **start** month - one object, one place, never split because a member's own date
        happens to fall later (`IMPLEMENTATION_STANDARDS.md` §4's cross-month consolidation rule,
        now shared by both shapes rather than re-derived for the second one).
        """
        if self.trip is not None:
            return self.trip[0]
        return self.event[0] if self.event is not None else self.captured_at


@dataclass(frozen=True)
class LayoutTemplate:
    """A parsed, validated destination-folder template."""

    template: str
    segments: tuple[str, ...]
    #: How this template spells an event folder. Carried here so organize, migrate and preview
    #: cannot disagree about it.
    event_naming: EventNaming = EventNaming.READABLE

    @classmethod
    def parse(
        cls, template: str, *, event_naming: EventNaming = EventNaming.READABLE
    ) -> LayoutTemplate:
        """Parse and fully validate a template, or raise :class:`TemplateError`.

        Everything checkable from the template *alone* is caught here, so an invalid template is
        rejected at set/preview time and can never fail a run: unknown tokens, empty segments,
        illegal characters in literal text, and fully-literal segments that are Windows reserved
        names. Data-dependent risks (empty token values, over-length, case collisions) are
        surfaced by :func:`preview_scheme` (via :func:`_preview_rows`) instead, since they
        depend on the files being organized.
        """
        cleaned = template.strip().strip("/")
        if not cleaned:
            message = "layout template is empty"
            raise TemplateError(message)
        segments = tuple(cleaned.split("/"))
        for segment in segments:
            if not segment:
                message = f"layout template has an empty path segment: {template!r}"
                raise TemplateError(message)
            for token in _TOKEN.findall(segment):
                if token not in KNOWN_TOKENS:
                    known = ", ".join(sorted(KNOWN_TOKENS))
                    message = f"unknown template token {{{token}}}; known tokens: {known}"
                    raise TemplateError(message)
            literal = _TOKEN.sub("", segment)  # the fixed text a user typed around the tokens
            if _LITERAL_ILLEGAL.search(literal):
                message = f"segment {segment!r} contains a character not allowed in a path"
                raise TemplateError(message)
            if not _TOKEN.search(segment) and _is_reserved(segment):
                message = f"segment {segment!r} is a reserved name on Windows"
                raise TemplateError(message)
        return cls(template=cleaned, segments=segments, event_naming=event_naming)

    def has_event_token(self) -> bool:
        """Whether the template places events explicitly (vs. relying on the append rule)."""
        return any("event" in _TOKEN.findall(segment) for segment in self.segments)

    def render(self, context: RenderContext) -> PurePosixPath:
        """Render the destination *directory* (no filename) for ``context``. Never raises."""
        return self._render(context)[0]

    def _render(self, context: RenderContext) -> tuple[PurePosixPath, list[str]]:
        """Render, also returning human-readable notes (empty tokens, sanitized values)."""
        date = context.date
        parts: list[str] = []
        notes: list[str] = []
        undated_done = False
        for segment in self.segments:
            tokens = _TOKEN.findall(segment)
            if date is None and any(token in _DATE_TOKENS for token in tokens):
                if not undated_done:
                    parts.append(UNDATED_DIRNAME)
                    undated_done = True
                continue
            rendered = self._render_segment(segment, context, date, notes)
            if rendered:
                if _is_reserved(rendered):
                    rendered = f"_{rendered}"
                    notes.append(f"segment {rendered!r} avoided a Windows reserved name")
                parts.append(rendered)
            elif tokens:
                notes.append(f"segment {segment!r} was empty and dropped")

        path = PurePosixPath(*parts) if parts else PurePosixPath()
        if context.trip is not None:
            path = path / self._trip_segments(context, notes)
        elif context.event is not None and not self.has_event_token():
            path = path / event_folder(*context.event, context.event_name, self.event_naming, notes)
        return path, notes

    def _trip_segments(self, context: RenderContext, notes: list[str]) -> PurePosixPath:
        """The trip's own header folder, then the individual day - always two levels (§2).

        The header is spelled by :func:`event_folder`, unchanged - a trip header is a dated,
        named folder exactly like an event's, so it reuses the same naming/sanitization/
        reserved-name logic rather than a second copy of it. The day level is the file's own
        capture date (never the trip's start, which the base segments above already used via
        `RenderContext.date`) in full ISO form, per §3(b) - `2014-08-16`, not a bare `16`, so the
        folder still says what it is once copied away from its parent.

        There is no ``{trip}`` token (`trip-grouping-research.md` §8 rejects one: a conditional
        inside a template is the DSL the one-seam rule forbids), so this unconditional append is
        the *only* way a trip renders - the same shape the event append already has, extended by
        one level rather than replaced.
        """
        assert context.trip is not None
        start, slug = context.trip
        header = event_folder(start, slug, context.trip_name, self.event_naming, notes)
        # Not reachable today: a trip day's membership is derived from captured_at in the first
        # place (trip-grouping-research.md §11), so a trip-claimed file is never undated. Kept
        # explicit rather than assumed, since `render` promises it never raises.
        day = (
            context.captured_at.strftime("%Y-%m-%d")
            if context.captured_at is not None
            else UNDATED_DIRNAME
        )
        if _is_reserved(day):
            day = f"_{day}"
            notes.append(f"segment {day!r} avoided a Windows reserved name")
        return PurePosixPath(header, day)

    def _render_segment(
        self, segment: str, context: RenderContext, date: datetime | None, notes: list[str]
    ) -> str:
        def substitute(match: re.Match[str]) -> str:
            token = match.group(1)
            if token == "category":
                value = context.category
            elif token == "event":
                value = (
                    event_folder(*context.event, context.event_name, self.event_naming, notes)
                    if context.event is not None
                    else ""
                )
            else:
                value = format(date, _DATE_TOKENS[token]) if date is not None else ""
            if not value:
                notes.append(f"token {{{token}}} was empty")
            return _sanitize_value(value)

        return _TOKEN.sub(substitute, segment)


@dataclass(frozen=True)
class PreviewRow:
    """One rendered sample path plus any data-dependent warnings for it."""

    path: PurePosixPath
    warnings: tuple[str, ...]


def _preview_rows(
    fulls: Sequence[PurePosixPath],
    render_notes: Sequence[Sequence[str]],
) -> list[PreviewRow]:
    """Attach data-dependent path-risk warnings to already-rendered sample paths.

    Surfaces exactly the risks that cannot be judged from the template alone: notes already
    collected during render (empty token values), a relative path approaching the Windows
    length limit, and two samples that collide on a case-insensitive filesystem. All are
    warnings, not errors: rendering is total, so a run never fails here.

    The single home for "is this path risky" - shared by :func:`preview_scheme` so the rule
    cannot drift between two copies.
    """
    lowered: dict[str, int] = {}
    collisions: set[int] = set()
    for i, full in enumerate(fulls):
        key = full.as_posix().lower()
        if key in lowered:
            collisions.add(i)
            collisions.add(lowered[key])
        lowered[key] = i

    rows: list[PreviewRow] = []
    for i, (full, notes) in enumerate(zip(fulls, render_notes, strict=True)):
        warnings = list(notes)
        if len(full.as_posix()) > PATH_LENGTH_WARN:
            warnings.append(f"path is {len(full.as_posix())} chars, near the Windows 260 limit")
        if i in collisions:
            warnings.append("collides with another sample on a case-insensitive filesystem")
        rows.append(PreviewRow(path=full, warnings=tuple(warnings)))
    return rows


#: The default layout, parsed once.
DEFAULT_TEMPLATE = LayoutTemplate.parse(DEFAULT_TEMPLATE_STRING)
DEFAULT_DAY_BUCKET_TEMPLATE = LayoutTemplate.parse(DEFAULT_DAY_BUCKET_TEMPLATE_STRING)

#: The rule whose files are the timeline. Exactly one rule in the chain produces camera photos
#: (`categorize.make_device_rule`), and routing keys on the **rule, not the label**: under
#: ``--by-device`` the label is the hardware name, so a label test would send a whole library
#: into a side bin.
TIMELINE_RULE = "device"

#: Where everything that is not the timeline goes. **Fixed, never user-editable.** The side bin
#: is a quarantine - screenshots and messenger images stay out of the photo timeline - so no
#: template a user can type may reshape a side bin into a timeline path.
SIDE_BIN_TEMPLATE_STRING = "{category}/{yyyy}/{yyyy}-{mm}"
SIDE_BIN_TEMPLATE = LayoutTemplate.parse(SIDE_BIN_TEMPLATE_STRING)

#: Tokens forbidden in the editable timeline template. Rejecting ``{category}`` at **input** is
#: what makes category-first and category-last structurally impossible for the timeline, rather
#: than merely absent from the preset list.
TIMELINE_FORBIDDEN_TOKENS: frozenset[str] = frozenset({"category"})


def parse_timeline_template(template: str) -> LayoutTemplate:
    """Parse a timeline template a **user** supplied, rejecting ``{category}``.

    Deliberately not the same door as :meth:`LayoutTemplate.parse`. Input is validated strictly;
    **stored** values stay leniently parsed, because a library organized before the year-first
    default has a category-first template written down (`pin_existing_layout`) and must keep
    resolving. Rejecting at load would break exactly the libraries the pin exists to protect.
    """
    parsed = LayoutTemplate.parse(template)
    for segment in parsed.segments:
        for token in _TOKEN.findall(segment):
            if token in TIMELINE_FORBIDDEN_TOKENS:
                message = (
                    f"{{{token}}} cannot be used in the timeline layout. The timeline is "
                    "chronological; category folders are placed automatically beside it "
                    "(Screenshots/, WhatsApp/ ...). Use date tokens only - for example "
                    "{yyyy}/{yyyy}-{mm}."
                )
                raise TemplateError(message)
    return parsed


class Placement(StrEnum):
    """**The shapes a file can land in.** One member per structure the product renders.

    This is the routing vocabulary. Every layout decision in truestill is a choice of one of
    these names, made exactly once by :func:`classify`; a template is then looked up by name and
    rendered. Naming the shapes rather than passing a set of booleans is what keeps the router
    from becoming the complexity: three booleans would be eight combinations of which only some
    are meaningful, and the impossible ones (a side bin that is also an event) would be excluded
    only by the order of a chain of ``if``s.
    """

    #: Not the timeline: a labelled quarantine beside it (Screenshots, WhatsApp, ...).
    SIDE_BIN = "side_bin"
    #: Timeline, no named event, capture day at or under the Everyday day-folder threshold.
    EVERYDAY = "everyday"
    #: Timeline, a member of a named event.
    EVENT_DAY = "event_day"
    #: Timeline, a day inside a named multi-day trip. Claims the whole day (see
    #: `RenderContext.trip`'s docstring) - a sub-day event on a trip-claimed day dissolves into
    #: the trip and never renders as :data:`EVENT_DAY` (`trip-grouping-research.md` §2).
    TRIP_DAY = "trip_day"
    #: Timeline, un-evented, capture day over the Everyday day-folder threshold
    #: (`docs/adaptive-day-folder-research.md`). Never applies inside a trip or named event.
    DAY_BUCKET = "day_bucket"


def normalize_everyday_day_threshold(value: object) -> int:
    """Positive threshold, else :data:`DEFAULT_EVERYDAY_DAY_THRESHOLD`."""
    if isinstance(value, bool):
        return DEFAULT_EVERYDAY_DAY_THRESHOLD
    try:
        number = int(value)  # type: ignore[call-overload]
    except (TypeError, ValueError):
        return DEFAULT_EVERYDAY_DAY_THRESHOLD
    return number if number >= 1 else DEFAULT_EVERYDAY_DAY_THRESHOLD


class InvalidEverydayDaySettingsError(ValueError):
    """Malformed Everyday day-folder threshold (stored or submitted)."""

    @classmethod
    def submitted(cls) -> InvalidEverydayDaySettingsError:
        return cls(
            "The day-folder threshold must be a whole number of 1 or more. "
            "Update it in Settings, then save again."
        )

    @classmethod
    def stored(cls, value: str) -> InvalidEverydayDaySettingsError:
        return cls(
            f"Stored {EVERYDAY_DAY_THRESHOLD_KEY} value {value!r} is invalid. "
            "Open Settings and save a whole number of 1 or more."
        )


class _SettingsReader(Protocol):
    def get_setting(self, key: str) -> str | None: ...


@dataclass(frozen=True, slots=True)
class EverydayDaySettings:
    """Validated per-catalog Everyday day-folder threshold (backlog ``(gg)``)."""

    threshold: int = DEFAULT_EVERYDAY_DAY_THRESHOLD
    is_default: bool = True

    def __post_init__(self) -> None:
        if (
            isinstance(self.threshold, bool)
            or not isinstance(self.threshold, int)
            or self.threshold < 1
        ):
            raise InvalidEverydayDaySettingsError.submitted()

    @classmethod
    def from_catalog(cls, catalog: _SettingsReader) -> Self:
        """Read and validate once; malformed persisted data is never coerced here."""
        stored = catalog.get_setting(EVERYDAY_DAY_THRESHOLD_KEY)
        if stored is None:
            return cls()
        if not stored.isascii() or not stored.isdecimal():
            raise InvalidEverydayDaySettingsError.stored(stored)
        try:
            threshold = int(stored)
        except ValueError as exc:
            raise InvalidEverydayDaySettingsError.stored(stored) from exc
        if threshold < 1 or str(threshold) != stored:
            raise InvalidEverydayDaySettingsError.stored(stored)
        return cls(threshold=threshold, is_default=False)


#: Shown after the threshold is saved - existing paths do not move until migrate.
EVERYDAY_DAY_THRESHOLD_MIGRATE_WARNING = (
    "Saved. Existing files stay where they are until you move them to match. "
    "Use Move existing files to match below to preview."
)

#: DOM id of the Settings migrate card - the warning routes here (scroll/focus).
EVERYDAY_DAY_THRESHOLD_MIGRATE_ANCHOR = "settings-migrate"


def count_capture_days(captured_ats: Sequence[datetime | date | None]) -> dict[str, int]:
    """Count dated files by ISO capture day in **one linear pass**.

    Callers must already have filtered to un-evented timeline members - this helper does not
    know about events, trips, catalogs or thresholds. Undated entries are skipped (they cannot
    be heavy days). **O(n)** over the sequence; later membership tests against the returned map
    (or :func:`heavy_capture_days`) are O(1) / O(d), never a recount per file.
    """
    counts: dict[str, int] = {}
    for captured_at in captured_ats:
        if captured_at is None:
            continue
        day = captured_at.date() if isinstance(captured_at, datetime) else captured_at
        key = day.isoformat()
        counts[key] = counts.get(key, 0) + 1
    return counts


def heavy_capture_days(
    counts: Mapping[str, int],
    *,
    threshold: int = DEFAULT_EVERYDAY_DAY_THRESHOLD,
) -> frozenset[str]:
    """ISO days whose count **exceeds** ``threshold`` (strictly greater). **O(d)** distinct days."""
    limit = normalize_everyday_day_threshold(threshold)
    return frozenset(day for day, n in counts.items() if n > limit)


#: Dated Everyday folder (`DAY_BUCKET`). Checked before the monthly form - a day path must not
#: be mistaken for a month path.
_DAY_BUCKET_FOLDER = re.compile(r"(?:^|/)(\d{4}-\d{2}-\d{2}) - Everyday(?:/|$)")
_MONTH_EVERYDAY_FOLDER = re.compile(r"(?:^|/)(\d{4}-\d{2}) - Everyday(?:/|$)")


def is_day_bucket_relative(relative: str) -> bool:
    """Whether ``relative`` sits under a ``YYYY-MM-DD - Everyday`` folder."""
    return _DAY_BUCKET_FOLDER.search(relative.replace("\\", "/")) is not None


def is_month_everyday_relative(relative: str) -> bool:
    """Whether ``relative`` sits under a monthly ``YYYY-MM - Everyday`` folder (not a day one)."""
    path = relative.replace("\\", "/")
    if is_day_bucket_relative(path):
        return False
    return _MONTH_EVERYDAY_FOLDER.search(path) is not None


def everyday_axis_changed(old_relative: str, new_relative: str) -> bool | None:
    """Month↔day Everyday transition, or ``None`` when the move is about something else.

    Returns ``True`` when moving **to** a day folder, ``False`` when moving **back** to the
    monthly bucket.
    """
    old_day = is_day_bucket_relative(old_relative)
    new_day = is_day_bucket_relative(new_relative)
    old_month = is_month_everyday_relative(old_relative)
    new_month = is_month_everyday_relative(new_relative)
    if old_month and new_day:
        return True
    if old_day and new_month:
        return False
    return None


def heavy_days_from_captures(
    *groups: Sequence[datetime | date | str | None],
    threshold: int = DEFAULT_EVERYDAY_DAY_THRESHOLD,
) -> frozenset[str]:
    """Union several capture-time sequences, count once, return heavy ISO days.

    Accepts datetimes, dates, or ISO strings (catalog rows). **One** :func:`count_capture_days`
    pass over the combined length - callers must not recount per file afterwards.
    """
    combined: list[datetime | date | None] = []
    for group in groups:
        for raw in group:
            if raw is None:
                continue
            if isinstance(raw, datetime | date):
                combined.append(raw)
            else:
                combined.append(datetime.fromisoformat(str(raw)))
    return heavy_capture_days(count_capture_days(combined), threshold=threshold)


def everyday_day_reconcile_reason(
    day: str, count: int, threshold: int, *, to_day_folder: bool
) -> str:
    """One never-silent sentence for a day whose Everyday placement is changing."""
    limit = normalize_everyday_day_threshold(threshold)
    if to_day_folder:
        return (
            f"{day} now has {count} photos, over your threshold of {limit} "
            "- moving to its own day folder"
        )
    return (
        f"{day} now has {count} photos, at or under your threshold of {limit} "
        "- moving back into the monthly Everyday folder"
    )


def classify(rule: str, context: RenderContext) -> Placement:
    """**The one router.** Every shape decision in the product is made here, exactly once.

    Order: side bin → trip day → event day → heavy un-evented day → everyday. A trip-claimed
    day takes precedence over an event unconditionally - `context.event` is never consulted
    once `context.trip` is set. Heavy-day uses the caller-supplied :attr:`RenderContext.heavy_day`
    flag only; this function never counts files and never opens a catalog. Pure, total, and free
    of any knowledge of what the shapes *are* - it returns a name, and the rendering is somebody
    else's job.
    """
    if rule != TIMELINE_RULE:
        return Placement.SIDE_BIN
    if context.trip is not None:
        return Placement.TRIP_DAY
    if context.event is not None:
        return Placement.EVENT_DAY
    if context.heavy_day:
        return Placement.DAY_BUCKET
    return Placement.EVERYDAY


@dataclass(frozen=True)
class LayoutScheme:
    """A whole layout: one template per :class:`Placement`, and the router between them.

    A mapping rather than a field per shape, because the shapes are open. Adding one is a new
    :class:`Placement` member plus an entry here, and :meth:`of` fails to type-check until the
    new shape has been given a template - so a shape cannot be added and silently left
    unrendered.

    Selecting a template is the entire mechanism. The token grammar stays a description of
    structure, never a language: no template contains a conditional, and no caller renders a
    shape it chose by hand.
    """

    templates: Mapping[Placement, LayoutTemplate]

    def __post_init__(self) -> None:
        # Renders are dict lookups, so totality is a construction-time property. Checking it here
        # turns a `KeyError` deep inside a run into a clear failure at the point of the mistake.
        if missing := [p for p in Placement if p not in self.templates]:
            names = ", ".join(sorted(missing))
            message = f"layout scheme is missing a template for: {names}"
            raise TemplateError(message)

    @classmethod
    def of(
        cls,
        *,
        timeline: LayoutTemplate,
        timeline_evented: LayoutTemplate,
        side_bin: LayoutTemplate = SIDE_BIN_TEMPLATE,
        trip_day: LayoutTemplate | None = None,
        day_bucket: LayoutTemplate | None = None,
    ) -> LayoutScheme:
        """Build a scheme from the shapes as a caller thinks of them.

        The ``match`` is the **build-time exhaustiveness gate**: add a member to
        :class:`Placement` and mypy fails here until this method says what template that shape
        gets. That is deliberate - this is the one place that must grow when the product does.

        ``trip_day`` defaults to **``timeline_evented`` itself** - "the trip shape is the
        day-event shape plus one dated level" (`trip-grouping-research.md` §2), so a fourth,
        independently-configurable Settings knob is not warranted; the *rendering* of the extra
        level (the trip's own header folder, then the day) is what actually differs, not the
        base template underneath it (see :meth:`LayoutTemplate._render`). Passing ``trip_day``
        explicitly is an escape hatch for tests that need it to diverge from ``timeline_evented``
        - no production caller does this yet.

        ``day_bucket`` defaults to :data:`DEFAULT_DAY_BUCKET_TEMPLATE` - the product Everyday
        heavy-day shape (`docs/adaptive-day-folder-research.md`), not a derivation from the
        user's timeline string (that would be a DSL conditional by another name).
        """
        chosen: dict[Placement, LayoutTemplate] = {}
        for placement in Placement:
            match placement:
                case Placement.SIDE_BIN:
                    chosen[placement] = side_bin
                case Placement.EVERYDAY:
                    chosen[placement] = timeline
                case Placement.EVENT_DAY:
                    chosen[placement] = timeline_evented
                case Placement.TRIP_DAY:
                    chosen[placement] = trip_day if trip_day is not None else timeline_evented
                case Placement.DAY_BUCKET:
                    chosen[placement] = (
                        day_bucket if day_bucket is not None else DEFAULT_DAY_BUCKET_TEMPLATE
                    )
                case _ as unreachable:
                    assert_never(unreachable)
        return cls(templates=chosen)

    def template_for(self, placement: Placement) -> LayoutTemplate:
        """The template for an already-decided shape. Total by construction (`__post_init__`)."""
        return self.templates[placement]

    def render(self, rule: str, context: RenderContext) -> PurePosixPath:
        return self.template_for(classify(rule, context)).render(context)


@dataclass(frozen=True)
class Preset:
    """A named, shippable layout."""

    key: str
    title: str
    timeline: str
    timeline_evented: str

    def scheme(self) -> LayoutScheme:
        return LayoutScheme.of(
            timeline=LayoutTemplate.parse(self.timeline),
            timeline_evented=LayoutTemplate.parse(self.timeline_evented),
        )


#: The shipped layouts. **Year-first only.** Two independent research syntheses put the year
#: above the source, so category-first is removed from the product rather than demoted - and
#: there is no bare-month preset either, because ``YYYY/MM`` stops being self-describing the
#: moment the folder is copied away from its parent, which is the principle this restores.
PRESETS: dict[str, Preset] = {
    "year-month-event": Preset(
        key="year-month-event",
        title="Year / Month / Event",
        # Ordinary photos get an `Everyday` bucket so they do not sit loose beside the month's
        # event folders; an event keeps the month itself as its parent.
        timeline="{yyyy}/{yyyy}-{mm}/{yyyy}-{mm} - Everyday",
        timeline_evented="{yyyy}/{yyyy}-{mm}",
    ),
    "year-event": Preset(
        key="year-event",
        title="Year / Event (events sit under the year)",
        timeline="{yyyy}/{yyyy}-{mm}",
        timeline_evented="{yyyy}",
    ),
    "year-month-day": Preset(
        key="year-month-day",
        title="Year / Month / Day",
        timeline="{yyyy}/{yyyy}-{mm}/{yyyy}-{mm}-{dd}",
        timeline_evented="{yyyy}/{yyyy}-{mm}/{yyyy}-{mm}-{dd}",
    ),
}

#: The preset a library gets when it has not chosen one. **Not yet in force** - the default
#: constant still points at the legacy shape until the flip commit; this names the destination.
DEFAULT_PRESET = PRESETS["year-month-event"]


def scheme_from_string(timeline: str, evented: str | None = None) -> LayoutScheme:
    """Build a whole layout from stored template strings. **Pure; the single interpretation.**

    The timeline is parsed through :func:`parse_timeline_template`, so a stored value naming a
    category is rejected here exactly as it would be at the Settings door -- there is no
    load-time leniency and no second interpretation of what a stored template means.
    ``{category}`` survives only inside the fixed side-bin shape, which is not user-supplied.
    """
    parsed = parse_timeline_template(timeline)
    parsed_evented = parse_timeline_template(evented) if evented else parsed
    return LayoutScheme.of(timeline=parsed, timeline_evented=parsed_evented)


def resolve_scheme(catalog: CatalogLike) -> LayoutScheme:
    """The whole layout in force for a catalog, router included. Pure; never writes.

    **The single resolution entry point.** Runs, previews and migration all come through here,
    so there is no second path that could answer differently -- the divergence the design audit
    found (a preview rendering through a scheme while runs rendered through a bare template).
    """
    stored = effective_layout_string(catalog)
    if stored is None:
        # Falls back to the whole default *scheme*, not to its timeline string: the default's
        # evented and un-evented shapes differ (events keep the month as their parent, ordinary
        # photos go to `Everyday`), and a single string cannot express that.
        return DEFAULT_SCHEME
    return scheme_from_string(stored, catalog.get_setting(LAYOUT_EVENT_TEMPLATE_KEY))


@dataclass(frozen=True, slots=True)
class SampleRow:
    """One row of the live layout preview: what kind of file, and where it lands."""

    description: str
    rule: str
    context: RenderContext


#: The live preview must show the **routing split**, not just date placement, because the split
#: is the thing a user cannot infer from a template string: camera photos go to the timeline,
#: everything else to a labelled side bin beside it, and an event gets its own readable folder.
#: An undated row is included because the collapse rule surprises people otherwise.
SAMPLE_ROWS: tuple[SampleRow, ...] = (
    SampleRow(
        "Camera",
        TIMELINE_RULE,
        RenderContext(category="Camera", captured_at=datetime(2014, 8, 20, 14, 30)),  # noqa: DTZ001
    ),
    SampleRow(
        "Camera event",
        TIMELINE_RULE,
        RenderContext(
            category="Camera",
            captured_at=datetime(2014, 8, 20, 14, 30),  # noqa: DTZ001
            event=(datetime(2014, 8, 20), "goa-trip"),  # noqa: DTZ001
            event_name="Goa Trip",
        ),
    ),
    SampleRow("Camera undated", TIMELINE_RULE, RenderContext(category="Camera")),
    SampleRow(
        "Screenshots",
        "screenshot_name",
        RenderContext(category="Screenshots", captured_at=datetime(2024, 1, 15)),  # noqa: DTZ001
    ),
)


def preview_scheme(
    scheme: LayoutScheme, *, filename: str = "sample.jpg"
) -> list[tuple[SampleRow, PreviewRow]]:
    """Render :data:`SAMPLE_ROWS` through a whole scheme, router included.

    Renders through the same :meth:`LayoutScheme.render` an organize run uses, so a preview can
    only ever show what a run would actually do. **O(len(SAMPLE_ROWS))** - a constant.
    """
    rendered = [
        scheme.template_for(classify(row.rule, row.context))._render(row.context)
        for row in SAMPLE_ROWS
    ]
    fulls = [directory / filename for directory, _ in rendered]
    rows = _preview_rows(fulls, [notes for _, notes in rendered])
    return list(zip(SAMPLE_ROWS, rows, strict=True))


#: The layout a run uses when a catalog has chosen nothing. Derived from
#: the default preset, so "the default" is a scheme like any other and there is no
#: template-only path anywhere. Built from the preset rather than from
#: :data:`DEFAULT_TEMPLATE_STRING` because the two timeline shapes differ.
DEFAULT_SCHEME = DEFAULT_PRESET.scheme()
