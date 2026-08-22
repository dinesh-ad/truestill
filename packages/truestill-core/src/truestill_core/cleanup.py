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
* Classifying and removing them (:func:`plan_cleanup`, :func:`run_cleanup`) is
  **O(folders + junk entries)**: one directory listing per folder, a set lookup per entry, and one
  trash call per junk file. ⚠ This said **O(folders)** and *"no file is ever opened"* until
  2026-08-22, when removal stopped handing whole folders to the trash and started sending their
  named junk individually (`(afj)`). The junk term is bounded by what `plan_cleanup` already
  listed, and a same-filesystem trash is a rename rather than a copy - but "no file is ever
  opened" is no longer true of a cross-device trash, and this module has corrected an over-claim
  of its own once already (below).

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
from truestill_core.path_reach import Reach, reach

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
        # ⚠ `reach`, not `folder.is_dir()`, and the two failure answers are deliberately
        # different. `(afb)` A bare predicate here RAISED on 3.13 when the folder's parent
        # refused - `plan_cleanup` calls itself "Pure: reads, never writes", and a traceback at
        # the end of a successful organize is the loudest possible way to break that promise.
        # Python 3.14 masked it by returning False, so the folder vanished from the plan through
        # the `continue` below, which is the answer reserved for one somebody has already
        # handled. Absent and refused are different answers here too: a folder that is gone was
        # dealt with; a folder that will not answer was not, and is reported OCCUPIED - the same
        # verdict `_classify_with` already gives when `iterdir` refuses.
        found = reach(folder)
        if found is Reach.REFUSED:
            candidates.append(Candidate(relative=relative, tier=Tier.OCCUPIED, contents=()))
            continue
        if found is not Reach.DIRECTORY:
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
    """What removal achieved. **Counts what cannot be undone; describes what can.**

    ⚠ **The fields were ``trashed``/``deleted``, counting FOLDERS, until 2026-08-22.** No folder
    is trashed any more -- every folder is removed by ``rmdir``, and only its *contents* can go to
    the trash -- so a ``trashed`` folder counter would have been permanently zero and a ``deleted``
    one would have made an ordinary tidy-up read as a permanent delete. A name that describes what
    a field used to mean is worse than no name, because a reader trusts it. `(afj)`

    **Junk that reached the trash is deliberately not counted.** The action it implies -- look in
    the trash -- does not depend on how many there were, while :attr:`discarded` is irreversible
    and does. It is reported in prose by each surface instead.
    """

    #: Folders removed. Always by ``rmdir``, on every path.
    removed: int = 0
    #: Junk **files** unlinked outright, which happens only under ``--permanent`` after the trash
    #: refused them. Nothing recoverable, which is why this one is a number.
    discarded: int = 0
    failures: list[str] = field(default_factory=list)


def _clear_junk(
    folder: Path, junk: tuple[str, ...], *, backend: str | None, permanent: bool
) -> tuple[tuple[str, ...], tuple[str, ...], str | None]:
    """Send each named junk entry to the trash, or discard it. **Never touches the folder.**

    Only the entries this plan already classified as junk are handled, **by name** -- never a
    wildcard and never a recursive walk. `Tier.JUNK_ONLY` contents are file names only: a
    surviving subdirectory short-circuits the folder to `Tier.OCCUPIED`, so nothing here is ever
    a directory.

    Returns ``(trashed, discarded, refusal)``. A refusal is a reason string and means **nothing
    further should happen to this folder** -- the trash said no and ``permanent`` was not given,
    so §1 condition (d) leaves it in place.
    """
    if backend is None:
        # No trash on this machine is a REFUSAL, not permission -- and it is the whole folder that
        # is refused, junk or no junk, because after this change every removal is outright and
        # `NO_TRASH_REASON` already says we will not do that unasked.
        if not permanent:
            return (), (), NO_TRASH_REASON
        discarded_here: list[str] = []
        for name in junk:
            entry = folder / name
            # Counted only if it was really there: `discarded` is the number of irreversible
            # removals, and a file that had already gone is not one of them.
            existed = entry.exists()
            entry.unlink(missing_ok=True)
            if existed:
                discarded_here.append(name)
        return (), tuple(discarded_here), None
    trashed: list[str] = []
    discarded: list[str] = []
    for name in junk:
        entry = folder / name
        try:
            _to_trash(entry, backend)
        except (OSError, subprocess.CalledProcessError) as exc:
            # ⚠ **Diagnosed after the act, never checked before it.** `_remove_permanently` used
            # ``unlink(missing_ok=True)``, so junk that vanished between the plan and the apply
            # was tolerated -- and it makes the ``rmdir`` below *more* likely to succeed, not
            # less. Neither backend offers that: ``send2trash`` raises and ``gio`` exits non-zero,
            # and on ``gio`` the failure arrives as a `CalledProcessError` that cannot be told
            # apart from any other. So the equivalence is restored by asking the filesystem
            # afterwards rather than by pre-checking, which is the same discipline the folder
            # itself gets.
            if not entry.exists():
                continue
            if not permanent:
                return tuple(trashed), tuple(discarded), str(exc)
            entry.unlink(missing_ok=True)
            discarded.append(name)
        else:
            trashed.append(name)
    return tuple(trashed), tuple(discarded), None


