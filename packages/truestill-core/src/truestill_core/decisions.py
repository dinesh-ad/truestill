"""The decisions a rescan cannot recompute, as a document that can live beside a drive marker.

A catalog can be lost - machine formatted, disk died, file corrupted. The photos survive on the
drives; **the decisions do not.** Nothing on disk knows "Wayanad"; a human typed it. Everything
else the catalog holds - hashes, dates, GPS, camera, categories, placements - is recomputable by
reading the files again, and is most of what makes a catalog megabytes rather than kilobytes.

**No server, decided rather than deferred.** The market leader has servers, a subscription and the
photos and still cannot restore a lost catalog. And a catalog holds GPS and timestamps, which are
personal data and a location history in practice, so "we only take folder names" would have been
false. This goes on the user's own drives or nowhere.

**Least recomputable first.** Every entry here except one is a name that could be retyped from
memory. `date_confirmations` is a human OVERRULING the evidence about when a photo was taken, and
re-reading the file reproduces the wrong answer they corrected - scanning actively undoes it.
`skipped_clusters` is the same class: lose it and every declined question is asked again.

**Membership travels as a signature, never as a list.** `events.signature` is already a SHA-256
over its sorted member SHA-256s, so a restore re-clusters and matches. Identical membership
reproduces the signature and the name re-attaches; a mismatch means membership changed, which is
exactly when the name must NOT be auto-applied. Correctness first - being 221 KB smaller at full
membership is the side effect.

**IDENTITY MUST TRAVEL INSIDE THE ROW IT IDENTIFIES.** That is what makes the signature work, and
trips needed the same treatment: their membership lives in `trip_days`, keyed by `trips.id`, and a
rowid is meaningless on a machine that has never seen this catalog. A document that carried those
ids looked like a mapping and was not - the first trip came back holding every other trip's days,
which is worse than a trip going missing because a wrong trip looks like a successful restore. So
a trip carries its OWN days. `trip_days.day` is a primary key, so days are disjoint across trips
and a day list identifies a trip exactly, the way a signature identifies an event.
"""

from __future__ import annotations

import contextlib
import errno
import json
import os
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from truestill_core.drive import DriveReach, drive_path_hint, drive_reach

#: Bumped only when a reader must REFUSE a document, never for an added field. Adding a field is
#: forward-compatible by construction (see :func:`from_document`), so a bump would be a false alarm
#: that strands a user's names on a disk they can see.
FORMAT_VERSION = 1

#: Settings excluded from the document. `path_hint.drive.<uuid>` holds an absolute local path - a
#: username, a folder layout, and in one real library the existence of a Crypto Folder. This file
#: lands on a drive the user may lend or sell, and a path from another machine is useless anyway.
#: Matched by PREFIX so a future `path_hint.something` is excluded without another edit.
#:
#: `decisions.` is this feature's own bookkeeping and is excluded for a different reason: it is
#: not a decision, and restoring it onto another machine would carry that machine's answer to
#: "have I written the upgrade copy yet" - the document would ship the reason it is never written
#: again. Machine-local notes about the backup do not belong in the backup.
_EXCLUDED_SETTING_PREFIXES = ("path_hint.", "decisions.")

#: When this catalog last put its decisions on a drive. Machine-local; see the exclusion above.
DECISIONS_SAVED_AT_KEY = "decisions.saved_at"

#: Top-level keys this version writes. Anything else in a document came from a newer version and
#: is carried through untouched - see :func:`from_document`.
_KNOWN_KEYS = frozenset(
    {
        "format",
        "written",
        "drive",
        "settings",
        "trips",
        "events",
        "skipped_clusters",
        "date_confirmations",
        "albums",
    }
)


@dataclass(frozen=True, slots=True)
class Decisions:
    """Everything a human decided, and nothing a machine can re-derive."""

    drive_uuid: str = ""
    drive_label: str = ""
    drive_notes: str | None = None
    settings: dict[str, str] = field(default_factory=dict)
    #: Each trip carries its own ``days``; see the module note on identity travelling in the row.
    trips: tuple[dict[str, Any], ...] = ()
    events: tuple[dict[str, Any], ...] = ()
    skipped_clusters: tuple[str, ...] = ()
    date_confirmations: tuple[dict[str, Any], ...] = ()
    albums: tuple[dict[str, Any], ...] = ()
    written: str = ""
    #: Sections a NEWER version wrote that this one does not understand. Held so a downgrade can
    #: write them back rather than deleting someone's data - see :func:`from_document`.
    unknown: dict[str, Any] = field(default_factory=dict)


