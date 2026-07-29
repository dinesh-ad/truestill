"""Guard tests for scripts/check_redirect_artifacts.py.

Both halves of ENGINEERING_STANDARD.md §4: what it catches, and what it must let through.
A guard that cries wolf on LICENSE / README.md gets switched off.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT = _ROOT / "scripts" / "check_redirect_artifacts.py"


def _load():
    spec = importlib.util.spec_from_file_location("check_redirect_artifacts", _SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


_mod = _load()


def test_catches_the_files_that_were_committed() -> None:
    for name in ("10.0", "25.9", "7.3", "2024-03-24"):
        assert _mod.is_redirect_artifact_name(name), name


def test_catches_integer_and_other_decimals() -> None:
    assert _mod.is_redirect_artifact_name("7")
    assert _mod.is_redirect_artifact_name("3.13")


def test_lets_ordinary_root_names_through() -> None:
    for name in (
        "LICENSE",
        "README.md",
        ".python-version",
        "uv.lock",
        "CHANGELOG.md",
        "Makefile",
        "pyproject.toml",
        ".gitignore",
        "CLAUDE.md",
        "SECURITY.md",
    ):
        assert not _mod.is_redirect_artifact_name(name), name


def test_nested_paths_are_not_this_defect() -> None:
    # The matcher is name-only; callers must restrict to the repo root.
    assert _mod._root_segment("tests/fixtures/10.0") is None
    assert _mod._root_segment("10.0") == "10.0"
    assert _mod._root_segment("./2024-03-24") == "2024-03-24"
