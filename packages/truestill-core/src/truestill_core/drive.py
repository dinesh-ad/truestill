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
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, NamedTuple, Protocol
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


class DriveReach(StrEnum):
    """Whether a registered drive is here right now. **Three states, not a boolean.**

    A boolean would have to fold ``UNKNOWN`` into one of the other two, and both folds lie. Read
    as connected it invents a drive that may not be plugged in; read as offline it tells someone
    their backup drive is missing when the truth is only that truestill has never recorded where
    it lives. The alarming reading is the worse one for a custody tool, and the honest answer -
    *we do not know* - is available, so it is reported.

    ``UNKNOWN`` is not a corner case: a drive registered and used entirely from the CLI has no
    remembered path until something records one, so it is the *normal* state for that user.
    """

    CONNECTED = "connected"  # the remembered path is there and carries this drive's marker
    OFFLINE = "offline"  # we know where it was; it is not there now
    UNKNOWN = "unknown"  # no remembered path, so there is nothing to check


def drive_path_hint(uuid: str) -> str:
    """Settings key for where a drive was last seen mounted.

    A *hint*, never identity: a drive that remounts elsewhere is the same drive, and this key is
    simply stale until something sees it again. It lives in core rather than in the app because
    both front-ends need it - the CLI cannot import `truestill_app` (`IMPLEMENTATION_STANDARDS`
    §2), and a second key spelled the same way in two packages is how they drift apart.
    """
    return f"path_hint.drive.{uuid}"


class CustodyFreshness(NamedTuple):
    """How old the custody claim is, and which places have never been looked at.

    `(abg)`. The catalog reports history as if it were state: a `file_copies` row is a true
    statement about the moment it was written and is read as a true statement about now. This
    carries the age of that statement to the surfaces that make the claim.

    **Pure, and it touches nothing.** It reads rows the caller already has - `last_verified` has
    been on `drives` all along and is already shown per drive; it simply never reached the number
    a person reads. No disk access, no query, no freshness *tracking* being added.

    **Lives in core because both surfaces make the claim.** The CLI's `status` and the app's
    custody strip would otherwise each grow their own version, which is the drift §4 names.
    """

    #: The OLDEST check across the places counted, because a claim is only as fresh as its
    #: weakest leg. `None` when any of them has never been checked - no single date would then be
    #: true of the whole claim.
    checked_at: str | None
    #: Labels of counted places never checked. Named, not counted: the name is the only clue a
    #: reader has to what happened.
    never_checked: tuple[str, ...]


def custody_freshness(drives: Iterable[Any]) -> CustodyFreshness:
    """Freshness for the drives that HOLD copies. Filtering to those is the caller's job."""
    never = sorted(str(d["label"]) for d in drives if not d["last_verified"])
    checked = [str(d["last_verified"]) for d in drives if d["last_verified"]]
    return CustodyFreshness(
        checked_at=min(checked) if checked and not never else None,
        never_checked=tuple(never),
    )


def drive_reach(hint: str | None, uuid: str) -> DriveReach:
    """Where ``uuid`` stands, given the path it was last seen at. **O(1)** - one marker read.

    Pure on purpose: it takes the remembered path rather than a `Catalog`, so it is the same
    answer on both surfaces, is trivially testable, and cannot become a second reachability
    mechanism by accident. Callers do their own settings read.

    A *different* drive at the remembered path is ``OFFLINE``, not ``CONNECTED``: the question is
    whether **this** drive is reachable, and someone else's marker is not a yes.
    """
    if not hint:
        return DriveReach.UNKNOWN
    marker = read_marker(Path(hint))
    if marker is None:
        return DriveReach.OFFLINE
    return DriveReach.CONNECTED if marker.uuid == uuid else DriveReach.OFFLINE


class _SettingsReader(Protocol):
    """The one thing :func:`reach_of` needs from a catalog.

    A protocol rather than importing `Catalog`: `drive.py` is a leaf module and identity has no
    business depending on storage. It also makes the helper testable with a dict.
    """

    def get_setting(self, key: str) -> str | None: ...


