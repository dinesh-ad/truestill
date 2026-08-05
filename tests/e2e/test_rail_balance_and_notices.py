"""Three fixes: the catalog diagnostic leaves the rail, the wordmark band, the metric wrap.

The custody strip's contract is *where your files are*. `catalog_detail` is a process startup
message - "pass --db PATH or run from the folder that holds your reports/catalog.sqlite" is CLI
instruction, and it was rendering inside the rail, where on a narrow window it detached and
floated mid-page. It belongs in the page-level notice region that already exists for this class.
"""

from __future__ import annotations

import json
from typing import Any

from playwright.sync_api import Page, expect

# `inspect_catalog` produces four states. Only two carry text, and they are not the same kind of
# thing: one is a first-run aside, the other says the wrong catalog may be open.
ALERT = "empty_with_drives"
NOTICE = "empty"


def _status(ui: Page, **overrides: Any) -> None:
    """Serve one library-status payload and reload onto it."""
    base: dict[str, Any] = {
        "files": 0,
        "photos": 0,
        "videos": 0,
        "audio": 0,
        "drives": [],
        "single_copy": 0,
        "custody": {"no_copy": 0, "one_copy": 0, "floor": 0, "held": 0, "held_floor": 0},
        "catalog_path": "/tmp/library/catalog.sqlite",
        "catalog_presence": NOTICE,
        "catalog_detail": "Opened empty catalog file at /tmp/library/catalog.sqlite.",
        "catalog_tone": "notice",
    }
    base.update(overrides)
    ui.route(
        "**/api/library/status",
        lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps(base)),
    )
    ui.reload()
    ui.wait_for_selector(".custody")


# --------------------------------------------------------------- 1. the diagnostic leaves the rail


def test_the_custody_strip_carries_no_startup_diagnostic(ui: Page) -> None:
    """The strip says where files are. It does not say which sqlite file this process opened."""
    _status(ui)
    line = ui.eval_on_selector(".custody .line", "el => el.textContent")
    assert "--db" not in line, f"CLI instruction is still in the rail: {line!r}"
    assert "Opened empty catalog file" not in line, (
        f"the startup message is still in the rail: {line!r}"
    )


def test_the_startup_notice_lands_in_the_page_notice_region(ui: Page) -> None:
    _status(ui)
    notice = ui.locator("#catalog-notice")
    expect(notice).to_be_visible()
    expect(notice).to_contain_text("Opened empty catalog file")

    # Beside the global error, not inside a screen: it is about the process, not the task.
    inside_screen = ui.eval_on_selector("#catalog-notice", "el => !!el.closest('.screen')")
    assert inside_screen is False, "the notice is inside a screen; it belongs to the page"


def test_the_two_states_are_not_flattened_into_one(ui: Page) -> None:
    """A first-run aside and 'this may be the wrong catalog' are different messages."""
    _status(ui)
    quiet = ui.eval_on_selector("#catalog-notice", "el => el.className")

    _status(
        ui,
        catalog_presence=ALERT,
        catalog_tone="alert",
        catalog_detail="Opened catalog file /tmp/x: 0 files but 2 drive(s) are registered.",
        drives=[{"label": "BackupA", "files": 3, "size": 10, "last_verified": None}],
    )
    loud = ui.eval_on_selector("#catalog-notice", "el => el.className")

    assert "warn" in loud, f"the wrong-catalog case is not an alert: {loud!r}"
    assert "warn" not in quiet, f"the first-run aside is shouting: {quiet!r}"
    assert loud != quiet


def test_a_healthy_catalog_shows_no_notice_at_all(ui: Page) -> None:
    """Anti-cry-wolf: two of the four states carry no text, and must render nothing."""
    _status(ui, files=12, catalog_presence="ready", catalog_tone="info", catalog_detail="")
    expect(ui.locator("#catalog-notice")).to_be_hidden()


def test_the_notice_survives_a_narrow_window_instead_of_floating(ui: Page) -> None:
    """In the rail it detached and floated mid-page below the breakpoint."""
    _status(ui)
    ui.set_viewport_size({"width": 680, "height": 900})
    ui.wait_for_timeout(200)

    notice = ui.locator("#catalog-notice")
    expect(notice).to_be_visible()
    box = notice.bounding_box()
    main = ui.locator(".main").bounding_box()
    assert box is not None
    assert main is not None
    assert box["x"] >= main["x"] - 1, "the notice is outside the content column"


