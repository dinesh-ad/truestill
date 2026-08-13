"""A monkeypatch must be aimed at the module that owns the name (audit F21 follow-up).

The third member of the guard-quality family, after "a fixture must fail against the bug" and
"a guard must not cry wolf": **a guard must still be aimed at the thing it guards.**

`service/__init__.py` is a pure facade - 78 re-export bindings, zero definitions. Patching
``service.X`` rebinds *the facade's* copy of the name. That reaches the real code only when the
caller also goes through the facade, which is true of ``server.py`` and false of every module
inside the service package: those call their neighbours through their own globals. So the moment
F10 moved a surface out of the monolith, every patch aimed at ``service.X`` silently stopped
intercepting it.

Two live instances, both found by this sweep and both fixed:

* ``tests/e2e/test_busy_state.py`` patched ``service.migration_preview`` while
  ``service/migrate.py`` called its own global. One test failed outright; two kept passing
  without exercising the per-drive lock at all.
* ``test_inventory.py`` patched ``service.organize_preview`` to prove ``organize_inventory``
  never routes through the expensive path. Both functions live in ``service/organize.py``, so
  the patch could not observe the call. Injecting the exact defect it names left it **green**.

The second is the shape that matters: a disarmed guard that still passes advertises coverage it
does not have, and nothing goes red to tell you.

**The rule this encodes:** under ``truestill_app.service``, a patch target's first segment must
be a *submodule* (``service.organize.read_metadata``), never a re-exported name
(``service.organize_preview``). Submodule-ness is read from the live package rather than a
hardcoded list, so a new surface is covered the day it is added.
"""

from __future__ import annotations

import ast
from pathlib import Path
from types import ModuleType
from uuid import uuid4

import pytest
from truestill_app import service

REPO = Path(__file__).resolve().parents[3]

#: Every test tree. e2e is included deliberately: that is where the F10 instance lived, and it
#: is the tree least likely to be re-read when a service module moves.
TEST_ROOTS: tuple[Path, ...] = (
    REPO / "packages/truestill-core/tests",
    REPO / "packages/truestill-cli/tests",
    REPO / "packages/truestill-app/tests",
    REPO / "tests/e2e",
)

_FACADE = "truestill_app.service"
_PATCHERS = frozenset({"setattr", "patch", "object"})


def _is_submodule(name: str) -> bool:
    return isinstance(getattr(service, name, None), ModuleType)


def _facade_aliases(tree: ast.Module) -> set[str]:
    """Local names bound to the facade *package itself*, not to one of its submodules.

    ``from truestill_app import service`` binds the facade; ``from truestill_app.service import
    migrate as service_migrate`` binds a submodule and is exactly the correct form.
    """
    aliases: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "truestill_app":
            aliases |= {a.asname or a.name for a in node.names if a.name == "service"}
        elif isinstance(node, ast.Import):
            aliases |= {a.asname for a in node.names if a.name == _FACADE and a.asname}
    return aliases


def _label(path: Path) -> str:
    """Repo-relative when possible, absolute otherwise - a report must never raise."""
    try:
        return str(path.relative_to(REPO))
    except ValueError:
        return str(path)


def _offenders_in(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    aliases = _facade_aliases(tree)
    found: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        func = node.func
        attr = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
        if attr not in _PATCHERS:
            continue
        target = node.args[0]
        where = f"{_label(path)}:{node.lineno}"

        # String form: patch("truestill_app.service.<first>...")
        if isinstance(target, ast.Constant) and isinstance(target.value, str):
            dotted = target.value
            if dotted.startswith(f"{_FACADE}.") and not _is_submodule(
                dotted[len(_FACADE) + 1 :].split(".")[0]
            ):
                found.append(f"{where}: patches the facade re-export {dotted!r}")

        # Object form: monkeypatch.setattr(service, "<name>", ...) - the F10 instance.
        elif isinstance(target, ast.Name) and target.id in aliases and len(node.args) > 1:
            second = node.args[1]
            named = second.value if isinstance(second, ast.Constant) else "?"
            found.append(f"{where}: patches {target.id}.{named} on the service facade")
    return found


def _test_files() -> list[Path]:
    return sorted(p for root in TEST_ROOTS for p in root.rglob("test_*.py"))


def test_the_test_roots_resolve() -> None:
    """A relocated test tree must fail this guard, never silently shrink its own scope."""
    missing = [str(root.relative_to(REPO)) for root in TEST_ROOTS if not root.is_dir()]
    assert not missing, "TEST_ROOTS missing - the sweep would be silently narrower:\n" + "\n".join(
        missing
    )
    assert len(_test_files()) > 50, "suspiciously few test files collected; check TEST_ROOTS"


def test_no_monkeypatch_aims_at_a_service_facade_re_export() -> None:
    offenders = [line for path in _test_files() for line in _offenders_in(path)]
    assert not offenders, (
        "a patch aimed at a service facade re-export does not reach callers inside the "
        "service package - patch the owning module instead:\n" + "\n".join(offenders)
    )


@pytest.mark.parametrize(
    ("source", "should_flag", "why"),
    [
        (
            'monkeypatch.setattr("truestill_app.service.organize_preview", fake)',
            True,
            "the real test_inventory defect: organize_preview is a re-export",
        ),
        (
            (
                "from truestill_app import service\n"
                'monkeypatch.setattr(service, "migration_preview", blocked)'
            ),
            True,
            "the real F10 e2e defect, in its object form",
        ),
        (
            'monkeypatch.setattr("truestill_app.service.organize.read_metadata", fake)',
            False,
            "correctly aimed at the owning submodule",
        ),
        (
            'monkeypatch.setattr("truestill_core.binaries.os_opener", fake)',
            False,
            "a stdlib name inside an owning submodule",
        ),
        (
            (
                "from truestill_app.service import migrate as service_migrate\n"
                'monkeypatch.setattr(service_migrate, "migration_preview", blocked)'
            ),
            False,
            "the corrected form: a submodule alias, not the facade",
        ),
        (
            'monkeypatch.setattr("truestill_core.scan.sha256_file", fake)',
            False,
            "a core module, nothing to do with the facade",
        ),
        (
            'monkeypatch.setattr(Path, "is_dir", fake)',
            False,
            "an unrelated object-form patch must not be swept up",
        ),
    ],
)
def test_the_guard_catches_the_two_real_defects_and_spares_the_look_alikes(
    source: str, should_flag: bool, why: str
) -> None:
    """Both halves, using the two defects that actually shipped and the forms that did not.

    Written against real strings from this repository rather than invented ones: the first two
    are what ``test_busy_state`` and ``test_inventory`` literally contained, and the third
    through fifth are what the rest of the suite already does correctly and must keep doing.
    """
    # `_offenders_in` labels paths relative to REPO, so the probe must live inside the repo tree -
    # `tmp_path` cannot serve. **The name must be UNIQUE**: a fixed one raced itself under
    # `-n auto`, because the five parametrised cases run on different xdist workers and each wrote
    # and unlinked the same path. One worker parsed a half-written file (`SyntaxError`) while
    # another found it already unlinked (`FileNotFoundError`). Red on CI run 31399973530, and
    # reproduced locally 8 times in 12 at `-n 5`.
    staged = REPO / "packages/truestill-app/tests" / f".probe_{uuid4().hex}.py"
    staged.write_text(source, encoding="utf-8")
    try:
        offenders = _offenders_in(staged)
    finally:
        staged.unlink()
    assert bool(offenders) is should_flag, f"{why}: got {offenders}"