def publishable_settings(settings: dict[str, str]) -> dict[str, str]:
    """The settings that may leave this machine. Excludes local paths; see the module note."""
    return {
        key: value
        for key, value in settings.items()
        if not key.startswith(_EXCLUDED_SETTING_PREFIXES)
    }


def to_document(decisions: Decisions) -> dict[str, Any]:
    """Render for the drive: plain JSON types, readable by a person with a text editor.

    Unknown sections are written back FIRST so a known key can never be shadowed by one.
    """
    document: dict[str, Any] = dict(decisions.unknown)
    document.update(
        {
            "format": FORMAT_VERSION,
            "written": decisions.written,
            "drive": {
                "uuid": decisions.drive_uuid,
                "label": decisions.drive_label,
                "notes": decisions.drive_notes,
            },
            "settings": publishable_settings(decisions.settings),
            "trips": [dict(trip) for trip in decisions.trips],
            "events": [dict(event) for event in decisions.events],
            "skipped_clusters": list(decisions.skipped_clusters),
            "date_confirmations": [dict(row) for row in decisions.date_confirmations],
            "albums": [dict(album) for album in decisions.albums],
        }
    )
    return document


def from_document(document: dict[str, Any]) -> Decisions:
    """Read a document, tolerating both older and newer versions. **Never raises on shape.**

    **Missing sections read as empty.** An older document simply has fewer; that is not corruption,
    and refusing it would strand names on a disk the user can see.

    **Unknown sections are KEPT, not ignored.** Tolerating them would be easy - skip and move on -
    but an older Truestill that reads a drive, restores, and later writes it back would then
    silently delete the newer version's data. The user downgrades once and loses their captions.
    Preservation is the requirement; surviving the read is only half of it.
    """
    drive = document.get("drive") or {}
    return Decisions(
        drive_uuid=str(drive.get("uuid") or ""),
        drive_label=str(drive.get("label") or ""),
        drive_notes=drive.get("notes"),
        settings=dict(document.get("settings") or {}),
        trips=tuple(dict(trip) for trip in document.get("trips") or ()),
        events=tuple(dict(event) for event in document.get("events") or ()),
        skipped_clusters=tuple(document.get("skipped_clusters") or ()),
        date_confirmations=tuple(dict(r) for r in document.get("date_confirmations") or ()),
        albums=tuple(dict(a) for a in document.get("albums") or ()),
        written=str(document.get("written") or ""),
        unknown={k: v for k, v in document.items() if k not in _KNOWN_KEYS},
    )


@dataclass(frozen=True, slots=True)
class ApplyReport:
    """What an apply changed, and what it deliberately did not."""

    applied: dict[str, int] = field(default_factory=dict)
    #: Decisions the catalog already held in a NEWER form. Skipped, never overwritten.
    skipped_newer_locally: tuple[str, ...] = ()
    #: Event names whose signature matched nothing here, so membership changed. Reported, never
    #: guessed at.
    unmatched_events: tuple[str, ...] = ()
    #: Trips whose days are already claimed by a DIFFERENT trip here. A day belongs to at most one
    #: trip, so these cannot be applied at all - and a skip with no channel is how the absorbed-
    #: days defect stayed invisible. One meaning per field, deliberately.
    conflicting_trips: tuple[str, ...] = ()
    #: Trips the document carries no days for, so there is nowhere to put them. Distinct from a
    #: conflict: nothing is competing, the document simply does not say which days they are.
    trips_without_days: tuple[str, ...] = ()
    #: Sections this version carries but cannot yet apply.
    not_applied: tuple[str, ...] = ()


