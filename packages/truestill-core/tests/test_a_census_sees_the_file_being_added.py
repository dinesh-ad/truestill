"""`repo_sources` must see the file the current commit is adding. **The whole point of it.**

⚠ **A SHAPE ASSERTION WOULD NOT BE ENOUGH, so this creates a real untracked file.** Checking that
the argument list contains `--others` proves the string is there, not that the listing widens -
and the defect being closed was precisely a listing that looked right and was blind. So a file is
written into the repository, enumerated, and removed in a `finally`.

The state under test cannot be reached any other way: on a clean tree there is nothing untracked,
so a `repo_sources` with `--others` removed would pass every other test in the suite. That is why
this file exists rather than the guarantee resting on the twelve callers.
"""

from __future__ import annotations

import subprocess

import repo_sources

#: Written, enumerated and removed. Under `packages/` so it is inside a pathspec the real guards
#: use, and named so that a leaked one is obviously this test's and obviously deletable.
_PROBE = (
    repo_sources.REPO
    / "packages"
    / "truestill-core"
    / "src"
    / "truestill_core"
    / "_census_probe.py"
)


def test_an_untracked_source_file_is_in_the_listing() -> None:
    """The hole, closed. This file is in no index; the census must still find it."""
    _PROBE.write_text("# written by a test, removed in a finally\n", encoding="utf-8")
    try:
        relative = _PROBE.relative_to(repo_sources.REPO).as_posix()
        assert relative in repo_sources.paths("packages/*/src/**/*.py")
        assert relative in repo_sources.paths()
        assert _PROBE in repo_sources.files("packages/*/src/**/*.py")
    finally:
        _PROBE.unlink(missing_ok=True)


def test_the_probe_really_was_invisible_to_the_index() -> None:
    """⚠ **The anti-vacuity half, and without it the test above proves nothing.**

    If the probe were somehow tracked, the assertion above would pass on a `repo_sources` that had
    never been widened at all. So the same file is checked against git's own index: it must be
    absent there and present in the listing, which is the difference this module exists for.
    """
    _PROBE.write_text("# written by a test, removed in a finally\n", encoding="utf-8")
    try:
        relative = _PROBE.relative_to(repo_sources.REPO).as_posix()
        indexed = subprocess.run(
            ["git", "ls-files", "--", relative],
            cwd=repo_sources.REPO,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.split()
        assert indexed == [], "the probe is tracked, so this proves nothing about untracked files"
        assert relative in repo_sources.paths()
    finally:
        _PROBE.unlink(missing_ok=True)


def test_an_ignored_file_stays_invisible() -> None:
    """⚠ **The cry-wolf half: a guard that went red on scratch would be worse than the hole.**

    `.gitignore` designates `.scratch/` for *"local scratch notes and throwaway files"*, and
    `--exclude-standard` is what keeps that promise. Without it every developer's scratch would
    enter twelve guards at once.
    """
    scratch = repo_sources.REPO / ".scratch"
    probe = scratch / "notes.py"
    scratch.mkdir(exist_ok=True)
    probe.write_text("# scratch: truestill drives --init /somewhere\n", encoding="utf-8")
    try:
        assert probe.is_file(), "the probe was not written, so its absence below is free"
        assert probe.relative_to(repo_sources.REPO).as_posix() not in repo_sources.paths()
    finally:
        probe.unlink(missing_ok=True)
        if scratch.is_dir() and not any(scratch.iterdir()):
            scratch.rmdir()


def test_every_path_returned_can_actually_be_opened() -> None:
    """Every path handed to a caller is a readable file, so a guard can open it without guarding.

    ⚠ **This is weaker than it looks, and the weakness is stated rather than implied.** The
    filter it exercises is there for a path **staged for deletion**, and a mutation run proved
    nothing here catches that: removing the filter survives the suite, because reaching the state
    needs a staged deletion and staging one would mutate the shared index while `make check` runs
    fourteen workers against it. `repo_sources`' own docstring carries the full reason.
    """
    listed = repo_sources.files("*.py")

    assert listed, "an empty listing would make the loop below free"
    assert all(path.is_file() for path in listed)
