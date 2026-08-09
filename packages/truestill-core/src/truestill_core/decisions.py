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
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

#: Bumped only when a reader must REFUSE a document, never for an added field. Adding a field is
#: forward-compatible by construction (see :func:`from_document`), so a bump would be a false alarm
#: that strands a user's names on a disk they can see.
FORMAT_VERSION = 1

#: Settings excluded from the document. `path_hint.drive.<uuid>` holds an absolute local path - a
#: username, a folder layout, and in one real library the existence of a Crypto Folder. This file
#: lands on a drive the user may lend or sell, and a path from another machine is useless anyway.
#: Matched by PREFIX so a future `path_hint.something` is excluded without another edit.
_EXCLUDED_SETTING_PREFIXES = ("path_hint.",)

#: Top-level keys this version writes. Anything else in a document came from a newer version and
#: is carried through untouched - see :func:`from_document`.
_KNOWN_KEYS = frozenset(
    {
        "format",
        "written",
        "drive",
        "settings",
        "trips",
        "trip_days",
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
    trips: tuple[dict[str, Any], ...] = ()
    trip_days: dict[str, int] = field(default_factory=dict)
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
            "trip_days": dict(decisions.trip_days),
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
        trip_days=dict(document.get("trip_days") or {}),
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
    #: Sections this version carries but cannot yet apply.
    not_applied: tuple[str, ...] = ()


def gather_decisions(catalog: Any, drive_uuid: str) -> Decisions:
    """Read the decisions a rescan could not recompute. **Read-only; writes nothing.**

    Column-by-column rather than ``SELECT *``, and that is the privacy guard rather than a style
    preference: a new column added to `files` or `settings` later cannot arrive on a user's drive
    by default. Every field here was chosen; nothing is inherited.
    """
    drive = catalog.drive_row(drive_uuid)
    return Decisions(
        drive_uuid=str(drive["uuid"]) if drive else drive_uuid,
        drive_label=str(drive["label"]) if drive else "",
        drive_notes=drive["notes"] if drive else None,
        settings=publishable_settings(catalog.all_settings()),
        trips=tuple(
            {"name": r["name"], "slug": r["slug"], "start": r["start_date"], "end": r["end_date"]}
            for r in catalog.all_trips()
        ),
        trip_days=catalog.all_trip_days(),
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

    for trip in decisions.trips:
        days = sorted(d for d, _ in decisions.trip_days.items())
        if not days:
            continue
        if catalog.trip_for_day(days[0]) is not None:
            continue  # already claimed: name-once, and re-creating would mint a second identity
        catalog.create_trip(
            name=str(trip["name"]),
            slug=str(trip["slug"]),
            start_date=str(trip["start"]),
            end_date=str(trip["end"]),
            days=days,
        )
        bump("trips")

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
        not_applied=("albums",) if decisions.albums else (),
    )
