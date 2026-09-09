"""The stepper, the source counts and the action summary - the three projections nothing guarded.

⚠ **All three shipped in `fa85dac` with NO test anywhere in `tests/e2e/` naming them.** Before
this file, `grep -rn 'org-stepper\\|org-summary\\|org-source-counts' tests/e2e/` returned nothing:
the row could say any step, the counts could vanish, and the summary could state two different
denominators in one sentence, and the whole 1058-test lane stayed green. Every defect fixed in the
commit that adds this file was found by a person looking at the screen, which is the only way a
region with no assertions is ever found.

**Driven through the props seam** (`window.organizeResult`), the entry point
`test_the_preview_draws_the_destination_tree.py` and `test_the_grid_is_the_result.py` already use.
A real dedup pass cannot be made to produce these states on demand and driving one would test the
scanner instead of the projection.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from playwright.sync_api import Page, expect

STEPPER = "[data-testid='org-stepper']"
COUNTS = "[data-testid='org-source-counts']"
SUMMARY = "[data-testid='org-summary']"

#: The four steps, in the order the row draws them. `stepFor` maps every `ResultState` onto one.
STEPS = ("configure", "preview", "apply", "done")


def _summary(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "files": 69,
        "photos": 60,
        "videos": 9,
        "audio": 0,
        "by_format": {},
        "new_unique": 40,
        "near_dup": 0,
        "exact_dup": 29,
        "exact_dup_matches": None,
        "near_dup_matches": None,
        # 40, NOT 69: the run takes fewer files than the folder holds, which is what makes the
        # two-denominator defect visible at all. A fixture where they agree cannot see it.
        "will_organize": 40,
        "undated": 0,
        "sentinel_rejected": 0,
        "future_rejected": 0,
        "suspect_default": 0,
        "inferred_local_shifts": [],
        "folders": {"Camera": 40},
        "destination_tree": {"2014/2014-08": 40},
        "mode": "copy",
    }
    base.update(overrides)
    return base


def _view() -> dict[str, Any]:
    return {
        "skippingUndated": False,
        "already": {"kind": "none"},
        "destinationLabel": "TruestillLibrary",
        "copiesAgain": False,
    }


def _set(ui: Page, state: str, **payload: Any) -> None:
    ui.evaluate("([s]) => { window.organizeResult.set(s); }", [{"kind": state, **payload}])


def _preview(ui: Page, **overrides: Any) -> None:
    _set(ui, "preview", preview=_summary(**overrides), view=_view())
    expect(ui.locator("#org-result .card.result")).to_be_visible()


def _current_step(ui: Page) -> str:
    """The one step marked current. Asserts there is EXACTLY one before reading it, because a row
    with none would otherwise read as whatever the first element happened to be."""
    current = ui.locator(f"{STEPPER} .step[data-state='current']")
    expect(current).to_have_count(1)
    return current.get_attribute("data-step") or ""


# --- the stepper -----------------------------------------------------------------------------


def test_the_row_draws_the_four_steps_in_order(ui: Page) -> None:
    """Anti-vacuity for everything below: with no steps drawn, every assertion here is an empty
    read and `_current_step` would have nothing to find."""
    steps = ui.locator(f"{STEPPER} .step")
    expect(steps).to_have_count(4)
    assert [s.get_attribute("data-step") for s in steps.all()] == list(STEPS)


def test_a_preview_with_files_to_take_reads_apply_not_preview(ui: Page) -> None:
    """⚠ **THE STEPPER LIED, and this is the mapping it lied through.**

    `app.js` sets `kind: "preview"` and, eight lines later in the same handler, draws the typed
    confirm - the control that STARTS THE RUN. The row read "Preview" while the screen was asking
    the person to commit. A tracker's whole job is to say what is current, and it was calling the
    current step a finished one. The step is where the PERSON is, not which payload arrived.

    ⚠ **The confirm itself is NOT asserted here, deliberately.** `#org-confirm` is drawn by
    `app.js`, and this seam feeds the island only - so a `to_be_visible` on it would hang and a
    `count() == 0` would pass for the wrong reason, which is the vacuity this repo keeps finding.
    The COUPLING between the control and the step is asserted on a real run, below.
    """
    _preview(ui)

    assert _current_step(ui) == "apply", "the row says Preview where the run confirm belongs"


def test_a_preview_with_nothing_to_take_stays_on_preview(ui: Page) -> None:
    """**The cry-wolf half, and it is what keeps the rule honest.** If the step advanced on the
    `preview` KIND it would say Apply here too - and a folder whose every file is already
    organized offers no run to start, so there is no decision and nothing to advance to."""
    _preview(ui, will_organize=0)

    assert _current_step(ui) == "preview", "the row advanced to Apply with no run to start"


def test_on_a_real_run_the_step_says_apply_exactly_when_the_confirm_is_on_screen(
    ui: Page, tmp_path: Path, library
) -> None:
    """**The coupling, through the real flow rather than the seam.**

    The two tests above pin the mapping; this one pins that the mapping describes the screen.
    It drives an actual Look inside and duplicate check, so `app.js` draws `#org-confirm` itself
    - and that is the only way to assert that the control and the step agree, because the seam
    cannot produce the control.
    """
    source = library(3, name="Lib")
    ui.check('input[name="org-mode"][value="copy"]')
    ui.fill("#org-source", str(source))
    ui.fill("#org-dest", str(tmp_path / "Out"))

    ui.click("#org-preview")
    expect(ui.locator("#org-result")).to_contain_text("photos found", timeout=30_000)
    # Look inside has answered and nothing has been committed to: still Preview.
    assert _current_step(ui) == "preview"

    ui.click("#org-dedup")
    expect(ui.locator("#org-confirm [data-typed-confirm]")).to_be_visible(timeout=60_000)
    assert _current_step(ui) == "apply", (
        "the typed confirm is on screen and the row still does not say Apply"
    )


def test_the_inventory_step_is_preview_and_a_finished_run_is_done(ui: Page) -> None:
    """The two ends, so the mapping is asserted across its range rather than at one point."""
    _set(ui, "inventory", inventory=_summary())
    assert _current_step(ui) == "preview"

    _set(ui, "complete", html="<div class='card result'>done</div>")
    assert _current_step(ui) == "done"


# --- the counts beside the folder field ------------------------------------------------------


def test_the_counts_survive_the_start_of_the_run(ui: Page) -> None:
    """⚠ **They used to blink out at the moment of most attention.** `running` carries an html
    payload and not the inventory, so the extractor returned `null` and three figures disappeared
    the instant the run began. Nothing about the folder had changed - the island had stopped
    being told."""
    _preview(ui)
    # TWO, not three: no organize payload has ever carried a byte count, so the "on disk" figure
    # this used to expect never rendered. `organize.py:OrganizeInventory` has `total_bytes` and
    # `OrganizeDedupCore` has none.
    expect(ui.locator(f"{COUNTS} .metric")).to_have_count(2)

    _set(ui, "running", html="<div class='card result'>working</div>")
    expect(ui.locator(f"{COUNTS} .metric")).to_have_count(2)
    expect(ui.locator(COUNTS)).to_contain_text("60")


def test_a_finished_run_clears_them_rather_than_leaving_a_stale_figure(ui: Page) -> None:
    """**And this half is the reason it is a carry and not a freeze.** After a MOVE or an
    in-place run the source folder no longer holds what Look inside found, so the figure beside
    its name is not stale - it is false. The completion card owns the finished numbers."""
    _preview(ui)
    expect(ui.locator(f"{COUNTS} .metric")).to_have_count(2)

    _set(ui, "complete", html="<div class='card result'>done</div>")
    expect(ui.locator(f"{COUNTS} .metric")).to_have_count(0)


def test_a_figure_of_zero_is_omitted_rather_than_printed(ui: Page) -> None:
    """⚠ **It printed "0 videos" from a component whose docstring says it never zeros.** The video
    figure was pushed unconditionally while the size was pushed conditionally, so the rule was
    stated in one paragraph and broken two lines under it. A folder of photographs now shows one
    metric, not one metric and a confident nothing."""
    _preview(ui, photos=6, videos=0)

    metrics = ui.locator(f"{COUNTS} .metric")
    expect(metrics).to_have_count(1)
    expect(metrics).to_contain_text("photos")
    expect(ui.locator(COUNTS)).not_to_contain_text("video")


def test_a_folder_of_videos_keeps_the_video_figure_and_drops_the_photo_one(ui: Page) -> None:
    """**The cry-wolf half.** A rule that only ever hides videos would pass the test above by
    hiding the wrong thing; this fails unless the omission is keyed on the VALUE."""
    _preview(ui, photos=0, videos=4)

    metrics = ui.locator(f"{COUNTS} .metric")
    expect(metrics).to_have_count(1)
    expect(metrics).to_contain_text("videos")
    expect(ui.locator(COUNTS)).not_to_contain_text("photo")


def test_an_invalidated_screen_drops_the_carried_answer(ui: Page) -> None:
    """A changed field throws the result away, and the figures describe a question nobody asked."""
    _preview(ui)
    expect(ui.locator(f"{COUNTS} .metric")).to_have_count(2)

    _set(ui, "resting")
    expect(ui.locator(f"{COUNTS} .metric")).to_have_count(0)


# --- the action summary ----------------------------------------------------------------------


def test_the_summary_states_one_denominator_and_it_is_the_run_s(ui: Page) -> None:
    """⚠ **It used to state two, six pixels apart.** The count came from `will_organize` - the 40
    files the run will take - and the size came from the inventory's total for all 69. One
    sentence, two different sets, and nothing on screen to tell the reader they were different.

    The size is gone rather than corrected: a "bytes this run will write" field does not exist in
    the payload, and adding one is a contract regeneration to put a decoration back.
    """
    _preview(ui)

    summary = ui.locator(SUMMARY)
    expect(summary).to_be_visible()
    expect(summary).to_contain_text("40 files")
    # The inventory total, which is what the dropped clause was derived from.
    expect(summary).not_to_contain_text("GB")
    expect(summary).not_to_contain_text("69")
