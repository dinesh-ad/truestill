"""The frame: the step row, the action bar, the first-run question and the column width.

⚠ **One cause behind four defects, and none of them had an assertion.** Measured at 1440x900
across one run before this file existed: the step row sat at y=+141, **-98, -308, -30** - off
screen in three of four states; the action bar was `static` with its primary at y=1051, 1017 and
**1637** against a 900px viewport; the first-run question was still open underneath the typed
confirm; and the content column went 1144, 1144, **896**, 896, so every line re-wrapped at the
moment the reader started reading the preview.

**Nothing on the screen held still**, and the whole 1058-test lane was green throughout, because
no test named the stepper, the bar's position, the question's close, or the column's width.
"""

from __future__ import annotations

import json
from pathlib import Path

from playwright.sync_api import Page, expect

STEPPER = "#org-stepper"
BAR = "#org-actionbar"
CARD = ".screen.active .card"
QUESTION = "[data-testid='org-first-run']"


def _y(ui: Page, selector: str) -> float:
    return float(ui.eval_on_selector(selector, "el => el.getBoundingClientRect().y"))


def _width(ui: Page, selector: str) -> float:
    return float(ui.eval_on_selector(selector, "el => el.getBoundingClientRect().width"))


def _position(ui: Page, selector: str) -> str:
    return str(ui.eval_on_selector(selector, "el => getComputedStyle(el).position"))


def _tracks(ui: Page) -> list[str]:
    """The shell's grid columns. Three means the panel's track is held open."""
    columns = ui.eval_on_selector(".app", "el => getComputedStyle(el).gridTemplateColumns")
    return str(columns).split()


def _panel_is_empty(ui: Page) -> bool:
    return bool(ui.eval_on_selector("#panel", "el => el.innerHTML.trim() === ''"))


def _value(ui: Page, selector: str) -> str:
    return str(ui.eval_on_selector(selector, "el => el.value"))


def _status_with_prefilled_destination(ui: Page) -> None:
    """The payload a first run leaves when it organized nothing: a live hint, no declaration and
    no rows - so the question is open AND `#org-dest` prefills from the hint."""
    ui.route(
        "**/api/library/status",
        lambda r: r.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(
                {
                    "files": 0,
                    "photos": 0,
                    "videos": 0,
                    "audio": 0,
                    "bytes": 0,
                    "by_format": {},
                    "places": 0,
                    "single_copy": 0,
                    "files_no_copy": 0,
                    "files_one_copy": 0,
                    "redundancy_floor": 0,
                    "files_on_a_drive": 0,
                    "held_floor": 0,
                    "library_path": "/tmp/AlreadyThere",
                    "library_root": None,
                    "needs_library_root": True,
                    "backup_path": None,
                    "never_checked_drives": [],
                    "catalog_path": "/tmp/c.sqlite",
                    "catalog_presence": "will_create",
                    "catalog_detail": "",
                    "catalog_tone": "info",
                }
            ),
        ),
    )
    ui.reload()
    ui.wait_for_selector(".nav-item")


def test_the_step_row_is_still_on_screen_after_scrolling(ui: Page, tmp_path: Path, library) -> None:
    """⚠ **The one element whose entire job is orientation, and it scrolled away.**

    It was the last child of `<header>`, and `position: sticky` is bounded by the parent's box -
    so its sticky range was zero and it left with the header. It is a child of `.screen` now.

    Asserted after a REAL scroll rather than by reading `position: sticky` off the element: the
    property being set is a declaration, and this test is about where the row actually is.
    """
    # A SHORT viewport and a real result, so there is genuinely something to scroll past. At
    # 900px with three files the page only moves 180px, and a test that cannot scroll cannot see
    # this defect at all.
    ui.set_viewport_size({"width": 1440, "height": 600})
    source = library(3, name="Lib")
    ui.fill("#org-source", str(source))
    ui.fill("#org-dest", str(tmp_path / "Out"))
    ui.click("#org-preview")
    expect(ui.locator("#org-result")).to_contain_text("photos found", timeout=30_000)

    before = _y(ui, STEPPER)
    ui.mouse.wheel(0, 900)
    ui.wait_for_timeout(400)
    after = _y(ui, STEPPER)

    # Anti-vacuity: if the page did not actually scroll, "still visible" proves nothing.
    scrolled = ui.eval_on_selector(".main", "el => el.scrollTop")
    assert scrolled > 200, f"the page did not scroll ({scrolled}px), so this test saw nothing"

    assert 0 <= after <= 120, (
        f"the step row is at y={after:.0f} after scrolling {scrolled}px (it was at {before:.0f}) - "
        "an orientation control that leaves the screen is worse than none"
    )
    expect(ui.locator(f"{STEPPER} .step[data-state='current']")).to_be_visible()


