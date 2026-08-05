"""Build the Truestill icon set from the geometric pillar T, and the legacy marks from a font.

THE ICONS COME FROM ``brand/pillar-t-geometric*.svg`` and need no font at all. There is one
mark in this product and it is the pillar T; the TS monogram is gone from the rail and the tab.
Below 128px the flute is sub-pixel, so those sizes take the ``-noflute`` variant.

One-shot authoring tool, not part of any gate. It is committed so the artwork in ``brand/`` is
re-derivable rather than being a binary someone has to trust.

``pillow`` is needed either way; ``fonttools`` and the font only for the legacy marks. Run::

    uv run --with pillow python scripts/build_brand_assets.py                    # icons only
    uv run --with fonttools --with pillow python scripts/build_brand_assets.py <path-to.ttf>

The second form also rewrites the Libre Caslon SVGs, which are ORPHANED - kept as a record and
for a possible website header, consumed by nothing.

Licence position for what it produces: outlined glyphs are artwork, not Font Software, so the
output is not subject to the OFL. See ``brand/PROVENANCE.md`` for the clauses.
"""

from __future__ import annotations

import re
import struct
import sys
from io import BytesIO
from itertools import pairwise
from pathlib import Path
from typing import TYPE_CHECKING

from PIL import Image, ImageChops, ImageDraw

if TYPE_CHECKING:  # fontTools is needed only for the orphaned Libre Caslon marks, so the
    from fontTools.ttLib import TTFont  # real imports are deferred into `outline` and `main`.

OUT = Path(__file__).resolve().parents[1] / "brand"

#: Light ground uses the brand sheet's own gradient. Dark is AUTHORED, not filtered: the sheet's
#: low stop measures 1.81:1 on the dark rail, which is unusable.
GRADIENTS = {"light": ("#4C63C4", "#2A3B8C"), "dark": ("#A9B6F0", "#7D90E6")}

#: Below this the hairline flute is sub-pixel and renders as a grey smudge; measured across
#: 16-128px, it only reaches paper white at 128. Same threshold `brand/PROVENANCE.md` records.
FLUTE_MIN_SIZE = 128
PNG_SIZES = (16, 24, 32, 48, 64, 128, 256, 512, 1024)
ICO_SIZES = (16, 24, 32, 48, 64, 128, 256)

#: name, glyphs, tracking in em units per gap.
#: The monogram and the Libre Caslon T are GONE, not merely unused: there is one mark in this
#: product and it is the geometric pillar T. Only the wordmark is still derived from the font,
#: and only because a website header may still want a set wordmark - it has no consumer today.
MARKS = (("wordmark", "Truestill", 0.0),)


def outline(
    font: TTFont, text: str, tracking: float, height: float = 1000.0
) -> tuple[str, float, float]:
    """Outlined path data plus the tight ink box, y flipped into SVG's coordinate sense."""
    # Deferred: the icons need no font, and requiring fontTools to build them would put the
    # dependency back that this whole change removed.
    from fontTools.misc.transform import Transform  # noqa: PLC0415
    from fontTools.pens.boundsPen import BoundsPen  # noqa: PLC0415
    from fontTools.pens.svgPathPen import SVGPathPen  # noqa: PLC0415
    from fontTools.pens.transformPen import TransformPen  # noqa: PLC0415

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


def rounded_tile(size: int, radius_ratio: float = 0.22) -> Image.Image:
    """An opaque gradient tile with rounded corners - the ground the mark is knocked out of."""
    tile = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, size - 1, size - 1), radius=int(size * radius_ratio), fill=255
    )
    tile.paste(gradient_image(size, size), (0, 0), mask)
    return tile


#: Absolute M L H V Q C Z is the whole vocabulary `make_pillar_t.py` emits. A parser that
#: silently ignored a command it did not know would produce a subtly wrong mark, so unknown
#: commands raise rather than being skipped.
_PATH_TOKENS = re.compile(r"([A-Za-z])|(-?\d+(?:\.\d+)?)")


