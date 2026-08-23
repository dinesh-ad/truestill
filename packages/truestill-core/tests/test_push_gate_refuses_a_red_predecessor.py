"""A push onto a red or unfinished predecessor is refused. `ENGINEERING_STANDARD.md` §2.

**The rule had two halves and only one was ever honoured.** §2 says *"a pending result outranks a
ready batch"*, written after three cancelled runs in one session. It carries:

* **CONTENTION** - do not push while a run is in flight, because `cancel-in-progress: true` kills
  it. Measured: 6 of 40 runs ended `cancelled`.
* **OUTCOME** - do not push again until you know the last one **passed**.

Nobody had separated them, so *"I am not cancelling anything"* read as permission. On 2026-08-21
the outcome half broke: a push went red and **two more landed on top of it**, leaving three runs
that could not be read as signals about their own commits.

§4's twenty-seventh member gives two acceptable answers - make it executable, or say plainly it
will be broken. This is the first, so the rule is tested rather than restated.

⚠ **The gate FAILS OPEN**, and these tests pin that as hard as they pin the refusal: a gate that
blocks a push on a fresh clone or with no network gets uninstalled, taking its real coverage with
it. The cry-wolf half of a guard is what keeps the guard.

⚠ **THE DECISION IS TESTED AT THE MODULE THAT MAKES IT, NOT THROUGH PATH STUBS.** The first
version wrote `#!/bin/sh` files named `gh` and `git` onto `PATH`. **Windows does not honour a
shebang**, so `gh` was simply not found, the gate correctly failed open, and six tests went red on
a lane where the product was behaving exactly as designed - `ENGINEERING_STANDARD.md` §4's
thirty-ninth member, a test whose subject is an OS behaviour being a test of that OS. Patching
`_gh` on the module that owns the name is both portable and stronger: it exercises the real
decision code rather than a shell's idea of an executable.

⚠ **AND IT SAVED THE REWRITE, 2026-08-23.** `(agn)` rebuilt exactly the PATH-stub harness this
paragraph warns about - a `#!/usr/bin/env python3` file named `gh` - and would have gone red on
the Windows lane for the recorded reason. The lesson held because it was written down here rather
than remembered.

⚠ **WHAT `(agn)` CHANGED, and the fixture with it.** The gate used to derive one sha from
`git rev-parse @{upstream}` and answer both halves of §2 from it. It now takes the remote tip from
git's own `pre-push` **stdin** protocol, asks about **the branch** for contention and **that
commit** for outcome, and refuses a tip with no run instead of reading absence as success. So the
fixture supplies a ref line rather than a sha, and `_gh` returns parsed rows rather than text.
"""

from __future__ import annotations

import io
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))

import check_push_gate

_SHA = "a" * 40
_OTHER = "c" * 40
_ZEROES = "0" * 40
_REFUSED = 1
_ALLOWED = 0


def _stdin(remote_sha: str, *, local_sha: str = "f" * 40, ref: str = "refs/heads/main") -> str:
    """One line in git's documented `pre-push` format: local ref, local sha, remote ref, remote sha."""
    return f"{ref} {local_sha} {ref} {remote_sha}\n"


@pytest.fixture
def gate(monkeypatch: pytest.MonkeyPatch) -> Any:
    """The real `main`, with only its outward contact replaced: stdin and `_gh`.

    Those two are the whole of the module's contact with the world since `(agn)`, so patching them
    leaves every branch of the decision under test - and neither is a PATH stub, for the reason
    this module's docstring records twice over.
    """
    monkeypatch.setattr(check_push_gate.sys, "stdin", io.StringIO(_stdin(_SHA)))
    monkeypatch.delenv(check_push_gate.OVERRIDE, raising=False)
    return check_push_gate


def _run(sha: str, status: str, conclusion: str | None, *, rid: int = 1) -> dict[str, object]:
    return {
        "databaseId": rid,
        "headSha": sha,
        "headBranch": "main",
        "status": status,
        "conclusion": conclusion,
        "url": f"https://example.invalid/{rid}",
    }


def _table(*runs: dict[str, object]) -> Any:
    """A `_gh` that answers from a table **honouring the flags the gate passes**.

    ⚠ **The filtering is the subject, not scaffolding.** `(agn)`'s whole point is that the gate
    must ask a KEYED question rather than fetch a recent window and sieve it locally, so a fake
    that ignored `--commit` and `--status` would let the old implementation pass every row below.
    """

    def answer(*args: str) -> list[dict[str, object]] | None:
        def opt(name: str) -> str | None:
            return args[args.index(name) + 1] if name in args else None

        rows = list(runs)
        commit = opt("--commit")
        if commit is not None:
            rows = [r for r in rows if r["headSha"] == commit]
        status = opt("--status")
        if status is not None:
            rows = [r for r in rows if r.get("status") == status]
        branch = opt("--branch")
        if branch is not None:
            rows = [r for r in rows if r.get("headBranch") == branch]
        limit = opt("--limit")
        if limit is not None:
            rows = rows[: int(limit)]
        return rows

    return answer


