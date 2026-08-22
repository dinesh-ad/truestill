"""The check lane gates the interpreter this project requires, from one job definition.

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

⚠ **Renamed and re-aimed 2026-08-22, when 3.14 stopped being evidence and became the gate.** The
file was `..._covers_both_interpreters` and asserted that 3.13 and 3.14 were both legs, with 3.14
allowed to fail. That was true of a transition that lasted a day. What survives is the part that
was never about a version: **one job definition**, and **the interpreter comes from the matrix**
so no step can pin one behind its back. The allowed-to-fail machinery is kept rather than deleted,
because 3.15 lands 2026-10-01 and will want exactly this shape again.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

_REPO = Path(__file__).resolve().parents[3]
_WORKFLOW = _REPO / ".github" / "workflows" / "ci.yml"

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


def _required_floor() -> str:
    """The minimum Python the manifests declare, as `major.minor`.

    Read from `truestill-core` because the three manifests are pinned equal by
    `test_the_three_packages_agree_on_a_floor`; if that ever stops being true this reads the one
    that matters, since core is what the other two depend on.
    """
    manifest = (_REPO / "packages/truestill-core/pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'requires-python\s*=\s*">=(\d+\.\d+)"', manifest)
    assert match is not None, (
        "truestill-core declares no `requires-python` floor to compare against"
    )
    return match.group(1)


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


def test_the_lane_gates_the_interpreter_the_manifests_require() -> None:
    """⚠ The lane and `requires-python` must name the same floor, or CI tests a version we do not
    ship - or ships one we do not test.

    Stronger than the assertion it replaced, which named `3.14` as a literal: this reads the floor
    out of the manifests, so bumping the floor and forgetting the lane fails here rather than
    passing quietly on the old interpreter.
    """
    floor = _required_floor()
    (job,) = _suite_jobs().values()
    matrix = job["strategy"]["matrix"]

    assert "python" in matrix, "the check lane pins one interpreter outside the matrix"
    assert floor in set(matrix["python"]), (
        f"the manifests require >={floor} and the lane runs {matrix['python']}; CI is not testing "
        f"the version this project ships"
    )
    # Both OS lanes matter more than the interpreter does: this machine is Linux, and the
    # platforms that break are the two nobody here can run.
    assert set(matrix["os"]) == {"ubuntu-latest", "macos-latest", "windows-latest"}


def test_every_leg_gates_and_the_machinery_for_an_unadopted_one_survives() -> None:
    """Every leg is a gate now - and `continue-on-error` stays matrix-driven for the next one.

    ⚠ **Read from the matrix rather than deleted**, and that is the point of keeping it. 3.15
    lands 2026-10-01 and will want an allowed-to-fail leg exactly as 3.14 had one; rebuilding the
    mechanism under time pressure is how someone hard-codes `continue-on-error: true` and silences
    the supported interpreter with it.
    """
    (job,) = _suite_jobs().values()

    assert job.get("continue-on-error") == "${{ matrix.experimental }}", (
        "the check lane's continue-on-error is not driven by the matrix. Hard-coding it true "
        "would silence the supported interpreter and leave the project with no gate at all."
    )
    flags = {
        entry["python"]: entry["experimental"] for entry in job["strategy"]["matrix"]["include"]
    }
    assert flags, "no leg declares whether it gates; `continue-on-error` reads an absent value"
    assert all(value is False for value in flags.values()), (
        f"a leg is allowed to fail while this project claims to support it: {flags}"
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
