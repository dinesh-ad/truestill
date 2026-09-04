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
    """The fit logic measures and middle-ellipsises; asserted against the width it actually has.

    The `...e` defect came from that code measuring mid-animation, and this test is what caught
    it. It must never fall back to the `.too-narrow` hide with room available.

    ⚠ **IT USED TO ASSERT `shown == full` UNCONDITIONALLY, AND THAT ASSERTED A PRECONDITION IT
    DID NOT ESTABLISH** - `(ajm)`. Its own docstring said *"with room to spare"* while the room
    came from the viewport and the path came from `tmp_path`, so it was testing the length of the
    directory pytest happened to hand it. **Two triggers, one cause**: a machine with a `/data`
    volume (95 characters against CI's 77), and `pytest-xdist` inserting `popen-gwN/`, which
    failed both `-n auto` dispatches of `(ajx)`. The product was correct on every one of those
    runs.

    **The contract is in `app.js:fitCatalogPath` and it is conditional**, so the test is too:

        el.textContent = full;
        if (el.clientWidth <= 0 || el.scrollWidth <= el.clientWidth) return;

    Whole when it fits, middle-ellipsised when it does not. Asking the element whether the full
    string fits - rather than assuming it does - tests the fit logic in **both** directions and is
    independent of how long the path happens to be. A fit test whose input length is incidental is
    not testing fit.
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
    if not full:
        return

    # Does the WHOLE path fit in the box it has? Measured the way the code measures it, and
    # restored in the same evaluation so the page is left exactly as it was found.
    fits = ui.eval_on_selector(
        "#custody-catalog",
        "el => { const was = el.textContent; el.textContent = el.dataset.full;"
        " const ok = el.clientWidth > 0 && el.scrollWidth <= el.clientWidth;"
        " el.textContent = was; return ok; }",
    )
    if fits:
        assert shown == full, f"the path is still being ellipsised with room to spare: {shown!r}"
    else:
        assert "\u2026" in shown, f"the path does not fit and was not ellipsised: {shown!r}"
        assert shown.endswith(full.rsplit("/", 1)[-1]), (
            f"the filename did not survive the ellipsis: {shown!r}"
        )


def test_the_fit_logic_shows_a_short_path_whole_and_ellipsises_a_long_one(ui: Page) -> None:
    """Both branches, driven with paths the test owns - so neither depends on the environment.

    ⚠ **THE CONDITIONAL TEST ABOVE IS CORRECT AND ITS COVERAGE IS NOT PORTABLE**, which is why
    this exists beside it. Whichever branch runs there is decided by how long `tmp_path` happens
    to be: on this machine the `/data` root makes it long, so only the ellipsis branch runs, and
    a mutation removing `fitCatalogPath`'s fits-early-return was **not caught** by it. In CI the
    path is shorter and the other branch runs. A test whose branch coverage moves with the
    filesystem is the same defect `(ajm)` is about, one level in.

    So this drives `fitCatalogPath` directly with two paths it constructs, and asserts both
    outcomes. `app.js` is a classic script (`<script src="/static/app.js">`), so its top-level
    functions are globals and are callable - the same seam `main.tsx` documents for
    `organizeCompletion` and `solveResultGrid`.
    """
    _narrow(ui)
    ui.wait_for_timeout(400)
    if ui.locator("#custody-catalog").count() == 0:
        return

    outcomes = ui.eval_on_selector(
        "#custody-catalog",
        "el => { const keep = el.dataset.full;"
        " const run = (p) => { el.dataset.full = p; window.fitCatalogPath(el);"
        "                      return el.textContent; };"
        " const short = run('/a/b.sqlite');"
        " const long = run('/' + 'verylongdirectory/'.repeat(24) + 'catalog.sqlite');"
        " el.dataset.full = keep; window.fitCatalogPath(el);"
        " return {short, long}; }",
    )

    assert outcomes["short"] == "/a/b.sqlite", (
        f"a path with room to spare was still ellipsised: {outcomes['short']!r}"
    )
    assert "\u2026" in outcomes["long"], (
        f"a path far too long for the box was not ellipsised: {outcomes['long']!r}"
    )
    assert outcomes["long"].endswith("catalog.sqlite"), (
        f"the filename did not survive the ellipsis: {outcomes['long']!r}"
    )


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
