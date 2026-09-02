"""`normalize_dashes.py --check` refuses a tracked file it could not read, rather than skipping it.

It read every tracked file in scope and, on a decode or read error, ``continue``d - so a file it
never checked counted towards *"dash style: clean"*. Found 2026-09-02 (P189) as the substitution
shape in a Python loop: "could not read" and "nothing to fix" were the same silence.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "normalize_dashes.py"


def _repo(tmp_path: Path, *, with_unreadable: bool) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    for args in (
        ("init", "-q"),
        ("config", "user.email", "t@example.invalid"),
        ("config", "user.name", "t"),
    ):
        subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)
    (repo / "ok.md").write_text("plain prose - with a spaced dash\n", encoding="utf-8")
    if with_unreadable:
        (repo / "bad.md").write_bytes(b"\xff\xfe not utf-8 \xc3\x28\n")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    return repo


def _sweep(repo: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(_SCRIPT), "--check"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )


def test_an_unreadable_tracked_file_is_refused(tmp_path: Path) -> None:
    done = _sweep(_repo(tmp_path, with_unreadable=True))
    assert done.returncode == 2, done.stdout + done.stderr
    assert "could not read bad.md" in done.stdout
    assert "dash style: clean" not in done.stdout


def test_a_readable_tree_is_still_clean(tmp_path: Path) -> None:
    done = _sweep(_repo(tmp_path, with_unreadable=False))
    assert done.returncode == 0, done.stdout + done.stderr
    assert "dash style: clean" in done.stdout
