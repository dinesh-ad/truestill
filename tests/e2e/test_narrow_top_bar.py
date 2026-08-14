"""Below 720px the rail is a real top bar: icons in one row, custody as a band beneath it.

What the breakpoint produced before: seven nav rows of one item each, because `.nav-item` keeps
`width: 100%` from the base rule and the wrap could never wrap. The bar was 619px of a 900px
viewport - the sidebar rotated in intent only - and the custody strip floated to the right edge
at y=382 with `margin-left: auto`.

The tooltip mechanism is the collapsed rail's, reused rather than reinvented: labels stay in the
DOM for assistive tech, and the tooltip appears on hover AND focus, which is what `(fff)` pins.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

#: THE MIGRATION'S EARLY-WARNING SYSTEM. This file belongs to no screen, so no screen's commit
#: carries it - and an island landing on a DIFFERENT screen changes the DOM around it without
#: touching a line here. `make e2e-shell` runs the set after every island; see
#: `docs/react-migration-plan.md`.
pytestmark = pytest.mark.shell

NARROW = {"width": 680, "height": 900}
TINY = {"width": 360, "height": 800}


def _narrow(ui: Page, size: dict[str, int] = NARROW) -> None:
    ui.set_viewport_size(size)
    ui.wait_for_timeout(250)


def test_the_seven_destinations_sit_on_one_row(ui: Page) -> None:
    """The whole point: `width: 100%` meant seven rows of one, whatever `flex-wrap` said."""
    _narrow(ui)
    tops = ui.eval_on_selector_all(
        ".nav-item", "els => els.map(e => Math.round(e.getBoundingClientRect().y))"
    )
    assert len(tops) == 7, f"expected seven destinations, got {len(tops)}"
    assert len(set(tops)) == 1, f"the nav is on {len(set(tops))} rows, not one: {sorted(set(tops))}"


def test_the_bar_is_a_bar_and_not_most_of_the_window(ui: Page) -> None:
    """It was 619px of a 900px viewport - 69% of the first screen spent on navigation."""
    _narrow(ui)
    bar = ui.eval_on_selector("#sidebar", "el => el.getBoundingClientRect().height")
    assert bar <= 120, f"the top bar is {bar:.0f}px tall - that is still a stacked sidebar"


def test_the_labels_are_gone_but_still_reachable(ui: Page) -> None:
    """Icons only. The label stays in the DOM so a screen reader still announces the item."""
    _narrow(ui)
    # Clipped to 1x1 rather than `display: none`, which is what keeps it for a screen reader -
    # so the assertion is that it PAINTS nothing, not that Playwright calls it hidden.
    painted = ui.eval_on_selector(
        '.nav-item[data-screen="organize"] .nav-label',
        "el => { const b = el.getBoundingClientRect();"
        " return {w: b.width, h: b.height, text: el.textContent.trim()}; }",
    )
    assert painted["w"] <= 1, f"the label still occupies {painted['w']:.0f}px of width"
    assert painted["h"] <= 1, f"the label still occupies {painted['h']:.0f}px of height"
    assert painted["text"] == "Organize", "the label was removed rather than hidden"


def test_the_tooltip_answers_on_hover_and_on_focus(ui: Page) -> None:
    """`(fff)`: keyboard reaches it too. Same mechanism as the collapsed rail, not a second one."""
    _narrow(ui)
    item = ui.locator('.nav-item[data-screen="backups"]')
    tip = item.locator(".nav-tooltip")

    expect(tip).to_be_hidden()
    item.hover()
    expect(tip).to_be_visible()
    expect(tip).to_contain_text("Backups")

    ui.locator('.nav-item[data-screen="find"]').hover()  # move the pointer away
    expect(tip).to_be_hidden()
    item.focus()
    expect(tip).to_be_visible()


def test_the_custody_strip_is_a_full_width_band_below_the_bar(ui: Page) -> None:
    """It floated to the right edge inside the bar. It is the ambient answer to 'where are my
    files', so it is not dropped at narrow widths - it becomes a band the width of the window."""
    _narrow(ui)
    strip = ui.locator(".custody")
    expect(strip).to_be_visible()

    box = ui.eval_on_selector(
        ".custody",
        "el => { const b = el.getBoundingClientRect();"
        " const nav = document.querySelector('.nav').getBoundingClientRect();"
        " const main = document.querySelector('.main').getBoundingClientRect();"
        " return {x: b.x, w: b.width, y: b.y, navBottom: nav.bottom, mainTop: main.y,"
        "         viewport: window.innerWidth}; }",
    )
    assert box["w"] >= box["viewport"] - 2, f"the strip is {box['w']:.0f}px of {box['viewport']}px"
    assert box["x"] <= 1, f"the strip starts at x={box['x']:.0f} - it is still floating"
    assert box["y"] >= box["navBottom"] - 1, "the strip is not below the nav"
    assert box["y"] <= box["mainTop"] + 1, "the strip is not above the content"


def test_the_custody_line_is_readable_at_narrow_widths(ui: Page) -> None:
    """It is hidden in the 64px rail; a full-width band has room for the sentence."""
    _narrow(ui)
    expect(ui.locator("#custody-line")).to_be_visible()
    expect(ui.locator("#custody-pips")).to_be_visible()


def test_the_catalog_path_fits_rather_than_truncating_to_nothing(ui: Page) -> None:
    """The fit logic measures and middle-ellipsises; a full-width strip gives it far more room.

    The `...e` defect came from that code measuring mid-animation. With room to spare it must
    show the path whole, and must never fall back to the `.too-narrow` hide.
    """
    _narrow(ui)
    ui.wait_for_timeout(400)  # let the ResizeObserver settle after the width change
    path = ui.locator("#custody-catalog")
    if path.count() == 0:
        return  # no catalog path in this state; nothing to fit
    expect(path).to_be_visible()

    shown = ui.eval_on_selector("#custody-catalog", "el => el.textContent.trim()")
    full = ui.eval_on_selector("#custody-catalog", "el => el.dataset.full || ''")
    assert len(shown) > 3, f"the path collapsed to {shown!r}"
    if full:
        assert shown == full, f"the path is still being ellipsised with room to spare: {shown!r}"


def test_the_bar_still_scrolls_away(ui: Page) -> None:
    """Ruled 2026-08-04 and kept: pinning a bar this size spends the viewport on navigation."""
    _narrow(ui)
    ui.evaluate("() => document.body.insertAdjacentHTML('beforeend', '<div style=height:2000px>')")
    before = ui.eval_on_selector("#sidebar", "el => el.getBoundingClientRect().y")
    ui.evaluate("() => window.scrollTo(0, 600)")
    ui.wait_for_timeout(200)
    after = ui.eval_on_selector("#sidebar", "el => el.getBoundingClientRect().y")
    assert after < before - 100, f"the bar is pinned: {before:.0f} -> {after:.0f}"


def test_at_360px_the_row_still_holds_or_wraps_without_overflowing(ui: Page) -> None:
    """The narrowest case worth supporting. Whatever it does, it must not scroll sideways."""
    _narrow(ui, TINY)
    overflow = ui.evaluate(
        "() => document.documentElement.scrollWidth - document.documentElement.clientWidth"
    )
    assert overflow <= 1, f"the page scrolls sideways by {overflow}px at 360px"

    clipped = ui.eval_on_selector_all(
        ".nav-item", "els => els.filter(e => e.getBoundingClientRect().width < 24).length"
    )
    assert clipped == 0, f"{clipped} destinations are squeezed below a tappable size"
