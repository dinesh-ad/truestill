"""The sidebar does not move when the page scrolls, and a screen switch lands at the top.

Both halves of papercut #9 in `docs/walkthrough-qa-report.md`, open since 2026-07-26.

**Half 1 - the sidebar scrolled away.** `.main` carried `overflow-y: auto` the whole time, so
the containment was written; it never engaged, because `.app` used `min-height: 100vh` rather
than `height`. The grid declares columns only, so its single implicit row sizes to content: when
the main column exceeded the viewport the row grew, `.main` was never overflowed, and the
*document* scrolled instead, carrying the sidebar with it. Measured before the fix at -1200px on
a 1200px scroll, at both 1280x800 and 700x800.

**Half 2 - the next screen landed scrolled down.** `showScreen` toggles a class and nothing
resets the scroller, so the offset survived the switch.

**A note on how half 2 had to be measured, because it defeated two attempts.** Making only the
outgoing screen tall lets the document shrink on switch, so the browser clamps `scrollTop` to 0
and the check reads "fixed" whether or not it is - a fixture that cannot fail against the bug.
And driving the switch with `page.click()` on a nav item reads 0 for a second wrong reason:
Playwright scrolls a target into view before clicking, and a sidebar that has scrolled away is
off-screen, so the click itself returns the page to the top. Both screens are therefore made
tall here, and **the switch is driven by `showScreen` directly** rather than by a click, so the
assertion is about the application and not about the harness.

Below the 720px breakpoint the sidebar becomes a wrapping top bar and deliberately keeps
scrolling away; that is asserted too, so a later "consistency" fix has to argue with a test.
"""

from __future__ import annotations

from playwright.sync_api import Page, expect

_TALL = (
    "el => { const d = document.createElement('div');"
    " d.className = 'tallblock'; d.style.height = '3000px';"
    " d.textContent = 'tall'; el.appendChild(d); }"
)


def _make_screens_tall(ui: Page) -> None:
    """Both screens, so the document cannot shrink on switch and clamp the answer to 0."""
    for screen in ("#screen-organize", "#screen-settings"):
        ui.eval_on_selector(screen, _TALL)


def test_the_sidebar_does_not_move_when_the_page_scrolls(ui: Page) -> None:
    """Half 1, at the design target width."""
    ui.set_viewport_size({"width": 1280, "height": 800})
    _make_screens_tall(ui)

    before = ui.eval_on_selector(".sidebar", "el => el.getBoundingClientRect().top")
    assert ui.eval_on_selector(".main", "el => el.scrollHeight > el.clientHeight + 1"), (
        "the main column is not a scroll container, so this test would pass by having nothing "
        "to scroll - the containment it exists to pin is absent"
    )

    ui.eval_on_selector(".main", "el => { el.scrollTop = 1200; }")
    ui.wait_for_timeout(120)

    assert ui.eval_on_selector(".main", "el => el.scrollTop") == 1200, "the scroll did not take"
    after = ui.eval_on_selector(".sidebar", "el => el.getBoundingClientRect().top")
    assert after == before, f"the sidebar moved {after - before}px when the page scrolled"


def test_switching_screens_lands_at_the_top(ui: Page) -> None:
    """Half 2. Driven through `showScreen`, not a click - see the module docstring."""
    ui.set_viewport_size({"width": 1280, "height": 800})
    _make_screens_tall(ui)

    ui.eval_on_selector(".main", "el => { el.scrollTop = 1200; }")
    ui.wait_for_timeout(100)
    assert ui.eval_on_selector(".main", "el => el.scrollTop") == 1200

    ui.evaluate("showScreen('settings')")
    ui.wait_for_timeout(150)

    expect(ui.locator("#screen-settings")).to_have_class("screen active")
    landed = ui.eval_on_selector(".main", "el => el.scrollTop")
    document_top = ui.evaluate("document.scrollingElement.scrollTop")
    assert landed == 0, f"the next screen opened {landed}px down"
    assert document_top == 0, f"the document was left {document_top}px down"


def test_below_the_breakpoint_the_top_bar_still_scrolls_away(ui: Page) -> None:
    """The narrow case is deliberately different, and the difference is pinned.

    Ruled 2026-08-04: the bar is seven items plus a wordmark plus the custody strip, and pinning
    that to a short window spends most of the viewport on navigation. Sticky nav pays when the
    nav is small relative to the content; here it is not. Asserted so that "make it consistent"
    has to be an argument rather than a tidy-up.
    """
    ui.set_viewport_size({"width": 700, "height": 800})
    _make_screens_tall(ui)

    before = ui.eval_on_selector(".sidebar", "el => el.getBoundingClientRect().top")
    assert ui.evaluate("document.scrollingElement.scrollHeight > window.innerHeight + 1"), (
        "the document does not scroll at this width, so this asserts nothing"
    )

    ui.evaluate("window.scrollTo(0, 600)")
    ui.wait_for_timeout(120)

    after = ui.eval_on_selector(".sidebar", "el => el.getBoundingClientRect().top")
    assert after < before, (
        "the top bar stayed put below the breakpoint; that is the opposite of the 2026-08-04 "
        "ruling, which keeps the narrow case scrolling away on purpose"
    )


def test_every_nav_item_is_reachable_on_a_short_window(ui: Page) -> None:
    """The defect the fix could have introduced, pinned rather than reasoned about.

    Pinning the shell to the viewport means the sidebar can no longer grow past it, so on a
    short window the last nav items would be clipped by `overflow: hidden` and simply
    unreachable - a worse defect than the scrolling one, and invisible on a developer's tall
    monitor. The rail is `overflow-y: auto` for exactly this, and this is what says so.

    **It asserts the USER can scroll it, not that a script can.** The first version of this
    test called `scroll_into_view_if_needed()` and passed with `overflow: hidden` restored,
    because a hidden container is still scrollable *programmatically* - only the wheel and the
    scrollbar are taken away. It was a guard that could not fail against the defect it names.
    A real wheel event is the discriminator, so that is what is dispatched.
    """
    ui.set_viewport_size({"width": 1280, "height": 380})

    overflowing = ui.eval_on_selector(".sidebar", "el => el.scrollHeight > el.clientHeight + 1")
    assert overflowing, (
        "the rail is not overflowing at this height, so nothing here is being tested - lower "
        "the viewport or this guard is decoration"
    )

    ui.hover(".sidebar")
    ui.mouse.wheel(0, 300)
    ui.wait_for_timeout(150)

    moved = ui.eval_on_selector(".sidebar", "el => el.scrollTop")
    assert moved > 0, (
        "the rail did not respond to the wheel, so the nav items below the fold cannot be "
        "reached by a person - only by a script"
    )


def test_the_folder_picker_still_covers_the_viewport_under_containment(ui: Page) -> None:
    """What containment could plausibly have broken, checked rather than assumed.

    The modal is `position: fixed; inset: 0`, so it is viewport-relative and a scroll container
    around it should not touch it - but "should not" is the sentence that precedes a defect.
    """
    ui.set_viewport_size({"width": 1280, "height": 800})
    _make_screens_tall(ui)
    ui.eval_on_selector(".main", "el => { el.scrollTop = 1200; }")
    ui.wait_for_timeout(100)

    ui.click('button[data-browse="org-source"]')
    backdrop = ui.locator(".modal-backdrop")
    expect(backdrop).to_be_visible()

    box = backdrop.bounding_box()
    assert box is not None
    assert box["y"] <= 1, f"the picker opened {box['y']}px down the viewport instead of covering it"
    assert box["height"] >= 700, "the picker did not fill the viewport height"
