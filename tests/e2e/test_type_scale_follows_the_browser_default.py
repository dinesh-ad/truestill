"""A raised browser default font size must actually enlarge the app.

Someone with low vision sets that preference once, globally. Absolute `px` tokens ignore it, so
the app stays small and the only recourse is per-profile zoom. Zoom is not a substitute: it is a
per-site gesture repeated on every machine, and it is not the setting the user already expressed.

Raising the root element's font-size is how that preference reaches a page, so these tests raise
it and assert the app followed.
"""

from __future__ import annotations

import pytest
from e2e_support import open_screen
from playwright.sync_api import Page

#: THE MIGRATION'S EARLY-WARNING SYSTEM. This file belongs to no screen, so no screen's commit
#: carries it - and an island landing on a DIFFERENT screen changes the DOM around it without
#: touching a line here. `make e2e-shell` runs the set after every island; see
#: `docs/react-migration-plan.md`.
pytestmark = pytest.mark.shell

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
        " return ['sm','base','lg','display','3xl'].map("
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
        " return ['sm','base','lg','display','3xl'].map("
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


# ------------------------------------------------------------------------- one scale, six steps

#: The ruling of 2026-09-10, in the order the scale runs. Six steps, and the ceiling is six.
#: ⚠ FIVE since 2026-09-10, was six. `xs` (13) left: against `sm` (14) it is a 7% difference,
#: invisible as a size, and what actually separated the two on screen was case and weight. A step
#: no reader can tell from its neighbour is not a step.
SCALE = {"sm": 14.0, "base": 16.0, "lg": 18.0, "display": 32.0, "3xl": 40.0}


def test_the_scale_is_six_steps_at_their_ruled_sizes(ui: Page) -> None:
    """⚠ **NOTHING GUARDED THE SCALE, WHICH IS HOW IT REACHED EIGHT SIZES.**

    Measured before the ruling, on one screen: 11, 12, 12.09, 14, 14.11, 16.12, 18 and 32.25 -
    where 12/12.09 and 14/14.11 are one step rendered at the rail's floor and at the fluid size.
    Eight steps is not a hierarchy, it is the absence of one, because no two neighbours differ
    enough to read as different. A token could be added at any time and no test would notice.

    Asserted at the FLOOR (a narrow viewport), because that is where the ruling's numbers are
    stated - the clamps scale every step by the same +12.5% above 1366px, so pinning the floor
    pins the scale without pinning the fluid band.
    """
    ui.set_viewport_size({"width": 1000, "height": 900})
    ui.wait_for_timeout(150)

    probe = (
        "(names) => Object.fromEntries(names.map(n => {"
        " const el = document.createElement('span');"
        " el.style.cssText = 'position:absolute;visibility:hidden;font-size:var(--type-'+n+')';"
        " document.body.appendChild(el);"
        " const px = parseFloat(getComputedStyle(el).fontSize);"
        " el.remove(); return [n, px]; }))"
    )
    sizes = ui.evaluate(probe, list(SCALE))

    for name, expected in SCALE.items():
        assert abs(sizes[name] - expected) < 0.5, (
            f"--type-{name} is {sizes[name]}px, ruled {expected}px. All: {sizes}"
        )

    # And no SEVENTH step crept back in beside them.
    declared = ui.evaluate(
        "() => [...document.styleSheets].flatMap(s => { try { return [...s.cssRules]; }"
        " catch { return []; } })"
        ".filter(r => r.selectorText === ':root')"
        ".flatMap(r => [...r.style]).filter(n => n.startsWith('--type-'))"
    )
    # `--type-*-min` are the floors each clamp is BUILT from, not steps of their own - the rail
    # references them so it cannot drift from the scale. A step is a token without that suffix.
    steps_only = {n for n in declared if not n.endswith("-min")}
    extra = sorted(steps_only - {f"--type-{n}" for n in SCALE})
    assert not extra, (
        f"the scale has grown past its five steps: {extra}. Four to six sizes was the ruling; a "
        "seventh step is one no reader can tell from its neighbours."
    )


def test_nothing_a_person_reads_is_set_below_twelve_pixels(ui: Page) -> None:
    """The floor the product's accessibility claim rests on, asserted on rendered text.

    ⚠ **It was broken by a raw `font-size: 11px` on `.step-dot`** - below the floor, and in px, so
    neither the text-size setting nor a raised browser default could reach it. Asserted on what
    renders rather than on the tokens, because the defect was not a token.
    """
    smallest = ui.evaluate(
        "() => { let worst = null;"
        " for (const e of document.querySelectorAll('.screen.active *, .sidebar *')) {"
        "   if (!e.offsetParent) continue;"
        "   const own = [...e.childNodes].some(n => n.nodeType === 3 && n.textContent.trim());"
        "   if (!own) continue;"
        "   const px = parseFloat(getComputedStyle(e).fontSize);"
        "   if (!worst || px < worst.px) worst = {px, cls: e.className.toString(), tag: e.tagName};"
        " } return worst; }"
    )
    assert smallest, "no rendered text was measured, so this asserted nothing"
    assert smallest["px"] >= 12, (
        f"{smallest['tag']}.{smallest['cls']} renders at {smallest['px']}px, below the 12px floor"
    )


