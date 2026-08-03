"""A duplicate count on screen says where the twin is (`IMPLEMENTATION_STANDARDS.md` §9).

The tile used to read *"2,057 duplicates - identical to a kept file, will skip"*. The count is
true; the clause after it is not, for the case that matters most - when the twin is **already in
your library** there is no kept file in this batch to be identical to. And neither half answers
what a person is actually asking, which decides what they do next: if Truestill already has these,
the source copies are redundant; if the batch simply contained each photo twice, that says nothing
about the library at all.

Asserted in the browser rather than in pytest for the reason §9 gives for this whole lane: the
defect **is** the rendered sentence. `test_duplicate_matches_are_named.py` in the app package
pins the payload's shape, and a payload can be correct while nothing on the page reads it - which
is exactly how `unreadable_folders` reached the browser and stopped there for weeks.
"""

from __future__ import annotations

import json

from playwright.sync_api import Page, expect


def _json_route(route, body: dict) -> None:
    route.fulfill(status=200, content_type="application/json", body=json.dumps(body))


def _preview(ui: Page, summary: dict) -> None:
    """Drive the dedup preview to a done-event carrying ``summary``.

    The cheap inventory is stubbed and clicked first: "Check for duplicates" stays disabled
    until it reports media, which is the app's own progressive-disclosure rule.
    """
    ui.route(
        "**/api/organize/inventory",
        lambda r: _json_route(
            r,
            {
                "files": 9,
                "photos": 9,
                "videos": 0,
                "audio": 0,
                "by_format": {},
                "total_bytes": 9_000,
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


def _matches(*, library: int = 0, batch: int = 0, unclassified: int = 0) -> dict:
    total = library + batch + unclassified
    return {
        "total": total,
        "shown": [],
        "already_in_library": library,
        "within_this_batch": batch,
        "unclassified": unclassified,
    }


def _summary(**overrides: object) -> dict:
    base: dict = {
        "tier": "dedup",
        "files": 9,
        "photos": 9,
        "videos": 0,
        "audio": 0,
        "by_format": {},
        "new_unique": 1,
        "near_dup": 0,
        "exact_dup": 0,
        "exact_dup_matches": _matches(),
        "near_dup_matches": {"total": 0, "shown": []},
        "undated": 0,
        "sentinel_rejected": 0,
        "suspect_default": 0,
        "inferred_local_shifts": [],
        "folders": {"Camera": 1},
        "destination_is_drive": False,
        "skipped": {"documents": {}, "unrecognized": {}, "exiftool_backups": {}},
        "unreadable_folders": [],
        "unreadable_files": {"total": 0, "shown": []},
        "mode": "copy",
        "mechanism": "copy",
    }
    return {**base, **overrides}


def test_both_origins_are_named_on_screen(ui: Page) -> None:
    """The deliverable, in the words a person reads."""
    _preview(ui, _summary(exact_dup=8, exact_dup_matches=_matches(library=5, batch=3)))
    result = ui.locator("#org-result")
    expect(result).to_contain_text("5 already in your library")
    expect(result).to_contain_text("3 earlier in this batch")


def test_the_tile_no_longer_claims_a_kept_file_that_may_not_exist(ui: Page) -> None:
    """The false clause, gone. When the twin is in the library there is no kept file here."""
    _preview(ui, _summary(exact_dup=5, exact_dup_matches=_matches(library=5)))
    result = ui.locator("#org-result")
    expect(result).to_contain_text("not copied again")
    expect(result).not_to_contain_text("identical to a kept file")


def test_the_screen_never_says_a_duplicate_was_deleted(ui: Page) -> None:
    """The fear behind the original complaint. Nothing of the user's was removed."""
    _preview(ui, _summary(exact_dup=8, exact_dup_matches=_matches(library=5, batch=3)))
    text = (ui.locator("#org-result").inner_text() or "").casefold()
    assert "deleted" not in text
    assert "removed" not in text


def test_one_origin_only_shows_one_phrase(ui: Page) -> None:
    """A re-run of an already-organized folder is the common case and reads as one statement."""
    _preview(ui, _summary(exact_dup=5, exact_dup_matches=_matches(library=5)))
    result = ui.locator("#org-result")
    expect(result).to_contain_text("5 already in your library")
    expect(result).not_to_contain_text("earlier in this batch")


def test_a_run_with_no_duplicates_grows_no_origin_line(ui: Page) -> None:
    """Cry-wolf: a clean run must not sprout a block of zeroes explaining what did not happen."""
    _preview(ui, _summary(exact_dup=0))
    result = ui.locator("#org-result")
    expect(result).not_to_contain_text("already in your library")
    expect(result).not_to_contain_text("earlier in this batch")