def _shared_decisions(catalog: Any) -> Decisions:
    """Every decision except the drive block, which is the only part that differs per drive.

    Split out so a save to N drives is **one pass over the catalog plus O(1) per drive** rather
    than N passes: the decision tables are catalog-wide, and re-reading them once per drive would
    make the cost of owning a second backup drive a second full read.
    """
    days_by_trip: dict[int, list[str]] = {}
    for day, trip_id in catalog.all_trip_days().items():
        days_by_trip.setdefault(int(trip_id), []).append(str(day))
    return Decisions(
        settings=publishable_settings(catalog.all_settings()),
        trips=tuple(
            {
                "name": r["name"],
                "slug": r["slug"],
                "start": r["start_date"],
                "end": r["end_date"],
                # The days, not the rowid that found them. See the module note.
                "days": sorted(days_by_trip.get(int(r["id"]), [])),
            }
            for r in catalog.all_trips()
        ),
        events=tuple(
            {
                "name": r["name"],
                "slug": r["slug"],
                "start": r["start_date"],
                "signature": r["signature"],
            }
            for r in catalog.all_events()
        ),
        skipped_clusters=tuple(str(r) for r in sorted(catalog.skipped_signatures())),
        date_confirmations=tuple(
            {
                "sha256": r["sha256"],
                "captured_at": r["captured_at"],
                "confirmed_at": r["confirmed_at"],
                "confirmed_by": r["confirmed_by"],
            }
            for r in catalog.all_date_confirmations()
        ),
        albums=tuple({"name": name} for name in catalog.all_album_names()),
    )


def _with_drive(shared: Decisions, drive: Any, drive_uuid: str) -> Decisions:
    """The shared decisions, addressed to one drive."""
    return replace(
        shared,
        drive_uuid=str(drive["uuid"]) if drive else drive_uuid,
        drive_label=str(drive["label"]) if drive else "",
        drive_notes=drive["notes"] if drive else None,
    )


def gather_decisions(catalog: Any, drive_uuid: str) -> Decisions:
    """Read the decisions a rescan could not recompute. **Read-only; writes nothing.**

    Column-by-column rather than ``SELECT *``, and that is the privacy guard rather than a style
    preference: a new column added to `files` or `settings` later cannot arrive on a user's drive
    by default. Every field here was chosen; nothing is inherited.
    """
    return _with_drive(_shared_decisions(catalog), catalog.drive_row(drive_uuid), drive_uuid)


def _apply_trips(
    catalog: Any,
    trips: tuple[dict[str, Any], ...],
    bump: Callable[[str], None],
) -> tuple[list[str], list[str]]:
    """Restore trips by their own days. Returns ``(conflicting, dayless)`` names.

    **A day belongs to at most one trip** (`trip_days.day` is a primary key), which is what makes
    a day list an identity rather than a hint - and what makes every outcome here decidable
    without a rowid.
    """
    conflicting: list[str] = []
    dayless: list[str] = []
    # Day -> the name of the trip holding it. Read once and kept in step as trips are created, so
    # a document that names one day twice cannot make `create_trip` fail on the day primary key.
    claimed_days: dict[str, str] = catalog.named_trip_days()

    for trip in trips:
        name = str(trip["name"])
        days = sorted(str(day) for day in trip.get("days") or ())
        if not days:
            dayless.append(name)
            continue
        holders = {claimed_days.get(day) for day in days}
        if holders == {name}:
            continue  # already restored, every day of it: a second apply is a no-op, not a clash
        if holders != {None}:
            # A partial claim is not a partial restore - it is a trip that cannot be applied at
            # all. Reported rather than skipped: silence here is what let one trip absorb
            # another's days with nothing saying so.
            conflicting.append(name)
            continue
        catalog.create_trip(
            name=name,
            slug=str(trip["slug"]),
            start_date=str(trip["start"]),
            end_date=str(trip["end"]),
            days=days,
        )
        for day in days:
            claimed_days[day] = name
        bump("trips")

    return conflicting, dayless


