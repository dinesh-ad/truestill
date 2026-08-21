"""A thumbnail is drawn the way up the photograph was taken.

**The defect, measured on 4,108 real photographs rather than reasoned about.** `render` never
applied the EXIF orientation tag, and the WebP it writes carries no EXIF - so nothing downstream
could compensate. Of the corpus:

| orientation | n | what shipped |
|---|---:|---|
| 1 (upright) | 2,738 | correct |
| 3 (180 degrees) | 67 | **upside down**, correct aspect |
| 6 / 8 (quarter turns) | 1,303 | **sideways**, wrong aspect |
| | **1,370 (33.3%)** | **drawn wrong** |

200 of 200 sampled quarter-turn photos produced a landscape tile from a portrait source: a
4000x3000 file whose tag says portrait rendered 320x240.

⚠ **The 67 are the ones an aspect check cannot find.** A 180-degree rotation leaves width and
height alone, so every measurement of shape agrees with a picture that is upside down. The first
census here counted only orientations 5-8 and reported 31.7%; the real figure is 33.3%, and the
1.6% it missed is the class that is invisible to the method that found the rest.

**Two tests, deliberately, because neither alone is honest.**

`test_a_real_rotated_photograph_comes_out_upright` is the one that found the bug: real
photographs, real camera tags, no fabrication. It **skips without the corpus**, which is the
price of using files that cannot be committed - `e2e_support` already rules that "media files do
not belong in git whatever their provenance".

`test_every_orientation_is_applied` generates its fixtures, so it runs everywhere including CI,
and covers **all eight** orientations. That matters because **the corpus contains only 1, 3, 6
and 8** - there is no 5 or 7 in 4,108 photographs, so a corpus-only guard would leave the two
transposed-mirror cases untested and quietly claim coverage it does not have.
"""

from __future__ import annotations

import io
import os
import shutil
import subprocess
from pathlib import Path

import pytest
from PIL import Image
from truestill_core import thumbnails
from truestill_core.hashing import HEIF_AVAILABLE

#: Where real photographs live. Read-only; a test never organizes them. Derived from $HOME
#: rather than written out, and overridable, so the path carries no one machine's owner.
_CORPUS = Path(os.environ.get("TRUESTILL_CORPUS") or Path.home() / "TruestillLibrary" / "Input")

#: EXIF orientations whose transform swaps the axes.
_TRANSPOSING = {5, 6, 7, 8}


def _corpus_photos(wanted: set[int], limit: int) -> list[tuple[Path, int, int, int]]:
    """(path, stored_w, stored_h, orientation) for corpus photos carrying ``wanted``."""
    found: list[tuple[Path, int, int, int]] = []
    if not _CORPUS.is_dir():
        return found
    for path in _CORPUS.rglob("*"):
        if len(found) >= limit:
            break
        if not (path.is_file() and path.suffix.lower() in {".jpg", ".jpeg", ".heic", ".png"}):
            continue
        try:
            with Image.open(path) as image:
                width, height = image.size
                exif = image.getexif()
                orientation = int(exif.get(274, 1) or 1) if exif else 1
        except OSError:
            continue
        if orientation in wanted:
            found.append((path, width, height, orientation))
    return found


@pytest.mark.skipif(not _CORPUS.is_dir(), reason="no photo corpus on this machine")
def test_a_real_rotated_photograph_comes_out_upright() -> None:
    """THE GUARD, against real cameras. Fails on today's render for every rotated photo."""
    photos = _corpus_photos(_TRANSPOSING, limit=40)
    assert photos, (
        f"no transposing-orientation photos found under {_CORPUS}; this guard has no subject and "
        "would pass by checking nothing (ENGINEERING_STANDARD.md 4, fifty-second member)"
    )

    sideways = []
    for path, stored_w, stored_h, orientation in photos:
        # The tag transposes, so the TRUE shape is the stored one with the axes swapped.
        true_portrait = stored_w > stored_h
        with Image.open(io.BytesIO(thumbnails.render(path))) as thumb:
            thumb_w, thumb_h = thumb.size
        if (thumb_h > thumb_w) != true_portrait:
            sideways.append(f"{path.name} orientation={orientation} thumb={thumb_w}x{thumb_h}")

    assert not sideways, (
        f"{len(sideways)} of {len(photos)} real photographs rendered sideways: {sideways[:3]}. "
        "`render` must apply the EXIF orientation to the PIXELS - the WebP it writes carries no "
        "EXIF, so nothing downstream can."
    )


