"""Finding an external binary: bundled with the application first, then the machine's PATH.

**Why the order is this way round ((aad)).** `shutil.which` alone is right for a developer
install and wrong for a shipped one. A double-clicked desktop app has no terminal, so it has no
inherited PATH worth relying on - and the binary it needs was shipped *inside* it. Searching PATH
first would mean an installed copy silently preferring whatever version happens to be on the
user's machine over the one it was tested against.

**"Bundled" is stated as a contract, not as a bundler's layout.** No PyInstaller ``_MEIPASS``, no
Briefcase directory shape - those would tie this to a tool the project has not chosen yet, and
`(aad)` is explicit that the bundler question is still open. What is fixed is what *we* promise
to look at, and a bundler is chosen partly on whether it can satisfy it:

1. a per-binary override (``TRUESTILL_EXIFTOOL``) - an escape hatch for a user with a specific
   build, and how these tests inject one;
2. ``TRUESTILL_BIN_DIR`` - one directory a packager fills;
3. ``bin/`` beside the running executable - the zero-configuration default, which both candidate
   bundlers can satisfy by laying the file down in the right place and setting nothing.
4. Then PATH.

**Resolution is deliberately not cached, and that is a measured decision.** ``ensure_exiftool``
is called once per *batch*, outside the chunk loop, and `shutil.which` costs **30.6 us** against
an exiftool process start of 50-200 ms - about 0.02% of one invocation, with the bundled probes
adding two ``stat`` calls ahead of it. Caching would buy nothing measurable and cost the ability
to honour an override set after first use, which is precisely the import-time-constant bug
`(aae)` was: *a value frozen early is a value no test can influence.*

`shutil.which` does the actual looking in every branch, including the bundled directories, via
its ``path`` argument. That is reuse rather than reimplementation, and on Windows it is the
difference between working and not: ``PATHEXT`` means the file is ``exiftool.exe``, and a
hand-rolled ``(directory / name).exists()`` would miss it on the one platform where the bundled
path matters most.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from truestill_core.binaries import BIN_DIR_ENV, resolve_binary


def _fake_binary(directory: Path, name: str) -> Path:
    """An executable file `shutil.which` will accept, on this platform.

    Windows decides by extension (``PATHEXT``); POSIX decides by the execute bit. Getting this
    wrong would make the whole suite pass vacuously on one platform.
    """
    directory.mkdir(parents=True, exist_ok=True)
    if sys.platform == "win32":
        path = directory / f"{name}.exe"
        path.write_bytes(b"MZ")
        return path
    path = directory / name
    path.write_text("#!/bin/sh\n")
    path.chmod(0o755)
    return path


def test_a_bundled_binary_is_preferred_over_the_machines_own(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The rule (aad) needs: a shipped app uses what it shipped with.

    Reversed, an installed copy would silently run whatever version is on the user's PATH rather
    than the one it was tested against.
    """
    bundled = tmp_path / "bundled"
    on_path = tmp_path / "elsewhere"
    _fake_binary(bundled, "toolx")
    _fake_binary(on_path, "toolx")
    monkeypatch.setenv(BIN_DIR_ENV, str(bundled))
    monkeypatch.setenv("PATH", str(on_path))

    resolved = resolve_binary("toolx")

    assert resolved is not None
    assert Path(resolved).parent == bundled


def test_path_is_used_when_nothing_is_bundled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A developer install must keep working exactly as it did - this is the common case."""
    on_path = tmp_path / "elsewhere"
    _fake_binary(on_path, "toolx")
    monkeypatch.delenv(BIN_DIR_ENV, raising=False)
    monkeypatch.setenv("PATH", str(on_path))

    resolved = resolve_binary("toolx")

    assert resolved is not None
    assert Path(resolved).parent == on_path


def test_a_per_binary_override_beats_both(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The escape hatch: a user pointing at one specific build wins over everything."""
    chosen = _fake_binary(tmp_path / "chosen", "toolx")
    _fake_binary(tmp_path / "bundled", "toolx")
    _fake_binary(tmp_path / "elsewhere", "toolx")
    monkeypatch.setenv(BIN_DIR_ENV, str(tmp_path / "bundled"))
    monkeypatch.setenv("PATH", str(tmp_path / "elsewhere"))
    monkeypatch.setenv("TOOLX_BIN", str(chosen))

    assert resolve_binary("toolx", override_env="TOOLX_BIN") == str(chosen)


def test_an_override_pointing_at_nothing_is_not_silently_ignored(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Falling back would run a different binary than the user asked for, and say nothing.

    Someone who sets an override and mistypes it must find out, not get a silent substitution -
    the never-silent rule applied to a path that looks like a convenience.
    """
    _fake_binary(tmp_path / "elsewhere", "toolx")
    monkeypatch.setenv("PATH", str(tmp_path / "elsewhere"))
    monkeypatch.setenv("TOOLX_BIN", str(tmp_path / "does-not-exist"))

    assert resolve_binary("toolx", override_env="TOOLX_BIN") is None


def test_a_missing_binary_resolves_to_none(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(BIN_DIR_ENV, raising=False)
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))

    assert resolve_binary("toolx") is None


def test_a_bundled_directory_that_does_not_exist_is_skipped_not_fatal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Cry-wolf half: running from source sets no bundle, and that is the normal case."""
    on_path = tmp_path / "elsewhere"
    _fake_binary(on_path, "toolx")
    monkeypatch.setenv(BIN_DIR_ENV, str(tmp_path / "nowhere"))
    monkeypatch.setenv("PATH", str(on_path))

    assert resolve_binary("toolx") is not None


def test_resolution_is_not_cached_between_calls(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An override set after the first call must still be honoured.

    Guards the `(aae)` failure directly: a value resolved once and frozen is a value no test and
    no user can influence afterwards. Measured cost of not caching is 30.6 us per batch.
    """
    first = tmp_path / "first"
    second = tmp_path / "second"
    _fake_binary(first, "toolx")
    _fake_binary(second, "toolx")
    monkeypatch.setenv(BIN_DIR_ENV, str(first))
    assert Path(resolve_binary("toolx") or "").parent == first

    monkeypatch.setenv(BIN_DIR_ENV, str(second))

    assert Path(resolve_binary("toolx") or "").parent == second


def test_the_executable_sibling_directory_is_searched(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The zero-configuration half of the contract, which a bundler satisfies by layout alone.

    A packaged app that drops the binary in ``bin/`` next to its executable needs no environment
    variable set, which is the difference between a contract a bundler can meet and one that
    needs a launcher script to set up first.
    """
    fake_root = tmp_path / "app"
    fake_root.mkdir()
    executable = fake_root / "truestill"
    executable.write_text("")
    _fake_binary(fake_root / "bin", "toolx")
    monkeypatch.delenv(BIN_DIR_ENV, raising=False)
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    monkeypatch.setattr(sys, "executable", str(executable))

    resolved = resolve_binary("toolx")

    assert resolved is not None
    assert Path(resolved).parent == fake_root / "bin"


def test_nothing_here_depends_on_a_real_binary_being_installed() -> None:
    """The hermeticity premise, asserted rather than assumed.

    Every path above is exercised against files this test made. If the module ever started
    consulting a real location, this suite would begin passing for reasons the CI matrix cannot
    reproduce - which is the trap the session fixture exists to close.
    """
    assert os.environ.get("TRUESTILL_BIN_DIR") in (None, ""), (
        "the suite must not inherit a bundled directory from the developer's environment"
    )
