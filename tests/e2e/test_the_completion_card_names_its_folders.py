"""A finished run says which folders it filled, and the chips agree with the count beside them.

**The regression this exists for, and it shipped silently.** `organizeCompletion` built the chip
markup by calling `window.truestillMarkup.chips(...)`, which renders a React component into a
detached node through `flushSync`. From 2026-09-05, when the island took over `#org-result`, that
call happened *during the island's own render* - and React does not flush there. The string came
back empty every time, `completionCard`'s `${chips ? ... : ""}` gate saw an empty string, and the
whole "Into these folders" block vanished from every completion card.

⚠ **Nothing failed.** The stats line went on printing "N folders" from `r.folders`, so the card
claimed folders existed and then showed none of them, and no test in this suite looked at the
chips. It was found by diffing the rendered card before and after the renderer moved to
`completion.tsx`, not by a red run.

The second test is the half that would have caught it earliest: the two numbers come from the same
payload field, so a card that can print one and not the other is contradicting itself on screen.
"""

from __future__ import annotations

import re
from typing import Any

from playwright.sync_api import Page, expect

CHIPS = "#org-result .chips .chip"

#: Three destination folders, so a count is not confusable with a boolean.
FOLDERS: dict[str, int] = {"2020": 4, "2021": 2, "Undated": 1}


def _finished_run(ui: Page, **overrides: Any) -> None:
    """Render a finished organize through the island's own props entry point.

    The same seam `test_the_grid_is_the_result.py` uses: a real run sits behind a typed-word
    confirm, and driving that would test the gate rather than the card.
    """
    summary: dict[str, Any] = {
        "organized": 7,
        "photos": 7,
        "videos": 0,
        "audio": 0,
        "bytes_organized": 5000,
        "duplicates": 0,
        "bytes_saved": 0,
        "moved_by_copy": 7,
        "moved_in_place": 0,
        "failed": 0,
        "folders": FOLDERS,
        "outcomes": {"organized": 7},
        "mode": "copy",
        "organized_sample": {"total": 0, "shown": []},
    }
    summary.update(overrides)
    ui.evaluate("(s) => { window.organizeResult.set({ kind: 'complete', summary: s }); }", summary)
    expect(ui.locator("#org-result .card")).to_be_visible()


def test_a_finished_run_draws_a_chip_for_every_destination_folder(ui: Page) -> None:
    """The card names where the photographs went, one chip per folder."""
    _finished_run(ui)

    expect(ui.locator("#org-result")).to_contain_text("Into these folders")
    expect(ui.locator(CHIPS)).to_have_count(len(FOLDERS))
    for name, count in FOLDERS.items():
        chip = ui.locator(CHIPS).filter(has_text=name)
        expect(chip).to_have_count(1)
        expect(chip).to_contain_text(str(count))


def test_the_folder_count_in_the_line_agrees_with_the_chips_drawn(ui: Page) -> None:
    """Both numbers are `r.folders`, so a card that prints one and not the other lies on screen.

    This is the assertion the silent regression would have failed from its first day: the stats
    line kept saying "3 folders" while the chips block was absent entirely.
    """
    _finished_run(ui)

    line = ui.locator("#org-result .result-numbers").inner_text()
    stated = re.search(r"(\d+) folders", line)
    assert stated is not None, f"the stats line does not state a folder count at all: {line!r}"

    drawn = ui.locator(CHIPS).count()
    assert int(stated.group(1)) == drawn, (
        f"the line claims {stated.group(1)} folders and the card draws {drawn} chips"
    )


def test_a_run_that_filled_no_folders_says_nothing_rather_than_an_empty_heading(
    ui: Page,
) -> None:
    """The cry-wolf half. An empty `folders` must draw no heading and no chips, so the two tests
    above are asserting a block that can genuinely be absent."""
    _finished_run(ui, folders={})

    expect(ui.locator("#org-result")).not_to_contain_text("Into these folders")
    expect(ui.locator(CHIPS)).to_have_count(0)
