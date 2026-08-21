"""A thumbnail for a photo, addressed by content and cached beside the hash cache.

**Why this exists.** truestill is a photo organizer that has never shown a photo: zero `<img>`
elements in the product. Every other complaint about how it looks was downstream of that.

**Addressed by `sha256`, never by path, and that is the security design rather than a convention.**
The route above this hands in content identity; nothing here ever receives a caller-supplied path.
§3.1 already rules that identity is never a path - it is why a confirmation survives a rename, a
migrate and a re-layout - and reusing it here means a client cannot ask for a file, only for
content the catalog already knows. Traversal is impossible by construction rather than defended by
validation.

**`draft()`, not the embedded EXIF thumbnail.** Pillow exposes **no supported API** for the
embedded one - the IFD1 offsets (tags 513/514) are absent from `getexif()` on **0 of 600** fenced
corpus files - so taking it means hand-rolling a JPEG marker scanner plus a fallback for whatever
it misses. `draft()` is Pillow's documented DCT-scaling decode (libjpeg returns the image at 1/2,
1/4 or 1/8 scale) and it covers everything Pillow opens, including HEIC.

**Cost, measured over 600 files of the fenced corpus rather than estimated** (median 8 MP JPEG):

| stage | ms |
|---|---:|
| decode at 1/8 scale + resize | 20.0 |
| WebP encode, method 2 | 3.1 |
| **cold total** | **~23** |
| warm (cache hit) | 0.05 |

⚠ **An earlier 80-file sample said 14 ms and it was wrong by 2.3x.** The sample skewed small; the
corpus pass is the number, and the two paths were re-run against the *same* 600 files before
anything here was believed. A 24-tile viewport costs **0.55 s cold, once**.

**Complexity: O(1) per thumbnail.** One decode at reduced scale, one encode. No walk, no catalog,
no I/O beyond the single source file and the cache entry. Callers build these **on demand for what
is on screen**; this module deliberately offers no way to sweep a library.
"""

from __future__ import annotations

import io
import re
from pathlib import Path

from PIL import Image, ImageOps
from PIL.ExifTags import IFD

# Imported for its IMPORT-TIME SIDE EFFECTS, not for a name, and that is why it is not an unused
# import: `hashing` registers the pillow-heif opener and raises `Image.MAX_IMAGE_PIXELS` to 300 MP
# when it loads. Depending on some other module having imported it first would make HEIC support
# and the panorama ceiling a function of import ORDER - working under the app, silently absent in a
# unit test or a future caller. `HEIF_AVAILABLE` is re-exported so the dependency is a name a
# linter can see and `test_heic_support_is_not_a_function_of_import_order` can assert.
from truestill_core.hashing import HEIF_AVAILABLE

__all__ = [
    "CACHE_SUBDIR",
    "HEIF_AVAILABLE",
    "THUMB_PX",
    "BadContentIdError",
    "cache_path",
    "render",
    "thumbnail",
    "upright_size",
]

#: The long edge, in CSS pixels of the grid tile times two, so a 160px tile stays sharp on a
#: 2x display. Larger buys nothing a grid can show; smaller is visibly soft when the panel widens.
THUMB_PX = 320

#: WebP quality. Lossy is right here: this is a proxy for a photo, never the photo, and §1's
#: no-re-encode rule is about the ORIGINAL, which is untouched. Median 13,395 bytes on the corpus.
_QUALITY = 80

#: WebP effort. **Chosen at the knee of a measured curve, not at the library default.** Encode ms
#: against median bytes over 200 corpus files: m0 2.02/15,743 · m1 2.48/14,892 · **m2 3.09/13,395**
#: · m3 6.28/13,025 · m4 6.25/13,031 · m6 17.83/12,341. Past 2 the encode DOUBLES to buy 3% fewer
#: bytes; below it the bytes climb fast. Pillow's default is 4, which is the wrong end of that
#: trade for an image regenerated on a cache miss and then never again.
_METHOD = 2

