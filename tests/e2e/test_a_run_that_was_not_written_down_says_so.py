"""`(afu)`: when the run record cannot be written, the app SAYS SO.

The record is automatic, so nobody asked for it and nobody would notice it missing - which is
exactly what makes its **absence** the news rather than the file. The CLI prints the same fact;
this is the app saying it in the same breath.

⚠ **Why a browser test and not a payload assertion.** The service test already proves
`record_error` reaches the payload. A value computed correctly and rendered nowhere is `(aer)`'s
shape and §4's fourteenth member, and it is precisely what happened here: the key was added, no
renderer read it, and the payload test was green throughout. Only a test that reads what a user
reads can tell those apart.
"""

from __future__ import annotations

from typing import Any

from playwright.sync_api import Page, expect

SOURCE = "/tmp/src"


def _completion(ui: Page, **overrides: Any) -> None:
    """Render a finished organize by handing the island the payload the server builds."""
    summary: dict = {
        "organized": 5,
        "photos": 5,
        "videos": 0,
        "audio": 0,
        "bytes_organized": 5000,
        "duplicates": 0,
        "bytes_saved": 0,
        "failed": 0,
        "folders": {},
        "outcomes": {"organized": 5},
        "mode": "copy",
    }
    summary.update(overrides)
    ui.evaluate(
        "(s) => { window.organizeResult.set({ kind: 'complete', summary: s }); }",
        summary,
    )


def test_a_record_that_could_not_be_written_is_named_with_its_reason(ui: Page) -> None:
    """The user is told, in the same place every other outcome is told."""
    _completion(ui, record_error="No space left on device")

    result = ui.locator("#org-result")
    expect(result).to_contain_text("not written down")
    expect(result).to_contain_text("No space left on device")


def test_the_run_still_reads_as_finished(ui: Page) -> None:
    """⚠ The paperwork failing must not read as the run failing.

    `(afu)`'s whole premise is that the copy succeeded and only its record did not, so a banner
    that made this look like a failed organize would be a worse lie than saying nothing.
    """
    _completion(ui, record_error="No space left on device")

    result = ui.locator("#org-result")
    expect(result).to_contain_text("5 files")
    expect(result).not_to_contain_text("could not be copied")


def test_a_run_that_was_written_down_says_nothing_about_it(ui: Page) -> None:
    """CRY-WOLF HALF. The key is absent on success, so the banner must never appear.

    Without this the renderer could print on every run and the test above would still pass -
    which is the guard that gets switched off, taking its real coverage with it.
    """
    _completion(ui)

    result = ui.locator("#org-result")
    expect(result).to_contain_text("5 files")
    expect(result).not_to_contain_text("not written down")
