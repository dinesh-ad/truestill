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

**Complexity, in two halves, because only one of them is bounded by the leftovers.**

* Deriving the candidate set (:func:`emptied_directories`) is **O(moves x depth) + O(F log F)**
  for the sort, where *moves* is one journal row **per migrated file**. That half does scale
  with library size.
* Classifying and removing them (:func:`plan_cleanup`, :func:`run_cleanup`) is **O(folders)**:
  one directory listing each, a set lookup per entry, and **no file is ever opened**.

The original wording here said "Nothing scales with library size", which was wrong about the
first half - it is pure string work, so it is cheap rather than absent, but a future optimiser
reading this module was entitled to a true sentence rather than a reassuring one. The claim that
matters is the second bullet: the expensive resource is directory I/O, and that is bounded by
the skeleton, not by the library.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path, PurePosixPath

from truestill_core import binaries

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

    **``send2trash`` is a required dependency as of 2026-08-04, and it is probed FIRST**, so on
    any correctly installed copy this returns ``"send2trash"`` without ever consulting ``gio``.
    That ordering is what makes the guarantee portable: ``gio`` is a GLib tool absent from stock
    Windows and macOS, and while this dependency was *optional* those were exactly the platforms
    where the answer was ``None``.

    This docstring used to say the opposite - that a dependency was avoided here because "adding
    one to `truestill-core` for a cleanup command fails the §7 test". That was true when it was
    written and is not any more: §7 now carries the row, and the argument it carries is that the
    optionality was the defect rather than the saving.

    **The two fallbacks are kept deliberately, and they are no longer the expected path.** A
    declared dependency can still be missing from a *bundle* - an import inside a ``try`` is what
    a bundler's static analysis misses - so ``gio`` remains a second chance rather than a plan.
    When this does return ``None`` the caller must **say so before asking to confirm**; a
    permanent delete is never disguised as a recoverable one.
    """
    try:
        import send2trash  # noqa: F401, PLC0415 - probing availability, not importing for use
    except ImportError:
        return "gio" if shutil.which("gio") else None
    else:
        return "send2trash"


#: Why a folder was left alone when this machine has no trash at all. **One home for the
#: wording**, because the CLI and the app both render `CleanupOutcome.failures` verbatim and §9
#: forbids the two surfaces wording one outcome differently. Phrased as the reason half of a
#: `"{folder}: {reason}"` line, which is the shape every other entry in that list already has.
NO_TRASH_REASON = (
    "left in place - this machine has no trash Truestill can use, and Truestill will not "
    "delete a folder outright without being asked (clean-empty --permanent)"
)


def _to_trash(path: Path, backend: str) -> None:
    if backend == "send2trash":
        import send2trash  # noqa: PLC0415 - resolved at runtime, see trash_backend

        send2trash.send2trash(str(path))
        return
    binaries.run(["gio", "trash", str(path)], check=True, capture_output=True)


@dataclass(frozen=True, slots=True)
class CleanupOutcome:
    """What removal achieved, split by how each folder went."""

    trashed: int = 0
    deleted: int = 0
    failures: list[str] = field(default_factory=list)

    @property
    def removed(self) -> int:
        return self.trashed + self.deleted


def _remove_permanently(folder: Path, junk: tuple[str, ...]) -> None:
    """Delete a folder with **rmdir semantics**: it physically cannot remove a non-empty one.

    Only the entries this plan already classified as junk are unlinked, by name -- never a
    wildcard and never a recursive walk. Then ``rmdir`` refuses if anything else is present, so a
    folder that gained a file between the preview and the confirm survives **by construction**
    rather than by a re-check that could itself race. ``rmtree`` would have taken it.
    """
    for name in junk:
        (folder / name).unlink(missing_ok=True)
    folder.rmdir()


def run_cleanup(
    root: Path,
    plan: CleanupPlan,
    *,
    apply: bool,
    backend: str | _Unset | None = _UNSET,
    permanent: bool = False,
) -> CleanupOutcome:
    """Remove the removable folders, deepest first.

    ``backend`` is the trash mechanism, defaulting to whatever this machine has. It is a
    parameter rather than a lookup inside the loop so the caller can **say which one is in force
    before asking to confirm** -- "these go to the trash" and "these are deleted permanently" are
    different questions, and the answer must not be discovered afterwards.

    **Trash is always tried first.** ``permanent`` changes only what happens when trash is
    *refused*: without it the folder is left in place and reported, with it the folder is deleted
    outright. That is why permanent mode needs no separate "is trash available here?" gate -- it
    applies per folder, and exactly to the folders trash would not take.
    """
    if not apply:
        return CleanupOutcome()
    if isinstance(backend, _Unset):
        backend = trash_backend()

    trashed = deleted = 0
    failures: list[str] = []
    for candidate in plan.removable:
        folder = root / candidate.relative
        if not folder.is_dir():
            continue
        junk = candidate.contents if candidate.tier is Tier.JUNK_ONLY else ()
        if backend is None:
            # No trash on this machine is a REFUSAL, not permission. Until 2026-08-04 this
            # branch did not exist: control fell straight through to the permanent removal
            # below without ever reading `permanent`, so the two states a user cannot tell
            # apart - "this drive would not accept it" and "this computer has no trash" -
            # produced opposite outcomes, and the destructive one needed no decision from
            # anybody. See `test_no_trash_backend_is_a_refusal_not_a_licence_to_destroy`.
            if not permanent:
                failures.append(f"{candidate.relative}: {NO_TRASH_REASON}")
                continue
        else:
            try:
                _to_trash(folder, backend)
            except (OSError, subprocess.CalledProcessError) as exc:
                if not permanent:
                    failures.append(f"{candidate.relative}: {exc}")
                    continue
            else:
                trashed += 1
                continue
        try:
            _remove_permanently(folder, junk)
            deleted += 1
        except OSError as exc:
            failures.append(f"{candidate.relative}: {exc}")
    return CleanupOutcome(trashed=trashed, deleted=deleted, failures=failures)