def test_the_rail_runs_the_same_scale_as_the_page(ui: Page) -> None:
    """⚠ **THE RAIL WAS A SECOND SCALE, and it had already gone stale.**

    `.sidebar` drops the `vw` term from each step - correctly, since a 232px frame has no
    viewport relationship to express - but it did so by RE-TYPING the four floors as literals.
    The moment `--type-xs` moved 12 -> 13 under the one-scale ruling, the page took 13.1px and the
    rail's section labels stayed at 12, silently, because a copy cannot follow its source.

    The rail references `--type-*-min` now, so this asserts the two agree by construction. A step
    re-typed as a literal in the rail passes only while someone keeps the two in step by hand,
    which is the arrangement that just failed.
    """
    ui.set_viewport_size({"width": 2400, "height": 900})  # wide, so the page's clamps are ABOVE
    ui.wait_for_timeout(150)  # their floors and a copy would show

    probe = (
        "(names) => Object.fromEntries(names.map(n => {"
        " const mk = (host, value) => { const el = document.createElement('span');"
        "   el.style.cssText = 'position:absolute;visibility:hidden;font-size:' + value;"
        "   host.appendChild(el); const px = parseFloat(getComputedStyle(el).fontSize);"
        "   el.remove(); return px; };"
        " const rail = document.querySelector('.sidebar');"
        " return [n, {rail: mk(rail, `var(--type-${n})`),"
        "             floor: mk(document.body, `var(--type-${n}-min)`)}]; }))"
    )
    sizes = ui.evaluate(probe, ["sm", "base", "lg"])

    for name, pair in sizes.items():
        assert pair["floor"], f"--type-{name}-min resolves to nothing - the floor token is gone"
        assert abs(pair["rail"] - pair["floor"]) < 0.01, (
            f"the rail renders --type-{name} at {pair['rail']}px against the scale's floor of "
            f"{pair['floor']}px - the rail is running its own copy of the scale"
        )


# ------------------------------------------------------- a control never shouts over its labels

#: Find's search field, the one deliberate exception. `test_the_search_field_leads_the_screen`
#: asserts it in as many words - *"Spotlight, not a dashboard: the input is the biggest thing
#: here"* - so it is named here rather than silently skipped by a size threshold.
LEADS_ITS_SCREEN = "where-term"


def test_no_form_control_is_set_larger_than_the_labels_around_it(ui: Page) -> None:
    """⚠ **A PATH IS A VALUE THE USER SUPPLIES, NOT PROSE THEY READ.**

    Measured 2026-09-11, before the fix: every `.input` computed **16.12px** - body size -
    against a **14.11px** surround of labels, hints and buttons, and the field is monospace,
    which reads larger still at the same nominal size. The string the user types was the largest
    text in the form, on Organize, Trips, Import, Backups and Settings alike.

    ⚠ **THE REFERENCE IS THE SURROUND, NOT BODY, AND THE FIRST VERSION OF THIS TEST GOT THAT
    WRONG.** It asserted `size <= body` - and body is `--type-base`, which is exactly what the
    defect was, so a field restored to 16px passed it. The mutation caught it: reverting `.input`
    to `--type-base` left the test green, proving nothing. A control is secondary type; the rule
    is that it sits at or below `--type-sm`, the step the labels, hints and buttons take.

    Stated against the TOKEN rather than a pixel, so it follows the scale if the scale moves.
    Swept across every screen, because the defect was in a shared `.input` rule and a test that
    looked at one screen would have proved nothing about the others.
    """
    ui.set_viewport_size({"width": 1440, "height": 900})
    secondary = float(
        ui.evaluate(
            "() => { const el = document.createElement('span');"
            " el.style.cssText = 'position:absolute;visibility:hidden;font-size:var(--type-sm)';"
            " document.body.appendChild(el);"
            " const px = parseFloat(getComputedStyle(el).fontSize); el.remove(); return px; }"
        )
    )
    assert secondary > 0, "--type-sm resolves to nothing, so there is no ceiling to compare against"

    probe = (
        "() => [...document.querySelectorAll("
        "  '.screen.active input, .screen.active select, .screen.active textarea')]"
        ".filter(e => e.offsetParent && !['checkbox','radio'].includes(e.type))"
        ".map(e => [e.id || e.name || e.tagName, parseFloat(getComputedStyle(e).fontSize)])"
    )

    measured: list[tuple[str, str, float]] = []
    for screen in ("organize", "events", "import", "backups", "find", "stats", "settings"):
        open_screen(ui, screen)
        ui.wait_for_timeout(200)
        for name, size in ui.evaluate(probe):
            measured.append((screen, name, float(size)))

    # Anti-vacuity: the filter drops hidden controls and the two input types that render no text
    # of their own, so an empty sweep would satisfy every assertion below having seen nothing.
    assert len(measured) >= 10, f"only {len(measured)} controls were measured across seven screens"
    assert any(name == LEADS_ITS_SCREEN for _screen, name, _size in measured), (
        f"{LEADS_ITS_SCREEN} was never reached, so the exception below is not being exercised"
    )

    too_big = [
        (screen, name, size)
        for screen, name, size in measured
        if size > secondary + 0.5 and name != LEADS_ITS_SCREEN
    ]
    assert not too_big, (
        "form controls set larger than the labels around them - the value the user types "
        f"outranks the words explaining it (--type-sm is {secondary:.2f}px): "
        + ", ".join(f"{s}/{n} at {px:.2f}px" for s, n, px in too_big)
    )