def apply_decisions(catalog: Any, decisions: Decisions) -> ApplyReport:  # noqa: PLR0912
    """Write the decisions into a catalog. **Idempotent**: a second apply changes nothing.

    Every branch asks whether the catalog already holds this decision before writing, so the count
    reported is what actually changed rather than what was offered.
    """
    applied: dict[str, int] = {}
    skipped: list[str] = []
    unmatched: list[str] = []

    def bump(section: str) -> None:
        applied[section] = applied.get(section, 0) + 1

    if decisions.drive_uuid:
        row = catalog.drive_row(decisions.drive_uuid)
        if row is None or (decisions.drive_label and row["label"] != decisions.drive_label):
            catalog.upsert_drive(uuid=decisions.drive_uuid, label=decisions.drive_label or "drive")
            bump("drive")

    for key, value in decisions.settings.items():
        if catalog.get_setting(key) != value:
            catalog.set_setting(key, value)
            bump("settings")

    conflicting, dayless = _apply_trips(catalog, decisions.trips, bump)

    for event in decisions.events:
        signature = str(event["signature"])
        existing = catalog.event_by_signature(signature)
        if existing is None:
            # Membership changed, so this is not that event. Reported, never guessed at - the same
            # distinction the screen makes when it declines to claim a grown cluster is named.
            unmatched.append(str(event["name"]))
            continue
        if existing["name"] != event["name"]:
            catalog.record_event(
                name=str(event["name"]),
                slug=str(event["slug"]),
                start_date=str(event["start"]),
                file_count=int(existing["file_count"] or 0),
                signature=signature,
            )
            bump("events")

    known_skips = catalog.skipped_signatures()
    for signature in decisions.skipped_clusters:
        if signature not in known_skips:
            catalog.record_skip(signature)
            bump("skipped_clusters")

    for confirmation in decisions.date_confirmations:
        sha = str(confirmation["sha256"])
        incoming_at = str(confirmation.get("confirmed_at") or "")
        held = catalog.date_confirmation_for(sha)
        if held is not None:
            # NEVER overwrite a later correction with an earlier one. This is the only decision
            # with no second source: the file reproduces the wrong answer the human corrected, so
            # an overwrite is unrecoverable. Ties count as already-held, not as a change.
            if str(held["confirmed_at"] or "") >= incoming_at:
                if str(held["captured_at"]) != str(confirmation["captured_at"]):
                    skipped.append("date_confirmations")
                continue
        elif not catalog.knows_content(sha):
            # The content is not in this catalog yet. The confirmation is kept in the document and
            # simply not applied; a later scan plus a re-apply lands it.
            skipped.append("date_confirmations")
            continue
        catalog.confirm_date(
            sha,
            str(confirmation["captured_at"]),
            confirmed_by=confirmation.get("confirmed_by"),
        )
        bump("date_confirmations")

    return ApplyReport(
        applied=applied,
        skipped_newer_locally=tuple(dict.fromkeys(skipped)),
        unmatched_events=tuple(unmatched),
        conflicting_trips=tuple(conflicting),
        trips_without_days=tuple(dayless),
        not_applied=("albums",) if decisions.albums else (),
    )


#: The document's filename, beside `.truestill-drive.json` at a drive root. A sibling rather than
#: a section of the marker: the marker is identity - tiny, stable, read on every reach check - and
#: this churns.
DECISIONS_NAME = ".truestill-decisions.json"


@dataclass(frozen=True, slots=True)
class WriteOutcome:
    """What happened when a document was offered to a drive. **Never an exception.**"""

    written: bool
    path: Path | None = None
    #: Plain words for a person, when the drive would not take it. `None` on success.
    error: str | None = None


def _explain(error: OSError) -> str:
    """What went wrong, in words a person can act on rather than an errno."""
    if error.errno in (errno.EROFS, errno.EACCES, errno.EPERM):
        return "the drive is read-only, or this account cannot write to it"
    if error.errno == errno.ENOSPC:
        return "there is no space left on the drive"
    if error.errno in (errno.ENOENT, errno.ENOTDIR):
        return "the drive is not there any more"
    if error.errno == errno.EIO:
        return "the drive stopped responding part way through"
    return error.strerror or str(error)


