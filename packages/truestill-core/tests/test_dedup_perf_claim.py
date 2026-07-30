"""Pin the complexity justification to the measured curve (audit F5)."""

from __future__ import annotations

from pathlib import Path

DEDUP = Path(__file__).resolve().parents[1] / "src" / "truestill_core" / "dedup.py"
PERFORMANCE = Path(__file__).resolve().parents[3] / "docs" / "PERFORMANCE.md"


def test_dedup_docstring_cites_the_measured_10k_cost_not_the_2275_row() -> None:
    """The O(n^2) justification must quote PERFORMANCE.md §3 at the alarm threshold.

    The bug was taking the 0.72 s @ 2,275 row and writing it as 0.7s for 10,000 - understating
    the cost by ~19x exactly where LINEAR_SCAN_ALARM fires.
    """
    doc = DEDUP.read_text(encoding="utf-8")
    module_doc = doc.split('"""', 2)[1]
    assert "13.5 s at 10,000" in module_doc
    assert "0.72 s at 2,275" in module_doc
    assert "0.7s for 10,000" not in module_doc
    assert "0.7 s for 10,000" not in module_doc
    assert "cheapest thing in the pipeline" not in module_doc

    perf = PERFORMANCE.read_text(encoding="utf-8")
    assert "| 2,275 | 0.72 s |" in perf
    assert "| 10,000 | 13.5 s |" in perf
