"""A background load that fails reaches the banner deliberately, not through the backstop.

**Why this is not the same as "the banner appears".** It appeared before this change too - the
last-resort `unhandledrejection` listener catches anything `guarded()` does not wrap, and screen
loads were the largest category it did not wrap. So an assertion that only checks the banner is
**vacuous here**: it passes identically with and without the fix, and would have gone on passing
if the routing were deleted tomorrow.

What actually changed is *which path reports it*. These tests assert the banner appears **and**
that the backstop never fired - the second half is the whole point, and it is what turns red if
`.catch(reportLoadFailure)` is removed from a load.

The distinction is not pedantry. `Promise.allSettled` is about to be introduced at these sites
for the readiness signal, and under `allSettled` nothing rejects - so the backstop would stop
firing and, without a deliberate route, the banner would **silently stop appearing at all**.
This commit establishes the reporting path that readiness then depends on.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

#: THE MIGRATION'S EARLY-WARNING SYSTEM. This file belongs to no screen, so no screen's commit
#: carries it - and an island landing on a DIFFERENT screen changes the DOM around it without
#: touching a line here. `make e2e-shell` runs the set after every island; see
#: `docs/react-migration-plan.md`.
pytestmark = pytest.mark.shell

#: Installed before any app code runs, so a rejection reaching the backstop is recorded rather
#: than merely shown. `add_init_script` needs a load to take effect, hence the `reload()` at each
#: call site.
_RECORD_BACKSTOP = """
window.__backstop = [];
window.addEventListener("unhandledrejection", (e) => window.__backstop.push(String(e.reason)));
"""


def _fail(route: object) -> None:
    route.fulfill(status=500, content_type="text/plain", body="boom")  # type: ignore[attr-defined]


def _arm(ui: Page, url: str) -> None:
    ui.route(url, _fail)
    ui.add_init_script(_RECORD_BACKSTOP)
    ui.reload()


def test_a_failing_screen_load_reports_without_reaching_the_backstop(ui: Page) -> None:
    """Stats' one load, refused. The banner is the visible half; `__backstop` is the real one."""
    _arm(ui, "**/api/library/stats")

    ui.click('button[data-screen="stats"]')

    expect(ui.locator("#global-error")).to_be_visible()
    expect(ui.locator("#global-error")).to_contain_text("500")
    # Read only after the assertion above has become true - the failure has certainly been
    # handled by now, so an empty list means the backstop was not the thing that handled it.
    assert ui.evaluate("window.__backstop") == []


def test_a_failing_boot_load_reports_without_reaching_the_backstop(ui: Page) -> None:
    """The shell's six run at module level, outside any handler - the case the backstop was
    written for, and the one it should stop being needed for."""
    _arm(ui, "**/api/library/status")

    expect(ui.locator("#global-error")).to_be_visible()
    expect(ui.locator("#global-error")).to_contain_text("500")
    assert ui.evaluate("window.__backstop") == []


def test_the_backstop_still_catches_what_nothing_anticipated(ui: Page) -> None:
    """The other direction, so the change above cannot be read as "the backstop is retired".

    It is still the route for an unforeseen rejection, and this proves the recorder itself works -
    without it, `__backstop == []` in the tests above would also be satisfied by a listener that
    never fires for any reason at all.
    """
    ui.add_init_script(_RECORD_BACKSTOP)
    ui.reload()

    # A statement body, not an expression: `evaluate` AWAITS whatever it is given, so returning
    # the rejected promise hands it to Playwright as a call failure and it never goes unhandled
    # in the page at all. Discarding it is what makes the rejection floating, which is the case
    # under test.
    ui.evaluate("() => { Promise.reject(new Error('nothing anticipated this')); }")

    expect(ui.locator("#global-error")).to_contain_text("nothing anticipated this")
    assert ui.evaluate("window.__backstop") == ["Error: nothing anticipated this"]
