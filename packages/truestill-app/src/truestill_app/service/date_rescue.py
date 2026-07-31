"""The rescue action: a person tells truestill when a photo was really taken (step 5).

`confirm_date` shipped in step 3 with **zero routes and zero CLI commands**, deliberately - the
ruling was that step 3 stay catalog-only so a bug in the write path could not cost a correction
a user had already made. This module is what makes it reachable, and therefore what makes steps
1 to 4 worth anything to a person rather than to a schema.

**App-only, and that is a deferral rather than a parity gap.** A rescue is review-shaped: look at
a photo, judge what it is, correct it - a loop over a list with the evidence in front of you,
which is what the honesty view is. A CLI equivalent would need file addressing by hash or path
and would be used for bulk correction, which is a different and more dangerous feature. Recorded
in `BACKLOG.md` under App-surface deferrals, **explicitly**, because a single-surface contract
that nobody wrote down is indistinguishable from the drift `test_surface_parity.py` cannot see
(its second blind spot: a surface that omits a key rather than calling a shared symbol
differently).

**Complexity: O(1)** per confirmation - one indexed lookup and two indexed writes in one
transaction. No file is read and nothing is scanned.
"""

from __future__ import annotations

from datetime import datetime, time
from pathlib import Path
from typing import Literal, TypedDict

from truestill_core.catalog import Catalog

#: The time of day used when someone supplies a date without one.
#:
#: **Midday, and the reason is not aesthetics.** Placement never uses time - `layout._DATE_TOKENS`
#: is years, months and days - so it would be easy to read this as arbitrary. It is not:
#:
#: * **Event clustering measures gaps in hours.** `events.py` groups by the interval between
#:   ``captured_at`` values, so confirming a batch of scanned prints at 00:00 would collapse them
#:   into one enormous midnight "event". Midday keeps a day's files near each other and away from
#:   the boundary where a cluster would straddle two dates.
#: * **Midnight looks like a dead clock.** `dates.SUSPECT_DEFAULT_DAYS` exists because cameras
#:   write exactly-midnight values when their battery dies. A human-confirmed date is not flagged
#:   by `is_suspect_default` (it gates on the clock-derived tiers), but writing values that *look*
#:   like the thing another part of the system treats as suspicious is a trap for the next reader.
#:
#: A user who knows the real time supplies it and this is not consulted.
ASSUMED_TIME = time(12, 0, 0)


class RescueOk(TypedDict):
    ok: Literal[True]
    #: What the library now believes, for a screen that must say it back concretely.
    captured_at: str
    #: True when the time was assumed rather than supplied, so the UI can say which.
    time_assumed: bool


class RescueRefusal(TypedDict):
    ok: Literal[False]
    error: str


def _parse(date_text: str, time_text: str | None) -> datetime | None:
    """A full calendar date, or ``None``. **Imprecision is refused, never rounded.**

    ``captured_at`` is a ``datetime``; the model has no year-only or month-only form. Accepting
    "1985" and storing 1985-01-01 would record a guess as an exact date in the
    ``HUMAN_CONFIRMED`` tier - the most trusted one in the system - which is the exact class of
    lie this program exists to remove. So a partial date is turned away with an explanation
    rather than being helpfully completed.
    """
    try:
        # Naive by design, like every capture date in this product: a photo was taken at a
        # local wall-clock moment, and `dates.resolve_capture_datetime` returns naive too.
        day = datetime.strptime(date_text.strip(), "%Y-%m-%d").date()  # noqa: DTZ007
    except ValueError:
        return None
    if not time_text or not time_text.strip():
        return datetime.combine(day, ASSUMED_TIME)
    try:
        moment = datetime.strptime(time_text.strip(), "%H:%M").time()  # noqa: DTZ007
    except ValueError:
        return None
    return datetime.combine(day, moment)


#: Said where the user meets it, not only in the backlog. The refusal is a decision, and a
#: message that reads like a parser failing to try invites someone to "fix" it by rounding.
IMPRECISE_DATE_ERROR = (
    "Enter a full date, like 2011-03-04. truestill will not turn a partial date into an exact "
    "one - if you only know the year or the month, a made-up day would be stored as though you "
    "were sure of it, and the rest of the library treats what you confirm as the truth. Storing "
    "your guess as a fact is the one thing this is here to prevent."
)


def confirm_file_date(
    db: Path, *, sha256: str, date_text: str, time_text: str | None = None
) -> RescueOk | RescueRefusal:
    """Record a human-confirmed capture date for one file.

    Refuses rather than half-succeeding: an unknown file, an unparseable date and a bad time all
    leave the catalog exactly as it was. The confirmation itself is `Catalog.confirm_date`, which
    writes the durable row and the ``files`` update in one transaction - this function adds the
    parsing, the refusals, and nothing else. **O(1).**
    """
    when = _parse(date_text, time_text)
    if when is None:
        return {"ok": False, "error": IMPRECISE_DATE_ERROR}
    with Catalog(db) as catalog:
        if catalog.find_by_sha256(sha256) is None:
            return {
                "ok": False,
                "error": (
                    "That photo is not in your library any more, so its date was not changed. "
                    "Reload the page to see what is there now."
                ),
            }
        catalog.confirm_date(sha256, when.isoformat(), confirmed_by="app")
    return {
        "ok": True,
        "captured_at": when.isoformat(),
        "time_assumed": not (time_text and time_text.strip()),
    }
