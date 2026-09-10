"""The content column left a band of empty page beside it on a wide window.

760px of content and a 320px panel in a 1500px window leaves ~190px of nothing between them,
which reads as broken rather than as breathing room. 760 existed to keep PROSE readable, so the
column grows and the prose keeps its own cap - the constraint moves to where it belongs.
"""

from __future__ import annotations

import json

from playwright.sync_api import Page

# A comfortable measure is ~45-75 characters; 80 is a ceiling, not a target.
#
# ⚠ **CHARACTERS, NOT PIXELS, AND THE PIXEL VERSION WAS UNSOUND ON ITS OWN TERMS.** This read
# `PROSE_MAX_PX = 660` with the note *"sans at 16px averages ~8px per character, so this is the px
# equivalent of roughly 80 characters"*. That conversion holds for exactly one font. `--family-sans`
# (`tokens.css`) is a pure system stack with nothing bundled - unlike `--family-mono`, which is - so
# the face that renders is whatever the machine has, and the `0` advance that `ch` is defined from
# moves with it. Measured on ONE element at ONE font-size, 15.5168px:
#
#     this machine   8.8660 px/ch  = 0.5714 em   (Liberation/Arial metrics)
#     CI's ubuntu    9.8614 px/ch  = 0.6355 em   (DejaVu Sans, to three decimals)
#
# So 660px enforced ~74 characters here and ~67 on CI - neither of them the 80 the comment claimed.
# The element under test is capped at `68ch` by `.screen .card .k` and measured **68ch on both**:
# the layout was doing its job exactly, and only the conversion failed. Run 34404705599 was red at
# 670.578125px for prose that was never too wide by the rule it is governed by.
#
# Asserting the character count is the same property the CSS is written in, so it is correct on
# every font, on every machine, and it cannot drift with a fallback nobody chose.
PROSE_MAX_CH = 80


def _with_panel(ui: Page) -> None:
    """The reported case had the panel showing. An empty catalog renders none, and the column
    then centres inside its cap - which is correct behaviour, not the band being measured."""
    ui.route(
        "**/api/library/status",
        lambda r: r.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(
                {
                    "files": 2300,
                    "photos": 2287,
                    "videos": 13,
                    "audio": 0,
                    "bytes": 13_295_210_826,
                    "by_format": {},
                    "places": 2,
                    "single_copy": 0,
                    "files_no_copy": 31,
                    "files_one_copy": 0,
                    "redundancy_floor": 1,
                    "files_on_a_drive": 2269,
                    "held_floor": 1,
                    "library_path": "",
                    "backup_path": "",
                    "drives": [],
                    "custody": {},
                    "catalog_path": "/tmp/c.sqlite",
                    "catalog_presence": "ready",
                    "catalog_detail": "",
                    "catalog_tone": "info",
                }
            ),
        ),
    )
    ui.reload()
    ui.wait_for_selector(".nav-item")


def test_no_empty_band_between_the_content_and_the_panel(ui: Page) -> None:
    ui.set_viewport_size({"width": 1500, "height": 950})
    _with_panel(ui)
    ui.wait_for_timeout(250)
    # Against the main column's CONTENT box, not its border box: `.main` has its own padding,
    # and a page gutter is not an empty band. Measuring the border box counted the gutter as
    # the defect and would have kept failing however wide the column grew.
    gap = ui.evaluate(
        "() => { const screen = document.querySelector('.screen.active');"
        " const main = document.querySelector('.main');"
        " const s = screen.getBoundingClientRect(), m = main.getBoundingClientRect();"
        " const cs = getComputedStyle(main);"
        " const left = m.left + parseFloat(cs.paddingLeft);"
        " const right = m.right - parseFloat(cs.paddingRight);"
        " return Math.max(right - s.right, s.left - left); }"
    )
    assert gap <= 40, f"{gap:.0f}px of empty page beside the content column"


def test_the_column_still_stops_growing_on_a_very_wide_window(ui: Page) -> None:
    """Filling 2500px would be worse than the band it replaced.

    The CEILING moved 1080 -> 1600 when the maintainer's own monitors were measured (1920, 2560
    and 3072 CSS px); the PROPERTY this guards - that there is a ceiling at all - did not. The
    number here follows the cap and stays below what a form row can carry without looking absurd.
    """
    ui.set_viewport_size({"width": 2400, "height": 950})
    ui.wait_for_timeout(250)
    width = ui.eval_on_selector(".screen.active", "el => el.getBoundingClientRect().width")
    assert width <= 1700, f"the content column grew to {width:.0f}px"


def test_prose_keeps_a_readable_measure_however_wide_the_column(ui: Page) -> None:
    """This is WHY 760 existed. The cap moves onto the text rather than onto the layout.

    Each element is measured in ITS OWN `ch` - the `0` advance of the face that actually rendered
    it, probed rather than assumed, because two elements here sit at different font sizes and a
    single constant for all of them would be the same mistake one level up.
    """
    ui.set_viewport_size({"width": 2400, "height": 950})
    ui.wait_for_timeout(250)
    measured = ui.evaluate(
        "() => [...document.querySelectorAll("
        "  '.screen.active .lede, .screen.active .card .k, .screen.active .hint')]"
        ".filter(e => e.offsetParent && e.textContent.trim().length > 60)"
        ".map(e => {"
        "  const probe = document.createElement('span');"
        "  probe.style.cssText = 'position:absolute;visibility:hidden;white-space:pre;font:'"
        "    + getComputedStyle(e).font;"
        "  probe.textContent = '0'.repeat(100);"
        "  document.body.appendChild(probe);"
        "  const chPx = probe.getBoundingClientRect().width / 100;"
        "  probe.remove();"
        "  return {ch: e.getBoundingClientRect().width / chPx,"
        "          px: e.getBoundingClientRect().width,"
        "          t: e.textContent.trim().slice(0, 40)};"
        "})"
    )
    # Anti-vacuity: an empty set satisfies every `not too_wide` below, and the filter above is
    # easy to make match nothing (a copy change under 60 characters, a screen that did not open).
    assert measured, "no prose was measured, so this test asserted nothing about the column"

    too_wide = [m for m in measured if m["ch"] > PROSE_MAX_CH]
    assert not too_wide, "prose runs past a readable measure: " + ", ".join(
        f"{m['t']!r} at {m['ch']:.0f}ch ({m['px']:.0f}px)" for m in too_wide
    )


def test_the_form_controls_do_use_the_extra_width(ui: Page) -> None:
    """The point of growing: a path field that shows the path. Controls are not prose."""
    ui.set_viewport_size({"width": 1500, "height": 950})
    ui.wait_for_timeout(250)
    field = ui.eval_on_selector("#org-source", "el => el.getBoundingClientRect().width")
    assert field >= 500, f"the folder field is {field:.0f}px - it did not take the space"