#: Cache entries live under the OS cache directory, in their own subdirectory so the whole set can
#: be dropped without touching `hashes.cache.sqlite` beside it.
CACHE_SUBDIR = "thumbs"

#: The only shape a content id may take. Checked BEFORE the value becomes a filename, so it cannot
#: carry a separator or a `..` into the join below - the second of the two joins the security
#: review named, the first being the drive-relative path that `destinations.check_contained` owns.
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class BadContentIdError(ValueError):
    """The identifier is not a sha256. Never rendered to a user - the route answers 400."""


def cache_path(cache_dir: Path, sha256: str) -> Path:
    """Where this content's thumbnail lives, or raise if the id is not a sha256.

    Two levels of fan-out on the first two hex characters. A single directory holding 33,457
    entries is legal on ext4 and slow to list on anything that does; 256 buckets keeps every
    directory small without a second lookup.
    """
    if not _SHA256.match(sha256):
        message = "content id is not a sha256"
        raise BadContentIdError(message)
    return cache_dir / CACHE_SUBDIR / sha256[:2] / f"{sha256}.webp"


#: The EXIF orientations whose transform swaps the axes. 5-8 are the transposed quarter-turns;
#: 2, 3 and 4 rotate or mirror without changing which edge is longer.
_TRANSPOSING_ORIENTATIONS = frozenset({5, 6, 7, 8})


def upright_size(width: int, height: int, orientation: int | None) -> tuple[int, int]:
    """The shape a photograph is SEEN in, from its stored dimensions and its EXIF orientation.

    **This lives beside `render` on purpose.** `render` applies `ImageOps.exif_transpose`, so a
    thumbnail's shape is the upright one; anything describing that photograph elsewhere - a
    payload a layout is computed from, say - has to reach the same answer or the numbers and the
    pixels disagree. Measured: **31.7% of a 4,108-photograph corpus** carries a transposing tag,
    so the two would part company on nearly a third of every grid.

    One function, two callers, no second implementation of the same rule. `orientation` is the
    raw EXIF integer 1-8; anything else, including ``None`` for a file that carries no tag, means
    the stored dimensions are already the upright ones.
    """
    if orientation in _TRANSPOSING_ORIENTATIONS:
        return height, width
    return width, height


def _fitted(width: int, height: int) -> tuple[int, int]:
    """The box ``thumbnail`` will actually produce for this image - long edge ``THUMB_PX``.

    **This exists because handing `draft()` a SQUARE target silently wastes a halving**, which is
    three quarters of the pixels. `draft()` picks its DCT scale from the *tighter* of the two
    ratios while `thumbnail()` fits the *long* edge, so a square box lets the short edge decide.
    On the corpus's median 3200x2368, `draft("RGB", (320, 320))` yields **800x592 (1/4)** where the
    aspect-correct `(320, 237)` yields **400x296 (1/8)**. Measured 25.8 ms -> 20.0 ms, with a mean
    per-channel difference from a full decode of **1.6/255**, which is not a visible one.
    """
    if width >= height:
        return THUMB_PX, max(1, round(height * THUMB_PX / width))
    return max(1, round(width * THUMB_PX / height)), THUMB_PX


#: EXIF ``Orientation``. Named because it is written here and read by `ImageOps.exif_transpose`,
#: and a bare `0x0112` at a call site is a magic number the next reader has to look up.
_ORIENTATION_TAG = 0x0112

#: Where `pillow_heif`'s Pillow plugin puts the orientation it removed. Its own key, not ours.
_HEIF_STASHED_ORIENTATION = "original_orientation"


#: EXIF ``PixelXDimension`` / ``PixelYDimension``, in the Exif sub-IFD. They describe the image as
#: **stored**, which is what makes them the discriminator below.
_STORED_EXTENT_TAGS = (0xA002, 0xA003)


