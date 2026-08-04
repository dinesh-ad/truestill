"""Build the Truestill brand marks from Libre Caslon Text.

One-shot authoring tool, not part of any gate. It is committed so the artwork in ``brand/`` is
re-derivable rather than being a binary someone has to trust.

**It needs two things this repo does not ship**: ``fonttools`` and ``pillow``, neither a runtime
dependency, and the Libre Caslon Text font file, which is not committed because the product
ships no font. Run it as::

    uv run --with fonttools --with pillow python scripts/build_brand_assets.py <path-to.ttf>

Licence position for what it produces: outlined glyphs are artwork, not Font Software, so the
output is not subject to the OFL. See ``brand/PROVENANCE.md`` for the clauses.
"""

from __future__ import annotations

import struct
import sys
from io import BytesIO
from pathlib import Path

from fontTools.misc.transform import Transform
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parents[1] / "brand"

#: Light ground uses the brand sheet's own gradient. Dark is AUTHORED, not filtered: the sheet's
#: low stop measures 1.81:1 on the dark rail, which is unusable.
GRADIENTS = {"light": ("#4C63C4", "#2A3B8C"), "dark": ("#A9B6F0", "#7D90E6")}

#: The T alone carries the sizes where an interlocked pair closes up.
TINY_SIZES = frozenset({16, 24})
PNG_SIZES = (16, 24, 32, 48, 64, 128, 256, 512, 1024)
ICO_SIZES = (16, 24, 32, 48, 64, 128, 256)

#: name, glyphs, tracking in em units per gap
MARKS = (("wordmark", "Truestill", 0.0), ("monogram", "TS", 0.012), ("pillar-t", "T", 0.0))


def outline(
    font: TTFont, text: str, tracking: float, height: float = 1000.0
) -> tuple[str, float, float]:
    """Outlined path data plus the tight ink box, y flipped into SVG's coordinate sense."""
    glyph_set = font.getGlyphSet()
    cmap = font.getBestCmap()
    upm = font["head"].unitsPerEm
    metrics = font["hmtx"]
    names = [cmap[ord(c)] for c in text]
    scale = height / upm

    advances: list[float] = []
    cursor = 0.0
    for index, name in enumerate(names):
        advances.append(cursor)
        cursor += metrics[name][0] + (tracking * upm if index < len(names) - 1 else 0.0)

    bounds = BoundsPen(glyph_set)
    for name, start in zip(names, advances, strict=True):
        glyph_set[name].draw(TransformPen(bounds, Transform(scale, 0, 0, -scale, start * scale, 0)))
    left, bottom, right, top = bounds.bounds

    pen = SVGPathPen(glyph_set, ntos=lambda v: f"{v:.2f}")
    for name, start in zip(names, advances, strict=True):
        placed = Transform(scale, 0, 0, -scale, start * scale - left, -bottom)
        glyph_set[name].draw(TransformPen(pen, placed))
    return pen.getCommands(), right - left, top - bottom


def svg_document(mark: str, path_data: str, width: float, height: float, variant: str) -> str:
    high, low = GRADIENTS[variant]
    gradient_id = f"tsg-{mark}-{variant}"
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width:.2f} {height:.2f}"\n'
        f'     role="img" aria-label="Truestill" focusable="false">\n'
        f"  <title>Truestill</title>\n"
        f"  <desc>Truestill {mark} ({variant}). Outlined from Libre Caslon Text (SIL OFL 1.1).\n"
        f"  Artwork is not subject to the OFL - see OFL condition 5 and OFL-FAQ 1.13.\n"
        f"  Provenance: brand/PROVENANCE.md</desc>\n"
        f"  <defs>\n"
        f'    <linearGradient id="{gradient_id}" x1="0" y1="0" x2="1" y2="0">\n'
        f'      <stop offset="0" stop-color="{high}"/>\n'
        f'      <stop offset="1" stop-color="{low}"/>\n'
        f"    </linearGradient>\n"
        f"  </defs>\n"
        f'  <path d="{path_data}" fill="url(#{gradient_id})"/>\n'
        f"</svg>\n"
    )


