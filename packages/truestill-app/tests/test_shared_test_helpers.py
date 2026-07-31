"""A helper a test imports by bare name must have exactly one candidate file in the repo.

**The bug this guards, reproduced before it was written.** Six app tests and three e2e tests
each said ``from conftest import ...`` - naming two *different* modules. They never collided
because ``testpaths`` keeps the two suites in separate sessions. Point pytest at both at once
and the app test resolves to the browser suite's file::

    $ pytest packages/truestill-app/tests/test_server.py tests/e2e/test_busy_state.py
    E   ImportError: cannot import name 'TOKEN' from 'conftest' (tests/e2e/conftest.py)

That is not a hypothetical: it is the command anyone runs to check one app test against one
browser test, and it fails with an error about a file they did not mention.

**Why the bare name resolves at all.** pytest's prepend import mode puts a test file's own
directory on ``sys.path`` (there is no ``__init__.py`` in any test directory). So a sibling
module is importable by its bare basename - and *whichever directory got prepended first wins*
when two directories hold the same basename. The winner depends on collection order, which is
an argument-order detail, not a decision anyone made.

**So the rule is about basenames, not about conftest.** ``conftest`` is merely the first name
this repo claimed four times; ``support.py`` in two test directories would fail the same way and
be harder to spot. Guarding "do not import conftest" would treat the instance, so this guards
the class: **any module a test imports by bare name must be unambiguous repo-wide.**

The clean split that follows - fixtures live in ``conftest.py`` where pytest injects them by
name and nobody imports it; anything a test needs to *import* lives in a uniquely-named sibling
module - is what makes the root ``conftest.py`` that keeps the suite hermetic harmless. It still
claims the name; nothing resolves against it.
"""

from __future__ import annotations

import ast
import subprocess
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]


def _tracked_python_files() -> list[Path]:
    out = subprocess.run(
        ["git", "ls-files", "*.py"], cwd=REPO, capture_output=True, text=True, check=True
    ).stdout
    return [REPO / line for line in out.splitlines() if line]


def _test_directories(files: list[Path]) -> set[Path]:
    """Directories pytest will prepend to ``sys.path``: those holding tests or a conftest.

    None of them carries an ``__init__.py``, which is what makes their contents importable by
    bare basename in the first place - asserted below rather than assumed.
    """
    return {
        path.parent for path in files if path.name == "conftest.py" or path.name.startswith("test_")
    }


def _importable_by_bare_name(files: list[Path]) -> dict[str, list[Path]]:
    """Module basename -> every file that claims it from a directory on ``sys.path``."""
    directories = _test_directories(files)
    claims: dict[str, list[Path]] = defaultdict(list)
    for path in files:
        if path.parent in directories:
            claims[path.stem].append(path)
    return claims


def _bare_imports(path: Path) -> set[str]:
    """Top-level module names imported without a package prefix, via ``ast`` not a regex."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module.split(".")[0])
        elif isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
    return names


def test_no_test_imports_a_module_name_that_two_files_claim() -> None:
    """The gate. A bare-name import must resolve to one file, whatever the collection order."""
    files = _tracked_python_files()
    claims = _importable_by_bare_name(files)

    ambiguous: list[str] = []
    for path in files:
        if path.parent not in _test_directories(files):
            continue
        for name in _bare_imports(path):
            claimants = claims.get(name, [])
            if len(claimants) > 1:
                where = ", ".join(str(c.relative_to(REPO)) for c in sorted(claimants))
                ambiguous.append(f"{path.relative_to(REPO)} imports '{name}' - claimed by {where}")

    assert not ambiguous, (
        "a test imports a module name that more than one file claims; which one wins depends on "
        "collection order:\n  " + "\n  ".join(sorted(ambiguous))
    )


def test_the_ambiguity_this_guards_is_reachable() -> None:
    """Cry-wolf half: prove the repo really does claim a name more than once.

    Without this, the gate above would keep passing if `_importable_by_bare_name` silently
    stopped finding anything - a guard that watches an empty population reports success forever.
    ``conftest`` is the standing example: four files, and that is fine precisely because the
    gate above proves nothing imports it.
    """
    claims = _importable_by_bare_name(_tracked_python_files())

    assert len(claims.get("conftest", [])) > 1, "the multiply-claimed name this rule exists for"


def test_no_test_directory_has_an_init_file() -> None:
    """The premise of the whole rule, asserted rather than assumed.

    An ``__init__.py`` would make these packages, imports would carry a package prefix, and
    bare-name resolution - along with this entire class of bug - would not arise.
    """
    files = _tracked_python_files()

    packages = [
        d.relative_to(REPO) for d in _test_directories(files) if (d / "__init__.py").exists()
    ]

    assert not packages, (
        f"test directories are not packages, but these have __init__.py: {packages}"
    )
