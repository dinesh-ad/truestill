"""Absolute imports only under packages/ (ENGINEERING_STANDARD §4).

Relative imports are legal Python and the natural reach inside a package split - which is
exactly why they are banned here. During ``service.py`` -> ``service/``, a relative import
hides where a symbol lives and makes every later surface move harder to reason about.
"""

from __future__ import annotations

import ast
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
PACKAGES = REPO / "packages"


def _display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO).as_posix()
    except ValueError:
        return path.as_posix()


def _relative_import_sites(path: Path) -> list[str]:
    """Return ``file:line: ...`` entries for every relative ImportFrom in ``path``."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    sites: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom) or node.level == 0:
            continue
        dots = "." * node.level
        module = node.module or ""
        names = ", ".join(alias.name for alias in node.names)
        sites.append(f"{_display_path(path)}:{node.lineno}: from {dots}{module} import {names}")
    return sites


def test_packages_use_absolute_imports_only() -> None:
    offenders: list[str] = []
    for path in sorted(PACKAGES.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        offenders.extend(_relative_import_sites(path))
    assert not offenders, "relative import(s) under packages/:\n" + "\n".join(offenders)


def test_the_guard_fails_on_a_relative_import(tmp_path: Path) -> None:
    """Mutation half: a relative ImportFrom must be visible to the scanner."""
    defective = tmp_path / "relative_probe.py"
    defective.write_text("from .sibling import thing\n", encoding="utf-8")
    sites = _relative_import_sites(defective)
    assert sites, "the guard would not have caught a relative import"
    assert "from .sibling import thing" in sites[0]

    # Look-alike half: an absolute import of a dotted package path must pass.
    clean = tmp_path / "absolute_probe.py"
    clean.write_text("from truestill_app.service.fs_browse import fs_dirs\n", encoding="utf-8")
    assert _relative_import_sites(clean) == []