def _partial_removal_reason(
    exc: OSError, trashed: tuple[str, ...], discarded: tuple[str, ...]
) -> str:
    """Why a folder was not removed, **and what already happened to it anyway**.

    ⚠ **The load-bearing sentence of this module.** A folder whose ``rmdir`` refused after its junk
    reached the trash is a state no previous version could produce, and this line is the only thing
    that makes it legible: *"this one failed"* standing in for *"this one partly succeeded"* is
    exactly `(aez)`'s shape, and `(afk)` is the same defect in the older, smaller form.
    """
    detail = (exc.strerror or str(exc)).lower()
    parts = [f"not removed ({detail})"]
    if trashed:
        parts.append(
            f"its {', '.join(trashed)} {'is' if len(trashed) == 1 else 'are'} in the trash"
        )
    if discarded:
        parts.append(
            f"its {', '.join(discarded)} {'was' if len(discarded) == 1 else 'were'} removed"
        )
    return "; ".join(parts)


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

    **The contents go to the trash; the folder goes to ``rmdir``.** ⚠ Until 2026-08-22 the whole
    folder was handed to `_to_trash`, and ``send2trash`` has **no emptiness precondition** --
    measured, it accepts a non-empty directory and moves it by atomic rename. So a folder that
    gained a file between the preview and the typed word was taken, with the file. `(afj)`

    ⚠ **The fix is not a check before trashing.** There is nothing to copy from the permanent
    path: it never re-verified either. Its safety is ``rmdir``'s kernel-enforced precondition, not
    a re-read -- see `_clear_junk` and the ordering note below. A contents check before the move
    would be the check-then-act race this module was written to avoid.

    **Ordering, and it is the only one available.** ``rmdir`` cannot be asked whether it *would*
    succeed, so junk is cleared first. If ``rmdir`` then refuses, the junk is in the trash and the
    folder remains -- **strictly better than the old permanent path**, which unlinked the junk
    outright in exactly that situation. `_partial_removal_reason` is what makes that state legible.

    **Trash is always tried first.** ``permanent`` changes only what happens when trash is
    *refused*, and what it now governs is the **junk**: without it the folder is left in place and
    reported, with it the junk is discarded and the folder still goes through ``rmdir``.
    """
    if not apply:
        return CleanupOutcome()
    if isinstance(backend, _Unset):
        backend = trash_backend()

    removed = discarded = 0
    failures: list[str] = []
    for candidate in plan.removable:
        folder = root / candidate.relative
        # ⚠ **No `is_dir()` pre-check, and its removal is part of the fix.** It was check-then-act
        # on the one path whose defining property is that it does not check -- it bought no
        # atomicity (`rmdir` raises anyway) and it *silently skipped*, so a preview naming six
        # folders could report five with nothing explaining the sixth. Worse, a folder whose
        # parent refuses answers `False` rather than raising, so a refusal was routed into the
        # skip that `plan_cleanup` reserves for a folder already dealt with. `(afb)`, `(afj)`.
        # `rmdir`'s own errno answers all three cases below, after the act.
        #
        # `Tier.EMPTY` carries no contents, so `junk` is `()` and the whole operation is that
        # `rmdir`. An empty directory has nothing to recover; trashing it preserved a name.
        junk = candidate.contents if candidate.tier is Tier.JUNK_ONLY else ()
        try:
            trashed_here, discarded_here, refusal = _clear_junk(
                folder, junk, backend=backend, permanent=permanent
            )
        except OSError as exc:
            failures.append(f"{candidate.relative}: {exc}")
            continue
        if refusal is not None:
            failures.append(f"{candidate.relative}: {refusal}")
            continue
        discarded += len(discarded_here)
        try:
            folder.rmdir()
        except FileNotFoundError:
            # Already gone - a previous cleanup, or the user. `plan_cleanup` treats an absent
            # candidate the same way, and neither removed nor failed is the honest count.
            continue
        except OSError as exc:
            failures.append(
                f"{candidate.relative}: "
                f"{_partial_removal_reason(exc, trashed_here, discarded_here)}"
            )
            continue
        removed += 1
    return CleanupOutcome(removed=removed, discarded=discarded, failures=failures)
