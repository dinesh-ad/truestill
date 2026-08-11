"""Organize on the shared pattern: metrics in the result, nothing invented in the resting state.

Two correctness fixes ride with the visual change, and both are about a screen stating something
untrue:

* the four-number grid did not sum. `undated` is not a bucket - it is counted over
  `buckets.organized` (`unique + near_duplicates`), so it overlapped two rows, while the real
  fourth bucket (`unreadable`) sat in a separate banner. `BACKLOG.md` forbids a summing block
  that does not sum; the conservation law is
  `new_unique + near_dup + exact_dup + unreadable == files`.
* "Look inside" could answer *Nothing to organize here* for a folder it had failed to open.
  `SourceInventory.unreadable_dirs` has carried that fact all along; the payload dropped it.
"""

from __future__ import annotations

import json
from typing import Any

from playwright.sync_api import Page, expect

SOURCE = "/tmp/pictures"


def _json_route(route: Any, body: dict) -> None:
    route.fulfill(status=200, content_type="application/json", body=json.dumps(body))


def _inventory(**overrides: Any) -> dict:
    base: dict = {
        "tier": "inventory",
        "files": 4,
        "photos": 4,
        "videos": 0,
        "audio": 0,
        "by_format": {},
        "total_bytes": 4_000,
        "skipped": {"documents": {}, "unrecognized": {}, "exiftool_backups": {}},
        "unreadable_folders": [],
    }
    base.update(overrides)
    return base


def _look_inside(ui: Page, inventory: dict) -> None:
    ui.route("**/api/organize/inventory", lambda r: _json_route(r, inventory))
    ui.fill("#org-source", SOURCE)
    ui.fill("#org-dest", "/tmp/library")
    ui.click("#org-preview")
    expect(ui.locator("#org-result .card")).to_be_visible(timeout=30_000)


def _dedup(ui: Page, summary: dict) -> None:
    ui.route("**/api/organize/inventory", lambda r: _json_route(r, _inventory()))
    ui.route("**/api/organize/preview", lambda r: _json_route(r, {"job_id": "prev-job"}))
    ui.route(
        "**/api/jobs/prev-job/events**",
        lambda r: r.fulfill(
            status=200,
            content_type="text/event-stream",
            body=f"data: {json.dumps({'type': 'done', 'summary': summary})}\n\n",
        ),
    )
    ui.fill("#org-source", SOURCE)
    ui.fill("#org-dest", "/tmp/library")
    ui.click("#org-preview")
    expect(ui.locator("#org-dedup")).to_be_enabled(timeout=30_000)
    ui.click("#org-dedup")
    # NOT `#org-result .card`, which the "Look inside" click above has ALREADY rendered - that
    # wait is satisfied before the dedup result exists, so a read after it races the second
    # render. §4's sixteenth member: wait for something only the finished work can produce. The
    # promise line is rendered by `organizeTally` and by nothing else, at every count including
    # zero. Measured 2026-08-11: with the old wait this file failed roughly one run in three.
    expect(ui.locator("[data-testid='org-will-organize']")).to_be_visible(timeout=30_000)


def _summary(**overrides: Any) -> dict:
    base: dict = {
        "tier": "dedup",
        "files": 10,
        "photos": 10,
        "videos": 0,
        "audio": 0,
        "by_format": {},
        "new_unique": 5,
        "near_dup": 2,
        # The number the card and the confirm control both render, `(abl)`/`(acx)`. A mock
        # without it renders "0 files" and no confirm block - which is how the payload
        # says a field is now load-bearing rather than decorative.
        "will_organize": 7,
        "exact_dup": 2,
        "exact_dup_matches": {"total": 0, "shown": []},
        "near_dup_matches": {"total": 0, "shown": []},
        "undated": 3,
        "sentinel_rejected": 0,
        "future_rejected": 0,
        "suspect_default": 0,
        "folders": {},
        "skipped": {"documents": {}, "unrecognized": {}, "exiftool_backups": {}},
        "unreadable_folders": [],
        "unreadable_files": {"total": 1, "shown": [{"name": "a.jpg", "reason": "permission"}]},
        "elapsed_seconds": 1.0,
    }
    base.update(overrides)
    return base


# --------------------------------------------------------------------------- resting state


def test_the_resting_screen_invents_no_metrics(ui: Page) -> None:
    """Organize is a form until it has run. A metric here would be a number we made up."""
    expect(ui.locator("#screen-organize")).to_be_visible()
    assert ui.locator("#screen-organize .metric").count() == 0, (
        "a metric is on the resting Organize screen, where no real number exists yet"
    )


# --------------------------------------------------------------------------- the tally defect


def test_the_card_and_the_confirm_control_state_the_same_number(ui: Page) -> None:
    """`(abl)`: they disagreed by `near_dup` for weeks, and both were on screen at once.

    The card said *"5 new - will be organized"* while the button below said *"Organize 7 files"*,
    because each derived its own answer from the payload. Neither cited the other and nothing
    compared them, so the screen asked the reader to do arithmetic to discover the two agreed -
    and on any folder with a look-alike they did not.

    This is trivial now, and that is the argument for the fix rather than an objection to the
    test: both render one field. A future surface that starts deriving the number again fails
    here at the moment it is added, which is the only time it is cheap to correct.
    """
    _dedup(ui, _summary())
    card = ui.eval_on_selector("[data-testid='org-will-organize']", "el => el.textContent")
    button = ui.eval_on_selector("#org-confirm [data-typed-go]", "el => el.textContent")
    assert "7 files" in card, f"the card does not state the promise: {card!r}"
    assert "7" in button, f"the confirm control states a different number: {button!r}"