def reach_of(settings: _SettingsReader, uuid: str) -> DriveReach:
    """:func:`drive_reach` for a drive whose hint is in the catalog. **O(1)**.

    Exists because reading the hint and interpreting it is one rule, and it was briefly written
    at two call sites - the app's drive listing and the CLI's. `test_surface_parity` caught that,
    correctly: the pair that drifts is the one where only one side later learns something.
    """
    return drive_reach(settings.get_setting(drive_path_hint(uuid)), uuid)


class DriveGhostError(Exception):
    """Refusal: this path is a known drive's recorded location and its marker is not there.

    One type in core rather than one per surface, so `jobs.py` reports the same `code` the CLI
    exits on and neither can word the refusal differently (§9).
    """


@dataclass(frozen=True, slots=True)
class GhostDrive:
    """A registered drive the catalog places at a path where its marker is no longer present."""

    uuid: str
    label: str
    #: The path the catalog recorded for it, which is the path being written to.
    recorded_at: str


def ghost_drive_at(
    path: Path, settings: _SettingsReader, drives: Iterable[tuple[str, str]]
) -> GhostDrive | None:
    """The known drive this path is recorded as, when no marker is there. **O(drives)**.

    **The failure this exists for, and it is a data-loss one.** A FUSE mountpoint with nothing
    mounted on it is an ordinary empty directory: writes into it succeed, and they land on the
    computer's own disk. `DestinationDevice` cannot see it - that guard latches the device on
    **first sighting**, so a run that STARTS in this state adopts the local disk as its baseline
    and never fires. The marker cannot see it either: an empty directory has none, and absence is
    what makes the surfaces mint a *new* identity for a library the catalog already knows, which
    is `(aap)` arriving through the one door `(aap)`'s content-based guard is blind to - it
    recognises a folder that HOLDS a known library, and this one holds nothing.

    **Only a recorded path discriminates it**, which is why this reads the hint. An empty
    directory carries no information about which drive it was, so the answer has to come from
    outside it. Measured alternatives that do not work: `os.path.ismount` is true only while
    something IS mounted, so it returns False for exactly this case; the mount table and
    `/etc/fstab` keep no record once a FUSE mount is gone; and matching the drive LABEL against
    the directory name is a coin toss, because `create_marker` defaults the label to that same
    directory name and every second `Backup` folder would be refused.

    **Fails open on purpose.** No hint, a differently-spelled path, or a marker actually present
    all mean "no opinion" - this must never block a genuine new destination. Compared lexically
    rather than through `resolve()`, for the reason `check_contained` gives: a path that cannot
    be resolved (a stale mount raises `ENOTCONN`) must still get an answer.
    """
    if existing_marker_path(path) is not None:
        return None  # a marker is here: whatever this is, it is not a ghost
    for uuid, label in drives:
        hint = settings.get_setting(drive_path_hint(uuid))
        if hint and Path(hint) == path:
            return GhostDrive(uuid=uuid, label=label, recorded_at=hint)
    return None


def drives_without_a_known_location(
    settings: _SettingsReader, drives: Iterable[tuple[str, str]]
) -> tuple[str, ...]:
    """Labels of registered drives the catalog cannot place. **O(drives)**.

    These are the ones :func:`ghost_drive_at` can say nothing about: with no recorded path there
    is no way to tell an empty folder that is one of them from an empty folder that is new. The
    caller asks before minting a *second* identity, so the person who does know can answer.
    """
    return tuple(label for uuid, label in drives if not settings.get_setting(drive_path_hint(uuid)))


def ghost_drive_refusal(ghost: GhostDrive) -> str:
    """What to say. One home, so the CLI and the app cannot word this differently (§9).

    Three facts, and the third is the one nobody can discover for themselves: files written into
    a mountpoint while nothing is mounted there are **shadowed the moment the filesystem returns**
    while still occupying the disk. `verify` then reports them missing and `df` shows the space
    gone, and the only way to see them again is to unmount - which nobody thinks to do.
    """
    return (
        f"{ghost.recorded_at} is where Truestill recorded the drive '{ghost.label}', "
        f"but that drive's marker file is not there.\n"
        f"       The drive is probably not plugged in or not mounted.\n"
        f"       Anything written here now would go onto THIS computer's disk, and would "
        f"DISAPPEAR from view the moment the drive comes back - while still using the space.\n"
        f"       Connect the drive and run again. If this folder is genuinely a different "
        f"place now, re-run with --force-new-identity."
    )


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
