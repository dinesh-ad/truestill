"""The empty-folder cleanup says WHICH removal happened, and never dead-ends a refusal.

Two facts reached the browser and neither reached the screen.

`CleanEmptyApply` has carried `trashed` and `deleted` since it was written, and the card
rendered `removed` - the property that is their **sum**. So the one distinction that matters
after the fact, whether a folder is recoverable from the trash or gone, was computed by core,
serialised to the browser, and then added up and thrown away. The CLI has always split them
(`cli.py`, "N deleted permanently").

And after the 2026-08-04 refusal change, a machine with no trash gets no removal at all from
the app - which is the safe outcome, and was a **dead end**: the card said the folders could not
be removed and named no way to remove them, while the CLI route (`clean-empty --permanent`)
existed the whole time.

Routes are mocked here rather than driven through a real cleanup, deliberately: the disposition
being asserted is decided by the machine's trash backend, so a test that ran the real thing
would assert whatever the runner happens to have and would go green on a box where the branch
never fires. `deleted` is **structurally unreachable from the app** - the app has no permanent
mode - so the only honest way to pin its rendering at all is to hand the payload in.
"""

from __future__ import annotations

import json
from typing import Any

from e2e_support import open_screen
from playwright.sync_api import Page, expect

_SOURCE = "/tmp/src"


def _stage_a_cleanup_offer(ui: Page, *, preview: dict[str, Any], applied: dict[str, Any]) -> None:
    """Drive Trips to a completed apply that left one empty folder, then open the cleanup.

    The offer is reached through the real UI path rather than by calling the renderer, so the
    assertions below are about what a person actually gets to.
    """
    ui.route(
        "**/api/events/propose",
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(
                {
                    "ok": True,
                    "session": "sess",
                    "label": "Drive",
                    "cards": [
                        {
                            "kind": "event",
                            "start": "2021-01-01T00:00:00",
                            "end": "2021-01-01T00:00:00",
                            "count": 3,
                            "active_days": 1,
                            "days": [],
                        }
                    ],
                    "min_files": 8,
                    "declines": [],
                }
            ),
        ),
    )
    ui.route(
        "**/api/events/sess/apply",
        lambda route: route.fulfill(
            status=200, content_type="application/json", body='{"events":1,"trips":0}'
        ),
    )
    ui.route(
        "**/api/events/sess/preview",
        lambda route: route.fulfill(
            status=200, content_type="application/json", body='{"job_id":"prev-job"}'
        ),
    )
    ui.route(
        "**/api/jobs/prev-job/events**",
        lambda route: route.fulfill(
            status=200,
            content_type="text/event-stream",
            body=(
                'data: {"type":"done","status":"done","summary":{"ok":true,'
                '"moves":[{"old":"a.jpg","new":"Trip/a.jpg"}]}}\n\n'
            ),
        ),
    )
    ui.route(
        "**/api/events/sess/apply-to-disk",
        lambda route: route.fulfill(
            status=200, content_type="application/json", body='{"job_id":"apply-job"}'
        ),
    )
    ui.route(
        "**/api/jobs/apply-job/events**",
        lambda route: route.fulfill(
            status=200,
            content_type="text/event-stream",
            body=(
                'data: {"type":"done","status":"done","summary":{"migrated":3,"groups":[],'
                '"leftover_empty_folders":{"source_root":"' + _SOURCE + '",'
                '"emptied":["DCIM/100"],"count":1,"folders":["DCIM/100"]}}}\n\n'
            ),
        ),
    )
    ui.route(
        "**/api/clean-empty/preview",
        lambda route: route.fulfill(
            status=200, content_type="application/json", body=json.dumps(preview)
        ),
    )
    ui.route(
        "**/api/clean-empty/apply",
        lambda route: route.fulfill(
            status=200, content_type="application/json", body=json.dumps(applied)
        ),
    )

    open_screen(ui, "events")
    ui.fill("#ev-source", _SOURCE)
    ui.click("#ev-propose")
    ui.fill('.ev-name[data-i="0"]', "Trip")
    ui.click("#ev-apply")
    ui.click("#ev-apply-disk")
    expect(ui.locator("#ev-disk-result")).to_contain_text("empty folder")
    ui.click("#ev-disk-result [data-clean-preview]")


