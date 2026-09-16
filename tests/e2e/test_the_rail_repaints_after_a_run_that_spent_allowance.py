"""The rail's allowance is repainted when a run ends, in a page that was never reloaded. `(akx)`

⚠ **WHY NO EXISTING TEST COULD SEE THIS, stated as the reason this file exists.** Every browser
test in this project opens the app and then asserts - so each one reads the rail exactly once, at
boot, when it is correct by construction. `loadAccount` had one call site, in that same boot list.
A rail that never repainted at all passed the whole lane, because the lane never asked it to.

**What this file does differently is one word: afterwards.** The page is opened ONCE, the
allowance read, a real organize driven through the real UI, and the allowance read AGAIN from the
same document. `_reload` from `test_the_account_slot_draws_every_licence_state.py` is deliberately
not imported: reloading is what hides the defect.

The sign-out test in that file is the precedent, and its own comment says why - *"a version that
signed out correctly and left the rail describing a signed-in user would pass every other test in
this file."* This is the same assertion about the other thing that moves the number.

**The expected text comes from core, never retyped.** `licence_notice` owns the wording, so the
assertion is built by asking core what an account with `used` files written says - which means a
reworded allowance line moves this test with it instead of breaking it.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from e2e_support import make_photo, stamp_capture_date
from playwright.sync_api import Page, expect
from truestill_core import allowance, licence, licence_notice

pytestmark = pytest.mark.skipif(shutil.which("exiftool") is None, reason="exiftool not installed")

#: How many photos the run organizes. Small enough to be quick, larger than one so a rail that
#: repainted by luck - an off-by-one, a boolean - cannot land on the right number.
ORGANIZED = 3


def _allowance_text(used: int) -> str:
    """What the rail must read once ``used`` files have been written, in core's own words.

    Built the way `service/account._summary` builds it, from the same three sources, so a
    reworded allowance line moves this test with it rather than breaking it.
    """
    current = licence.read_licence()
    remaining = allowance.remaining_for(current.state, used)
    return licence_notice.account_summary(
        current, remaining, allowance.FREE_FILE_ALLOWANCE
    ).allowance


def _organize(ui: Page, source: Path, destination: Path) -> None:
    """The journey `test_golden_path` walks, minus everything after the run."""
    ui.fill("#org-source", str(source))
    ui.fill("#org-dest", str(destination))
    ui.click("#org-preview")
    expect(ui.locator("#org-result")).to_contain_text("photos found")
    ui.click("#org-dedup")
    ui.fill("#org-confirm [data-typed-confirm]", "copy")
    ui.click("#org-confirm [data-typed-go]")
    expect(ui.locator("#org-result")).to_contain_text(f"{ORGANIZED} files organized")


def test_the_allowance_is_right_after_a_run_in_a_page_nobody_reloaded(
    ui: Page, tmp_path: Path, library
) -> None:
    """The defect, and the whole point of the file.

    Measured before the fix: organize 100 files through the app and the rail still read
    "700 of 1,000 left" while the server said 600. The two assertions are separate on purpose -
    the first says the number MOVED, the second says it moved to the right place. A repaint that
    fetched the wrong account would satisfy the first alone.
    """
    source = library(ORGANIZED, name="Pictures")
    rail = ui.locator("#account-slot .account-allowance")

    expect(rail).to_have_text(_allowance_text(0))
    _organize(ui, source, tmp_path / "Library")

    expect(rail).not_to_have_text(_allowance_text(0))
    expect(rail).to_have_text(_allowance_text(ORGANIZED))
    assert allowance.files_written() == ORGANIZED, "the server's own counter, for comparison"


def _folder(tmp_path: Path, name: str, seeds: range) -> Path:
    """Photos with the given seeds, so two folders here hold genuinely different pictures.

    ⚠ **The `library` fixture cannot do this**: it always seeds `0..count`, so two folders built
    from it are byte-identical and the second run is all exact duplicates. That would spend no
    allowance for a perfectly correct reason, and the test below would then be asserting that the
    number does NOT move - passing against the very defect it exists for.
    """
    root = tmp_path / name
    made = [make_photo(root / f"IMG_{seed:04d}.jpg", seed) for seed in seeds]
    stamp_capture_date(made)
    return root


def test_a_second_run_moves_it_again_rather_than_once(ui: Page, tmp_path: Path) -> None:
    """A repaint wired to a one-shot - a `once` flag, a boot-time guard - passes the test above."""
    rail = ui.locator("#account-slot .account-allowance")
    _organize(ui, _folder(tmp_path, "First", range(ORGANIZED)), tmp_path / "Library")
    expect(rail).to_have_text(_allowance_text(ORGANIZED))

    _organize(ui, _folder(tmp_path, "Second", range(100, 100 + ORGANIZED)), tmp_path / "Library")
    expect(rail).to_have_text(_allowance_text(ORGANIZED * 2))


def test_the_rail_still_says_nothing_during_the_run(ui: Page, tmp_path: Path, library) -> None:
    """D6 §3 forbids a countdown, so the repaint must be an END, never a stream.

    Asserted as *the number does not move while the job is in flight*: the run is started, the
    rail is read while the progress block is up, and it must still be the pre-run text. A
    live-updating rail - a `setInterval`, a per-file event - fails here and passes both tests
    above, which is why this is not folded into them.
    """
    source = library(ORGANIZED, name="Pictures")
    rail = ui.locator("#account-slot .account-allowance")
    ui.fill("#org-source", str(source))
    ui.fill("#org-dest", str(tmp_path / "Library"))
    ui.click("#org-preview")
    expect(ui.locator("#org-result")).to_contain_text("photos found")
    ui.click("#org-dedup")
    ui.fill("#org-confirm [data-typed-confirm]", "copy")

    ui.click("#org-confirm [data-typed-go]")
    # Read immediately, before waiting for the completion card: whatever the run is doing now,
    # the rail is describing the allowance as it stood before it started.
    assert rail.inner_text() == _allowance_text(0)

    expect(ui.locator("#org-result")).to_contain_text(f"{ORGANIZED} files organized")
    expect(rail).to_have_text(_allowance_text(ORGANIZED))
