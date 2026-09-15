"""The payload is compared against a written promise. `(akv)`

⚠ **THE CLI WAS ABSENT FROM EVERY RELEASE AND NOTHING WENT RED.** The lane froze
`truestill_app/__main__.py` alone and named the result `truestill`, so the binary a customer got
was the web UI wearing the CLI's name. Six capabilities have no other home - `reclaim`, `rescan`,
`repoint-sources`, `carried`, `self-check`, `catalog --move` - and for anyone who installed the
product they were not CLI-only, they were **unreachable**.

**Why every existing gate was green**, which is the part worth keeping:

* a bundler drops what nothing imports, **with a zero exit** - a missing entry point looks
  exactly like a successful build;
* `--self-check` runs **inside a process** and can only report on the process it is in, so the
  app's report was complete and correct in a tree containing no CLI whatsoever;
* the install detector asserted `/usr/bin/truestill` **exists**. It did. It was the app. A true
  assertion, a false conclusion, and the one command CI ran on the installed copy
  (`--self-check`) was the single flag both surfaces happen to share.

So the check cannot live inside the artifact and cannot be "is a file there". It has to compare
the payload against a promise recorded **outside** it, which is `build_deb.BUNDLE_BINARIES`.

**This guard is cheap because the promise already had to exist**: `/usr/bin` gets a symlink per
name, so the packaging step was always going to enumerate them. `(ago)`'s bar is met on one
instance here rather than two, and deliberately - the instance shipped in two public releases.
"""

from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

import pytest

_PACKAGING = Path(__file__).resolve().parents[3] / "packaging"


def _build_deb():
    """`packaging/` is not an installed package, so it is loaded by path like the lane does."""
    spec = importlib.util.spec_from_file_location("build_deb", _PACKAGING / "build_deb.py")
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _frozen_tree(root: Path, *, names: tuple[str, ...], suffix: str = "") -> Path:
    """A stand-in for PyInstaller's output: one file per executable it was asked to build."""
    dist = root / "truestill"
    dist.mkdir()
    for name in names:
        (dist / f"{name}{suffix}").write_bytes(b"\x7fELF-ish")
    return dist


def test_the_promise_names_both_surfaces() -> None:
    """⚠ **THE NAMES ARE `[project.scripts]`, NOT A CHOICE MADE IN PACKAGING.** Both packages
    have declared `truestill = truestill_cli.cli:main` and `truestill-app =
    truestill_app.__main__:main` all along; the freeze is what diverged from them. Asserting the
    pair here is what stops a future rename happening in one of the two places."""
    assert _build_deb().BUNDLE_BINARIES == ("truestill", "truestill-app")


@pytest.mark.parametrize(("platform", "suffix"), [("linux", ""), ("win32", ".exe")])
def test_a_complete_tree_is_accepted(tmp_path: Path, platform: str, suffix: str) -> None:
    """The cry-wolf half. Without it a check that refuses everything reports a healthy payload
    forever, which is exactly the failure mode being fixed one level up.

    ⚠ **PARAMETRIZED OVER BOTH PLATFORMS BECAUSE THE FIRST VERSION WAS NOT**, and it cost a red
    Windows release lane: the check looked for a bare `truestill` on every platform and reported
    a tree *"missing truestill, truestill-app"* that held `truestill.exe` and `truestill-app.exe`.
    A test that only runs the developer's own platform is how a packaging defect reaches CI.
    """
    module = _build_deb()
    module.verify_bundle_binaries(
        _frozen_tree(tmp_path, names=module.BUNDLE_BINARIES, suffix=suffix), platform=platform
    )


def test_the_extension_is_the_platforms_and_not_the_promises() -> None:
    """`BUNDLE_BINARIES` names binaries; `.exe` is how one platform spells them."""
    module = _build_deb()
    assert module.executable_suffix("linux") == ""
    assert module.executable_suffix("darwin") == ""
    assert module.executable_suffix("win32") == ".exe"


