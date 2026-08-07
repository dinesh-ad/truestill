"""TEMPORARY - forces one e2e failure so CI can be checked for a real uploaded trace.

Never merged. A green upload step is exactly what has been lying, so the only proof that
`include-hidden-files: true` works is an artifact that actually lands.
"""

from playwright.sync_api import Page


def test_zzz_deliberate_failure_to_prove_trace_capture(ui: Page) -> None:
    assert ui.title() == "this will never match", "deliberate: proving the trace uploads"
