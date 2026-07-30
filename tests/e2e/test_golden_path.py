"""The journey a new user actually walks, start to finish, in one test.

Organize a folder of photos, then follow the Backups screen's own guidance to copy that
library to a second drive, then check the copy is sound -- with no CLI at any point and no
prior knowledge of drives, markers or catalogs.

This is one long test on purpose. The value is in the *handoffs*: state carried from organize
to Backups, a library the app itself registered being accepted by the copy flow, and a drive
card that can check itself. Split into six tests, each handoff would be set up rather than
travelled, and the bug that broke this path -- organize never registering its own destination,
so the app rejected the library it had just built -- would have passed all six.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.skipif(shutil.which("exiftool") is None, reason="exiftool not installed")


def test_organize_then_back_up_then_check(ui: Page, tmp_path: Path, library) -> None:
    source = library(8, name="Pictures")
    destination = tmp_path / "TruestillLibrary" / "Output"
    backup = tmp_path / "TruestillBackup"
    backup.mkdir()

    # --- 1. Organize -----------------------------------------------------------------
    expect(ui.locator("#custody-line")).to_contain_text("not backed up yet")
    ui.fill("#org-source", str(source))
    ui.fill("#org-dest", str(destination))
    ui.click("#org-preview")
    expect(ui.locator("#org-result")).to_contain_text("8 photos found")
    expect(ui.locator("#org-result")).to_contain_text("no dates or duplicates checked yet")
    expect(ui.locator("#org-run")).to_have_count(0)
    expect(ui.locator("#org-confirm [data-typed-go]")).to_have_count(0)

    ui.click("#org-dedup")
    expect(ui.locator("#org-confirm [data-typed-confirm]")).to_be_visible()
    ui.fill("#org-confirm [data-typed-confirm]", "move")
    ui.click("#org-confirm [data-typed-go]")
    expect(ui.locator("#org-result")).to_contain_text("8 files organized")
    expect(ui.locator("#org-result")).not_to_contain_text("uploaded")
    assert len(list(destination.rglob("*.jpg"))) == 8  # the screen matches the disk

    # Organizing registered its own destination, so the library lives somewhere the app knows.
    expect(ui.locator("#custody-line")).to_contain_text("safe in 1 place")

    # --- 2. Backups: the library is already known ------------------------------------
    ui.click('button[data-screen="backups"]')
    expect(ui.locator("#drives-list")).to_contain_text("Output")
    expect(ui.locator("#bk-source")).to_have_value(str(destination))  # never asked to Browse

    # --- 3. Copy to a second drive ----------------------------------------------------
    ui.fill("#bk-target", str(backup))
    ui.click("#bk-preview")
    expect(ui.locator("#bk-result")).to_contain_text("8 photos")
    ui.click("#bk-run")

    expect(ui.locator("#bk-result")).to_contain_text("8 photos copied to TruestillBackup")
    expect(ui.locator("#bk-result")).to_contain_text("Every copy verified")
    assert len(list(backup.rglob("*.jpg"))) == 8

    # --- 4. The promise, kept ---------------------------------------------------------
    expect(ui.locator("#custody-line")).to_contain_text("safe in 2 places")
    expect(ui.locator("#drives-list")).to_contain_text("TruestillBackup")

    # --- 5. Check the new backup, from its own card -----------------------------------
    card = ui.locator("#drives-list .card", has_text="TruestillBackup")
    expect(card).to_contain_text("last checked: never")
    card.locator(".drive-check").click()

    expect(ui.locator("#verify-result")).to_contain_text("Checked TruestillBackup")
    expect(ui.locator("#verify-result")).to_contain_text("8")
    expect(ui.locator("#verify-result")).not_to_contain_text("NaN")
    # The fact now carries its date rather than inviting the same action again.
    expect(ui.locator("#drives-list .card", has_text="TruestillBackup")).not_to_contain_text(
        "last checked: never"
    )
