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


def _unreadable_folders(*paths: str) -> list[dict]:
    """One `skipped_folders` group, worded as `models` words it. `(aer)`

    The stub carries the label and remedy because the payload does: the browser maps no reason to
    a sentence, which `test_the_browser_holds_no_folder_wording.py` asserts against `models`' real
    strings. A stub that invented wording here would test the stub.
    """
    return [
        {
            "reason": "unreadable",
            "label": "folders that could not be opened",
            "remedy": "check the folder's permissions and try again to include what is inside",
            "folders": list(paths),
            "total": len(paths),
        }
    ]


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
        # The number the card and the confirm control both render, `(abl)`/`(acx)`. A mock
        # without it renders "0 files" and no confirm block - which is how the payload
        # says a field is now load-bearing rather than decorative.
        "will_organize": 4,
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
        "skipped_folders": [],
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

    ⚠ **The heading changed shape in `(aer)` and the reason is worth reading before "fixing" it
    back.** This said ``"1 folder could not be opened"`` - a sentence the browser built itself with
    ``plural()``. Wording now comes from `models.folder_skip_label`, so every surface prints
    ``"<label>: <count>"``, which is the form the CLI already used for every other skipped group.
    What this test pins is unchanged and is the part that matters: the count, the folder's name,
    *contents unknown*, and the verb.
    """
    _preview(ui, _summary(skipped_folders=_unreadable_folders("/tmp/pictures/Locked")))

    block = ui.locator("[data-testid='org-unreadable']")
    expect(block).to_be_visible(timeout=30_000)
    expect(block).to_contain_text("folders that could not be opened: 1")
    expect(block).to_contain_text("/tmp/pictures/Locked")
    expect(block).to_contain_text("contents unknown")
    # ⚠ "could not be read" is the FILE wording, and this assertion is why the CLI's phrasing was
    # NOT the one adopted. A folder was not read either, but saying so here would invite the count
    # the line above deliberately withholds - and `cli.py` had said exactly that, directly above
    # its own "files that could not be read: N". This lane is what caught it; pytest cannot.
    expect(block).not_to_contain_text("could not be read")


def test_a_hidden_folder_reaches_the_screen_with_its_own_remedy(ui: Page) -> None:
    """⚠ `(aer)`'s browser half: the reason nobody had looked at.

    The payload's folder list carried **unreadable** folders only, so a hidden one - `.MyAlbum`
    holding an entire album - reached no app surface at all. Same silence as the one this file was
    written for, one layer down, in the half that had been declared fixed.

    **The remedy must be the HIDDEN one**, not the permissions sentence: renaming is what the user
    can do about a dot-folder, and checking permissions on a folder nothing is wrong with is the
    exact misdirection `models.UnreadableReason` splits its own members to avoid. That is what
    makes this more than a second copy of the test above.
    """
    _preview(
        ui,
        _summary(
            skipped_folders=[
                {
                    "reason": "hidden",
                    "label": "hidden folders (not looked inside)",
                    "remedy": (
                        "rename it without the leading dot and try again to include what is in it"
                    ),
                    "folders": ["/tmp/pictures/.MyAlbum"],
                    "total": 1,
                }
            ]
        ),
    )

    block = ui.locator("[data-testid='org-unreadable']")
    expect(block).to_be_visible(timeout=30_000)
    expect(block).to_contain_text("hidden folders (not looked inside): 1")
    expect(block).to_contain_text(".MyAlbum")
    expect(block).to_contain_text("contents unknown")
    # Capitalised by `app.js` `sentence()`: the shared clause is bracketed by the CLI and opens a
    # sentence here. Asserted as rendered, because that is what a person reads.
    expect(block).to_contain_text("Rename it without the leading dot")
    # The wrong remedy would be worse than none: it sends someone to a permissions dialog for a
    # folder whose permissions are fine.
    expect(block).not_to_contain_text("permissions")


def test_two_reasons_are_two_groups_and_neither_borrows_the_other_s_remedy(ui: Page) -> None:
    """The discriminating case for the payload's shape, and the reason it is not two flat lists.

    One entry per REASON means a run that hit both must produce both headings and both remedies.
    A renderer that read only the first group, or that worded a remedy itself, passes every
    single-reason test above and fails here.
    """
    _preview(
        ui,
        _summary(
            skipped_folders=[
                {
                    "reason": "hidden",
                    "label": "hidden folders (not looked inside)",
                    "remedy": "rename it without the leading dot and try again",
                    "folders": ["/tmp/pictures/.MyAlbum"],
                    "total": 1,
                },
                {
                    "reason": "unreadable",
                    "label": "folders that could not be opened",
                    "remedy": "check the folder's permissions and try again",
                    "folders": ["/tmp/pictures/Locked"],
                    "total": 1,
                },
            ]
        ),
    )

    block = ui.locator("[data-testid='org-unreadable']")
    expect(block).to_contain_text("hidden folders (not looked inside): 1", timeout=30_000)
    expect(block).to_contain_text("folders that could not be opened: 1")
    expect(block).to_contain_text(".MyAlbum")
    expect(block).to_contain_text("Locked")
    # Capitalised by `app.js` `sentence()`: the shared clause is bracketed by the CLI and opens a
    # sentence here. Asserted as rendered, because that is what a person reads.
    expect(block).to_contain_text("Rename it without the leading dot")
    expect(block).to_contain_text("Check the folder's permissions")


def test_a_capped_folder_list_says_how_many_it_hid_and_counts_folders(ui: Page) -> None:
    """Truncation is never silent here either - and the number is of FOLDERS.

    `total` counting folders rather than the files inside them is the whole rule this entry
    restored, so the browser is asserted against a case where the two could differ: 25 folders
    named, 3 elided, and not one statement about what is in any of them.
    """
    _preview(
        ui,
        _summary(
            skipped_folders=[
                {
                    "reason": "hidden",
                    "label": "hidden folders (not looked inside)",
                    "remedy": "rename it without the leading dot and try again",
                    "folders": [f"/tmp/pictures/.a{i:02d}" for i in range(25)],
                    "total": 28,
                }
            ]
        ),
    )

    block = ui.locator("[data-testid='org-unreadable']")
    expect(block).to_contain_text("hidden folders (not looked inside): 28", timeout=30_000)
    expect(block).to_contain_text("and 3 more")


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
