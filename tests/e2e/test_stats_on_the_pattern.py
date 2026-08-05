"""Stats on the pattern - the only true dashboard, and the components' other extreme.

Find had no numbers; this has nothing else. The screen's own lede prescribes a reading order -
custody, then completeness, then shape - and that order is asserted rather than assumed.

The empty state is the common case here, not the edge: a new user reaches Stats before they have
organized anything, and a dashboard of zeros would be both useless and discouraging.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from playwright.sync_api import Page, expect

ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / "packages/truestill-app/src/truestill_app/static"


def _stats(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "complexity": "aggregate SQL only",
        "safety": {
            "total_files": 2269,
            "total_size": 6_650_000_000,
            "photos": 2100,
            "videos": 169,
            "audio": 0,
            "files_on_two_plus_drives": 1800,
            "files_on_one_drive": 400,
            "files_on_zero_drives": 69,
            "zero_drive_samples": ["IMG_0001.jpg"],
            "never_verified_files": 12,
            "drives": [
                {
                    "label": "BackupA",
                    "files": 1800,
                    "size": 5_000_000_000,
                    "last_verified": "2026-08-01T10:00:00",
                },
            ],
        },
        "completeness": {
            "undated_files": 31,
            "undated_samples": [{"relative": "Undated/IMG_9.jpg", "source_path": ""}],
            "timeline_files": 2200,
            "side_bin_files": 38,
            "near_duplicates_flagged": 14,
            "exact_duplicates_found": 0,
            "exact_duplicates_omission_reason": "Counted during organize, not stored.",
        },
        "shape": {
            "by_year": [{"year": 2018, "count": 900}, {"year": 2019, "count": 1300}],
            "by_format": {"jpg": 2000, "mp4": 169},
            "oldest_capture": "2014-08-14T00:00:00",
            "newest_capture": "2019-01-02T00:00:00",
        },
        "dates": {"rows": [], "total": 2269, "recorded": 2269, "not_recorded": 0},
    }
    base.update(overrides)
    return base


EMPTY = _stats(
    safety={
        "total_files": 0,
        "total_size": 0,
        "photos": 0,
        "videos": 0,
        "audio": 0,
        "files_on_two_plus_drives": 0,
        "files_on_one_drive": 0,
        "files_on_zero_drives": 0,
        "zero_drive_samples": [],
        "never_verified_files": 0,
        "drives": [],
    }
)


def _open(ui: Page, payload: dict[str, Any]) -> None:
    ui.route(
        "**/api/library/stats",
        lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps(payload)),
    )
    ui.click('.nav-item[data-screen="stats"]')
    ui.wait_for_selector("#stats-result .card", timeout=15_000)


# ------------------------------------------------------------------- the empty state


def test_the_empty_state_is_an_invitation_not_a_dashboard_of_zeros(ui: Page) -> None:
    """The common case on this screen. A new user has no library, and zeros would be noise."""
    _open(ui, EMPTY)
    result = ui.locator("#stats-result")
    expect(result).to_contain_text("Nothing to report yet")

    assert ui.locator("#stats-result .metric").count() == 0, (
        "the empty state renders metrics; there is no number to report"
    )
    assert ui.locator("#stats-result table").count() == 0, "the empty state renders a table"
    assert ui.locator("#stats-result .proportion").count() == 0


def test_the_empty_state_offers_the_two_ways_in(ui: Page) -> None:
    """It should say what to do next, not merely that there is nothing here."""
    _open(ui, EMPTY)
    for action in ("organize", "import"):
        button = ui.locator(f"#stats-result [data-stats-action='{action}']")
        expect(button).to_be_visible()

    ui.click("#stats-result [data-stats-action='organize']")
    expect(ui.locator("#screen-organize")).to_be_visible()


def test_the_empty_state_says_what_will_appear_here(ui: Page) -> None:
    """An empty screen that does not explain itself teaches nothing."""
    _open(ui, EMPTY)
    text = ui.eval_on_selector("#stats-result", "el => el.textContent.toLowerCase()")
    assert "custody" in text, "the empty state does not say what this screen is for"


# ------------------------------------------------------------------- the reading order


def test_the_cards_follow_the_lede_custody_completeness_shape(ui: Page) -> None:
    """The lede prescribes it; breaking it by accident is the failure this prevents."""
    _open(ui, _stats())
    headings = ui.eval_on_selector_all(
        "#stats-result .headline", "els => els.map(e => e.textContent.trim().toLowerCase())"
    )
    assert headings[0].startswith("custody"), f"custody does not lead: {headings}"
    order = [h for h in headings if h.startswith(("custody", "completeness", "shape"))]
    assert order == ["custody", "completeness", "shape"], f"reading order broken: {headings}"


# ----------------------------------------------------------------------- the metrics


def test_custody_leads_with_the_numbers_that_decide_something(ui: Page) -> None:
    """Not seven equal tallies. The reference set's rule: a few KPIs, nothing competing."""
    _open(ui, _stats())
    # The FIRST `.metrics` group, not `:first-of-type` - that matches the first <div> among
    # siblings, which is not the same thing and silently selected nothing.
    values = ui.evaluate(
        "() => [...document.querySelector('#stats-result .metrics').children]"
        ".map(e => ({text: e.textContent.trim(),"
        " size: parseFloat(getComputedStyle(e.querySelector('.metric-value')).fontSize)}))"
    )
    assert 2 <= len(values) <= 4, f"custody leads with {len(values)} metrics - too many to rank"
    assert any(v["size"] >= 40 for v in values), "no metric is at the metric size"


