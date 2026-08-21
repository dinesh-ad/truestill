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
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "check_push_gate.py"
_SHA = "a" * 40

_REFUSED = 1
_ALLOWED = 0


def _gate(
    tmp_path: Path, *, gh_stdout: str | None, gh_exit: int = 0, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    """Run the real script with `gh` and `git` replaced by stubs on PATH.

    Stubbed rather than mocked because the script shells out: patching a Python name would leave
    the subprocess untouched, which is §4's guard rule 3 in its subprocess form.
    """
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    git = bin_dir / "git"
    git.write_text(f'#!/bin/sh\necho "{_SHA}"\n', encoding="utf-8")
    git.chmod(0o755)
    gh = bin_dir / "gh"
    if gh_stdout is None:
        gh.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
    else:
        gh.write_text(
            f"#!/bin/sh\ncat <<'EOF'\n{gh_stdout}\nEOF\nexit {gh_exit}\n", encoding="utf-8"
        )
    gh.chmod(0o755)
    return subprocess.run(
        [sys.executable, str(_SCRIPT)],
        capture_output=True,
        text=True,
        check=False,
        env={"PATH": f"{bin_dir}:/usr/bin:/bin", **(env or {})},
    )


def _runs(status: str, conclusion: str | None) -> str:
    return json.dumps(
        [{"databaseId": 1, "headSha": _SHA, "status": status, "conclusion": conclusion}]
    )


@pytest.mark.parametrize("conclusion", ["failure", "cancelled", "timed_out", "startup_failure"])
def test_a_red_predecessor_refuses_the_push(tmp_path: Path, conclusion: str) -> None:
    """The OUTCOME half - the one that broke, and the one nothing enforced."""
    result = _gate(tmp_path, gh_stdout=_runs("completed", conclusion))

    assert result.returncode == _REFUSED, f"a {conclusion} predecessor was not refused"
    assert conclusion.upper() in result.stderr
    assert "TRUESTILL_PUSH_ANYWAY=1" in result.stderr, "the refusal does not say how to proceed"


def test_a_run_still_going_refuses_the_push(tmp_path: Path) -> None:
    """The CONTENTION half, which was already the written rule: pushing now CANCELS it."""
    result = _gate(tmp_path, gh_stdout=_runs("in_progress", None))

    assert result.returncode == _REFUSED
    assert "CANCELS" in result.stderr


def test_a_green_predecessor_is_allowed(tmp_path: Path) -> None:
    """⚠ The cry-wolf half. A gate that refuses ordinary work is the one that gets removed."""
    result = _gate(tmp_path, gh_stdout=_runs("completed", "success"))

    assert result.returncode == _ALLOWED, f"an ordinary push was blocked: {result.stderr}"
    assert result.stderr == ""


def test_the_override_says_you_mean_it(tmp_path: Path) -> None:
    """Pushing a FIX onto a red main is the ordinary case and must stay cheap."""
    result = _gate(
        tmp_path, gh_stdout=_runs("completed", "failure"), env={"TRUESTILL_PUSH_ANYWAY": "1"}
    )

    assert result.returncode == _ALLOWED
    assert "overridden" in result.stderr, "an override that says nothing is indistinguishable"


def test_an_unreachable_gh_fails_open_and_says_so(tmp_path: Path) -> None:
    """⚠ The gap, pinned. A gate nobody can push past on a plane gets uninstalled.

    §4's twenty-second member: a report about state must say what it does not cover, so the
    warning names the gap rather than the push passing silently.
    """
    result = _gate(tmp_path, gh_stdout=None)

    assert result.returncode == _ALLOWED, "a missing `gh` blocked the push"
    assert "UNKNOWN" in result.stderr, "the gap was not named"
    assert "NOT gated" in result.stderr, "the warning does not say the push was ungated"


def test_a_commit_with_no_run_is_not_treated_as_a_failure(tmp_path: Path) -> None:
    """A docs-only push, or one that has aged out of the listing. Ordinary, so silent."""
    result = _gate(
        tmp_path,
        gh_stdout=json.dumps(
            [{"databaseId": 2, "headSha": "b" * 40, "status": "completed", "conclusion": "failure"}]
        ),
    )

    assert result.returncode == _ALLOWED, "another commit's failure blocked this push"
    assert result.stderr == ""
