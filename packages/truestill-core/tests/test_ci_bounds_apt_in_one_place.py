"""apt's mirror bound is set ONCE per job, in config, not re-applied per command. `(aee)`.

**The defect this exists to prevent is one I made and shipped.** On 2026-08-19 the bound went in
as flags on a single step - `sudo apt-get -o Acquire::Retries=1 ... update` - which bounded the
one call site I happened to be looking at. Run **32295312064** found the rest during a live
mirror outage:

* the `check` job's exiftool step - **fixed**, took **58 s**;
* the `e2e` job's OWN exiftool step - same command, different job, **never touched**;
* `playwright install --with-deps`, which shells out to `apt-get` **internally** - **37+ minutes**,
  and no flag of ours can reach it.

**Bounding a call site fixes the calls you can see.** The setting belongs in
`/etc/apt/apt.conf.d/`, where every apt invocation inherits it - ours, Playwright's, and whatever
is added next.

⚠ **Both halves are needed and the second is the cry-wolf one.** "No step carries flags" is green
on a workflow with no bound at all; "every apt job has the drop-in" is what makes deleting it
fail. Removing either leaves a real regression silent - proved by mutation, not assumed.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import yaml

_WORKFLOW = Path(__file__).resolve().parents[3] / ".github" / "workflows" / "ci.yml"

#: The drop-in writes this file; a step is the bound if it mentions it.
_DROP_IN = "/etc/apt/apt.conf.d/"

#: The out-of-band bound. apt's own timeout does not survive LP#2003851, so every consumer runs
#: under `timeout(1)` with one retry - see `scripts/ci_bounded.sh`.
_BOUNDED = "ci_bounded.sh"

#: What marks a step as an apt CONSUMER. `--with-deps` is here because Playwright's installer
#: runs `apt-get` itself - the call site that proved per-command flags were the wrong altitude.
_CONSUMERS = ("apt-get", "apt install", "--with-deps")


def _jobs() -> dict[str, list[dict[str, Any]]]:
    data = yaml.safe_load(_WORKFLOW.read_text())
    return {name: job.get("steps", []) for name, job in data["jobs"].items()}


def _run_of(step: dict[str, Any]) -> str:
    value = step.get("run")
    return value if isinstance(value, str) else ""


def test_no_apt_command_carries_its_own_retry_flags() -> None:
    """A step that invokes apt must not also set the policy - that is a second encoding.

    Two places holding one setting is how they drift, and the drifted one is silent: it looks
    configured. The next person needing a different bound must edit the drop-in, where it applies
    to every consumer, rather than adding a flag that covers their command alone.
    """
    offenders = [
        (job, step.get("name", "<unnamed>"))
        for job, steps in _jobs().items()
        for step in steps
        if any(marker in _run_of(step) for marker in _CONSUMERS)
        and "Acquire::" in _run_of(step)
        and _DROP_IN not in _run_of(step)
    ]

    assert not offenders, (
        "apt commands carrying their own Acquire:: flags:\n"
        + "\n".join(f"    {job}: {name}" for job, name in offenders)
        + "\n\nThe bound belongs in the drop-in, which every apt consumer inherits - including "
        "`playwright install --with-deps`, whose apt call takes no flags from us. `(aee)`."
    )


def test_every_job_that_uses_apt_bounds_it_first() -> None:
    """⚠ THE CRY-WOLF HALF, and the one that catches the defect that actually happened.

    The test above is green on a workflow with no bound anywhere. This one fails the moment a job
    reaches apt without one, or reaches it BEFORE one - which is the same failure, since a drop-in
    written after the install it was meant to bound has bounded nothing.
    """
    for job, steps in _jobs().items():
        first_consumer = next(
            (
                index
                for index, step in enumerate(steps)
                if any(marker in _run_of(step) for marker in _CONSUMERS)
            ),
            None,
        )
        if first_consumer is None:
            continue
        bound_at = next(
            (index for index, step in enumerate(steps) if _DROP_IN in _run_of(step)), None
        )
        assert bound_at is not None, (
            f"job '{job}' invokes apt but never bounds its mirror retries. Add the "
            f"`Bound apt's mirror retries` step before the first apt consumer. `(aee)`."
        )
        assert bound_at < first_consumer, (
            f"job '{job}' bounds apt at step {bound_at} but first uses it at {first_consumer}. "
            "A bound written after the install it was meant to cover has bounded nothing."
        )


def test_the_guard_can_see_the_playwright_call_site() -> None:
    """The one that made this necessary must actually be visible to the rule above.

    `playwright install --with-deps` carries no literal `apt-get`, so a guard matching only that
    string would pass a workflow whose longest apt call is entirely unbounded - green, and blind
    to the 37-minute step. This pins that `--with-deps` counts as a consumer.
    """
    steps = _jobs()["e2e"]
    playwright = [s for s in steps if "playwright install" in _run_of(s)]
    assert playwright, "the e2e job no longer installs browsers - has this moved?"
    assert any("--with-deps" in _run_of(s) for s in playwright), (
        "`playwright install` no longer passes --with-deps. If the system dependencies are now "
        "installed some other way, teach `_CONSUMERS` about it - otherwise this guard is blind "
        "to the call site it was written for."
    )


def test_every_apt_consumer_runs_under_the_out_of_band_bound() -> None:
    """⚠ apt's OWN TIMEOUT DOES NOT SURVIVE THE HANG, SO THE BOUND MUST BE OUTSIDE IT.

    `LP#2003851` is a queue-ordering deadlock in apt's retry machinery: a source failing with a
    retry-after delay is queued behind lower-priority items, and workers on half-closed
    connections never get new instructions. Measured on run 32302928420 - apt reached a WORKING
    mirror in 16 s, then hung 19m54s on a 126 kB file with `Acquire::http::Timeout` set and
    honoured elsewhere. The bug report is explicit that the timeout "merely times out each source
    rather than preventing the hang entirely".

    **The deadlock is per-process, so killing the process IS the remedy** - the retry gets a fresh
    apt with an empty queue. This pins that no consumer is left to rely on apt bounding itself.
    """
    naked = [
        (job, step.get("name", "<unnamed>"))
        for job, steps in _jobs().items()
        for step in steps
        if any(marker in _run_of(step) for marker in _CONSUMERS)
        and _DROP_IN not in _run_of(step)
        and _BOUNDED not in _run_of(step)
    ]

    assert not naked, (
        "apt consumers running unbounded:\n"
        + "\n".join(f"    {job}: {name}" for job, name in naked)
        + "\n\nWrap them in `scripts/ci_bounded.sh <seconds>`. apt cannot be trusted to bound "
        "itself on noble - LP#2003851 is unfixed there. `(aee)`."
    )


def test_the_bound_retries_a_hang_and_refuses_to_retry_a_real_failure() -> None:
    """The script's two behaviours, and the second is the one that keeps it honest.

    A timeout is retried once, because the deadlock is per-process and a fresh one usually
    succeeds. **Any other exit status is NOT retried** - a package that does not exist will not
    exist on the second attempt either, and retrying real failures is how a wrapper turns a broken
    build into a slow one.

    ⚠ Its first draft reported every timeout as *"exit 0, not a timeout"*: `if cmd; then ...; fi`
    with no `else` leaves `$?` at ZERO when `cmd` fails, because the `if` itself succeeded. Caught
    by running it, not by reading it.
    """
    script = Path(__file__).resolve().parents[3] / "scripts" / "ci_bounded.sh"
    assert script.is_file(), "the bound script is gone but the workflow still calls it"

    quick = subprocess.run([str(script), "10", "true"], capture_output=True, text=True, check=False)
    assert quick.returncode == 0, "a command well inside the bound must pass untouched"

    real = subprocess.run([str(script), "10", "false"], capture_output=True, text=True, check=False)
    assert real.returncode == 1, f"a real failure must surface its own status: {real.returncode}"
    assert "not retrying" in real.stderr.lower(), (
        f"a real failure was retried, or said nothing about it: {real.stderr!r}"
    )

    hung = subprocess.run(
        [str(script), "1", "sleep", "20"], capture_output=True, text=True, check=False
    )
    assert hung.returncode == 124, f"a killed command must report the timeout: {hung.returncode}"
    assert "TIMED OUT" in hung.stderr, "the swallowed timeout was not reported"
    assert "retry" in hung.stderr.lower(), "nothing said the command was retried"
