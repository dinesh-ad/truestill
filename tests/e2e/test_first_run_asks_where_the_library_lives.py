"""The first run asks where the library should live, and only the first run. `(abx)`.

The Organize screen offers three modes and **all three presume an organized folder that does not
exist yet**. Until now the answer was inferred from whatever the user typed into "Organized
folder" once, and the only guidance on that field was a placeholder naming a removable drive.

**§4's sixteenth member throughout.** Every absence assertion below waits on a positive signal
first: the card renders hidden and is revealed by a request, so "no card" is satisfied by the
blank page before anything has been answered.
"""

from __future__ import annotations

import json
from typing import Any

from playwright.sync_api import Page, expect

CARD = "[data-testid='org-first-run']"


def _status(ui: Page, **overrides: Any) -> None:
    base: dict[str, Any] = {
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
        "library_path": None,
        "library_root": None,
        "needs_library_root": True,
        "backup_path": None,
        "never_checked_drives": [],
        "catalog_path": "/tmp/c.sqlite",
        "catalog_presence": "will_create",
        "catalog_detail": "",
        "catalog_tone": "info",
    }
    base.update(overrides)
    ui.route(
        "**/api/library/status",
        lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps(base)),
    )
    ui.reload()
    ui.wait_for_selector(".nav-item")


def test_a_first_run_is_asked_the_question(ui: Page) -> None:
    _status(ui)
    expect(ui.locator(CARD)).to_be_visible(timeout=30_000)
    expect(ui.locator(CARD)).to_contain_text("Where should your library live?")


def test_the_question_names_the_trade_a_removable_drive_would_be(ui: Page) -> None:
    """The placeholder used to say `/media/BackupA`, so the screen's only hint about where a
    library goes pointed at the one place it should not. The card says so in words instead."""
    _status(ui)
    expect(ui.locator(CARD)).to_contain_text("removable drive is for backups", timeout=30_000)


def test_the_suggested_folder_is_a_place_that_exists_on_this_machine(ui: Page) -> None:
    """Suggested from the folder picker's own roots rather than a path spelled in JavaScript."""
    ui.route(
        "**/api/fs/dirs**",
        lambda r: r.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(
                {
                    "roots": [
                        {"label": "Home", "path": "/home/you"},
                        {"label": "Pictures", "path": "/home/you/Pictures"},
                    ],
                    "entries": [],
                    "path": "",
                }
            ),
        ),
    )
    _status(ui)
    expect(ui.locator("#org-library-root")).to_have_value(
        "/home/you/Pictures/Truestill", timeout=30_000
    )


def test_a_library_that_already_holds_files_is_never_asked(ui: Page) -> None:
    """**CRY-WOLF HALF.** A user who organized before this shipped answered the question by doing
    it. Non-vacuous: the destination field is waited for first, so the screen is known to have
    rendered before the absence is asserted."""
    _status(ui, files=2269, needs_library_root=False, library_path="/home/you/Pictures/Truestill")
    expect(ui.locator("#org-dest")).to_have_value("/home/you/Pictures/Truestill", timeout=30_000)
    expect(ui.locator(CARD)).to_have_count(1)
    expect(ui.locator(CARD)).to_be_hidden()


def test_the_destination_prefills_from_the_declaration_before_any_run(ui: Page) -> None:
    """THE POINT OF THE WHOLE ENTRY. `library_path` is only written *after* a successful run, so
    on the run that follows the answer there is nothing observed yet - the declaration is what
    fills the field, and nothing else would notice if this silently stopped."""
    _status(
        ui, needs_library_root=False, library_path=None, library_root="/home/you/Pictures/Truestill"
    )
    expect(ui.locator("#org-dest")).to_have_value("/home/you/Pictures/Truestill", timeout=30_000)


def test_an_unreachable_declared_library_is_still_not_re_asked(ui: Page) -> None:
    """The drive is unplugged: `library_path` is cleared by design, the declaration is not. If the
    card returned here, first run would re-arm every time the library drive was out."""
    _status(
        ui, needs_library_root=False, library_path=None, library_root="/media/Elements/Truestill"
    )
    expect(ui.locator("#org-dest")).to_have_value("/media/Elements/Truestill", timeout=30_000)
    expect(ui.locator(CARD)).to_be_hidden()


def test_settings_shows_the_declared_folder_so_it_can_be_changed(ui: Page) -> None:
    """One-time is not irreversible."""
    _status(ui, needs_library_root=False, library_root="/home/you/Pictures/Truestill")
    ui.click('button[data-screen="settings"]')
    expect(ui.locator("#library-root-current")).to_have_text(
        "/home/you/Pictures/Truestill", timeout=30_000
    )
    expect(ui.locator("#set-library-root")).to_have_value("/home/you/Pictures/Truestill")


def test_settings_says_plainly_when_nothing_has_been_chosen(ui: Page) -> None:
    """A blank would read as a rendering failure rather than as an unanswered question."""
    _status(ui)
    ui.click('button[data-screen="settings"]')
    expect(ui.locator("#library-root-current")).to_have_text("not chosen yet", timeout=30_000)
