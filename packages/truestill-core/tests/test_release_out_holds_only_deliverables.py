"""`out/` is what gets published, so nothing may leave scratch in it.

**The defect this pins, reproduced 2026-08-15 before the fix existed.** `build_deb.build` staged
into ``out/truestill_<version>_<arch>/`` and removed that tree only at the *start* of the next
build, so it survived every run. `release.yml` uploads `out/` wholesale and the publish job then
runs ``cd out; sha256sum *``, which exits 1 on a directory - *"sha256sum: truestill_1.0.0_amd64:
Is a directory"* - and GitHub runs `run:` steps under ``bash -e``. Measured: the step exits 1 and
`cat SHA256SUMS` never runs. **The first real tag would have died at publish**, after the whole
build matrix had already spent its minutes, and `gh release create out/*` two steps later would
have been handed the same directory.

**Why the fix is in the producer and the assertion is in both places.** `out/` has two consumers
that assume regular files (the checksum step and `gh release create`), and neither can be made
safe by the other. So the staging tree moves out of the published directory - the root cause -
and the checksum step gains a named refusal, so a *future* step that drops a directory in `out/`
reports which one rather than failing on `Is a directory`.

**dpkg-deb is never invoked here**, deliberately: `test_verify_icon.py` already records that
nothing in `make check` builds a real `.deb`, and this suite runs on three operating systems where
`dpkg-deb` exists on one. `subprocess.run` is replaced, so what is tested is the staging
discipline rather than Debian's packager.
"""

from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml

_ROOT = Path(__file__).resolve().parents[3]


def _build_deb() -> Any:
    spec = importlib.util.spec_from_file_location("build_deb", _ROOT / "packaging" / "build_deb.py")
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _frozen_app(tmp_path: Path) -> Path:
    """The one thing `build` checks for before it stages anything."""
    dist = tmp_path / "dist" / "truestill"
    dist.mkdir(parents=True)
    (dist / "truestill").write_text("#!/bin/sh\n", encoding="utf-8")
    return dist


def _directories_in(out: Path) -> list[str]:
    return sorted(entry.name for entry in out.iterdir() if entry.is_dir())


def test_the_output_directory_holds_no_directories_when_the_build_succeeds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The published directory holds the package and nothing else."""
    build_deb = _build_deb()

    def _packaged(*_args: object, **_kwargs: object) -> None:
        """Stands in for `dpkg-deb`, which exists on one of the three lanes this runs on."""

    monkeypatch.setattr(build_deb.subprocess, "run", _packaged)

    out = tmp_path / "out"
    out.mkdir()
    build_deb.build(_frozen_app(tmp_path), "1.0.0", out)

    assert _directories_in(out) == [], (
        "build_deb left staging trees in the directory release.yml publishes: "
        f"{_directories_in(out)}. `sha256sum *` exits 1 on a directory."
    )


def test_a_failing_dpkg_deb_leaves_no_staging_tree_behind(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The cleanup is on every exit path, not only the happy one.

    Removing the tree after a successful `dpkg-deb` would satisfy the test above and still leave
    debris whenever packaging failed - which is exactly when someone re-runs the lane.
    """
    build_deb = _build_deb()

    def _explode(*_args: object, **_kwargs: object) -> None:
        raise subprocess.CalledProcessError(2, "dpkg-deb")

    monkeypatch.setattr(build_deb.subprocess, "run", _explode)

    out = tmp_path / "out"
    out.mkdir()
    with pytest.raises(subprocess.CalledProcessError):
        build_deb.build(_frozen_app(tmp_path), "1.0.0", out)

    assert _directories_in(out) == [], (
        f"a failed package build left staging behind: {_directories_in(out)}"
    )


def test_the_checksum_step_names_a_non_file_instead_of_dying_on_it() -> None:
    """The backstop, because `out/` has two consumers that assume regular files.

    Asserted on the workflow rather than by running it: the step is bash, and this suite runs on
    Windows too. What is checked is that a regular-file test reaches the entries before
    `sha256sum` does - the producer fix above is what makes it never fire.
    """
    workflow = yaml.safe_load((_ROOT / ".github" / "workflows" / "release.yml").read_text())
    steps = workflow["jobs"]["publish"]["steps"]
    checksums = [step for step in steps if step.get("name") == "Checksums"]
    assert len(checksums) == 1, "expected exactly one Checksums step in the publish job"

    run = checksums[0]["run"]
    assert "sha256sum" in run, "the Checksums step stopped computing checksums"
    assert "-f" in run, (
        "the Checksums step hashes `out/*` with no regular-file test. A directory there exits 1 "
        "under `bash -e` and fails the publish after the build matrix has already run."
    )
