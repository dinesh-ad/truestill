"""The palette, and what Organize shows before you do anything.

Structure was right and the app was still black and white. Indigo leads on every screen, amber
and green stay status-only, and the neutrals are WARM - a cool-grey ground is most of what reads
as clinical.

Every pairing is measured in the browser against the computed style, not against a hex string in
a comment: a token can be changed without the comment noticing.
"""

from __future__ import annotations

import json
from typing import Any

from playwright.sync_api import Page, expect

AA_TEXT = 4.5
AA_LARGE = 3.0


def _rgb(value: str) -> tuple[int, int, int]:
    parts = [
        int(n) for n in value.replace("rgba", "rgb").split("(")[1].split(")")[0].split(",")[:3]
    ]
    return (parts[0], parts[1], parts[2])


def _luminance(rgb: tuple[int, int, int]) -> float:
    out = []
    for channel in rgb:
        srgb = channel / 255
        out.append(srgb / 12.92 if srgb <= 0.04045 else ((srgb + 0.055) / 1.055) ** 2.4)
    return 0.2126 * out[0] + 0.7152 * out[1] + 0.0722 * out[2]


def _contrast(a: str, b: str) -> float:
    high, low = sorted((_luminance(_rgb(a)), _luminance(_rgb(b))), reverse=True)
    return (high + 0.05) / (low + 0.05)


def _token(ui: Page, name: str) -> str:
    return ui.evaluate(
        "(n) => { const el = document.createElement('span');"
        " el.style.color = getComputedStyle(document.documentElement).getPropertyValue(n).trim();"
        " document.body.appendChild(el);"
        " const c = getComputedStyle(el).color; el.remove(); return c; }",
        name,
    )


# --------------------------------------------------------------------------- warm neutrals


def test_the_light_ground_is_warm_not_cool(ui: Page) -> None:
    """A cool-grey page is most of what reads as clinical, and the ground is the cheapest fix."""
    ui.emulate_media(color_scheme="light")
    ground = _rgb(ui.eval_on_selector("body", "el => getComputedStyle(el).backgroundColor"))
    assert ground[0] >= ground[2] + 3, (
        f"the light ground is cool or neutral (r={ground[0]}, b={ground[2]}) - it must be warm"
    )


def test_the_dark_ground_is_warm_too(ui: Page) -> None:
    ui.emulate_media(color_scheme="dark")
    ui.wait_for_timeout(120)
    ground = _rgb(ui.eval_on_selector("body", "el => getComputedStyle(el).backgroundColor"))
    assert ground[0] >= ground[2], f"the dark ground is cool: r={ground[0]}, b={ground[2]}"


# ------------------------------------------------------------------------------- contrast


def test_body_text_and_the_secondary_tier_clear_aa_in_both_themes(ui: Page) -> None:
    for scheme in ("light", "dark"):
        ui.emulate_media(color_scheme=scheme)
        ui.wait_for_timeout(120)
        surface = ui.eval_on_selector(".card", "el => getComputedStyle(el).backgroundColor")
        for token in ("--text", "--text-secondary", "--text-muted"):
            ratio = _contrast(_token(ui, token), surface)
            assert ratio >= AA_TEXT, f"{token} is {ratio:.2f}:1 on {scheme} surface"


def test_the_status_colours_clear_aa_as_text(ui: Page) -> None:
    """FOUND BY MEASURING: light amber was 2.94:1 and green 3.42:1 - both below AA, and amber
    below even the 3:1 large-text floor it needed for a 40px metric."""
    for scheme in ("light", "dark"):
        ui.emulate_media(color_scheme=scheme)
        ui.wait_for_timeout(120)
        surface = ui.eval_on_selector(".card", "el => getComputedStyle(el).backgroundColor")
        for token in ("--warning", "--success"):
            ratio = _contrast(_token(ui, token), surface)
            assert ratio >= AA_TEXT, f"{token} is {ratio:.2f}:1 on {scheme} surface"


def test_the_indigo_heading_clears_aa(ui: Page) -> None:
    for scheme in ("light", "dark"):
        ui.emulate_media(color_scheme=scheme)
        ui.wait_for_timeout(120)
        colour = ui.eval_on_selector(".screen.active h1", "el => getComputedStyle(el).color")
        ground = ui.eval_on_selector("body", "el => getComputedStyle(el).backgroundColor")
        ratio = _contrast(colour, ground)
        assert ratio >= AA_LARGE, f"the h1 is {ratio:.2f}:1 in {scheme}"


