"""The destination folder layout, as a token template.

Historically the structure ``<Label>/YYYY/MM/`` was built inline in two places
(``organizer.build_relative`` and ``organizer.apply_events``). This module makes the layout a
single first-class thing -- a :class:`LayoutTemplate` parsed from a token string -- so both
sites render through one seam and the structure can later be made configurable.

Grammar: ``/``-separated segments of literals and ``{token}`` placeholders. v1 tokens are exactly
those a :class:`~vaeon_core.models.Decision` carries for free:

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
from dataclasses import dataclass
from datetime import datetime
from pathlib import PurePosixPath

from vaeon_core.events import event_dirname
from vaeon_core.models import UNDATED_DIRNAME

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

#: The structure vaeon has always produced; the default until a catalog stores its own.
DEFAULT_TEMPLATE_STRING = "{category}/{yyyy}/{mm}"


class TemplateError(ValueError):
    """Raised when a layout template is malformed or references an unknown token."""


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
        """Parse and validate a template string, or raise :class:`TemplateError`."""
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
        return cls(template=cleaned, segments=segments)

    def has_event_token(self) -> bool:
        """Whether the template places events explicitly (vs. relying on the append rule)."""
        return any("event" in _TOKEN.findall(segment) for segment in self.segments)

    def render(self, context: RenderContext) -> PurePosixPath:
        """Render the destination *directory* (no filename) for ``context``."""
        date = context.date
        parts: list[str] = []
        undated_done = False
        for segment in self.segments:
            tokens = _TOKEN.findall(segment)
            if date is None and any(token in _DATE_TOKENS for token in tokens):
                if not undated_done:
                    parts.append(UNDATED_DIRNAME)
                    undated_done = True
                continue
            rendered = self._render_segment(segment, context, date)
            if rendered:
                parts.append(rendered)

        path = PurePosixPath(*parts) if parts else PurePosixPath()
        if context.event is not None and not self.has_event_token():
            path = path / event_dirname(*context.event)
        return path

    def _render_segment(self, segment: str, context: RenderContext, date: datetime | None) -> str:
        def substitute(match: re.Match[str]) -> str:
            token = match.group(1)
            if token == "category":
                return context.category
            if token == "event":
                return event_dirname(*context.event) if context.event is not None else ""
            return format(date, _DATE_TOKENS[token]) if date is not None else ""

        return _TOKEN.sub(substitute, segment)


#: The default layout, parsed once.
DEFAULT_TEMPLATE = LayoutTemplate.parse(DEFAULT_TEMPLATE_STRING)