def test_the_at_risk_number_carries_meaning_in_its_colour(ui: Page) -> None:
    """Amber and green already mean risk and custody elsewhere; reuse, do not decorate."""
    _open(ui, _stats())
    at_risk = ui.locator("#stats-result .metric-value.at-risk").first
    expect(at_risk).to_be_visible()
    expect(at_risk).to_contain_text("69")


def test_a_library_fully_backed_up_shows_no_amber(ui: Page) -> None:
    """Anti-cry-wolf: the risk colour must mean risk, or it stops meaning anything."""
    safe = _stats()
    safe["safety"] = {
        **safe["safety"],
        "files_on_zero_drives": 0,
        "files_on_one_drive": 0,
        "files_on_two_plus_drives": 2269,
        "zero_drive_samples": [],
    }
    _open(ui, safe)
    # Scoped to custody: undated files are a completeness risk and are legitimately amber
    # there, so asserting "no amber anywhere" would be asserting the wrong thing.
    custody = ui.evaluate(
        "() => document.querySelectorAll('#stats-result .card:first-child .metric-value.at-risk')"
        ".length"
    )
    assert custody == 0, "a fully backed-up library still shows amber in custody"


def test_secondary_numbers_do_not_compete_with_the_metrics(ui: Page) -> None:
    """Photos, videos and total size are library size, not custody. They rank below."""
    _open(ui, _stats())
    sizes = ui.eval_on_selector_all(
        "#stats-result .metric-value",
        "els => els.map(e => parseFloat(getComputedStyle(e).fontSize))",
    )
    assert len(set(sizes)) >= 2, "every number is the same size - nothing is ranked"
    assert max(sizes) > min(sizes), f"no tiering: {sorted(set(sizes))}"


def test_only_the_metric_still_owns_the_biggest_size() -> None:
    """`--text-3xl` is metric-only and guarded; Stats must not reach past it."""
    # Comments stripped first: a comment that MENTIONS the token is not a use of it, and
    # counting one made this fail on its own explanatory note.
    css = re.sub(r"/\*.*?\*/", "", (STATIC / "app.css").read_text(encoding="utf-8"), flags=re.S)
    users = [
        block.split("{")[0].strip().splitlines()[-1].strip()
        for block in css.split("}")
        if "--text-3xl" in block and "{" in block
    ]
    assert users == [".metric-value"], f"--text-3xl is used outside the metric: {users}"


# ------------------------------------------------------------------- the last bar


def test_the_year_bars_are_the_shared_proportion_component(ui: Page) -> None:
    """`.stats-bar` was the last separate bar implementation."""
    _open(ui, _stats())
    assert ui.locator("#stats-result .proportion").count() >= 2, "the year bars are not shared"
    assert ui.locator("#stats-result .stats-bar").count() == 0, ".stats-bar is still here"


def test_no_bar_implementation_remains_anywhere() -> None:
    """Say it plainly in a guard: one bar, or name what is left."""
    css = (STATIC / "app.css").read_text(encoding="utf-8")
    assert ".stats-bar {" not in css, ".stats-bar still has its own rule"
    assert ".progress-wrap .bar {" not in css, "the run block's bar rule is still separate"


# ----------------------------------------------------------------------- the orphans


def test_the_orphan_count_reads_as_an_inconsistency_not_a_forgotten_step(ui: Page) -> None:
    """The custody work put these here. They are a records-versus-disk mismatch, and the copy
    must not imply the user skipped something."""
    _open(ui, _stats())
    banner = ui.locator("#stats-result .banner").first
    expect(banner).to_contain_text("no copy on any drive it knows")
    text = ui.eval_on_selector("#stats-result", "el => el.textContent.lower ? '' : el.textContent")
    for blaming in ("you forgot", "you have not", "you did not"):
        assert blaming not in text.lower(), f"the orphan copy blames the user: {blaming!r}"
