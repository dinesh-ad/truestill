"""Server-side folder picker (Browse) - roots, dirs, create, validate.

Self-contained surface: no Catalog. Depends only on ``read_marker`` and
``MEDIA_EXTENSIONS`` from core.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal, TypedDict, cast

from truestill_core.drive import read_marker
from truestill_core.organizer import MEDIA_EXTENSIONS


class FsRoot(TypedDict):
    label: str
    path: str


class FsEntry(TypedDict):
    name: str
    path: str


class FsDirsOk(TypedDict):
    path: str
    parent: str | None
    roots: list[FsRoot]
    entries: list[FsEntry]


class FsDirsErr(TypedDict):
    error: str
    roots: list[FsRoot]
    entries: list[FsEntry]


class FsValidateResolved(TypedDict):
    exists: bool
    is_dir: bool
    readable: bool
    writable: bool
    is_drive: bool
    media: int
    media_capped: bool


class FsValidateUnresolved(TypedDict):
    """Resolve failed: same keys the API has always returned on that path (no is_drive)."""

    exists: bool
    is_dir: bool
    readable: bool
    writable: bool
    media: int


class FsCreateFailed(TypedDict):
    created: Literal[False]
    error: str


class FsCreateOk(FsValidateResolved):
    created: Literal[True]


def fs_roots() -> list[FsRoot]:
    """Friendly starting points: Home + common media folders + mounted drives."""
    roots: list[FsRoot] = []
    home = Path.home()
    roots.append({"label": "Home", "path": str(home)})
    for name in ("Pictures", "Downloads", "Desktop", "Documents"):
        candidate = home / name
        if candidate.is_dir():
            roots.append({"label": name, "path": str(candidate)})
    for base in ("/media", "/mnt", "/run/media", "/Volumes"):
        root = Path(base)
        if not root.is_dir():
            continue
        try:
            for child in sorted(root.iterdir()):
                if child.is_dir():
                    roots.append({"label": child.name, "path": str(child)})
        except OSError:
            continue
    return roots


def fs_dirs(path_str: str) -> FsDirsOk | FsDirsErr:
    """List the immediate sub-directories of ``path`` (or the roots when empty)."""
    if not path_str.strip():
        return {"path": "", "parent": None, "roots": fs_roots(), "entries": []}
    path = Path(path_str).expanduser()
    try:
        path = path.resolve()
    except OSError:
        return {
            "error": "That path could not be read. It may have moved or access may be blocked. Pick another folder.",
            "roots": fs_roots(),
            "entries": [],
        }
    if not path.is_dir():
        return {
            "error": "That path is not a folder. Pick a folder.",
            "roots": fs_roots(),
            "entries": [],
        }
    entries: list[FsEntry] = []
    try:
        for child in sorted(path.iterdir(), key=lambda p: p.name.lower()):
            if child.is_dir() and not child.name.startswith("."):
                entries.append({"name": child.name, "path": str(child)})
    except OSError:
        return {
            "error": "That folder could not be read. Check permissions, then try again.",
            "roots": fs_roots(),
            "entries": [],
        }
    parent = str(path.parent) if path.parent != path else None
    return {"path": str(path), "parent": parent, "roots": fs_roots(), "entries": entries}


def fs_create(path_str: str) -> FsCreateOk | FsCreateFailed:
    """Create a folder (and parents) - for the "Create it?" action on a new backup destination."""
    path = Path(path_str).expanduser()
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return {
            "created": False,
            "error": (
                f"Couldn't create this folder ({exc}). "
                "Choose another location, or create it in your file manager."
            ),
        }
    validated = fs_validate(str(path))
    # Same spread the untyped path used; cast records the post-create resolved shape.
    return cast(FsCreateOk, {"created": True, **validated})


def fs_validate(path_str: str, *, cap: int = 10000) -> FsValidateResolved | FsValidateUnresolved:
    """Report whether ``path`` is a usable folder and roughly how much media it holds."""
    path = Path(path_str).expanduser()
    try:
        path = path.resolve()
    except OSError:
        return {"exists": False, "is_dir": False, "readable": False, "writable": False, "media": 0}
    is_dir = path.is_dir()
    media = 0
    capped = False
    if is_dir and os.access(path, os.R_OK):
        for child in path.rglob("*"):
            if child.suffix.lower() in MEDIA_EXTENSIONS:
                media += 1
                if media >= cap:
                    capped = True
                    break
    return {
        "exists": path.exists(),
        "is_dir": is_dir,
        "readable": os.access(path, os.R_OK) if path.exists() else False,
        "writable": os.access(path, os.W_OK) if path.exists() else False,
        "is_drive": read_marker(path) is not None,
        "media": media,
        "media_capped": capped,
    }