def _with_trash(removable: list[str]) -> dict[str, Any]:
    return {
        "ok": True,
        "path": _SOURCE,
        "backend": "send2trash",
        "removable": removable,
        "occupied": [],
    }


def _confirm(ui: Page) -> None:
    typed = ui.locator("#ev-disk-result [data-clean-stage] [data-typed-confirm]")
    expect(typed).to_be_visible()
    typed.fill("clean")
    ui.click("#ev-disk-result [data-clean-stage] [data-typed-go]")


def test_the_ordinary_removal_says_the_folders_went_to_the_trash(ui: Page) -> None:
    """Zero-deleted is now the normal case, so it is the one the wording has to be right for.

    The card must name the trash rather than report a bare total. "Removed 2 folders" is true of
    a permanent deletion too, which is the whole reason the split exists.
    """
    _stage_a_cleanup_offer(
        ui,
        preview=_with_trash(["DCIM/100", "DCIM/101"]),
        applied={
            "ok": True,
            "path": _SOURCE,
            "removed": 2,
            "trashed": 2,
            "deleted": 0,
            "failures": [],
        },
    )
    _confirm(ui)

    stage = ui.locator("#ev-disk-result [data-clean-stage]")
    expect(stage).to_contain_text("2 folders moved to the trash")
    # A zero bucket prints no line - never-silent is about what happened, not what did not.
    expect(stage).not_to_contain_text("deleted permanently")


def test_a_permanent_removal_is_named_as_permanent(ui: Page) -> None:
    """The branch the app cannot currently reach, pinned by handing the payload in.

    `deleted` is non-zero only under `--permanent`, which the app does not offer, so this cannot
    be produced by driving the UI. Rendering a branch nothing exercises is untested code that
    reads as though it works - and the day an app permanent mode is added, this is what says the
    renderer was ready rather than plausible.
    """
    _stage_a_cleanup_offer(
        ui,
        preview=_with_trash(["DCIM/100", "DCIM/101", "DCIM/102"]),
        applied={
            "ok": True,
            "path": _SOURCE,
            "removed": 3,
            "trashed": 1,
            "deleted": 2,
            "failures": [],
        },
    )
    _confirm(ui)

    stage = ui.locator("#ev-disk-result [data-clean-stage]")
    expect(stage).to_contain_text("1 folder moved to the trash")
    expect(stage).to_contain_text("2 folders deleted permanently")


def test_a_run_that_removed_nothing_says_so_and_names_the_refusals(ui: Page) -> None:
    """All-refused must not render as a removal with a zero in it."""
    _stage_a_cleanup_offer(
        ui,
        preview=_with_trash(["DCIM/100"]),
        applied={
            "ok": True,
            "path": _SOURCE,
            "removed": 0,
            "trashed": 0,
            "deleted": 0,
            "failures": ["DCIM/100: left in place - this drive would not accept it"],
        },
    )
    _confirm(ui)

    stage = ui.locator("#ev-disk-result [data-clean-stage]")
    expect(stage).to_contain_text("No folders were removed")
    expect(stage).to_contain_text("DCIM/100")


def test_no_trash_names_the_way_out_instead_of_dead_ending(ui: Page) -> None:
    """A refusal that names no route is a dead end, and this one had a route the whole time.

    The app has no permanent mode by deliberate deferral, so the way out is the CLI. Saying the
    folders cannot be removed *here* while never saying where they can be leaves a user with a
    correct sentence and nothing to do with it.
    """
    _stage_a_cleanup_offer(
        ui,
        preview={
            "ok": True,
            "path": _SOURCE,
            "backend": None,
            "removable": ["DCIM/100"],
            "occupied": [],
        },
        applied={},
    )

    stage = ui.locator("#ev-disk-result [data-clean-stage]")
    expect(stage).to_contain_text("no trash")
    expect(stage).to_contain_text("truestill clean-empty")
    expect(stage).to_contain_text("--permanent")
    # And it must not offer a confirm for a removal that cannot happen.
    expect(ui.locator("#ev-disk-result [data-clean-stage] [data-typed-confirm]")).to_have_count(0)