@pytest.mark.parametrize("orientation", [1, 2, 3, 4, 5, 6, 7, 8])
def test_every_orientation_is_applied(orientation: int, tmp_path: Path) -> None:
    """All eight, including the 5 and 7 that 4,108 real photographs do not contain.

    The fixture is a deliberately ASYMMETRIC 40x20 image, so a transform that is applied wrongly
    cannot look like one that is applied rightly - a square would make four of the eight
    indistinguishable.
    """
    source = tmp_path / f"orientation-{orientation}.jpg"
    image = Image.new("RGB", (40, 20), "white")
    for x in range(12):  # a mark in one corner, so the transform is observable
        for y in range(6):
            image.putpixel((x, y), (255, 0, 0))
    exif = image.getexif()
    exif[274] = orientation
    image.save(source, "JPEG", exif=exif)

    with Image.open(io.BytesIO(thumbnails.render(source))) as thumb:
        width, height = thumb.size

    swapped = orientation in _TRANSPOSING
    expected_portrait = swapped  # the fixture is landscape 40x20 before any transform
    assert (height > width) == expected_portrait, (
        f"orientation {orientation}: thumbnail is {width}x{height}; a transposing tag must swap "
        "the axes and a non-transposing one must not"
    )


def _camera_style_heic(path: Path, orientation: int | None) -> None:
    """A HEIC written the way a CAMERA writes one: pixels UNROTATED, the tag applied after.

    ⚠ **The obvious construction is wrong and would validate a fix that double-rotates.** Saving
    a landscape image *with* `exif=` through pillow_heif makes its ENCODER rotate the pixels and
    still write the tag, producing a file whose stored data is already portrait while its EXIF
    says to rotate again - internally inconsistent, and nothing a camera produces. Measured while
    building this: a fix validated against that fixture rotated the real file twice.

    So the tag goes on with exiftool, after encoding, leaving stored landscape + a pending turn.
    """
    Image.new("RGB", (40, 20), "white").save(path, format="HEIF")
    if orientation is None:
        return
    # ⚠ `PixelXDimension`/`PixelYDimension` are written too, because **every real camera HEIC
    # carries them** - verified on all four in `metadata-extractor-images` - and they are what
    # tells a decoded image apart from a stored one. A fixture without them exercises the
    # "cannot tell" branch instead of the one under test, which is how this fixture first
    # silently stopped reproducing the defect.
    subprocess.run(
        [
            "exiftool",
            "-overwrite_original",
            f"-Orientation#={orientation}",
            "-ExifImageWidth=40",
            "-ExifImageHeight=20",
            str(path),
        ],
        capture_output=True,
        check=True,
    )


@pytest.mark.skipif(not HEIF_AVAILABLE, reason="pillow-heif is not installed")
@pytest.mark.skipif(shutil.which("exiftool") is None, reason="exiftool not installed")
@pytest.mark.parametrize("orientation", [1, 2, 3, 4, 5, 6, 7, 8])
def test_every_orientation_is_applied_on_heif_too(orientation: int, tmp_path: Path) -> None:
    """`(aeu)`: the same promise as the JPEG case above, on the format current phones produce.

    **Why HEIF needs its own test rather than a parametrize over suffixes.** `pillow_heif`'s
    *Pillow plugin* path resets the EXIF orientation to 1 on open and stashes the value in
    ``info["original_orientation"]`` - it never rotates, and `as_plugin.py` contains no transpose
    at all. So `ImageOps.exif_transpose` reads a tag that has been zeroed and does nothing, and
    every rotated HEIC rendered sideways while every rotated JPEG rendered correctly. The
    mechanism is invisible to a JPEG fixture, so a JPEG fixture cannot guard it.

    Found by soak two on `metadata-extractor-images`: 4 of 20 HEIC files, one of them an
    iPhone 13 Pro Max capture. The maintainer's own corpus is 2013-2014 and effectively all JPEG,
    which is why `(adp)` measured 33.3% and still left this whole class wrong.
    """
    source = tmp_path / f"heif-orientation-{orientation}.heic"
    _camera_style_heic(source, orientation)

    with Image.open(io.BytesIO(thumbnails.render(source))) as thumb:
        width, height = thumb.size

    expected_portrait = orientation in _TRANSPOSING  # the fixture is landscape 40x20
    assert (height > width) == expected_portrait, (
        f"HEIF orientation {orientation}: thumbnail is {width}x{height}; a transposing tag must "
        "swap the axes and a non-transposing one must not"
    )


@pytest.mark.skipif(not HEIF_AVAILABLE, reason="pillow-heif is not installed")
def test_a_heif_carrying_no_orientation_is_left_alone(tmp_path: Path) -> None:
    """The cry-wolf half. A fix that reaches for a stashed value must not invent a rotation.

    Without this, `test_every_orientation_is_applied_on_heif_too` is satisfied by a change that
    rotates every HEIC, which would break the untagged majority - and `(adp)`'s own census says
    two thirds of a real corpus carry orientation 1.
    """
    source = tmp_path / "no-tag.heic"
    _camera_style_heic(source, None)

    with Image.open(io.BytesIO(thumbnails.render(source))) as thumb:
        assert thumb.width > thumb.height, (
            "a HEIC with no orientation tag was rotated anyway; the stored shape must survive"
        )