def flatten_path(  # noqa: PLR0915 - one dispatch table; splitting it hides the vocabulary
    data: str, steps: int = 48
) -> list[list[tuple[float, float]]]:
    """SVG path data to closed polygons, Beziers sampled at ``steps`` per segment."""

    def bezier(
        start: tuple[float, float], points: list[tuple[float, float]]
    ) -> list[tuple[float, float]]:
        out = []
        for index in range(1, steps + 1):
            t = index / steps
            control = [start, *points]
            while len(control) > 1:
                control = [
                    (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
                    for a, b in pairwise(control)
                ]
            out.append(control[0])
        return out

    tokens = [command or number for command, number in _PATH_TOKENS.findall(data)]
    polygons: list[list[tuple[float, float]]] = []
    current: list[tuple[float, float]] = []
    position = start = (0.0, 0.0)
    index = 0
    command = ""

    def number() -> float:
        nonlocal index
        value = float(tokens[index])
        index += 1
        return value

    while index < len(tokens):
        if tokens[index].isalpha():
            command = tokens[index]
            index += 1
            if command == "Z":
                if current:
                    polygons.append(current)
                    current = []
                position = start
                continue
        if command == "M":
            position = (number(), number())
            start = position
            current = [position]
        elif command == "L":
            position = (number(), number())
            current.append(position)
        elif command == "H":
            position = (number(), position[1])
            current.append(position)
        elif command == "V":
            position = (position[0], number())
            current.append(position)
        elif command == "Q":
            control = (number(), number())
            end = (number(), number())
            current += bezier(position, [control, end])
            position = end
        elif command == "C":
            first = (number(), number())
            second = (number(), number())
            end = (number(), number())
            current += bezier(position, [first, second, end])
            position = end
        else:
            message = f"unsupported path command {command!r}"
            raise ValueError(message)
    if current:
        polygons.append(current)
    return polygons


def mark_mask(svg_path: Path, canvas: int, padding_fraction: float = 0.10) -> Image.Image:
    """An alpha mask of the mark, centred on its own INK box rather than on its viewBox.

    The viewBox is taller and wider than the drawing, so centring on it would leave the mark
    high and small inside the tile - the same mistake as sizing a glyph by its em square.
    """
    svg = svg_path.read_text(encoding="utf-8")
    # `(?<![a-zA-Z])` or the `d` of `id="..."` matches and every path becomes its own id.
    # Grouped per <path>, because even-odd is resolved within one element, not across the file.
    elements = [flatten_path(data) for data in re.findall(r'(?<![a-zA-Z])d="(.*?)"', svg, re.S)]
    polygons = [polygon for element in elements for polygon in element]
    if not polygons:
        message = f"no path data in {svg_path}"
        raise ValueError(message)

    xs = [x for polygon in polygons for x, _ in polygon]
    ys = [y for polygon in polygons for _, y in polygon]
    ink_width, ink_height = max(xs) - min(xs), max(ys) - min(ys)

    padding = int(canvas * padding_fraction)
    inner = canvas - 2 * padding
    scale = min(inner / ink_width, inner / ink_height)
    offset_x = padding + (inner - ink_width * scale) / 2 - min(xs) * scale
    offset_y = padding + (inner - ink_height * scale) / 2 - min(ys) * scale

    mask = Image.new("L", (canvas, canvas), 0)
    for element in elements:
        # EVEN-ODD, per subpath. The flute is a cutout inside the body: filling it like any
        # other polygon welds it into the stem, which is how the 128px icon first shipped with
        # no flute. Each path element is resolved on its own, then OR-ed into the whole.
        layer = Image.new("L", (canvas, canvas), 0)
        piece = Image.new("L", (canvas, canvas), 0)
        for polygon in element:
            piece.paste(0, (0, 0, canvas, canvas))
            ImageDraw.Draw(piece).polygon(
                [(x * scale + offset_x, y * scale + offset_y) for x, y in polygon], fill=255
            )
            layer = ImageChops.difference(layer, piece)
        mask = ImageChops.lighter(mask, layer)
    return mask


def icon_source(size: int) -> Path:
    """Which variant a given size takes. Below 128 the flute cannot survive."""
    name = "pillar-t-geometric.svg" if size >= FLUTE_MIN_SIZE else "pillar-t-geometric-noflute.svg"
    return OUT / name


def raster_pillar_t(size: int, supersample: int = 8) -> Image.Image:
    """The tile with the pillar T knocked out of it.

    Knockout rather than a filled glyph: a transparent mark in the light gradient measures
    1.61:1 on a dark browser tab. The tile carries the contrast and the letterform shows the
    host background through itself, so one asset reads on light chrome and dark.
    """
    canvas = size * supersample
    mask = mark_mask(icon_source(size), canvas)
    out = rounded_tile(canvas)
    out.paste(Image.new("RGBA", (canvas, canvas), (0, 0, 0, 0)), (0, 0), mask)
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
    """Icons always; the orphaned Libre Caslon SVGs only when a font is supplied."""
    if len(argv) > 2:
        print(__doc__)
        return 2

    icons = OUT / "icons"
    icons.mkdir(parents=True, exist_ok=True)
    for size in PNG_SIZES:
        raster_pillar_t(size).save(icons / f"truestill-{size}.png")
    raster_pillar_t(1024).save(OUT / "master-1024.png")

    frames = []
    for size in ICO_SIZES:
        buffer = BytesIO()
        Image.open(icons / f"truestill-{size}.png").save(buffer, format="PNG", optimize=True)
        frames.append((size, buffer.getvalue()))
    write_ico(OUT / "favicon.ico", frames)
    fluted = [s for s in ICO_SIZES if s >= FLUTE_MIN_SIZE]
    print(f"png {list(PNG_SIZES)}\nico {list(ICO_SIZES)}  fluted at {fluted}, flute-less below")

    if len(argv) == 2:
        from fontTools.ttLib import TTFont  # noqa: PLC0415 - see `outline`

        font_path = Path(argv[1])
        font = TTFont(font_path)
        for mark, text, tracking in MARKS:
            data, width, height = outline(font, text, tracking)
            for variant in GRADIENTS:
                (OUT / f"{mark}-{variant}.svg").write_text(
                    svg_document(mark, data, width, height, variant)
                )
            print(f"{mark:9} viewBox 0 0 {width:.1f} {height:.1f}  (ORPHANED - no consumer)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
