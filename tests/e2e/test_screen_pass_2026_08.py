"""The maintainer's pass over all seven screens: the panel, the debug string, dark mode, density.

Each of these was visible on screen and invisible to every gate, which is the same shape as the
mangled-dash sweep that produced `test_user_facing_copy.py`: nothing we run reads a rendered
page for *composition*, only for words.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from playwright.sync_api import Page, expect

ROOT = Path(__file__).resolve().parents[2]
STATS = ROOT / "packages/truestill-app/src/truestill_app/service/stats.py"


def _lin(c: float) -> float:
    s = c / 255
    return s / 12.92 if s <= 0.04045 else ((s + 0.055) / 1.055) ** 2.4


def _luminance(value: str) -> float:
    parts = [
        int(n) for n in value.replace("rgba", "rgb").split("(")[1].split(")")[0].split(",")[:3]
    ]
    return 0.2126 * _lin(parts[0]) + 0.7152 * _lin(parts[1]) + 0.0722 * _lin(parts[2])


def _contrast(a: str, b: str) -> float:
    high, low = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def _with_library(ui: Page, **overrides: Any) -> None:
    base: dict[str, Any] = {
        "files": 1997,
        "photos": 1997,
        "videos": 0,
        "audio": 0,
        "bytes": 5_298_094_843,
        "by_format": {"photos": {"jpg": 1996}},
        "places": 2,
        "single_copy": 1836,
        "files_no_copy": 0,
        "files_one_copy": 1836,
        "redundancy_floor": 1,
        "files_on_a_drive": 1997,
        "held_floor": 1,
        "library_path": "/media/A",
        "backup_path": "/media/B",
        "drives": [],
        "custody": {},
        "catalog_path": "/tmp/c.sqlite",
        "catalog_presence": "ready",
        "catalog_detail": "",
        "catalog_tone": "info",
    }
    base.update(overrides)
    ui.route(
        "**/api/library/status",
        lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps(base)),
    )
    ui.set_viewport_size({"width": 1920, "height": 1080})
    ui.reload()
    ui.wait_for_selector(".nav-item")
    ui.wait_for_timeout(500)


# ------------------------------------------------------------------ 1. the debug string


def test_no_engineering_annotation_reaches_the_screen(ui: Page) -> None:
    """Stats rendered "Query cost: O(n) aggregate SQL over catalog tables; grouped rollups
    only.." where a description belongs - with a double full stop, because the payload value
    already ended in one and the template added another."""
    ui.route(
        "**/api/library/stats**",
        lambda r: r.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps({"safety": {"total_files": 0}, "completeness": {}, "shape": {}}),
        ),
    )
    ui.click('.nav-item[data-screen="stats"]')
    ui.wait_for_timeout(600)

    text = ui.eval_on_selector("#screen-stats", "el => el.innerText")
    for leak in ("Query cost", "O(n)", "aggregate SQL", "rollup"):
        assert leak not in text, f"engineering prose on screen: {leak!r}"


def test_the_payload_no_longer_carries_a_cost_annotation() -> None:
    """The render site is not the only place to close this: a key that exists invites a second
    reader. Checked at the source, because an empty payload proves nothing about the shape."""
    body = STATS.read_text("utf-8")
    assert '"complexity"' not in body, "the stats payload still ships a cost annotation"


def test_no_service_payload_ships_engineering_prose() -> None:
    """THE CLASS, not the instance. One annotation reached a user-facing slot; this fails if
    another is added anywhere in the service layer, so it cannot happen twice quietly."""
    markers = re.compile(r"O\(n|O\(1|aggregate SQL|grouped rollup|index scan|query plan|per-row")
    offenders = []
    for path in (ROOT / "packages/truestill-app/src/truestill_app/service").glob("*.py"):
        source = path.read_text("utf-8")
        # Only VALUES in a returned dict literal - docstrings and comments are where this
        # prose belongs and must stay allowed.
        for match in re.finditer(r'^\s*"[\w_]+":\s*"([^"]{10,})",?\s*$', source, re.M):
            if markers.search(match.group(1)):
                offenders.append(f"{path.name}: {match.group(1)[:60]}")
    assert not offenders, "engineering prose in a payload value:\n  " + "\n  ".join(offenders)


# ------------------------------------------------------------- 2 & 3. the panel is a card


def test_the_panel_is_a_card_like_every_other_region(ui: Page) -> None:
    """It was a full-height white slab: no border, no radius, no card padding - text floating
    against the page while every other region sat in a container."""
    _with_library(ui)
    expect(ui.locator("#panel")).to_be_visible()

    style = ui.evaluate(
        "() => { const p = document.querySelector('#panel > *') || document.querySelector('#panel');"
        " const s = getComputedStyle(p);"
        " return { radius: parseFloat(s.borderTopLeftRadius), bw: parseFloat(s.borderTopWidth),"
        "   bg: s.backgroundColor, pad: parseFloat(s.paddingTop) }; }"
    )
    assert style["radius"] > 0, "the panel has square corners; every other region is rounded"
    assert style["bw"] > 0, "the panel has no border"
    assert style["pad"] > 0, "the panel has no padding of its own"


def test_the_panel_starts_level_with_the_first_content_card(ui: Page) -> None:
    """It began at the grid row, 178px above the card beside it - `--space-7` of `.main` padding
    plus the screen header - so the right column read as detached from the middle one."""
    _with_library(ui)
    ui.evaluate("() => document.querySelector('.main').scrollTo(0, 0)")
    ui.wait_for_timeout(200)

    tops = ui.evaluate(
        "() => { const p = document.querySelector('#panel > *') || document.querySelector('#panel');"
        " const c = document.querySelector('.screen.active .card');"
        " return [Math.round(p.getBoundingClientRect().top),"
        "         Math.round(c.getBoundingClientRect().top)]; }"
    )
    assert abs(tops[0] - tops[1]) <= 8, f"panel top {tops[0]} vs first card top {tops[1]}"


# ------------------------------------------------------- 7. one fact, stated once


def test_the_one_place_count_is_not_stated_twice_at_once(ui: Page) -> None:
    """1,836 appeared in the rail AND in the panel, simultaneously, in different words. The RAIL
    keeps it: it is the ambient custody line and it is on every screen, while the panel is absent
    below 1336px - so the panel is the copy that can vanish without losing the fact."""
    _with_library(ui)

    rail = ui.eval_on_selector("#custody", "el => el.innerText")
    panel = ui.eval_on_selector("#panel", "el => el.innerText")

    assert "1,836" in rail, f"the rail stopped stating it: {rail!r}"
    assert "1,836" not in panel, f"the panel still repeats the rail's number: {panel!r}"


def test_the_panel_still_says_what_only_it_says(ui: Page) -> None:
    """CRY-WOLF HALF. Dropping the duplicated row must not empty the panel of its own facts.

    **This assertion changed with `(acq)` Stage A, and it was asserting the defect.** It read
    `"2" in panel`, which matched the `places` count - and this fixture is precisely the shape
    `(acq)` is about: two drives, but 1,836 of 1,997 files on one of them, so `held_floor` is 1.
    The panel now reads "1 place" and the old assertion failed on the *correct* output.

    Stronger, not merely different: it names the row and its value instead of substring-matching
    a lone digit that any number on the panel could have satisfied.
    """
    _with_library(ui)
    panel = ui.eval_on_selector("#panel", "el => el.innerText")

    assert "1,997" in panel, panel
    assert "GB" in panel, panel
    assert "In at least" in panel, panel
    assert "1 place" in panel, panel


# --------------------------------------------------------- 8. Backups' conditional block


def _backups(ui: Page, drives: list[dict[str, Any]]) -> str:
    # `/api/drives` is the list Backups renders from; `/api/library/status` only feeds the
    # total. Stubbing one and not the other left the screen on its no-drives empty state,
    # whose copy contains the words this test looks for - a fixture defect, not a product one.
    ui.route(
        "**/api/drives",
        lambda r: r.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps({"drives": drives, "at_risk": []}),
        ),
    )
    _with_library(ui, drives=drives, places=len(drives))
    ui.click('.nav-item[data-screen="backups"]')
    ui.wait_for_timeout(800)
    return ui.eval_on_selector("#screen-backups", "el => el.innerText")


def test_one_drive_does_not_get_the_library_block_repeated_beside_it(ui: Page) -> None:
    """With a single drive, "Your library" and that drive are necessarily the same set - two
    identical blocks stacked. This is the new-user case."""
    text = _backups(
        ui,
        [
            {
                "label": "destA",
                "files": 1997,
                "size": 5_298_094_843,
                "reach": "connected",
                "path": "/media/A",
                "last_verified": None,
            }
        ],
    )

    assert "Your library" not in text, f"the library block is still stacked on one drive:\n{text}"
    assert "destA" in text, "the drive itself must still be listed"


def test_a_second_drive_earns_the_library_block_back(ui: Page) -> None:
    """The moment the drives can DISAGREE with the library, the total is a fact of its own."""
    text = _backups(
        ui,
        [
            {
                "label": "destA",
                "files": 1997,
                "size": 5_298_094_843,
                "reach": "connected",
                "path": "/media/A",
                "last_verified": None,
            },
            {
                "label": "BackupB",
                "files": 161,
                "size": 296_509_852,
                "reach": "connected",
                "path": "/media/B",
                "last_verified": None,
            },
        ],
    )

    assert "Your library" in text, f"two drives and no library total:\n{text}"


# ------------------------------------------------------------------ 5. dark mode depth


def test_dark_mode_separates_card_from_page_by_value_not_by_border(ui: Page) -> None:
    """MEASURED, both themes. Light gets a shadow and 1.060:1 of value separation; dark sets
    `--shadow-sm: none` (correct - a shadow is invisible on near-black) and had 1.077:1, so the
    border did all the work while being the WEAKER of the two borders (1.19:1 against 1.28:1).

    Dark is where depth is cheapest: lightness is the elevation cue, so it should have MORE
    separation than light, not the same.
    """
    ui.emulate_media(color_scheme="dark")
    ui.wait_for_timeout(200)
    dark = ui.evaluate(
        "() => { const c = getComputedStyle(document.querySelector('.card'));"
        " return { card: c.backgroundColor, border: c.borderTopColor, text: c.color,"
        "   page: getComputedStyle(document.body).backgroundColor }; }"
    )
    separation = _contrast(dark["card"], dark["page"])
    assert separation >= 1.20, (
        f"dark card/page separation is {separation:.3f}:1 - the border is doing the work"
    )
    assert _contrast(dark["border"], dark["card"]) >= 1.25, "the dark border is the weaker one"
    assert _contrast(dark["text"], dark["card"]) >= 4.5, "raising the surface cost text contrast"


def test_light_mode_separation_is_not_regressed(ui: Page) -> None:
    """CRY-WOLF HALF: light already had a shadow, so it must not be 'fixed' too."""
    ui.emulate_media(color_scheme="light")
    ui.wait_for_timeout(200)
    light = ui.evaluate(
        "() => { const c = getComputedStyle(document.querySelector('.card'));"
        " return { card: c.backgroundColor, shadow: c.boxShadow,"
        "   page: getComputedStyle(document.body).backgroundColor,"
        "   text: c.color }; }"
    )
    assert light["shadow"] != "none", "light lost its shadow"
    assert _contrast(light["text"], light["card"]) >= 4.5
