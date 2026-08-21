"""A preview that finds nearly everything already in the library says what the user is asking.

**External evidence, not a repo finding.** Lightroom users wanting an existing library rearranged
into dated folders are answered with a seven-step manual procedure repeated year by year, or a
rebuild in a fresh catalogue that loses flags, virtual copies, develop history and collections;
one concluded there was no solution but manual reimport. The visible exasperation is at being
told to use metadata instead of being answered.

Truestill already ships the answer - `migrate-layout`, crash-safe, journalled, resumable, with an
undo that refuses any file changed since - and a person re-pointing organize at their own library
is asking for it in the only vocabulary the screen offers them.

The pointer SUBSUMES the move-preview line rather than sitting beside it. Both open on the same
count, and stacking them reads as the app repeating itself. Above the threshold there is one
banner; below it, the line exactly as it shipped.
"""

from __future__ import annotations

import json
import re
from typing import Any

from playwright.sync_api import Page, expect

SOURCE = "/tmp/pictures"


def _json_route(route: Any, body: dict) -> None:
    route.fulfill(status=200, content_type="application/json", body=json.dumps(body))


def _drives(*entries: tuple[str, int, str, str | None]) -> dict:
    return {
        "total": sum(e[1] for e in entries),
        "unplaced": 0,
        "drives": [
            {"label": label, "files": files, "reach": reach, "path": path}
            for label, files, reach, path in entries
        ],
    }


