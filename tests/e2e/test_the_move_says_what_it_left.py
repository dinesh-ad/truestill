"""A move that could not take everything says so, in the two places it has to.

`test_overlapping_organize_runs.py` measured the behaviour: organizing `A` after `A/D/E` in move
mode reports `organized: 5, duplicates: 3` and leaves those three in `D/E`. The source comes back
PARTIALLY emptied - harder to read than "nothing happened" - and the empty-folder offer that
follows names `B` and `C` and is silent about `D/E`, because `plan_cleanup` correctly drops an
occupied folder. So the app tidied around the leftover files without mentioning them.

Two sentences, because they answer different questions:

* the PREVIEW says what will happen, while the user can still change their mind;
* the RESULT says what to do now, and it is the only place the leftover files are explained
  after the fact.

§9 asserts on the words a person reads, never on element ids: every defect in that section was a
wrong string inside an element that existed and rendered.
"""

from __future__ import annotations

import json
from typing import Any

from playwright.sync_api import Page, expect

SOURCE = "/tmp/pictures"


def _json_route(route: Any, body: dict) -> None:
    route.fulfill(status=200, content_type="application/json", body=json.dumps(body))


def _preview(ui: Page, **overrides: Any) -> None:
    """Drive Organize to a rendered dedup preview in move mode."""
    summary: dict = {
        "tier": "dedup",
        "files": 8,
        "photos": 8,
        "videos": 0,
        "audio": 0,
        "by_format": {},
        "new_unique": 3,
        "near_dup": 0,
        # The number the card and the confirm control both render, `(abl)`/`(acx)`. A mock
        # without it renders "0 files" and no confirm block - which is how the payload
        # says a field is now load-bearing rather than decorative.
        "will_organize": 3,
        "exact_dup": 5,
        "exact_dup_matches": {
            "total": 5,
            "shown": [],
            "already_in_library": 5,
            "within_this_batch": 0,
            "unclassified": 0,
        },
        "near_dup_matches": {"total": 0, "shown": []},
        "undated": 0,
        "sentinel_rejected": 0,
        "future_rejected": 0,
        "suspect_default": 0,
        "folders": {},
        "skipped": {},
        "unreadable_folders": [],
        "unreadable_files": {"total": 0, "shown": []},
        "mode": "move",
    }
    summary.update(overrides)
    ui.route(
        "**/api/organize/inventory",
        lambda r: _json_route(
            r,
            {
                "tier": "inventory",
                "files": 8,
                "photos": 8,
                "videos": 0,
                "audio": 0,
                "by_format": {},
                "total_bytes": 8000,
                "skipped": {},
                "unreadable_folders": [],
            },
        ),
    )
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
    expect(ui.locator("#org-result .card")).to_be_visible(timeout=30_000)


def _completion(ui: Page, **overrides: Any) -> None:
    """Render a finished move by handing `organizeCompletion` the payload the server builds.

    The confirm gate ahead of a real run is a typed word on a destructive action, and driving it
    would test the gate rather than the sentence. The payload is the seam that matters here, and
    it is the shape `service/organize.py` returns.
    """
    summary: dict = {
        "organized": 5,
        "photos": 5,
        "videos": 0,
        "audio": 0,
        "bytes_organized": 5000,
        "duplicates": 3,
        "bytes_saved": 3000,
        "moved_by_copy": 5,
        "moved_in_place": 0,
        "failed": 0,
        "folders": {},
        "outcomes": {"organized": 5, "duplicate": 3},
        "mode": "move",
        "left_in_source": {
            "total": 3,
            "already_in_library": 3,
            "within_this_batch": 0,
            "unclassified": 0,
            "folders": [{"folder": "D/E", "files": 3}],
            "folders_total": 1,
        },
        "leftover_empty_folders": {
            "source_root": SOURCE,
            "emptied": ["B", "C"],
            "count": 2,
            "folders": ["B", "C"],
        },
    }
    summary.update(overrides)
    ui.evaluate(
        "(s) => { document.getElementById('org-result').innerHTML = organizeCompletion(s); }",
        summary,
    )
    expect(ui.locator("#org-result .card")).to_be_visible()


# ------------------------------------------------------------------------------ the preview


def test_the_move_preview_says_which_files_it_will_not_take(ui: Page) -> None:
    """The count alone answers "how many", not "so what happens to my photos"."""
    _preview(ui)
    note = ui.locator("[data-testid='org-will-remain']")
    expect(note).to_be_visible()
    expect(note).to_contain_text("5")
    expect(note).to_contain_text("already in your library")
    expect(note).to_contain_text("will not be moved")


def test_a_copy_preview_does_not_promise_a_move(ui: Page) -> None:
    """CRY-WOLF HALF, and the answer for copy mode: the originals always stay, so there is
    nothing here the user did not already ask for."""
    _preview(ui, mode="copy")
    assert ui.locator("[data-testid='org-will-remain']").count() == 0


