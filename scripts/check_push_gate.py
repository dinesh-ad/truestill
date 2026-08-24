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

⚠ **THE TRANSPORT IS PART OF THE GATE, AND IT WAS SILENTLY MISSING FOR A DAY (P33).** From
`a173c42` to `1d5a...`'s fix, this file was correct and INERT: pre-commit's `hook-impl` consumes
git's pre-push stdin and forwards **nothing** - observed 2026-08-23 with a probe hook printing
``stdin:[]`` - so the gate saw no refs, exited 0 through the not-gated branch, and pre-commit
suppressed the warning under ``Passed``. Two pushes were "allowed" that were never judged, one of
them onto a RED tip. What pre-commit sets instead, **observed rather than read off its docs**:
``PRE_COMMIT_FROM_REF`` = the sha of the REMOTE tip being pushed onto, ``PRE_COMMIT_TO_REF`` =
the local sha, ``PRE_COMMIT_REMOTE_BRANCH`` = the ref name. And for a brand-new branch (zero
remote sha) `hook-impl` runs **no pre-push hooks at all**, so the env transport never carries a
new-branch push - the zero-sha filtering below serves direct git installs only. The stdin
protocol stays first because it is githooks(5) truth and carries multi-ref pushes; the env is
the fallback for the one harness that actually runs this file.

⚠ **A MESSAGE THAT MATTERS MUST RIDE A NON-ZERO EXIT.** pre-commit shows a passing hook's name
and ``Passed`` and swallows everything it printed. That suppression has now cost twice - the
override's report in `(agn)`, and this gate's own "NOT gated" confession above - so the
no-subject case FAILS CLOSED: unknown is not green, and a warning nobody can see is not a
warning. `.pre-commit-config.yaml` carries the same constraint where the hooks are defined.

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
import time
from pathlib import Path
from typing import Final

#: Waives the OUTCOME check only - a red or unknown tip - because that is the one thing it was
#: ever for: pushing the fix onto the red it fixes. ⚠ **It does NOT waive contention** (P38):
#: its first exercise cancelled a live run, and red and contention are unrelated conditions - a
#: red tip is a run that CONCLUDED, so waiving it must never imply killing one in flight. An
#: environment variable rather than a flag because a hook receives git's arguments, not yours.
OVERRIDE = "TRUESTILL_PUSH_ANYWAY"

#: The contention escape, with its own name because it is its own decision: "I mean to cancel
#: the run in flight." One variable meaning two things is the two-places-disagree shape in a
#: single symbol, which is how the first exercise cancelled 95e357c's run.
CANCEL_OVERRIDE = "TRUESTILL_PUSH_CANCELS_THE_RUN"

#: Contention WAITS, bounded, instead of refusing outright - re-ruled in P38 against P33's
#: refusal. P33 cited the reasoning behind `IMPLEMENTATION_STANDARDS.md` §6.1: a blocking hook
#: gets `--no-verify`d by a human who can simply try again. The agent now pushes for itself, so
#: a refusal costs a full round trip while a bounded wait costs minutes of hook time - the
#: economics reversed with the operator. A push lane measures ~3 minutes (`CLAUDE.md`); the
#: bound is double that plus slack. **At the bound it REFUSES** - never pushes, never cancels -
#: naming how long it waited, because an unbounded wait is a hang and a hang gets uninstalled.
CONTENTION_WAIT_SECONDS: Final = 480.0
CONTENTION_POLL_SECONDS: Final = 15.0

#: `githooks(5)`: an all-zero sha means the ref does not exist on that side. As the REMOTE sha it
#: is a brand-new branch - no tip, nothing to have failed. As the LOCAL sha it is a deletion.
ZERO_SHA: Final = "0" * 40

#: When set to a writable path, every subject resolution and verdict is appended there - an
#: observability seam for the installed-chain tests and for watching a real push, never a
#: behaviour switch. Failures to write are swallowed: observation must not change the verdict.
PROBE = "TRUESTILL_PUSH_GATE_PROBE"

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


def _probe(note: str) -> None:
    target = os.environ.get(PROBE)
    if not target:
        return
    try:
        with Path(target).open("a", encoding="utf-8") as fh:
            fh.write(note + "\n")
    except OSError:
        pass


def subject(raw: str) -> tuple[str, list[tuple[str, str, str]]]:
    """``(transport, refs)`` - stdin when git speaks directly, pre-commit's env when it does not.

    The env triple is trusted only whole: a FROM without a TO is a mis-invocation, not a subject.
    ``PRE_COMMIT_REMOTE_BRANCH`` defaults to nothing - if pre-commit ever stops setting it, the
    push is unidentifiable and the no-subject refusal in ``main`` says so, rather than this
    function guessing ``main``.
    """
    refs = pushed_refs(raw)
    if refs:
        return "stdin", refs
    from_ref = os.environ.get("PRE_COMMIT_FROM_REF")
    to_ref = os.environ.get("PRE_COMMIT_TO_REF")
    branch = os.environ.get("PRE_COMMIT_REMOTE_BRANCH")
    if from_ref and to_ref and branch:
        return "pre-commit-env", [(branch, to_ref, from_ref)]
    return "none", []


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


