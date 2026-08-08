"""The Trips screen offers a folder-derived name without ever filling the box for you.

**Not prefilled into ``value``.** On this screen an empty box means "skip this card", so writing
a suggestion into it would make doing nothing silently accept a guess. The suggestion renders
BELOW the input in the `.carried` vocabulary already used for carried-over values, with a **Use**
button; clicking it fills the box, and typing anything dismisses it. Same idiom, and the one
difference - no prefill - is because empty means something different here than it does on Backups.

**Waits.** Every assertion below waits on something only the suggested state can PRODUCE: the
suggestion line itself, or the input's value after Use. Never on `to_have_count(0)` of a container
the render empties first, and never on text a previous render could have left behind
(`ENGINEERING_STANDARD.md` §4, sixteenth member - a test that waited on a cleared element and on
stale text passed against a live defect two days ago).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest
from e2e_support import AppServer
from playwright.sync_api import Page, expect
from truestill_core.catalog import Catalog
from truestill_core.drive import create_marker

_START = datetime(2026, 3, 4, 10, 0)  # noqa: DTZ001 - naive, as capture times are


def _drive_named(db: Path, root: Path, folder: str, *, days: int = 1, per_day: int = 20) -> str:
    root.mkdir(parents=True, exist_ok=True)
    marker = create_marker(root, label="Backup A")
    with Catalog(db) as catalog:
        catalog.upsert_drive(uuid=marker.uuid, label=marker.label)
        for day in range(days):
            for index in range(per_day):
                sha = f"sha{day:02d}{index:03d}"
                catalog.record_uploaded(
                    source_path=f"/src/{folder}/{sha}.jpg",
                    original_name=f"{sha}.jpg",
                    sha256=sha,
                    copy_sha256=sha,
                    perceptual=None,
                    size=1000,
                    captured_at=(_START + timedelta(days=day, minutes=index)).isoformat(),
                    category="Camera",
                    relative=f"2026/2026-03/{sha}.jpg",
                    drive_uuid=marker.uuid,
                )
    return marker.uuid


def _propose(ui: Page, root: Path) -> None:
    ui.click('button[data-screen="events"]')
    ui.fill("#ev-source", str(root))
    ui.click("#ev-propose")


@pytest.fixture
def drive(app_server: AppServer, tmp_path: Path):
    def make(folder: str, **kw):
        root = tmp_path / "drive"
        _drive_named(app_server.db, root, folder, **kw)
        return root

    return make


def test_the_suggestion_is_offered_below_the_box_and_never_inside_it(ui: Page, drive) -> None:
    """THE SHAPE. The name is visible, the box is empty, and doing nothing still skips the card."""
    root = drive("Sea Diving")
    _propose(ui, root)

    # Waits on the suggestion line, which only the suggested state can produce.
    line = ui.locator(".ev-suggest")
    expect(line).to_be_visible(timeout=30_000)
    expect(line).to_contain_text("Sea Diving")
    expect(ui.locator(".ev-name")).to_have_value("")


def test_use_fills_the_box_and_the_offer_stands_down(ui: Page, drive) -> None:
    """Accepting is one click, and once accepted it is the user's answer, not a suggestion."""
    root = drive("Sea Diving")
    _propose(ui, root)
    expect(ui.locator(".ev-suggest")).to_be_visible(timeout=30_000)

    ui.click(".ev-suggest-use")

    # Waits on the VALUE, which only Use can produce - not on the line's absence.
    expect(ui.locator(".ev-name")).to_have_value("Sea Diving")
    expect(ui.locator(".ev-suggest")).to_be_hidden()


def test_typing_your_own_name_dismisses_the_offer(ui: Page, drive) -> None:
    """`.carried`'s own rule: once the user has written something it is theirs, so stop calling
    it a suggestion."""
    root = drive("Sea Diving")
    _propose(ui, root)
    expect(ui.locator(".ev-suggest")).to_be_visible(timeout=30_000)

    ui.fill(".ev-name", "My Own Name")

    expect(ui.locator(".ev-name")).to_have_value("My Own Name")
    expect(ui.locator(".ev-suggest")).to_be_hidden()


def test_a_folder_that_says_nothing_offers_nothing_and_the_card_is_unchanged(
    ui: Page, drive
) -> None:
    """The cry-wolf half. With no suggestion the screen must behave exactly as it did before:
    an empty box, and no line under it."""
    root = drive("DCIM")
    _propose(ui, root)

    # Waits on the CARD, which the proposal produces either way, before asserting the absence.
    expect(ui.locator(".ev-name")).to_be_visible(timeout=30_000)
    expect(ui.locator(".ev-name")).to_have_value("")
    expect(ui.locator(".ev-suggest")).to_have_count(0)