def _stored_extent(image: Image.Image) -> tuple[int, int] | None:
    """The size EXIF says the image is stored at, or ``None`` when it does not say."""
    try:
        sub = image.getexif().get_ifd(IFD.Exif)
    except (KeyError, OSError, ValueError, SyntaxError):  # a malformed EXIF block is not fatal here
        return None
    width, height = (sub.get(tag) for tag in _STORED_EXTENT_TAGS)
    if isinstance(width, int) and isinstance(height, int) and width > 0 and height > 0:
        return width, height
    return None


def _pending_heif_orientation(image: Image.Image) -> int | None:
    """The turn `pillow_heif` removed that libheif did **not** already apply, or ``None``. `(aeu)`

    ⚠ **CALL THIS BEFORE `draft`/`thumbnail`.** It compares the DECODED size against the stored
    extent, and both of those resize the image - after them the comparison is meaningless and
    would answer "already applied" for everything.

    **Why a comparison is needed at all, and why the obvious fix is wrong.** HEIF can express a
    rotation twice: as the container property ``irot``, which libheif applies while decoding, and
    as the legacy EXIF ``Orientation`` tag. Apple writes **both**. So the stash alone cannot say
    whether a turn is still pending, and re-applying it on a file that has one double-rotates.
    Measured on four real HEICs: three carry ``irot`` and decode already upright, one carries only
    the EXIF tag and decodes flat. A fix keyed on the stash alone corrected the one and **broke
    the three** - caught before it shipped, by checking the real files rather than the fixture.

    **The discriminator, which needs nothing we do not already hold**: EXIF's own
    ``PixelXDimension``/``PixelYDimension`` describe the image as **stored**. If the decoded size
    differs from them, libheif transformed it and the tag is spent; if it matches, the turn is
    still pending and `exif_transpose` must do it.

    ⚠ **LIMITED TO THE TRANSPOSING TURNS, DELIBERATELY, AND THIS IS A KNOWN GAP.** Orientations 2,
    3 and 4 mirror or turn 180 degrees, which leaves both dimensions unchanged - so the comparison
    reads "sizes match" whether or not libheif already applied them, and acting on it could turn a
    correct picture upside down. That is `(adp)`'s own blind spot restated: *"a 180-degree rotation
    leaves width and height alone, so every measurement of shape agrees with a picture that is
    upside down."* An EXIF-only HEIC carrying orientation 3 therefore stays as it renders today.
    Closing it needs the container read for ``irot``, which is a parser this module does not have
    and should not grow for one case.
    """
    stashed = image.info.get(_HEIF_STASHED_ORIENTATION)
    if not isinstance(stashed, int) or stashed not in _TRANSPOSING_ORIENTATIONS:
        return None
    stored = _stored_extent(image)
    # No stored extent means we cannot tell, and the safe default is the majority case: files
    # carrying `irot` decode upright already, so doing nothing leaves them right.
    if stored is None or stored != image.size:
        return None
    return stashed


def _restore_heif_orientation(image: Image.Image, pending: int | None) -> None:
    """Put back the orientation `pillow_heif` removed, so `exif_transpose` can act on it. `(aeu)`

    **The defect this closes, measured rather than reasoned about.** `pillow_heif`'s *Pillow
    plugin* path calls `set_orientation` on open, whose own docstring is *"Reset orientation in
    EXIF to 1 if any orientation present"* - and `as_plugin.py` contains **no transpose at all**.
    So the pixels stay as stored, the tag is zeroed, and the value is stashed under
    ``info["original_orientation"]``. `ImageOps.exif_transpose` then reads a 1 and does nothing.

    Its sibling path, `HeifImage.to_pillow`, *does* rotate - so the two ways of opening the same
    file disagree, and the one Pillow's `Image.open` reaches is the one that does not.

    Measured on `metadata-extractor-images`: **4 of 20** HEIC files, every one `exiftool=6 /
    PIL=1`, including an iPhone 13 Pro Max capture. `(adp)` measured this class at **33.3%** of a
    real corpus and fixed it for JPEG; HEIC is what current phones write, so on a modern library
    this is the whole rotated class.

    ⚠ **Nothing here is HEIF-specific except the key.** The stash is set only by `pillow_heif`, so
    a JPEG, PNG or TIFF never has it and this is inert for them - which is why it sits in `render`
    rather than behind a suffix check that would rot the first time a format is added.

    ⚠ **This is a WORKAROUND for a library's behaviour, and it is written to fail loudly if that
    behaviour changes.** If `pillow_heif` ever starts rotating in the plugin path while still
    stashing the value, this would rotate twice - and
    `test_every_orientation_is_applied_on_heif_too` goes red the moment it does, in both
    directions, because it asserts the shape for all eight orientations and its sibling asserts an
    untagged file is left alone. The guard is the contract with upstream, not this comment.
    """
    if pending is not None:
        image.getexif()[_ORIENTATION_TAG] = pending


