"""Plain-language answers to "why this date?" - one wording, shared by every surface.

`IMPLEMENTATION_STANDARDS.md` §9 already requires that an outcome be worded in exactly one place
(`models.status_label`) so the CLI and the app cannot drift. Date provenance is the same kind of
claim and gets the same treatment: this module is the only place a `DateSource` becomes a sentence.

**The wording rules that shaped these strings**, from `(ccc)`'s plain-language audit:

* Name what happened, not the mechanism. "From the filename", never "FILENAME tier".
* Never alarm about something that is fine. The commonest case on a real library is *not
  recorded*, and a library whose dates are correct must not be described as if it has a problem.
* Say what it means for the user's photos, not for the code.

**Complexity: O(1)** per lookup - a dict and a string format. No I/O.
"""

from __future__ import annotations

from dataclasses import dataclass

from truestill_core.date_provenance import format_offset, parse_inferred_date_tag
from truestill_core.models import DateSource


@dataclass(frozen=True, slots=True)
class DateExplanation:
    """How a group of files got their dates, in words a user can act on."""

    #: Short label for the row: "From the photo's own data".
    label: str
    #: One sentence saying what that means. Never a warning unless something is genuinely wrong.
    detail: str
    #: True when this group is worth a second look. Drives emphasis, never alarm.
    review: bool = False


#: The commonest group on any library organized before schema v13, including Dinesh's own
#: ~2,300-file catalog - so it is written as the calm, ordinary thing it is. It is not an error,
#: not a gap in the photos, and not something the user did wrong: only the *note* is missing.
#: Deliberately offers no remedy, because there is no cheap one - a re-organize skips these files
#: as exact duplicates and would not rewrite the note, and promising otherwise would be a lie.
NOT_RECORDED = DateExplanation(
    label="Not recorded",
    detail=(
        "These were organized before truestill started keeping this note. Their dates are "
        "unaffected - only the record of where each date came from is missing."
    ),
)

_EXPLANATIONS: dict[DateSource, DateExplanation] = {
    DateSource.HUMAN_CONFIRMED: DateExplanation(
        label="You confirmed this date",
        detail=(
            "Someone told truestill when this was taken, and that answer wins over anything the "
            "file says. It stays put through every later reorganize."
        ),
    ),
    DateSource.EXIF: DateExplanation(
        label="From the photo's own data",
        detail="The camera recorded when the photo was taken, and truestill used that.",
    ),
    DateSource.TAKEOUT: DateExplanation(
        label="From the Google Takeout record",
        detail="Google's export said when this was taken, and the file itself did not.",
    ),
    DateSource.TAKEOUT_UPLOAD: DateExplanation(
        label="From when it was uploaded to Google",
        detail=(
            "Google recorded when this was uploaded, not when it was taken. That is usually "
            "later, sometimes by years."
        ),
        review=True,
    ),
    DateSource.INFERRED_LOCAL: DateExplanation(
        label="Worked out from the video's clock",
        detail=(
            "The video stored its time in UTC. truestill found evidence of the local time zone "
            "and shifted it, so the date matches when you were actually there."
        ),
    ),
    DateSource.FILENAME: DateExplanation(
        label="From the filename",
        detail=(
            "The date came from the file's name, like 20140820_143000.jpg. Usually right - but a "
            "name can be changed or copied from another file, so these are worth a look."
        ),
        review=True,
    ),
    DateSource.REJECTED_SENTINEL: DateExplanation(
        label="A date was found and refused",
        detail=(
            "The file carried a placeholder like 1904 or 1970 - what a device writes when it has "
            "no real date. Filing by it would have been worse than leaving it undated."
        ),
        review=True,
    ),
    DateSource.NONE: DateExplanation(
        label="No date found",
        detail=(
            "Nothing in the file or its name said when it was taken, so it is filed under "
            "Undated. Adding the date yourself is the surest fix."
        ),
        review=True,
    ),
}


def explain(source: str | None) -> DateExplanation:
    """The explanation for a stored ``date_source``, including ``None`` and unknown values.

    An unrecognised stored string falls back to :data:`NOT_RECORDED` rather than raising: this
    is a display path, and a catalog written by a newer build must not be able to break the
    screen that is trying to describe it.
    """
    if source is None:
        return NOT_RECORDED
    try:
        return _EXPLANATIONS[DateSource(source)]
    except (ValueError, KeyError):
        return NOT_RECORDED


def explain_evidence(source: str | None, tag: str | None) -> str | None:
    """The specific evidence behind one group, or ``None`` when there is none to show.

    This is the half that answers "why *this* date" rather than "what kind of date". For EXIF it
    is the winning tag; for an inferred video time it is the rung that proved the offset and the
    offset itself, because "we shifted your video by 5 hours 30" is the part a user can check.
    """
    if not tag:
        return None
    if source == DateSource.INFERRED_LOCAL.value:
        parsed = parse_inferred_date_tag(tag)
        if parsed is None:
            return tag  # an unparseable tag is still evidence; show it rather than hide it
        if parsed.offset is None:
            # not-proven-UTC: the digits were kept as local, which is usually right. Said as a
            # fact rather than a doubt, per (uu) - "treated as local, usually correct".
            return f"{parsed.container_tag} kept as local time (no time zone proof)"
        return (
            f"{parsed.container_tag} shifted by {format_offset(parsed.offset)}, "
            f"proved by {parsed.evidence}"
        )
    return f"tag: {tag}"
