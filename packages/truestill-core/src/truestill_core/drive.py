"""Drive identity via a marker file.

A destination drive is identified by a marker file at its root -- ``.truestill-drive.json`` --
carrying a truestill-minted ``uuid4``, a human label, and a creation timestamp. Identity is the
marker, **never** the mount path: drive letters and mount points change per session and OS,
and filesystem UUIDs are inconsistent across filesystems (NTFS/FAT serials) and copied by
cloning. A marker's uuid is OS/filesystem-independent, collision-free, and travels with the
data. See ``docs/drive-identity-research.md``.

Cloning a drive copies the marker too, so a clone shares identity until it is deliberately
re-labelled (a fresh uuid) -- correct, since clones are identical at clone time.

Legacy marker compatibility (vaeon -> truestill rename)
-------------------------------------------------------
Drives initialised before the rename carry ``.vaeon-drive.json``. Those drives must keep
working, so:

* **Read falls back.** :func:`read_marker` prefers the canonical name and falls back to any
  name in :data:`LEGACY_MARKER_NAMES`. If both exist, the **canonical file wins** -- a single,
  documented precedence, never a merge.
* **A read never writes.** :func:`read_marker` runs on every filesystem browse in the app and
  on preview/dry-run paths, where writing would break the "planning writes nothing" invariant
  and touch drives that may be mounted read-only. Upgrading is always an explicit act:
  :func:`write_marker` / :func:`create_marker`, or :func:`upgrade_marker`.
* **Identity is preserved verbatim.** An upgrade copies ``uuid``, ``label`` and ``created``
  unchanged. The uuid is the foreign key behind the catalog's ``drives`` / ``file_copies``
  tables; re-minting one would orphan every recorded copy and silently under-report how many
  places a file is safe in -- the exact failure this product exists to prevent.
* **The legacy file is kept, not deleted.** Deleting a file on a user's drive is what the
  copy-only invariant forbids, and retaining it (~100 bytes) means an older build reading the
  legacy name and a current build reading the canonical one agree on identity.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

#: Marker filename written at a drive's root. The only name this code ever writes.
MARKER_NAME = ".truestill-drive.json"

#: Marker filenames still honoured on read, newest first. Never written.
LEGACY_MARKER_NAMES: tuple[str, ...] = (".vaeon-drive.json",)


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
    """The canonical marker path for ``root`` -- where a write would go."""
    return root / MARKER_NAME


def existing_marker_path(root: Path) -> Path | None:
    """The marker file actually present at ``root``: canonical first, then legacy names.

    Returns ``None`` when the drive carries no marker at all. Purely a lookup -- it never
    creates, moves or removes anything.
    """
    canonical = marker_path(root)
    try:
        if canonical.is_file():
            return canonical
        for name in LEGACY_MARKER_NAMES:
            legacy = root / name
            if legacy.is_file():
                return legacy
    except OSError:  # unreadable/disconnected mount -- treat as "no marker"
        return None
    return None


@dataclass(frozen=True, slots=True)
class DriveLocation:
    """What a path turned out to be, when a command wanted a drive root.

    Three outcomes, and telling them apart is the whole point: the path **is** a drive root, the
    path is **inside** one (so there is a correction to offer), or there is no drive above it at
    all (so registration is the answer). Reporting all three as "is the drive connected?" asks a
    question whose answer is plainly yes, and leaves the user with nothing to do.
    """

    given: Path
    root: Path | None = None
    marker: DriveMarker | None = None

    @property
    def is_root(self) -> bool:
        return self.marker is not None and self.root == self.given

    @property
    def is_inside(self) -> bool:
        """The path sits below a drive root - the case that used to read as 'not connected'."""
        return self.marker is not None and self.root != self.given


def path_is_usable_dir(path: Path) -> bool:
    """True when ``path`` is an existing directory we can stat.

    Stale mount hints (ENOENT, ENOTDIR, ``PermissionError`` on a locked Crypto folder, dead
    FUSE) must not escape as raw ``OSError`` to the UI. False means "do not trust this path";
    identity still lives on the marker uuid elsewhere, never here.
    """
    try:
        return path.is_dir()
    except OSError:
        return False


def locate_drive(path: Path) -> DriveLocation:
    """Find the drive a path belongs to, by walking **up** for a marker.

    A user pointing at ``.../The Memory Cabinet/2014`` has connected the drive; they simply named
    a folder inside it. Walking the parents turns an unanswerable error into a correction the
    caller can offer in one click.

    Reads only, and never above the filesystem root. **O(depth)** stat calls - a handful, and
    independent of library size. An unreachable path (missing, not a directory, or raising
    ``OSError`` on access) returns an empty location - never propagates the OS error.
    """
    try:
        exists = path.exists()
    except OSError:
        return DriveLocation(given=path)
    try:
        resolved = path.resolve() if exists else path
    except OSError:
        resolved = path
    for candidate in (resolved, *resolved.parents):
        marker = read_marker(candidate)
        if marker is not None:
            return DriveLocation(given=resolved, root=candidate, marker=marker)
    return DriveLocation(given=resolved)


def read_marker(root: Path) -> DriveMarker | None:
    """Return the drive's marker, or ``None`` if absent or unreadable/invalid.

    Honours legacy marker names (see the module docstring). This function never writes, so a
    legacy drive stays legacy on disk until something explicitly upgrades it.
    """
    found = existing_marker_path(root)
    if found is None:
        return None
    try:
        data = json.loads(found.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    uuid, label, created = data.get("uuid"), data.get("label"), data.get("created")
    if not isinstance(uuid, str) or not isinstance(label, str):
        return None
    return DriveMarker(uuid=uuid, label=label, created=created if isinstance(created, str) else "")


def write_marker(root: Path, marker: DriveMarker) -> None:
    """Write ``marker`` to the drive root under the canonical name (creating the root if needed).

    Any legacy marker present is left untouched, so an interrupted or downgraded run still finds
    a readable identity.
    """
    root.mkdir(parents=True, exist_ok=True)
    marker_path(root).write_text(marker.to_json(), encoding="utf-8")


def needs_marker_upgrade(root: Path) -> bool:
    """True when ``root`` carries only a legacy marker and no canonical one."""
    found = existing_marker_path(root)
    return found is not None and found.name != MARKER_NAME


def upgrade_marker(root: Path) -> DriveMarker | None:
    """Write a canonical marker for a legacy-only drive, preserving identity verbatim.

    Returns the marker now stored canonically, or ``None`` if ``root`` carries no marker at all.
    Already-canonical drives are returned unchanged without a write. The legacy file is
    deliberately left in place (see the module docstring).
    """
    marker = read_marker(root)
    if marker is None:
        return None
    if needs_marker_upgrade(root):
        write_marker(root, marker)  # uuid/label/created copied verbatim
    return marker


def create_marker(root: Path, label: str, *, uuid: str | None = None) -> DriveMarker:
    """Mint (or re-attach, if ``uuid`` given) a marker and write it to ``root``."""
    marker = DriveMarker(
        uuid=uuid or str(uuid4()),
        label=label,
        created=datetime.now(UTC).isoformat(),
    )
    write_marker(root, marker)
    return marker