def render(source: Path) -> bytes:
    """Decode ``source`` at reduced scale and return WebP bytes. Raises on anything unreadable."""
    with Image.open(source) as image:
        # ⚠ BEFORE `draft`, because it compares the decoded size against the stored extent and
        # both `draft` and `thumbnail` change that size. `(aeu)`
        pending = _pending_heif_orientation(image)
        # Ask libjpeg for the smallest DCT scale that still covers the target. A no-op for formats
        # that cannot do it, which is why it is safe unconditionally, and a no-op upward: a source
        # already smaller than THUMB_PX is left at its own size rather than enlarged.
        image.draft("RGB", _fitted(*image.size))
        image.thumbnail((THUMB_PX, THUMB_PX))
        # ROTATE THE PIXELS, because nothing downstream can. Measured on a 4,108-photo corpus:
        # **31.7% carry an EXIF orientation that transposes the axes**, and every one of 200
        # sampled rendered sideways - a 4000x3000 source whose tag says portrait produced a
        # 320x240 landscape tile. The browser cannot compensate: WebP is written without EXIF, so
        # the tag a JPEG carried is gone by the time anything sees the bytes.
        #
        # ⚠ **LAST, NOT FIRST, AND THE ORDER IS WORTH 4.4x.** `exif_transpose` needs pixels, so
        # calling it before `draft` forces a full-resolution decode and throws away the DCT
        # scaling this function exists for. Measured over 40 corpus photos: **27.00 ms/file with
        # the transpose last, 117.82 ms/file with it first.** Same output either way - verified,
        # both orders give (240, 320) on a rotated source - so the cheap order is free.
        _restore_heif_orientation(image, pending)
        upright = ImageOps.exif_transpose(image)
        buffer = io.BytesIO()
        # `convert` after `thumbnail`: a palette or CMYK source cannot be saved as WebP directly,
        # and converting the already-reduced image is the cheap order.
        upright.convert("RGB").save(buffer, "WEBP", quality=_QUALITY, method=_METHOD)
    return buffer.getvalue()


def thumbnail(source: Path, sha256: str, cache_dir: Path) -> bytes:
    """Cached WebP bytes for ``source``. Builds and stores on a miss.

    **The cache needs no invalidation, and that follows from the key rather than from care.**
    The entry is addressed by content, so an edited file is a different sha and a different entry;
    a stale one is unreachable rather than wrong. The directory is disposable per `(aae)` -
    deleting it costs only time.

    **Written to a sibling and renamed**, the same discipline `safe_copy` applies to the library:
    two viewers can request the same tile at once, and a half-written file must never be served as
    a whole one. A failed write leaves the cache without the entry, which is a rebuild, not a
    corruption.
    """
    target = cache_path(cache_dir, sha256)
    try:
        return target.read_bytes()
    except OSError:
        pass

    data = render(source)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        partial = target.with_name(f"{target.name}.{id(data):x}.partial")
        partial.write_bytes(data)
        partial.replace(target)
    except OSError:
        # A cache that cannot be written is a slower app, never a broken one. The bytes are
        # already in hand and are returned regardless.
        pass
    return data
