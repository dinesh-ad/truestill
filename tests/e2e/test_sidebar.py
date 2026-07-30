"""Collapsible sidebar (backlog fff).

Real Playwright flows. Each behaviour was broken once while authoring (persist skipped,
tooltip CSS removed, custody line left visible in the rail, keyboard blur after toggle)
and restored so the assertion fails against the defect it names.
"""

from __future__ import annotations

import re

from playwright.sync_api import Page, expect


def _wait_expanded(ui: Page) -> None:
    expect(ui.locator("#sidebar")).to_have_attribute("data-collapsed", "false")
    expect(ui.locator("#sidebar-toggle")).to_have_attribute("aria-expanded", "true")


def _collapse(ui: Page) -> None:
    _wait_expanded(ui)
    with ui.expect_response(
        lambda r: "/api/sidebar/settings" in r.url and r.request.method == "POST" and r.ok
    ):
        ui.click("#sidebar-toggle")
    expect(ui.locator("#sidebar")).to_have_attribute("data-collapsed", "true")


def test_sidebar_collapses_and_expands(ui: Page) -> None:
    _collapse(ui)
    expect(ui.locator(".app")).to_have_class(re.compile(r"(^|\s)sidebar-collapsed(\s|$)"))
    expect(ui.locator("#sidebar-toggle .nav-label")).to_contain_text("Expand")

    with ui.expect_response(
        lambda r: "/api/sidebar/settings" in r.url and r.request.method == "POST" and r.ok
    ):
        ui.click("#sidebar-toggle")
    expect(ui.locator("#sidebar")).to_have_attribute("data-collapsed", "false")
    expect(ui.locator(".app")).not_to_have_class(re.compile(r"(^|\s)sidebar-collapsed(\s|$)"))
    expect(ui.locator("#sidebar-toggle .nav-label")).to_contain_text("Collapse")


def test_sidebar_collapse_persists_across_reload(ui: Page) -> None:
    _collapse(ui)
    ui.reload()
    expect(ui.locator("#sidebar")).to_have_attribute("data-collapsed", "true")
    expect(ui.locator(".app")).to_have_class(re.compile(r"(^|\s)sidebar-collapsed(\s|$)"))


def test_collapsed_nav_shows_tooltip_on_hover_and_focus(ui: Page) -> None:
    _collapse(ui)
    item = ui.locator('.nav-item[data-screen="organize"]')
    tip = item.locator(".nav-tooltip")

    expect(tip).to_be_hidden()
    item.hover()
    expect(tip).to_be_visible()
    expect(tip).to_contain_text("Organize")

    ui.locator("#sidebar-toggle").hover()  # clear organize hover
    expect(tip).to_be_hidden()
    item.focus()
    expect(tip).to_be_visible()
    expect(tip).to_contain_text("Organize")


def test_collapsed_custody_stays_inside_the_rail(ui: Page) -> None:
    _collapse(ui)
    expect(ui.locator("#custody-line")).to_be_hidden()

    rail = ui.locator("#sidebar").bounding_box()
    strip = ui.locator("#custody").bounding_box()
    assert rail is not None
    assert strip is not None
    assert strip["x"] + strip["width"] <= rail["x"] + rail["width"] + 1
    assert strip["y"] + strip["height"] <= rail["y"] + rail["height"] + 1


def test_sidebar_toggle_works_from_keyboard_without_losing_focus(ui: Page) -> None:
    _wait_expanded(ui)
    toggle = ui.locator("#sidebar-toggle")
    toggle.focus()
    expect(toggle).to_be_focused()

    with ui.expect_response(
        lambda r: "/api/sidebar/settings" in r.url and r.request.method == "POST" and r.ok
    ):
        ui.keyboard.press("Enter")
    expect(ui.locator("#sidebar")).to_have_attribute("data-collapsed", "true")
    expect(toggle).to_be_focused()

    with ui.expect_response(
        lambda r: "/api/sidebar/settings" in r.url and r.request.method == "POST" and r.ok
    ):
        ui.keyboard.press(" ")
    expect(ui.locator("#sidebar")).to_have_attribute("data-collapsed", "false")
    expect(toggle).to_be_focused()
