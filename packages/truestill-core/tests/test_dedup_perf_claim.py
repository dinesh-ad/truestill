"""Pin the complexity justification to the measured curve (audit F5)."""

from __future__ import annotations

from pathlib import Path

DEDUP = Path(__file__).resolve().parents[1] / "src" / "truestill_core" / "dedup.py"
PERFORMANCE = Path(__file__).resolve().parents[3] / "docs" / "PERFORMANCE.md"


def test_dedup_docstring_cites_the_measured_10k_cost_not_the_2275_row() -> None:
    """The O(n^2) justification must quote PERFORMANCE.md §3 at the alarm threshold.

    The bug was taking the 0.72 s @ 2,275 row and writing it as 0.7s for 10,000 - understating
    the cost by ~19x at exactly the size where `LINEAR_SCAN_ALARM` then warned. (That constant
    was removed on 2026-08-02 with the packed matcher; the figures it guards are still the
    honest cost of the implementation §3 measured, which is why this guard outlives it.)

    Figures re-measured 2026-07-31 to the PERFORMANCE.md §2.1 method (median over n runs); the
    docstring and the table are pinned to each other so neither can drift alone.
    """
    doc = DEDUP.read_text(encoding="utf-8")
    module_doc = doc.split('"""', 2)[1]
    assert "13.709 s at 10,000" in module_doc
    assert "0.685 s at 2,275" in module_doc

    # The original defect and its neighbours: the 2,275 cost worn as the 10,000 cost.
    for understatement in ("0.7s for 10,000", "0.7 s for 10,000", "0.685 s at 10,000"):
        assert understatement not in module_doc
    assert "cheapest thing in the pipeline" not in module_doc

    # Both figures must still be the ones §3 actually records, not a stale copy of them.
    perf = PERFORMANCE.read_text(encoding="utf-8")
    assert "| 2,275 | 0.685 s |" in perf
    assert "| 10,000 | 13.709 s |" in perf
