"""Find and Stats must say when a drive is not connected. Clicked, in a real browser.

⚠ **MEASURED ON A REAL EJECTED DRIVE, 2026-09-12.** Find returned a location on an unplugged
drive rendered identically to a reachable one - under its own lede promising it *"works even when
the drives are unplugged"* - and **zero of twelve** absence phrasings appeared anywhere on Stats,
whose per-drive table showed the absent drive with the MORE recent verification date.

The drive is taken away by removing the folder its marker lives in, which is the same code path
`drive.drive_reach` takes for a pulled USB stick. §2: these are rendered surfaces, so a payload
assertion is not coverage of what a person sees.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from e2e_support import open_backups
from playwright.sync_api import Page, expect


def _organize_onto(ui: Page, source: Path, destination: Path, count: int) -> None:
    """Copy ``count`` photographs onto ``destination``, which registers it as a drive.

    ⚠ **THE COMPLETION IS ASSERTED BY ITS COUNT, NOT BY THE WORD "organized".** The first draft
    waited for `to_contain_text("organized")`, which the PREVIEW card already satisfies - so the
    test tore the drive down before a byte had been copied and failed on a directory that was
    never created. That is `test_the_preview_does_not_pre_satisfy_the_run_gate`'s defect, in the
    test that was meant to prove a different one.
    """
    ui.click('button[data-screen="organize"]')
    ui.fill("#org-source", str(source))
    ui.fill("#org-dest", str(destination))
    ui.click("#org-preview")
    expect(ui.locator("#org-result")).to_contain_text("photos found", timeout=60_000)
    ui.click("#org-dedup")
    expect(ui.locator("#org-confirm [data-typed-confirm]")).to_be_visible(timeout=60_000)
    ui.fill("#org-confirm [data-typed-confirm]", "copy")
    ui.click("#org-confirm [data-typed-go]")
    expect(ui.locator("#org-result")).to_contain_text(f"{count} files organized", timeout=120_000)
    assert destination.is_dir(), "organize reported done and wrote no destination"


def test_find_and_stats_both_say_a_drive_is_not_plugged_in(
    ui: Page, tmp_path: Path, library
) -> None:
    """Two screens, one fact. Asserted before AND after, because a marker that is always shown
    would satisfy the 'after' half on its own."""
    external = tmp_path / "AD_2TB"
    _organize_onto(ui, library(3, name="Away"), external, 3)

    # --- connected: no marker anywhere -------------------------------------------------
    ui.click('button[data-screen="find"]')
    ui.fill("#where-term", "IMG_0000")
    ui.click("#where-go")
    expect(ui.locator("#where-result")).to_contain_text("IMG_0000", timeout=60_000)
    assert ui.locator("#where-result tr[data-reach='connected']").count() >= 1
    assert ui.locator("#where-result tr[data-reach='offline']").count() == 0

    # --- take the drive away -----------------------------------------------------------
    shutil.rmtree(external)

    ui.click('button[data-screen="find"]')
    ui.fill("#where-term", "IMG_0000")
    ui.click("#where-go")
    expect(ui.locator("#where-result")).to_contain_text("not plugged in", timeout=60_000)
    assert ui.locator("#where-result tr[data-reach='offline']").count() >= 1

    ui.click('button[data-screen="stats"]')
    expect(ui.locator("#screen-stats")).to_contain_text("not plugged in", timeout=60_000)
    assert ui.locator("#screen-stats tr[data-reach='offline']").count() >= 1


def test_the_at_risk_remedy_does_not_offer_a_copy_it_cannot_make(
    ui: Page, tmp_path: Path, library
) -> None:
    """⚠ **`(akp)`.** A file whose only copy is on a drive that is not here was told to *"copy your
    library to another drive"* - advice that backs up a set the file is not in. With nothing
    reachable to copy FROM, there must be no copy button at all."""
    external = tmp_path / "AD_2TB"
    _organize_onto(ui, library(3, name="Away"), external, 3)
    shutil.rmtree(external)

    open_backups(ui)
    banner = ui.locator("[data-testid='backups-at-risk']")
    expect(banner).to_be_visible(timeout=60_000)
    expect(banner).to_contain_text("not connected")
    expect(banner).to_contain_text("Connect")
    # The library case keeps its button; this case has nothing to copy from.
    assert banner.locator("[data-risk-action='copy']").count() == 0
    # ⚠ And the verb agrees now - it read "1 file exist in only one place".
    expect(banner).not_to_contain_text("file exist in")
