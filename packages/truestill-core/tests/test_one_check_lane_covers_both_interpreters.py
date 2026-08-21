"""The 3.14 leg is a matrix dimension of the check lane, never a second copy of it.

**Why this is a guard and not a note.** `ci.yml`'s `check` job carries 22 steps of accumulated,
hard-won detail: an apt drop-in that contains LP#2003851, a Windows Defender exclusion, a `TEMP`
move onto the fast volume, a 20-minute bound written after a 33-minute hang, and the timing
probes that measure all of it. A `check-314:` job pasted beside it would be correct on the day it
landed and wrong by the next fix - whichever lane the author was looking at would get the change
and the other would drift, both staying green. That is `ENGINEERING_STANDARD.md` §4's fifty-sixth
member with a schedule attached.

⚠ **The sharing is structural, so this test asserts the structure rather than comparing text.**
One job definition means the steps cannot differ; what could still go wrong is somebody adding a
second job later, or pinning an interpreter inside a step so the 3.14 leg quietly runs 3.13.

**3.14 is evidence, not a target.** The move was deferred - 3.13 is supported to October 2029 and
3.15 lands 2026-10-01 - so the leg must stay `continue-on-error`, or a version this project has
not adopted acquires the power to redden `main`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

_WORKFLOW = Path(__file__).resolve().parents[3] / ".github" / "workflows" / "ci.yml"

#: What identifies the check lane, whatever it is called.
#:
#: ⚠ **`uv run mypy`, NOT the `uv sync` line, and the first version got this wrong.** Syncing the
#: workspace is what *every* lane does - the browser lane matched it too, so the guard reported
#: "2 jobs run the test suite" and named `e2e`, which is a different lane on purpose. A marker
#: that catches a neighbour is a guard that will be switched off. Type-checking is the check
#: lane's own job and nothing else does it.
_SUITE_MARKER = "uv run mypy"


def _workflow() -> dict[str, Any]:
    return yaml.safe_load(_WORKFLOW.read_text(encoding="utf-8"))


def _suite_jobs() -> dict[str, Any]:
    return {
        name: job
        for name, job in _workflow()["jobs"].items()
        if any(_SUITE_MARKER in str(step.get("run", "")) for step in (job.get("steps") or []))
    }


def test_the_scan_actually_finds_the_check_lane() -> None:
    """Non-emptiness first: zero violations over zero jobs is not a pass (§4, fifty-second)."""
    found = _suite_jobs()

    assert found, (
        f"no job in ci.yml syncs the workspace with {_SUITE_MARKER!r}; this guard is aimed at "
        f"nothing and would report the same green over a deleted lane"
    )


def test_exactly_one_job_runs_the_suite() -> None:
    """⚠ The load-bearing assertion. Two interpreters, one lane.

    A second job would duplicate 22 steps of workarounds that each earned their place after a
    real failure, and nothing would keep the copies in step.
    """
    found = _suite_jobs()

    assert len(found) == 1, (
        f"{len(found)} jobs run the test suite: {sorted(found)}. The interpreter belongs in the "
        f"matrix, not in a second job - see this module's docstring for what drifts."
    )


def test_both_interpreters_are_matrix_legs_of_that_one_job() -> None:
    """The coverage half: 3.14 must actually be exercised, on every OS the lane covers."""
    (job,) = _suite_jobs().values()
    matrix = job["strategy"]["matrix"]

    assert "python" in matrix, "the check lane pins one interpreter; 3.14 is not exercised at all"
    assert set(matrix["python"]) >= {"3.13", "3.14"}, (
        f"expected both interpreters as matrix legs, found {matrix['python']}"
    )
    # Both OS lanes matter more than the interpreter does: this machine is Linux, and the
    # platforms that break are the two nobody here can run.
    assert set(matrix["os"]) == {"ubuntu-latest", "macos-latest", "windows-latest"}


def test_the_unadopted_interpreter_cannot_redden_main() -> None:
    """3.14 reports; it does not gate. The move was deferred and this encodes that decision.

    ⚠ Read from the matrix rather than hard-coded `true`, because a blanket
    `continue-on-error: true` would ALSO stop 3.13 failing the build - which is the whole gate.
    """
    (job,) = _suite_jobs().values()

    assert job.get("continue-on-error") == "${{ matrix.experimental }}", (
        "the check lane's continue-on-error is not driven by the matrix. Hard-coding it true "
        "would silence 3.13 as well and leave the project with no gate at all."
    )
    flags = {
        entry["python"]: entry["experimental"] for entry in job["strategy"]["matrix"]["include"]
    }
    assert flags["3.13"] is False, "the supported interpreter stopped gating the build"
    assert flags["3.14"] is True, (
        "3.14 can now fail the build for a version this project has not adopted"
    )


def test_no_step_pins_an_interpreter_behind_the_matrix_s_back() -> None:
    """The quiet failure: a step that names 3.13 runs 3.13 inside the 3.14 leg, and passes.

    `UV_PYTHON` is set once at job level so every `uv` call inherits it. A literal version in a
    step would override that for one command and report green about the wrong interpreter -
    exactly the shape of today's `(aev)` initializer, which was green because the platform it ran
    on hid the defect.
    """
    (job,) = _suite_jobs().values()

    assert job.get("env", {}).get("UV_PYTHON") == "${{ matrix.python }}", (
        "the job does not select its interpreter from the matrix, so the 3.14 leg is not "
        "guaranteed to run 3.14"
    )
    offenders = [
        str(step.get("name") or step.get("run", ""))[:60]
        for step in job["steps"]
        if "uv python install" in str(step.get("run", ""))
        and "${{ matrix.python }}" not in str(step.get("run", ""))
    ]
    assert not offenders, f"these steps install a hard-coded interpreter: {offenders}"
