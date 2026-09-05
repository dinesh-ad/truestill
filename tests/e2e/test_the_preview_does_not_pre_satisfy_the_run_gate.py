"""A wait for a run to finish must not already be true before the run starts.

Run 33947262070 (2026-09-05, webkit): `test_the_confirm_word_names_the_run.py` waited for
"organized" in `#org-result` after clicking the run, and the preview card the duplicate check
renders into that same region already said "3 files will be organized." The wait passed before
`/api/organize/run` was posted, the second duplicate check was refused with `DriveBusy` while the
first run held the drive, and `#org-why` kept its resting text for the whole budget.
`test_busy_state.py` had the same gate, and `test_ui_regressions.py` waited on "3 photos · 1 video"
in `#bk-result`, which the backup preview writes there before the run.

The ruling: a gate reads a state marker the completion renderer sets and the preview does not;
prose stays for assertions. The marker is `.done-mark`, emitted only by `completionCard` in
`app.js`, whose only callers are `organizeCompletion` and `backupCompletion`. Two tests here show
the marker is absent once the preview has rendered and present once the run has finished; the
third pins the three gates to it, so a gate reverted to prose goes red without a browser.
"""

from __future__ import annotations

from pathlib import Path

from e2e_support import open_backups
from playwright.sync_api import Page, expect

_GATES = (
    ("test_the_confirm_word_names_the_run.py", "#org-result .done-mark"),
    ("test_busy_state.py", "#org-result .done-mark"),
    ("test_ui_regressions.py", "#bk-result .done-mark"),
)


def test_the_organize_gate_is_not_already_satisfied_by_the_preview(
    ui: Page, tmp_path: Path, library
) -> None:
    source = library(3, name="Lib")
    ui.check('input[name="org-mode"][value="copy"]')
    ui.fill("#org-source", str(source))
    ui.fill("#org-dest", str(tmp_path / "Out"))
    ui.click("#org-preview")
    expect(ui.locator("#org-result")).to_contain_text("photos found", timeout=30_000)
    ui.click("#org-dedup")
    expect(ui.locator("#org-confirm [data-typed-confirm]")).to_be_visible(timeout=60_000)

    # The preview has rendered and nothing has clicked the run: no marker yet.
    expect(ui.locator("#org-result .done-mark")).to_have_count(0)

    ui.fill("#org-confirm [data-typed-confirm]", "copy")
    ui.click("#org-confirm [data-typed-go]")
    expect(ui.locator("#org-result .done-mark")).to_be_visible(timeout=60_000)


def test_the_backup_gate_is_not_already_satisfied_by_the_preview(
    ui: Page, tmp_path: Path, library
) -> None:
    source = library(3, name="Lib")
    dest = tmp_path / "Out"
    backup = tmp_path / "Backup"
    backup.mkdir()
    ui.check('input[name="org-mode"][value="copy"]')
    ui.fill("#org-source", str(source))
    ui.fill("#org-dest", str(dest))
    ui.click("#org-preview")
    expect(ui.locator("#org-result")).to_contain_text("photos found", timeout=30_000)
    ui.click("#org-dedup")
    expect(ui.locator("#org-confirm [data-typed-confirm]")).to_be_visible(timeout=60_000)
    ui.fill("#org-confirm [data-typed-confirm]", "copy")
    ui.click("#org-confirm [data-typed-go]")
    expect(ui.locator("#org-result .done-mark")).to_be_visible(timeout=60_000)

    open_backups(ui)
    expect(ui.locator("#bk-source")).to_have_value(str(dest))
    ui.fill("#bk-target", str(backup))
    ui.click("#bk-preview")
    expect(ui.locator("#bk-run")).to_be_visible()

    # The preview has rendered into the region and nothing has clicked the run: no marker yet.
    expect(ui.locator("#bk-result")).to_contain_text("to copy")
    expect(ui.locator("#bk-result .done-mark")).to_have_count(0)

    ui.click("#bk-run")
    expect(ui.locator("#bk-result .done-mark")).to_be_visible(timeout=60_000)


def test_the_three_run_gates_read_the_marker() -> None:
    here = Path(__file__).parent
    for name, marker in _GATES:
        text = (here / name).read_text(encoding="utf-8")
        assert f'expect(ui.locator("{marker}"))' in text, (
            f"{name}: the run gate no longer waits on {marker}"
        )