def _preview(ui: Page, **overrides: Any) -> None:
    """Drive Organize to a rendered dedup preview. 440 of 460 already in the library."""
    summary: dict = {
        "tier": "dedup",
        "files": 460,
        "photos": 460,
        "videos": 0,
        "audio": 0,
        "by_format": {},
        "new_unique": 20,
        "near_dup": 0,
        # The number the card and the confirm control both render, `(abl)`/`(acx)`. A mock
        # without it renders "0 files" and no confirm block - which is how the payload
        # says a field is now load-bearing rather than decorative.
        "will_organize": 20,
        "exact_dup": 440,
        "exact_dup_matches": {
            "total": 440,
            "shown": [],
            "already_in_library": 440,
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
        "skipped_folders": [],
        "unreadable_files": {"total": 0, "shown": []},
        "mode": "copy",
        "matched_drives": _drives(("BackupA", 440, "connected", "/media/BackupA")),
    }
    summary.update(overrides)
    ui.route(
        "**/api/organize/inventory",
        lambda r: _json_route(
            r,
            {
                "tier": "inventory",
                "files": 460,
                "photos": 460,
                "videos": 0,
                "audio": 0,
                "by_format": {},
                "total_bytes": 460_000,
                "skipped": {},
                "skipped_folders": [],
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
    # Wait for the TALLY, not for `#org-result .card`: the inventory step already rendered a
    # card, so waiting on that returns before the dedup summary has landed - and every
    # `count() == 0` assertion below would then pass because nothing had rendered yet.
    expect(ui.locator("[data-testid='org-tally']")).to_be_visible(timeout=30_000)


POINTER = "[data-testid='org-rearrange']"
WILL_REMAIN = "[data-testid='org-will-remain']"


# --------------------------------------------------------------------------- it fires, and says


def test_it_names_the_drive_the_files_are_actually_on(ui: Page) -> None:
    """The whole reason the previous commit exists. Naming the wrong library is worse than
    naming none, and the destination box is not the answer."""
    _preview(ui)
    banner = ui.locator(POINTER)
    expect(banner).to_be_visible()
    expect(banner).to_contain_text("440 of 460")
    expect(banner).to_contain_text("BackupA")


def test_it_says_organizing_again_will_not_change_the_arrangement(ui: Page) -> None:
    """NOT "nothing will happen" - 20 files will be organized and the run is not pointless.

    The claim is narrower and it is the true one: re-organizing does not rearrange.
    """
    text = _text(ui)
    assert "will not change how they are arranged" in text, text
    assert "nothing will happen" not in text.lower(), text


def test_it_does_not_tell_the_user_to_do_something_else_instead(ui: Page) -> None:
    """They may well want both. "Instead" is the answer that made the incumbent's users
    exasperated - being redirected rather than answered."""
    assert "instead" not in _text(ui).lower(), _text(ui)


def test_it_offers_the_action_rather_than_describing_it(ui: Page) -> None:
    _preview(ui)
    expect(ui.locator(f"{POINTER} [data-rearrange-go]")).to_be_visible()


def _text(ui: Page) -> str:
    """The banner's words, whitespace collapsed.

    `expect(...).to_contain_text` normalises whitespace and raw `textContent` does not, so a
    sentence that happens to wrap in the template literal is not the same string twice. These
    assertions are about the wording, never about where it breaks.
    """
    if ui.locator(POINTER).count() == 0:
        _preview(ui)
    return re.sub(r"\s+", " ", ui.eval_on_selector(POINTER, "el => el.textContent")).strip()


# ------------------------------------------------------------------------------ the threshold


def test_a_folder_that_is_mostly_new_gets_no_pointer(ui: Page) -> None:
    """CRY-WOLF HALF, and the reason for a ratio at all. Below 0.8 a real minority is new,
    organizing IS the right action, and redirecting would answer a question nobody asked."""
    _preview(
        ui,
        new_unique=200,
        exact_dup=260,
        exact_dup_matches={
            "total": 260,
            "shown": [],
            "already_in_library": 260,
            "within_this_batch": 0,
            "unclassified": 0,
        },
        matched_drives=_drives(("BackupA", 260, "connected", "/media/BackupA")),
    )
    assert ui.locator(POINTER).count() == 0, "the pointer fired at 260/460"


def test_a_handful_of_files_gets_no_pointer_however_complete_the_match(ui: Page) -> None:
    """3 of 3 is 100% and means nothing - somebody testing with a folder. The floor is what
    stops a ratio alone from firing on a toy."""
    _preview(
        ui,
        files=3,
        photos=3,
        new_unique=0,
        exact_dup=3,
        exact_dup_matches={
            "total": 3,
            "shown": [],
            "already_in_library": 3,
            "within_this_batch": 0,
            "unclassified": 0,
        },
        matched_drives=_drives(("BackupA", 3, "connected", "/media/BackupA")),
    )
    assert ui.locator(POINTER).count() == 0, "the pointer fired on three files"


def test_a_batch_twin_does_not_count_toward_the_threshold(ui: Page) -> None:
    """It says nothing about the library - the twin is in this very batch."""
    _preview(
        ui,
        exact_dup_matches={
            "total": 440,
            "shown": [],
            "already_in_library": 0,
            "within_this_batch": 440,
            "unclassified": 0,
        },
        matched_drives=_drives(),
    )
    assert ui.locator(POINTER).count() == 0


# ------------------------------------------------------------------- subsume, do not stack


def test_the_move_line_is_absorbed_rather_than_repeated(ui: Page) -> None:
    """Both open on the same count. Two of them reads as the app repeating itself."""
    _preview(ui, mode="move")
    expect(ui.locator(POINTER)).to_be_visible()
    assert ui.locator(WILL_REMAIN).count() == 0, "the move line is still stacked beside the banner"


def test_the_absorbed_line_keeps_its_tail_in_move_mode(ui: Page) -> None:
    """The reassuring half is the half that must not be lost in the merge."""
    _preview(ui, mode="move")
    expect(ui.locator(POINTER)).to_contain_text("They stay where they are")


def test_a_copy_run_gets_no_move_tail(ui: Page) -> None:
    _preview(ui, mode="copy")
    text = _text(ui)
    assert "stay where they are" not in text, text


def test_below_the_threshold_the_move_line_is_exactly_as_it_shipped(ui: Page) -> None:
    """The subsumption must not cost the sentence Stage 2 built."""
    _preview(
        ui,
        mode="move",
        new_unique=200,
        exact_dup=260,
        exact_dup_matches={
            "total": 260,
            "shown": [],
            "already_in_library": 260,
            "within_this_batch": 0,
            "unclassified": 0,
        },
        matched_drives=_drives(("BackupA", 260, "connected", "/media/BackupA")),
    )
    assert ui.locator(POINTER).count() == 0
    expect(ui.locator(WILL_REMAIN)).to_contain_text("will not be moved")


# ------------------------------------------------------------------------ more than one drive


def test_two_drives_are_both_named_and_neither_is_picked(ui: Page) -> None:
    """Stage 1's two-destination case reaches the screen. Choosing one silently is the failure
    the previous commit exists to prevent; it must not be reintroduced by the wording."""
    _preview(
        ui,
        matched_drives=_drives(
            ("BackupA", 300, "connected", "/media/BackupA"),
            ("BackupB", 140, "connected", "/media/BackupB"),
        ),
    )
    banner = ui.locator(POINTER)
    expect(banner).to_contain_text("BackupA")
    expect(banner).to_contain_text("BackupB")


def test_two_drives_do_not_prefill_a_guess(ui: Page) -> None:
    _preview(
        ui,
        matched_drives=_drives(
            ("BackupA", 300, "connected", "/media/BackupA"),
            ("BackupB", 140, "connected", "/media/BackupB"),
        ),
    )
    ui.locator(f"{POINTER} [data-rearrange-go]").click()
    expect(ui.locator("#mig-path")).to_have_value("")


# ------------------------------------------------------------------------------- reach


def test_an_offline_library_is_named_and_says_it_is_not_plugged_in(ui: Page) -> None:
    """ "Not plugged in" must never read as "not there" - `DriveReach` is three-valued and the
    alarming fold is the worse one for a custody tool."""
    _preview(ui, matched_drives=_drives(("BackupA", 440, "offline", None)))
    banner = ui.locator(POINTER)
    expect(banner).to_contain_text("BackupA")
    expect(banner).to_contain_text("not plugged in")
    text = _text(ui)
    assert "missing" not in text.lower(), text
    assert "lost" not in text.lower(), text


def test_a_library_whose_location_is_unknown_says_that_and_not_that_it_is_offline(
    ui: Page,
) -> None:
    """Registered from the CLI and never seen here. It is not an error and not an absence."""
    _preview(ui, matched_drives=_drives(("BackupA", 440, "unknown", None)))
    expect(ui.locator(POINTER)).to_contain_text("location not known yet")


def test_matches_with_no_recorded_drive_still_get_the_answer_but_no_button(ui: Page) -> None:
    """The orphan state. We cannot point at a library we cannot name, and offering a button that
    lands nowhere is worse than the sentence alone."""
    _preview(ui, matched_drives={"total": 440, "unplaced": 440, "drives": []})
    banner = ui.locator(POINTER)
    expect(banner).to_be_visible()
    expect(banner).to_contain_text("will not change how they are arranged")
    assert ui.locator(f"{POINTER} [data-rearrange-go]").count() == 0


# ------------------------------------------------------------------------------- the jump


def test_the_button_lands_on_the_rearrange_card_with_the_drive_filled_in(ui: Page) -> None:
    """One connected library: the path is known, so the user should not retype it."""
    _preview(ui)
    ui.locator(f"{POINTER} [data-rearrange-go]").click()
    expect(ui.locator("#screen-settings")).to_be_visible()
    expect(ui.locator("#mig-path")).to_have_value("/media/BackupA")


def test_an_offline_library_jumps_without_pretending_to_know_where_it_is(ui: Page) -> None:
    _preview(ui, matched_drives=_drives(("BackupA", 440, "offline", None)))
    ui.locator(f"{POINTER} [data-rearrange-go]").click()
    expect(ui.locator("#screen-settings")).to_be_visible()
    expect(ui.locator("#mig-path")).to_have_value("")


# ------------------------------------------------------------------------------ the heading


def test_the_card_says_what_it_does_rather_than_what_it_matches(ui: Page) -> None:
    """ "Move existing files to match" - match what? Nobody looking for "rearrange my library
    into dated folders" would find that, which is most of why it was invisible."""
    heading = ui.eval_on_selector("#settings-migrate h2", "el => el.textContent")
    assert "Rearrange your library" in heading, heading
    assert "to match" not in heading, heading
