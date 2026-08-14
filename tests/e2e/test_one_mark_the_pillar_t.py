"""One mark everywhere: the pillar T. There is no TS in this product.

The TS monogram appeared in two places - the collapsed rail and the browser tab - and both are
now the geometric pillar T. `(abi)` closed with it: `build_brand_assets.py` generated every icon
from the Libre Caslon font, so the geometric mark was committed and reached nothing.

Two measured constraints shape how it appears:

* **The rail is dark**, and the mark's authored ramp measures 2.45:1 and 1.11:1 there - the foot
  is invisible. It is drawn flat in `--rail-accent` (9.17:1), which is the treatment the wordmark
  already got when the same gradient was rejected on the same ground.
* **The tab is small**, and the hairline flute is sub-pixel below ~61px. The 16 and 24 entries
  carry the flute-less variant.
"""

from __future__ import annotations

import re
import struct
from pathlib import Path

import pytest
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

    expect(ui.locator("svg[data-brand='pillar-t']")).to_be_visible()
    assert ui.locator("svg[data-brand='monogram']").count() == 0, "the TS monogram is still here"


def test_no_surface_a_person_reads_contains_a_ts_monogram() -> None:
    """Aimed at the shipped files, because 'nowhere' is not a thing a page can show."""
    markup = INDEX.read_text(encoding="utf-8")
    assert 'data-brand="monogram"' not in markup, "index.html still inlines the TS monogram"
    assert ">TS<" not in markup


def test_the_rail_mark_is_legible_on_the_rail_it_sits_on(ui: Page) -> None:
    """The authored ramp measures 1.11:1 here, so the mark is flat in a rail token instead."""
    ui.click("#sidebar-toggle")
    expect(ui.locator("#sidebar")).to_have_attribute("data-collapsed", "true")

    fill = ui.eval_on_selector(
        "svg[data-brand='pillar-t'] path",
        "el => getComputedStyle(el).fill",
    )
    numbers = [int(n) for n in re.findall(r"\d+", fill)[:3]]
    assert len(numbers) == 3, f"could not read the mark's fill: {fill!r}"

    ratio = _contrast((numbers[0], numbers[1], numbers[2]), RAIL_BG)
    assert ratio >= 4.5, f"the rail mark measures {ratio:.2f}:1 on #14161b - it is not legible"

    # A gradient here would reintroduce exactly what was rejected: a `url(#...)` fill cannot be
    # measured against the ground, and the low stop is 1.11:1.
    assert "url(" not in fill, "the mark is gradient-filled on the dark rail again"


def test_the_rail_mark_has_no_flute_at_rail_size() -> None:
    """It renders ~26px tall; the flute is sub-pixel below ~61px and reads as a smudge."""
    markup = INDEX.read_text(encoding="utf-8")
    flute_less = (BRAND / "pillar-t-geometric-noflute.svg").read_text(encoding="utf-8")
    expected = re.findall(r'\sd="(.*?)"', flute_less, re.S)
    assert expected, "no path data in the flute-less variant"
    for path in expected:
        assert " ".join(path.split()) in " ".join(markup.split()), (
            "the rail mark has drifted from brand/pillar-t-geometric-noflute.svg"
        )


# --------------------------------------------------------------------------- the tab


def test_the_favicon_is_generated_from_the_geometric_mark_not_from_a_font() -> None:
    """`(abi)`: the generator built every icon from the font, so the geometric T reached nothing."""
    script = (ROOT / "scripts/build_brand_assets.py").read_text(encoding="utf-8")
    assert "pillar-t-geometric" in script, "the generator does not read the geometric artwork"
    assert '"TS"' not in script, "the generator still rasterises a TS monogram"


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
