"""A `skipif` that calls a POSIX-only function must be short-circuited in its own condition.

**The failure this prevents has no test-level symptom: the module does not collect at all.**
`pytest.mark.skipif` evaluates its condition at import time, and *every* decorator on a
function is evaluated independently - so stacking them does not make the second conditional on
the first:

    @pytest.mark.skipif(os.name == "nt", reason="POSIX permission bits")
    @pytest.mark.skipif(os.getuid() == 0, reason="root can list any directory")

reads as "skip on Windows, and also skip for root", and on Windows raises
``AttributeError: module 'os' has no attribute 'getuid'`` before either skip applies. The whole
file fails to collect, so **thirty tests silently stop running on that lane** while the other
lanes stay green. Found on CI 2026-08-03; the two pre-existing sites in this repo had always
used the correct single-condition form, and the new file did not.

The rule is therefore about the **shape of one condition**, not about which decorators exist:
``sys.platform == "win32" or os.geteuid() == 0`` is safe because ``or`` short-circuits and the
platform test is first. Two decorators can never do that.

Scoped to `skipif` conditions rather than to modules generally: a POSIX-only call inside a test
*body* is fine, because the body does not run on the skipped lane.

⚠ **IF YOU ARE WRITING A PLATFORM-SPECIFIC TEST, THIS FILE IS THE THING TO READ FIRST, AND ON
2026-08-20 IT WAS NOT.** `test_ci_bounds_apt_in_one_place` gained two tests that execute a bash
script using `timeout(1)`, with no marker at all, and **turned `main` red on two lanes** (run
32337630094): macOS exits **127** because `timeout` is GNU coreutils and BSD ships none, and
Windows raises `WinError 193` because it cannot execute a bash script. Neither is exotic; both
are the first thing this file is about.

**The rule the next person needs, stated once:** a test that *shells out* is platform-specific
whether or not it says so. Ask what the command is before asking whether the test passes -
`timeout`, `chmod`, `ln -s`, `/bin/sh` and anything with a shebang are all Linux-and-maybe-macOS
at best. The guard below cannot catch that, because the defect is a **missing** condition rather
than a malformed one; only reading this file catches it.
"""

from __future__ import annotations

import ast
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]

#: `os` functions that do not exist on Windows. Touching one at import time is the defect.
POSIX_ONLY: frozenset[str] = frozenset(
    {"getuid", "geteuid", "getgid", "getegid", "getgroups", "getlogin", "getpriority"}
)

#: What a platform short-circuit looks like. Either spelling is used in this repo.
PLATFORM_MARKERS: frozenset[str] = frozenset({"platform", "name"})


def _test_files() -> list[Path]:
    return sorted(REPO.glob("packages/*/tests/**/*.py")) + sorted(REPO.glob("tests/**/*.py"))


def _posix_only_calls(node: ast.AST) -> set[str]:
    """POSIX-only ``os.<fn>()`` calls anywhere inside ``node``."""
    found: set[str] = set()
    for child in ast.walk(node):
        if (
            isinstance(child, ast.Call)
            and isinstance(child.func, ast.Attribute)
            and child.func.attr in POSIX_ONLY
            and isinstance(child.func.value, ast.Name)
            and child.func.value.id == "os"
        ):
            found.add(child.func.attr)
    return found


def _has_platform_guard(node: ast.AST) -> bool:
    """Whether ``node`` reads ``sys.platform`` or ``os.name``."""
    return any(
        isinstance(child, ast.Attribute)
        and child.attr in PLATFORM_MARKERS
        and isinstance(child.value, ast.Name)
        and child.value.id in {"sys", "os"}
        for child in ast.walk(node)
    )


def _skipif_conditions(tree: ast.AST) -> list[ast.expr]:
    """The first positional argument of every ``pytest.mark.skipif(...)`` decorator."""
    conditions: list[ast.expr] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            continue
        for decorator in node.decorator_list:
            if (
                isinstance(decorator, ast.Call)
                and isinstance(decorator.func, ast.Attribute)
                and decorator.func.attr == "skipif"
                and decorator.args
            ):
                conditions.append(decorator.args[0])
    return conditions


def _offenders() -> list[str]:
    found: list[str] = []
    for path in _test_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for condition in _skipif_conditions(tree):
            calls = _posix_only_calls(condition)
            if calls and not _has_platform_guard(condition):
                relative = path.relative_to(REPO).as_posix()
                names = ", ".join(sorted(calls))
                found.append(f"{relative}:{condition.lineno}: os.{names} with no platform guard")
    return found


def test_no_skipif_calls_a_posix_only_function_unguarded() -> None:
    offenders = _offenders()
    assert not offenders, (
        f"{len(offenders)} skipif condition(s) call a Windows-absent `os` function without a "
        "platform short-circuit in the SAME condition:\n  "
        + "\n  ".join(offenders)
        + "\n\nStacking a second @skipif does not help - every decorator is evaluated at import, "
        "so the module fails to collect on Windows and its tests silently stop running. Write "
        'one condition: `sys.platform == "win32" or os.geteuid() == 0`.'
    )


def test_the_guard_can_see_the_defect() -> None:
    """Proven against the real 2026-08-03 shape, which no lane but Windows could reveal."""
    broken = ast.parse(
        "import os, pytest\n"
        '@pytest.mark.skipif(os.name == "nt", reason="a")\n'
        '@pytest.mark.skipif(os.getuid() == 0, reason="b")\n'
        "def test_x() -> None: ...\n"
    )
    conditions = _skipif_conditions(broken)
    assert len(conditions) == 2
    unguarded = [c for c in conditions if _posix_only_calls(c) and not _has_platform_guard(c)]
    assert len(unguarded) == 1, "the getuid condition must be seen as unguarded"


def test_the_guard_spares_the_correct_form() -> None:
    """Cry-wolf: the short-circuited single condition is the form this repo already uses."""
    correct = ast.parse(
        "import os, sys, pytest\n"
        '@pytest.mark.skipif(sys.platform == "win32" or os.geteuid() == 0, reason="a")\n'
        "def test_x() -> None: ...\n"
    )
    conditions = _skipif_conditions(correct)
    assert conditions
    assert not [c for c in conditions if _posix_only_calls(c) and not _has_platform_guard(c)]


def test_the_guard_actually_scans_something() -> None:
    """Anti-vacuity: a walk that found no `skipif` at all would pass while checking nothing."""
    total = sum(
        len(_skipif_conditions(ast.parse(p.read_text(encoding="utf-8")))) for p in _test_files()
    )
    assert total >= 3, f"expected the repo's skipif sites to be visible, saw {total}"
