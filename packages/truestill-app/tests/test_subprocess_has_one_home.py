"""Every external program is launched through one function, so the Windows flag is set once.

**The defect ((aad)).** A windowed Windows build has no console, so **every** ``subprocess``
call pops a black console window. exiftool is batched at 100-200 files per invocation, so
organizing a large library flashes windows repeatedly - not fatal, but constant, and exactly the
kind of thing that makes a paid product look unfinished. ``CREATE_NO_WINDOW`` suppresses it.

**Why a guard rather than five edits.** Five call sites were correct the day they were written;
the sixth is the problem. "Someone adds a `subprocess.run` and forgets the flag" is precisely
how this recurs, and it recurs invisibly on a platform most contributors are not running. A
grep-shaped test turns that into a failing build instead of a bug report six months later.

Parsed with `ast`, not a regex: a comment, a docstring or a string mentioning
``subprocess.run`` must not fail this, and a call spread over several lines must not escape it.
"""

from __future__ import annotations

import ast
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]

#: The one module allowed to call subprocess directly - it *is* the wrapper.
HOME = "packages/truestill-core/src/truestill_core/binaries.py"

#: Names that create a process. ``check_output``/``call``/``check_call`` are included even
#: though nothing uses them today: the rule is about the class, and they take the same flag.
LAUNCHERS = frozenset({"run", "Popen", "call", "check_call", "check_output"})


def _source_files() -> list[Path]:
    out = subprocess.run(
        ["git", "ls-files", "packages/*/src/**/*.py"],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return [REPO / line for line in out.splitlines() if line]


def _direct_launches(path: Path) -> list[str]:
    """``file:line`` for every direct ``subprocess.<launcher>(...)`` call in ``path``."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if (
            isinstance(func, ast.Attribute)
            and func.attr in LAUNCHERS
            and isinstance(func.value, ast.Name)
            and func.value.id == "subprocess"
        ):
            found.append(f"{path.relative_to(REPO)}:{node.lineno}")
    return found


def test_no_module_launches_a_process_except_the_one_that_owns_it() -> None:
    """The gate. A new subprocess call must go through `binaries.run` / `binaries.popen`."""
    offenders: list[str] = []
    for path in _source_files():
        if path.relative_to(REPO).as_posix() == HOME:
            continue
        offenders.extend(_direct_launches(path))

    assert not offenders, (
        "these launch a process without the no-console-window flag; use truestill_core.binaries "
        "instead:\n  " + "\n  ".join(offenders)
    )


def test_the_home_really_does_launch_processes() -> None:
    """Cry-wolf half: if the wrapper stopped calling subprocess, the gate above would pass by
    watching an empty population and every call site would be unprotected."""
    assert _direct_launches(REPO / HOME), "the exempt module no longer launches anything"


def test_every_known_launcher_name_is_covered() -> None:
    """The allowlist is of *modules*, not of function names - so the name list must stay whole.

    Without this, adding ``subprocess.check_output`` somewhere would slip past a gate that only
    knew about ``run`` and ``Popen``, which is how the guard would rot.
    """
    public_launchers = {
        name
        for name in dir(subprocess)
        if name in {"run", "Popen", "call", "check_call", "check_output"}
    }

    assert public_launchers <= LAUNCHERS
