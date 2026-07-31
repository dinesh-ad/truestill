"""Announce which catalog file a process opened - and whether that is normal or suspicious.

The default path is CWD-relative (``reports/catalog.sqlite``). Opening the app from the wrong
directory silently creates or opens an empty catalog and looks like the library vanished.
This module makes the resolved absolute path impossible to miss, without turning a genuine
first run into an error.

How first-run is told from "wrong catalog"
------------------------------------------
* **will_create** - the path is not a file yet. Normal for a new user or a new ``--db``.
  Message: where it will be created. Tone: info (never error/warning wording).
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

from truestill_core.app_paths import default_catalog_path
from truestill_core.catalog import Catalog

#: The catalog both surfaces use when the caller does not name one. Resolved **once at import**
#: from `app_paths.default_catalog_path`, so an existing `reports/catalog.sqlite` keeps being
#: used where it is and a fresh install lands in the OS data directory - see `(aae)` and that
#: module for why a CWD-relative default is undefined for an installed app.
DEFAULT_CATALOG_PATH = default_catalog_path()

Tone = Literal["info", "notice", "alert"]


class CatalogPresence(StrEnum):
    WILL_CREATE = "will_create"
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


def format_startup_lines(info: CatalogStartupInfo) -> list[str]:
    """Stdout lines: always the absolute path; situational detail when not READY."""
    if info.presence is CatalogPresence.READY:
        return [f"Catalog: {info.absolute_path} ({info.file_count} files)"]
    lines = [f"Catalog: {info.absolute_path}"]
    if info.detail:
        lines.append(info.detail)
    return lines
