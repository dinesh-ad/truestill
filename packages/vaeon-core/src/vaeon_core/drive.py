"""Drive identity via a marker file.

A destination drive is identified by a marker file at its root -- ``.vaeon-drive.json`` --
carrying a vaeon-minted ``uuid4``, a human label, and a creation timestamp. Identity is the
marker, **never** the mount path: drive letters and mount points change per session and OS,
and filesystem UUIDs are inconsistent across filesystems (NTFS/FAT serials) and copied by
cloning. A marker's uuid is OS/filesystem-independent, collision-free, and travels with the
data. See ``docs/drive-identity-research.md``.

Cloning a drive copies the marker too, so a clone shares identity until it is deliberately
re-labelled (a fresh uuid) -- correct, since clones are identical at clone time.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

#: Marker filename written at a drive's root.
MARKER_NAME = ".vaeon-drive.json"


@dataclass(frozen=True, slots=True)
class DriveMarker:
    """The identity of a destination drive, as stored in its marker file."""

    uuid: str
    label: str
    created: str  # ISO-8601, UTC

    def to_json(self) -> str:
        return json.dumps(
            {"uuid": self.uuid, "label": self.label, "created": self.created}, indent=2
        )


def marker_path(root: Path) -> Path:
    return root / MARKER_NAME


def read_marker(root: Path) -> DriveMarker | None:
    """Return the drive's marker, or ``None`` if absent or unreadable/invalid."""
    try:
        data = json.loads(marker_path(root).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    uuid, label, created = data.get("uuid"), data.get("label"), data.get("created")
    if not isinstance(uuid, str) or not isinstance(label, str):
        return None
    return DriveMarker(uuid=uuid, label=label, created=created if isinstance(created, str) else "")


def write_marker(root: Path, marker: DriveMarker) -> None:
    """Write ``marker`` to the drive root (creating the root if needed)."""
    root.mkdir(parents=True, exist_ok=True)
    marker_path(root).write_text(marker.to_json(), encoding="utf-8")


def create_marker(root: Path, label: str, *, uuid: str | None = None) -> DriveMarker:
    """Mint (or re-attach, if ``uuid`` given) a marker and write it to ``root``."""
    marker = DriveMarker(
        uuid=uuid or str(uuid4()),
        label=label,
        created=datetime.now(UTC).isoformat(),
    )
    write_marker(root, marker)
    return marker