def _answer(status: str, conclusion: str | None, *, sha: str = _SHA) -> Any:
    return _table(_run(sha, status, conclusion))


@pytest.mark.parametrize("conclusion", ["failure", "cancelled", "timed_out", "startup_failure"])
def test_a_red_predecessor_refuses_the_push(
    gate: Any, conclusion: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The OUTCOME half - the one that broke, and the one nothing enforced."""
    monkeypatch.setattr(gate, "_gh", _answer("completed", conclusion))

    assert gate.main() == _REFUSED, f"a {conclusion} predecessor was not refused"
    err = capsys.readouterr().err
    assert conclusion.upper() in err
    assert "TRUESTILL_PUSH_ANYWAY=1" in err, "the refusal does not say how to proceed"


def test_a_run_still_going_refuses_the_push(
    gate: Any, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The CONTENTION half, which was already the written rule: pushing now CANCELS it."""
    monkeypatch.setattr(gate, "_gh", _answer("in_progress", None))

    assert gate.main() == _REFUSED
    assert "CANCELS" in capsys.readouterr().err


def test_a_green_predecessor_is_allowed(
    gate: Any, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """⚠ The cry-wolf half. A gate that refuses ordinary work is the one that gets removed."""
    monkeypatch.setattr(gate, "_gh", _answer("completed", "success"))

    assert gate.main() == _ALLOWED
    assert capsys.readouterr().err == "", "an ordinary push was not silent"


def test_the_override_says_you_mean_it(
    gate: Any, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Pushing a FIX onto a red main is the ordinary case and must stay cheap."""
    monkeypatch.setenv(gate.OVERRIDE, "1")
    monkeypatch.setattr(gate, "_gh", _answer("completed", "failure"))

    assert gate.main() == _ALLOWED
    err = capsys.readouterr().err
    assert "OVERRIDDEN" in err, "a silent override is indistinguishable"
    assert _SHA[:7] in err, "the override does not say what it bypassed"


def test_an_unreachable_gh_fails_open_and_says_so(
    gate: Any, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """⚠ The gap, pinned. A gate nobody can push past on a plane gets uninstalled.

    §4's twenty-second member: a report about state must say what it does not cover, so the
    warning names the gap rather than the push passing silently.
    """
    monkeypatch.setattr(gate, "_gh", lambda *_a: None)

    assert gate.main() == _ALLOWED, "a missing `gh` blocked the push"
    err = capsys.readouterr().err
    assert "UNKNOWN" in err, "the gap was not named"
    assert "NOT gated" in err, "the warning does not say the push was ungated"


def test_unparseable_output_is_the_same_class_as_an_unreachable_gh(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A `gh` that answers with something that is not JSON cannot answer, and `_gh` says so by
    returning ``None``.

    ⚠ **Tested at `_gh` since `(agn)`, because that is where the decision moved.** It used to
    return raw text and the caller parsed; it now returns parsed rows or ``None``, and that
    ``None`` is the entire fail-open signal. Asserting it through `main` would only re-test the
    caller's `if runs is None`, which two other rows already cover.
    """

    class _Done:
        returncode = 0
        stdout = "not json at all"

    monkeypatch.setattr(check_push_gate.subprocess, "run", lambda *_a, **_k: _Done())

    assert check_push_gate._gh("run", "list") is None, "unparseable output was not a non-answer"


def test_a_tip_with_no_run_is_refused_rather_than_assumed_good(
    gate: Any, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """⚠ **THIS ASSERTED THE OPPOSITE UNTIL `(agn)`, and the reason it changed is a measurement.**

    It read *"a docs-only push, or one that has aged out of the listing. Ordinary, so silent."*
    Checked rather than assumed: `ci.yml` has **no `paths` filter** on `push: branches: [main]`,
    so every push to main creates a run, and a tip with no run is not ordinary - it is a question
    the gate could not answer. **Unknown is not green**, which is the `(afl)` shape.

    The other half of the old assertion still holds and is the point of the sha here: another
    commit's failure must not block this push. It does not - what blocks it is that *this* tip has
    nothing.
    """
    monkeypatch.setattr(gate, "_gh", _answer("completed", "failure", sha="b" * 40))

    assert gate.main() == _REFUSED, "a tip with no run at all was treated as passing"
    err = capsys.readouterr().err
    assert "NO CI run exists" in err
    assert _SHA[:7] in err, "the refusal does not name the tip it could not find"


def test_a_brand_new_branch_is_allowed_and_asks_nothing(
    gate: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`githooks(5)` gives an all-zero REMOTE sha for a ref the remote does not have yet.

    Nothing has been pushed, so nothing can be red - and `gh` must not even be consulted.
    ⚠ **Without this, Q72's fail-closed rule would refuse every first push forever**: no tip, no
    run, therefore "unknown". Two correct rules meeting to make a trap.
    """
    monkeypatch.setattr(check_push_gate.sys, "stdin", io.StringIO(_stdin(_ZEROES)))

    def unreachable(*_a: str) -> list[dict[str, object]] | None:  # pragma: no cover
        message = "gh was consulted for a branch the remote does not have"
        raise AssertionError(message)

    monkeypatch.setattr(gate, "_gh", unreachable)
    assert gate.main() == _ALLOWED


def test_deleting_a_branch_is_allowed(gate: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """The mirror: an all-zero LOCAL sha is a deletion, and nothing is being built."""
    monkeypatch.setattr(check_push_gate.sys, "stdin", io.StringIO(_stdin(_SHA, local_sha=_ZEROES)))
    monkeypatch.setattr(gate, "_gh", _answer("completed", "failure"))

    assert gate.main() == _ALLOWED


def test_the_script_runs_as_a_hook_does() -> None:
    """One end-to-end invocation, because every test above patches the module.

    The override path needs no network and no `gh`, so it proves the file is executable, parses,
    and returns a code git will read - which patching can never show.

    ⚠ **The inherited environment, not a minimal one.** Handing Windows an empty `PATH` and
    `SYSTEMROOT` is the same POSIX assumption that made the first version of this file fail there;
    the override short-circuits before any subprocess call, so the environment need not be
    stripped to make the test honest.
    """
    result = subprocess.run(
        [sys.executable, str(Path(check_push_gate.__file__))],
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, check_push_gate.OVERRIDE: "1"},
    )

    assert result.returncode == _ALLOWED
    assert "OVERRIDDEN" in result.stderr


# --- (agn): the two halves have different keys -------------------------------------------------


def test_a_red_tip_is_refused_when_its_run_has_aged_out_of_any_recent_window(
    gate: Any, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """⚠ **THE DEFECT `(agn)` FIXED, and the refusal alone does not prove it.**

    The old gate fetched the fifteen most recent runs and sieved them locally, so a tip whose run
    had aged out read as *no evidence of a failure*. Twenty newer runs is an afternoon.

    ⚠ **The discriminating assertion is the stated REASON**, found by a surviving mutation. With
    a window the tip's run is not in the fetched page, so the gate reports *"NO CI run exists"* -
    and Q72's fail-closed rule refuses on that, meaning **both** implementations refuse. The keyed
    query is not load-bearing for the refusal; it is load-bearing for the refusal being **true**.
    A person sent to look for a missing run when the truth is a red one has been told the wrong
    thing by a gate that happened to land on the right verdict.
    """
    aged_out = [_run(f"{i:040x}", "completed", "success", rid=100 + i) for i in range(20)]
    monkeypatch.setattr(gate, "_gh", _table(*aged_out, _run(_SHA, "completed", "failure", rid=8)))

    assert gate.main() == _REFUSED, "a red tip was invisible behind newer runs"
    err = capsys.readouterr().err
    assert "FAILURE" in err, f"the gate refused for a reason that is not what happened: {err!r}"
    assert "NO CI run exists" not in err


def test_a_run_in_flight_for_another_sha_on_the_branch_is_refused(
    gate: Any, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The CONTENTION half, and its key is the **branch** - which is why the old gate missed it.

    `ci.yml`'s concurrency group is `ci-${{ github.ref }}-${{ github.event_name }}` with
    `cancel-in-progress: true`, so this push cancels **any** live push run on the ref, whatever
    commit it is for. A question about one sha could never see somebody else's run.
    """
    monkeypatch.setattr(
        gate,
        "_gh",
        _table(_run(_OTHER, "in_progress", None, rid=9), _run(_SHA, "completed", "success", rid=8)),
    )

    assert gate.main() == _REFUSED, "a push that would cancel a run in flight was allowed"
    err = capsys.readouterr().err
    assert "CANCELS" in err
    assert "9" in err, "the refusal does not name the run it would kill"


def test_a_nightly_run_in_flight_does_not_block_a_push(
    gate: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """⚠ **CRY-WOLF HALF for the contention key.** `ci.yml` puts `github.event_name` in the
    concurrency group precisely so a push does **not** cancel the nightly, and its own comment
    says why: *"the one thing the nightly exists to run is the one thing no other trigger runs"*.
    So refusing a push because a scheduled run is live would be a false alarm - `--event push` is
    part of the key, and this proves the fake is asked with it.
    """
    seen: list[tuple[str, ...]] = []

    def answer(*args: str) -> list[dict[str, object]] | None:
        seen.append(args)
        if "--status" in args:
            return []  # no PUSH run is live; the nightly is a different event and unasked for
        return [_run(_SHA, "completed", "success")]

    monkeypatch.setattr(gate, "_gh", answer)

    assert gate.main() == _ALLOWED
    assert any("--event" in args and "push" in args for args in seen), (
        "contention was not asked about push runs specifically, so the nightly could block a push"
    )


def test_it_says_so_when_it_is_not_invoked_as_a_pre_push_hook(
    gate: Any, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Run by hand there is no ref on stdin, and inventing one is how this defect started.

    Falling back to `@{upstream}` would silently reintroduce the stale-cache bug `(agn)` is about,
    so the gate says it judged nothing instead.
    """
    monkeypatch.setattr(check_push_gate.sys, "stdin", io.StringIO(""))
    monkeypatch.setattr(gate, "_gh", _answer("completed", "failure"))

    assert gate.main() == _ALLOWED
    assert "NOT gated" in capsys.readouterr().err
