"""Find on the shared pattern - the screen the pattern was least likely to fit.

Find has nothing to summarise until you search, so the resting state is a search box and
nothing else. No metric, no panel, no proportion bar: inventing any of them would mean
inventing numbers, which is the failure the pattern was written to avoid.

The placeholder taught a query the search cannot answer. `find_copies_query` builds ONE
substring `LIKE` over three columns - no whitespace split, no AND - so `beach 2019` needs that
exact substring, and a photo at `2019/2019-07/2019-07-04 - Beach/` never matches it.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from playwright.sync_api import Page, expect

ROOT = Path(__file__).resolve().parents[2]
CATALOG = ROOT / "packages/truestill-core/src/truestill_core/catalog.py"
INDEX = ROOT / "packages/truestill-app/src/truestill_app/templates/index.html"

PAGE_SIZE = 50


def _rows(count: int, start: int = 0) -> list[dict[str, Any]]:
    return [
        {
            "name": f"IMG_{i:04d}.jpg",
            "drive": "BackupA",
            "relative": f"2019/2019-07/2019-07-04 - Wayanad/IMG_{i:04d}.jpg",
            "last_verified": None,
        }
        for i in range(start, start + count)
    ]


def _search(ui: Page, term: str, *, total: int, shown: int, page: int = 1) -> None:
    pages = max(1, -(-total // PAGE_SIZE))
    ui.route(
        "**/api/where**",
        lambda r: r.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(
                {
                    "copies": _rows(shown, (page - 1) * PAGE_SIZE),
                    "total": total,
                    "page": page,
                    "pages": pages,
                    "page_size": PAGE_SIZE,
                }
            ),
        ),
    )
    ui.click('.nav-item[data-screen="find"]')
    ui.fill("#where-term", term)
    ui.click("#where-go")
    ui.wait_for_selector("#where-result *", timeout=15_000)


# --------------------------------------------------------------------------- resting state


def test_the_resting_screen_is_a_search_box_and_nothing_else(ui: Page) -> None:
    """No numbers exist yet, so none are shown. This is the pattern's own rule."""
    ui.click('.nav-item[data-screen="find"]')
    expect(ui.locator("#screen-find")).to_be_visible()

    for absent in (".metric", ".proportion", ".metrics"):
        assert ui.locator(f"#screen-find {absent}").count() == 0, (
            f"{absent} is on the resting Find screen, where there is nothing to report"
        )
    assert ui.eval_on_selector("#where-result", "el => el.textContent.trim()") == ""


def test_the_panel_stays_empty_on_find(ui: Page) -> None:
    """A screen with no ambient facts must leave the panel empty rather than fill it."""
    ui.set_viewport_size({"width": 1500, "height": 900})
    ui.click('.nav-item[data-screen="find"]')
    ui.wait_for_timeout(200)
    expect(ui.locator("#panel")).to_be_hidden()


def test_the_search_field_leads_the_screen(ui: Page) -> None:
    """Spotlight, not a dashboard: the input is the biggest thing here."""
    ui.click('.nav-item[data-screen="find"]')
    size = ui.eval_on_selector("#where-term", "el => parseFloat(getComputedStyle(el).fontSize)")
    body = ui.eval_on_selector("body", "el => parseFloat(getComputedStyle(el).fontSize)")
    assert size > body, f"the search field is {size}px against {body}px body text"


# ------------------------------------------------------------------------- the placeholder


def test_the_placeholder_is_a_query_the_search_can_actually_answer(ui: Page) -> None:
    """`beach 2019` cannot match anything: the query is one substring, not two terms."""
    ui.click('.nav-item[data-screen="find"]')
    placeholder = ui.eval_on_selector("#where-term", "el => el.placeholder")

    example = placeholder.split("e.g.")[-1].strip().strip(".")
    assert example, f"no example in the placeholder: {placeholder!r}"
    assert " " not in example, (
        f"the placeholder suggests a multi-word query ({example!r}), which the search cannot "
        "answer - it builds one substring LIKE with no whitespace split"
    )


def test_the_search_says_it_matches_part_of_a_name(ui: Page) -> None:
    """The behaviour is a substring match; a user who is told that can use it."""
    ui.click('.nav-item[data-screen="find"]')
    hint = ui.eval_on_selector("#screen-find .hint", "el => el.textContent.toLowerCase()")
    assert "part of" in hint or "one word" in hint, f"the field does not explain itself: {hint!r}"