@pytest.mark.parametrize("dropped", ["truestill", "truestill-app"])
@pytest.mark.parametrize(("platform", "suffix"), [("linux", ""), ("win32", ".exe")])
def test_a_tree_missing_a_promised_binary_is_refused(
    tmp_path: Path, dropped: str, platform: str, suffix: str
) -> None:
    """**The defect, reproduced in each direction.** Parametrized rather than written once
    against the CLI, because a guard that only notices the binary that went missing last time is
    a guard aimed at history."""
    module = _build_deb()
    kept = tuple(name for name in module.BUNDLE_BINARIES if name != dropped)

    with pytest.raises(SystemExit) as refusal:
        module.verify_bundle_binaries(
            _frozen_tree(tmp_path, names=kept, suffix=suffix), platform=platform
        )

    assert f"{dropped}{suffix}" in str(refusal.value)
    assert "truestill.spec" in str(refusal.value), (
        "the refusal must say how to produce both, or it only reports that something is wrong"
    )


def test_the_spec_builds_both_and_collects_them_once() -> None:
    """⚠ **THE SPEC IS WHERE THE PROMISE IS KEPT, so the two must not drift apart.**

    Read as text rather than executed: a `.spec` is only valid inside a PyInstaller build, where
    `Analysis`, `PYZ`, `EXE` and `COLLECT` are injected. What is checked is the shape the promise
    depends on - one `COLLECT`, an `EXE` per promised name, and `console=True` on the CLI, which
    is the whole reason there are two executables rather than one that switches (#6244: a
    windowed build has no stdout on Windows).
    """
    spec = (_PACKAGING / "truestill.spec").read_text(encoding="utf-8")
    module = _build_deb()

    for name in module.BUNDLE_BINARIES:
        assert f'name="{name}"' in spec, f"the spec builds no executable named {name}"
    assert spec.count("COLLECT(") == 1, "two COLLECTs would write the shared tree twice"
    assert spec.count("Analysis(") == 2
    reason = "one console setting cannot serve a CLI and a double-clicked app - that is #6244"
    assert "console=True" in spec, reason
    assert "console=False" in spec, reason


def test_the_spec_the_lane_runs_is_tracked_by_git() -> None:
    """⚠ **A SOURCE FILE THE LANE NEEDS MUST BE IN THE REPOSITORY, and one was not.**

    `.gitignore` carried `truestill.spec` to ignore the spec **PyInstaller generates** when it is
    driven by command-line flags - build output, correctly ignored. Without a leading slash git
    matches that name at *any* depth, so the moment `packaging/truestill.spec` became a **source**
    file, `git add -A` skipped it **in silence**: `make check` was green, the commit was green,
    the three `check` lanes were green, and the release lane failed with *"Spec file
    packaging/truestill.spec not found!"*.

    **Reading the file is not enough and that is the whole point** - every other test in this
    module opens it from the working tree, where it exists whether or not git knows about it. The
    question is what a fresh clone gets, and only `git ls-files` answers that.

    Same shape as `verify_bundle_binaries` one level up: **the artifact cannot testify to what is
    missing from it.**
    """
    root = _PACKAGING.parent
    named = [
        line.split("packaging/")[1].split()[0]
        for line in (root / ".github/workflows/release.yml")
        .read_text(encoding="utf-8")
        .splitlines()
        if "pyinstaller" in line and "packaging/" in line
    ]
    assert named, "the release lane no longer names a spec - has the build step changed shape?"

    tracked = subprocess.run(
        ["git", "ls-files", "--error-unmatch", *[f"packaging/{name}" for name in named]],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert tracked.returncode == 0, (
        f"the release lane runs packaging/{named[0]}, which git does not track - a fresh clone "
        f"has no such file and the lane fails on it. Check .gitignore: {tracked.stderr.strip()}"
    )


def test_the_desktop_entry_launches_the_app_and_not_the_command_line() -> None:
    """⚠ **`Terminal=false` IS WHAT MAKES THIS SILENT.** `(akv)` renamed the frozen app to
    `truestill-app` and gave `truestill` to the CLI, so a desktop entry still pointing at
    `truestill` would launch a **console application with no arguments** from a double-click -
    and with `Terminal=false` the user sees nothing at all. No gate covered this line: the
    installer detector runs binaries directly and never opens the entry.
    """
    module = _build_deb()
    entry = dict(line.split("=", 1) for line in module._DESKTOP.splitlines() if "=" in line)

    assert entry["Exec"] == "/usr/bin/truestill-app", (
        "the desktop entry launches the command line, which shows a user nothing"
    )
    assert entry["Terminal"] == "false"
    assert entry["Exec"].rsplit("/", 1)[1] in module.BUNDLE_BINARIES, (
        "the entry names a binary the package does not promise"
    )
