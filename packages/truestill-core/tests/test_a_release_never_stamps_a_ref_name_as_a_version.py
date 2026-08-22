"""A build from a non-tag ref is stamped `0.0.0`, never with the ref's name. `(aex)`

**The defect, from a real run rather than reasoning.** Run **32552435733** - a
`workflow_dispatch` with `dry_run=true` from `main` - produced
**`TruestillSetup-main.exe`**: an installer carrying a branch name in its filename and in
Add/Remove Programs. It **passed every gate**: self-check, comparison, install, verify, uninstall.
Linux, in the same run, produced `truestill_0.0.0_amd64.deb`.

⚠ **Two platforms, two derivations, two different wrong answers.**

* Linux asked *"is this ref `main`?"* - one hardcoded branch name, so a dispatch from any other
  branch stamps a package with that branch's name.
* Windows had `if (-not $version) { $version = '0.0.0-dev' }`, **a guard that cannot fire**:
  `$version` was `github.ref_name` minus a leading `v`, and on a dispatch that is `main`, a
  non-empty string. It looks exactly like the Linux defence beside it and defends nothing.

⚠ **AND `0.0.0` WAS ALSO WRONG, WHICH IS THE QUIETER HALF.** The first fix made a dispatch stamp
`0.0.0`, matching what Linux already did - and `truestill_0.0.0_amd64.deb` is **indistinguishable
from a real 0.0.0 release**. Windows produced something obviously broken; Linux produced something
**plausibly wrong**, and the plausible one outlives the obvious one. The industry pattern is
**validate, not fall back**: a release workflow checks the version is a 3-component semver and
refuses otherwise, and a manual dispatch stamps something that cannot be mistaken for a release.

**So the rule is one rule on both branches** - the value must be semver with three components -
and a dispatch carries `-dev` and the run that made it. These tests execute **the actual script
out of the YAML** rather than asserting its text, so what is pinned is behaviour rather than
spelling.

⚠ **WHAT THIS CANNOT TEST, stated rather than implied.** It runs the step's `run:` block under
this machine's bash with the environment a runner sets. It does **not** prove that GitHub wires
`$GITHUB_OUTPUT`, that `pwsh` interpolates the output into `ISCC.exe` correctly, or that `bash`
exists on the Windows image. Those need a dispatch, and a dispatch is what found the defect. What
is testable without one is the decision the script makes, and that is what these assert.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

_REPO = Path(__file__).resolve().parents[3]
_WORKFLOW = _REPO / ".github" / "workflows" / "release.yml"

_POSIX_ONLY = pytest.mark.skipif(
    sys.platform == "win32", reason="executes a bash step; the runner's own bash is not under test"
)


def _build_steps() -> list[dict[str, Any]]:
    workflow = yaml.safe_load(_WORKFLOW.read_text(encoding="utf-8"))
    return [s for s in workflow["jobs"]["build"]["steps"] if isinstance(s, dict)]


def _version_step() -> dict[str, Any]:
    steps = [s for s in _build_steps() if s.get("id") == "version"]
    assert len(steps) == 1, (
        f"expected exactly one version derivation, found {len(steps)}. Two derivations is how the "
        f"two platforms came to disagree in the first place."
    )
    return steps[0]


def _resolve(ref_type: str, ref_name: str, tmp_path: Path) -> tuple[int, str]:
    """Run the workflow's own version script. Returns `(exit code, resolved value)`."""
    output = tmp_path / "gh_output"
    output.touch()
    result = subprocess.run(
        ["bash", "-c", _version_step()["run"]],
        env={
            **os.environ,
            "GITHUB_REF_TYPE": ref_type,
            "GITHUB_REF_NAME": ref_name,
            "GITHUB_OUTPUT": str(output),
            # The runner always sets this; the script defaults it so a missing one is not a
            # crash under `set -u`. Set here so the test exercises the runner's shape.
            "GITHUB_RUN_ID": "32552435733",
        },
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    written = output.read_text(encoding="utf-8").strip()
    value = written.split("=", 1)[1] if written.startswith("value=") else ""
    return result.returncode, value


def test_the_step_is_actually_found_and_runs() -> None:
    """Non-emptiness first: a scan over a step that moved would report the same green."""
    step = _version_step()

    assert step.get("shell") == "bash", (
        "the derivation is not a bash step, so it cannot be the single one both platforms share"
    )
    assert "GITHUB_REF_TYPE" in step["run"], "the script does not consult the ref TYPE at all"


@_POSIX_ONLY
@pytest.mark.parametrize("ref_name", ["main", "feature/anything", "release-prep", "v-not-a-tag"])
def test_a_non_tag_ref_never_becomes_the_version(ref_name: str, tmp_path: Path) -> None:
    """⚠ THE REGRESSION, in the shape of the run that found it.

    `main` is the case that shipped `TruestillSetup-main.exe`. The others are the case the Linux
    fallback never covered: it asked *"is this `main`?"*, so **every other branch** stamped its
    own name. Fixing the instance would have left three of these four failing.
    """
    code, value = _resolve("branch", ref_name, tmp_path)

    assert code == 0, "a dispatch from a branch is an ordinary thing to do and must not fail"
    assert ref_name not in value, (
        f"the ref name leaked into the version: {value!r}. This is what put a branch name into an "
        f"installer's filename and into Add/Remove Programs."
    )
    # ⚠ AND IT MUST NOT LOOK LIKE A RELEASE EITHER. `0.0.0` is a real version somebody could ship;
    # a build that wears it is plausibly wrong, which outlives obviously wrong.
    assert value != "0.0.0", "a dispatch build is stamped indistinguishably from a real release"
    assert "-dev" in value, f"a dispatch build must be unmistakable, got {value!r}"
    assert "32552435733" in value, (
        "the stamp does not name the run that made it, so an unmistakable build is still an "
        "untraceable one"
    )


@_POSIX_ONLY
@pytest.mark.parametrize(
    ("tag", "expected"),
    [("v1.2.3", "1.2.3"), ("v0.1.0", "0.1.0"), ("v1.2.3-rc1", "1.2.3-rc1")],
)
def test_a_version_tag_becomes_its_version(tag: str, expected: str, tmp_path: Path) -> None:
    """The other half. A guard that refused everything would pass the test above and ship nothing."""
    code, value = _resolve("tag", tag, tmp_path)

    assert code == 0, f"{tag!r} is a version tag and was refused"
    assert value == expected


@_POSIX_ONLY
@pytest.mark.parametrize("tag", ["vNext", "v2", "v1.2", "vlatest", "v1.2.3.4"])
def test_a_tag_that_is_not_a_three_component_semver_is_refused(tag: str, tmp_path: Path) -> None:
    """⚠ Refused, not defaulted, because the publish job runs on tags.

    Falling back here would publish a release named after a guess - the same class of defect as
    stamping a branch name, arriving from the opposite direction.

    ⚠ **`v2` and `v1.2` are in this list deliberately.** The first version of this fix accepted
    them and turned `v2` into `2`. Two components is not a version this project can express - the
    packagers and every consumer expect `X.Y.Z` - so accepting it means shipping something whose
    meaning nobody agreed. **Validate, do not coerce.**
    """
    code, value = _resolve("tag", tag, tmp_path)

    assert code != 0, f"{tag!r} was silently turned into a version"
    assert value == "", "a refused derivation still wrote a version for something to consume"


def test_no_consumer_derives_its_own_version() -> None:
    """The shape, not the instance: nothing may ask the question a second way.

    ⚠ **`main` must not appear as a version test anywhere.** Hardcoding one branch name is the
    Linux half of this defect, and it passes every test written about `main`.
    """
    consumers = [
        s
        for s in _build_steps()
        if s.get("id") != "version"
        and ("MyAppVersion" in str(s.get("run", "")) or "--version" in str(s.get("run", "")))
    ]

    assert len(consumers) == 2, (
        f"expected the installer and the .deb to consume the version, found {len(consumers)}"
    )
    for step in consumers:
        run = str(step["run"])
        assert "steps.version.outputs.value" in run, (
            f"{step.get('name')!r} does not read the shared version"
        )
        hardcoded = (
            f"{step.get('name')!r} tests for a hardcoded branch name. The question is whether the "
            f"ref is a version tag, not whether it is one particular branch."
        )
        assert '"main"' not in run, hardcoded
        assert "'main'" not in run, hardcoded


def test_no_build_step_names_an_artefact_after_the_ref() -> None:
    """⚠ The whole build job, not only the two packagers. `(aex)`

    The installer and the `.deb` were fixed first, and the **archive** was still
    `truestill-${{ github.ref_name }}-${RUNNER_OS}` - found by reading the artefact list of the
    very run that proved the other two. One fix, three artefacts, and the third was missed because
    the search was for "version" rather than for "ref name in a filename".

    ⚠ **The distinction this asserts is expression versus environment.** The version step reads
    `$GITHUB_REF_NAME` - it is the one place entitled to ask what the ref is called. Every other
    step must read the *resolved* value, so what is banned is the `github.ref_name` **context
    expression**, not the string.

    The publish job is deliberately out of scope: `gh release create "${{ github.ref_name }}"`
    names a GitHub release after its tag, which is correct and is not a filename.
    """

    # ⚠ COMMENTS STRIPPED FIRST, and this cost a red run here exactly as it did in
    # `test_every_exiftool_install_is_guarded`: the fixed step EXPLAINS what it used to
    # interpolate, so a bare search matches the prose arguing against the defect and reports the
    # opposite of the truth. Assert the statement, never an identifier that also appears in the
    # target's own commentary.
    def _code(step: dict[str, Any]) -> str:
        lines = str(step.get("run", "")).splitlines()
        return "\n".join(line for line in lines if not line.strip().startswith("#"))

    offenders = [s.get("name") for s in _build_steps() if "github.ref_name" in _code(s)]

    assert not offenders, (
        f"these build steps interpolate the ref name: {offenders}. On a dispatch that puts a "
        f"branch name in a filename; on a tag it puts a `v` prefix on one artefact and not its "
        f"siblings. Read `steps.version.outputs.value` instead."
    )
