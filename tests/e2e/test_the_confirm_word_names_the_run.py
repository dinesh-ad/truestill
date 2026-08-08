"""The typed word must name the operation, and the gate must guard what it displays.

**Defect 1.** The word was hardcoded `move` for every mode, so copy mode asked a person to type
`move` to perform a copy - naming an operation the run will not do, at the moment of decision
(§9). The CLI's vocabulary is the reference: `_confirm_in_place` requires `move`, and requires it
only for in-place. Copy therefore gets `copy`; move and in-place both genuinely move, and both
keep the CLI's word.

**Defect 2.** The gate tested `summary.files` - files FOUND - while the button rendered `kept` -
files that would be ORGANIZED. A folder whose every file is already a duplicate has a truthy
`files` and a zero `kept`, so the full typed-word ceremony rendered and ended in a button reading
`Organize 0 files`. Guarding nothing, and asking for a word first.
"""

from __future__ import annotations

from pathlib import Path

from playwright.sync_api import Page, expect


def _preview_and_check(ui: Page, source: Path, dest: Path) -> None:
    ui.fill("#org-source", str(source))
    ui.fill("#org-dest", str(dest))
    ui.click("#org-preview")
    expect(ui.locator("#org-result")).to_contain_text("photos found", timeout=30_000)
    ui.click("#org-dedup")


def _choose_mode(ui: Page, mode: str) -> None:
    ui.check(f'input[name="org-mode"][value="{mode}"]')


def test_copy_mode_asks_for_the_word_copy(ui: Page, tmp_path: Path, library) -> None:
    """It copies, so it asks for `copy`. Typing `move` must NOT unlock it - that is the whole
    defect: the old gate accepted the word for an operation it was not going to perform."""
    source = library(3, name="Lib")
    _choose_mode(ui, "copy")
    _preview_and_check(ui, source, tmp_path / "Out")

    box = ui.locator("#org-confirm [data-typed-confirm]")
    expect(box).to_be_visible(timeout=60_000)
    expect(ui.locator("#org-confirm")).to_contain_text("copy")

    go = ui.locator("#org-confirm [data-typed-go]")
    ui.fill("#org-confirm [data-typed-confirm]", "move")
    expect(go).to_be_disabled()
    ui.fill("#org-confirm [data-typed-confirm]", "copy")
    expect(go).to_be_enabled()


def test_in_place_keeps_the_word_the_command_line_already_uses(ui: Page, library) -> None:
    """`_confirm_in_place` requires `move`; two vocabularies for one operation would be worse
    than the wrong one."""
    source = library(3, name="Lib")
    _choose_mode(ui, "inplace")
    ui.fill("#org-source", str(source))
    ui.click("#org-preview")
    expect(ui.locator("#org-result")).to_contain_text("photos found", timeout=30_000)
    ui.click("#org-dedup")

    expect(ui.locator("#org-confirm [data-typed-confirm]")).to_be_visible(timeout=60_000)
    go = ui.locator("#org-confirm [data-typed-go]")
    ui.fill("#org-confirm [data-typed-confirm]", "copy")
    expect(go).to_be_disabled()
    ui.fill("#org-confirm [data-typed-confirm]", "move")
    expect(go).to_be_enabled()


def test_copy_says_originals_are_untouched_rather_than_warning_about_undo(
    ui: Page, tmp_path: Path, library
) -> None:
    """Defect 1b. "not reversible with undo-organize" is TRUE of copy and belongs nowhere near a
    warning: copy is the one mode that changes nothing, and the worst case is files the user can
    delete. The fact is kept and reframed as the reason undo does not apply."""
    source = library(3, name="Lib")
    _choose_mode(ui, "copy")
    _preview_and_check(ui, source, tmp_path / "Out")

    banner = ui.locator("#org-confirm")
    expect(banner).to_be_visible(timeout=60_000)
    expect(banner).to_contain_text("originals")
    expect(banner).not_to_contain_text("not reversible")


def test_a_run_with_nothing_to_organize_says_so_instead_of_asking_for_a_word(
    ui: Page, tmp_path: Path, library
) -> None:
    """THE EXACT SHAPE THAT PRODUCED IT: every file in the folder is already an exact duplicate.

    `summary.files` is truthy - the files are all there - while `kept` is zero, which is what let
    the ceremony render and end in "Organize 0 files". Organizing the same folder twice is the
    cheapest way to reach it and is what a person does by accident.
    """
    source = library(3, name="Lib")
    dest = tmp_path / "Out"
    _choose_mode(ui, "copy")
    _preview_and_check(ui, source, dest)
    ui.fill("#org-confirm [data-typed-confirm]", "copy")
    ui.click("#org-confirm [data-typed-go]")
    expect(ui.locator("#org-result")).to_contain_text("organized", timeout=60_000)

    _preview_and_check(ui, source, dest)  # again: everything is now a duplicate

    # Asserted on the sentence only the FIXED path can produce. `#org-confirm` is emptied at the
    # START of the dedup click and `#org-result` still holds the first run's text, so waiting on
    # either of those can pass before the second run has finished - which is exactly how the
    # first version of this test passed against the defect it exists to catch.
    expect(ui.locator("#org-why")).to_contain_text("already organized", timeout=60_000)
    expect(ui.locator("#org-confirm [data-typed-confirm]")).to_have_count(0)