# --------------------------------------------------------------------- 3. the wordmark band


def test_the_wordmark_band_is_not_larger_than_the_nav_rhythm(ui: Page) -> None:
    """It read as a large empty band while the nav crowded beneath it.

    The space under the wordmark accumulated from three sources - its own padding, the rail's
    flex gap, and the first section label's top padding - and nothing owned the total.
    """
    # To the label's TEXT, not its box: the label carries its own top padding, so measuring to
    # the box top hides a third of the gap and the assertion cannot see the spacing it is about.
    gaps = ui.evaluate(
        "() => { const text = document.querySelector('.wordmark-text').getBoundingClientRect();"
        " const label = document.querySelector('.nav-section-label');"
        " const box = label.getBoundingClientRect();"
        " const pad = parseFloat(getComputedStyle(label).paddingTop);"
        " const rail = document.querySelector('#sidebar').getBoundingClientRect();"
        " const item = document.querySelector('.nav-item').getBoundingClientRect();"
        " return {above: text.y - rail.y, below: (box.y + pad) - (text.y + text.height),"
        "         row: item.height}; }"
    )
    assert gaps["below"] <= 20, f"{gaps['below']:.0f}px under the wordmark - still a band"
    assert gaps["above"] <= 24, f"{gaps['above']:.0f}px above the wordmark"
    # Balanced, not merely small: the two sides should not differ by more than a step.
    assert abs(gaps["above"] - gaps["below"]) <= 12, f"the band is lopsided: {gaps}"


def test_the_nav_rows_are_not_crowded(ui: Page) -> None:
    """The other half of the complaint: the band was generous and the nav was not."""
    gap = ui.eval_on_selector(".nav", "el => parseFloat(getComputedStyle(el).rowGap)")
    assert gap >= 4, f"nav rows are {gap}px apart - still crowded"


def test_both_section_labels_are_styled_the_same(ui: Page) -> None:
    """Only the FIRST label's top padding differs; everything else is shared.

    Giving `:first-child` the whole declaration block instead of the override left the second
    label with no type, no letter-spacing, no uppercase and the wrong colour - and the existing
    grouping test could not see it, because it uppercases the text in JS before comparing.
    """
    styles = ui.eval_on_selector_all(
        ".nav-section-label",
        "els => els.map(e => { const s = getComputedStyle(e);"
        " return [s.fontSize, s.fontWeight, s.letterSpacing, s.textTransform, s.color].join('|'); })",
    )
    assert len(styles) == 2, f"expected two section labels, got {len(styles)}"
    assert styles[0] == styles[1], f"the two section labels are styled differently: {styles}"
    assert "uppercase" in styles[1], f"the second label is not uppercased: {styles[1]}"


# ------------------------------------------------------------------------ 6. metrics two-up


def test_metrics_go_two_up_rather_than_wrapping_three_and_one(ui: Page) -> None:
    """Four metrics in a 760px column wrapped 3+1. Two-up, without shrinking the numbers."""
    ui.evaluate(
        "() => { const host = document.querySelector('.screen.active');"
        " host.insertAdjacentHTML('beforeend', '<div class=\"metrics\" id=\"probe\">' +"
        '   [1,2,3,4].map(n => \'<div class="metric"><div class="metric-value">\' + n +'
        "     '</div><div class=\"metric-label\">label ' + n + '</div></div>').join('') +"
        " '</div>'); }"
    )
    ui.wait_for_timeout(120)
    rows = ui.evaluate(
        "() => { const tops = [...document.querySelectorAll('#probe .metric')]"
        "   .map(e => Math.round(e.getBoundingClientRect().y));"
        " return [...new Set(tops)].length; }"
    )
    per_row = ui.evaluate(
        "() => { const tops = [...document.querySelectorAll('#probe .metric')]"
        "   .map(e => Math.round(e.getBoundingClientRect().y));"
        " return tops.filter(t => t === tops[0]).length; }"
    )
    assert rows == 2, f"four metrics laid out over {rows} rows, expected 2"
    assert per_row == 2, f"{per_row} metrics on the first row, expected 2"

    size = ui.eval_on_selector("#probe .metric-value", "el => getComputedStyle(el).fontSize")
    assert size == "40px", f"the number shrank to {size} - two-up was the alternative to that"
