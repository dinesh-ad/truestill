"""Drives / Where / At-risk, reveal, attach, and library custody status."""

from __future__ import annotations

import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, NotRequired, TypedDict, cast

from truestill_core.catalog import Catalog
from truestill_core.catalog_startup import inspect_catalog
from truestill_core.drive import create_marker, path_is_usable_dir, read_marker

from truestill_app.service.drive_support import (
    drive_correction,
    drive_path_hint,
    take_live_path_hint,
)
from truestill_app.service.media_support import media_breakdown

#: Remembered paths, for prefilling fields the catalog can already answer. **Hints only.**
#: Drive *identity* is the marker's uuid and never a path (§3.1).
LIBRARY_PATH_HINT = "path_hint.library"
BACKUP_PATH_HINT = "path_hint.backup"


class RevealOk(TypedDict):
    ok: Literal[True]
    path: str


class RevealErr(TypedDict):
    ok: Literal[False]
    error: str
    suggested_root: NotRequired[str | None]
    drive_label: NotRequired[str | None]
    can_register: NotRequired[bool]


def reveal_in_file_manager(path: Path) -> RevealOk | RevealErr:
    """Open a folder in the desktop's own file manager.

    A path printed on screen is a dead end: to actually look at the photos a user has to select
    it, copy it and paste it somewhere else. This is the one action that makes a displayed path
    useful.

    **Degrades honestly.** There is no cross-platform way to do this, so the opener is chosen per
    platform (`xdg-open`, `open`, `explorer`); where none exists the caller is told plainly and
    given the path, rather than being left with a button that silently does nothing.

    Only ever opens a directory that already exists, and the path goes into an argument vector
    rather than a shell, so a folder name containing shell metacharacters is just a name. A
    stale/unreachable hint returns the same drive-correction shape as verify - never a raw
    ``OSError``.
    """
    if not path_is_usable_dir(path):
        return cast(RevealErr, {"ok": False, **drive_correction(path)})
    opener = {"darwin": "open", "win32": "explorer"}.get(sys.platform, "xdg-open")
    if shutil.which(opener) is None:
        return {
            "ok": False,
            "error": (
                f"Can't open a file manager because this machine has no '{opener}'. "
                f"Open the folder yourself: {path}"
            ),
        }
    try:
        subprocess.Popen([opener, str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError as exc:
        return {
            "ok": False,
            "error": f"Couldn't open a file manager ({exc}). Open the folder yourself in your file manager.",
        }
    return {"ok": True, "path": str(path)}


@dataclass(frozen=True, slots=True)
class DriveAttachment:
    """The result of making a folder usable as a truestill drive."""

    label: str
    registered: bool  # a marker was written now (the folder was not a drive before)
    linked: int  # already-organized files newly attached to this drive
    absent: int  # catalogued files whose copy is not actually on the drive


def attach_drive(path: Path, db: Path, *, write: bool) -> DriveAttachment:
    """Make ``path`` a registered drive, attaching any library already organized into it.

    **Why this exists.** Organizing through the app used to leave its destination unregistered:
    no marker, so no ``file_copies`` rows, so the app could not verify it, could not copy it
    anywhere, and counted it as living in zero places. The whole custody half of the product
    was reachable only by running the CLI's ``drives --init`` first -- a concept a user has no
    reason to have heard of, standing between "I organized my photos" and "make me a backup".

    Two halves, because a folder can be behind in two different ways:

    * **No marker** -- write one, labelled after the folder. A ~100-byte file at the root of a
      folder the user just asked us to fill with copies of their library.
    * **No recorded copies** -- a library organized before its folder was registered has rows
      in ``files`` but none in ``file_copies``. Each is attached only after confirming the copy
      is *actually present*; anything missing is counted and reported, never assumed.

    ``write=False`` reports what would happen and touches nothing, so previews stay pure.
    """
    marker = read_marker(path)
    was_registered = marker is not None
    if marker is None and not write:
        # Report what would happen without doing it: previews write nothing, ever.
        return DriveAttachment(label=path.name or "Library", registered=True, linked=0, absent=0)
    if marker is None:
        marker = create_marker(path, label=path.name or "Library")

    linked = absent = 0
    with Catalog(db) as catalog:
        if write:
            catalog.upsert_drive(uuid=marker.uuid, label=marker.label)
            catalog.set_setting(drive_path_hint(marker.uuid), str(path))
        known = {row["sha256"] for row in catalog.copies_on_drive(marker.uuid)}
        for row in catalog.organized_files():
            if row["sha256"] in known:
                continue
            if not (path / str(row["relative"])).is_file():
                absent += 1
                continue
            linked += 1
            if write:
                catalog.record_copy(
                    sha256=str(row["sha256"]),
                    drive_uuid=marker.uuid,
                    relative=str(row["relative"]),
                    copy_sha256=row["copy_sha256"],
                    size=row["size"],
                )
    return DriveAttachment(
        label=marker.label, registered=not was_registered, linked=linked, absent=absent
    )


class DriveRow(TypedDict):
    label: str
    uuid: str
    files: int
    photos: int
    videos: int
    audio: int
    size: int
    last_seen: str | None
    last_verified: str | None
    path: str | None


class WhereCopy(TypedDict):
    name: str
    drive: str
    relative: str
    last_verified: str | None


class WhereResult(TypedDict):
    copies: list[WhereCopy]
    total: int
    page: int
    pages: int
    page_size: int


class AtRiskRow(TypedDict):
    name: str
    drive: str


def list_drives(db: Path) -> list[DriveRow]:
    with Catalog(db) as catalog:
        names_by_drive: dict[str, list[str]] = {}
        for row in catalog.copy_names_by_drive():
            names_by_drive.setdefault(row["drive_uuid"], []).append(row["relative"])
        drives: list[DriveRow] = []
        for d in catalog.list_drives():
            breakdown = media_breakdown(names_by_drive.get(d["uuid"], []))
            # Live hint only. A dead path is cleared here so the next screen load does not
            # re-stat it; Check now / open-folder are omitted when path is absent.
            path = take_live_path_hint(catalog, drive_path_hint(d["uuid"]))
            drives.append(
                {
                    "label": d["label"],
                    "uuid": d["uuid"],
                    "files": d["file_count"],
                    "photos": breakdown["photos"],
                    "videos": breakdown["videos"],
                    "audio": breakdown["audio"],
                    "size": d["total_size"] or 0,
                    "last_seen": d["last_seen"],
                    "last_verified": d["last_verified"],
                    # Where it was last seen, so a card can offer "Check now" for the right
                    # folder. Absent when we have never had a path for it, or the hint was
                    # stale and cleared -- in which case the card states the fact without
                    # offering an action it cannot honour.
                    "path": path,
                }
            )
        return drives


def where(term: str, db: Path, *, page: int = 1) -> WhereResult:
    """One page of search results, plus what the caller needs to render a pager.

    Paged in SQL (`Catalog.find_copies`), so a page costs a page of rows however large the
    library is. The total comes from a separate `COUNT(*)`, which is what makes "page 3 of 12"
    honest rather than "more results, somewhere".
    """
    size = Catalog.FIND_PAGE_SIZE
    page = max(1, page)
    with Catalog(db) as catalog:
        total = catalog.count_copies(term)
        rows = catalog.find_copies(term, limit=size, offset=(page - 1) * size)
        copies: list[WhereCopy] = [
            {
                "name": r["original_name"] or r["relative"],
                "drive": r["drive_label"],
                "relative": r["relative"],
                "last_verified": r["last_verified"],
            }
            for r in rows
        ]
    return {
        "copies": copies,
        "total": total,
        "page": page,
        "pages": max(1, -(-total // size)),
        "page_size": size,
    }


def at_risk(db: Path) -> list[AtRiskRow]:
    with Catalog(db) as catalog:
        return [
            {"name": r["original_name"] or r["sha256"][:12], "drive": r["drive_label"]}
            for r in catalog.single_copy_shas()
        ]


class LibraryStatus(TypedDict):
    """Honest, catalog-driven totals for the custody strip."""

    library_path: str | None
    backup_path: str | None
    files: int
    photos: int
    videos: int
    audio: int
    by_format: dict[str, dict[str, int]]
    places: int
    single_copy: int
    bytes: int
    catalog_path: str
    catalog_presence: str
    catalog_detail: str
    catalog_tone: Literal["info", "notice", "alert"]


def library_status(db: Path, *, explicit_db: bool = False) -> LibraryStatus:
    """Honest, catalog-driven totals for the custody strip.

    Always names the resolved absolute catalog path. A missing file is first-run (info), not
    an error; an empty file with registered drives is the loud wrong-catalog case.
    """
    # Inspect before Catalog() so a missing path stays will_create (Catalog would create it).
    startup = inspect_catalog(db, explicit_db=explicit_db)
    with Catalog(db) as catalog:
        breakdown = media_breakdown(catalog.media_names())
        total = catalog.count()
        drives = [d for d in catalog.list_drives() if d["file_count"]]
        single_copy = catalog.single_copy_count()
        total_bytes = sum(d["total_size"] or 0 for d in drives)
        library_path = take_live_path_hint(catalog, LIBRARY_PATH_HINT)
        backup_path = take_live_path_hint(catalog, BACKUP_PATH_HINT)
    return {
        "library_path": library_path,
        "backup_path": backup_path,
        "files": total,
        "photos": breakdown["photos"],
        "videos": breakdown["videos"],
        "audio": breakdown["audio"],
        "by_format": breakdown["by_format"],
        "places": len(drives),
        "single_copy": single_copy,
        "bytes": total_bytes,
        "catalog_path": startup.absolute_path,
        "catalog_presence": startup.presence.value,
        "catalog_detail": startup.detail,
        "catalog_tone": startup.tone,
    }
