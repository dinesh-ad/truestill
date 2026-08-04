"""The rail: dark in both themes, an outlined wordmark, a monogram when collapsed.

Shell only. Nothing here asserts screen content.

The rail is **theme-independent**: it is dark in light mode too, so its tokens sit outside the
light/dark ladder and the two colours that used to be borrowed from it were re-derived against
it rather than reused - `--text-muted` measured 3.91:1 there, below AA, while its own source
annotation claims 4.6:1 *on white*.
"""

from __future__ import annotations

from playwright.sync_api import Page, expect

_LIGHT = {"colorScheme": "light"}


def _rail_bg(ui: Page) -> str:
    return ui.eval_on_selector(".sidebar", "el => getComputedStyle(el).backgroundColor")


def test_the_rail_is_dark_in_light_mode_too(ui: Page) -> None:
    """Theme-independent, which is the whole point of giving it its own token group."""
    ui.emulate_media(color_scheme="light")
    light = _rail_bg(ui)
    ui.emulate_media(color_scheme="dark")
    dark = _rail_bg(ui)

    assert light == dark, f"the rail changed with the theme: light {light} vs dark {dark}"
    # Dark means dark: every channel low. Parsed rather than string-matched so a token
    # rename that keeps the colour still passes, and a colour change fails.
    channels = [int(v) for v in light[light.index("(") + 1 : light.index(")")].split(",")[:3]]
    assert max(channels) < 60, f"the rail is not dark: {light}"


def test_the_wordmark_is_outlined_artwork_with_an_accessible_name(ui: Page) -> None:
    """Outlined paths, not a font - so it is identical wherever it renders.

    Georgia is absent from a stock Linux install, which is a launch platform, so a font-rendered
    wordmark is a different shape per machine. The accessible name is asserted because outlining
    turns readable text into geometry: without it the product's own name stops existing for a
    screen reader.
    """
    mark = ui.locator(".wordmark svg[data-brand='wordmark']")
    expect(mark).to_be_visible()

    assert (
        ui.eval_on_selector(
            ".wordmark svg[data-brand='wordmark']", "el => el.querySelectorAll('path').length"
        )
        > 0
    ), "the wordmark has no path data - it is not outlined artwork"

    assert (
        ui.eval_on_selector(
            ".wordmark svg[data-brand='wordmark']", "el => el.getAttribute('aria-label')"
        )
        == "Truestill"
    )
    assert "Truestill" in ui.eval_on_selector(
        ".wordmark svg[data-brand='wordmark'] title", "el => el.textContent"
    )


def test_the_wordmark_gradient_is_authored_for_the_rail_not_the_brand_sheet(ui: Page) -> None:
    """The supplied gradient cannot be used here, and this pins why.

    `#2A3B8C`, the brand sheet's low stop, measures **1.81:1** against the rail - it fails every
    threshold. The sheet's gradient is for a light page. The rail's is authored separately, and
    this asserts the unusable stop is not what shipped.
    """
    stops = ui.eval_on_selector_all(
        ".wordmark svg linearGradient stop",
        "els => els.map(e => (e.getAttribute('stop-color') || '').toLowerCase())",
    )
    assert stops, "no gradient stops found"
    assert "#2a3b8c" not in stops, (
        "the brand sheet's light-page gradient stop is on the dark rail, where it measures "
        "1.81:1 and is effectively invisible"
    )


def test_each_mark_carries_its_own_gradient_so_it_paints_when_its_sibling_is_hidden(
    ui: Page,
) -> None:
    """The defect this caught: a shared gradient that stops resolving when collapsed.

    Both marks first referenced one `<linearGradient>` declared inside the wordmark SVG. When
    the rail collapses, the wordmark is `display: none` - and **a hidden SVG's `defs` do not
    resolve**, so the monogram rendered at its full 39x26 box and painted nothing at all. It was
    present, measurable, correctly sized and invisible, which is why the geometry assertions
    above did not notice. Each mark now declares its own gradient.
    """
    for mark in ("wordmark", "monogram"):
        own = ui.eval_on_selector(
            f".wordmark svg[data-brand='{mark}']",
            "el => { const g = el.querySelector('linearGradient');"
            " if (!g) return null;"
            " const fill = el.querySelector('path').getAttribute('fill') || '';"
            " return fill.includes(g.id); }",
        )
        assert own is True, f"the {mark} does not reference a gradient it declares itself"


def test_collapsing_swaps_the_wordmark_for_the_monogram(ui: Page) -> None:
    """The 64px rail gets the monogram; the full wordmark does not fit and is not shrunk into it."""
    expect(ui.locator(".wordmark svg[data-brand='wordmark']")).to_be_visible()
    expect(ui.locator(".wordmark svg[data-brand='monogram']")).to_be_hidden()

    ui.click("#sidebar-toggle")
    expect(ui.locator("#sidebar")).to_have_attribute("data-collapsed", "true")

    expect(ui.locator(".wordmark svg[data-brand='monogram']")).to_be_visible()
    expect(ui.locator(".wordmark svg[data-brand='wordmark']")).to_be_hidden()


def test_the_nav_is_grouped_but_still_seven_flat_items(ui: Page) -> None:
    """Section labels are grouping, not hierarchy. `(aam)` closed as no nested submenus."""
    labels = ui.eval_on_selector_all(
        ".nav-section-label", "els => els.map(e => e.textContent.trim().toUpperCase())"
    )
    assert labels == ["MAIN", "SETTINGS"], f"expected MAIN and SETTINGS, got {labels}"

    assert ui.eval_on_selector_all(".nav-item", "els => els.length") == 7
    assert (
        ui.eval_on_selector_all(
            ".nav-item [class*='submenu'], .nav-item ul, .nav-item .nav-children",
            "els => els.length",
        )
        == 0
    ), "a submenu appeared; (aam) closed as no nested submenus"


def test_the_section_labels_are_hidden_when_collapsed(ui: Page) -> None:
    """A 64px rail has no room for a word, and a clipped 'SETTINGS' is worse than none."""
    labels = ui.locator(".nav-section-label")
    # Anti-vacuity: with no labels at all this test is an empty loop that always passes.
    assert labels.count() == 2, f"expected 2 section labels before collapsing, got {labels.count()}"

    ui.click("#sidebar-toggle")
    expect(ui.locator("#sidebar")).to_have_attribute("data-collapsed", "true")
    for label in labels.all():
        expect(label).to_be_hidden()