def test_the_query_really_is_a_single_substring() -> None:
    """Pins the claim the placeholder is written against, in the source it is a claim about.

    If the search ever learns to split on whitespace, this fails and the placeholder gets
    revisited with it - which is the point, because the two must agree.
    """
    sql = CATALOG.read_text(encoding="utf-8")
    body = sql[sql.index("def find_copies_query") : sql.index("def find_copies(")]
    assert 'like = f"%{term}%"' in body, "the search no longer builds one substring"
    assert body.count("LIKE ?") == 3, "the LIKE columns changed; revisit the placeholder"
    assert ".split(" not in body, "the search now splits the term - the placeholder may change"


# ------------------------------------------------------------------------------- results


def test_a_result_names_the_file_the_drive_and_where_it_sits(ui: Page) -> None:
    _search(ui, "Wayanad", total=3, shown=3)
    rows = ui.eval_on_selector_all("#where-result tbody tr", "els => els.length")
    assert rows == 3
    expect(ui.locator("#where-result")).to_contain_text("IMG_0000.jpg")
    expect(ui.locator("#where-result")).to_contain_text("BackupA")


def test_the_count_is_stated_but_is_not_the_loudest_thing(ui: Page) -> None:
    """A count here is context for the list, not the subject of the screen.

    This is where the metric component does NOT fit: making 2,269 a 40px number would shout
    the tally over the results a person came to read.
    """
    _search(ui, "Wayanad", total=3, shown=3)
    expect(ui.locator("#where-result")).to_contain_text("3 matches")
    assert ui.locator("#where-result .metric").count() == 0, (
        "the result count was rendered as a metric; it is context, not the subject"
    )


def test_nothing_found_says_so_without_a_zero(ui: Page) -> None:
    _search(ui, "zzz", total=0, shown=0)
    expect(ui.locator("#where-result")).to_contain_text("No files match")
    assert ui.locator("#where-result .metric").count() == 0


# --------------------------------------------------------------------------------- pager


def test_no_pager_at_fifty_results_or_fewer(ui: Page) -> None:
    """`FIND_PAGE_SIZE` is 50, so one page needs no controls."""
    _search(ui, "Wayanad", total=PAGE_SIZE, shown=PAGE_SIZE)
    assert ui.locator("#where-next").count() == 0, "a pager appeared for a single page"
    expect(ui.locator("#where-result")).to_contain_text("50 matches")


def test_a_pager_appears_past_fifty_and_says_where_you_are(ui: Page) -> None:
    """'Showing 1-50 of 120' is the difference between a page and a page that hides the file."""
    _search(ui, "Wayanad", total=120, shown=PAGE_SIZE)
    expect(ui.locator("#where-next")).to_be_visible()
    expect(ui.locator("#where-prev")).to_be_disabled()
    expect(ui.locator("#where-result")).to_contain_text("Showing 1-50 of 120")
    expect(ui.locator("#where-result")).to_contain_text("Page 1 of 3")


# ---------------------------------------------------------------- what Find leaves behind


def test_find_uses_neither_proportion_bar(ui: Page) -> None:
    """Nothing here is a share of anything, so both bars stay unused on this screen."""
    _search(ui, "Wayanad", total=3, shown=3)
    for unused in (".proportion", ".bar", ".stats-bar"):
        assert ui.locator(f"#screen-find {unused}").count() == 0, f"{unused} appeared on Find"


def test_the_drive_column_is_the_surface_abd_lives_on() -> None:
    """RECORD ONLY - not solved here.

    `find_copies_query` joins `drives` and selects `d.label` with no drive filter, so on a
    shared catalog this column names another machine's drives. `(abd)` owns that question.
    """
    sql = CATALOG.read_text(encoding="utf-8")
    body = sql[sql.index("def find_copies_query") : sql.index("def find_copies(")]
    assert "d.label AS drive_label" in body
    assert "drive_uuid = ?" not in body, (
        "the search now filters by drive - (abd) may have been solved; update this note"
    )


def test_the_find_screen_declares_no_table_component() -> None:
    """A finding about the PATTERN, pinned so it is not quietly forgotten.

    The component set has card, field, metric, chip, proportion and run block - and no result
    table. Find builds one from `.table`, which predates the pattern. Stats and Backups will
    want the same thing; when a real component arrives, this assertion is what says where to
    look.
    """
    markup = INDEX.read_text(encoding="utf-8")
    find = markup[markup.index('id="screen-find"') : markup.index('id="screen-stats"')]
    assert "<table" not in find, "the table is built in JS, not in the template - as expected"
    assert re.search(r'id="where-result"', find), "the results host is gone"
