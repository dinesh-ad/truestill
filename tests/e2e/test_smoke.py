"""Harness smoke: the app boots, authenticates, and renders."""

from __future__ import annotations

from playwright.sync_api import Page, expect


def test_the_app_boots_and_renders(ui: Page) -> None:
    expect(ui.locator(".wordmark")).to_contain_text("Truestill")
    expect(ui.locator("#custody-line")).to_contain_text("0 photos")
