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
