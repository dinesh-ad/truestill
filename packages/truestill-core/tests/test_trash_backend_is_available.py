"""A trash backend exists on every platform this suite runs on, and it is the declared one.

**Why this guard exists, and why it is not a one-line ``is not None``.**

``cleanup.trash_backend`` used to probe for an optional ``send2trash`` and fall back to the
``gio`` binary, returning ``None`` when it found neither. ``run_cleanup`` **then** treated
``None`` as permission to remove a folder outright, so on any machine with neither, the
empty-folder cleanup **destroyed** rather than trashed. ⚠ Past tense on purpose twice over: that
was fixed on 2026-08-04 (``None`` is a refusal), and since 2026-08-22 no folder goes to the trash
at all - only its contents do, and the folder goes to ``rmdir``. `(afj)` The guard below is
unaffected, because what it asserts is that the **declared** backend resolves. ``gio`` ships with GLib, so "neither" was the ordinary state of
Windows and macOS - the two platforms `DECISIONS.md` D9 launches on and builds for - while a
Linux desktop with ``gio`` on PATH quietly took the recoverable path. The value that decided
which of those happened was never measured on Windows by anyone, and could not be measured from
a developer's Linux box.

Declaring the dependency (`IMPLEMENTATION_STANDARDS.md` §7) removes the state. **This test is
what converts that from a claim into something the {ubuntu, macos, windows} matrix answers on
every run**, which is the whole point of the commit that added it. It carries no ``skipif``: a
platform that cannot satisfy it is exactly the platform we need to hear from.

**It asserts PROVENANCE, not the outcome, and that is load-bearing here.**
`ENGINEERING_STANDARD.md` §4: *"Where two defences catch the same case, assert PROVENANCE, not
the outcome."* Two mechanisms can answer this question, and a bare ``assert trash_backend() is
not None`` would be satisfied by ``gio`` on the Linux runner - green, while proving nothing about
the platforms the defect actually lived on, and green again if the dependency were dropped
tomorrow. Asserting the *identity* of the backend is what makes the guard fail when the
dependency goes, on the one runner that has ``gio`` as well.
"""

from __future__ import annotations

import shutil
import sys
import tomllib
from pathlib import Path

import pytest
from truestill_core.cleanup import trash_backend

_ROOT = Path(__file__).resolve().parents[3]
_CORE_MANIFEST = _ROOT / "packages" / "truestill-core" / "pyproject.toml"


def test_a_trash_backend_is_available_on_every_platform() -> None:
    """The rule. No ``skipif`` - a platform that fails this is the one we need to hear from."""
    assert trash_backend() == "send2trash", (
        "no trash backend resolved to the declared dependency on this platform. "
        "`run_cleanup` treats a `None` backend as permission to remove folders outright, so "
        "this is a destructive difference and not a degraded one. If send2trash is genuinely "
        "unimportable here, that is the finding - do not relax this assertion to `is not None`, "
        "which `gio` would answer on Linux while telling you nothing about Windows or macOS."
    )


def test_send2trash_is_declared_rather_than_merely_installed() -> None:
    """Installed-by-accident is not a guarantee; declared-and-locked is.

    The test above passes just as happily against a package that arrived transitively, or that a
    developer installed by hand once. Neither survives a fresh `uv sync --locked` on a CI runner,
    which is where the guarantee has to hold. This reads the manifest so the runtime property and
    the declaration cannot drift apart - the same reason `test_dependency_inventory` reads §7.
    """
    data = tomllib.loads(_CORE_MANIFEST.read_text(encoding="utf-8"))
    declared = data["project"]["dependencies"]

    assert any(spec.strip().lower().startswith("send2trash") for spec in declared), (
        f"send2trash is importable but not declared by {_CORE_MANIFEST.name}. "
        "An undeclared import is one a fresh `uv sync --locked` does not install and a bundler "
        "does not collect."
    )


def test_send2trash_is_probed_before_gio_so_the_answer_does_not_depend_on_glib() -> None:
    """The ordering is the portability argument, so it is pinned rather than assumed.

    Were ``gio`` consulted first, a Linux desktop would answer ``"gio"`` and the declared
    dependency would only ever be reached on the platforms that lack it - inverting the property
    this commit bought. Asserted on a machine that *has* ``gio``, because that is the only
    machine on which the two answers differ and the order can therefore be observed at all.
    """
    if shutil.which("gio") is None:
        pytest.skip("no gio on this machine, so the two candidates cannot be told apart here")

    assert trash_backend() == "send2trash", "gio answered ahead of the declared dependency"


def test_the_gio_fallback_still_works_when_the_import_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The cry-wolf half: this guard must not have deleted the fallback it stopped relying on.

    `ENGINEERING_STANDARD.md` §4 - a guard states both what it catches and what it must let
    through. A declared dependency can still be absent from a *bundle*, since an import inside a
    ``try`` is what a bundler's static analysis misses, so ``gio`` is kept as a second chance.
    Without this half, deleting the fallback entirely would leave every test above green.

    ``sys.modules[name] = None`` is the supported way to make an ``import name`` raise
    ``ImportError`` without touching the filesystem or the installed package.
    """
    if shutil.which("gio") is None:
        pytest.skip("no gio on this machine, so the fallback has nothing to resolve to")

    monkeypatch.setitem(sys.modules, "send2trash", None)

    assert trash_backend() == "gio", "the gio fallback was removed along with the reliance on it"


def test_no_backend_at_all_is_still_representable(monkeypatch: pytest.MonkeyPatch) -> None:
    """The other half of the cry-wolf pair: ``None`` is still reachable, and still means something.

    Declaring the dependency makes ``None`` unexpected; it does not make it impossible, and a
    caller that stopped handling it would be wrong. Pinned so the return type stays honest and so
    the branch that handles it keeps a reason to exist.
    """
    monkeypatch.setitem(sys.modules, "send2trash", None)
    monkeypatch.setattr(shutil, "which", lambda _name: None)

    assert trash_backend() is None
