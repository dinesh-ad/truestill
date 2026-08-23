"""A green run removes its own scratch root; a red one keeps the evidence. P31.

⚠ **THE DEFECT, measured before this existed**: `tmp_path_retention_policy = "failed"` was set
and did nothing - under pytest-xdist the deletion lives in the `tmp_path` finalizer inside each
WORKER, which never learns its tests' outcomes, so every green `make test` (`-n auto`) kept its
full ~336 MB root. Three retained green runs held ~1 GB of scratch nothing would ever read,
while the setting read as applied. The fix is the controller-side `pytest_sessionfinish` hook
in the root `conftest.py`; this exercises it end-to-end through real subprocess pytest runs,
xdist on, because the worker/controller split IS the defect.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

PASSING = "def test_fine(tmp_path):\n    (tmp_path / 'x').write_text('hi')\n"
FAILING = "def test_broken(tmp_path):\n    (tmp_path / 'x').write_text('hi')\n    assert False\n"


def _run_suite(scratch: Path, test_body: str, where: Path) -> subprocess.CompletedProcess[str]:
    """A real pytest run over one probe test, xdist on, with the hook under test wired in.

    ⚠ Pytest loads conftests along the TEST FILE's path, never the cwd - the first draft ran
    from the repo root and quietly exercised nothing (and wrote to the real ``/tmp``), which
    the cry-wolf half caught. So the probe dir carries its own two-line conftest delegating to
    ``suite_scratch.remove_green_session_root`` - the same wiring the root ``conftest.py``
    uses - and ``TMPDIR`` pins the probe's basetemp under the probe's own scratch.
    """
    where.mkdir()
    # TMPDIR naming a directory that does not exist is silently IGNORED by tempfile (it falls
    # back to /tmp) - the anti-vacuity assert in `_run_roots` caught exactly that on the first
    # green run of this harness.
    scratch.mkdir(parents=True)
    (where / "test_probe.py").write_text(test_body, encoding="utf-8")
    (where / "conftest.py").write_text(
        f"import sys\nsys.path.insert(0, {str(ROOT)!r})\n"
        "from suite_scratch import remove_green_session_root\n\n\n"
        "def pytest_sessionfinish(session, exitstatus):\n"
        "    remove_green_session_root(session, exitstatus)\n",
        encoding="utf-8",
    )
    return subprocess.run(
        [sys.executable, "-m", "pytest", str(where / "test_probe.py"), "-n", "2", "-q"],
        cwd=ROOT,
        # The REAL environment, three keys overridden - never a hand-rolled minimal one. The
        # first draft passed only PATH/HOME/TMPDIR: on Windows that strips SYSTEMROOT, without
        # which Winsock cannot initialize (WinError 10106 at asyncio import - the CI lane
        # caught it), and Windows tempfile consults TEMP/TMP, not TMPDIR, so the probe scratch
        # would have gone unused there anyway. All three spellings point at the probe scratch.
        env={**os.environ, "TMPDIR": str(scratch), "TEMP": str(scratch), "TMP": str(scratch)},
        capture_output=True,
        text=True,
        check=False,
    )


def _run_roots(scratch: Path) -> list[Path]:
    roots = [p for user in scratch.glob("pytest-of-*") for p in user.glob("pytest-*") if p.is_dir()]
    assert scratch.is_dir(), "the probe scratch was never used - this harness is testing nothing"
    return roots


def test_a_green_run_leaves_no_scratch_root_even_under_xdist(tmp_path: Path) -> None:
    """⚠ **THE HEADLINE - fails with the policy alone**, which xdist silently ignores."""
    scratch = tmp_path / "scratch"

    proc = _run_suite(scratch, PASSING, tmp_path / "suite")

    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert _run_roots(scratch) == [], "a green run left its scratch root behind"


def test_a_red_run_keeps_its_scratch_for_the_autopsy(tmp_path: Path) -> None:
    """⚠ **CRY-WOLF HALF.** A hook that tidied failures too would delete the one thing a
    failing run exists to leave behind."""
    scratch = tmp_path / "scratch"

    proc = _run_suite(scratch, FAILING, tmp_path / "suite")

    assert proc.returncode != 0
    roots = _run_roots(scratch)
    assert roots, "the failing run's scratch was deleted - the evidence is gone"
    assert any(p.name.startswith("test_broken") for r in roots for p in r.rglob("test_broken*")), (
        "the kept root does not hold the failing test's directory"
    )
