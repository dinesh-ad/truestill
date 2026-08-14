"""A tab older than the server has to say so, because a missing control cannot ask to be noticed.

`_static_fingerprint` already warns in the other direction: it fires when the SERVER process is
older than the files on disk. Nothing fired when the open PAGE was older than the server, and
the app is a single page - navigating between screens never reloads it. So an upgrade lands, the
tab keeps running the JS it loaded hours ago, and a new control simply does not exist. There is
no error, nothing to click, and no route by which a user would learn to reload.

That is what "text size does nothing" looks like from the other side of the screen.

THE CHECK COSTS NO REQUEST. Every action already calls the API, so the server stamps its
fingerprint on each JSON response and the page compares it with the one baked into its own HTML.
No polling, no timer, no endpoint of its own.
"""

from __future__ import annotations

import json

import pytest
from playwright.sync_api import Page, expect

#: THE MIGRATION'S EARLY-WARNING SYSTEM. This file belongs to no screen, so no screen's commit
#: carries it - and an island landing on a DIFFERENT screen changes the DOM around it without
#: touching a line here. `make e2e-shell` runs the set after every island; see
#: `docs/react-migration-plan.md`.
pytestmark = pytest.mark.shell


def _stamp(ui: Page, fingerprint: str) -> None:
    """Answer one API call with a DIFFERENT fingerprint - what a restarted, upgraded server does."""

    def handler(route):  # type: ignore[no-untyped-def]
        route.fulfill(
            status=200,
            content_type="application/json",
            headers={"x-truestill-static": fingerprint},
            body=json.dumps({"collapsed": False}),
        )

    ui.route("**/api/sidebar/settings", handler)


def test_the_page_carries_the_fingerprint_it_was_served_with(ui: Page) -> None:
    baked = ui.evaluate("() => window.TRUESTILL_STATIC")
    assert baked, "the page does not know its own version"
    assert len(baked) >= 8, baked


def test_a_matching_fingerprint_says_nothing(ui: Page) -> None:
    """CRY-WOLF HALF, and the one that matters most: this banner is on every response path, so
    a false positive would follow a user around the whole app."""
    ui.reload()
    ui.wait_for_selector(".nav-item")
    ui.wait_for_timeout(600)

    expect(ui.locator("[data-testid='page-stale']")).to_have_count(0)


def test_a_newer_server_tells_the_open_tab_to_reload(ui: Page) -> None:
    _stamp(ui, "0000000000000000000000000000000000000000000000000000000000000000")
    ui.click("#sidebar-toggle")
    ui.wait_for_timeout(600)

    banner = ui.locator("[data-testid='page-stale']")
    expect(banner).to_be_visible()
    text = banner.inner_text().lower()
    assert "reload" in text or "refresh" in text, text


def test_the_warning_offers_the_action_rather_than_describing_it(ui: Page) -> None:
    """A banner that says "reload the page" and makes you find the key is a worse banner."""
    _stamp(ui, "1111111111111111111111111111111111111111111111111111111111111111")
    ui.click("#sidebar-toggle")
    ui.wait_for_timeout(600)

    expect(ui.locator("[data-testid='page-stale-reload']")).to_be_visible()


def test_it_is_said_once_however_many_calls_follow(ui: Page) -> None:
    """Every response carries the header, so a naive implementation stacks one banner per call."""
    _stamp(ui, "2222222222222222222222222222222222222222222222222222222222222222")
    for _ in range(3):
        ui.click("#sidebar-toggle")
        ui.wait_for_timeout(250)

    assert ui.locator("[data-testid='page-stale']").count() == 1
