"""Build the Truestill icon set from the maintainer's mark, and the legacy marks from a font.

THE ICONS COME FROM ``brand/truestill-mark.svg`` - the same file the rail inlines - and need no
font at all. There is one mark in this product and it is the maintainer's T.

⚠ **RE-POINTED 2026-09-10, and the divergence it ended had shipped for weeks.** The icons were
built from ``brand/pillar-t-geometric*.svg`` - a fluted column serif on a BLUE tile - while the
rail carried the maintainer's rounded T on a rose-to-orange plate. Two unrelated marks, sharing
neither letterform nor a single colour, and every test green: both favicon tests tied the icon to
``brand/`` and nothing tied the icon to the rail. ``test_the_shipped_icon_is_a_current_render``
is the guard that closes it.

⚠ **THE FLUTE/NO-FLUTE SIZE SPLIT IS GONE, not left inert.** ``icon_source(size)`` chose a
variant per size because the pillar T's hairline flute is sub-pixel below 128px. The mark has no
flute, so the branch could never choose anything again; a dead branch that still reads as a
decision is worse than no branch. ``FLUTE_MIN_SIZE`` went with it.

⚠ **THE MARK IS DRAWN, NOT KNOCKED OUT, and that reverses an earlier decision on its own terms.**
The pillar T was knocked out of the tile because "a transparent mark in the light gradient
measures 1.61:1 on a dark browser tab" - the tile carried the contrast and the letterform showed
the host background through itself. The maintainer's mark carries its own: ``#161826`` measures
4.79:1 on the rose stop and 7.78:1 on the amber. Knocking it out would make the tab icon change
with the browser's theme while the rail's never does, which is precisely the "no surface on which
the two coexist" this file now has to hold.

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
import xml.etree.ElementTree as ET
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING

from PIL import Image, ImageDraw

if TYPE_CHECKING:  # fontTools is needed only for the orphaned Libre Caslon marks, so the
    from xml.etree.ElementTree import Element

    from fontTools.ttLib import TTFont  # real imports are deferred into `outline` and `main`.

OUT = Path(__file__).resolve().parents[1] / "brand"

#: Light ground uses the brand sheet's own gradient. Dark is AUTHORED, not filtered: the sheet's
#: low stop measures 1.81:1 on the dark rail, which is unusable.
#: ⚠ These belong to the ORPHANED Libre Caslon wordmark below, not to the icons - the icons take
#: the mark's own ramp, read from the artwork.
GRADIENTS = {"light": ("#4C63C4", "#2A3B8C"), "dark": ("#A9B6F0", "#7D90E6")}

#: The one mark, and the one place its name is written down.
MARK = "truestill-mark.svg"
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


# ⚠ THE POLYGON RASTERISER IS GONE, 2026-09-10 - `flatten_path` and `mark_mask`, about 110
# lines. They existed to turn the pillar T's bezier paths into an alpha mask, and their only
# consumers were `icon_source` and `raster_pillar_t`, both retired with the mark. The maintainer's
# artwork is rects, circles and one round-capped stroke, so it needs no bezier flattener at all.
# Deleted rather than kept: dead machinery still reads as a decision, which is the same reason
# the flute/no-flute branch went. `scripts/make_pillar_t.py` still generates the retired SVGs and
# does not use any of this.

#: A drawable, in viewBox units: ``(x0, y0, x1, y1, radius)``. Every shape in the mark reduces
#: to a rounded box - a circle is one with radius = half its side, and a straight stroke with a
#: round cap is one with radius = half the stroke width.
Box = tuple[float, float, float, float, float]


def _shapes(svg: str) -> tuple[list[Box], list[Box]]:
    """The mark's shapes and its knockouts, in viewBox units, with the group transform applied.

    ⚠ **READ FROM THE FILE, NEVER TRANSCRIBED.** Hand-copying these numbers into this script
    would make the icon a SECOND copy of the artwork - the exact defect being fixed, one level
    down: a copy agrees with its source until somebody edits one of them.

    Returns ``(draw, knockout)``. A knockout is a shape inside ``<mask>`` filled ``#000`` - the
    eyes - and is removed from the mark so the plate's ramp shows through it.
    """
    root = ET.fromstring(svg)
    namespace = "{http://www.w3.org/2000/svg}"
    draw: list[Box] = []
    knockout: list[Box] = []

    def placed(element: Element) -> tuple[float, float, float]:
        raw = element.get("transform", "")
        move = re.search(r"translate\(\s*(-?[\d.]+)[\s,]+(-?[\d.]+)\s*\)", raw)
        grow = re.search(r"scale\(\s*(-?[\d.]+)\s*\)", raw)
        dx, dy = (float(move[1]), float(move[2])) if move else (0.0, 0.0)
        return dx, dy, float(grow[1]) if grow else 1.0

    def box(element: Element, tag: str, at: tuple[float, float, float]) -> Box:
        dx, dy, scale = at
        get = element.get

        def number(name: str) -> float:
            return float(get(name, 0.0))

        if tag == "rect":
            x, y = number("x") * scale + dx, number("y") * scale + dy
            return (
                x,
                y,
                x + number("width") * scale,
                y + number("height") * scale,
                number("rx") * scale,
            )
        if tag == "circle":
            cx, cy = number("cx") * scale + dx, number("cy") * scale + dy
            r = number("r") * scale
            return (cx - r, cy - r, cx + r, cy + r, r)
        # A straight stroke with a round cap IS a stadium: the caps are semicircles of half the
        # stroke width, so the outline is a rounded box of that radius. Only this one path shape
        # is supported, and anything else RAISES rather than being silently dropped - the polygon
        # parser this replaces raised on an unknown command for exactly that reason.
        points = [float(n) for n in re.findall(r"-?[\d.]+", get("d", ""))]
        expected = 4
        if get("stroke-linecap") != "round" or len(points) != expected:
            message = f"unsupported path in the mark: {get('d')!r}"
            raise ValueError(message)
        half = number("stroke-width") / 2 * scale
        x1, y1, x2, y2 = points
        x1, y1 = x1 * scale + dx, y1 * scale + dy
        x2, y2 = x2 * scale + dx, y2 * scale + dy
        return (
            min(x1, x2) - half,
            min(y1, y2) - half,
            max(x1, x2) + half,
            max(y1, y2) + half,
            half,
        )

    def walk(node: Element, at: tuple[float, float, float], masked: bool) -> None:
        for child in node:
            tag = child.tag.removeprefix(namespace)
            if tag in {"defs", "mask"}:
                walk(child, at, masked or tag == "mask")
            elif tag == "g":
                dx, dy, scale = at
                cdx, cdy, cscale = placed(child)
                walk(child, (dx + cdx * scale, dy + cdy * scale, scale * cscale), masked)
            elif tag in {"rect", "circle", "path"}:
                # The mask's white backdrop rect means "show everything" - it is not a shape.
                if masked and child.get("fill") != "#000":
                    continue
                # ⚠ THE PLATE IS NOT PART OF THE MARK, and forgetting that painted the whole tile
                # in the mark's ink on the first render - a dark square with two rose eyes. The
                # plate is the one shape filled from the ramp (`fill="url(#...)"`); the mark is
                # everything drawn ON it. Identified by its fill rather than by being first or
                # being a rect, because both of those are accidents of how the file is written.
                if not masked and child.get("fill", "").startswith("url("):
                    continue
                (knockout if masked else draw).append(box(child, tag, at))

    walk(root, (0.0, 0.0, 1.0), False)
    if not draw:
        message = "no shapes found in the mark"
        raise ValueError(message)
    return draw, knockout


def _ramp(svg: str) -> tuple[tuple[int, ...], tuple[int, ...]]:
    """The plate's two gradient stops, read from the artwork rather than restated here."""
    stops = re.findall(r'stop-color="#([0-9a-fA-F]{6})"', svg)
    if len(stops) != 2:
        message = f"the mark declares {len(stops)} gradient stops, expected 2"
        raise ValueError(message)
    first, second = (tuple(int(v[i : i + 2], 16) for i in (0, 2, 4)) for v in stops)
    return first, second