def write_decisions(root: Path, decisions: Decisions) -> WriteOutcome:
    """Put the document on a drive, atomically, and **never raise**.

    **Atomic, because this is the only copy of names a human typed.** Written to a sibling temp
    file, flushed, `fsync`ed, then `os.replace`d over the target - so a crash leaves either the
    previous good document or the new one, never a half of either. A truncated file at the right
    path is worse than no file, because it looks like a backup.

    **The temp sits in the SAME directory as the target**, which is what makes the rename atomic:
    a temp in the system temp directory would turn the final step into a copy across filesystems,
    which is exactly the non-atomic write this exists to avoid.

    **Nothing here may propagate into the caller.** Naming a trip must succeed even when the drive
    write does not - a decision lost because its own backup failed is the worst trade available -
    so every failure comes back as a reported outcome. A read-only disk, a full one and one pulled
    out mid-write are ordinary events for removable media, not exceptions.
    """
    if not root.is_absolute():
        # `Path("")` normalises to `Path(".")`, which IS a directory - so an `is_dir` check alone
        # lets an empty root write the document into the working directory. Caught by this
        # module's own test doing exactly that. A drive root is always absolute in practice;
        # requiring it turns a silent misfile into a reported refusal.
        return WriteOutcome(written=False, error="a drive root must be a full path")
    if not root.is_dir():
        return WriteOutcome(written=False, error="the drive is not there any more")

    target = root / DECISIONS_NAME
    temp = root / f"{DECISIONS_NAME}.writing"
    try:
        payload = json.dumps(to_document(decisions), indent=2, sort_keys=True) + "\n"
        with temp.open("w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        temp.replace(target)
    except OSError as error:
        # A drive that will not take the write may not take the cleanup either.
        with contextlib.suppress(OSError):
            temp.unlink(missing_ok=True)
        return WriteOutcome(written=False, error=_explain(error))
    return WriteOutcome(written=True, path=target)


@dataclass(frozen=True, slots=True)
class DocumentOnDrive:
    """What is already at a drive root. **Never an exception.**"""

    #: A file is there. True even when it could not be read - which is the case that matters.
    found: bool = False
    decisions: Decisions | None = None
    #: Why it could not be read. `None` when there was nothing to read, or the read worked.
    error: str | None = None


def read_decisions(root: Path) -> DocumentOnDrive:
    """Read the document at a drive root, if there is one. **Never raises.**

    **`found` and `decisions` are separate answers on purpose.** "Nothing is there" and "something
    is there and I cannot read it" lead to opposite actions: the first may be written over freely,
    the second must not be touched. Collapsing them to `None` is how a damaged copy of somebody's
    names becomes no copy at all.
    """
    target = root / DECISIONS_NAME
    try:
        text = target.read_text(encoding="utf-8")
    except FileNotFoundError:
        return DocumentOnDrive()
    except OSError as error:
        return DocumentOnDrive(found=True, error=_explain(error))
    try:
        document = json.loads(text)
    except ValueError:
        return DocumentOnDrive(found=True, error="the file on the drive is not readable JSON")
    if not isinstance(document, dict):
        return DocumentOnDrive(
            found=True, error="the file on the drive is not a decisions document"
        )
    return DocumentOnDrive(found=True, decisions=from_document(document))


#: Sections compared before a write, to refuse one that would lose decisions the drive already
#: holds. `settings` is deliberately absent: UI preferences churn per machine and per version, so
#: a difference there is not evidence of another catalog's work.
_LOSS_KEYS: tuple[tuple[str, Callable[[Decisions], set[str]]], ...] = (
    ("trips", lambda d: {str(t.get("name")) for t in d.trips}),
    ("events", lambda d: {str(e.get("signature")) for e in d.events}),
    ("skipped_clusters", lambda d: {str(s) for s in d.skipped_clusters}),
    ("date_confirmations", lambda d: {str(c.get("sha256")) for c in d.date_confirmations}),
    ("albums", lambda d: {str(a.get("name")) for a in d.albums}),
)


def would_lose(existing: Decisions, fresh: Decisions) -> tuple[str, ...]:
    """Sections where the drive holds decisions ``fresh`` does not. **`O(document)`.**

    **This is the same rule as the unknown-section merge, applied to sections we understand.** A
    re-attached drive carries names a rebuilt catalog has never seen; writing over them destroys
    the only copy, which is precisely what this feature exists to prevent. So the write does not
    happen and the caller is told which sections stopped it.

    Its one false positive is a decision the user DELETED locally: the drive still holds it, so
    the write refuses until a restore reconciles the two. Reported rather than silently resolved,
    because guessing which side is intentional is how the other direction loses data.
    """
    return tuple(name for name, of in _LOSS_KEYS if of(existing) - of(fresh))


def merge_onto_drive(existing: Decisions | None, fresh: Decisions) -> Decisions:
    """``fresh``, carrying forward sections only the drive's copy understands.

    **Read-merge-replace, never write.** :func:`to_document` preserves unknown sections out of a
    `Decisions` that came from a document - but a trigger's object comes from
    :func:`gather_decisions`, and the catalog has never held those sections, so its `unknown` is
    empty. Without this read, a user who downgrades and renames one trip loses the newer version's
    captions to the code written to keep them.
    """
    if existing is None or not existing.unknown:
        return fresh
    return replace(fresh, unknown={**existing.unknown, **fresh.unknown})


class SaveOutcome(StrEnum):
    """What happened to one drive. Four states, because three of them need different words."""

    WRITTEN = "written"
    UNREACHABLE = "unreachable"  # not plugged in, or something else is at the remembered path
    WOULD_LOSE = "would_lose"  # its copy holds decisions this catalog does not
    FAILED = "failed"  # read-only, full, unreadable copy, pulled out mid-write


@dataclass(frozen=True, slots=True)
class DriveSave:
    """One drive's result, in a form a surface can turn into a sentence."""

    uuid: str
    label: str
    outcome: SaveOutcome
    #: Plain words for a person: what stopped it, or which sections would have been lost.
    detail: str = ""


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def save_decisions_to_reachable_drives(
    catalog: Any, *, stamp: str | None = None
) -> tuple[DriveSave, ...]:
    """Put the catalog's decisions on every reachable registered drive. **Never raises.**

    **One catalog pass, then `O(1)` per drive** plus one read and one write each: the decision
    tables are catalog-wide and only the drive block differs, so a second backup drive costs a
    second file write rather than a second full read.

    **One stamp for the whole run.** Restore resolves disagreement by newest `written`, so two
    drives saved by the same run must not be able to disagree about which is newer.

    **A failure here never reaches the user's own operation.** Naming a trip must succeed even
    when the backup of that name does not; the outcome is reported instead.
    """
    drives = catalog.registered_drives()
    if not drives:
        return ()

    shared = replace(_shared_decisions(catalog), written=stamp or _utc_now())
    results: list[DriveSave] = []
    for row in drives:
        uuid = str(row["uuid"])
        label = str(row["label"] or "")
        hint = catalog.get_setting(drive_path_hint(uuid))
        if drive_reach(hint, uuid) is not DriveReach.CONNECTED:
            results.append(DriveSave(uuid, label, SaveOutcome.UNREACHABLE, "not connected"))
            continue

        root = Path(str(hint))
        found = read_decisions(root)
        if found.error is not None:
            results.append(DriveSave(uuid, label, SaveOutcome.FAILED, found.error))
            continue

        fresh = _with_drive(shared, row, uuid)
        if found.decisions is not None:
            lost = would_lose(found.decisions, fresh)
            if lost:
                results.append(
                    DriveSave(
                        uuid,
                        label,
                        SaveOutcome.WOULD_LOSE,
                        f"this drive holds {', '.join(lost)} this catalog does not; restore first",
                    )
                )
                continue
            fresh = merge_onto_drive(found.decisions, fresh)

        outcome = write_decisions(root, fresh)
        results.append(
            DriveSave(uuid, label, SaveOutcome.WRITTEN)
            if outcome.written
            else DriveSave(uuid, label, SaveOutcome.FAILED, outcome.error or "")
        )
    return tuple(results)


def ensure_decisions_on_drives(
    catalog: Any, *, stamp: str | None = None
) -> tuple[DriveSave, ...] | None:
    """The upgrade write: put the decisions on the drives ONCE for a catalog that predates this.

    Returns `None` when it has already happened, so a caller can stay silent.

    **Existing users are the ones this protects**, and a trigger of "after a decision changes"
    reaches them only when they next rename something. The user most at risk has a finished
    library and has stopped naming things, so for them that trigger never fires at all.

    **Recorded only when a drive actually took it.** A user whose drive was in a drawer at upgrade
    time must get the write when they next plug it in; recording the attempt would mean they never
    do, which is the Lightroom failure - a backup the user believes in and does not have.
    """
    if catalog.get_setting(DECISIONS_SAVED_AT_KEY):
        return None
    when = stamp or _utc_now()
    results = save_decisions_to_reachable_drives(catalog, stamp=when)
    if any(r.outcome is SaveOutcome.WRITTEN for r in results):
        catalog.set_setting(DECISIONS_SAVED_AT_KEY, when)
    return results
