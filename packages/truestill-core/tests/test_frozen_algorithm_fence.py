"""No shipped code may reach a perceptual algorithm a frozen build does not carry.

**The landmine this defuses.** A frozen build drops `scipy` and `PyWavelets` - 82.2 MiB of a
208.1 MiB Linux build - so `phash`, `phash_simple` and `whash` are unavailable there and
available everywhere else. Today nothing calls them: `scan._hash_one` takes the `dhash` default
and no caller passes `algorithm="phash"`. That is a fact about today, not a property.

Whoever adds a "hashing algorithm" setting, or reaches for `whash` because it handles cropping
better, will do it in a source checkout where it works perfectly - and ship a build where it
raises. This fails at the moment that code is written, in the repository, with the reason
attached, rather than in a user's installer.

**Why it is a source fence rather than a runtime check.** The failure it guards is a *packaging*
divergence: the code is correct in the environment its author runs it in. Only something reading
the source can catch it before the build, which is the whole point - a runtime assertion would
fire in the frozen build, which is exactly where the news arrives too late.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from truestill_freeze import UNAVAILABLE

_ROOT = Path(__file__).resolve().parents[3]
_SHIPPED = ("truestill-core", "truestill-cli", "truestill-app")

#: The algorithms a frozen build cannot run. Kept in step with `truestill_freeze.UNAVAILABLE` by
#: the test at the bottom, so the fence cannot quietly stop covering one of them.
_FORBIDDEN = ("phash", "phash_simple", "whash")

#: `hashing.py` is where the choice legitimately lives: it names `phash` to dispatch on it and in
#: its docstring. Fencing it would mean fencing the one module allowed to know these exist.
_ALLOWED = {_ROOT / "packages" / "truestill-core" / "src" / "truestill_core" / "hashing.py"}


def _shipped_sources() -> list[Path]:
    return [
        path
        for name in _SHIPPED
        for path in (_ROOT / "packages" / name / "src").rglob("*.py")
        if path not in _ALLOWED
    ]


def test_no_shipped_module_calls_an_algorithm_the_frozen_build_lacks() -> None:
    """`imagehash.phash(...)`, `imagehash.whash(...)` and friends, anywhere but `hashing.py`."""
    pattern = re.compile(rf"imagehash\s*\.\s*({'|'.join(_FORBIDDEN)})\b")
    offenders = [
        f"{path.relative_to(_ROOT)}:{number}: {line.strip()}"
        for path in _shipped_sources()
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1)
        if pattern.search(line)
    ]

    assert not offenders, (
        "These call a perceptual algorithm a frozen build does not carry:\n  "
        + "\n  ".join(offenders)
        + "\n\nA frozen build excludes scipy and PyWavelets (82.2 MiB). Use dhash, or take the "
        "size back deliberately - see `packaging/truestill_freeze`."
    )


@pytest.mark.parametrize("algorithm", ["phash", "phash_simple", "whash"])
def test_no_shipped_module_selects_one_by_name(algorithm: str) -> None:
    """The other way in: `perceptual_hash(p, algorithm="phash")` never names `imagehash` at all,
    so the import-style check above cannot see it."""
    pattern = re.compile(rf"""algorithm\s*=\s*['"]{algorithm}['"]""")
    offenders = [
        f"{path.relative_to(_ROOT)}:{number}"
        for path in _shipped_sources()
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1)
        if pattern.search(line)
    ]

    assert not offenders, (
        f"These select {algorithm!r}, which a frozen build cannot run: {offenders}. "
        "Use dhash, or take the size back deliberately."
    )


def test_the_fence_finds_the_thing_it_is_looking_for() -> None:
    """Aimed at itself: a source fence whose glob silently matches nothing passes forever.

    This asserts the sweep really reads the shipped tree, and that `hashing.py` - the one file
    that legitimately names `phash` - is excluded on purpose rather than by an empty glob.
    """
    scanned = _shipped_sources()

    assert len(scanned) > 30, f"only {len(scanned)} shipped modules scanned; the glob is broken"
    hashing = next(iter(_ALLOWED))
    assert hashing.is_file(), "the allowlisted module moved; the fence now covers less than it says"
    assert "phash" in hashing.read_text(encoding="utf-8"), (
        "hashing.py no longer names phash, so the allowlist entry is stale and should go"
    )


def test_the_fence_covers_exactly_what_the_shim_refuses() -> None:
    """The two lists must not drift. If the shim starts refusing a fourth function and this fence
    does not know about it, a caller can add it here and only find out after freezing."""
    assert set(_FORBIDDEN) == set(UNAVAILABLE)
