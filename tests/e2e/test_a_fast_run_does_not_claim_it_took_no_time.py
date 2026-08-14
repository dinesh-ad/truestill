"""`fmtDuration` rounds, and a completed run must not round to nothing.

**Found in a screenshot, not by a test.** A real 14-photo organize finished in under half a
second and the result card said **"0s taken"**. `Math.round(0.4)` is `0`, and all four callers of
this helper render a *completed* duration - "0s taken", "elapsed 0s", "checked in 0s" - so the
rounding turned a fast run into a claim that no time passed at all. On a card whose entire job is
to report honestly what a run did, that is the wrong direction to be wrong in.

Tested against the helper directly rather than through a run: the defect is in a pure function,
and driving a real organize fast enough to hit it would be a race by construction.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [
        pytest.param(0.4, "under 1s", id="the screenshot case"),
        pytest.param(0.04, "under 1s", id="far below the rounding boundary"),
        pytest.param(0, "under 1s", id="a literal zero is still not 'no time'"),
        pytest.param(0.6, "1s", id="rounds up as it always did"),
        pytest.param(1, "1s", id="one second"),
        pytest.param(59, "59s", id="just under a minute"),
        pytest.param(61, "1m 01s", id="minutes are unchanged"),
        pytest.param(3661, "1h 01m", id="hours are unchanged"),
    ],
)
def test_a_duration_never_reads_as_zero(ui: Page, seconds: float, expected: str) -> None:
    """The boundary and both sides of it, because a fix that only moved the rounding would be
    just as wrong one step further down."""
    rendered = ui.evaluate("(s) => fmtDuration(s)", seconds)
    assert rendered == expected, f"fmtDuration({seconds}) rendered {rendered!r}"


def test_the_result_card_says_it_rather_than_zero(ui: Page) -> None:
    """End of the same claim, where a person actually reads it: the organize card."""
    summary = {
        "organized": 3,
        "photos": 3,
        "videos": 0,
        "audio": 0,
        "bytes_organized": 5000,
        "duplicates": 0,
        "bytes_saved": 0,
        "moved_by_copy": 3,
        "moved_in_place": 0,
        "failed": 0,
        "folders": {},
        "outcomes": {"organized": 3},
        "mode": "copy",
        "elapsed_seconds": 0.42,
        "organized_sample": {"total": 0, "shown": []},
    }
    ui.evaluate(
        # THE PROPS ENTRY POINT. `#org-result` has one owner - the React island - so writing its
        # innerHTML from outside is either clobbered on the next render or, worse, survives
        # while the island believes it rendered nothing. That second case is not hypothetical:
        # it left this suite green while the row solver never ran, and only the panorama guard
        # noticed. The island is told what state to be in; it decides the DOM.
        "(s) => { window.organizeResult.set({ kind: 'complete', summary: s }); }",
        summary,
    )
    text = ui.inner_text("#org-result")
    assert "0s taken" not in text, "a sub-second run still reports that it took no time"
    assert "under 1s taken" in text, f"the duration is missing entirely: {text!r}"
