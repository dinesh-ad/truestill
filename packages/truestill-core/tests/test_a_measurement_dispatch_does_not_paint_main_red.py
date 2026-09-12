"""The browser lane tolerates a failure ONLY when somebody asked for a non-default configuration.

⚠ **WRITTEN AFTER IT HAPPENED.** On 2026-09-12 an `-n auto` dispatch went red on `efe9ec3` forty
minutes after the ordinary lane went green on the same commit. Both sat in the Actions tab with
nothing to tell them apart: a red `main` that was not one. `e2e_extra` exists so a configuration
can be TRIED without editing the lane, and a tried configuration that does not work is the
experiment succeeding, not the branch breaking.

**The property this guards is the other half** - that the NIGHTLY can still fail the run. On a
`schedule` every input is null, and GitHub then coerces both sides to a number so
`inputs.e2e_extra != ''` is false on its own. That is the documented behaviour, and it is also
the whole nightly resting on a coercion rule: simplify the expression to the shorter form that
"obviously works" and the scheduled lane silently becomes allowed-to-fail, which is the failure
this repo cannot see - a guard that is green because it stopped guarding.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

_CI = Path(__file__).resolve().parents[3] / ".github" / "workflows" / "ci.yml"


def _e2e_job() -> dict[str, Any]:
    workflow = yaml.safe_load(_CI.read_text(encoding="utf-8"))
    return dict(workflow["jobs"]["e2e"])


def test_the_lane_is_allowed_to_fail_only_on_a_dispatch_that_asked_for_something() -> None:
    """Both halves in one expression: the event AND a non-empty `e2e_extra`."""
    expression = str(_e2e_job()["continue-on-error"])

    assert "workflow_dispatch" in expression, (
        f"the event is not named, so a scheduled run could be tolerated too: {expression}"
    )
    assert "e2e_extra" in expression, (
        f"nothing ties the tolerance to a non-default configuration: {expression}"
    )


def test_the_nightly_cannot_be_tolerated_by_a_coercion_rule() -> None:
    """⚠ **The conjunct is the point, not the style.** Without `github.event_name` the scheduled
    lane's ability to fail depends on null coercing to `''` - true today, and invisible the day
    it is not. This asserts the guard does not rest on that."""
    expression = str(_e2e_job()["continue-on-error"])

    assert "github.event_name == 'workflow_dispatch'" in expression, (
        f"the schedule case must be unreachable by construction, not by type coercion: {expression}"
    )
    assert "&&" in expression, f"the two conditions are not both required: {expression}"


def test_the_check_lanes_are_not_tolerated_at_all() -> None:
    """The anti-vacuity anchor. `check` carries its own matrix-driven `continue-on-error`, which
    is `false` for every leg; if this file's subject ever spread to the gate lanes, the tests
    above would still pass while every platform became allowed-to-fail."""
    workflow = yaml.safe_load(_CI.read_text(encoding="utf-8"))
    check = workflow["jobs"]["check"]

    assert check["continue-on-error"] == "${{ matrix.experimental }}"
    legs = check["strategy"]["matrix"]["include"]
    assert legs, "no matrix legs, so the assertion below is free"
    assert all(leg["experimental"] is False for leg in legs), (
        f"a gate lane is allowed to fail: {legs}"
    )