def test_a_primary_button_clears_aa_against_its_own_label(ui: Page) -> None:
    for scheme in ("light", "dark"):
        ui.emulate_media(color_scheme=scheme)
        ui.wait_for_timeout(120)
        pair = ui.eval_on_selector(
            ".btn-primary",
            "el => { const s = getComputedStyle(el); return [s.color, s.backgroundColor]; }",
        )
        ratio = _contrast(pair[0], pair[1])
        assert ratio >= AA_TEXT, f"the primary button is {ratio:.2f}:1 in {scheme}"


# ------------------------------------------------------------------- indigo leads everywhere


def test_indigo_is_visible_on_the_content_screens_not_only_the_rail(ui: Page) -> None:
    """The lead colour has to appear where a person is working, or the app is black and white."""
    ui.emulate_media(color_scheme="light")
    accent = _rgb(_token(ui, "--accent-strong"))
    heading = _rgb(ui.eval_on_selector(".screen.active h1", "el => getComputedStyle(el).color"))
    assert heading == accent, f"the h1 is {heading}, not the lead colour {accent}"


def test_amber_and_green_stay_status_only(ui: Page) -> None:
    """Colour keeps meaning: if a heading is green it stops meaning `safe`."""
    ui.emulate_media(color_scheme="light")
    warning = _rgb(_token(ui, "--warning"))
    success = _rgb(_token(ui, "--success"))
    for selector in (".screen.active h1", ".screen.active .lede", ".btn-primary"):
        colour = _rgb(ui.eval_on_selector(selector, "el => getComputedStyle(el).color"))
        assert colour != warning, f"{selector} is using the warning colour"
        assert colour != success, f"{selector} is using the success colour"


# ------------------------------------------------------------ the panel at rest on Organize


def _status(ui: Page, **overrides: Any) -> None:
    base: dict[str, Any] = {
        "files": 2269,
        "photos": 2100,
        "videos": 169,
        "audio": 0,
        "bytes": 6_650_000_000,
        "by_format": {"photos": {"jpg": 2100}, "videos": {"mp4": 169}},
        "places": 2,
        "single_copy": 400,
        "files_no_copy": 69,
        "files_one_copy": 400,
        "redundancy_floor": 0,
        "files_on_a_drive": 2200,
        "held_floor": 1,
        "library_path": "/media/BackupA",
        "backup_path": "/media/BackupB",
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
    ui.reload()
    ui.wait_for_selector(".nav-item")


def test_the_panel_shows_the_library_at_rest_on_organize(ui: Page) -> None:
    """The third column did not exist when he opened the app. It is the library, not the run."""
    ui.set_viewport_size({"width": 1500, "height": 900})
    _status(ui)
    panel = ui.locator("#panel")
    expect(panel).to_be_visible()
    # `mediaCount` - the house phrasing, a photo/video split rather than a bare total, which
    # is what the rest of the app says and the more useful reading.
    expect(panel).to_contain_text("2,100")
    expect(panel).to_contain_text("GB")


def test_the_resting_panel_names_what_is_on_one_copy_only(ui: Page) -> None:
    ui.set_viewport_size({"width": 1500, "height": 900})
    _status(ui)
    expect(ui.locator("#panel")).to_contain_text("400")


def test_an_empty_library_gets_no_panel_rather_than_a_row_of_zeros(ui: Page) -> None:
    ui.set_viewport_size({"width": 1500, "height": 900})
    _status(ui, files=0, photos=0, videos=0, bytes=0, files_one_copy=0, places=0)
    expect(ui.locator("#panel")).to_be_hidden()


def test_the_resting_panel_still_holds_nothing_task_critical(ui: Page) -> None:
    ui.set_viewport_size({"width": 1500, "height": 900})
    _status(ui)
    controls = ui.evaluate(
        "() => document.querySelectorAll("
        " '#panel button, #panel input, #panel select, #panel a[href]').length"
    )
    assert controls == 0, "the resting panel gained a control; it vanishes on a narrow window"


# ------------------------------------------------------------------------- quick access


def test_organize_offers_places_without_opening_a_dialogue(ui: Page) -> None:
    """The picker already had a places rail buried in a modal. Surface it."""
    quick = ui.locator("[data-testid='org-quick']")
    expect(quick).to_be_visible()
    assert ui.locator("[data-testid='org-quick'] .quick-place").count() >= 1


def test_a_quick_place_fills_the_folder_field(ui: Page) -> None:
    first = ui.locator("[data-testid='org-quick'] .quick-place").first
    path = first.get_attribute("data-path")
    first.click()
    expect(ui.locator("#org-source")).to_have_value(path or "")
