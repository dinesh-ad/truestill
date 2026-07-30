"""Guard: ENGINEERING_STANDARD.md §4 claims mypy strict is mandatory (audit F4)."""

from __future__ import annotations

import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_mypy_strict_is_enabled_in_pyproject() -> None:
    """The claim and the check must agree - strict must be configured, not merely documented."""
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert data["tool"]["mypy"].get("strict") is True
