"""Splitting the browser lane by engine must not make half of it quietly optional.

⚠ **THE WHOLE RISK OF A MATRIX.** One job became two on 2026-09-12. A `fail-fast: false` that
drifted into `continue-on-error: true`, or a leg dropped from the matrix, would leave the Actions
tab green while an engine's 632 tests either failed or never ran - and WebKit is the engine the
product actually ships in on Linux and macOS. Two of this project's timing defects were
WebKit-only, so the leg most worth losing is the one most likely to be lost.

The tolerance that DOES exist is narrow and is pinned by
`test_a_measurement_dispatch_does_not_paint_main_red`: only a `workflow_dispatch` that passed a
non-empty `e2e_extra`. Nothing here may widen it.
"""

from __future__ import annotations

from pathlib import Path

import yaml

_CI = Path(__file__).resolve().parents[3] / ".github" / "workflows" / "ci.yml"

#: The engines the product ships in. `(jj)` and the Tauri note: WebKitGTK on Linux, WKWebView on
#: macOS. A matrix that lost either is a lane testing something the user never runs.
_REQUIRED = {"chromium", "webkit"}


def _e2e() -> dict:
    return dict(yaml.safe_load(_CI.read_text(encoding="utf-8"))["jobs"]["e2e"])


def test_both_engines_are_still_legs() -> None:
    """The anti-vacuity anchor for every assertion below: there are two legs to fail."""
    browsers = set(_e2e()["strategy"]["matrix"]["browser"])

    assert browsers == _REQUIRED, (
        f"the browser matrix is {sorted(browsers)}; the lane must run both engines the product "
        "ships in, and a leg removed here is 632 tests that stop running with nothing going red"
    )


def test_a_red_leg_is_not_tolerated_on_an_ordinary_run() -> None:
    """⚠ **The property the split could silently lose.** `continue-on-error` is allowed to name
    only the measurement case; a bare `true` here would make BOTH engines optional at once."""
    tolerance = str(_e2e()["continue-on-error"]).strip()

    assert tolerance not in {"true", "True", "${{ true }}"}, (
        f"every e2e leg is allowed to fail: {tolerance}"
    )
    assert "github.event_name == 'workflow_dispatch'" in tolerance, (
        f"the tolerance is not confined to a dispatch: {tolerance}"
    )
    assert "e2e_extra" in tolerance, (
        f"the tolerance is not confined to a non-default configuration: {tolerance}"
    )


def test_fail_fast_is_off_so_one_engine_does_not_hide_the_other() -> None:
    """`fail-fast: true` would CANCEL webkit the moment chromium went red, so a run with two
    real failures would report one and destroy the evidence for the other. Off is not tolerance -
    the run still fails; it fails with both answers."""
    assert _e2e()["strategy"]["fail-fast"] is False


def test_each_leg_reports_its_own_count_under_its_own_name() -> None:
    """Two legs uploading one artifact name is an ERROR in upload-artifact v4+, and the junit
    floor has to run per leg or a leg that collected nothing would pass unnoticed."""
    steps = _e2e()["steps"]
    names = [str(s.get("with", {}).get("name", "")) for s in steps if "with" in s]
    uploads = [n for n in names if n.startswith(("test-results-e2e", "e2e-failure-artifacts"))]

    assert uploads, "no e2e artifact uploads found, so this guard has no subject"
    for name in uploads:
        assert "${{ matrix.browser }}" in name, (
            f"artifact `{name}` is not per-leg; two legs uploading one name is a hard error"
        )

    floors = [s for s in steps if "check_junit_floor" in str(s.get("run", ""))]
    assert len(floors) == 1, "the junit floor must run in every leg, once per leg"
