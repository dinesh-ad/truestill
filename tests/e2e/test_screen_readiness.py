"""`data-ready` tells the truth, or these fail.

**The failure this guards against is worse than the one it fixes.** A readiness signal that flips
to "ready" too early is worse than no signal at all: every test in the suite would then wait on a
lie and pass, and the suite would go quiet about a whole class of defect while looking healthier
than before. So the tests here are aimed at the flag itself, not at the screens.

**Where the proof is weak, said out loud rather than discovered later:**

1. *A load that resolves and writes the DOM a microtask later* has **no reliable test here.** A
   write deferred by `requestAnimationFrame` or `setTimeout(0)` lands within a frame, and the
   one-shot read below is a separate round trip - so the deferred write almost certainly arrives
   first and the test passes against a live defect. That case is defended **statically**, in
   `packages/truestill-app/tests/test_screen_readiness_is_honest.py`, by a text scan, not a parser.
2. *Nothing proves the flag is complete* - that it covers every write a screen owes. A load added
   outside `SCREEN_LOADS` is invisible to all of this. What makes it unlikely is that `showScreen`
   no longer branches per screen, so there is no natural place to put one.
3. *The "not ready yet" assertions are licensed negatives, not eliminated ones.* Asserting
   `data-ready != "ready"` is asserting something already true from the markup. Each one is
   therefore anchored first on `.active`, which BECOMES true - so the negative is only read once
   the click has demonstrably been processed. That is weaker than a positive, and it is the best
   available for "has not happened yet".
"""

from __future__ import annotations

import re
from typing import Any

import pytest
from playwright.sync_api import Page, expect

_ACTIVE = re.compile(r"\bactive\b")

#: The screens whose open fires at least one unconditional request. `import` and `find` fire none
#: (they are covered by the uniformity guard instead), and `events` is conditional - it needs a
#: path in the field before it asks anything, so it gets its own test below.
_LOADING_SCREENS = [
    ("organize", "**/api/organize/undo"),
    ("backups", "**/api/drives"),
    ("stats", "**/api/library/stats"),
    ("settings", "**/api/layout"),
]


def _hold(ui: Page, url: str) -> list[Any]:
    """Hold the next request to ``url`` open, and hand back the handle that releases it.

    The route handler stores the route and returns without fulfilling, so the request stays
    pending while the driver stays responsive. A handler that slept instead would block the
    same connection the assertions travel over, and nothing could be observed mid-flight.
    """
    held: list[Any] = []
    # The lambda is required, not stylistic: Playwright stamps an attribute onto the handler it
    # is given, and a built-in method (`held.append`) has no `__dict__` to stamp - it raises
    # AttributeError at route registration. Ruff's PLW0108 is a false positive here.
    ui.route(url, lambda route: held.append(route))  # noqa: PLW0108
    return held


def _release(held: list[Any]) -> None:
    """Let the held request through.

    No polling loop is needed, and a sleep would be wrong: the auto-retrying assertions that run
    before every call site pump the driver's message loop for up to two seconds, which is when
    the route handler actually fires. If `held` is still empty by here, the load never happened -
    a missing registry entry or a wrong glob - and that deserves to be said, not waited out.

    Every held route is drained, not just the first. One screen holds more than one: filling
    `#ev-source` fires a `change` listener that refreshes the same panel (app.js), so the field
    and the screen open each ask once. Releasing only the first leaves the screen at "loading"
    for a reason that has nothing to do with the flag being wrong.
    """
    assert held, "the load never fired: check the SCREEN_LOADS entry and the URL pattern"
    for route in held:
        route.continue_()
    held.clear()


@pytest.mark.parametrize(("screen", "url"), _LOADING_SCREENS)
def test_a_screen_is_not_ready_while_its_load_is_outstanding(
    ui: Page, screen: str, url: str
) -> None:
    """Table-driven on purpose. Proving the mechanism on one screen and assuming the other three
    is exactly how a `null` gets into a registry and nobody notices."""
    held = _hold(ui, url)
    section = ui.locator(f"#screen-{screen}")

    ui.click(f'button[data-screen="{screen}"]')

    # The becomes-true anchor that licenses the negative below: the click has been processed and
    # `settleScreen` has run its synchronous half.
    expect(section).to_have_class(_ACTIVE)
    expect(section).to_have_attribute("data-ready", "loading")
    expect(section).not_to_have_attribute("data-ready", "ready", timeout=2_000)

    _release(held)
    expect(section).to_have_attribute("data-ready", "ready")


