"""Serve a thumbnail for catalogued content, addressed by sha256.

**The first route in truestill that returns file-derived bytes**, so what stops it returning
anything else is the point of this module rather than an afterthought.

* `LocalGuard` wraps the **whole app**, not each route, and its one exemption is `/static/`
  ("inert assets, no data"). A route under `/api/` therefore inherits the token, Host and Origin
  checks by construction - there is nothing to remember to add.
* **The caller names CONTENT, never a path.** §3.1 already rules that identity is not a path;
  reusing that here means a client can ask for something the catalog knows and cannot express a
  file request at all. Traversal is not defended against, it is unrepresentable.
* The two joins that do exist are both guarded by code that already owned them: the content id is
  refused unless it matches `^[0-9a-f]{64}$` before it becomes a cache filename, and the catalog's
  **relative** copy path goes through `destinations.check_contained` before it is joined onto a
  drive root.

**What a token holder can still do, stated rather than implied:** fetch a thumbnail of any
catalogued photo. That is the authority the token already grants over `library/status`, `where`
and the rest. A stolen token was already game over; this uses the boundary, it does not move it.

**Why the token rides in the query string here.** An `<img>` element cannot set a header, so tiles
authenticate with `?token=`, exactly as the SSE URLs already do. The consequence is that a cached
tile URL is scoped to one session, which is why the response is `private` rather than `public`.
"""

from __future__ import annotations

from pathlib import Path

from PIL import UnidentifiedImageError
from truestill_core import thumbnails
from truestill_core.app_paths import cache_path_for
from truestill_core.catalog_session import open_catalog
from truestill_core.destinations.base import check_contained
from truestill_core.drive import drive_path_hint
from truestill_core.thumbnails import BadContentIdError

from truestill_app.service.drive_support import take_live_path_hint

#: Content-addressed, so a URL's bytes can never change and a year is not a gamble. `private`
#: rather than `public` because the URL carries a session token - there is no shared proxy on
#: 127.0.0.1, but declaring the truth costs nothing and outlives the assumption.
CACHE_CONTROL = "private, max-age=31536000, immutable"


class NoReachableCopyError(LookupError):
    """The catalog knows this content but no copy of it can be opened right now.

    Distinct from "unknown content" on purpose, and both answer 404: telling an unauthenticated
    caller which hashes exist would be a membership oracle over the library.
    """


class UndecodableImageError(OSError):
    """The file is present and its format is known, but its bytes will not decode.

    **A distinct class because it is a distinct fact.** `UnidentifiedImageError` means Pillow
    could not tell what the file *is*; this means it knows exactly what it is and the data is
    damaged - a JPEG that stops early raises a plain `OSError` (*"broken data stream"*, *"image
    file is truncated"*), which is **not** a subclass of `UnidentifiedImageError` (verified) and
    so fell through every handler and reached the client as a **500**.

    **Measured, not hypothetical: 5 of 4,108 real photographs in the corpus do this.** One damaged
    photo in a grid of forty-eight took the tile out with a server error.

    **Answered 422 rather than 415, following imgproxy**, which returns 422 when a source is
    reachable but cannot be processed and reserves media-type codes for media types. A truncated
    JPEG *is* a supported media type; nothing about the format is unsupported. 500 would be a lie
    in the other direction - the server is fine, the photograph is damaged.

    ⚠ **Deliberately NOT salvaged with `ImageFile.LOAD_TRUNCATED_IMAGES`.** It is the common
    remedy and it is wrong here: it would render the intact prefix, pad the rest, and **cache that
    silently under the content hash** - so a damaged photo would look fine forever and the one
    surface that could have told a person their file is rotting would be the one hiding it. This
    is a custody tool; a photo that will not decode is something the owner needs to know.
    """


def source_for(sha256: str, db: Path) -> Path | None:
    """An openable file holding this content, or ``None``.

    Drives are tried **biggest-holding first** (`drives_holding`'s order), which puts the library
    drive ahead of a partial backup without needing to know which is which. Each candidate costs
    one settings read and one `is_file`, so a miss is cheap and a hit is the first one.
    """
    with open_catalog(db) as catalog:
        for holding in catalog.drives_holding([sha256]):
            root = take_live_path_hint(catalog, drive_path_hint(holding.drive_uuid))
            if root is None:
                continue  # drive not mounted where it was last seen; the hint is now cleared
            relative = catalog.copy_relative(sha256, holding.drive_uuid)
            if relative is None:
                continue
            # The catalog's own string, but guarded anyway: `check_contained` is the existing
            # owner of this join, and a stored path is only as trustworthy as every writer that
            # ever touched the row. Cheap, lexical, and it makes the property local.
            check_contained(relative)
            candidate = Path(root) / relative
            if candidate.is_file():
                return candidate
    return None


def thumbnail_bytes(sha256: str, db: Path) -> bytes:
    """WebP bytes for this content.

    Raises :class:`~truestill_core.thumbnails.BadContentIdError` when the id is not a sha256,
    :class:`NoReachableCopyError` when nothing holding it can be opened, and
    ``UnidentifiedImageError`` when the file is there but is not a decodable image.

    **The cache is consulted before the catalog, which is what makes a warm grid free.** A hit
    costs one `read_bytes` (0.05 ms measured) and opens no database at all; only a miss pays for
    the lookup. A grid of fifty revisited tiles therefore does fifty file reads rather than fifty
    catalog opens.
    """
    cache_dir = cache_path_for(db).parent
    cached = thumbnails.cache_path(cache_dir, sha256)  # raises on a bad id, before any I/O
    try:
        return cached.read_bytes()
    except OSError:
        pass

    source = source_for(sha256, db)
    if source is None:
        raise NoReachableCopyError(sha256)
    try:
        return thumbnails.thumbnail(source, sha256, cache_dir)
    except UnidentifiedImageError:
        raise
    except OSError as error:
        # A damaged photo, not a broken server - see `UndecodableImageError`. Narrowed to
        # OSError rather than Exception: a permission or disk fault is a different fact and
        # must not be reported to the user as a corrupt photograph.
        raise UndecodableImageError(str(error)) from error


__all__ = [
    "CACHE_CONTROL",
    "BadContentIdError",
    "NoReachableCopyError",
    "UndecodableImageError",
    "UnidentifiedImageError",
    "source_for",
    "thumbnail_bytes",
]