def test_a_move_preview_with_nothing_already_in_the_library_says_nothing(ui: Page) -> None:
    _preview(
        ui,
        exact_dup=0,
        new_unique=8,
        exact_dup_matches={
            "total": 0,
            "shown": [],
            "already_in_library": 0,
            "within_this_batch": 0,
            "unclassified": 0,
        },
    )
    assert ui.locator("[data-testid='org-will-remain']").count() == 0


def test_a_batch_twin_is_not_counted_as_a_file_that_stays(ui: Page) -> None:
    """It matched a file this very run is moving in, so it says nothing about the library and
    its original does not stay behind for that reason."""
    _preview(
        ui,
        exact_dup_matches={
            "total": 5,
            "shown": [],
            "already_in_library": 0,
            "within_this_batch": 5,
            "unclassified": 0,
        },
    )
    assert ui.locator("[data-testid='org-will-remain']").count() == 0


# ------------------------------------------------------------------------------- the result


def test_the_finished_move_names_the_folder_the_leftovers_are_in(ui: Page) -> None:
    """THE SENTENCE THIS CHANGE EXISTS FOR. "3 files remain" is weaker than "in D/E"."""
    _completion(ui)
    note = ui.locator("[data-testid='org-left-in-source']")
    expect(note).to_be_visible()
    expect(note).to_contain_text("3 files remain in D/E")
    expect(note).to_contain_text("already in your library")


def test_the_result_says_nothing_of_the_users_was_deleted(ui: Page) -> None:
    """The fear a leftover report invites, answered in the same breath rather than left open."""
    _completion(ui)
    expect(ui.locator("[data-testid='org-left-in-source']")).to_contain_text("deleted")


def test_the_leftovers_are_read_before_the_offer_to_tidy_up(ui: Page) -> None:
    """The offer names B and C and cannot mention D/E - `plan_cleanup` drops occupied folders.

    Read first, it leaves a person thinking the source is now tidy while their photos sit in it.
    """
    _completion(ui)
    order = ui.evaluate(
        "() => { const notes = [...document.querySelectorAll('#org-result .banner')];"
        " const left = notes.findIndex(n => n.dataset.testid === 'org-left-in-source');"
        " const tidy = notes.findIndex(n => n.textContent.includes('empty'));"
        " return [left, tidy]; }"
    )
    assert order[0] >= 0, "the leftover note did not render"
    assert order[1] >= 0, "the cleanup offer did not render"
    assert order[0] < order[1], "the offer to tidy up is read before the files it does not name"


def test_a_move_that_left_nothing_gains_no_note(ui: Page) -> None:
    """CRY-WOLF HALF. `left_in_source` is absent, not zeroed, when there is nothing to say."""
    _completion(ui, left_in_source=None, duplicates=0, organized=8)
    assert ui.locator("[data-testid='org-left-in-source']").count() == 0


def test_several_folders_are_each_named_with_their_count(ui: Page) -> None:
    _completion(
        ui,
        left_in_source={
            "total": 8,
            "already_in_library": 8,
            "within_this_batch": 0,
            "unclassified": 0,
            "folders": [{"folder": "C", "files": 5}, {"folder": "D/E", "files": 3}],
            "folders_total": 2,
        },
    )
    note = ui.locator("[data-testid='org-left-in-source']")
    expect(note).to_contain_text("C (5)")
    expect(note).to_contain_text("D/E (3)")
    expect(note).to_contain_text("8 files remain")


def test_two_reasons_stop_the_sentence_claiming_one(ui: Page) -> None:
    """With both present, no single "because" clause is true of every file."""
    _completion(
        ui,
        left_in_source={
            "total": 4,
            "already_in_library": 3,
            "within_this_batch": 1,
            "unclassified": 0,
            "folders": [{"folder": "D/E", "files": 4}],
            "folders_total": 1,
        },
    )
    text = ui.eval_on_selector("[data-testid='org-left-in-source']", "el => el.textContent")
    assert "because" not in text, text
    assert "3 already in your library" in text, text
    assert "1 matched another file earlier in this batch" in text, text


def test_a_file_left_in_the_chosen_folder_itself_is_not_given_an_invented_name(ui: Page) -> None:
    """There is no relative name for the source root, so the sentence names it as what the user
    picked rather than printing an empty folder name."""
    _completion(
        ui,
        left_in_source={
            "total": 1,
            "already_in_library": 1,
            "within_this_batch": 0,
            "unclassified": 0,
            "folders": [{"folder": "", "files": 1}],
            "folders_total": 1,
        },
    )
    note = ui.locator("[data-testid='org-left-in-source']")
    expect(note).to_contain_text("1 file remains in the folder you selected")


def test_a_truncated_folder_list_says_how_many_it_did_not_name(ui: Page) -> None:
    _completion(
        ui,
        left_in_source={
            "total": 90,
            "already_in_library": 90,
            "within_this_batch": 0,
            "unclassified": 0,
            "folders": [{"folder": f"f{i}", "files": 3} for i in range(5)],
            "folders_total": 11,
        },
    )
    expect(ui.locator("[data-testid='org-left-in-source']")).to_contain_text("6 more folders")
