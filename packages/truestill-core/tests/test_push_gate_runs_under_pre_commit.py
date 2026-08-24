"""The INSTALLED chain judges: pre-commit `hook-impl` -> the gate, with a real subject. P33.

⚠ **THE DEFECT, and why this file exists**: from `a173c42` (the `(agn)` rewrite) until P33 the
gate was correct and INERT - pre-commit consumes git's pre-push stdin and forwards **nothing**
(observed: a probe hook read ``stdin:[]`` while git had supplied the ref line), so the gate saw
no refs, exited 0, and pre-commit suppressed its "NOT gated" confession under ``Passed``. Two
pushes were "allowed" that were never judged, one onto a RED tip. Every prior test drove the
SCRIPT; none drove the INSTALLATION - a true answer from the unit was not the answer for the
system. These tests drive `pre-commit hook-impl` itself, the exact process `.git/hooks/pre-push`
execs, so the transport can never silently disarm again.

**The gh-independent half runs everywhere**: the probe seam records which transport delivered
which subject, written before GitHub is ever asked. **The verdict half runs where `gh` can
answer** (this machine; CI lanes carry no auth and skip with the reason named) against two
permanent facts of this repo's history: run 32663974549 concluded FAILURE for `57d1652`, and
`6ba3948`'s run concluded SUCCESS.

**The probe branch is deliberately not `main`**: `contention()` is branch-keyed and a live run
on main at test time would flake the green case; a branch that has never had a run keeps the
contention half silently clean while `outcome()` - sha-keyed - judges the real tips.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]

RED_TIP = "57d1652c17843926e1bd4adc808ce107fd6e24c1"  # run 32663974549: failure, forever


def _origin_url() -> str:
    """The real repo's own remote, so no name is hardcoded and a fork tests itself."""
    done = subprocess.run(
        ["git", "-C", str(ROOT), "remote", "get-url", "origin"],
        capture_output=True,
        text=True,
        check=True,
    )
    return done.stdout.strip()


GREEN_TIP = "6ba3948c5c05dbc45b24edee5c14cf21826be2a3"  # its run: success, forever
LOCAL = "72ee2c2649af0cd30caf2ecbe72b047c3195d93e"  # any real, distinct commit


def _gh_can_answer() -> bool:
    try:
        done = subprocess.run(
            ["gh", "run", "list", "--limit", "1", "--json", "databaseId"],
            capture_output=True,
            text=True,
            check=False,
            timeout=20,
            cwd=ROOT,
        )
    except OSError, subprocess.SubprocessError:
        return False
    return done.returncode == 0


needs_gh = pytest.mark.skipif(
    not _gh_can_answer(),
    reason="gh cannot answer here (no auth or no network) - the gate fails open by design "
    "there, so the verdict half of the chain is only judgeable where gh is; the transport "
    "half below runs everywhere",
)


def _chain(tmp_path: Path, remote_sha: str, probe: Path) -> subprocess.CompletedProcess[str]:
    """One `hook-impl` invocation, the process `.git/hooks/pre-push` execs, stdin as git sends it.

    ⚠ **In a throwaway local clone, and that is load-bearing three ways.** `hook-impl` stashes a
    dirty working tree around the hooks: against the real repo that is a stash/restore cycle of
    whatever a developer (or a peer session) has in flight, and two of these tests running under
    xdist would race each other's stashes. The clone's tree is clean by construction - the
    WORKING-TREE gate script is committed into it, both because the committed one is yesterday's
    gate and because an uncommitted copy would itself trigger the stash. Its `origin` URL is
    pointed at GitHub so `gh` resolves the right repo from the clone's cwd.

    The entry string is tied to the committed config by
    `test_the_committed_config_still_names_the_gate`, so this cannot drift onto an orphan.
    """
    repo = tmp_path / "repo"
    subprocess.run(
        ["git", "clone", "-q", "--no-hardlinks", str(ROOT), str(repo)], check=True, text=True
    )
    subprocess.run(
        ["git", "-C", str(repo), "remote", "set-url", "origin", _origin_url()], check=True
    )
    (repo / "scripts" / "check_push_gate.py").write_bytes(
        (ROOT / "scripts" / "check_push_gate.py").read_bytes()
    )
    subprocess.run(["git", "-C", str(repo), "add", "scripts/check_push_gate.py"], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t",
         "commit", "-q", "--no-verify", "--allow-empty", "-m", "probe gate"],
        check=True,
    )  # fmt: skip

    config = tmp_path / "gate-only.yaml"
    config.write_text(
        "repos:\n"
        "  - repo: local\n"
        "    hooks:\n"
        "      - id: push-gate-under-test\n"
        "        name: push gate under test\n"
        f"        entry: '\"{Path(sys.executable).as_posix()}\" scripts/check_push_gate.py'\n"
        "        language: system\n"
        "        pass_filenames: false\n"
        "        always_run: true\n"
        "        stages: [pre-push]\n",
        encoding="utf-8",
    )
    hook_dir = tmp_path / "hooks"
    hook_dir.mkdir(exist_ok=True)
    line = f"refs/heads/p33-chain-probe {LOCAL} refs/heads/p33-chain-probe {remote_sha}\n"
    env = {k: v for k, v in os.environ.items() if k != "TRUESTILL_PUSH_ANYWAY"}
    env["TRUESTILL_PUSH_GATE_PROBE"] = str(probe)
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "pre_commit",
            "hook-impl",
            f"--config={config}",
            "--hook-type=pre-push",
            "--hook-dir",
            str(hook_dir),
            "--",
            "origin",
            _origin_url(),
        ],
        cwd=repo,
        input=line,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_the_transport_delivers_the_remote_tip_to_the_gate(tmp_path: Path) -> None:
    """⚠ **THE HEADLINE - fails against yesterday's gate**, which saw pre-commit's empty stdin
    and judged nothing. The probe is written before GitHub is asked, so this holds with or
    without `gh` - it is the transport under test, not the verdict."""
    probe = tmp_path / "probe.log"

    _chain(tmp_path, RED_TIP, probe)

    recorded = probe.read_text(encoding="utf-8") if probe.exists() else ""
    assert "transport=pre-commit-env" in recorded, (
        f"the gate did not receive its subject from pre-commit's env: {recorded!r}"
    )
    assert RED_TIP[:7] in recorded, "the subject the env carried is not the remote tip"


@needs_gh
def test_a_red_tip_refuses_through_the_installed_chain(tmp_path: Path) -> None:
    """⚠ **The push that should have been refused on 2026-08-23, replayed end-to-end.**"""
    proc = _chain(tmp_path, RED_TIP, tmp_path / "probe.log")

    assert proc.returncode != 0, f"a red tip passed the installed chain:\n{proc.stdout}"
    assert RED_TIP[:7] in proc.stdout + proc.stderr, "the refusal does not name its subject"
    assert "FAILURE" in proc.stdout + proc.stderr


@needs_gh
def test_a_green_tip_passes_through_the_installed_chain(tmp_path: Path) -> None:
    """⚠ **CRY-WOLF HALF.** A rearmed gate that refused green tips too would be uninstalled."""
    proc = _chain(tmp_path, GREEN_TIP, tmp_path / "probe.log")

    assert proc.returncode == 0, f"a green tip was refused:\n{proc.stdout}\n{proc.stderr}"


def test_the_committed_config_still_names_the_gate() -> None:
    """The mini-config above tests the real script only while the real config runs it too."""
    config = (ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8")
    assert "scripts/check_push_gate.py" in config
    assert "stages: [pre-push]" in config
