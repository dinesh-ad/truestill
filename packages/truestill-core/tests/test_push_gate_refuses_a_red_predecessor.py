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
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))

import check_push_gate

_SHA = "a" * 40
_REFUSED = 1
_ALLOWED = 0


@pytest.fixture
def gate(monkeypatch: pytest.MonkeyPatch) -> Any:
    """The real `main`, with only its two outward calls replaced.

    `_upstream_sha` and `_gh` are the whole of the module's contact with the world, so patching
    them leaves every branch of the decision under test.
    """
    monkeypatch.setattr(check_push_gate, "_upstream_sha", lambda: _SHA)
    monkeypatch.delenv(check_push_gate.OVERRIDE, raising=False)
    return check_push_gate


def _answer(status: str, conclusion: str | None, *, sha: str = _SHA) -> str:
    return json.dumps(
        [{"databaseId": 1, "headSha": sha, "status": status, "conclusion": conclusion}]
    )


@pytest.mark.parametrize("conclusion", ["failure", "cancelled", "timed_out", "startup_failure"])
def test_a_red_predecessor_refuses_the_push(
    gate: Any, conclusion: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The OUTCOME half - the one that broke, and the one nothing enforced."""
    monkeypatch.setattr(gate, "_gh", lambda *_a: _answer("completed", conclusion))

    assert gate.main() == _REFUSED, f"a {conclusion} predecessor was not refused"
    err = capsys.readouterr().err
    assert conclusion.upper() in err
    assert "TRUESTILL_PUSH_ANYWAY=1" in err, "the refusal does not say how to proceed"


def test_a_run_still_going_refuses_the_push(
    gate: Any, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The CONTENTION half, which was already the written rule: pushing now CANCELS it."""
    monkeypatch.setattr(gate, "_gh", lambda *_a: _answer("in_progress", None))

    assert gate.main() == _REFUSED
    assert "CANCELS" in capsys.readouterr().err


def test_a_green_predecessor_is_allowed(
    gate: Any, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """⚠ The cry-wolf half. A gate that refuses ordinary work is the one that gets removed."""
    monkeypatch.setattr(gate, "_gh", lambda *_a: _answer("completed", "success"))

    assert gate.main() == _ALLOWED
    assert capsys.readouterr().err == "", "an ordinary push was not silent"


def test_the_override_says_you_mean_it(
    gate: Any, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Pushing a FIX onto a red main is the ordinary case and must stay cheap."""
    monkeypatch.setenv(gate.OVERRIDE, "1")
    monkeypatch.setattr(gate, "_gh", lambda *_a: _answer("completed", "failure"))

    assert gate.main() == _ALLOWED
    assert "overridden" in capsys.readouterr().err, "a silent override is indistinguishable"


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


def test_unreadable_output_fails_open_and_says_so(
    gate: Any, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A `gh` that answers with something that is not JSON is the same class as one that cannot."""
    monkeypatch.setattr(gate, "_gh", lambda *_a: "not json at all")

    assert gate.main() == _ALLOWED
    assert "unreadable" in capsys.readouterr().err


def test_a_commit_with_no_run_is_not_treated_as_a_failure(
    gate: Any, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A docs-only push, or one that has aged out of the listing. Ordinary, so silent."""
    monkeypatch.setattr(gate, "_gh", lambda *_a: _answer("completed", "failure", sha="b" * 40))

    assert gate.main() == _ALLOWED, "another commit's failure blocked this push"
    assert capsys.readouterr().err == ""


def test_a_branch_with_no_upstream_is_allowed(gate: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """Nothing has been pushed, so nothing can be red - and `gh` must not even be consulted."""
    monkeypatch.setattr(gate, "_upstream_sha", lambda: None)

    def unreachable(*_a: str) -> str | None:  # pragma: no cover - proving it is not called
        message = "gh was consulted for a branch with no upstream"
        raise AssertionError(message)

    monkeypatch.setattr(gate, "_gh", unreachable)
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
    assert "overridden" in result.stderr