def test_the_question_closes_once_a_destination_names_the_folder(ui: Page) -> None:
    """⚠ **It stayed open through Look inside, the duplicate check and the typed confirm**, because
    the server's `needs_library_root` only turns false once the catalog has ROWS - which happens
    after a run finishes. A one-time setup question that is still asking while the answer sits in
    a field six inches below it is the screen repeating itself.
    """
    expect(ui.locator(QUESTION)).to_be_visible(timeout=30_000)

    ui.fill("#org-dest", "/tmp/Somewhere")
    expect(ui.locator(QUESTION)).to_be_hidden()


def test_clearing_the_destination_asks_again(ui: Page) -> None:
    """**The cry-wolf half.** Hiding on any input at all would pass the test above while breaking
    a first run that types a path and thinks better of it - the question is unanswered again and
    has to come back."""
    expect(ui.locator(QUESTION)).to_be_visible(timeout=30_000)
    ui.fill("#org-dest", "/tmp/Somewhere")
    expect(ui.locator(QUESTION)).to_be_hidden()

    ui.fill("#org-dest", "")
    expect(ui.locator(QUESTION)).to_be_visible()


def test_the_bar_sticks_once_the_question_is_answered(ui: Page) -> None:
    """The bar is un-stuck only while the question is genuinely open, and that window is now short.

    It used to be gated on the question being PRESENT, and the question never left - so the
    primary action sat below the fold for the whole run. Fixing the question's close fixed this
    without the condition changing, which is why the condition is asserted rather than the rule.
    """
    ui.set_viewport_size({"width": 1440, "height": 900})
    expect(ui.locator(QUESTION)).to_be_visible(timeout=30_000)
    assert _position(ui, BAR) == "static", "the bar is stuck over an open first-run question"

    ui.fill("#org-dest", "/tmp/Somewhere")
    expect(ui.locator(QUESTION)).to_be_hidden()
    assert _position(ui, BAR) == "sticky", "the bar did not stick once the question closed"
    assert _y(ui, BAR) < 900, "the primary action is below the fold with the question answered"


def test_a_source_only_state_has_its_primary_within_reach(ui: Page, library) -> None:
    """⚠ **THE GATE WAS ON A FIELD THE BUTTON DOES NOT USE.**

    "Look inside" posts `{ source }` alone - `app.js`'s handler says *"NO DESTINATION CHECK"* in
    as many words - but the bar was un-stuck whenever the first-run question was open, and the
    question stays open until a destination is named. So a person who typed a source path and
    reached for the one button needing nothing else found it at y=1051 in a 900px window.

    The state under test is source-filled, destination-empty: exactly the gap between the two
    fields' conditions, and the one a real first run walks through.
    """
    ui.set_viewport_size({"width": 1440, "height": 900})
    source = library(3, name="Lib")

    ui.fill("#org-source", str(source))
    ui.wait_for_timeout(200)

    # The precondition IS the finding: the question is still open, and the bar must stick anyway.
    expect(ui.locator(QUESTION)).to_be_visible()
    assert _value(ui, "#org-dest") == "", (
        "fixture check: the destination is filled, so the gap this test is about was skipped"
    )

    assert _position(ui, BAR) == "sticky", (
        "the action bar is un-stuck with a source typed - the one control that needs no "
        "destination is gated on the destination"
    )
    expect(ui.locator("#org-preview")).to_be_visible()
    reach = _y(ui, "#org-preview")
    assert reach < 900, (
        f"'Look inside' is at y={reach:.0f} in a 900px window - below the fold, and it is the "
        "only thing this state can do"
    )


