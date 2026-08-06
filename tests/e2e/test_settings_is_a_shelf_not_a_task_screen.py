"""Settings does not adopt the lifecycle pattern, and that is the finding rather than a gap.

CORRECTING MY OWN EARLIER DESCRIPTION, which said Settings has no run block and no result state.
It has TWO of each. Rearrange and Dates-you-have-corrected are complete preview -> typed confirm
-> run -> undo flows that already use the shared run block exactly as Organize does.

So the real shape is not "a screen the pattern cannot describe". It is that Settings is not a
SCREEN in the pattern's sense at all - it is a SHELF. The pattern describes a surface with one
job: one form, one run, one result. Settings holds five cards with five unrelated jobs, three of
them plain preferences that finish the moment you press Save, and two of them full task flows
that happen to be filed here. Bending one lifecycle over the whole thing would mean inventing a
result for "Settings", which is not a thing that runs.

What the pattern DOES reach here is its components, and those are already in use: card, field,
the run block, the button hierarchy. Nothing was bent to fit and nothing was added to pretend.

THE ORDER IS LOAD-BEARING, which is the other half of this file. `layout.py`'s day-threshold
warning says "Use Rearrange your library BELOW to preview" - copy that encodes DOM order. Copy
like that is a lie waiting for a reorder, so the order is pinned here.
"""

from __future__ import annotations

import re
from pathlib import Path

from playwright.sync_api import Page, expect
from truestill_core.layout import EVERYDAY_DAY_THRESHOLD_MIGRATE_WARNING

ROOT = Path(__file__).resolve().parents[2]
INDEX = ROOT / "packages/truestill-app/src/truestill_app/templates/index.html"


def _settings_markup() -> str:
    markup = INDEX.read_text("utf-8")
    return markup[
        markup.index('id="screen-settings"') : markup.index(
            "</section>", markup.index('id="screen-settings"')
        )
    ]


def _card_headings(ui: Page) -> list[str]:
    return ui.eval_on_selector_all(
        "#screen-settings .card h2", "els => els.map(e => e.textContent.trim())"
    )


# ------------------------------------------------------------------ the shape, stated once


def test_settings_holds_several_jobs_rather_than_one(ui: Page) -> None:
    """The pattern's unit is a screen with one job. This has five cards and no single subject."""
    ui.click('.nav-item[data-screen="settings"]')
    expect(ui.locator("#screen-settings")).to_be_visible()

    assert len(_card_headings(ui)) >= 4, _card_headings(ui)


def test_two_of_its_cards_are_real_task_flows_already_on_the_run_block(ui: Page) -> None:
    """The correction. Rearrange and the date bake are lifecycle flows filed under Settings, and
    they use the shared component rather than a private one - which is why nothing here needed
    the pattern extended.

    Asserted on the MOUNTED result, not on `[data-run]`: `mountRunBlocks` calls `replaceWith`,
    so the mount attribute does not survive into the live DOM and a selector for it would read
    zero on every screen - passing here by accident and proving nothing anywhere.
    """
    ui.click('.nav-item[data-screen="settings"]')

    blocks = ui.locator("#screen-settings .progress-wrap")
    assert blocks.count() == 2, f"{blocks.count()} run blocks on Settings"
    for prefix in ("mig", "bake"):
        assert ui.locator(f"#screen-settings #{prefix}-cancel").count() == 1, prefix


def test_settings_reports_no_numbers_because_it_counts_nothing(ui: Page) -> None:
    """A metric here would have to be invented: nothing on this screen measures a library."""
    ui.click('.nav-item[data-screen="settings"]')

    for absent in (".metric", ".metrics"):
        assert ui.locator(f"#screen-settings {absent}").count() == 0, (
            f"{absent} appeared on Settings, which counts nothing"
        )


def test_the_panel_stays_empty_on_settings(ui: Page) -> None:
    ui.set_viewport_size({"width": 1500, "height": 900})
    ui.click('.nav-item[data-screen="settings"]')
    ui.wait_for_timeout(200)
    expect(ui.locator("#panel")).to_be_hidden()


# ------------------------------------------------------------------------ position and copy


def test_rearrange_sits_directly_under_the_layout_it_answers(ui: Page) -> None:
    """POSITION, not just the heading. It is the answer to the question this whole space is
    asked most - how do I rearrange a library I already have - and it sat third, under a niche
    number field for trip suggestions.

    Directly under Folder layout is where it belongs: that card decides how NEW files are laid
    out, and this one brings the existing library to that layout. The two are one thought.
    """
    ui.click('.nav-item[data-screen="settings"]')
    headings = _card_headings(ui)

    layout = headings.index("Folder layout")
    rearrange = next(i for i, h in enumerate(headings) if h.startswith("Rearrange"))
    suggestions = next(i for i, h in enumerate(headings) if "suggestions" in h)

    assert rearrange == layout + 1, f"Rearrange is not directly under Folder layout: {headings}"
    assert rearrange < suggestions, f"Rearrange still sits below the suggestion field: {headings}"


def test_the_copy_that_says_below_is_pinned_to_an_order_that_makes_it_true() -> None:
    """`EVERYDAY_DAY_THRESHOLD_MIGRATE_WARNING` says "below". That word is a claim about DOM
    order, and nothing but this test connects the two - a reorder would leave the sentence
    pointing the wrong way with every other gate still green."""
    assert "below" in EVERYDAY_DAY_THRESHOLD_MIGRATE_WARNING

    settings = _settings_markup()
    threshold = settings.index('id="everyday-day-threshold"')
    migrate = settings.index('id="settings-migrate"')
    assert threshold < migrate, (
        "the day-threshold field now sits BELOW the Rearrange card it calls 'below'"
    )


def test_appearance_stays_last_because_it_is_the_only_card_that_is_not_about_photos() -> None:
    settings = _settings_markup()
    headings = re.findall(r"<h2>(.*?)</h2>", settings, re.S)

    assert headings[-1].strip() == "Appearance", headings
