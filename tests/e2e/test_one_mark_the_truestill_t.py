"""One mark everywhere: the pillar T. There is no TS in this product.

The TS monogram appeared in two places - the collapsed rail and the browser tab - and both are
now the geometric pillar T. `(abi)` closed with it: `build_brand_assets.py` generated every icon
from the Libre Caslon font, so the geometric mark was committed and reached nothing.

Two measured constraints shape how it appears:

* **The rail is dark**, and the mark's authored ramp measures 2.45:1 and 1.11:1 directly on it -
  the foot is invisible. That is why the rail carries the PLATE (`brand/truestill-mark.svg`): the
  letter is knocked out of a square the ramp fills, so the artwork brings its own ground and the
  rail's colour stops being an input. The wordmark beside it still takes the flat treatment, which
  is the same gradient rejected on the same ground.
* **The tab is small**, and the hairline flute is sub-pixel below ~61px. The 16 and 24 entries
  carry the flute-less variant.
"""

from __future__ import annotations

import importlib.util
import io
import re
import struct
import sys
from pathlib import Path

import pytest
from PIL import Image, ImageChops
from playwright.sync_api import Page, expect

#: THE MIGRATION'S EARLY-WARNING SYSTEM. This file belongs to no screen, so no screen's commit
#: carries it - and an island landing on a DIFFERENT screen changes the DOM around it without
#: touching a line here. `make e2e-shell` runs the set after every island; see
#: `docs/react-migration-plan.md`.
pytestmark = pytest.mark.shell

ROOT = Path(__file__).resolve().parents[2]
BRAND = ROOT / "brand"
STATIC = ROOT / "packages/truestill-app/src/truestill_app/static"
INDEX = ROOT / "packages/truestill-app/src/truestill_app/templates/index.html"

RAIL_BG = (0x14, 0x16, 0x1B)