def test_the_tally_sums_to_the_files_it_counted(ui: Page) -> None:
    """The block reads as a partition, so it has to be one.

    5 + 2 + 2 + 1 unreadable = 10 files. `undated` (3) is deliberately not among them.
    """
    _dedup(ui, _summary())
    rows = ui.eval_on_selector_all(
        "[data-testid='org-tally'] .metric",
        "els => els.map(e => ({n: e.querySelector('.metric-value').textContent.trim(),"
        " label: e.querySelector('.metric-label').textContent.trim()}))",
    )
    assert rows, "no tally metrics rendered"
    total = sum(int(r["n"].replace(",", "")) for r in rows)
    files = int(ui.eval_on_selector("[data-testid='org-tally']", "el => el.dataset.files"))
    assert total == files, (
        f"the tally sums to {total} but {files} files were counted: "
        + ", ".join(f"{r['n']} {r['label']}" for r in rows)
    )


def test_undated_is_stated_as_a_property_not_as_a_bucket(ui: Page) -> None:
    """It is counted over what will be organized, so it overlaps two of the rows above."""
    _dedup(ui, _summary())
    labels = ui.eval_on_selector_all(
        "[data-testid='org-tally'] .metric-label", "els => els.map(e => e.textContent.trim())"
    )
    assert not any("no date" in label.lower() for label in labels), (
        f"'no date' is still one of the summing rows: {labels}"
    )

    qualifier = ui.locator("[data-testid='org-undated']")
    expect(qualifier).to_be_visible()
    expect(qualifier).to_contain_text("3")


def test_the_unreadable_bucket_is_in_the_tally_not_only_in_a_banner(ui: Page) -> None:
    """It is the real fourth bucket; leaving it out is what stopped the block summing."""
    _dedup(ui, _summary())
    labels = ui.eval_on_selector_all(
        "[data-testid='org-tally'] .metric-label", "els => els.map(e => e.textContent.trim())"
    )
    assert any("could not be read" in label.lower() for label in labels), (
        f"the unreadable bucket is missing from the tally: {labels}"
    )


def test_a_run_with_nothing_unreadable_shows_no_zero_row(ui: Page) -> None:
    """A zero bucket is noise, and the sum still holds without it: 5 + 2 + 2 = 9 of 9."""
    _dedup(ui, _summary(files=9, unreadable_files={"total": 0, "shown": []}))
    labels = ui.eval_on_selector_all(
        "[data-testid='org-tally'] .metric-label", "els => els.map(e => e.textContent.trim())"
    )
    assert not any("could not be read" in label.lower() for label in labels), (
        "an empty unreadable bucket is being rendered as a zero row"
    )
    rows = ui.eval_on_selector_all(
        "[data-testid='org-tally'] .metric-value",
        "els => els.map(e => +e.textContent.replace(/,/g,''))",
    )
    assert sum(rows) == 9


# ------------------------------------------------------------------- the Look inside defect


def test_look_inside_never_says_nothing_is_here_about_a_folder_it_could_not_open(
    ui: Page,
) -> None:
    """The calibration case. `unreadable_dirs` was known and dropped from the payload."""
    _look_inside(ui, _inventory(files=0, photos=0, unreadable_folders=[f"{SOURCE}/Locked"]))

    block = ui.locator("[data-testid='org-unreadable']")
    expect(block).to_be_visible()
    expect(block).to_contain_text("Locked")
    expect(block).to_contain_text("could not be opened")


def test_look_inside_reports_an_unopenable_folder_even_when_it_did_find_media(ui: Page) -> None:
    """A partial answer is still partial: some files found does not mean everything was seen."""
    _look_inside(ui, _inventory(files=4, unreadable_folders=[f"{SOURCE}/Locked"]))
    expect(ui.locator("[data-testid='org-unreadable']")).to_be_visible()


def test_an_ordinary_look_inside_grows_no_warning(ui: Page) -> None:
    """Anti-cry-wolf: the block appears only when there is something to report."""
    _look_inside(ui, _inventory())
    assert ui.locator("[data-testid='org-unreadable']").count() == 0


# --------------------------------------------------------------------------- the panel


def test_the_panel_carries_library_facts_and_no_controls(ui: Page) -> None:
    """`duplicate_bytes`, `largest_files` and `capture_span` compute today and reached nothing."""
    ui.set_viewport_size({"width": 1500, "height": 900})
    _dedup(
        ui,
        _summary(
            duplicate_bytes={"total": 2048, "shown": 2},
            capture_span={"oldest": "2014-08-14", "newest": "2019-01-02"},
        ),
    )
    panel = ui.locator("#panel")
    expect(panel).to_be_visible()
    expect(panel).to_contain_text("2014-08-14")

    controls = ui.evaluate(
        "() => document.querySelectorAll("
        " '#panel button, #panel input, #panel select, #panel a[href], #panel [data-testid]'"
        ").length"
    )
    assert controls == 0, "the panel gained a control; it is not rendered on narrow windows"


def test_the_panel_is_gone_below_the_threshold_and_the_result_is_not(ui: Page) -> None:
    """Supplementary means the task survives without it."""
    ui.set_viewport_size({"width": 1200, "height": 900})
    _dedup(ui, _summary(capture_span={"oldest": "2014-08-14", "newest": "2019-01-02"}))
    expect(ui.locator("#panel")).to_be_hidden()
    expect(ui.locator("[data-testid='org-tally']")).to_be_visible()


# --------------------------------------------------------------------------- the bar


def test_the_progress_bar_on_this_screen_is_the_shared_component(ui: Page) -> None:
    """`.bar` migrates here; the other screens keep theirs until they move."""
    assert ui.locator("#org-card .proportion").count() == 1, (
        "the organize run block is not using the shared proportion bar"
    )
    assert ui.locator("#org-card .bar").count() == 0, "the old .bar is still on this screen"
