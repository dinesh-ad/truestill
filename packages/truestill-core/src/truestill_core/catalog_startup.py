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

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Literal

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


def _zero_byte_detail(absolute: Path) -> str:
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
        return CatalogStartupInfo(
            absolute_path=str(absolute),
            presence=CatalogPresence.ZERO_BYTES,
            file_count=0,
            drive_count=0,
            explicit_db=explicit_db,
            tone="alert",
            detail=_zero_byte_detail(absolute),
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


def format_startup_lines(info: CatalogStartupInfo) -> list[str]:
    """Stdout lines: always the absolute path; situational detail when not READY."""
    if info.presence is CatalogPresence.READY:
        return [f"Catalog: {info.absolute_path} ({info.file_count} files)"]
    lines = [f"Catalog: {info.absolute_path}"]
    if info.detail:
        lines.append(info.detail)
    return lines
