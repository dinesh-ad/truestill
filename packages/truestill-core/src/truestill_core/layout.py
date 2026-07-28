"""The destination folder layout, as a token template.

Historically the structure ``<Label>/YYYY/MM/`` was built inline in two places
(``organizer.build_relative`` and ``organizer.apply_events``). This module makes the layout a
single first-class thing -- a :class:`LayoutTemplate` parsed from a token string -- so both
sites render through one seam and the structure can later be made configurable.

Grammar: ``/``-separated segments of literals and ``{token}`` placeholders. v1 tokens are exactly
those a :class:`~truestill_core.models.Decision` carries for free:

* ``{category}`` -- the derived label (``Camera``, ``WhatsApp``, ...).
* date tokens ``{yyyy} {yy} {mm} {mon} {month} {dd}`` -- from the capture date (or, for an event
  member, the event's start date).
* ``{event}`` -- the event folder ``YYYYMMDD_slug`` for a named-event member.

Two behavioural rules preserve exactly what the inline code did:

* **Undated collapse.** When there is no date, every date-derived segment is dropped and a single
  ``Undated`` folder takes their place -- so ``{category}/{yyyy}/{mm}`` becomes
  ``{category}/Undated``, never ``{category}//``.
* **Event append.** A named-event member's date tokens resolve from the event *start* (so a
  cross-month event stays whole under its start month), and when the template has no explicit
  ``{event}`` token the event folder is appended -- reproducing today's
  ``{category}/{yyyy}/{mm}/YYYYMMDD_slug``.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import PurePosixPath
from typing import Protocol

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
#: (Before 2026-07-28 this was ``{category}/{yyyy}/{mm}``; see `docs/default-layout-research.md`.)
DEFAULT_TEMPLATE_STRING = "{yyyy}/{yyyy}-{mm}/{yyyy}-{mm} - Everyday"

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

    @property
    def date(self) -> datetime | None:
        """The date the tokens resolve from: the event start if any, else the capture date."""
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
        surfaced by :func:`preview` instead, since they depend on the files being organized.
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
        if context.event is not None and not self.has_event_token():
            path = path / event_folder(*context.event, context.event_name, self.event_naming, notes)
        return path, notes

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


def preview(
    template: LayoutTemplate,
    contexts: Sequence[RenderContext],
    *,
    filename: str = "sample.jpg",
) -> list[PreviewRow]:
    """Render ``contexts`` through ``template`` for the live preview, collecting warnings.

    Surfaces exactly the risks that cannot be judged from the template alone: an empty token
    value (and where the file then lands), a relative path approaching the Windows length limit,
    and two samples that collide on a case-insensitive filesystem. All are warnings, not errors:
    rendering is total, so a run never fails here.
    """
    rendered = [template._render(c) for c in contexts]
    fulls = [directory / filename for directory, _ in rendered]

    lowered: dict[str, int] = {}
    collisions: set[int] = set()
    for i, full in enumerate(fulls):
        key = full.as_posix().lower()
        if key in lowered:
            collisions.add(i)
            collisions.add(lowered[key])
        lowered[key] = i

    rows: list[PreviewRow] = []
    for i, (full, (_, notes)) in enumerate(zip(fulls, rendered, strict=True)):
        warnings = list(notes)
        if len(full.as_posix()) > PATH_LENGTH_WARN:
            warnings.append(f"path is {len(full.as_posix())} chars, near the Windows 260 limit")
        if i in collisions:
            warnings.append("collides with another sample on a case-insensitive filesystem")
        rows.append(PreviewRow(path=full, warnings=tuple(warnings)))
    return rows


#: The default layout, parsed once.
DEFAULT_TEMPLATE = LayoutTemplate.parse(DEFAULT_TEMPLATE_STRING)

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


@dataclass(frozen=True)
class LayoutScheme:
    """A whole layout: two timeline templates, the fixed side bin, and the router between them.

    Two timeline templates rather than one because an event is a **second routing axis**, not a
    conditional: "Year / Event" puts an evented file under ``{yyyy}`` and an ordinary one under
    ``{yyyy}/{yyyy}-{mm}``, which no single template can express. Selecting a template is the
    entire mechanism - the token grammar stays a description of structure, never a language.
    """

    timeline: LayoutTemplate
    timeline_evented: LayoutTemplate
    side_bin: LayoutTemplate = SIDE_BIN_TEMPLATE

    def template_for(self, rule: str, *, evented: bool) -> LayoutTemplate:
        """Route: the rule picks timeline vs side bin; the event flag picks which timeline."""
        if rule != TIMELINE_RULE:
            return self.side_bin
        return self.timeline_evented if evented else self.timeline

    def render(self, rule: str, context: RenderContext) -> PurePosixPath:
        return self.template_for(rule, evented=context.event is not None).render(context)


@dataclass(frozen=True)
class Preset:
    """A named, shippable layout."""

    key: str
    title: str
    timeline: str
    timeline_evented: str

    def scheme(self) -> LayoutScheme:
        return LayoutScheme(
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
    return LayoutScheme(timeline=parsed, timeline_evented=parsed_evented)


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
        scheme.template_for(row.rule, evented=row.context.event is not None)._render(row.context)
        for row in SAMPLE_ROWS
    ]
    fulls = [directory / filename for directory, _ in rendered]

    lowered: dict[str, int] = {}
    collisions: set[int] = set()
    for i, full in enumerate(fulls):
        key = full.as_posix().lower()
        if key in lowered:
            collisions.add(i)
            collisions.add(lowered[key])
        lowered[key] = i

    out: list[tuple[SampleRow, PreviewRow]] = []
    for i, (row, full, (_, notes)) in enumerate(zip(SAMPLE_ROWS, fulls, rendered, strict=True)):
        warnings = list(notes)
        if len(full.as_posix()) > PATH_LENGTH_WARN:
            warnings.append(f"path is {len(full.as_posix())} chars, near the Windows 260 limit")
        if i in collisions:
            warnings.append("collides with another sample on a case-insensitive filesystem")
        out.append((row, PreviewRow(path=full, warnings=tuple(warnings))))
    return out


#: The layout a run uses when a catalog has chosen nothing. Derived from
#: the default preset, so "the default" is a scheme like any other and there is no
#: template-only path anywhere. Built from the preset rather than from
#: :data:`DEFAULT_TEMPLATE_STRING` because the two timeline shapes differ.
DEFAULT_SCHEME = DEFAULT_PRESET.scheme()
