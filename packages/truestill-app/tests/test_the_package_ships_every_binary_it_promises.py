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


def _frozen_tree(root: Path, *, names: tuple[str, ...]) -> Path:
    """A stand-in for PyInstaller's output: one file per executable it was asked to build."""
    dist = root / "truestill"
    dist.mkdir()
    for name in names:
        (dist / name).write_bytes(b"\x7fELF-ish")
    return dist


def test_the_promise_names_both_surfaces() -> None:
    """⚠ **THE NAMES ARE `[project.scripts]`, NOT A CHOICE MADE IN PACKAGING.** Both packages
    have declared `truestill = truestill_cli.cli:main` and `truestill-app =
    truestill_app.__main__:main` all along; the freeze is what diverged from them. Asserting the
    pair here is what stops a future rename happening in one of the two places."""
    assert _build_deb().BUNDLE_BINARIES == ("truestill", "truestill-app")


def test_a_complete_tree_is_accepted(tmp_path: Path) -> None:
    """The cry-wolf half. Without it a check that refuses everything reports a healthy payload
    forever, which is exactly the failure mode being fixed one level up."""
    module = _build_deb()
    module.verify_bundle_binaries(_frozen_tree(tmp_path, names=module.BUNDLE_BINARIES))


@pytest.mark.parametrize("dropped", ["truestill", "truestill-app"])
def test_a_tree_missing_a_promised_binary_is_refused(tmp_path: Path, dropped: str) -> None:
    """**The defect, reproduced in each direction.** Parametrized rather than written once
    against the CLI, because a guard that only notices the binary that went missing last time is
    a guard aimed at history."""
    module = _build_deb()
    kept = tuple(name for name in module.BUNDLE_BINARIES if name != dropped)

    with pytest.raises(SystemExit) as refusal:
        module.verify_bundle_binaries(_frozen_tree(tmp_path, names=kept))

    assert dropped in str(refusal.value)
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
