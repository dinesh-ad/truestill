"""The shared visual pattern: components defined once, before any screen adopts them.

Nothing visible changes in the commit that introduces this. These guards exist so the pattern
cannot rot between being defined and being applied, and so the two rules that are easy to break
by accident - the metric's size, and what may live in the panel - are enforced rather than
remembered.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from playwright.sync_api import Page, expect

#: THE MIGRATION'S EARLY-WARNING SYSTEM. This file belongs to no screen, so no screen's commit
#: carries it - and an island landing on a DIFFERENT screen changes the DOM around it without
#: touching a line here. `make e2e-shell` runs the set after every island; see
#: `docs/react-migration-plan.md`.
pytestmark = pytest.mark.shell

STATIC = Path(__file__).resolve().parents[2] / "packages/truestill-app/src/truestill_app/static"
APP_CSS = (STATIC / "app.css").read_text(encoding="utf-8")

# Every run block in the app, by id prefix. `createProgress(prefix)` builds ids as
# `<prefix>-<suffix>`, so these are the contract the eight mounts have to keep.
RUN_PREFIXES = ("org", "ev", "rc", "verify", "bk", "mig", "bake", "undo")
RUN_PARTS = ("phase", "activity", "count", "bar", "meta", "cancel", "tally")

PANEL_WIDTH_MIN = 1336


def test_the_run_block_is_authored_once(ui: Page) -> None:
    """Eight structurally identical copies existed in the template; now there is one source."""
    templates = ui.eval_on_selector_all("template#tpl-run", "els => els.length")
    assert templates == 1, f"expected exactly one run-block template, found {templates}"

    # The mounts carry no markup of their own - if they did, the template is not the source.
    stray = ui.evaluate(
        "() => [...document.querySelectorAll('[data-run]')]"
        ".filter(el => el.children.length === 0).length"
    )
    assert stray == 0, f"{stray} run mounts are empty - the template did not mount into them"


def test_every_run_block_still_exists_with_its_original_ids(ui: Page) -> None:
    """The regression guard for the dedup: nothing visible may change.

    `createProgress()` and thirty top-level handlers address these by id. If mounting produced a
    different id, or ran after the handlers were wired, the job UI would silently stop updating -
    which no screenshot would show, because the markup would still look right.
    """
    missing = ui.evaluate(
        "(spec) => { const out = [];"
        " for (const p of spec.prefixes) for (const part of spec.parts) {"
        "   if (!document.getElementById(p + '-' + part)) out.push(p + '-' + part); }"
        " return out; }",
        {"prefixes": list(RUN_PREFIXES), "parts": list(RUN_PARTS)},
    )
    assert missing == [], f"run-block elements are missing after mounting: {missing}"


def test_the_mounted_blocks_are_wired_because_mounting_ran_first(ui: Page) -> None:
    """Mounting must precede the top-level handler wiring, and this says so directly.

    Deferring it to `DOMContentLoaded` throws on the first `$("...").onclick`, which aborts the
    rest of the script and leaves every later handler unbound. Sixteen tests in other files do
    fail on that, but they fail as a broken app; this names the cause.
    """
    errors: list[str] = []
    ui.on("pageerror", lambda e: errors.append(str(e)))
    ui.reload()
    ui.wait_for_selector(".nav-item")

    assert errors == [], f"the page threw during load: {errors}"
    wired = ui.evaluate(
        "() => ['org', 'bk', 'undo'].every(p => {"
        " const el = document.getElementById(p + '-cancel'); return !!(el && el.onclick); })"
    )
    assert wired, "a mounted Cancel button has no handler - mounting ran after the wiring"


def test_the_run_blocks_start_hidden_exactly_as_before(ui: Page) -> None:
    """They are revealed by a job starting, never by being mounted."""
    for prefix in RUN_PREFIXES:
        card = ui.locator(f"#{prefix}-card")
        assert card.count() == 1, f"#{prefix}-card is gone"
        expect(card).to_be_hidden()


def test_the_metric_size_token_exists_and_is_rem(ui: Page) -> None:
    """A metric must outrank everything else; 28px was not enough to be 'the biggest element'.

    ASSERT THE PROMISE, NOT THE STRING. This read `== "2.5rem"`, which is the *value* the token
    happened to have rather than the property it is here for - the token became fluid and the
    promise ("rem, so the root still governs, and 2.5rem at its floor") held throughout. §4's
    fourth member, applied to my own guard.
    """
    value = ui.evaluate(
        "() => getComputedStyle(document.documentElement).getPropertyValue('--type-3xl').trim()"
    )
    assert value, "--type-3xl resolves to nothing"
    assert "px" not in value, f"--type-3xl is pinned in px ({value!r}); the root cannot raise it"
    assert value.startswith(("2.5rem", "clamp(2.5rem")), (
        f"--type-3xl no longer floors at 2.5rem: {value!r}"
    )


def test_only_the_metric_uses_the_metric_size() -> None:
    """Aimed at the stylesheet, because the rule is 'nothing else', which no page can show.

    If a heading or a hero number quietly takes `--type-3xl`, the metric stops being the biggest
    element on the screen and the whole hierarchy argument goes with it.
    """
    # Comments stripped: a comment naming the token is not a use of it.
    stripped = re.sub(r"/\*.*?\*/", "", APP_CSS, flags=re.S)
    users = []
    for block in re.finditer(r"([^{}]+)\{([^}]*)\}", stripped):
        selector, body = block.group(1).strip(), block.group(2)
        if "--type-3xl" in body:
            users.append(selector.splitlines()[-1].strip())

    assert users, "nothing uses --type-3xl - the token is dead"
    assert users == [".metric-value"], f"--type-3xl is used outside the metric: {users}"


def test_the_panel_exists_and_costs_nothing_while_empty(ui: Page) -> None:
    """Reserved like the account slot: present in the shell, renders nothing until it has content."""
    panel = ui.locator("#panel")
    assert panel.count() == 1, "the panel region is missing from the shell"
    expect(panel).to_be_hidden()

    columns = ui.eval_on_selector(".app", "el => getComputedStyle(el).gridTemplateColumns")
    assert len(columns.split()) == 2, (
        f"an empty panel is taking a grid column: {columns!r} - it must cost nothing"
    )


def test_the_panel_can_hold_nothing_task_critical(ui: Page) -> None:
    """THE CONSTRAINT, ENFORCED RATHER THAN TRUSTED.

    The panel disappears below a wide viewport, so anything needed to finish a task must not live
    there. Written as a guard because 'we will remember' is exactly how a Save button ends up in a
    column that vanishes on a laptop.
    """
    # Anti-vacuity: with no panel in the DOM the query below is empty and this passes for the
    # wrong reason.
    assert ui.locator("#panel").count() == 1, "no panel in the shell - this guard would be empty"

    offenders = ui.evaluate(
        "() => [...document.querySelectorAll("
        "  '#panel button, #panel input, #panel select, #panel textarea,"
        "   #panel a[href], #panel [data-testid], #panel [onclick]')]"
        ".map(el => el.tagName.toLowerCase() + (el.id ? '#' + el.id : ''))"
    )
    assert offenders == [], (
        f"task-critical elements are inside the panel: {offenders}. The panel is supplementary "
        "and is not rendered on narrow windows; nothing needed to act may live in it."
    )

    # AND THE GUARD ITSELF MUST BE ABLE TO FAIL. While the panel is empty the assertion above is
    # true by definition, so it would sit green until the day someone fills the panel - which is
    # the day it needs to already work. Plant an offender and confirm the query sees it.
    planted = ui.evaluate(
        "() => { const p = document.getElementById('panel');"
        " p.innerHTML = '<button id=\"planted\">Save</button>';"
        " const hits = [...document.querySelectorAll('#panel button, #panel input, #panel select,"
        "   #panel textarea, #panel a[href], #panel [data-testid], #panel [onclick]')]"
        "   .map(el => el.id);"
        " p.innerHTML = ''; return hits; }"
    )
    assert planted == ["planted"], (
        f"the panel guard does not see a planted control ({planted}) - it would pass forever"
    )


def test_the_panel_is_absent_on_anything_narrower_than_a_wide_window(ui: Page) -> None:
    """It drops entirely rather than being squeezed or stacked under the content."""
    assert ui.locator("#panel").count() == 1, "no panel in the shell - this guard would be empty"

    # The panel MUST have content for this to mean anything: `:empty` hides it at every width,
    # so an empty panel satisfies "hidden when narrow" without any breakpoint existing.
    ui.evaluate("() => { document.getElementById('panel').innerHTML = '<p>fact</p>'; }")

    ui.set_viewport_size({"width": PANEL_WIDTH_MIN + 200, "height": 900})
    ui.wait_for_timeout(150)
    expect(ui.locator("#panel")).to_be_visible()
    wide = ui.eval_on_selector(".app", "el => getComputedStyle(el).gridTemplateColumns")
    assert len(wide.split()) == 3, f"a filled panel gets no column on a wide window: {wide!r}"

    ui.set_viewport_size({"width": PANEL_WIDTH_MIN - 40, "height": 900})
    ui.wait_for_timeout(150)
    expect(ui.locator("#panel")).to_be_hidden()

    columns = ui.eval_on_selector(".app", "el => getComputedStyle(el).gridTemplateColumns")
    assert len(columns.split()) == 2, f"the panel still holds a column when narrow: {columns!r}"
