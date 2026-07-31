"""Copy a legacy catalog to the OS-conventional location - explicitly, and refusing on doubt.

`(aae)` moved the *default* location; this is the only thing that moves an existing file, and it
happens **because a user asked**, never on startup. `app_paths.default_catalog_path` keeps
preferring an existing ``reports/catalog.sqlite`` precisely so an upgrade changes nothing until
someone decides otherwise.

**Every choice here inverts a documented failure of the mechanism it imitates.** wxWidgets'
``MigrateLocalFile`` renames over the destination when a file exists in both locations, and does
not check for symlinks. On a settings file that is an annoyance; on the record of which drive
holds the only copy of someone's photos it is data loss. So:

* **copy, never move** - the original stays, and the *user* deletes it when satisfied;
* **never overwrite** - two catalogs means two histories, and only their owner knows which one
  matters. Refuse, and report both with sizes and times so the choice is possible;
* **never follow or clobber a symlink** - someone may have linked the old path at the new one
  already, and following it would copy a file onto itself or write through to a third place.

**It also reports what it did not do**, which is the part a successful-sounding message would
omit: after the copy the old catalog is still there and is still the one that will be used, and
the cache is deliberately not migrated.

**Complexity: O(size of the catalog)** - one ``copy2``, a few ``stat`` calls. Nothing is read
into memory and no catalog is opened; this moves a file, it does not understand one.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path


class CatalogMoveOutcome(StrEnum):
    """What happened. Each is a distinct answer to a distinct question the user asked."""

    COPIED = "copied"
    #: The catalog is already where it belongs - the ordinary state after a migration, and a
    #: calm answer rather than a refusal.
    ALREADY_STANDARD = "already_standard"
    #: There is no legacy catalog to move. Not an error: a reasonable question, answered.
    NOTHING_TO_MOVE = "nothing_to_move"
    #: Both exist. Refused, with enough detail to tell them apart.
    DESTINATION_EXISTS = "destination_exists"
    #: A symlink is involved on either side. Never followed, never written through.
    SYMLINK_REFUSED = "symlink_refused"


@dataclass(frozen=True, slots=True)
class CatalogMove:
    """The result, including the part a success message would leave out."""

    outcome: CatalogMoveOutcome
    source: Path
    destination: Path
    #: What a person should read. Carries what was *not* done as well as what was.
    detail: str
    #: The catalog that will actually be used on the next run. After a copy this is still the
    #: **old** one, because `default_catalog_path` prefers it while it exists - which is exactly
    #: what someone who copies and deletes nothing needs to be told.
    still_in_use: Path


def _describe(path: Path) -> str:
    """``path`` with its size and modification time, so two catalogs can be told apart."""
    try:
        stat = path.stat()
    except OSError:
        return f"{path} (cannot read its details)"
    when = datetime.fromtimestamp(stat.st_mtime, UTC).strftime("%Y-%m-%d %H:%M")
    return f"{path} ({stat.st_size} bytes, last changed {when})"


#: Said every time a copy succeeds. The cache is keyed by absolute path and machine-specific
#: (`hash_cache`), so copying it would carry a hundred percent misses to the new location while
#: looking like it had done something useful.
_CACHE_NOTE = (
    "The cache was not copied, on purpose: it is tied to this machine and rebuilds itself the "
    "next time you organize."
)


def move_catalog_to_standard(source: Path, destination: Path) -> CatalogMove:
    """Copy ``source`` to ``destination``, refusing rather than risking either file."""
    if source == destination:
        return CatalogMove(
            CatalogMoveOutcome.ALREADY_STANDARD,
            source,
            destination,
            f"Your catalog is already at {destination}. Nothing to do.",
            still_in_use=destination,
        )
    if not source.exists():
        return CatalogMove(
            CatalogMoveOutcome.NOTHING_TO_MOVE,
            source,
            destination,
            f"There is no catalog at {source}, so there is nothing to move. "
            f"truestill is using {destination}.",
            still_in_use=destination,
        )
    # Checked before anything else touches the paths: `exists()` follows symlinks, so a link
    # would otherwise read as an ordinary file and be copied through.
    if source.is_symlink() or destination.is_symlink():
        linked = source if source.is_symlink() else destination
        return CatalogMove(
            CatalogMoveOutcome.SYMLINK_REFUSED,
            source,
            destination,
            f"{linked} is a shortcut to somewhere else, so nothing was copied. truestill will "
            f"not write through a shortcut - it cannot tell whether you linked these two "
            f"together on purpose. Move or remove the shortcut yourself, then try again.",
            still_in_use=source,
        )
    if destination.exists():
        return CatalogMove(
            CatalogMoveOutcome.DESTINATION_EXISTS,
            source,
            destination,
            "There is already a catalog in the new location, and truestill will not overwrite "
            "it - only you know which one holds your library.\n"
            f"  in use now : {_describe(source)}\n"
            f"  new location: {_describe(destination)}\n"
            "Keep the one you want, move the other out of the way, and try again.",
            still_in_use=source,
        )

    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    return CatalogMove(
        CatalogMoveOutcome.COPIED,
        source,
        destination,
        f"Copied your catalog to {destination}.\n"
        f"  Nothing was removed: {source} is still there, and truestill is still using it. "
        f"Check the copy, then delete the old one when you are happy - the next run will use "
        f"the new location.\n"
        f"  {_CACHE_NOTE}",
        still_in_use=source,
    )