def test_a_prefilled_destination_does_not_answer_the_question(ui: Page) -> None:
    """⚠ **THE SILENT-SATISFACTION FAILURE, IN THE OPPOSITE DIRECTION.**

    `organize.py` writes `path_hint.library` on every completed run, not only one that organized
    something, so a first run taking zero files leaves a hint with an empty catalog and
    `needs_library_root` still true. `app.js` prefills `#org-dest` from that hint five lines
    before `renderFirstRunLibrary` runs on the same load.
    `test_an_open_question_can_arrive_with_the_destination_already_filled_in` settles that the two
    coexist and `test_a_run_that_organized_nothing_still_writes_the_hint` that a real run gets
    there; this asserts the screen does not read the prefill as an answer.

    A question closed by a value nobody typed hides a decision the user was meant to make.
    """
    _status_with_prefilled_destination(ui)

    expect(ui.locator("#org-dest")).to_have_value("/tmp/AlreadyThere", timeout=30_000)
    expect(ui.locator(QUESTION)).to_be_visible()


def test_the_content_column_does_not_change_width_once_a_result_exists(
    ui: Page, tmp_path: Path, library
) -> None:
    """⚠ **248px, at the moment the reader started reading.** The panel fills at the duplicate-check
    step and `.panel:empty` had collapsed its grid track until then, so the column lost a fifth of
    its width and the whole preview re-wrapped under the reader.

    The track is reserved from the moment the source field holds a value - before anything is
    rendered - so the width is final by the time there is anything to read. Asserted ACROSS the
    tiers rather than at one of them, because a single reading cannot see a jump.
    """
    ui.set_viewport_size({"width": 1440, "height": 900})
    source = library(3, name="Lib")
    ui.fill("#org-source", str(source))
    ui.fill("#org-dest", str(tmp_path / "Out"))

    ui.click("#org-preview")
    expect(ui.locator("#org-result")).to_contain_text("photos found", timeout=30_000)
    at_inventory = _width(ui, CARD)
    tracks = _tracks(ui)
    panel_empty_then = _panel_is_empty(ui)

    ui.click("#org-dedup")
    expect(ui.locator("#org-confirm [data-typed-confirm]")).to_be_visible(timeout=60_000)
    at_preview = _width(ui, CARD)

    # ⚠ THE PRECONDITION, AND WITHOUT IT THIS TEST PROVES NOTHING. Equality alone passes on the
    # BROKEN layout too: with the track un-reserved the panel becomes an implicit grid column and
    # the measured width happened not to move, so the first draft of this test survived a mutation
    # that removed the fix entirely. What distinguishes them is the track being held open WHILE
    # the panel is still empty - which is the whole mechanism.
    assert panel_empty_then, (
        "fixture check: the panel already had content at the inventory tier, so the reservation "
        "this test is about was never exercised"
    )
    assert not _panel_is_empty(ui), (
        "fixture check: the panel never filled, so no jump was possible either way"
    )
    assert len(tracks) == 3, (
        f"the panel's grid track is not reserved while it is still empty: {tracks} - the column "
        "will narrow when it fills, under whatever the reader is reading"
    )
    assert at_inventory > 400, f"the card is {at_inventory:.0f}px wide - nothing was measured"
    assert at_inventory == at_preview, (
        f"the content column moved from {at_inventory:.0f}px to {at_preview:.0f}px when the panel "
        "filled - every line of the preview re-wrapped under the reader"
    )
