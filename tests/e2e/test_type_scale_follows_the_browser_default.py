"""A raised browser default font size must actually enlarge the app.

Someone with low vision sets that preference once, globally. Absolute `px` tokens ignore it, so
the app stays small and the only recourse is per-profile zoom. Zoom is not a substitute: it is a
per-site gesture repeated on every machine, and it is not the setting the user already expressed.

Raising the root element's font-size is how that preference reaches a page, so these tests raise
it and assert the app followed.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page

# Rail chrome, a main-column control, and body copy: if any of these is pinned in px the
# preference is only partly honoured, which is the state worth failing on.
PROBES = (
    ("body", "body copy"),
    (".nav-item", "rail nav item"),
    (".field > label", "main-column control label"),
    (".custody .line", "custody strip"),
)

ROOT_PX = 20  # a 25% raise: modest, and what a browser's "Large" preset is close to


def _sizes(ui: Page) -> dict[str, float]:
    return ui.evaluate(
        "(sels) => Object.fromEntries(sels.map(s => {"
        " const el = document.querySelector(s);"
        " return [s, el ? parseFloat(getComputedStyle(el).fontSize) : null]; }))",
        [s for s, _ in PROBES],
    )


def test_the_app_grows_when_the_browser_default_is_raised(ui: Page) -> None:
    """The defect this file exists for. With px tokens every probe is unchanged."""
    ui.wait_for_selector(".nav-item")
    before = _sizes(ui)

    ui.evaluate(f"document.documentElement.style.fontSize = '{ROOT_PX}px'")
    ui.wait_for_timeout(150)
    after = _sizes(ui)

    unmoved = [
        f"{label} ({sel}) stayed at {before[sel]}px"
        for sel, label in PROBES
        if before[sel] is not None and after[sel] == before[sel]
    ]
    assert not unmoved, (
        "raising the browser's default font size changed nothing:\n  "
        + "\n  ".join(unmoved)
        + "\nThe type scale is pinned in px, so a preference the user already set is ignored."
    )


def test_the_raise_is_proportional_not_merely_nonzero(ui: Page) -> None:
    """A single hard-coded rem among px tokens would satisfy the test above."""
    ui.wait_for_selector(".nav-item")
    before = _sizes(ui)
    ui.evaluate(f"document.documentElement.style.fontSize = '{ROOT_PX}px'")
    ui.wait_for_timeout(150)
    after = _sizes(ui)

    expected = ROOT_PX / 16
    for sel, label in PROBES:
        if before[sel] is None:
            continue
        ratio = after[sel] / before[sel]
        assert abs(ratio - expected) < 0.02, (
            f"{label} scaled {ratio:.3f}x, expected {expected:.3f}x "
            f"({before[sel]}px -> {after[sel]}px)"
        )


def test_no_text_token_is_declared_in_px(ui: Page) -> None:
    """Aimed at the tokens themselves, so a px value cannot creep back unnoticed."""
    declared = ui.evaluate(
        "() => { const cs = getComputedStyle(document.documentElement);"
        " return ['xs','sm','base','lg','xl','2xl'].map("
        "   n => [n, cs.getPropertyValue('--type-' + n).trim()]); }"
    )
    in_px = [f"--type-{n}: {v}" for n, v in declared if v.endswith("px")]
    assert not in_px, f"type tokens still declared in px: {in_px}"
    assert declared, "no --type-* tokens found at all"


def test_every_step_of_the_scale_actually_resolves(ui: Page) -> None:
    """THE HOLE THE TEST ABOVE HAD, closed by the defect that walked through it.

    A stray `*/` in `tokens.css` ended a comment two lines early, and CSS error recovery ate the
    declaration that followed - `--type-xs` simply stopped existing. Nothing failed: `ruff`,
    `mypy` and 1802 pytest cases do not read a stylesheet, and the test above passed because an
    EMPTY value does not end in `px`. What noticed was two unrelated browser tests, by three
    pixels of top-bar height.

    A missing token is not a smaller token. It is no rule at all, so the element falls back to
    whatever it inherits - which is how a 12px label silently became body size.
    """
    resolved = ui.evaluate(
        "() => { const cs = getComputedStyle(document.documentElement);"
        " return ['xs','sm','base','lg','xl','2xl','3xl'].map("
        "   n => [n, cs.getPropertyValue('--type-' + n).trim()]); }"
    )
    missing = [f"--type-{n}" for n, v in resolved if not v]
    assert not missing, (
        f"type token(s) resolve to nothing: {missing}. A declaration was dropped - most likely "
        "swallowed by a malformed comment above it."
    )


@pytest.mark.parametrize("root_px", [20, 24])
def test_nothing_overflows_its_container_at_a_raised_default(ui: Page, root_px: int) -> None:
    """The scale change must not simply move the failure into a clipped container.

    `#layout-preset` carries a 78-character option and `.custody .line .k` carries a filesystem
    path - an unbreakable token. Both are the cases that actually overflow when text grows.
    """
    ui.wait_for_selector(".nav-item")
    ui.evaluate(f"document.documentElement.style.fontSize = '{root_px}px'")
    ui.wait_for_timeout(200)

    note = ui.evaluate(
        "() => { const k = document.querySelector('.custody .line .k');"
        " return k ? k.scrollWidth - k.clientWidth : 0; }"
    )
    assert note <= 2, f"the custody note overflows the rail by {note}px at a {root_px}px root"

    ui.click('.nav-item[data-screen="settings"]')
    ui.wait_for_selector("#layout-preset")
    ui.wait_for_timeout(200)
    select = ui.evaluate(
        "() => { const s = document.querySelector('#layout-preset');"
        " return s.getBoundingClientRect().width - s.parentElement.getBoundingClientRect().width; }"
    )
    assert select <= 2, f"the layout select overflows its field by {select:.0f}px at {root_px}px"

    body = ui.evaluate("() => document.body.scrollWidth - document.body.clientWidth")
    assert body <= 2, f"the page scrolls horizontally by {body}px at a {root_px}px root"
