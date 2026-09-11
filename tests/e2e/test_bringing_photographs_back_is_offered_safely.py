"""The recover card, in a browser: the reassurance, and when the button is offered. Stage 3.

⚠ **THE REASSURANCE IS ON SCREEN BEFORE ANY REQUEST, and that is what these tests defend.** The
user arriving at this button has met restores that destroy things - UrBackup ships restore
disabled by default, and
Backblaze tells people to make another backup first. Truestill's never overwrites and
never deletes, and the remedy for that inherited fear is a sentence read *before* deciding to be
brave. It is substituted into the markup server-side for exactly that reason, so a test that
waited for a preview would be testing the wrong moment.

**The button obeys `loadDrives`' own rule**, quoted from the source it sits next to: rendered only
when we know where the drive is, because *"offering an action we cannot honour would be worse than
stating the fact plainly."*
"""

from __future__ import annotations

import json
from typing import Any

from e2e_support import open_backups
from playwright.sync_api import Page, expect


def _drive(label: str, uuid: str, path: str | None, **over: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "label": label,
        "uuid": uuid,
        "files": 2,
        "photos": 2,
        "videos": 0,
        "audio": 0,
        "size": 100,
        "last_seen": None,
        "last_verified": None,
        "path": path,
        "reach": "connected" if path else "unknown",
        "decisions": None,
    }
    row.update(over)
    return row


def _show(ui: Page, drives: list[dict[str, Any]]) -> None:
    ui.route(
        "**/api/drives**",
        lambda r: r.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(
                {
                    "library": {
                        "files": 2,
                        "photos": 2,
                        "videos": 0,
                        "audio": 0,
                        "bytes": 100,
                        "by_format": {},
                    },
                    "at_risk": [],
                    "drives": drives,
                }
            ),
        ),
    )
    open_backups(ui)


# ------------------------------------------------------------------------- the reassurance


def test_the_screen_says_nothing_is_deleted_before_anything_is_pressed(ui: Page) -> None:
    """⚠ **The sentence that answers the fear, and WHEN it is readable.**

    Asserted without any interaction at all: no field filled, no preview run. A reassurance that
    appeared only after a preview would be one the user reads after deciding to be brave.
    """
    _show(ui, [_drive("Morrowkeep", "u1", "/mnt/backup")])

    banner = ui.locator("#recover-safety")
    expect(banner).to_contain_text("deleted or replaced", timeout=30_000)
    expect(banner).to_contain_text("only added")
    expect(banner).to_contain_text("left exactly as it is")
    expect(banner).to_contain_text("only read from")


def test_the_reassurance_is_not_styled_as_an_aside(ui: Page) -> None:
    """⚠ **Found by looking at it.** The first version used `class="banner ok"`, and `app.css`'s
    `.banner:not(.warn)` deliberately demotes every non-warning banner to muted small text - right
    for a first-run diagnostic, wrong for the one sentence on the screen that has to be believed.

    Asserted on the CLASS rather than on computed colour: the class is what selects the treatment,
    and a colour assertion would re-encode the palette here and break on a token change.
    """
    _show(ui, [_drive("Morrowkeep", "u1", "/mnt/backup")])

    expect(ui.locator("#recover-safety")).to_have_class("banner safe", timeout=30_000)


# ------------------------------------------------------------------------------- the button


def test_a_connected_drive_is_offered_the_action(ui: Page) -> None:
    """The positive half. Without it, a button that never rendered would pass the test below."""
    _show(ui, [_drive("Morrowkeep", "u1", "/mnt/backup")])

    expect(ui.locator("#drives-list")).to_contain_text("Morrowkeep", timeout=30_000)
    expect(ui.locator(".drive-recover")).to_have_count(1)


def test_a_drive_whose_location_is_unknown_is_not_offered_it(ui: Page) -> None:
    """⚠ **`loadDrives`' rule, obeyed rather than restated**: *"offering an action we cannot
    honour would be worse than stating the fact plainly."* Without a path there is nothing to
    recover from, so neither this button nor `Check now` renders."""
    _show(ui, [_drive("Morrowkeep", "u1", None)])

    expect(ui.locator("#drives-list")).to_contain_text("Morrowkeep", timeout=30_000)
    expect(ui.locator(".drive-recover")).to_have_count(0)
    expect(ui.locator(".drive-check")).to_have_count(0)


def test_the_button_fills_the_form_rather_than_starting_a_run(ui: Page) -> None:
    """⚠ **It opens the question, never the copy**, and that is the difference from `Check now`.

    A verify only reads, so its button runs immediately. This one leads to writing into a library,
    so the button's whole job is to fill the field and let the typed word start anything.
    """
    _show(ui, [_drive("Morrowkeep", "u1", "/mnt/backup")])
    expect(ui.locator("#drives-list")).to_contain_text("Morrowkeep", timeout=30_000)

    ui.locator(".drive-recover").first.click()

    expect(ui.locator("#rcv-drive")).to_have_value("/mnt/backup")
    # Nothing was started: no confirmation appeared, and the result region is untouched.
    expect(ui.locator("#rcv-confirm")).to_be_empty()


def test_clicking_it_on_the_library_itself_says_so_instead_of_starting_a_job(ui: Page) -> None:
    """⚠ **The rule obeyed at the moment it becomes obeyable.**

    `library_path` is written by the app's own organize flow, so on a catalog built by the CLI it
    is absent and the button renders on every connected drive - including the library's own card.
    Once the user has typed where their library is, the un-honourable click is answerable, and it
    is answered here rather than by starting a job that can only refuse.
    """
    _show(ui, [_drive("Morrowkeep", "u1", "/mnt/library")])
    expect(ui.locator("#drives-list")).to_contain_text("Morrowkeep", timeout=30_000)
    ui.locator("#rcv-library").fill("/mnt/library")

    ui.locator(".drive-recover").first.click()

    expect(ui.locator("#rcv-result")).to_contain_text("That is your library")
    expect(ui.locator("#rcv-drive")).to_have_value("")
