"""The last two task screens on the shared pattern, and the two sentences the audit caught.

TRIPS asked for "enough camera photos taken close together" - a description of within-day
clustering wearing the name of a trip. A four-day trip is not "close together"; it is four days
in a row that each cleared a bar. And the sentence stated no number while that exact number is a
field on the Settings screen of the same product, so a user who read it had no way to know
whether they were two photos short or two hundred.

IMPORT was headed "Import from Google Photos" while `ingest` reads any folder and any archive
from any source. SHIPPED records that scope correction in capitals and says every user-facing
string was audited; this heading, and the button on Stats that points at it, are the two the
audit missed.

Putting Import on the pattern also found a summing block that does not sum - the same defect
`ab0a76a` fixed on Organize, in a payload that already guarantees the identity it needed.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from playwright.sync_api import Page, expect

ROOT = Path(__file__).resolve().parents[2]
INDEX = ROOT / "packages/truestill-app/src/truestill_app/templates/index.html"


def _json_route(route: Any, body: dict[str, Any]) -> None:
    route.fulfill(status=200, content_type="application/json", body=json.dumps(body))


def _text(ui: Page, selector: str) -> str:
    """Collapsed whitespace. A template literal wraps mid-sentence, and raw `textContent` keeps
    the newline - so an assertion about the WORDS must not also be an assertion about where the
    source happened to break the line."""
    return re.sub(r"\s+", " ", ui.eval_on_selector(selector, "el => el.textContent")).strip()


# ------------------------------------------------------------------ Trips & events: the empty state


def _propose(ui: Page, *, cards: list[dict[str, Any]], min_files: int = 8) -> None:
    ui.route(
        "**/api/events/propose",
        lambda r: _json_route(
            r,
            {
                "ok": True,
                "session": "sess",
                "label": "BackupA",
                "cards": cards,
                "collapsed": None,
                "declines": [],
                "min_files": min_files,
            },
        ),
    )
    ui.click('button[data-screen="events"]')
    ui.fill("#ev-source", "/media/BackupA")
    ui.click("#ev-propose")
    ui.wait_for_selector("#ev-clusters *", timeout=15_000)


def test_the_empty_state_states_the_number_it_is_actually_using(ui: Page) -> None:
    """The old sentence said "enough" while the number is a field on Settings."""
    _propose(ui, cards=[], min_files=8)

    empty = _text(ui, "[data-testid='ev-empty']")
    assert "8 camera photos" in empty, empty


def test_the_number_is_read_from_the_setting_and_not_from_a_constant(ui: Page) -> None:
    """The anti-hardcode half. A pasted `8` passes the test above and fails this one."""
    _propose(ui, cards=[], min_files=25)

    empty = _text(ui, "[data-testid='ev-empty']")
    assert "25 camera photos" in empty, empty
    assert "8 camera photos" not in empty, empty


def test_the_empty_state_no_longer_calls_a_four_day_trip_close_together(ui: Page) -> None:
    """The two rules are separate and the old sentence collapsed them into the wrong one.

    A day qualifies on photos taken in one stretch; a TRIP is days in a row. "Close together"
    describes the first and was printed as the definition of both.
    """
    _propose(ui, cards=[], min_files=8)

    empty = _text(ui, "[data-testid='ev-empty']").lower()
    assert "close together" not in empty, empty
    assert "in a row" in empty, f"the multi-day rule is not stated: {empty}"
    assert "day" in empty, empty


def test_the_empty_state_says_what_is_never_grouped(ui: Page) -> None:
    """`camera_copies_for_events` excludes side-bin labels and undated files.

    Both exclusions are silent everywhere else, and either one explains an empty screen on a
    library that is full of pictures.

    ⚠ **This docstring said the filter was `category = 'Camera'` until 2026-08-26, which was the
    DEFECT written down as the specification.** That predicate matched nothing on a `--by-device`
    library, so this suite documented a dead screen as intended behaviour. `(ahw)`
    """
    _propose(ui, cards=[], min_files=8)

    empty = _text(ui, "[data-testid='ev-empty']").lower()
    assert "no date" in empty, f"undated files are excluded and unmentioned: {empty}"


def test_the_empty_state_points_at_the_setting_by_the_label_it_really_has(ui: Page) -> None:
    """A pointer that names a control which does not exist is worse than no pointer.

    Read from the template rather than repeated here, so renaming the field fails this test
    instead of leaving the sentence aimed at nothing.
    """
    label = re.search(r'<label for="events-min-files">([^<]+)</label>', INDEX.read_text("utf-8"))
    assert label, "the minimum-photos field lost its label"

    _propose(ui, cards=[], min_files=8)

    assert label.group(1).strip() in _text(ui, "[data-testid='ev-empty']")


def test_a_screen_with_findings_shows_no_empty_state(ui: Page) -> None:
    """CRY-WOLF HALF: the sentence must not appear beside actual trips."""
    _propose(
        ui,
        cards=[
            {
                "kind": "event",
                "start": "2021-06-15T10:00:00",
                "end": "2021-06-15T18:00:00",
                "count": 40,
                "active_days": 1,
                "days": [],
                "location": None,
                "collapsed": False,
            }
        ],
    )

    assert ui.locator("[data-testid='ev-empty']").count() == 0


# ---------------------------------------------------------------- Trips & events: the pattern


def test_the_resting_trips_screen_invents_no_numbers(ui: Page) -> None:
    """Nothing has run, so there is nothing to put in a metric - the pattern's own rule.

    A FINDING ABOUT THE PATTERN, and the reason this is not written the way Find's equivalent is.
    `test_find_on_the_pattern` asserts `.proportion` is ABSENT, which is only available to Find
    because Find has no run block. Every screen that mounts one carries the run bar's
    `.proportion` in its DOM from page load, so on the other seven "absent" is unassertable and
    the real rule is that it must not be SHOWING.
    """
    ui.click('button[data-screen="events"]')
    expect(ui.locator("#screen-events")).to_be_visible()

    for absent in (".metric", ".metrics"):
        assert ui.locator(f"#screen-events {absent}").count() == 0, (
            f"{absent} is on the resting Trips screen, where nothing has been counted yet"
        )
    bars = ui.locator("#screen-events .proportion")
    assert bars.count() == 1, "a proportion bar beyond the run block's own appeared at rest"
    expect(bars.first).to_be_hidden()


def test_the_panel_stays_empty_on_trips(ui: Page) -> None:
    ui.set_viewport_size({"width": 1500, "height": 900})
    ui.click('button[data-screen="events"]')
    ui.wait_for_timeout(200)
    expect(ui.locator("#panel")).to_be_hidden()


def test_a_review_card_does_not_use_the_tally_as_a_layout_hack(ui: Page) -> None:
    """`.tally` is a two-column number block. It was carrying a card header with an inline
    `grid-template-columns` override, which is a component used for its grid and nothing else."""
    _propose(
        ui,
        cards=[
            {
                "kind": "trip",
                "start": "2021-06-15",
                "end": "2021-06-18",
                "count": 120,
                "active_days": 4,
                "days": [{"date": "2021-06-15", "count": 30}],
                "location": None,
                "collapsed": False,
            }
        ],
    )

    assert ui.locator("#ev-clusters .tally").count() == 0, (
        "a review card still renders `.tally` for its header row"
    )
    overrides = ui.eval_on_selector_all(
        "#ev-clusters [style]", "els => els.map(e => e.getAttribute('style'))"
    )
    assert not any("grid-template-columns" in style for style in overrides), overrides


# ------------------------------------------------------------------------ Import: the heading


def test_the_import_heading_names_no_single_service(ui: Page) -> None:
    ui.click('button[data-screen="import"]')

    heading = _text(ui, "#screen-import h1")
    assert "Google" not in heading, heading
    assert heading == "Import", heading


def test_the_lede_carries_the_scope_the_heading_gave_up(ui: Page) -> None:
    """Dropping the service name must not cost the screen its subject."""
    ui.click('button[data-screen="import"]')

    lede = _text(ui, "#screen-import .lede").lower()
    assert "folder" in lede, lede
    assert "archive" in lede, lede


def test_the_way_in_from_stats_is_not_scoped_to_one_service_either(ui: Page) -> None:
    """The audit missed two strings, not one: this button is the other."""
    ui.route(
        "**/api/library/stats**",
        lambda r: _json_route(r, {"safety": {"total_files": 0}, "completeness": {}, "shape": {}}),
    )
    ui.click('button[data-screen="stats"]')
    ui.wait_for_selector("[data-stats-action='import']", timeout=15_000)

    assert "Google" not in _text(ui, "[data-stats-action='import']")


# ------------------------------------------------------------------------- Import: the tally


def _summary(**overrides: Any) -> dict[str, Any]:
    """`files == kept + dup_collapsed + unreadable` is guaranteed by `ingest_preview`.

    10 = 6 kept + 3 collapsed + 1 unreadable. `dates_photo_taken` (4) and `undated` (2) are
    counted over the 6 kept, which is exactly why neither may be a row in the summing block.
    """
    base: dict[str, Any] = {
        "files": 10,
        "kept": 6,
        "dup_collapsed": 3,
        "unreadable": 1,
        "reclaimed_mb": 12.5,
        "dates_photo_taken": 4,
        "dates_upload_approx": 0,
        "dates_exif": 0,
        "undated": 2,
        "sentinel_rejected": 0,
        "future_rejected": 0,
        "suspect_default": 0,
        "inferred_local_shifts": [],
        "missing_sidecar": 0,
    }
    base.update(overrides)
    return base


def _import_preview(ui: Page, summary: dict[str, Any]) -> None:
    """Drive the folder path (not the archive path): a precheck reporting no parts falls
    through to the single-step scan, which is what an already-extracted folder does."""
    ui.route("**/api/ingest/archives/precheck", lambda r: _json_route(r, {"parts": 0, "ok": True}))
    ui.route("**/api/ingest/preview", lambda r: _json_route(r, {"job_id": "imp-job"}))
    ui.route(
        "**/api/jobs/imp-job/events**",
        lambda r: r.fulfill(
            status=200,
            content_type="text/event-stream",
            body=f"data: {json.dumps({'type': 'done', 'summary': summary})}\n\n",
        ),
    )
    ui.click('button[data-screen="import"]')
    ui.fill("#rc-takeout", "/tmp/photos")
    ui.fill("#rc-dest", "/media/BackupA")
    ui.click("#rc-preview")
    ui.wait_for_selector("[data-testid='rc-tally']", timeout=30_000)


def test_the_import_tally_sums_to_the_files_it_found(ui: Page) -> None:
    """6 + 3 + 1 = 10. The old block showed kept, collapsed, dates-recovered and undated, which
    summed to 15 of 10 while the real third bucket was not on the screen at all."""
    _import_preview(ui, _summary())

    rows = ui.eval_on_selector_all(
        "[data-testid='rc-tally'] .metric",
        "els => els.map(e => ({n: e.querySelector('.metric-value').textContent.trim(),"
        " label: e.querySelector('.metric-label').textContent.trim()}))",
    )
    assert rows, "no tally metrics rendered"
    total = sum(int(row["n"].replace(",", "")) for row in rows)
    files = int(ui.eval_on_selector("[data-testid='rc-tally']", "el => el.dataset.files"))
    assert total == files, f"the tally sums to {total} but {files} files were found: " + ", ".join(
        f"{row['n']} {row['label']}" for row in rows
    )


def test_the_unreadable_bucket_reaches_the_screen(ui: Page) -> None:
    """It has been in the payload, named there as the reason the identity holds, and no surface
    ever showed it."""
    _import_preview(ui, _summary())

    labels = ui.eval_on_selector_all(
        "[data-testid='rc-tally'] .metric-label", "els => els.map(e => e.textContent.trim())"
    )
    assert any("could not be read" in label.lower() for label in labels), labels


def test_a_run_with_nothing_unreadable_shows_no_zero_row(ui: Page) -> None:
    """6 + 3 = 9 of 9, and the sum still holds without the row."""
    _import_preview(ui, _summary(files=9, kept=6, dup_collapsed=3, unreadable=0))

    labels = ui.eval_on_selector_all(
        "[data-testid='rc-tally'] .metric-label", "els => els.map(e => e.textContent.trim())"
    )
    assert not any("could not be read" in label.lower() for label in labels), labels
    values = ui.eval_on_selector_all(
        "[data-testid='rc-tally'] .metric-value",
        "els => els.map(e => +e.textContent.replace(/,/g,''))",
    )
    assert sum(values) == 9


def test_dates_recovered_and_undated_are_properties_not_buckets(ui: Page) -> None:
    """Both are counted over `kept`, so as rows they double-counted against it."""
    _import_preview(ui, _summary())

    labels = [
        label.lower()
        for label in ui.eval_on_selector_all(
            "[data-testid='rc-tally'] .metric-label", "els => els.map(e => e.textContent.trim())"
        )
    ]
    assert not any("date" in label for label in labels), f"a date row is still summing: {labels}"

    note = _text(ui, "[data-testid='rc-dates']")
    assert "4" in note, note
    assert "2" in note, note


def test_the_import_summary_uses_the_pattern_component(ui: Page) -> None:
    """`.tally` predates the pattern; `.metrics` is what every adopted screen reports with."""
    _import_preview(ui, _summary())

    assert ui.locator("#rc-result .metrics").count() >= 1
    assert ui.locator("#rc-result .tally").count() == 0, "the old tally survives on Import"


def test_the_reclaimed_space_stays_with_the_duplicates_it_came_from(ui: Page) -> None:
    """It is a property of that one bucket, not a fifth number floating beside four others."""
    _import_preview(ui, _summary())

    labels = ui.eval_on_selector_all(
        "[data-testid='rc-tally'] .metric-label", "els => els.map(e => e.textContent.trim())"
    )
    duplicates = [label for label in labels if "duplicate" in label.lower()]
    assert duplicates, labels
    assert "12.5" in duplicates[0], labels
