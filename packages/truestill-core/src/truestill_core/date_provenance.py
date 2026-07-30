"""Cycle-free provenance and offset wire format for inferred-local dates.

``dates`` imports ``DateSource`` from ``models``; ``models.inferred_local_shifts`` needs
``+HH:MM`` formatting. Putting both sides' shared formatter here retires the duplicate
``models._format_offset_hhmm`` that existed only to dodge that cycle.
"""

from __future__ import annotations

import re
from datetime import timedelta
from typing import NamedTuple

# ---------------------------------------------------------------------------
# Inferred-local provenance (``DateSource.INFERRED_LOCAL`` / not-proven-UTC)
#
# ``date_tag`` is the durable provenance record a later pass reads. Format:
#
#   {container_tag}|{evidence}[|{offset}]
#
# Field separator is ASCII ``|`` (U+007C). Exiftool tag names use ``Group:Tag`` with a
# colon, never a pipe, so splitting on ``|`` cannot collide with a real tag name we place
# in field 0 or with evidence tokens such as ``TimeZone`` / ``filename:VID_``.
# Evidence tokens that combine signals join with ``+`` inside field 1
# (``GPSDateStamp+filename:VID_``), never with ``|``.
#
# Offset is ``+HH:MM`` / ``-HH:MM`` (half-hour grid). Absent only for the not-proven-UTC form.
#
# Examples:
#   CreateDate|filename:VID_|+05:30
#   CreateDate|TimeZone|+06:30
#   CreateDate|not_proven_utc  (not proven UTC; treated as local - usually correct)
# ---------------------------------------------------------------------------

#: Provenance field separator. Must not appear in container tags or evidence tokens.
INFERRED_DATE_TAG_SEP = "|"

#: Evidence token when a container stamp was left as local digits.
#: Means "not proven to be UTC; treated as local" - **not** a defect. Most cameras that
#: write local into ``CreateDate`` land here correctly; reports must not alarm.
NOT_PROVEN_UTC = "not_proven_utc"

_OFFSET_RE = re.compile(r"^([+-])(\d{2}):(\d{2})$")
_SECONDS_PER_MINUTE = 60
_MINUTES_PER_HOUR = 60
_NOT_PROVEN_FIELD_COUNT = 2
_INFERRED_FIELD_COUNT = 3


class InferredDateTag(NamedTuple):
    """Parsed ``date_tag`` for an inferred-local (or not-proven-UTC) CreateDate decision."""

    container_tag: str
    evidence: str
    offset: timedelta | None  # None iff evidence is :data:`NOT_PROVEN_UTC`


def format_offset(offset: timedelta) -> str:
    """Format a UTC offset as ``+HH:MM`` / ``-HH:MM`` (minute granularity)."""
    total = int(offset.total_seconds())
    if total % _SECONDS_PER_MINUTE != 0:
        message = f"offset must be whole minutes, got {offset!r}"
        raise ValueError(message)
    sign = "+" if total >= 0 else "-"
    total = abs(total)
    hours, minutes = divmod(total // _SECONDS_PER_MINUTE, _MINUTES_PER_HOUR)
    return f"{sign}{hours:02d}:{minutes:02d}"


def parse_offset(text: str) -> timedelta:
    """Parse ``+HH:MM`` / ``-HH:MM`` into a :class:`~datetime.timedelta`."""
    match = _OFFSET_RE.fullmatch(text.strip())
    if match is None:
        message = f"not an offset: {text!r}"
        raise ValueError(message)
    sign, hours_s, minutes_s = match.groups()
    hours, minutes = int(hours_s), int(minutes_s)
    if minutes >= _MINUTES_PER_HOUR:
        message = f"not an offset: {text!r}"
        raise ValueError(message)
    delta = timedelta(hours=hours, minutes=minutes)
    return delta if sign == "+" else -delta


def format_inferred_date_tag(container_tag: str, evidence: str, offset: timedelta) -> str:
    """Build a machine-parseable inferred-local ``date_tag``.

    Round-trips with :func:`parse_inferred_date_tag`. ``container_tag`` and ``evidence``
    must not contain :data:`INFERRED_DATE_TAG_SEP`.
    """
    if INFERRED_DATE_TAG_SEP in container_tag or INFERRED_DATE_TAG_SEP in evidence:
        message = (
            f"provenance fields must not contain {INFERRED_DATE_TAG_SEP!r}: "
            f"{container_tag!r} / {evidence!r}"
        )
        raise ValueError(message)
    if evidence == NOT_PROVEN_UTC:
        message = "use format_not_proven_utc_tag when UTC is not proven"
        raise ValueError(message)
    return (
        f"{container_tag}{INFERRED_DATE_TAG_SEP}{evidence}"
        f"{INFERRED_DATE_TAG_SEP}{format_offset(offset)}"
    )


def format_not_proven_utc_tag(container_tag: str) -> str:
    """Record that a container stamp was **not proven UTC** and was treated as local.

    Form: ``{container_tag}|not_proven_utc``. This is the common, usually-correct path for
    cameras that write local wall-clock into ``CreateDate`` - not a failure flag.
    """
    if INFERRED_DATE_TAG_SEP in container_tag:
        message = f"container_tag must not contain {INFERRED_DATE_TAG_SEP!r}: {container_tag!r}"
        raise ValueError(message)
    return f"{container_tag}{INFERRED_DATE_TAG_SEP}{NOT_PROVEN_UTC}"


def parse_inferred_date_tag(tag: str) -> InferredDateTag | None:
    """Parse an inferred / not-proven-UTC ``date_tag``, or ``None`` if the shape is wrong.

    Accepts ``CreateDate|filename:VID_|+05:30`` and ``CreateDate|not_proven_utc``.
    Plain EXIF tags such as ``CreationDate`` or ``DateTimeOriginal`` return ``None``.
    """
    parts = tag.split(INFERRED_DATE_TAG_SEP)
    if len(parts) == _NOT_PROVEN_FIELD_COUNT:
        container, evidence = parts
        if not container or evidence != NOT_PROVEN_UTC:
            return None
        return InferredDateTag(container, evidence, None)
    if len(parts) == _INFERRED_FIELD_COUNT:
        container, evidence, offset_text = parts
        if not container or not evidence or evidence == NOT_PROVEN_UTC or not offset_text:
            return None
        try:
            offset = parse_offset(offset_text)
        except ValueError:
            return None
        return InferredDateTag(container, evidence, offset)
    return None
