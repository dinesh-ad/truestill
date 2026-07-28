"""Remove the folder skeleton a layout migration leaves behind.

A migration moves every file out of the old tree and leaves the tree, because truestill never
deletes a folder. After migrating a real library that is a `Camera/` skeleton of empty months.

Two decisions carry this module, both recorded in `docs/empty-folder-cleanup-research.md`:

* **Scope is the journal, not the filesystem.** Only folders the migration record shows
  truestill *emptied* are candidates. The whole category of "empty folder cleaner" bugs comes
  from sweeping a drive and deleting a directory the tool never touched and knows nothing about
  -- a deliberate placeholder looks exactly like a leftover. truestill created this skeleton, so
  it cleans only this skeleton.
* **Unknown is never junk.** A folder is removable when it is empty, or when everything in it is
  named in :data:`JUNK_NAMES` (or is a zero-byte file). Anything else -- however small, however
  hidden -- leaves the folder alone and is reported with its contents named.

**O(folders)** in the leftovers: one directory listing each, a set lookup per entry. Nothing
scales with library size.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path, PurePosixPath

#: Operating-system detritus that may be removed **along with** the folder holding it.
#:
#: Enumerated on purpose, and short on purpose. The moment this becomes a pattern ("small
#: files", "dotfiles", "files I don't recognise") the tool starts deleting things it cannot
#: name. Adding an entry here is a deliberate edit somebody has to justify in review; it is not
#: something that should grow by accident.
JUNK_NAMES: frozenset[str] = frozenset(
    {
        ".DS_Store",  # macOS Finder metadata
        "._.DS_Store",
        "Thumbs.db",  # Windows Explorer thumbnail cache
        "ehthumbs.db",
        "desktop.ini",  # Windows folder view settings
        ".nomedia",  # Android media-scanner opt-out
    }
)


class _Unset:
    """Sentinel: "resolve the trash backend for me", distinct from an explicit ``None``."""


_UNSET = _Unset()


class Tier(StrEnum):
    """What a candidate folder turned out to contain."""

    EMPTY = "empty"
    JUNK_ONLY = "junk-only"
    OCCUPIED = "occupied"


@dataclass(frozen=True, slots=True)
class Candidate:
    """One folder the migration emptied, and what is in it now."""

    relative: str
    tier: Tier
    #: Names inside the folder: the junk to be removed with it, or what is keeping it alive.
    contents: tuple[str, ...] = ()

    @property
    def removable(self) -> bool:
        return self.tier is not Tier.OCCUPIED


@dataclass(frozen=True, slots=True)
class CleanupPlan:
    """Every candidate, deepest first, split by what may happen to it."""

    candidates: list[Candidate] = field(default_factory=list)

    @property
    def removable(self) -> list[Candidate]:
        return [c for c in self.candidates if c.removable]

    @property
    def occupied(self) -> list[Candidate]:
        return [c for c in self.candidates if not c.removable]


def emptied_directories(journal_old_paths: list[str]) -> list[str]:
    """Every directory a migration moved files out of, **deepest first**.

    Each move's old path contributes its parent and every ancestor above it, because emptying
    `Camera/2013/09/` is what makes `Camera/2013/` and then `Camera/` empty in turn. Sorting by
    depth is what lets a single bottom-up pass collapse a whole skeleton: a parent is only
    inspected after its children have had their chance to go.
    """
    directories: set[str] = set()
    for old in journal_old_paths:
        parent = PurePosixPath(old).parent
        while parent != PurePosixPath("."):
            directories.add(parent.as_posix())
            parent = parent.parent
    return sorted(directories, key=lambda d: (-d.count("/"), d))


def plan_cleanup(root: Path, emptied: list[str]) -> CleanupPlan:
    """Classify each emptied folder that still exists. **Pure: reads, never writes.**

    Classification happens in the same deepest-first order the removal will use, and a folder
    that no longer exists is simply skipped -- a previous cleanup, or the user, may already have
    dealt with it.
    """
    candidates: list[Candidate] = []
    removed: set[str] = set()
    for relative in emptied:
        folder = root / relative
        if not folder.is_dir():
            continue
        tier, contents = _classify_with(folder, removed, relative)
        candidates.append(Candidate(relative=relative, tier=tier, contents=contents))
        if tier is not Tier.OCCUPIED:
            removed.add(relative)
    return CleanupPlan(candidates=candidates)


def _classify_with(folder: Path, removed: set[str], relative: str) -> tuple[Tier, tuple[str, ...]]:
    """Classify ``folder``, treating children this plan already intends to remove as gone.

    Without this the preview would be wrong about parents: `Camera/2013/` still physically holds
    `09/` while planning, even though `09/` is about to go, so a naive check calls the parent
    occupied and the skeleton only half-collapses.
    """
    try:
        entries = list(folder.iterdir())
    except OSError:
        return Tier.OCCUPIED, ()
    surviving = [e for e in entries if not (e.is_dir() and f"{relative}/{e.name}" in removed)]
    if not surviving:
        return Tier.EMPTY, ()

    junk: list[str] = []
    for entry in surviving:
        if entry.is_dir():
            return Tier.OCCUPIED, tuple(sorted(e.name for e in surviving))
        if entry.name in JUNK_NAMES or (entry.is_file() and entry.stat().st_size == 0):
            junk.append(entry.name)
            continue
        return Tier.OCCUPIED, tuple(sorted(e.name for e in surviving))
    return Tier.JUNK_ONLY, tuple(sorted(junk))


def trash_backend() -> str | None:
    """How this machine can send something to the trash, or ``None`` if it cannot.

    Resolved at runtime rather than by taking a dependency: adding one to `truestill-core` for a
    cleanup command fails the §7 test, and `pillow-heif` already sets the graceful-degradation
    precedent. When this returns ``None`` the caller must **say so before asking to confirm** --
    a permanent delete is never disguised as a recoverable one.
    """
    try:
        import send2trash  # noqa: F401, PLC0415 - probing availability, not importing for use
    except ImportError:
        return "gio" if shutil.which("gio") else None
    else:
        return "send2trash"


def _to_trash(path: Path, backend: str) -> None:
    if backend == "send2trash":
        import send2trash  # noqa: PLC0415 - resolved at runtime, see trash_backend

        send2trash.send2trash(str(path))
        return
    subprocess.run(["gio", "trash", str(path)], check=True, capture_output=True)


def run_cleanup(
    root: Path, plan: CleanupPlan, *, apply: bool, backend: str | _Unset | None = _UNSET
) -> tuple[int, list[str]]:
    """Remove the removable folders, deepest first. Returns ``(removed, failures)``.

    ``backend`` is the trash mechanism to use, defaulting to whatever this machine has. It is a
    parameter rather than a lookup inside the loop so the caller can **report which one is in
    force before asking to confirm** -- "these go to the trash" and "these are deleted
    permanently" are different questions to be asked, and the answer must not be discovered
    afterwards. ``None`` means a real delete.

    A trash failure is recorded, never quietly downgraded to a permanent delete: the user agreed
    to a recoverable removal, and doing an irreversible one instead would break that agreement.
    """
    if not apply:
        return 0, []
    if isinstance(backend, _Unset):
        backend = trash_backend()
    removed = 0
    failures: list[str] = []
    for candidate in plan.removable:
        folder = root / candidate.relative
        if not folder.is_dir():
            continue
        try:
            if backend is not None:
                _to_trash(folder, backend)
            else:
                shutil.rmtree(folder)
            removed += 1
        except (OSError, subprocess.CalledProcessError) as exc:
            failures.append(f"{candidate.relative}: {exc}")
    return removed, failures
