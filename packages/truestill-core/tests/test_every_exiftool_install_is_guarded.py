"""(aeq) Every lane that installs exiftool proves it is callable, and Windows retries a feed 503.

**The defect this exists to prevent, measured rather than imagined.** exiftool is installed three
ways and the care was uneven: Linux went through `scripts/ci_bounded.sh` (bounded, retried), macOS
was a bare `brew install` with nothing at all, and Windows was a bare `choco install` plus a probe.
On 2026-08-21 **two of three Windows install attempts inside thirty minutes** died on an identical
`503 (Service Unavailable)` from `community.chocolatey.org`, one of them on a docs-only push.

⚠ **THE RETRY MUST BE KEYED ON THE PROBE, NEVER ON THE EXIT CODE**, and that is what the second
test pins. `choco` **returns 0** after a feed 503 - upstream `chocolatey/choco#1609` is titled
*"Chocolatey reporting success when install fails with 503 error"* - so `$LASTEXITCODE` cannot
distinguish a working install from a missing one. A retry written against it would be a loop that
never loops, green on every run, and indistinguishable from one that works.

That is the same shape as `ci_bounded.sh` keying on exit 124 because apt swallows its status and
deadlocks. Different swallowed signal, different observable, so the two are **deliberately not one
mechanism** - which is why this file exists beside `test_ci_bounds_apt_in_one_place.py` rather
than inside it.

**The subject is proved non-empty first** (§4, fifty-second member): a guard that finds no install
steps reports the same green as one over a correct workflow.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

_WORKFLOW = Path(__file__).resolve().parents[3] / ".github" / "workflows" / "ci.yml"

#: What a step must invoke to count as an exiftool install.
_INSTALLERS = (
    "apt-get install -y libimage-exiftool-perl",
    "brew install exiftool",
    "choco install exiftool",
)

#: The probe. Running the binary is the only thing that distinguishes "resolved" from "runs" -
#: `ENGINEERING_STANDARD.md` §4's forty-second member, where this exact proxy was caught twice.
_PROBE = "exiftool -ver"


def _steps() -> list[dict[str, Any]]:
    workflow = yaml.safe_load(_WORKFLOW.read_text(encoding="utf-8"))
    return [
        step
        for job in workflow["jobs"].values()
        for step in (job.get("steps") or [])
        if isinstance(step, dict)
    ]


def _run_of(step: dict[str, Any]) -> str:
    run = step.get("run")
    return run if isinstance(run, str) else ""


def _install_steps() -> list[tuple[str, str]]:
    found = []
    for step in _steps():
        run = _run_of(step)
        if any(marker in run for marker in _INSTALLERS):
            found.append((str(step.get("name") or "<unnamed>"), run))
    return found


def test_the_scan_actually_finds_the_install_steps() -> None:
    """Non-emptiness, first. Zero violations over zero steps is not a pass."""
    found = _install_steps()

    assert found, "no exiftool install step found in ci.yml; the guard is aimed at nothing"
    assert len(found) >= 3, f"expected one install per platform, found: {[n for n, _ in found]}"


def test_every_exiftool_install_proves_the_binary_runs() -> None:
    """Resolving is not running. A silently missing exiftool surfaces minutes later as twenty
    unrelated-looking test errors instead of one clear failure at the step that caused it."""
    unguarded = [name for name, run in _install_steps() if _PROBE not in run]

    assert not unguarded, (
        f"these install exiftool without proving it is callable: {unguarded}. A package manager "
        f"that reports success and installs nothing is not hypothetical - see (aeq)."
    )


def test_the_windows_retry_is_keyed_on_the_probe_and_not_the_exit_code() -> None:
    """⚠ The load-bearing assertion of this file.

    `choco` returns 0 after a feed 503, so a retry gated on `$LASTEXITCODE` would never fire and
    would be green forever. The loop must decide from `Get-Command exiftool`, which is the only
    thing that knows.
    """
    windows = [run for name, run in _install_steps() if "choco install exiftool" in run]
    assert len(windows) == 1, f"expected exactly one Windows install step, found {len(windows)}"
    run = windows[0]

    assert "Get-Command exiftool" in run, (
        "the Windows install does not decide from the probe. choco returns 0 after a feed 503 "
        "(chocolatey/choco#1609), so anything keyed on the exit code is a loop that never loops."
    )
    # ⚠ COMMENTS STRIPPED FIRST. The step EXPLAINS why it does not use `$LASTEXITCODE`, so a
    # bare identifier search matches the prose arguing against it and reports the opposite of the
    # truth. §4 names this exactly: assert the STATEMENT, never an identifier that also appears in
    # the target's own commentary. It cost one red run here before the rule was applied.
    code = "\n".join(line for line in run.splitlines() if not line.strip().startswith("#"))
    assert "LASTEXITCODE" not in code, (
        "the Windows install consults choco's exit code, which cannot distinguish a 503 from a "
        "success. Decide from the probe instead."
    )
    assert "Start-Sleep" in run, (
        "the retry re-enters immediately. The trigger is a server-side temporary failure that may "
        "still be in force - see scripts/ci_bounded.sh, which pauses for the same reason."
    )


def test_a_failed_windows_install_is_never_silent() -> None:
    """A green second attempt must not read as a clean first one, and exhaustion must fail.

    `ci_bounded.sh` carries the same property in its own words: *a swallowed timeout prints what
    was killed and how long it had.* A retry nobody can see in the log is a flake-laundering
    machine (§4, twenty-sixth member).
    """
    run = next(r for _n, r in _install_steps() if "choco install exiftool" in r)

    assert "::warning::" in run, "a retried install says nothing, so a flake looks like a clean run"
    assert "throw" in run, "the loop can fall through without failing the step"


def test_every_exiftool_install_is_bounded() -> None:
    """An unbounded network fetch destroys its evidence at the moment it becomes valuable.

    §4's forty-third member: cancelling a hung step discards its logs, so the one run that
    reproduced the fault is the one you cannot read. GitHub's default job timeout is six hours.
    """
    unbounded = [
        str(step.get("name") or "<unnamed>")
        for step in _steps()
        if any(marker in _run_of(step) for marker in _INSTALLERS)
        and step.get("timeout-minutes") is None
    ]

    assert not unbounded, f"these install exiftool over the network with no step bound: {unbounded}"
