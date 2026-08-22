"""Announce which catalog file a process opened - and whether that is normal or suspicious.

The default path is CWD-relative (``reports/catalog.sqlite``). Opening the app from the wrong
directory silently creates or opens an empty catalog and looks like the library vanished.
This module makes the resolved absolute path impossible to miss, without turning a genuine
first run into an error.

How first-run is told from "wrong catalog"
------------------------------------------
* **will_create** - the path is not a file yet. Normal for a new user or a new ``--db``.
  Message: where it will be created. Tone: info (never error/warning wording).
* **zero_bytes** - the file exists and is **empty on disk**, which no working Truestill ever
  leaves behind. Something created it and never wrote to it: a copy that failed part-way
  (``shutil.copy2`` creates the destination before it writes), or a process that died between
  ``sqlite3.connect`` and the schema commit. Tone: alert, and the **only** state that stops the
  process - see :func:`refuse_unusable_catalog`. `BACKLOG.md` ``(adr)``.
* **empty** - the file exists, ``files`` is 0, no drives registered. Could be a fresh file
  after a mistaken CWD, or an unused catalog. Tone: notice; when the default relative path
  was used, mention ``--db`` / working directory. Still not framed as a hard failure.
* **empty_with_drives** - file exists, 0 files, but ``drives`` rows are present. That shape
  does not happen on a calm first run; it is the loud "you may have opened a different
  catalog" case.
* **ready** - at least one ``files`` row. Just name the absolute path and the count.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Literal

from truestill_core.app_paths import CatalogChoice
from truestill_core.catalog import Catalog

# The default catalog is deliberately **not** a module constant here. It was, briefly, and that
# froze it at import: an environment override could not reach it and no test could isolate it,
# so every default-`--db` command wrote into the real user home. Call
# `app_paths.default_catalog_path()` at the point of use instead.

Tone = Literal["info", "notice", "alert"]

#: Exit code for "the file at the catalog path cannot be opened; nothing here will fix itself".
#:
#: **In core rather than beside `CATALOG_BUSY_EXIT` in the CLI, and the difference is real.**
#: Busy is *presented* differently by each surface -- the CLI has an exit code, the app has an
#: SSE terminal event -- so only its wording is shared. Unusable is presented the *same* way by
#: both: refuse to start, exit non-zero. One meaning that two processes must agree on is one
#: constant, not two literals that drift.
#:
#: `6` continues the CLI's allocation -- `3` a missing exiftool, `4` an unusable destination,
#: `5` a busy catalog -- one per failure family a caller would act on differently. Deliberately
#: **not** `5`: busy means *retry* and this must never be retried, and not `2`, which is a usage
#: error the user could have avoided.
CATALOG_UNUSABLE_EXIT = 6


class CatalogUnusableError(Exception):
    """The file at the catalog path exists and must not be opened.

    Carries the :class:`CatalogStartupInfo` so a surface can render the same sentence the
    startup banner would have, without re-deriving why.
    """

    def __init__(self, info: CatalogStartupInfo) -> None:
        super().__init__(info.detail)
        self.info = info


class CatalogPresence(StrEnum):
    WILL_CREATE = "will_create"
    ZERO_BYTES = "zero_bytes"
    EMPTY = "empty"
    EMPTY_WITH_DRIVES = "empty_with_drives"
    READY = "ready"


@dataclass(frozen=True, slots=True)
class CatalogStartupInfo:
    """What to print or show about the catalog path for this process."""

    absolute_path: str
    presence: CatalogPresence
    file_count: int
    drive_count: int
    explicit_db: bool
    tone: Tone
    detail: str  # situational sentence; empty when presence is READY


def resolve_catalog_path(db: Path) -> Path:
    """Absolute path for display and comparison. Does not create the file."""
    return db.expanduser().resolve()


def db_flag_explicit(argv: list[str]) -> bool:
    """True when the user passed ``--db`` / ``--db=`` on this invocation."""
    return any(arg == "--db" or arg.startswith("--db=") for arg in argv)


def _zero_byte_detail(absolute: Path, *, waited: bool = False) -> str:
    """What to tell someone whose catalog path holds an empty file.

    **The last sentence is not politeness, it is the point.** `catalog_move.py` already tells the
    user *"Check the copy, then delete the old one when you are happy"*. Checking a 0-byte copy
    by opening it used to turn it into a healthy-looking empty catalog, which is precisely the
    state that makes deleting the real one feel safe. Naming which file is disposable is what
    stops that instruction pointing at the wrong one.

    **The journal is evidence in one direction only.** Under ``journal_mode=delete`` -- which is
    what this catalog runs, `BACKLOG.md` ``(ads)`` -- SQLite removes the rollback journal on
    commit, so one still on disk means a write did not finish. Its **absence proves nothing**: a
    failed copy never creates one either. So the quiet case says what happened without choosing
    between the two causes, and only the journal case names one.
    """
    journal = absolute.with_name(absolute.name + "-journal")
    said = [
        (
            f"{absolute} is 0 bytes. Something created it and never wrote to it - a copy that "
            "failed part-way, or a run that stopped before its first write. It holds no photos "
            "and no settings, and Truestill will not open it: once opened, an empty file and a "
            "real library look the same."
        )
    ]
    if waited:
        # ⚠ **THE BOUND FIRED, AND THE ADVICE MUST CHANGE WITH IT.** A journal means a write is in
        # flight - interrupted OR unfinished. We waited out the "unfinished" reading and it did
        # not resolve, so this is no longer ordinary contention. Telling someone to delete a file
        # another process may still be writing is the one thing this must not say. `(afp)`
        said.append(
            f"A rollback journal is beside it ({journal.name}) and it is still empty after "
            f"{_CREATION_WAIT_SECONDS:.0f} seconds, so this is not simply another Truestill "
            "finishing its work. Something went wrong while this catalog was being created."
        )
        said.append(
            "Your library, if you have one, is untouched. Check whether another Truestill is "
            "running before you touch this file: if one is, let it finish. If nothing else is "
            "running, rename this file and run again, or pass --db PATH to point at the catalog "
            "you meant."
        )
        return " ".join(said)
    if journal.exists():
        said.append(
            f"A rollback journal is beside it ({journal.name}), so a write to this catalog was "
            "interrupted."
        )
    said.append(
        "Your library, if you have one, is untouched. Rename or delete this file and run again, "
        "or pass --db PATH to point at the catalog you meant."
    )
    return " ".join(said)


def refuse_unusable_catalog(info: CatalogStartupInfo) -> None:
    """Raise when ``info`` describes a file that must not be opened. A no-op otherwise.

    **Why the refusal is here and not inside :func:`inspect_catalog`.** The inspector stays a
    pure describer: several callers legitimately want to *read* the state -- `library_status`
    renders it into the custody strip on every request -- and a function that raises cannot be
    one of them. The cost of that split is that a new entry point can forget to call this, and a
    missing call is invisible; `test_every_entry_point_refuses_an_unusable_catalog.py` is what
    makes it visible, function by function.

    **Only ZERO_BYTES.** Every other presence is a description a surface may act on however it
    likes; widening this would refuse a genuine first run, which is the one thing `(adr)`'s
    ruling costs nobody today because ``WILL_CREATE`` is ``is_file()`` being false and a 0-byte
    file is a file. The two states are disjoint at the branch.

    ⚠ **A KNOWN, ACCEPTED RACE.** ``sqlite3.connect`` creates a 0-byte file before its first
    write, so a second process inspecting inside that window would refuse a catalog that is
    merely being born. The window is microseconds, `(adn)` records that nothing stops two
    processes anyway, and the outcome is a refusal the user recovers from by running again --
    against a retry loop that would be real complexity guarding a state we cannot distinguish
    from the real defect. Accepted deliberately, 2026-08-18, rather than discovered later.
    """
    if info.presence is CatalogPresence.ZERO_BYTES:
        raise CatalogUnusableError(info)


#: How long a 0-byte catalog may stay that way while another process creates it. `(afp)`
#:
#: ⚠ **Bounded, and the bound fails VISIBLY rather than extending.** Creating a catalog is
#: milliseconds; if two seconds pass and the file is still empty, something is wrong beyond
#: contention, and saying that beats waiting longer on a command a person is watching.
_CREATION_WAIT_SECONDS = 2.0

#: How often to look while waiting. Short enough that the ordinary case is indistinguishable from
#: the command simply working.
_CREATION_POLL_SECONDS = 0.02


def _has_journal(absolute: Path) -> bool:
    """Whether a rollback journal sits beside this catalog."""
    return absolute.with_name(absolute.name + "-journal").exists()


#: Bound at module level rather than taken as defaulted parameters, and that is not style: a
#: default argument captures the function at DEF time, so patching `time.sleep` could not reach
#: it and the wait's own test passed while nothing ever waited.
_now: Callable[[], float] = time.monotonic
_sleep: Callable[[float], None] = time.sleep


def _another_process_finished_creating_it(absolute: Path) -> bool:
    """Whether a 0-byte catalog stops being one while we watch. `(afp)`

    ⚠ **The journal is the discriminator, and `(adr)` had it and did not use it.** Under
    ``journal_mode=delete`` a journal on disk means a write did not finish - which is *"was
    interrupted"* **and** *"has not finished yet"*, the same observation for opposite situations.
    `(adr)`'s refusal read it as the first and told the user to delete the file; measured
    2026-08-22, 2 of 6 concurrent cold starts hit the second, where that file is a live catalog
    another process is writing.

    **The rule, and it is a rule rather than a special case:** *wait when the contended state is
    bounded and short; refuse when it is not.* Creating a catalog is milliseconds, so waiting here
    is indistinguishable from the command working. A held drive lock is seconds to hours, so
    `drive_lock` refuses instead. The next contended state gets the test, not the precedent.

    **No journal, no wait.** A failed `copy2` leaves a 0-byte file and no journal, and that is
    `(adr)`'s case exactly - it is not contention and waiting would only delay a correct refusal.
    """
    if not _has_journal(absolute):
        return False
    deadline = _now() + _CREATION_WAIT_SECONDS
    while _now() < deadline:
        _sleep(_CREATION_POLL_SECONDS)
        try:
            if absolute.stat().st_size > 0:
                return True
        except OSError:
            # It went away entirely - the other process gave up and cleaned up. That is not this
            # function's question; the caller re-stats and sees MISSING.
            return False
    return False


def inspect_catalog(db: Path, *, explicit_db: bool) -> CatalogStartupInfo:
    """Describe ``db`` without treating a missing file as a failure.

    Does **not** create a missing catalog (``Catalog`` would). Callers that later open
    ``Catalog(db)`` may create it; pass the same ``db`` path.
    """
    absolute = resolve_catalog_path(db)
    if not absolute.is_file():
        return CatalogStartupInfo(
            absolute_path=str(absolute),
            presence=CatalogPresence.WILL_CREATE,
            file_count=0,
            drive_count=0,
            explicit_db=explicit_db,
            tone="info",
            detail=f"No catalog yet. Truestill will create catalog file {absolute} on first use.",
        )

    # ⚠ BEFORE THE CATALOG OPEN, AND THAT ORDER IS THE WHOLE FIX. `Catalog._migrate` builds the
    # full schema into whatever file it is handed, so one line lower this check would run against
    # a 159,744-byte catalog and always be false: **the evidence is destroyed by the act of
    # looking**, and what is left is indistinguishable from a library the user just started.
    # Pinned by `test_a_zero_byte_catalog_is_not_adopted_as_an_empty_library`, whose size
    # assertion is the half that survives a mutation moving this below the open.
    #
    # Exactly zero, not "small". A partially-written file raises `database disk image is
    # malformed`, which stops the user by itself -- that is `(adb)`, and it is loud. Zero bytes is
    # silent, because SQLite treats a zero-length file as a valid empty database by design. We
    # decline to inherit that at this one path.
    if absolute.stat().st_size == 0:
        if _another_process_finished_creating_it(absolute):
            # It was transient. Fall through and open the catalog the winner just built.
            pass
        else:
            return CatalogStartupInfo(
                absolute_path=str(absolute),
                presence=CatalogPresence.ZERO_BYTES,
                file_count=0,
                drive_count=0,
                explicit_db=explicit_db,
                tone="alert",
                detail=_zero_byte_detail(absolute, waited=_has_journal(absolute)),
            )

    with Catalog(absolute) as catalog:
        file_count = catalog.count()
        drive_count = len(catalog.list_drives())

    if file_count > 0:
        return CatalogStartupInfo(
            absolute_path=str(absolute),
            presence=CatalogPresence.READY,
            file_count=file_count,
            drive_count=drive_count,
            explicit_db=explicit_db,
            tone="info",
            detail="",
        )

    if drive_count > 0:
        return CatalogStartupInfo(
            absolute_path=str(absolute),
            presence=CatalogPresence.EMPTY_WITH_DRIVES,
            file_count=0,
            drive_count=drive_count,
            explicit_db=explicit_db,
            tone="alert",
            detail=(
                f"Opened catalog file {absolute}: 0 files but {drive_count} drive(s) are registered. "
                "If your library looks missing, this may not be the catalog you expect "
                "(check --db and your working folder)."
            ),
        )

    if explicit_db:
        detail = f"Opened empty catalog file at {absolute} (from --db)."
    else:
        detail = (
            f"Opened empty catalog file at {absolute}. "
            "If you expected an existing library, pass --db PATH or run from the folder "
            "that holds your reports/catalog.sqlite."
        )
    return CatalogStartupInfo(
        absolute_path=str(absolute),
        presence=CatalogPresence.EMPTY,
        file_count=0,
        drive_count=0,
        explicit_db=explicit_db,
        tone="notice",
        detail=detail,
    )


def migrate_catalog(db: Path) -> None:
    """Create and migrate ``db`` now, so nothing serving requests has to.

    **Why a process does this before serving rather than on first use.** `Catalog._migrate` takes
    the write lock and builds the schema; on a fresh catalog the six requests a page load fires
    all reach it, one wins and the rest queue. Measured in CI run 31821214510, with the
    cross-process fix in place and no startup migration: 7828 opens reached `_migrate` and the
    wait at `BEGIN IMMEDIATE` ran to **2832 ms**, with 155 waits over a second. Correct, and still
    a cost every first-run user pays on their own disk.

    ⚠ **This CREATES the file.** Callers that report first-run presence must call
    :func:`inspect_catalog` **before** this, never after - see `create_app`, which does exactly
    that and says what bounds the captured value.
    """
    with Catalog(db):
        pass


def format_startup_lines(
    info: CatalogStartupInfo, choice: CatalogChoice | None = None
) -> list[str]:
    """Stdout lines: always the absolute path; situational detail when not READY.

    ``choice`` is passed when the path was **resolved for** the user rather than named by them -
    i.e. no ``--db``. It says which of the three rules won and, when two real catalogs disagree,
    what to do about it. `(adv)`: the path alone was already on screen and read identically
    whether an override had won, lost, or never been set, so a person had to suspect the problem
    to see it.
    """
    if info.presence is CatalogPresence.READY:
        lines = [f"Catalog: {info.absolute_path} ({info.file_count} files)"]
    else:
        lines = [f"Catalog: {info.absolute_path}"]
        if info.detail:
            lines.append(info.detail)
    if choice is not None:
        lines.append(choice.summary)
        if choice.note:
            lines.append(choice.note)
    return lines
