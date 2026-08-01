"""Every declared lower bound is a version we actually test, not one we think would work.

**The fiction this closes.** The floors drifted years below reality: ``starlette>=0.40`` while
1.3.1 was what every test ran against, ``pillow>=10.0.0`` against 12.3.0, ``pillow-heif>=0.16.0``
against 1.5.0. Nothing installs those old versions here, so nothing ever exercised them - the
bounds asserted compatibility that had never once been demonstrated. A resolver that picked one
would hand a user an untested application, and we would find out from the user.

**The rule: a floor means tested-at, not thought-to-work.** `uv.lock` is the single source of
truth for what ships (`IMPLEMENTATION_STANDARDS` §7), so the floor and the lock must agree. This
compares them and fails when a floor sits below the version the suite actually ran against.

**Deliberately not a floor-resolution CI lane.** Resolving and testing at the minimum would be a
second matrix to maintain for a configuration nobody is asked to run. The cheaper and more
honest answer is to stop claiming support for it. When a dependency is upgraded, its floor moves
with it - and this is what says so, at the moment it stops being true rather than months later.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[3]
_MANIFESTS = (
    _ROOT / "pyproject.toml",
    _ROOT / "packages" / "truestill-core" / "pyproject.toml",
    _ROOT / "packages" / "truestill-cli" / "pyproject.toml",
    _ROOT / "packages" / "truestill-app" / "pyproject.toml",
)
#: Workspace members are source, not resolved versions - they carry no floor to check.
_WORKSPACE = {"truestill-core", "truestill-cli", "truestill-app"}
_SPEC = re.compile(r"^([A-Za-z0-9._-]+)\s*>=\s*([0-9][0-9A-Za-z.*+!-]*)$")


def _locked_versions() -> dict[str, str]:
    """Every package in `uv.lock`, normalized, with the version this suite resolved to."""
    lock = tomllib.loads((_ROOT / "uv.lock").read_text(encoding="utf-8"))
    return {
        p["name"].lower().replace("_", "-"): p["version"]
        for p in lock.get("package", [])
        if "version" in p
    }


def _declared_floors() -> list[tuple[str, str, str, str]]:
    """``(manifest, package, floor, raw)`` for every ``>=`` bound across the workspace."""
    found: list[tuple[str, str, str, str]] = []
    for manifest in _MANIFESTS:
        data = tomllib.loads(manifest.read_text(encoding="utf-8"))
        specs = list(data.get("project", {}).get("dependencies", []))
        for group in data.get("dependency-groups", {}).values():
            specs.extend(s for s in group if isinstance(s, str))
        for spec in specs:
            match = _SPEC.match(spec.strip())
            if match is None:
                continue  # a bare workspace member, or a form this rule does not cover
            name = match.group(1).lower().replace("_", "-")
            if name not in _WORKSPACE:
                found.append((manifest.name, name, match.group(2), spec))
    return found


def _as_tuple(version: str) -> tuple[int, ...]:
    """Numeric release segments only - enough to order the versions this repo declares."""
    return tuple(int(part) for part in re.findall(r"\d+", version.split("+", maxsplit=1)[0])[:4])


def test_every_declared_floor_is_a_version_the_suite_actually_ran() -> None:
    """The whole rule, in one assertion: no floor below what `uv.lock` resolved."""
    locked = _locked_versions()
    behind = [
        f"{manifest}: {raw!r} but the suite tests against {locked[name]}"
        for manifest, name, floor, raw in _declared_floors()
        if name in locked and _as_tuple(floor) < _as_tuple(locked[name])
    ]

    assert not behind, (
        "A lower bound claims support for a version nothing here has ever run:\n  "
        + "\n  ".join(behind)
        + "\n\nRaise the floor to the locked version. A floor means tested-at, not "
        "thought-to-work - see this module's docstring."
    )


def test_the_check_finds_a_floor_that_has_drifted() -> None:
    """The guard, aimed at itself.

    A rule of this shape passes trivially when its parser silently matches nothing - the failure
    mode is a green test that reads no dependencies at all. This drives the comparison with a
    floor that *has* drifted and asserts it is caught.
    """
    assert _as_tuple("0.40") < _as_tuple("1.3.1"), "the version comparison is not ordering"
    assert _as_tuple("10.0.0") < _as_tuple("12.3.0")
    assert not _as_tuple("12.3.0") < _as_tuple("12.3.0"), "equal must not read as behind"


def test_the_floors_actually_being_checked_are_the_real_ones() -> None:
    """Guards the same silent-empty failure from the other side: that the parser found the
    dependencies at all, and the well-known ones by name."""
    names = {name for _m, name, _f, _r in _declared_floors()}

    assert {"pillow", "imagehash", "starlette", "uvicorn", "platformdirs"} <= names
    assert len(names) >= 10, f"only {len(names)} floors parsed - the reader is missing manifests"


@pytest.mark.parametrize("manifest", _MANIFESTS, ids=lambda p: p.parent.name)
def test_every_manifest_is_readable(manifest: Path) -> None:
    """A manifest that moved would otherwise make the rule above vacuously true."""
    assert manifest.is_file(), f"{manifest} is gone; the floor rule now checks less than it says"
