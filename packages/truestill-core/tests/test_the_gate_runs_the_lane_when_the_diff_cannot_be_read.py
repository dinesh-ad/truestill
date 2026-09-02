"""`make gate` runs the browser lane when it cannot read the diff, rather than skipping it.

The recipe decided with ``touched=$(git diff ...)`` and ``[ -n "$touched" ]``. A command
substitution reports its OUTPUT, so a `git diff` that failed and a diff that was empty were the
same empty string, and the lane was SKIPPED with *"nothing in the diff touches ..."* - the
substitution shape, found 2026-09-02 (P189). The recipe already refused to read an unresolvable
BASE as "nothing changed"; a diff that fails for any other reason is the same question.

The subject is the real recipe: `make -n -o check gate` prints it with its variables expanded,
and it runs here under `sh` in a throwaway repo with `make` shimmed to record the call.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]

pytestmark = pytest.mark.skipif(
    os.name == "nt", reason="the recipe is POSIX sh, driven through make -n and an sh shim"
)


def _recipe() -> str:
    done = subprocess.run(
        ["make", "-n", "-o", "check", "gate", "BASE=HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    # `-n` still EXECUTES a recipe line that mentions `$(MAKE)`, so the script is followed by
    # its own output; the recipe ends at the outermost `fi`.
    lines = done.stdout.split("\n")
    assert "fi" in lines, "make -n did not print the gate recipe; the subject is missing"
    recipe = "\n".join(lines[: lines.index("fi") + 1])
    assert "git diff" in recipe
    return recipe


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    for args in (
        ("init", "-q"),
        ("config", "user.email", "t@example.invalid"),
        ("config", "user.name", "t"),
    ):
        subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)
    (repo / "a.txt").write_text("a\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-q", "-m", "base"], cwd=repo, check=True, capture_output=True)
    return repo


def _env(tmp_path: Path, *, git_diff_fails: bool) -> dict[str, str]:
    """`make` records its call and exits 7, so the lane's status is visible; `git diff` can be
    made to fail while every other git call reaches the real binary."""
    real_git = shutil.which("git")
    assert real_git
    shims = tmp_path / "bin"
    shims.mkdir()
    (shims / "make").write_text('#!/bin/sh\necho "shim make: $*"; exit 7\n', encoding="utf-8")
    if git_diff_fails:
        (shims / "git").write_text(
            # Only the FIRST diff fails; the `--cached` one answers. That is the defect's shape:
            # with `;` between them the substitution carried the second diff's status and the
            # first failure vanished. A shim that fails both would pass the old recipe too.
            f'#!/bin/sh\nif [ "$1" = diff ] && [ "$2" != --cached ]; then '
            f'echo "fatal: shim refuses diff" >&2; exit 128; fi\n'
            f'exec "{real_git}" "$@"\n',
            encoding="utf-8",
        )
    for shim in shims.iterdir():
        shim.chmod(0o755)
    return {**os.environ, "PATH": f"{shims}{os.pathsep}{os.environ['PATH']}"}


def _run(recipe: str, repo: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["sh", "-c", recipe], cwd=repo, env=env, capture_output=True, text=True, check=False
    )


def test_an_unreadable_diff_runs_the_lane_and_carries_its_status(tmp_path: Path) -> None:
    done = _run(_recipe(), _repo(tmp_path), _env(tmp_path, git_diff_fails=True))
    assert "cannot be read" in done.stdout, done.stdout + done.stderr
    assert "shim make: --no-print-directory e2e" in done.stdout, "the lane was not run"
    assert "SKIPPED" not in done.stdout
    assert done.returncode == 7, "the lane's own status must be the recipe's status"


def test_a_readable_empty_diff_still_skips(tmp_path: Path) -> None:
    """The control: with git answering and nothing touched, the lane is skipped and says so."""
    done = _run(_recipe(), _repo(tmp_path), _env(tmp_path, git_diff_fails=False))
    assert done.returncode == 0, done.stdout + done.stderr
    assert "e2e SKIPPED" in done.stdout
    assert "shim make" not in done.stdout