def _live_push_run(branch: str) -> dict[str, object] | None:
    """The in-flight push run on ``branch``, or ``None`` (also on cannot-ask).

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
        if runs:
            return runs[0]
    return None


def contention(branch: str) -> str | None:
    """A refusal if a push run is in flight on ``branch`` and stays in flight past the bound.

    ⚠ **Waits before refusing** (P38, the re-ruling recorded at `CONTENTION_WAIT_SECONDS`): the
    ordinary case is a run minutes from concluding, and with the agent as the operator a refusal
    costs a round trip the wait does not. At the bound it refuses - never cancels.
    """
    run = _live_push_run(branch)
    if run is None:
        return None
    deadline = time.monotonic() + CONTENTION_WAIT_SECONDS
    print(
        f"push gate: a CI run for {branch} is in flight (run {run.get('databaseId')}, "
        f"{str(run.get('headSha', ''))[:7]}); waiting up to {CONTENTION_WAIT_SECONDS:.0f}s for it "
        f"rather than cancelling it.",
        file=sys.stderr,
    )
    while time.monotonic() < deadline:
        time.sleep(CONTENTION_POLL_SECONDS)
        run = _live_push_run(branch)
        if run is None:
            return None
    return (
        f"\npush gate: a CI run for {branch} was still live after "
        f"{CONTENTION_WAIT_SECONDS:.0f}s (run {run.get('databaseId')}, "
        f"{str(run.get('headSha', ''))[:7]}), and pushing now CANCELS it "
        f"(`cancel-in-progress: true`). {OVERRIDE} does NOT waive this - a red tip is a run "
        f"that concluded, not one in flight. If you mean to cancel it:  "
        f"{CANCEL_OVERRIDE}=1 git push\n"
        f"    {run.get('url')}\n{_advice()}"
    )


def outcome(sha: str) -> str | None:
    """A refusal if the run for ``sha`` is not green, else ``None``.

    **Sha-keyed, server-side.** ``--commit`` asks GitHub about this one commit, so no listing
    window can hide it and no newer run for another sha can answer in its place.
    """
    # ``--event push``: the sixty-ninth member applied to this check's own sibling while P38
    # split the override. Without it, ``--commit`` on a main tip can answer with the NIGHTLY
    # run of the same sha - different coverage, judged in the push lanes' place.
    runs = _gh(
        "run", "list", "--commit", sha, "--event", "push", "--limit", "10", "--json", _FIELDS
    )
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


def judgeable(refs: list[tuple[str, str, str]]) -> list[tuple[str, str]]:
    """``(branch, remote_sha)`` for each ref that HAS a tip to judge.

    A deletion (all-zero local sha) and a branch the remote does not have yet (all-zero remote
    sha) are filtered out here rather than inside the checks, so a push made entirely of those
    asks GitHub nothing at all - there is no question to have an answer.
    """
    return [
        (remote_ref.removeprefix("refs/heads/"), remote_sha)
        for remote_ref, local_sha, remote_sha in refs
        if ZERO_SHA not in (local_sha, remote_sha)
    ]


def refusals(refs: list[tuple[str, str, str]]) -> list[str]:
    """Everything wrong with this push, or an empty list. ``None`` from a check means *not asked*.

    ⚠ **The two overrides waive different checks and say so** (P38). `TRUESTILL_PUSH_ANYWAY`
    waives OUTCOME only - contention was still checked, and the audit line says exactly that,
    because "nothing was verified" would overstate what was skipped. `TRUESTILL_PUSH_CANCELS_THE_RUN`
    waives CONTENTION only, named for what it does.
    """
    waive_outcome = bool(os.environ.get(OVERRIDE))
    cancel_run = bool(os.environ.get(CANCEL_OVERRIDE))
    problems: list[str] = []
    for branch, remote_sha in judgeable(refs):
        if cancel_run:
            live = _live_push_run(branch)
            if live is not None:
                print(
                    f"push gate: {CANCEL_OVERRIDE} set - the live run "
                    f"{live.get('databaseId')} on {branch} will be CANCELLED by this push. "
                    f"Contention was waived; outcome is still checked below.",
                    file=sys.stderr,
                )
            contended = None
        else:
            contended = contention(branch)
        judged = outcome(remote_sha)
        if judged is not None and waive_outcome:
            print(
                f"push gate: OVERRIDDEN by {OVERRIDE} - the OUTCOME of tip {remote_sha[:7]} "
                f"was waived (its run is red or unknown). Contention WAS still checked; only "
                f"the outcome went unverified.",
                file=sys.stderr,
            )
            judged = None
        found = [m for m in (contended, judged) if m is not None]
        _probe(
            f"judged branch={branch} tip={remote_sha[:7]} refusals={len(found)}"
            f" waive_outcome={waive_outcome} cancel_run={cancel_run}"
        )
        problems.extend(found)
    return problems


def main() -> int:
    raw = "" if sys.stdin.isatty() else sys.stdin.read()
    transport, refs = subject(raw)
    _probe(f"transport={transport} refs=" + ",".join(f"{r}@{s[:7]}" for r, _l, s in refs))

    # ⚠ No blanket override short-circuit any more (P38): each override waives its ONE check
    # inside `refusals`, so an override push still identifies its subject and still checks
    # everything it did not explicitly waive - which is how the first exercise's cancelled run
    # cannot recur.
    if not refs:
        # ⚠ FAIL CLOSED (P33). This exact condition exited 0 for a day while pre-commit dropped
        # the stdin and suppressed the warning - two pushes went unjudged, one onto a red tip.
        # It cannot be a legitimate first push either: observed 2026-08-23, pre-commit runs no
        # pre-push hooks at all for a new branch, and direct git invocation always has stdin.
        print(
            "push gate: NO SUBJECT. Nothing on stdin and no PRE_COMMIT_FROM_REF/TO_REF/"
            "REMOTE_BRANCH, so the tip being pushed onto cannot be identified - and unknown is "
            "not green. If you are running this by hand, feed it a ref line:\n"
            "    echo 'refs/heads/main <local-sha> refs/heads/main <remote-sha>' | "
            "python3 scripts/check_push_gate.py",
            file=sys.stderr,
        )
        return 1

    if not judgeable(refs):
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

    problems = refusals(refs)
    for message in problems:
        print(message, file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
