"""A source truestill could not read is on the screen, in words (`BACKLOG.md` ``(aac)``).

Two facts, one question. A user asks "did you see everything of mine?", and until now the app
answered yes in both of the cases where it should not have:

* an unreadable **file** was invisible everywhere - the engine folded it into the same empty
  hashes the size pre-filter produces for a file it legitimately skipped;
* an unreadable **folder** was worse in a quieter way. ``unreadable_folders`` has been in the
  preview payload since it shipped and **no code in `app.js` ever rendered it**, so the fact
  reached the browser and stopped there.

Asserted here rather than in pytest because the defect is what a person reads, and §9 is
explicit that this lane asserts **words, never element ids** - an id-based check would have
passed throughout the entire period the folders key was dead.

The payload is stubbed. Its *shape* is pinned by `test_unreadable_files_payload.py` against the
real service; what only a browser can answer is whether any of it reaches the screen.
"""

from __future__ import annotations

import json

from playwright.sync_api import Page, expect


def _json_route(route, body: dict) -> None:
    route.fulfill(status=200, content_type="application/json", body=json.dumps(body))


def _preview(ui: Page, summary: dict) -> None:
    """Drive the dedup preview to a done-event carrying ``summary``.

    The cheap inventory has to be stubbed and clicked first: "Check for duplicates" stays
    disabled until it reports media, which is the app's own progressive-disclosure rule.
    """
    ui.route(
        "**/api/organize/inventory",
        lambda r: _json_route(
            r,
            {
                "files": 4,
                "photos": 4,
                "videos": 0,
                "audio": 0,
                "by_format": {},
                "total_bytes": 4_000,
                "skipped": {"documents": {}, "unrecognized": {}, "exiftool_backups": {}},
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
    ui.fill("#org-source", "/tmp/pictures")
    ui.fill("#org-dest", "/tmp/library")
    ui.click("#org-preview")
    expect(ui.locator("#org-dedup")).to_be_enabled(timeout=30_000)
    ui.click("#org-dedup")


def _summary(**overrides: object) -> dict:
    base: dict = {
        "tier": "dedup",
        "files": 4,
        "photos": 4,
        "videos": 0,
        "audio": 0,
        "by_format": {},
        "new_unique": 4,
        "near_dup": 0,
        "exact_dup": 0,
        "exact_dup_matches": {"total": 0, "shown": []},
        "near_dup_matches": {"total": 0, "shown": []},
        "undated": 0,
        "sentinel_rejected": 0,
        "suspect_default": 0,
        "inferred_local_shifts": [],
        "folders": {"Camera": 4},
        "destination_is_drive": False,
        "skipped": {"documents": {}, "unrecognized": {}, "exiftool_backups": {}},
        "unreadable_folders": [],
        "unreadable_files": {"total": 0, "shown": []},
        "mode": "copy",
        "mechanism": "copy",
    }
    return {**base, **overrides}


def test_an_unreadable_file_is_named_on_screen_with_its_reason(ui: Page) -> None:
    """The count, the filename and the remedy - three things, because one is not enough.

    A bare count cannot be acted on and a bare name does not say what to do about it. The
    reasons differ on purpose: a permission is the user's to fix, an I/O error is the disk's.
    """
    _preview(
        ui,
        _summary(
            unreadable_files={
                "total": 2,
                "shown": [
                    {
                        "name": "DSC_0042.jpg",
                        "path": "/tmp/p/DSC_0042.jpg",
                        "reason": "permission denied",
                    },
                    {
                        "name": "IMG_1180.heic",
                        "path": "/tmp/p/IMG_1180.heic",
                        "reason": "input/output error",
                    },
                ],
            }
        ),
    )

    block = ui.locator("[data-testid='org-unreadable']")
    expect(block).to_be_visible(timeout=30_000)
    expect(block).to_contain_text("2 files could not be read")
    expect(block).to_contain_text("DSC_0042.jpg")
    expect(block).to_contain_text("permission denied")
    expect(block).to_contain_text("IMG_1180.heic")
    expect(block).to_contain_text("input/output error")
    expect(block).to_contain_text("Fix the permission or check the disk")


def test_an_unreadable_folder_is_named_and_says_its_contents_are_unknown(ui: Page) -> None:
    """The half that reached the browser and was never drawn.

    No count of what is inside, on purpose: that number is exactly what could not be read, so
    printing one would invent the missing figure. "contents unknown" is the honest form.
    """
    _preview(ui, _summary(unreadable_folders=["/tmp/pictures/Locked"]))

    block = ui.locator("[data-testid='org-unreadable']")
    expect(block).to_be_visible(timeout=30_000)
    expect(block).to_contain_text("1 folder could not be opened")
    expect(block).to_contain_text("/tmp/pictures/Locked")
    expect(block).to_contain_text("contents unknown")
    # "could not be read" is the FILE wording. A folder was not read either, but saying so here
    # would invite the count that the line above deliberately withholds.
    expect(block).not_to_contain_text("could not be read")


def test_a_shortened_list_says_how_many_it_hid(ui: Page) -> None:
    """Truncation is never silent: a capped list that looks complete is a false all-clear."""
    _preview(
        ui,
        _summary(
            unreadable_files={
                "total": 205,
                "shown": [
                    {
                        "name": f"p{i:04d}.jpg",
                        "path": f"/tmp/p/p{i:04d}.jpg",
                        "reason": "permission denied",
                    }
                    for i in range(200)
                ],
            }
        ),
    )

    block = ui.locator("[data-testid='org-unreadable']")
    expect(block).to_contain_text("205 files could not be read", timeout=30_000)
    expect(block).to_contain_text("and 5 more")


def test_an_ordinary_preview_grows_no_warning_at_all(ui: Page) -> None:
    """The cry-wolf half. A block that appears when nothing is wrong teaches people to ignore it."""
    _preview(ui, _summary())

    expect(ui.locator("#org-result")).to_contain_text("found", timeout=30_000)
    expect(ui.locator("[data-testid='org-unreadable']")).to_have_count(0)


def test_a_skipped_group_the_engine_adds_reaches_the_screen(ui: Page) -> None:
    """The renderer must show whatever groups the payload carries, not three it names by hand.

    `hidden` was added to the engine's skipped census on 2026-08-04. `app.js` listed
    `documents`, `unrecognized` and `exiftool_backups` literally, so the new group would have
    reached the browser and stopped there - the same way `unreadable_folders` did, which is the
    defect this whole file exists for. Asserted through the browser because a payload can be
    perfectly correct while nothing on the page reads it.
    """
    _preview(ui, _summary(skipped={"hidden": {".picasa.ini": 1}, "documents": {}}))
    result = ui.locator("#org-result")
    expect(result).to_contain_text("hidden")
    expect(result).to_contain_text(".picasa.ini")