def test_events_waits_for_the_load_it_only_sometimes_makes(ui: Page) -> None:
    """`refreshUndoAffordance` returns without asking anything when the path field is empty, so
    Trips is the one screen whose readiness has two shapes. Both must be honest: the empty case
    settles anyway (it still writes - it clears the panel), and the case that DOES fetch waits."""
    section = ui.locator("#screen-events")

    ui.click('button[data-screen="events"]')
    expect(section).to_have_attribute("data-ready", "ready")

    held = _hold(ui, "**/api/migrate/undo*")
    ui.fill("#ev-source", "/anything")
    ui.click('button[data-screen="organize"]')
    ui.click('button[data-screen="events"]')

    expect(section).to_have_class(_ACTIVE)
    expect(section).not_to_have_attribute("data-ready", "ready", timeout=2_000)

    _release(held)
    expect(section).to_have_attribute("data-ready", "ready")


def test_ready_means_the_writes_have_landed_read_the_dangerous_way(ui: Page) -> None:
    """**The most valuable test here, and it is written in the unsafe idiom deliberately.**

    `eval_on_selector` does not auto-wait. Every other test in the suite that reads this way is a
    latent race; this one is a race ON PURPOSE, pointed at the flag. If `data-ready` ever flips
    before the DOM writes it claims to cover, this is deterministically red - which turns "an
    early flag" from a flake somewhere else in the suite into one named failing test here.

    The stats assertion is the strongest of the three, because the wrong answer is a SPECIFIC
    STRING that only the pre-load state can produce. An emptiness check would be far weaker:
    several regions render `innerHTML = ""` when they load successfully with nothing to show, so
    empty is a real loaded state and proves nothing.
    """
    stats = ui.locator("#screen-stats")
    ui.click('button[data-screen="stats"]')
    expect(stats).to_have_attribute("data-ready", "ready")

    # `#stats-result`'s placeholder is written by JS, so seeing it here means ready led the write.
    assert "Loading library stats" not in ui.eval_on_selector(
        "#stats-result", "el => el.textContent"
    )

    # The shell half: no screen may claim ready while the rail still says it is checking. Without
    # this, a per-screen flag that ignored `shellLoads` would pass everything above.
    assert ui.eval_on_selector("#custody-line", "el => el.textContent") != "Checking your library…"


def test_returning_to_a_screen_clears_ready_before_it_reloads(ui: Page) -> None:
    """The stale-true case, and the only test that catches a missing synchronous reset.

    Without the reset, coming back to a screen finds the previous visit's "ready" still standing
    while its loads re-run - a flag that is true about the wrong visit. Every other test here
    passes with the reset removed.
    """
    backups = ui.locator("#screen-backups")
    ui.click('button[data-screen="backups"]')
    expect(backups).to_have_attribute("data-ready", "ready")

    held = _hold(ui, "**/api/drives")
    ui.click('button[data-screen="find"]')
    ui.click('button[data-screen="backups"]')

    expect(backups).to_have_class(_ACTIVE)
    expect(backups).to_have_attribute("data-ready", "loading")

    _release(held)
    expect(backups).to_have_attribute("data-ready", "ready")


def test_a_failed_load_says_failed_and_does_not_say_ready(ui: Page) -> None:
    """`failed` is terminal and is NOT `ready`. The last assertion is the honest half: the region
    is still showing its placeholder, and the flag's whole job is to say so rather than to call
    that state ready."""
    ui.route(
        "**/api/library/stats",
        lambda route: route.fulfill(status=500, content_type="text/plain", body="boom"),
    )
    stats = ui.locator("#screen-stats")

    ui.click('button[data-screen="stats"]')

    expect(stats).to_have_attribute("data-ready", "failed")
    expect(stats).to_have_attribute("data-ready-error", re.compile("500"))
    expect(ui.locator("#global-error")).to_be_visible()
    # Why `failed` is not `ready`: this region is still lying, and the flag admits it.
    expect(ui.locator("#stats-result")).to_contain_text("Loading library stats")


def test_a_screen_with_no_loads_of_its_own_still_becomes_ready(ui: Page) -> None:
    """`import` and `find` fetch nothing on open. They must still carry the signal and still wait
    for the shell - a flag present on some screens and absent on others is worse than none,
    because a caller cannot tell "not ready" from "never says"."""
    for screen in ("import", "find"):
        ui.click(f'button[data-screen="{screen}"]')
        expect(ui.locator(f"#screen-{screen}")).to_have_attribute("data-ready", "ready")


def test_the_screen_that_ships_open_becomes_ready_without_a_click(ui: Page) -> None:
    """Organize ships `class="screen active"` and `showScreen` is never called at boot, so this is
    the one screen whose readiness comes from the boot path rather than from navigation. Left out,
    the screen a user actually lands on would sit at "loading" for the life of the page."""
    expect(ui.locator("#screen-organize")).to_have_attribute("data-ready", "ready")