def gradient_image(width: int, height: int) -> Image.Image:
    high = (0x4C, 0x63, 0xC4)
    low = (0x2A, 0x3B, 0x8C)
    image = Image.new("RGB", (width, height))
    pixels = image.load()
    assert pixels is not None
    for x in range(width):
        ratio = x / max(width - 1, 1)
        colour = tuple(round(high[i] + (low[i] - high[i]) * ratio) for i in range(3))
        for y in range(height):
            pixels[x, y] = colour
    return image


def raster_mark(font_path: Path, text: str, size: int, supersample: int = 8) -> Image.Image:
    """A square transparent PNG with the mark centred on its ink box and gradient-filled."""
    canvas = size * supersample
    padding = int(canvas * 0.10)
    inner = canvas - 2 * padding

    low, high, chosen = 4, inner * 4, None
    while low <= high:
        middle = (low + high) // 2
        candidate = ImageFont.truetype(str(font_path), middle)
        box = candidate.getbbox(text)
        if (box[2] - box[0]) <= inner and (box[3] - box[1]) <= inner:
            chosen = (middle, box)
            low = middle + 1
        else:
            high = middle - 1
    assert chosen is not None, "no point size fits the canvas"
    point_size, box = chosen

    face = ImageFont.truetype(str(font_path), point_size)
    mask = Image.new("L", (canvas, canvas), 0)
    dx = padding + (inner - (box[2] - box[0])) // 2 - box[0]
    dy = padding + (inner - (box[3] - box[1])) // 2 - box[1]
    ImageDraw.Draw(mask).text((dx, dy), text, fill=255, font=face)

    out = Image.new("RGBA", (canvas, canvas), (0, 0, 0, 0))
    out.paste(gradient_image(canvas, canvas), (0, 0), mask)
    return out.resize((size, size), Image.Resampling.LANCZOS)


def write_ico(target: Path, frames: list[tuple[int, bytes]]) -> None:
    """Assemble the ICO by hand so each size keeps its OWN artwork.

    Pillow's ICO writer ignores ``append_images`` and downsamples a single image instead - which
    produced one 16x16 entry here, and would have discarded the point of the exercise: the tiny
    entries carry the pillar T rather than a shrunken TS.
    """
    header = struct.pack("<HHH", 0, 1, len(frames))
    offset = 6 + 16 * len(frames)
    entries, blob = b"", b""
    for size, data in frames:
        dimension = 0 if size == 256 else size
        entries += struct.pack("<BBBBHHII", dimension, dimension, 0, 0, 1, 32, len(data), offset)
        blob += data
        offset += len(data)
    target.write_bytes(header + entries + blob)


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2
    font_path = Path(argv[1])
    font = TTFont(font_path)

    for mark, text, tracking in MARKS:
        data, width, height = outline(font, text, tracking)
        for variant in GRADIENTS:
            (OUT / f"{mark}-{variant}.svg").write_text(
                svg_document(mark, data, width, height, variant)
            )
        print(f"{mark:9} viewBox 0 0 {width:.1f} {height:.1f}")

    icons = OUT / "icons"
    icons.mkdir(parents=True, exist_ok=True)
    for size in PNG_SIZES:
        art = "T" if size in TINY_SIZES else "TS"
        raster_mark(font_path, art, size).save(icons / f"truestill-{size}.png")
    raster_mark(font_path, "TS", 1024).save(OUT / "master-1024.png")

    frames = []
    for size in ICO_SIZES:
        buffer = BytesIO()
        Image.open(icons / f"truestill-{size}.png").save(buffer, format="PNG", optimize=True)
        frames.append((size, buffer.getvalue()))
    write_ico(OUT / "favicon.ico", frames)
    print(f"png {list(PNG_SIZES)} (16/24 = pillar T)\nico {list(ICO_SIZES)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
