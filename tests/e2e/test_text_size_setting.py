"""Text size, and the one thing it must not do: overwrite the size the user already chose.

`tokens.css` said it plainly - "NO root font-size is declared: the root is the user's ... which
is why there is no font-size setting in the product." That reasoning holds against an ABSOLUTE
setting and only against one. Somebody who raised their browser default to 24px and then picks
"Large" must not be handed 18px; that is not a preference, it is a reset.

So the steps are PERCENTAGES of whatever the root already is, and `medium` declares nothing at
all. The setting nudges the browser's answer; it never replaces it. That is also why this needs
no new layout mechanism: it moves the same lever a raised browser default already moves, and
`test_type_scale_follows_the_browser_default.py` has proved the app follows that lever since
`d8f4f4e`.

WHAT EACH STEP COSTS THE FIXED FRAME is asserted rather than assumed. `--sidebar-width`
(232/64px), `--icon-size` (16px), `--space-*` and the 720px breakpoint are all px ON PURPOSE, and
`tokens.css` says why. If the setting moved any of them, it would be doing something the browser
default does not, and the "same lever" claim would be false.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from playwright.sync_api import Page, expect

ROOT = Path(__file__).resolve().parents[2]
TOKENS = ROOT / "packages/truestill-app/src/truestill_app/static/tokens.css"

#: A browser default a low-vision user really sets, and **125%** of it - the largest root the app
#: can be asked to render, and past the 24px the existing type-scale tests prove.
#:
#: THIS READ 27 UNTIL 2026-08-13, AND THE GUARD BELOW CALLED ITSELF THE WORST CASE WHILE BEING
#: THREE PIXELS SHORT OF ONE. `f953b25` widened the band from +/-12.5% to 75%/125% - the first one
#: read as nothing happening - and `test_the_step_is_a_nudge_and_not_a_multiplier_that_compounds`
#: below states the resulting 18/24/30 in its own docstring. Nothing connected the two numbers, so
#: nothing went red: the property holds at both roots. A constant that is *derived* from another
#: and copied by hand is the thing to look for.
RAISED_DEFAULT_PX = 24
COMPOUND_WORST_CASE_PX = 30


def _body_px(ui: Page) -> float:
    return ui.eval_on_selector("body", "el => parseFloat(getComputedStyle(el).fontSize)")


def _pick(ui: Page, size: str) -> None:
    ui.click('.nav-item[data-screen="settings"]')
    ui.click(f'input[name="text-size"][value="{size}"]')
    ui.wait_for_timeout(200)


# --------------------------------------------------- where the "relative" claim is settled
#
# WHY THESE THREE ARE SOURCE ASSERTIONS AND NOT BROWSER ONES, recorded because I wrote them as
# browser tests first and they passed while proving nothing.
#
# The obvious test is "raise the root font-size, pick Large, assert the result is bigger". There
# is no way to raise it from inside the page except an inline style on `<html>` - and an inline
# style beats an external stylesheet rule on the same element. So the simulated default wins
# outright, the `:root[data-text-size]` rule never applies, and the assertion reads back the
# number the test itself just set. An ABSOLUTE implementation passes it identically. A real
# raised default is not an inline style; it is the root's inherited value, which is exactly what
# a percentage resolves against, and reproducing that needs Chromium launched with
# `--blink-settings=defaultFontSize=N` - a different browser, not a different page.
#
# So the claim is settled where it is actually made: in the declaration. `font-size: 125%` on
# the root CANNOT overwrite a browser default - resolving against it is what percent means.


def _steps() -> dict[str, str]:
    """Every `:root[data-text-size=...]` rule and the font-size it declares."""
    return dict(
        re.findall(
            r':root\[data-text-size="(\w+)"\]\s*\{\s*font-size:\s*([^;]+);',
            TOKENS.read_text("utf-8"),
        )
    )


def test_no_step_is_declared_as_a_length() -> None:
    """THE TEST THIS FILE EXISTS FOR. `font-size: 18px` for large hands a 24px reader 18px and
    calls it Large - not a preference, a reset."""
    steps = _steps()
    assert steps, "no text-size rules found at all"
    for name, value in steps.items():
        assert value.strip().endswith("%"), (
            f"{name} is declared as {value.strip()!r}, an absolute size - it would REPLACE the "
            "reader's own default rather than adjust it"
        )


def test_medium_declares_no_rule_at_all() -> None:
    """The property `d8f4f4e` shipped, and the reason `100%` is not written: it looks equivalent
    while making medium a value the app asserts rather than one it declines to."""
    assert "medium" not in _steps(), "medium declares a root size; it must declare nothing"


def test_medium_is_expressed_as_the_absence_of_the_attribute(ui: Page) -> None:
    """The client half of the same rule - the JS must REMOVE the attribute, not set it to
    `medium`, or the missing rule above would simply do nothing and look identical."""
    _pick(ui, "large")
    assert ui.evaluate("() => document.documentElement.dataset.textSize") == "large"

    _pick(ui, "medium")
    assert ui.evaluate("() => document.documentElement.dataset.textSize") is None


# --------------------------------------------------------------- the steps do what they say


def test_small_is_smaller_and_large_is_larger_than_medium(ui: Page) -> None:
    """The maintainer's own case is the SMALL one: browser zoom handles shrinking badly because
    it scales the layout with the type, and this must not."""
    _pick(ui, "medium")
    medium = _body_px(ui)
    _pick(ui, "small")
    small = _body_px(ui)
    _pick(ui, "large")
    large = _body_px(ui)

    assert small < medium, f"small ({small}px) is not below medium ({medium}px)"
    assert large > medium, f"large ({large}px) is not above medium ({medium}px)"


def test_each_step_is_big_enough_to_be_seen(ui: Page) -> None:
    """THE HALF THE FIRST BAND WAS MISSING, and the reason it shipped feeling broken.

    +/-12.5% (14/16/18) satisfies "small < medium < large" perfectly and reads as nothing
    happening - the maintainer changed the setting and reported no effect. "There is an
    ordering" was the only thing asserted, so a band too small to perceive passed.

    >= 20% either way. Chrome's own Small and Large are 12 and 20 against a 16 medium (25%);
    this leaves room to tune without letting it collapse back to invisible.
    """
    _pick(ui, "medium")
    medium = _body_px(ui)
    _pick(ui, "small")
    small = _body_px(ui)
    _pick(ui, "large")
    large = _body_px(ui)

    assert small <= medium * 0.8, f"small is {small}px against {medium}px - not a visible step"
    assert large >= medium * 1.2, f"large is {large}px against {medium}px - not a visible step"


def test_the_step_is_a_nudge_and_not_a_multiplier_that_compounds() -> None:
    """The other half of relative: it must not mean unbounded.

    The band was WIDENED from +/-12.5% to 75%/125% - 12 / 16 / 20px at the common default, which
    is Chrome's own Small and Large. The first band was too timid to read as a setting: the
    maintainer changed it and saw nothing. Bounded still, because these are percentages: a 24px
    default gives 18 / 24 / 30, large by choice rather than by accident.
    """
    for name, value in _steps().items():
        percent = float(value.strip().rstrip("%"))
        assert 70 <= percent <= 130, f"{name} is {percent}% - it compounds a raised default too far"


# ------------------------------------------------- what it costs the frame that is not type


def test_the_collapsed_rail_stays_64px_at_every_size(ui: Page) -> None:
    """`--sidebar-width` is px on purpose: a collapsed rail that grew with body text would clip
    its own icons, which are px for the same reason."""
    ui.click("#sidebar-toggle")
    ui.wait_for_timeout(200)
    widths = {}
    for size in ("small", "medium", "large"):
        _pick(ui, size)
        widths[size] = ui.eval_on_selector("#sidebar", "el => el.getBoundingClientRect().width")

    assert len({round(w) for w in widths.values()}) == 1, widths


def test_the_icon_size_does_not_move_either(ui: Page) -> None:
    sizes = {}
    for size in ("small", "medium", "large"):
        _pick(ui, size)
        sizes[size] = ui.eval_on_selector(".nav-item .ico", "el => getComputedStyle(el).fontSize")

    assert len(set(sizes.values())) == 1, sizes


def test_the_720px_breakpoint_fires_at_the_same_width_at_every_size(ui: Page) -> None:
    """A media query in px is not affected by the root font-size, so the top-bar switch happens
    at the same window width whatever the reader chose. Asserted because the alternative - `em`
    in the query - would move the breakpoint and surprise someone mid-resize."""
    for size in ("small", "medium", "large"):
        _pick(ui, size)
        ui.set_viewport_size({"width": 700, "height": 900})
        ui.wait_for_timeout(150)
        narrow = ui.eval_on_selector("#sidebar", "el => getComputedStyle(el).flexDirection")
        ui.set_viewport_size({"width": 900, "height": 900})
        ui.wait_for_timeout(150)
        wide = ui.eval_on_selector("#sidebar", "el => getComputedStyle(el).flexDirection")
        assert narrow != wide, f"the breakpoint did not fire at {size}"


def test_the_custody_strip_does_not_overflow_the_rail_at_the_compound_worst_case(
    ui: Page,
) -> None:
    """Large ON TOP OF an already-raised default is the biggest root the app can be asked for,
    and it is past the 24px that `test_type_scale_follows_the_browser_default` proves.

    The ROOT is set directly to the resulting 30px rather than composed from a default and a
    step. That is faithful for this question - overflow depends on the resulting size and not on
    how it was arrived at - and it is deliberately not used to claim anything about the
    composition itself, which the source assertions above own.
    """
    ui.evaluate(
        "() => document.documentElement.style.setProperty("
        f"'font-size', '{COMPOUND_WORST_CASE_PX}px', 'important')"
    )
    ui.wait_for_timeout(250)

    note = ui.evaluate(
        "() => { const k = document.querySelector('.custody .line .k');"
        " return k ? k.scrollWidth - k.clientWidth : 0; }"
    )
    assert note <= 2, f"the custody note overflows the rail by {note}px"
    body = ui.evaluate("() => document.body.scrollWidth - document.body.clientWidth")
    assert body <= 2, f"the page scrolls horizontally by {body}px"


# ----------------------------------------------------------------------------- persistence


def test_the_choice_survives_a_reload(ui: Page) -> None:
    """Per catalog, like the sidebar's collapse - so it travels with the library."""
    _pick(ui, "large")
    chosen = _body_px(ui)

    ui.reload()
    ui.wait_for_selector(".nav-item")
    ui.wait_for_timeout(400)

    assert _body_px(ui) == pytest.approx(chosen, abs=0.5)
    ui.click('.nav-item[data-screen="settings"]')
    expect(ui.locator('input[name="text-size"][value="large"]')).to_be_checked()
