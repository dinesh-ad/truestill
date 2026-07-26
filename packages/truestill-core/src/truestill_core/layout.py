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
from pathlib import PurePosixPath

from truestill_core.events import event_dirname
from truestill_core.models import UNDATED_DIRNAME

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

#: The catalog settings key under which a library's chosen template is persisted.
LAYOUT_TEMPLATE_KEY = "layout_template"

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


@dataclass(frozen=True)
class RenderContext:
    """Everything :meth:`LayoutTemplate.render` needs about one file."""

    category: str
    captured_at: datetime | None = None
    #: ``(start, slug)`` when the file belongs to a named event, else ``None``.
    event: tuple[datetime, str] | None = None

    @property
    def date(self) -> datetime | None:
        """The date the tokens resolve from: the event start if any, else the capture date."""
        return self.event[0] if self.event is not None else self.captured_at


@dataclass(frozen=True)
class LayoutTemplate:
    """A parsed, validated destination-folder template."""

    template: str
    segments: tuple[str, ...]

    @classmethod
    def parse(cls, template: str) -> LayoutTemplate:
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
        return cls(template=cleaned, segments=segments)

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
            path = path / event_dirname(*context.event)
        return path, notes

    def _render_segment(
        self, segment: str, context: RenderContext, date: datetime | None, notes: list[str]
    ) -> str:
        def substitute(match: re.Match[str]) -> str:
            token = match.group(1)
            if token == "category":
                value = context.category
            elif token == "event":
                value = event_dirname(*context.event) if context.event is not None else ""
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

#: Named starting points, drawn from what mainstream organizers actually ship (see
#: docs/org-structure-research.md §1b.4). The first equals the default. Power users can edit
#: any of these into a custom template.
PRESETS: dict[str, str] = {
    "category-year-month": "{category}/{yyyy}/{mm}",
    "category-year-month-day": "{category}/{yyyy}/{mm}/{dd}",
    "category-year": "{category}/{yyyy}",
    "flat-date": "{yyyy}-{mm}-{dd}",
    "category-year-event": "{category}/{yyyy}/{event}",
}

#: Three representative files for the live preview: a dated camera photo, a dated messenger
#: image, and an undated file -- enough to show date placement and the Undated fallback.
SAMPLE_CONTEXTS: tuple[RenderContext, ...] = (
    RenderContext(category="Camera", captured_at=datetime(2023, 8, 20, 14, 30)),  # noqa: DTZ001
    RenderContext(category="WhatsApp", captured_at=datetime(2024, 1, 15)),  # noqa: DTZ001
    RenderContext(category="Screenshots", captured_at=None),
)