@pytest.mark.skipif(not HEIF_AVAILABLE, reason="pillow-heif is not installed")
@pytest.mark.skipif(shutil.which("exiftool") is None, reason="exiftool not installed")
def test_a_heif_libheif_already_rotated_is_not_rotated_twice(tmp_path: Path) -> None:
    """⚠ The direction that broke three real files, and the one a "never" mutation cannot reach.

    HEIF can express a rotation **twice**: the container property ``irot``, which libheif applies
    while decoding, and the legacy EXIF ``Orientation`` tag. Apple writes both. So a file can
    arrive already upright with a stashed orientation that has **already been honoured**, and
    re-applying it turns a correct photograph on its side.

    Measured on `metadata-extractor-images` while building the fix: of four HEICs carrying
    orientation 6, **three carry `irot` and decode upright** and one carries only the EXIF tag.
    A fix keyed on the stash alone corrected that one and broke the other three.

    Mutating `_pending_heif_orientation` to return the stash unconditionally **survived** until
    this test existed - §4's thirty-first member, mutate the condition to *always* as well as to
    *never*, or you have measured whichever half you happened to pick.

    The fixture is built by saving *with* `exif=`, which makes pillow_heif's encoder rotate the
    pixels and write `irot`; the stored extent is then stamped on so the size comparison - rather
    than the "cannot tell" fallback - is what decides.
    """
    source = tmp_path / "already-rotated.heic"
    image = Image.new("RGB", (40, 20), "white")
    exif = image.getexif()
    exif[274] = 6
    image.save(source, format="HEIF", exif=exif.tobytes())
    subprocess.run(
        [
            "exiftool",
            "-overwrite_original",
            "-ExifImageWidth=40",
            "-ExifImageHeight=20",
            str(source),
        ],
        capture_output=True,
        check=True,
    )

    with Image.open(source) as opened:
        assert opened.size[1] > opened.size[0], (
            "PRECONDITION: this fixture must arrive already rotated, or it tests the other branch"
        )
        assert opened.info.get("original_orientation") == 6, (
            "PRECONDITION: the stash must be present, or nothing could double-rotate"
        )

    with Image.open(io.BytesIO(thumbnails.render(source))) as thumb:
        assert thumb.height > thumb.width, (
            f"a HEIC libheif had already rotated was rotated again: {thumb.size}. The stashed "
            "orientation had already been honoured by the container's irot property."
        )


@pytest.mark.skipif(not HEIF_AVAILABLE, reason="pillow-heif is not installed")
@pytest.mark.skipif(shutil.which("exiftool") is None, reason="exiftool not installed")
@pytest.mark.xfail(
    strict=True,
    reason="(aeu) KNOWN GAP: a 180-degree turn leaves both dimensions unchanged, so the stored-vs-"
    "decoded comparison cannot tell an applied turn from a pending one. Closing it needs the "
    "container read for irot. Strict, so widening the condition turns this XPASS into a failure "
    "and the double-rotation risk has to be confronted rather than inherited.",
)
def test_an_exif_only_heif_turned_180_is_a_known_gap(tmp_path: Path) -> None:
    """Pins the gap by CONTENT rather than by aspect, which is the only way to see it.

    `(adp)`'s own census makes the point: *"a 180-degree rotation leaves width and height alone, so
    every measurement of shape agrees with a picture that is upside down"* - 67 of its 1,370 were
    invisible to the aspect method that found the other 1,303. The same blindness applies to the
    discriminator this fix uses, so the gap is asserted here rather than left for someone to
    rediscover.

    A mark in the top-left must end up bottom-right after a 180-degree turn. It does not today.
    """
    source = tmp_path / "turned-180.heic"
    image = Image.new("RGB", (40, 20), "white")
    for x in range(12):
        for y in range(6):
            image.putpixel((x, y), (255, 0, 0))
    image.save(source, format="HEIF")
    subprocess.run(
        [
            "exiftool",
            "-overwrite_original",
            "-Orientation#=3",
            "-ExifImageWidth=40",
            "-ExifImageHeight=20",
            str(source),
        ],
        capture_output=True,
        check=True,
    )

    with Image.open(io.BytesIO(thumbnails.render(source))) as thumb:
        rgb = thumb.convert("RGB")
        bottom_right = rgb.getpixel((rgb.width - 3, rgb.height - 3))
    assert isinstance(bottom_right, tuple)
    assert bottom_right[0] > bottom_right[1], (
        "a 180-degree turn must move the mark to the opposite corner"
    )
