"""A result on screen describes the fields that produced it, and stops when they change.

**The defect.** The two path fields are wired only to `validatePath` (`app.js:2080-2088`), whose
branches touch nothing but the hint span (`app.js:2005-2018`). The only reset of `#org-result` is
inside the Look-inside handler (`app.js:2578`). So typing a new folder over a finished preview
leaves the previous folder's card, its tally and its typed-confirm control on screen, and
`startOrganizeRun` reads the fields fresh at click time - the button offers to organize a count
that belongs to a folder the form no longer names.

**Why these gate on the contract rather than on prose.** Each asserts the presence and absence of
`[data-testid="org-tally"]` and `#org-confirm [data-typed-confirm]` - a payload-derived element and
a control - never a sentence, which is `ENGINEERING_STANDARD.md` §4's eighty-seventh member.

**Each test asserts the precondition first, and that is the non-vacuity proof.** The tally is
asserted PRESENT, with the file count of the first folder, before the field is touched. A wrong
selector fails there rather than at the invalidation, so a failure at the second assertion is the
defect and cannot be a typo.

The ten-second budget on the invalidation assertions is deliberate and well above anything a real
reset would need: the `input` listener is debounced 400 ms (`app.js:2085`) and a reset on the event
is synchronous. The 30 s suite budget is for waiting on work; this waits on a DOM removal.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from playwright.sync_api import Page, expect

#: `strict=True` so the fix cannot land quietly: the moment Stage 2 wires the invalidation
#: these XPASS, the lane goes red, and the marker has to come off in the fix's own commit.
#: Committed marked rather than red, because a red `main` is not a to-do list.


@pytest.mark.xfail(
    strict=True,
    reason="Stage 1: no listener clears #org-result on a source change (app.js:2080-2088)",
)
def test_a_new_source_clears_the_result_that_described_the_old_one(
    ui: Page, tmp_path: Path, library
) -> None:
    alpha = library(6, name="Alpha")
    bravo = library(3, name="Bravo")
    ui.check('input[name="org-mode"][value="copy"]')
    ui.fill("#org-source", str(alpha))
    ui.fill("#org-dest", str(tmp_path / "Out"))
    ui.click("#org-preview")
    expect(ui.locator("#org-result")).to_contain_text("photos found", timeout=30_000)
    ui.click("#org-dedup")

    # Precondition, and the non-vacuity proof: the tally is here and it describes Alpha's six.
    expect(ui.locator('#org-result [data-testid="org-tally"]')).to_have_attribute(
        "data-files", "6", timeout=60_000
    )

    ui.fill("#org-source", str(bravo))

    expect(ui.locator('#org-result [data-testid="org-tally"]')).to_have_count(0, timeout=10_000)


@pytest.mark.xfail(
    strict=True,
    reason="Stage 1: nothing clears #org-confirm on a source change; app.js:2608 is the dedup path only",
)
def test_a_new_source_clears_the_typed_confirm_that_offered_the_old_run(
    ui: Page, tmp_path: Path, library
) -> None:
    alpha = library(6, name="Alpha")
    bravo = library(3, name="Bravo")
    ui.check('input[name="org-mode"][value="copy"]')
    ui.fill("#org-source", str(alpha))
    ui.fill("#org-dest", str(tmp_path / "Out"))
    ui.click("#org-preview")
    expect(ui.locator("#org-result")).to_contain_text("photos found", timeout=30_000)
    ui.click("#org-dedup")

    # Precondition: the run is on offer for Alpha. `startOrganizeRun` reads the fields at click
    # time, so leaving this control up after the source changes offers Alpha's count for Bravo.
    expect(ui.locator("#org-confirm [data-typed-confirm]")).to_be_visible(timeout=60_000)

    ui.fill("#org-source", str(bravo))

    expect(ui.locator("#org-confirm [data-typed-confirm]")).to_have_count(0, timeout=10_000)


@pytest.mark.xfail(
    strict=True,
    reason="Stage 1: the destination field is wired to validatePath alone (app.js:2080-2088)",
)
def test_a_new_destination_clears_the_result_and_the_typed_confirm(
    ui: Page, tmp_path: Path, library
) -> None:
    alpha = library(6, name="Alpha")
    ui.check('input[name="org-mode"][value="copy"]')
    ui.fill("#org-source", str(alpha))
    ui.fill("#org-dest", str(tmp_path / "Out"))
    ui.click("#org-preview")
    expect(ui.locator("#org-result")).to_contain_text("photos found", timeout=30_000)
    ui.click("#org-dedup")
    expect(ui.locator('#org-result [data-testid="org-tally"]')).to_have_attribute(
        "data-files", "6", timeout=60_000
    )
    expect(ui.locator("#org-confirm [data-typed-confirm]")).to_be_visible()

    # The destination is in the preview payload (`app.js:2612`) and, since `D14`, in the promise
    # the tally states - so a second destination is a different answer, not the same one.
    ui.fill("#org-dest", str(tmp_path / "Out2"))

    expect(ui.locator('#org-result [data-testid="org-tally"]')).to_have_count(0, timeout=10_000)
    expect(ui.locator("#org-confirm [data-typed-confirm]")).to_have_count(0, timeout=10_000)


@pytest.mark.xfail(
    strict=True,
    reason="Stage 1: the mode radios rebuild the form (app.js:2156) and leave the result standing",
)
def test_a_new_mode_clears_the_result_and_the_typed_confirm(
    ui: Page, tmp_path: Path, library
) -> None:
    alpha = library(6, name="Alpha")
    ui.check('input[name="org-mode"][value="copy"]')
    ui.fill("#org-source", str(alpha))
    ui.fill("#org-dest", str(tmp_path / "Out"))
    ui.click("#org-preview")
    expect(ui.locator("#org-result")).to_contain_text("photos found", timeout=30_000)
    ui.click("#org-dedup")
    expect(ui.locator('#org-result [data-testid="org-tally"]')).to_have_attribute(
        "data-files", "6", timeout=60_000
    )
    expect(ui.locator("#org-confirm [data-typed-confirm]")).to_be_visible()

    # copy to move, not to inplace: the destination field stays on screen, so the only thing that
    # changed is the mode. `mode` is in the preview payload and decides the confirm word.
    ui.check('input[name="org-mode"][value="move"]')

    expect(ui.locator('#org-result [data-testid="org-tally"]')).to_have_count(0, timeout=10_000)
    expect(ui.locator("#org-confirm [data-typed-confirm]")).to_have_count(0, timeout=10_000)


@pytest.mark.xfail(
    strict=True,
    reason="Stage 1: the gate at app.js:2572-2575 refuses, though the call it guards posts { source } alone",
)
def test_look_inside_reports_the_folder_without_a_destination(ui: Page, library) -> None:
    alpha = library(6, name="Alpha")
    ui.check('input[name="org-mode"][value="copy"]')
    ui.fill("#org-source", str(alpha))

    # Precondition: the destination really is empty, so the gate at `app.js:2572-2575` is the only
    # thing that can refuse. The call it guards posts `{ source }` alone (`app.js:2580`) and
    # `server.py:266-270` reads `body["source"]` and nothing else, so the destination is not an
    # input to this answer.
    expect(ui.locator("#org-dest")).to_have_value("")

    ui.click("#org-preview")

    expect(ui.locator("#org-result .card.result")).to_be_visible(timeout=30_000)
    expect(ui.locator("#org-dedup")).to_be_enabled(timeout=10_000)
