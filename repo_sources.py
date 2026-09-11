"""What a guard should look at: **everything a reviewer would see, not just the index.**

⚠ **`git ls-files` ALONE LISTS THE INDEX, SO A BRAND-NEW FILE IS INVISIBLE UNTIL IT IS ADDED -
which is after the `make check` that was supposed to catch it.** `test_no_incidental_naming` found
this first and wrote it down as *"a false green with a delay fuse: the run that could act on it
passes, and the failure arrives on the next one, or on CI."*

**It is not hypothetical, and the fuse went off.** Stage 1 of the restore arc
(`truestill_core.carried`) shipped a suggestion the runtime refuses - `truestill drives --init`
without `--label` - straight past `test_a_suggested_command_can_be_run`, because the file was
untracked when the gate ran. `make check` was green, the commit landed, and the guard only saw it
on the *next* run, once the file was tracked. The turn's own record said the gate was green. It
was green and blind.

**So the enumeration is `--cached --others --exclude-standard`**, which is the working tree as a
reviewer meets it: tracked files, plus untracked ones, minus anything `.gitignore` covers.

⚠ **WHAT THIS DELIBERATELY DOES NOT SEE, and it is the reason the remedy is safe rather than
noisy**: `.gitignore` already designates `.scratch/` for *"local scratch notes and throwaway
files"*, and covers every build artifact, cache and vendored tree. A guard that went red on a
developer's scratch file would be worse than the hole it closes, so scratch keeps a home that
stays invisible - it simply has to be the designated one.

⚠ **AND IT DOES NOT SEE A FILE STAGED FOR DELETION.** ``--cached`` lists index entries whose
working-tree file may be gone, and a guard that opened one would crash on a state that is not a
defect. Entries with nothing on disk are dropped here, once, rather than in each caller.

⚠ **That last filter is defended by argument, not by a test, and a mutation run is what
established it.** Removing it survives the whole suite: reaching the state needs a path staged for
deletion, and staging one would mutate the **shared index** while `make check` runs fourteen
workers in parallel - every other census here reads that index, so the test would make its
neighbours flaky. A guard that causes intermittent failures elsewhere is worse than an unproven
line, so the line stays and this paragraph is the record of why it is unproven.

**Not `pathlib` for the pathspec results** - `git ls-files` emits forward slashes on every
platform, so :func:`paths` returns POSIX strings that are stable on Windows. :func:`files` is the
absolute form for callers that read bytes.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parent

#: The listing every caller here uses. ⚠ **`--others` is what closes the hole**; without it this
#: module would be `git ls-files` with extra words.
_ARGS = ("--cached", "--others", "--exclude-standard", "-z")


def paths(*pathspec: str) -> list[str]:
    """Repo-relative POSIX paths matching ``pathspec``, deduplicated and sorted.

    No pathspec means the whole repository. Raises rather than returning nothing when git itself
    fails, so a missing `.git` is an error and not a quiet empty census - `ENGINEERING_STANDARD`
    §4's fifty-second member. **The empty-subject assertion stays with each caller**, because only
    the caller knows whether zero rows is impossible or merely unexpected for its own pathspec.
    """
    out = subprocess.run(
        ["git", "ls-files", *_ARGS, "--", *pathspec],
        cwd=REPO,
        capture_output=True,
        # UTF-8 rather than `text=True`, which decodes with the machine locale - cp1252 on a
        # Windows runner - and mangles any path with a non-ASCII character in it.
        check=True,
    ).stdout.decode("utf-8")
    seen = {line for line in out.split("\0") if line}
    return sorted(rel for rel in seen if (REPO / rel).is_file())


def files(*pathspec: str) -> list[Path]:
    """:func:`paths`, as absolute paths, for callers that read the bytes."""
    return [REPO / rel for rel in paths(*pathspec)]
