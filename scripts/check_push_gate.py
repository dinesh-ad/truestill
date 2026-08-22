#!/usr/bin/env python3
"""Refuse a push while the previous one's CI is red or still running.

**The rule this makes executable, and the distinction that made it fail.**
`ENGINEERING_STANDARD.md` §2 rules that *"a pending result outranks a ready batch"*, written after
three cancelled runs in one session. That sentence carries **two** obligations and only the first
was ever honoured:

* **CONTENTION** - do not push while a run is in flight, because `cancel-in-progress: true` kills
  it. Measured: 6 of 40 runs ended `cancelled`, 15% that verified nothing.
* **OUTCOME** - do not push again until you know the last one **passed**. Nobody had separated
  these, so "I am not cancelling anything" read as permission.

On 2026-08-21 the second half broke: a push went red, two more landed on top of it, and three runs
became unreadable as signals about their own commits. §4's twenty-seventh member rules that a rule
depending on somebody remembering is not a control, and that the acceptable answers are to make it
executable or to say plainly that it will be broken. This is the first.

**It refuses; it never waits.** A hook that blocked for eleven minutes would be bypassed with
`--no-verify` the first afternoon, which is worse than an honest refusal - the same reasoning
§6.1 records for not making `make gate` a blocking hook.

**The override is explicit and is the point.** `TRUESTILL_PUSH_ANYWAY=1 git push` is how you say
*I know, and I mean it* - pushing a fix onto a red main is the ordinary case and must stay cheap.
What the gate removes is pushing onto red **without noticing**, which is the only failure it saw.

⚠ **IT FAILS OPEN AND SAYS SO.** Without `gh`, without auth, or with the API unreachable, it
cannot see the subject and allows the push with a warning - because a gate that blocks every push
on a plane or a fresh clone gets uninstalled, taking its real coverage with it. §4's twenty-second
member: a report about state must say what it does not cover, so the warning names the gap rather
than passing silently.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

#: Set to anything non-empty to push regardless. Deliberately not a `--force`-style flag: a hook
#: receives git's arguments, not yours, so an environment variable is the only channel a person
#: can actually reach.
OVERRIDE = "TRUESTILL_PUSH_ANYWAY"

#: Run conclusions that mean the last push is not known to be good. `None` is an unfinished run -
#: the contention half - and the rest are the outcome half.
_BAD = frozenset({"failure", "cancelled", "timed_out", "startup_failure", "action_required"})

_ADVICE = (
    f"    Read it:  gh run view --log-failed\n    Push anyway (you mean it):  {OVERRIDE}=1 git push"
)


def _gh(*args: str) -> str | None:
    """Run `gh` and return stdout, or ``None`` when it cannot answer at all."""
    try:
        result = subprocess.run(
            ["gh", *args], capture_output=True, text=True, check=False, timeout=20
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout if result.returncode == 0 else None


def _upstream_sha() -> str | None:
    """The commit the remote already has - the one whose run we are asking about.

    `@{upstream}` rather than `origin/main`: on a branch the question is about what THIS branch
    last pushed. A branch with no upstream has nothing to have failed.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "@{upstream}"],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout.strip() or None if result.returncode == 0 else None


def _run_for(sha: str) -> dict[str, str] | None:
    """The CI run for ``sha``, or ``None`` when there is nothing to gate on.

    ``None`` deliberately covers three different situations, because they all mean the same thing
    here - *no evidence of a failure* - and none of them is a reason to block someone's push:
    `gh` unreachable or unauthenticated, output that will not parse, and a commit with no run at
    all (a docs-only push, or one that has aged out of the listing). The first two say so out
    loud; a missing run is silent because it is ordinary.
    """
    listing = _gh("run", "list", "--limit", "15", "--json", "databaseId,headSha,status,conclusion")
    if listing is None:
        print(
            "push gate: could not reach `gh`, so the previous run's result is UNKNOWN and this "
            "push is NOT gated. Check it yourself.",
            file=sys.stderr,
        )
        return None
    try:
        runs = [r for r in json.loads(listing) if r.get("headSha") == sha]
    except json.JSONDecodeError:
        print("push gate: `gh` returned something unreadable; NOT gated.", file=sys.stderr)
        return None
    return runs[0] if runs else None


def main() -> int:
    if os.environ.get(OVERRIDE):
        print(f"push gate: overridden by {OVERRIDE}.", file=sys.stderr)
        return 0

    sha = _upstream_sha()
    if sha is None:
        return 0  # nothing pushed yet on this branch, so nothing can be red

    run = _run_for(sha)
    if run is None:
        return 0  # unknown, unreadable, or no run for that commit - see `_run_for`
    if run.get("status") != "completed":
        print(
            f"\npush gate: the run for {sha[:7]} is still {run.get('status')}, and pushing now "
            f"CANCELS it (`cancel-in-progress: true`).\n{_ADVICE}",
            file=sys.stderr,
        )
        return 1

    conclusion = run.get("conclusion")
    if conclusion in _BAD:
        print(
            f"\npush gate: the last push ({sha[:7]}) is {conclusion.upper()}. Pushing on top of it "
            f"makes the next run unreadable as a signal about its own commit.\n{_ADVICE}",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