def diagonal_gradient(size: int, low: tuple[int, ...], high: tuple[int, ...]) -> Image.Image:
    """Corner to corner, which is what the artwork's ``x1=0 y1=0 x2=100 y2=100`` says.

    ⚠ **Built small and resized, not looped per pixel.** The first version wrote every pixel in
    Python; the icons rasterise at 8x supersample, so the 1024px master alone is a 8192x8192
    canvas - 67 million writes, and the build did not finish. A linear ramp is exactly
    reproducible under bilinear resampling, so a 64px original carries the same gradient at any
    size for a fraction of the cost.
    """
    seed = 64
    small = Image.new("RGB", (seed, seed))
    pixels = small.load()
    assert pixels is not None
    span = max(2 * (seed - 1), 1)
    for x in range(seed):
        for y in range(seed):
            t = (x + y) / span
            pixels[x, y] = tuple(round(low[i] + (high[i] - low[i]) * t) for i in range(3))
    return small.resize((size, size), Image.Resampling.BILINEAR)


def raster_mark(size: int, supersample: int = 8) -> Image.Image:
    """The plate with the mark drawn on it, both read from `brand/truestill-mark.svg`.

    Every number comes from the artwork: the viewBox, the corner radius, the ramp's two stops and
    the mark's own colour. Nothing about the mark is written down twice.
    """
    svg = (OUT / MARK).read_text(encoding="utf-8")
    box = re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', svg)
    if not box:
        message = "the mark declares no viewBox"
        raise ValueError(message)
    units = float(box[1])

    canvas = size * supersample
    scale = canvas / units
    plate = re.search(r'<rect[^>]*rx="([\d.]+)"[^>]*fill="url\(#[^)]+\)"', svg)
    radius = float(plate[1]) * scale if plate else canvas * 0.22
    colour = re.search(r'fill="#([0-9a-fA-F]{6})"', svg[svg.index("<g mask=") :])
    ink = tuple(int(colour[1][i : i + 2], 16) for i in (0, 2, 4)) if colour else (0, 0, 0)

    low, high = _ramp(svg)
    tile = Image.new("RGBA", (canvas, canvas), (0, 0, 0, 0))
    shape = Image.new("L", (canvas, canvas), 0)
    ImageDraw.Draw(shape).rounded_rectangle(
        (0, 0, canvas - 1, canvas - 1), radius=int(radius), fill=255
    )
    tile.paste(diagonal_gradient(canvas, low, high), (0, 0), shape)

    draw, knockout = _shapes(svg)
    mark = Image.new("L", (canvas, canvas), 0)
    pen = ImageDraw.Draw(mark)
    for x0, y0, x1, y1, r in draw:
        pen.rounded_rectangle(
            (x0 * scale, y0 * scale, x1 * scale, y1 * scale), radius=int(r * scale), fill=255
        )
    for x0, y0, x1, y1, r in knockout:
        pen.rounded_rectangle(
            (x0 * scale, y0 * scale, x1 * scale, y1 * scale), radius=int(r * scale), fill=0
        )
    tile.paste(Image.new("RGBA", (canvas, canvas), (*ink, 255)), (0, 0), mark)
    return tile.resize((size, size), Image.Resampling.LANCZOS)


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
        raster_mark(size).save(icons / f"truestill-{size}.png")
    raster_mark(1024).save(OUT / "master-1024.png")

    frames = []
    for size in ICO_SIZES:
        buffer = BytesIO()
        Image.open(icons / f"truestill-{size}.png").save(buffer, format="PNG", optimize=True)
        frames.append((size, buffer.getvalue()))
    write_ico(OUT / "favicon.ico", frames)
    print(f"png {list(PNG_SIZES)}\nico {list(ICO_SIZES)}  all from brand/{MARK}")

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