def _relative_luminance(rgb: tuple[int, int, int]) -> float:
    channels = []
    for value in rgb:
        srgb = value / 255
        channels.append(srgb / 12.92 if srgb <= 0.04045 else ((srgb + 0.055) / 1.055) ** 2.4)
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def _contrast(a: tuple[int, int, int], b: tuple[int, int, int]) -> float:
    high, low = sorted((_relative_luminance(a), _relative_luminance(b)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def _hex_to_rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return (int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16))


# --------------------------------------------------------------------------- the rail


def test_the_collapsed_rail_shows_the_pillar_t_and_no_monogram(ui: Page) -> None:
    ui.click("#sidebar-toggle")
    expect(ui.locator("#sidebar")).to_have_attribute("data-collapsed", "true")

    expect(ui.locator("svg[data-brand='truestill-t']")).to_be_visible()
    assert ui.locator("svg[data-brand='monogram']").count() == 0, "the TS monogram is still here"


def test_no_surface_a_person_reads_contains_a_ts_monogram() -> None:
    """Aimed at the shipped files, because 'nowhere' is not a thing a page can show."""
    markup = INDEX.read_text(encoding="utf-8")
    assert 'data-brand="monogram"' not in markup, "index.html still inlines the TS monogram"
    assert ">TS<" not in markup


def test_the_rail_mark_carries_its_own_contrast(ui: Page) -> None:
    """The mark is legible **without depending on the rail behind it**.

    ⚠ **Re-expected 2026-09-10, and THE MEASURED PAIR INVERTED.** The floor is unchanged at 4.5:1
    and the property is unchanged - the artwork brings its own ground - but which two colours make
    that pair is now the other way round. The previous plate was a dark ground with the ramp
    knocked through it, so the pair was RAMP against GROUND. The maintainer's artwork fills the
    plate with the ramp and paints the letter on it in `#161826`, so the pair is MARK against
    RAMP: 4.79:1 on the rose stop and 7.78:1 on the amber.

    Both stops are measured because a ramp is only as legible as its worst end, and the rose end
    is the near one - 4.79:1 has 0.29 of headroom, so a darker rose would fail here rather than
    silently ship.

    ⚠ **He supplied a second arrangement and it is deliberately not the one on the rail.** The
    same file offers a dark `#161826` plate with a ramp-filled mark, captioned as suiting a dark
    rail. Measured against this rail's own `#161014` (`D20`), that plate is **1.07:1** - its edge is
    invisible, so the mark would read as the floating gradient T that was rejected on 2026-09-06
    for looking like a red letter beside the word rather than a brand. This test asserts the
    arrangement that shipped; the other is one `fill` attribute away if he ever wants it.
    """
    ui.click("#sidebar-toggle")
    expect(ui.locator("#sidebar")).to_have_attribute("data-collapsed", "true")

    mark, ramp = ui.eval_on_selector(
        "svg[data-brand='truestill-t']",
        "el => { const plate = el.querySelector(':scope > rect');"
        " const ref = (getComputedStyle(plate).fill.match(/#([\\w-]+)/) || [])[1];"
        " const stops = [...el.querySelectorAll('#' + ref + ' stop')]"
        "   .map(e => getComputedStyle(e).stopColor);"
        " const letter = el.querySelector('g[mask] rect');"
        " return [getComputedStyle(letter).fill, stops]; }",
    )
    letter = tuple(int(n) for n in re.findall(r"\d+", mark)[:3])
    assert len(letter) == 3, f"could not read the mark's colour: {mark!r}"
    assert len(ramp) >= 2, "the plate's ramp declares no stops"

    for stop in ramp:
        colour = tuple(int(n) for n in re.findall(r"\d+", stop)[:3])
        ratio = _contrast(letter, colour)
        assert ratio >= 4.5, (
            f"the mark {letter} measures {ratio:.2f}:1 on a stop of its own plate {colour} - "
            "the letter is not legible against the ground the artwork brings with it"
        )


def test_the_rail_mark_has_no_flute_at_rail_size() -> None:
    """It renders ~30px tall; the hairline flute is sub-pixel below ~61px and reads as a smudge.

    ⚠ **Re-expected 2026-09-10, and this test had been passing for a reason that no longer
    exists.** It asserted that the flute-LESS geometric variant's path data appears in
    `index.html` - true only because the plate then in the rail was a reconstruction that reused
    exactly that geometry. The maintainer's own artwork is a different letterform entirely (a
    stroked crossbar, a rounded stem, two shoulders), so that assertion had lost its subject and
    would have failed for the right reason on the wrong grounds.

    The PROPERTY it exists for is unchanged and still worth holding: whatever is inlined at rail
    size must not carry the hairline flute. So the check is now the direct one - the FLUTED
    variant's geometry must appear nowhere in the rail's markup. That is what would go wrong if
    someone re-pointed the rail at `pillar-t-geometric.svg`, and it is checkable without knowing
    which artwork the rail carries.
    """
    markup = " ".join(INDEX.read_text(encoding="utf-8").split())
    fluted = (BRAND / "pillar-t-geometric.svg").read_text(encoding="utf-8")
    noflute = (BRAND / "pillar-t-geometric-noflute.svg").read_text(encoding="utf-8")

    only_fluted = {" ".join(d.split()) for d in re.findall(r'\sd="(.*?)"', fluted, re.S)} - {
        " ".join(d.split()) for d in re.findall(r'\sd="(.*?)"', noflute, re.S)
    }
    # Anti-vacuity: if the two variants ever stop differing, this test can never fail and the
    # smudge it guards against would ship unnoticed.
    assert only_fluted, (
        "the fluted and flute-less variants carry identical path data, so this test cannot "
        "distinguish them and is asserting nothing"
    )

    for path in only_fluted:
        assert path not in markup, (
            "the rail inlines the FLUTED geometric mark - the flute is sub-pixel at rail size "
            "and reads as a smudge"
        )


# --------------------------------------------------------------------------- the tab


def _brand_generator():
    """The icon generator, loaded from source - it is a one-shot tool, not an importable package."""
    spec = importlib.util.spec_from_file_location(
        "build_brand_assets", ROOT / "scripts" / "build_brand_assets.py"
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["build_brand_assets"] = module
    spec.loader.exec_module(module)
    return module


def test_the_favicon_is_generated_from_the_mark_not_from_a_font() -> None:
    """`(abi)`: the generator built every icon from the font, so the committed T reached nothing.

    ⚠ **Re-pointed 2026-09-10.** This asserted `"pillar-t-geometric" in script` - that the icons
    come from the RETIRED mark, which is the divergence rather than a guard against it.
    """
    script = (ROOT / "scripts/build_brand_assets.py").read_text(encoding="utf-8")
    assert "truestill-mark.svg" in script, "the generator does not read the one mark"
    assert '"TS"' not in script, "the generator still rasterises a TS monogram"


def test_the_shipped_icon_is_a_current_render_of_the_mark_the_rail_shows(ui: Page) -> None:
    """⚠ **THE GUARD THAT WOULD HAVE CAUGHT TWO MARKS SHIPPING FOR WEEKS.**

    Both favicon tests tied the icon to `brand/` and the artwork test tied the rail to `brand/` -
    but to *different files in it*, so the tab carried a fluted column serif on a blue tile while
    the rail carried the maintainer's rounded T on a rose plate, and every test was green. The
    icon was dated 2026-08-05 and the artwork had moved underneath it.

    Nothing here reads a filename. The icon is re-rendered from whatever source the RAIL is
    proved against, and compared to what actually ships - so re-pointing either one, or leaving
    the icon stale after the artwork changes, fails.

    Compared as PIXELS at 128px, downsampled to 32 to stay clear of resampling noise: the
    question is "is this the same mark", not "is this the same file", and a build-tool change
    that produced the same artwork by another route should not fail.
    """
    served = ui.request.get(f"{ui.url.split('?')[0].rstrip('/')}/static/favicon.ico")
    assert served.ok, "the favicon does not serve"

    generator = _brand_generator()
    fresh = generator.raster_mark(128).convert("RGB")

    blob = served.body()
    count = struct.unpack("<H", blob[4:6])[0]
    entries = {}
    for index in range(count):
        at = 6 + 16 * index
        width = blob[at] or 256
        length, offset = struct.unpack("<II", blob[at + 8 : at + 16])
        entries[width] = blob[offset : offset + length]
    assert 128 in entries, f"the shipped ICO has no 128px entry to compare: {sorted(entries)}"

    shipped = Image.open(io.BytesIO(entries[128])).convert("RGB")
    small = (32, 32)
    a = fresh.resize(small, Image.Resampling.LANCZOS)
    b = shipped.resize(small, Image.Resampling.LANCZOS)
    # `get_flattened_data`, not `getdata`: the latter is deprecated in Pillow 14 and this suite
    # turns warnings into errors.
    # Through `ImageChops`, PIL's own per-channel difference: the hand-rolled zip over pixel data
    # used `getdata`, which Pillow 14 deprecates and this suite turns into an error.
    worst = max(high for _low, high in ImageChops.difference(a, b).getextrema())
    assert worst <= 12, (
        f"the shipped icon is not a current render of the mark the rail shows (worst channel "
        f"difference {worst}/255). Re-run `uv run --with pillow python "
        f"scripts/build_brand_assets.py` and copy brand/favicon.ico into static/."
    )


def test_the_ico_still_carries_every_size_it_did_before() -> None:
    """The mark changed; the container must not lose entries while nobody is looking."""
    blob = (BRAND / "favicon.ico").read_bytes()
    assert blob[:4] == b"\x00\x00\x01\x00", "not an ICO"
    count = struct.unpack("<H", blob[4:6])[0]
    assert count == 7, f"the ICO carries {count} sizes, expected 7"

    sizes = []
    for index in range(count):
        entry = 6 + 16 * index
        width = blob[entry] or 256
        sizes.append(width)
    assert sorted(sizes) == [16, 24, 32, 48, 64, 128, 256]


def test_the_served_favicon_is_the_committed_one(ui: Page) -> None:
    base = ui.url.split("?")[0].rstrip("/")
    response = ui.request.get(f"{base}/static/favicon.ico")
    assert response.ok
    assert response.body() == (BRAND / "favicon.ico").read_bytes(), (
        "the served favicon has drifted from brand/favicon.ico"
    )
