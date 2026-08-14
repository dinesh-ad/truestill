"""Prove the browser stack never reaches a user.

Playwright is a test tool. If it -- or the ~114 MB of browser binaries behind it -- ever
appeared in a shipped wheel's dependencies, a user installing a local-first photo organizer
would silently be installing a browser engine. This asserts the claim rather than trusting the
file it is written in.

Lives with the E2E suite deliberately: it is the suite that introduced the risk, so it is the
suite that carries the proof.
"""

from __future__ import annotations

import subprocess
import tomllib
from pathlib import Path

import pytest

#: THE MIGRATION'S EARLY-WARNING SYSTEM. This file belongs to no screen, so no screen's commit
#: carries it - and an island landing on a DIFFERENT screen changes the DOM around it without
#: touching a line here. `make e2e-shell` runs the set after every island; see
#: `docs/react-migration-plan.md`.
pytestmark = pytest.mark.shell

_ROOT = Path(__file__).resolve().parents[2]
_PACKAGES = ("truestill-core", "truestill-cli", "truestill-app")
#: Tools that exist to test or to BUILD, and must never appear in a shipped package. The
#: bundlers are here for the same reason Playwright is: a user installing a photo organizer
#: should not receive the machinery that packages it.
_TEST_ONLY = (
    "playwright",
    "pytest",
    "ruff",
    "mypy",
    "pre-commit",
    "httpx",
    "coverage",
    "pyinstaller",
    "briefcase",
    # The PE reader `verify_icon.py` uses. Build-only for the same reason the bundlers are: it
    # inspects an artifact and is absent from one.
    "pefile",
)


def test_no_shipped_package_depends_on_a_test_tool() -> None:
    """Runtime dependency lists carry only what the product needs to run."""
    for name in _PACKAGES:
        manifest = tomllib.loads((_ROOT / "packages" / name / "pyproject.toml").read_text())
        declared = " ".join(manifest["project"].get("dependencies", [])).lower()
        for tool in _TEST_ONLY:
            assert tool not in declared, f"{name} declares the test tool {tool!r} at runtime"


def test_the_build_only_bundlers_are_declared_only_in_the_dev_group() -> None:
    """(aad)'s bundlers produce artifacts; they must never be inside one.

    Declared dev-only under the build-tool ruling: a tool that never enters the runtime graph
    carries none of a shipped dependency's burden. This is the guard that keeps that true, so
    the exemption cannot quietly become a shipped dependency later.
    """
    root = tomllib.loads((_ROOT / "pyproject.toml").read_text())
    dev = " ".join(root["dependency-groups"]["dev"]).lower()

    assert "pyinstaller" in dev
    assert "briefcase" in dev


def test_playwright_is_declared_only_in_the_dev_group() -> None:
    root = tomllib.loads((_ROOT / "pyproject.toml").read_text())
    dev = " ".join(root["dependency-groups"]["dev"]).lower()
    assert "pytest-playwright" in dev
    assert "dependencies" not in root.get("project", {})  # the workspace root ships nothing


def test_a_runtime_install_resolves_without_playwright() -> None:
    """The claim, checked against the resolver rather than against the manifests.

    ``uv export --no-dev`` is the exact set a user would install. Nothing browser-shaped may
    appear in it, however the manifests happen to be written.
    """
    exported = subprocess.run(
        ["uv", "export", "--no-dev", "--no-emit-workspace", "--format", "requirements-txt"],
        cwd=_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.lower()

    assert exported.strip(), "export produced nothing -- the check would be vacuous"
    for tool in ("playwright", "pytest", "ruff", "mypy"):
        assert f"\n{tool}" not in f"\n{exported}", f"{tool} is in the runtime install set"
