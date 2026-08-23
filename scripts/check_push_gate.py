#!/usr/bin/env python3
"""Refuse a push while a run is in flight on the branch, or the tip being pushed onto is red.

**The rule this makes executable, and the distinction that made it fail twice.**
`ENGINEERING_STANDARD.md` §2 rules that *"a pending result outranks a ready batch"*, written after
three cancelled runs in one session. That sentence carries **two** obligations:

* **CONTENTION** - do not push while a run is in flight, because `ci.yml` sets
  `cancel-in-progress: true` and the push kills it. Measured: 6 of 40 runs ended `cancelled`.
* **OUTCOME** - do not push onto a tip whose run is red, or the next run stops being a readable
  signal about its own commit.

The first failure was that only contention was honoured. The second, `(agn)`, is that the two were
separated **in prose and conflated in code**:

⚠ **THEY HAVE DIFFERENT KEYS, AND THAT IS THE WHOLE FIX.** Contention is a question about the
**branch** - *any* live push run on the ref dies, whatever commit it is for. Outcome is a question
about **one specific commit** - the tip the remote actually has. The old implementation answered
both from a single sha it derived with ``git rev-parse @{upstream}``, then scanned the fifteen most
recent runs and sieved them locally. Three ways that is wrong:

* ``@{upstream}`` is the **local remote-tracking cache**. Somebody else's push, or simply not
  having fetched, made it ask about a commit the remote no longer had.
* a red tip whose run had aged out of a fifteen-run window read as *no evidence of a failure*.
* a run in flight for a **different** sha on the branch was invisible, and the push cancelled it.

🔑 **git hands the answer over, and the gate did not take it.** `githooks(5)` specifies that
``pre-push`` receives ``<local ref> SP <local sha1> SP <remote ref> SP <remote sha1> LF`` per ref
on **stdin**. The remote tip is a given, not something to infer, and this file previously contained
no reference to stdin at all.

**It refuses; it never waits.** A hook that blocked for eleven minutes would be bypassed with
`--no-verify` the first afternoon, which is worse than an honest refusal - the same reasoning
`IMPLEMENTATION_STANDARDS.md` §6.1 records for not making `make gate` a blocking hook.

⚠ **CANNOT-ASK AND ASKED-AND-NOTHING ARE DIFFERENT, and only the first fails open.** Without `gh`,
without auth, or with the API unreachable, the gate cannot see its subject and says so - because a
gate that blocks every push on a plane or a fresh clone gets uninstalled, taking its real coverage
with it. But a tip with **no run** is not that: `ci.yml` has no `paths` filter on
``push: branches: [main]``, so every push to main creates one. Absent is therefore unknown, and
unknown is not green - the shape `(afl)` keeps finding.

⚠ **EVERY VERDICT NAMES ITS SUBJECT**, including the override. On 2026-08-23 a push passed while
the remote tip was red and the only visible line was this hook's *name* followed by `Passed`: the
override had fired and pre-commit had suppressed its message, so nothing on screen said which
commit had been judged, or that nothing had been. A verdict that does not name its subject cannot
be checked by the person reading it.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from typing import Final

#: Set to anything non-empty to push regardless. Deliberately not a `--force`-style flag: a hook
#: receives git's arguments, not yours, so an environment variable is the only channel a person
#: can actually reach.
OVERRIDE = "TRUESTILL_PUSH_ANYWAY"

#: `githooks(5)`: an all-zero sha means the ref does not exist on that side. As the REMOTE sha it
#: is a brand-new branch - no tip, nothing to have failed. As the LOCAL sha it is a deletion.
ZERO_SHA: Final = "0" * 40

#: The one conclusion that means a tip is known good. Everything else - `cancelled` above all,
#: which verified nothing - is not a reason to build on top of it.
GOOD: Final = "success"

#: Statuses GitHub reports for a run that has not finished. A push cancels these.
LIVE: Final = ("in_progress", "queued", "requested", "waiting")

_FIELDS = "databaseId,headSha,status,conclusion,url"


def _advice() -> str:
    return (
        f"    Read it:  gh run view --log-failed\n"
        f"    Push anyway (you mean it):  {OVERRIDE}=1 git push"
    )


def _gh(*args: str) -> list[dict[str, object]] | None:
    """Ask `gh` for runs, or ``None`` when it cannot answer **at all**.

    ⚠ The distinction this return value carries is the whole of the fail-open rule: ``None`` means
    *the question could not be asked*, and an empty list means *it was asked and the answer is
    nothing*. Collapsing them is how a gate starts treating absence as success.
    """
    try:
        done = subprocess.run(
            ["gh", *args], capture_output=True, text=True, check=False, timeout=20
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if done.returncode != 0:
        return None
    try:
        parsed = json.loads(done.stdout)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, list) else None


def pushed_refs(raw: str) -> list[tuple[str, str, str]]:
    """``(remote_ref, local_sha, remote_sha)`` per ref, from git's pre-push stdin protocol.

    Malformed lines are skipped rather than guessed at: this runs on every push, and a parser that
    invents a ref would gate the wrong thing - which is the defect the whole entry is about.
    """
    refs = []
    for line in raw.splitlines():
        parts = line.split()
        if len(parts) == 4:
            _local_ref, local_sha, remote_ref, remote_sha = parts
            refs.append((remote_ref, local_sha, remote_sha))
    return refs


def contention(branch: str) -> str | None:
    """A refusal if a push run is already in flight on ``branch``, else ``None``.

    **Branch-keyed, and recency is the right lens here** - unlike the outcome half. `ci.yml`'s
    concurrency group is ``ci-${{ github.ref }}-${{ github.event_name }}`` with
    `cancel-in-progress: true`, so this push cancels **any** live push run on the ref regardless of
    which commit it is for. ``--event push`` is part of the key for the same reason the workflow
    puts it in the group: a scheduled run shares the ref and is NOT cancelled by a push, so
    refusing on account of the nightly would be a false alarm.
    """
    for status in LIVE:
        runs = _gh(
            "run", "list", "--branch", branch, "--event", "push",
            "--status", status, "--limit", "5", "--json", _FIELDS,
        )  # fmt: skip
        if runs is None:
            return None  # cannot ask; the caller has already said so
        if runs:
            run = runs[0]
            return (
                f"\npush gate: a CI run for {branch} is still {status} "
                f"(run {run.get('databaseId')}, {str(run.get('headSha', ''))[:7]}), and pushing now "
                f"CANCELS it (`cancel-in-progress: true`).\n"
                f"    {run.get('url')}\n{_advice()}"
            )
    return None


def outcome(sha: str) -> str | None:
    """A refusal if the run for ``sha`` is not green, else ``None``.

    **Sha-keyed, server-side.** ``--commit`` asks GitHub about this one commit, so no listing
    window can hide it and no newer run for another sha can answer in its place.
    """
    runs = _gh("run", "list", "--commit", sha, "--limit", "10", "--json", _FIELDS)
    if runs is None:
        return None  # cannot ask; the caller has already said so
    if not runs:
        return (
            f"\npush gate: NO CI run exists for {sha[:7]}, the commit the remote already has, so "
            f"whether it passed is UNKNOWN - and unknown is not green. Every push to main creates "
            f"a run, so a missing one is a question rather than an ordinary absence.\n{_advice()}"
        )
    run = runs[0]
    if run.get("status") in LIVE:
        return (
            f"\npush gate: the run for {sha[:7]} is still {run.get('status')} "
            f"(run {run.get('databaseId')}), and pushing now CANCELS it.\n"
            f"    {run.get('url')}\n{_advice()}"
        )
    if run.get("conclusion") != GOOD:
        return (
            f"\npush gate: the tip you are pushing onto ({sha[:7]}) is "
            f"{str(run.get('conclusion')).upper()} (run {run.get('databaseId')}). Pushing on top "
            f"of it makes the next run unreadable as a signal about its own commit.\n"
            f"    {run.get('url')}\n{_advice()}"
        )
    return None


def judgeable(raw: str) -> list[tuple[str, str]]:
    """``(branch, remote_sha)`` for each ref that HAS a tip to judge.

    A deletion (all-zero local sha) and a branch the remote does not have yet (all-zero remote
    sha) are filtered out here rather than inside the checks, so a push made entirely of those
    asks GitHub nothing at all - there is no question to have an answer.
    """
    return [
        (remote_ref.removeprefix("refs/heads/"), remote_sha)
        for remote_ref, local_sha, remote_sha in pushed_refs(raw)
        if ZERO_SHA not in (local_sha, remote_sha)
    ]


def refusals(raw: str) -> list[str]:
    """Everything wrong with this push, or an empty list. ``None`` from a check means *not asked*."""
    problems: list[str] = []
    for branch, remote_sha in judgeable(raw):
        problems.extend(m for m in (contention(branch), outcome(remote_sha)) if m is not None)
    return problems


def main() -> int:
    raw = "" if sys.stdin.isatty() else sys.stdin.read()

    if os.environ.get(OVERRIDE):
        tips = ", ".join(sha[:7] for _r, _l, sha in pushed_refs(raw) if sha != ZERO_SHA) or "none"
        print(
            f"push gate: OVERRIDDEN by {OVERRIDE}. The tip(s) this bypassed the check on: {tips}. "
            f"Nothing was verified.",
            file=sys.stderr,
        )
        return 0

    if not pushed_refs(raw):
        print(
            "push gate: no ref on stdin, so this was not invoked as a pre-push hook and this "
            "push is NOT gated. Falling back to the remote-tracking ref would ask about the wrong commit, "
            "which is the defect this gate was rewritten for.",
            file=sys.stderr,
        )
        return 0

    if not judgeable(raw):
        # Only deletions and brand-new branches: nothing has a tip, so nothing is asked and
        # nothing is said. Probing GitHub here would be a question with no subject.
        return 0

    if _gh("run", "list", "--limit", "1", "--json", "databaseId") is None:
        print(
            "push gate: could not reach `gh`, so the tip's result is UNKNOWN and this push is "
            "NOT gated. Check it yourself.",
            file=sys.stderr,
        )
        return 0

    problems = refusals(raw)
    for message in problems:
        print(message, file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
