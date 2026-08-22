"""A staging path is private to the process that made it. `(aaw)`

**Measured, not reasoned.** Two `organize --apply` runs writing one destination used to stage into
**one** `.partial`, because the staging path was `target.name + STAGING_SUFFIX` - a pure function
of the destination. One process then renamed it and reported success while the file held the other
process's bytes. On real photographs, 2 of 9 concurrent attempts lost **99** and **45** organized
copies; the loser failed loudly with `ENOENT` on a `.partial` that was no longer there, which is
what the `FAILED` lines in those runs were.

⚠ **This fixes the shared file, NOT who wins the name.** Both runs still resolve to the same
target and one still renames over the other - which after this change is *quieter*, because both
renames now succeed and both processes exit 0. That residual is `(aaw)`'s lock, and it is the
reason unique staging was ruled *"must not ship alone"*.

**Why the token goes before the suffix.** `.partial` ending the name is a contract two other
places depend on: `cli`'s rescan picks debris with `path.name.endswith(STAGING_SUFFIX)`, and
`scan_source` must keep classifying it as an unrecognized extension rather than media.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from truestill_core import safe_copy

_TOKEN_SOURCE = "from truestill_core.safe_copy import staging_path\nfrom pathlib import Path\nprint(staging_path(Path('/d/IMG_0001.jpg')))"


def test_the_staged_name_is_not_derived_from_the_target_alone() -> None:
    """The defect itself, stated as the thing that must never be true again."""
    target = Path("/d/IMG_0001.jpg")

    staged = safe_copy.staging_path(target)

    assert staged != target.with_name(target.name + safe_copy.STAGING_SUFFIX), (
        "a staging path derived from the target alone is shared by every process that computes it"
    )


def test_the_staged_name_keeps_every_contract_that_depends_on_it() -> None:
    """Sibling, names its target, and still ENDS in the suffix - all three are load-bearing."""
    target = Path("/d/sub/IMG_0001.jpg")

    staged = safe_copy.staging_path(target)

    assert staged.parent == target.parent, "the rename must stay within one filesystem"
    assert staged.name.startswith(target.name), "debris must say what it was staging"
    assert staged.name.endswith(safe_copy.STAGING_SUFFIX), (
        "rescan picks debris with endswith(STAGING_SUFFIX); a token after it would hide the litter"
    )
    assert Path(staged.name).suffix == safe_copy.STAGING_SUFFIX, (
        "scan_source must see an unrecognized extension, not a media one"
    )


def test_the_same_process_is_stable_across_calls() -> None:
    """One token per process, so a crashed run's litter is attributable to that run."""
    target = Path("/d/IMG_0001.jpg")

    assert safe_copy.staging_path(target) == safe_copy.staging_path(target)


def test_two_real_processes_never_compute_the_same_staging_path() -> None:
    """⚠ **Two real interpreters, because that is the thing being claimed.**

    A same-process test cannot see this: the token is a module global, so it is trivially equal to
    itself. Only a second process can show it differs, and a second process is exactly what the
    measured failure needed.
    """
    runs = [
        subprocess.run(
            [sys.executable, "-c", _TOKEN_SOURCE], capture_output=True, text=True, check=True
        ).stdout.strip()
        for _ in range(2)
    ]

    assert runs[0] != runs[1], (
        f"two processes computed the SAME staging path ({runs[0]}) - this is the measured defect, "
        "where both wrote into one file and one reported success holding the other's bytes"
    )
    for produced in runs:
        assert produced.endswith(safe_copy.STAGING_SUFFIX)
        assert Path(produced).name.startswith("IMG_0001.jpg")
