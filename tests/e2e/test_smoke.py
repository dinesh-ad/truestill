"""Harness smoke: the app boots, authenticates, and renders."""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

#: THE MIGRATION'S EARLY-WARNING SYSTEM. This file belongs to no screen, so no screen's commit
#: carries it - and an island landing on a DIFFERENT screen changes the DOM around it without
#: touching a line here. `make e2e-shell` runs the set after every island; see
#: `docs/react-migration-plan.md`.
pytestmark = pytest.mark.shell


def test_the_app_boots_and_renders(ui: Page) -> None:
    expect(ui.locator(".wordmark")).to_contain_text("Truestill")
    # The inventory line was removed 2026-08-05; the strip states custody only.
    expect(ui.locator("#custody-line")).to_contain_text("nothing organized yet")
