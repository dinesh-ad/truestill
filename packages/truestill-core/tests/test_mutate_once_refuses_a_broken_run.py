"""The mutation harness must not report a kill for a run that never ran a test.

**This is the instrument, not the subject, and that is why it matters more than any one guard.**
`ENGINEERING_STANDARD.md` §4's fifty-third member already rules that a mutation proof needs a
control, *"because 'it failed' and 'it failed for the reason I think' are different claims"*, and
its own addendum says the control must **visibly have run tests**. Both were written after false
proofs. Both were prose.

On 2026-08-21 the same trap fired a **third** time, in one session: ``pytest $TARGETS`` with two
paths in an unquoted variable. zsh does not word-split an unquoted parameter, so pytest received
one path that does not exist, exited **4**, and `mutate_once.py` - whose verdict was
``returncode != 0`` - printed ``mutation caught``. Three proofs were void and the only tell was
``no tests ran`` in output nobody read.

A harness that can report a kill without running a test is an instrument that agrees with the
outcome without measuring it - §4's fifty-fourth member, aimed at the tool this repo uses to
check everything else. So the rule stopped being a paragraph and became the script's own job:
the control runs first, always, with no flag to skip it, and a run that collected nothing is
refused rather than counted either way.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "mutate_once.py"

#: `mutate_once` exits 0 for a caught mutation, 1 for a survivor and 2 for a refusal.
_REFUSED = 2


def _harness(tmp_path: Path, *command: str) -> subprocess.CompletedProcess[str]:
    """Drive the real script against a real file, so nothing here is a stand-in for it."""
    target = tmp_path / "subject.py"
    target.write_text("VALUE = 1\n", encoding="utf-8")
    (tmp_path / "old.txt").write_text("VALUE = 1", encoding="utf-8")
    (tmp_path / "new.txt").write_text("VALUE = 2", encoding="utf-8")
    return subprocess.run(
        [
            sys.executable,
            str(_SCRIPT),
            "--file",
            str(target),
            "--old-file",
            str(tmp_path / "old.txt"),
            "--new-file",
            str(tmp_path / "new.txt"),
            "--",
            *command,
        ],
        capture_output=True,
        text=True,
        check=False,
    )


def test_a_command_that_runs_no_tests_is_refused_not_reported_as_a_kill(tmp_path: Path) -> None:
    """⚠ The exact shape of the three void proofs: pytest given a path that does not exist.

    It exits 4, which is non-zero, which the old verdict read as the guard biting.
    """
    result = _harness(tmp_path, sys.executable, "-m", "pytest", "-q", "no/such/path.py")

    assert result.returncode == _REFUSED, (
        f"a run that collected nothing was not refused (exit {result.returncode}). "
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert "mutation caught" not in result.stdout, "a broken invocation was reported as a kill"
    assert "THE CONTROL FAILED" in result.stderr


def test_the_refusal_names_the_word_splitting_cause(tmp_path: Path) -> None:
    """A refusal nobody can act on sends the reader back to the same mistake.

    §4's twenty-seventh member: a rule that depends on remembering is not a control - so the
    script says what went wrong and what to do instead, at the moment it happens.
    """
    result = _harness(tmp_path, sys.executable, "-m", "pytest", "-q", "no/such/path.py")

    assert "word-split" in result.stderr
    assert "quote it or pass the paths literally" in result.stderr


def test_a_control_that_passes_lets_the_proof_proceed_and_prints_its_count(
    tmp_path: Path,
) -> None:
    """⚠ The cry-wolf half. A harness that refuses everything is worse than one that refuses
    nothing, because it stops being used - and the count is what §4's addendum requires be
    VISIBLE rather than merely true."""
    suite = tmp_path / "test_subject_suite.py"
    suite.write_text(
        "import subject\n\n\ndef test_value() -> None:\n    assert subject.VALUE == 1\n",
        encoding="utf-8",
    )
    result = _harness(
        tmp_path, sys.executable, "-m", "pytest", "-q", "-p", "no:randomly", str(suite)
    )

    assert "control OK" in result.stdout, f"the control was not reported: {result.stdout}"
    assert "1 passed" in result.stdout, "the control did not print a passing COUNT"
    assert result.returncode == 0, "a real mutation of a real guard was not reported as caught"
    assert "mutation caught" in result.stdout
