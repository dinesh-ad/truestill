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

#: The structure truestill has always produced; the default until a catalog stores its own.
DEFAULT_TEMPLATE_STRING = "{category}/{yyyy}/{mm}"

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
    #: ``20140820_goa-trip`` - the pre-year-first spelling, kept so a legacy library is stable.
    SLUG = "slug"


#: Longest event *name* allowed in a folder. Names are user input becoming a directory, and a
#: path component is bounded on every filesystem.
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
    cleaned = _sanitize_value(name)[:MAX_EVENT_NAME].strip().rstrip(" .")
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


class TemplateError(ValueError):
    """Raised when a layout template is malformed or references an unknown token."""


def _is_reserved(component: str) -> bool:
    """Whether a path component is a Windows reserved device name (stem, case-insensitive)."""
    stem = component.split(".", 1)[0].strip().lower()
    return stem in _WIN_RESERVED


def _sanitize_value(value: str) -> str:
    """Make a rendered token value safe as a single path component (never raises).

    Illegal characters (incl. ``/`` and ``\\``) become ``_`` so a value cannot inject a
    directory level, and trailing dots/spaces are trimmed (Windows silently drops them).
    """
    return _VALUE_ILLEGAL.sub("_", value).strip().rstrip(" .")


def resolve_template(stored: str | None) -> LayoutTemplate:
    """The active template: the stored one if a catalog has set it, else the default."""
    return LayoutTemplate.parse(stored) if stored else DEFAULT_TEMPLATE


#: The layout truestill produced before the year-first default. Written into a catalog that has
#: already placed files under it, so that changing :data:`DEFAULT_TEMPLATE_STRING` cannot
#: re-shape a library nobody asked to re-shape. See :func:`pin_existing_layout`.
LEGACY_TEMPLATE_STRING = "{category}/{yyyy}/{mm}"


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
    if effective_layout_string(catalog) != LEGACY_TEMPLATE_STRING:
        return False
    if catalog.get_setting(LAYOUT_TEMPLATE_KEY) is not None:
        return False
    catalog.set_setting(LAYOUT_TEMPLATE_KEY, LEGACY_TEMPLATE_STRING)
    return True


def effective_layout_string(catalog: CatalogLike) -> str | None:
    """The layout in force right now - **pure, never writes.**

    A library that qualifies for the pin renders through the legacy layout *whether or not the
    pin has run yet*. That equivalence is the point: previews run on read-only paths where
    writing a setting would break the dry-run invariant (`IMPLEMENTATION_STANDARDS.md` §5), so
    the preview cannot pin - and if it resolved differently from the run that follows it, the
    plan a user approved would not be the plan that executed.
    """
    stored = catalog.get_setting(LAYOUT_TEMPLATE_KEY)
    if stored is not None:
        return stored
    return LEGACY_TEMPLATE_STRING if catalog.has_placed_files() else None


def resolve_for(catalog: CatalogLike) -> LayoutTemplate:
    """The template to render a catalog's files through. Pure; safe on preview paths."""
    return resolve_template(effective_layout_string(catalog))


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

    @property
    def is_legacy(self) -> bool:
        """Whether this is a pinned pre-year-first library (its timeline names a category)."""
        return any("category" in _TOKEN.findall(seg) for seg in self.timeline.segments)

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
        timeline="{yyyy}/{yyyy}-{mm}",
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


def resolve_scheme(catalog: CatalogLike) -> LayoutScheme:
    """The whole layout in force for a catalog, router included. Pure; never writes.

    A legacy (pinned) library resolves to a scheme whose timeline still carries ``{category}``,
    whose side bin *is* that same template, and whose events keep their slug spelling - so it
    renders exactly as it always has.
    """
    stored = effective_layout_string(catalog) or DEFAULT_TEMPLATE_STRING
    legacy = "category" in stored
    naming = EventNaming.SLUG if legacy else EventNaming.READABLE
    timeline = LayoutTemplate.parse(stored, event_naming=naming)
    evented_stored = catalog.get_setting(LAYOUT_EVENT_TEMPLATE_KEY)
    evented = (
        LayoutTemplate.parse(evented_stored, event_naming=naming) if evented_stored else timeline
    )
    return LayoutScheme(
        timeline=timeline,
        timeline_evented=evented,
        side_bin=timeline if legacy else SIDE_BIN_TEMPLATE,
    )


#: Three representative files for the live preview: a dated camera photo, a dated messenger
#: image, and an undated file -- enough to show date placement and the Undated fallback.
SAMPLE_CONTEXTS: tuple[RenderContext, ...] = (
    RenderContext(category="Camera", captured_at=datetime(2023, 8, 20, 14, 30)),  # noqa: DTZ001
    RenderContext(category="WhatsApp", captured_at=datetime(2024, 1, 15)),  # noqa: DTZ001
    RenderContext(category="Screenshots", captured_at=None),
)
