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

from collections.abc import Sequence
from datetime import datetime, time
from pathlib import Path
from typing import Literal, NotRequired, TypedDict

from truestill_core.catalog_session import open_catalog
from truestill_core.dates import resolve_capture_datetime
from truestill_core.exif import read_metadata
from truestill_core.models import DateSource
from truestill_core.path_reach import Reach, reach

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


#: Tiers whose date came out of the file's own metadata. Only for these can the card say the
#: file "still says <year> inside" - a filename-dated or undated photo carries nothing, and
#: claiming otherwise would be a fresh false statement from the screen built to remove them.
_EMBEDDED_TIERS = frozenset(
    {
        DateSource.EXIF.value,
        DateSource.TAKEOUT.value,
        DateSource.TAKEOUT_UPLOAD.value,
        DateSource.INFERRED_LOCAL.value,
        DateSource.HUMAN_CONFIRMED.value,
    }
)


def _year(value: str | None) -> str | None:
    return None if not value else value[:4]


def _states(*, now: datetime, previous: str | None, source: str | None, baked: bool) -> list[str]:
    """The three states, concretely. **Deliberately not generalised.**

    "Changes apply on the next operation" is true and useless - it tells a user nothing about
    which of their photos is where. Each sentence carries the real value instead.
    """
    filed = _year(previous)
    lines = [f"Recorded. This photo is now dated {now.date().isoformat()} in your library."]
    lines.append(
        f"It is still filed under {filed} on disk."
        if filed
        else "It has not moved on disk; it is still where it was."
    )
    if baked and previous:
        # The bytes carry the date last written into them, which is a previous confirmation -
        # not the original evidence and not the new answer.
        lines.append(f"The file itself still says {filed} inside, from the last time it was set.")
    elif source in _EMBEDDED_TIERS and filed:
        lines.append(f"The file itself still says {filed} inside.")
    else:
        lines.append("The file itself has no date inside it, and still has none.")
    return lines


def _next_steps() -> list[NextStep]:
    """Both follow-ups, offered. Neither is performed, and neither is implied to have been."""
    return [
        {
            "action": "bake",
            "label": "Set the dates in the files",
            "detail": "Writes the date inside each photo so other apps read it too.",
            "done": False,
        },
        {
            "action": "migrate",
            "label": "Move files to match",
            "detail": "Refiles photos into the folders their corrected dates belong in.",
            "done": False,
        },
    ]


class NextStep(TypedDict):
    """An offer, never an action. Each of these writes to user files and has its own
    preview-then-typed-confirm; nothing here runs one."""

    action: Literal["bake", "migrate"]
    label: str
    detail: str
    #: Always False. Present so a renderer cannot accidentally imply a step has happened by
    #: omitting the state - the card's whole job is that a user closing the tab believes
    #: something true.
    done: bool


class RescueOk(TypedDict):
    ok: Literal[True]
    #: What the library now believes, for a screen that must say it back concretely.
    captured_at: str
    #: True when the time was assumed rather than supplied, so the UI can say which.
    time_assumed: bool
    #: The three states, as sentences with real values in them. Built here rather than in the
    #: browser for the same reason `models.status_label` and `date_explain` are: one home, so
    #: the CLI could say the identical thing if it ever gains this surface.
    states: list[str]
    next_steps: list[NextStep]


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
    with open_catalog(db) as catalog:
        row = catalog.find_by_sha256(sha256)
        if row is None:
            return {
                "ok": False,
                "error": (
                    "That photo is not in your library any more, so its date was not changed. "
                    "Reload the page to see what is there now."
                ),
            }
        # Read the outgoing state BEFORE confirming: the card describes what the file still is,
        # and after the write the catalog no longer remembers it.
        previous = None if row["captured_at"] is None else str(row["captured_at"])
        source = None if row["date_source"] is None else str(row["date_source"])
        baked = catalog.copy_is_baked(sha256)
        catalog.confirm_date(sha256, when.isoformat(), confirmed_by="app")
    return {
        "ok": True,
        "captured_at": when.isoformat(),
        "time_assumed": not (time_text and time_text.strip()),
        "states": _states(now=when, previous=previous, source=source, baked=baked),
        "next_steps": _next_steps(),
    }


