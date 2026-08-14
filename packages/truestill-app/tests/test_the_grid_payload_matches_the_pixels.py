"""The shape the payload states is the shape the thumbnail actually is.

**The failure this exists to prevent is silent and affects a third of a real library.**
`thumbnails.render` applies `ImageOps.exif_transpose`, so a thumbnail's shape is the UPRIGHT one.
exiftool's `ImageWidth`/`ImageHeight` are the **stored** dimensions. On the **31.7% of a
4,108-photograph corpus** that carries a transposing orientation tag, those two describe different
rectangles - and a row solver laying out against the payload would compute every row from
dimensions the pixels contradict, producing gaps and overlaps that look like a CSS bug.

Nothing else would catch it. The payload is well-formed, the thumbnail is correct, and only their
*relationship* is wrong.

`thumbnails.upright_size` is the single rule both sides use, which is why this guard is about
drift rather than about arithmetic: it asserts the two callers still agree, not that the swap is
correct in isolation.
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any

import pytest
from PIL import Image
from truestill_app.service.organize import _tile_shape
from truestill_core import thumbnails

#: Stored 4000x3000 landscape with orientation 6: seen as 3000x4000 portrait. The single most
#: common shape in the corpus (1,152 of 4,108 files carry orientation 6).
_ROTATED = {"ImageWidth": 4000, "ImageHeight": 3000, "Orientation": 6}


def test_a_rotated_photograph_is_described_as_it_is_seen() -> None:
    """THE GUARD. Against a payload built from stored dimensions this returns 4000x3000."""
    source = Path("/library/IMG_0001.jpg")
    shape = _tile_shape({source: _ROTATED}, source)
    assert shape == {"w": 3000, "h": 4000}, (
        f"a photograph stored 4000x3000 with a transposing orientation tag is SEEN as 3000x4000; "
        f"the payload says {shape}. A row solver would lay out a portrait as a landscape."
    )


def test_an_unrotated_photograph_is_left_alone() -> None:
    """The cry-wolf half. A swap applied unconditionally satisfies the guard above and breaks the
    other 66.3% of the corpus."""
    source = Path("/library/IMG_0002.jpg")
    flat: dict[Path, dict[str, Any]] = {
        source: {"ImageWidth": 4000, "ImageHeight": 3000, "Orientation": 1}
    }
    assert _tile_shape(flat, source) == {"w": 4000, "h": 3000}


@pytest.mark.parametrize(
    ("tags", "why"),
    [
        ({}, "exiftool read nothing"),
        ({"ImageWidth": 4000}, "height missing"),
        ({"ImageWidth": 0, "ImageHeight": 3000}, "a zero dimension"),
        ({"ImageWidth": "wide", "ImageHeight": "tall"}, "non-numeric"),
    ],
)
def test_an_unreadable_shape_is_omitted_not_guessed(tags: dict[str, Any], why: str) -> None:
    """A layout can place an unknown shape honestly; it cannot recover from a confident wrong one.

    5 of 4,108 corpus files will not decode at all, and exiftool fails on more than that.
    """
    source = Path("/library/IMG_0003.jpg")
    assert _tile_shape({source: tags}, source) == {}, f"a shape was invented when {why}"


def test_the_payload_and_a_real_thumbnail_agree(tmp_path: Path) -> None:
    """End to end on real bytes: build a rotated JPEG, render it, compare the two shapes.

    The fixture is deliberately NON-SQUARE and rotated - a square would agree either way, and a
    landscape without a tag would agree even if the swap were deleted.
    """
    source = tmp_path / "rotated.jpg"
    image = Image.new("RGB", (400, 300), "white")
    exif = image.getexif()
    exif[274] = 6  # a quarter turn: seen as 300x400 portrait
    image.save(source, "JPEG", exif=exif)

    shape = _tile_shape({source: {"ImageWidth": 400, "ImageHeight": 300, "Orientation": 6}}, source)
    with Image.open(io.BytesIO(thumbnails.render(source))) as thumb:
        thumb_w, thumb_h = thumb.size

    assert shape, "no shape emitted for a readable photograph"
    payload_ratio = shape["w"] / shape["h"]
    thumb_ratio = thumb_w / thumb_h
    assert abs(payload_ratio - thumb_ratio) / thumb_ratio <= 0.02, (
        f"the payload says {shape['w']}x{shape['h']} (ratio {payload_ratio:.3f}) and the "
        f"thumbnail is {thumb_w}x{thumb_h} (ratio {thumb_ratio:.3f}). The row solver would lay "
        "out against dimensions the pixels contradict."
    )
