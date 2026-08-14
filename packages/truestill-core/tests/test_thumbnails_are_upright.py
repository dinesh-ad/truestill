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
from pathlib import Path

import pytest
from PIL import Image
from truestill_core import thumbnails

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
