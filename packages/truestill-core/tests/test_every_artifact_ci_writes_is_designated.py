"""Anything CI writes INTO the working tree must be invisible to a whole-repo census.

⚠ **WRITTEN AFTER IT TOOK DOWN A NIGHTLY.** `ci.yml`'s `Pytest` step writes a junit report at the
repo root; `Pytest (different collection order)` runs in the SAME job afterwards and censuses the
whole repo. A report names every test it ran, and `test_layout_scheme.py`'s decommissioned-layout
guard forbids strings that three test IDs spell out deliberately - so the second run read the
first run's report and failed. Run 34681980628, 2026-09-12.

**Five pushes were green first**, because that step runs on `schedule` and `pull_request` only.
And it was invisible before `1867be3` widened `repo_sources` from `git ls-files` to `--others`:
widening a census is what turns every undesignated artifact into a latent failure.

**`.gitignore` is the designated mechanism** - `repo_sources`'s docstring states it - so this
asserts the two stay in step rather than asserting one particular filename, which would go stale
the moment somebody adds a third reporter.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[3]
_CI = _ROOT / ".github" / "workflows" / "ci.yml"
_MAKEFILE = _ROOT / "Makefile"

#: `--junitxml=<path>`, and pytest's `--output <path>` for the browser lane's traces.
_WRITES = (
    re.compile(r"--junitxml=(\S+)"),
    re.compile(r"--output\s+(\S+)"),
)


def _artifact_paths() -> set[str]:
    found: set[str] = set()
    for source in (_CI, _MAKEFILE):
        text = source.read_text(encoding="utf-8")
        for pattern in _WRITES:
            for match in pattern.findall(text):
                cleaned = match.strip("\"'").split("$")[0].strip()
                if cleaned and not cleaned.startswith("-"):
                    found.add(cleaned)
    return found


def _ignores(relative: str) -> bool:
    """`git check-ignore` is the authority, not a string search of `.gitignore`.

    A pattern can cover a path through a parent directory, a negation or a glob; only git knows.
    Matching text would pass on a `.gitignore` that mentions the name and excludes nothing, which
    is the failure this file exists about.
    """
    return (
        subprocess.run(
            ["git", "check-ignore", "-q", "--no-index", relative],
            cwd=_ROOT,
            capture_output=True,
            check=False,
        ).returncode
        == 0
    )


def _is_hidden_from_a_census(relative: str) -> bool:
    """Whether a census could reach anything written at this path.

    ⚠ **THE QUESTION IS ABOUT FILES, NOT ABOUT THE PATH.** `repo_sources.paths()` runs
    `git ls-files --others`, which lists files and never bare directories - so for a
    directory-shaped artifact the thing to ask about is a file INSIDE it. `tests/e2e/.artifacts/`
    is ignored as a directory pattern and `check-ignore` answers False for the bare name, which
    the first draft of this guard reported as a hole. It is not one: nothing can be listed at
    that path except files under it, and those are covered.
    """
    if Path(relative).suffix:
        return _ignores(relative)
    return _ignores(f"{relative}/probe") and _ignores(f"{relative}/")


def test_the_census_would_see_something_if_it_were_not_designated() -> None:
    """The anti-vacuity anchor: `git check-ignore` really does answer False for a source file.

    Without this, a `_is_ignored` that always returned True would satisfy every assertion below.
    """
    assert not _is_hidden_from_a_census("Makefile")
    assert not _is_hidden_from_a_census("packages/truestill-core/src/truestill_core/layout.py")


def test_ci_writes_at_least_one_artifact_into_the_tree() -> None:
    """A guard over an empty set passes by finding no violations in nothing to check."""
    assert _artifact_paths(), (
        "no `--junitxml` or `--output` found in ci.yml or the Makefile, so the test below has "
        "no subject - the flags were renamed and this guard is now aimed at nothing"
    )


@pytest.mark.parametrize("relative", sorted(_artifact_paths()))
def test_each_artifact_ci_writes_is_hidden_from_a_whole_repo_census(relative: str) -> None:
    """⚠ The one that would have caught it. `test-results.xml` was undesignated for months and
    cost a nightly the day a census widened to untracked files."""
    assert _is_hidden_from_a_census(relative), (
        f"CI writes `{relative}` into the working tree and `.gitignore` does not cover it, so "
        "`repo_sources.paths()` lists it and every whole-repo guard reads it. Add it to "
        "`.gitignore` - that file is the designated mechanism, not an exclusion list in a test."
    )