#: **truestill never creates these files.** Its own metadata writes pass ``-overwrite_original``
#: (`exif._WRITE_FLAGS`), which keeps no sidecar - a fact pinned by
#: `test_a_video_write_leaves_no_original_sidecar`. So every ``*_original`` beside a user's photo
#: came from **their own** exiftool use, on their own terms, at a time truestill knows nothing
#: about.
#:
#: That is the whole reason this is an **offer and never an authority**. truestill cannot tell
#: whether the sidecar holds the original truth or the mistake its owner was busy correcting, so
#: it may surface the disagreement and must not resolve it. The framing does not survive in
#: anyone's head, which is why it is written here rather than in a design doc.
#:
#: `(bbb)`'s safety half already ensures these are never ingested as a second photo:
#: `organizer.is_exiftool_original_backup` routes them to ``SourceScan.exiftool_backups`` at
#: scan time, for every caller including ``--all-files``.
_ORIGINAL_SUFFIX = "_original"


class Candidate(TypedDict):
    """What truestill can say about a sidecar for one file.

    Three statuses, kept separate on purpose. ``none`` is a fact about the **file** - we looked
    and there is nothing to offer. ``unreachable`` is a fact about **truestill's reach** - we
    could not look at all. Collapsing them would let a screen tell a user their photo has no
    backup when the truth is that nobody checked.
    """

    status: Literal["offer", "none", "unreachable"]
    #: Present only for ``offer``: the sidecar's capture date, for pre-filling the rescue field.
    captured_at: NotRequired[str]


#: Why a sidecar can be unreachable, and it is usually this rather than a bug.
#:
#: The sibling lives beside the file exiftool edited, which is the **source**, and the catalog's
#: only record of that is ``files.source_path`` - **absolute, and not machine-portable: see
#: `BACKLOG.md` (xx)**. After a machine move it is dead, and in copy mode the user may have
#: deleted the source directory entirely once the library was organized.
#:
#: So this feature will frequently be unavailable, and that is **honest rather than broken** -
#: it reports that it could not look instead of asserting there is nothing there. **It improves
#: automatically when (xx) portability or (yy) reconnect lands**; whoever builds those should
#: know this surface is a beneficiary.
_UNREACHABLE = "the source this was imported from cannot be reached"


def original_candidates(db: Path, sha256s: Sequence[str]) -> dict[str, Candidate]:
    """Sidecar candidates for one page of files, keyed by content hash.

    **Complexity: O(page)** stats, plus one batched exiftool read for the files that actually
    have a sidecar - so cost is proportional to **hits, not rows**. That is what makes it
    affordable to compute eagerly for a page of 50; doing it for a whole tier of 2,300 files
    would be a multi-minute open.

    A sidecar whose date **equals** the live one is deliberately not offered: accepting it would
    record ``HUMAN_CONFIRMED`` - the most trusted tier - on the strength of the machine agreeing
    with itself, and on a screen about trust an offer that changes nothing is worse than noise.
    """
    result: dict[str, Candidate] = {sha: {"status": "unreachable"} for sha in sha256s}
    siblings: dict[Path, tuple[str, datetime | None]] = {}
    with open_catalog(db) as catalog:
        for sha in sha256s:
            row = catalog.find_by_sha256(sha)
            if row is None or not row["source_path"]:
                continue
            source = Path(str(row["source_path"]))
            sidecar = source.with_name(source.name + _ORIGINAL_SUFFIX)
            # ⚠ `reach`, not `is_file()`, and the comment below is why. On 3.14 `is_file()`
            # returns False for a refused path, so this fell through and reported "none" -
            # exactly the "nothing there" the next line forbids. `(aey)`
            found = reach(sidecar)
            if found is Reach.REFUSED:
                continue  # unreadable mount: cannot look, which is not "nothing there"
            present = found is Reach.FILE
            if not source.parent.is_dir():
                continue
            if not present:
                result[sha] = {"status": "none"}
                continue
            current = row["captured_at"]
            siblings[sidecar] = (sha, None if current is None else datetime.fromisoformat(current))

    if siblings:
        metadata = read_metadata(list(siblings))
        for sidecar, (sha, current) in siblings.items():
            when, _source, _tag = resolve_capture_datetime(sidecar, metadata.get(sidecar, {}))
            # Offered only when it parses AND differs. Same date, or no date, is "none".
            if when is None or when == current:
                result[sha] = {"status": "none"}
            else:
                result[sha] = {"status": "offer", "captured_at": when.isoformat()}
    return result
