"""A folder cleanup could not look at is never offered for removal, and never crashes the plan.

**Found by sweeping, not by a failure.** `(aez)` was two bare `is_file()` probes in `reclaim.py`
with the guarded helper three functions above them. Two adjacent misses in one module is evidence
that nobody had swept the area rather than that those were the only two - so the delete-adjacent
paths were read end to end. `cleanup.plan_cleanup` is the third, `(afb)`.

⚠ **`plan_cleanup` decides which of a user's folders get sent to the trash**, and its own
docstring calls itself *"Pure: reads, never writes"* - the guarantee that makes the preview safe
to run. A probe that raises breaks that guarantee in the loudest possible way: on 3.13 a folder
whose **parent** refuses made `folder.is_dir()` raise, uncaught, and the whole plan died with a
traceback at the end of an otherwise successful organize.

**And 3.14 masks it, exactly as it masked `(aez)`.** There `is_dir()` returns `False`, so the
folder is silently `continue`d - conservative, but indistinguishable from *"already dealt with"*,
which is what `continue` is reserved for in that loop.

**Absent and refused are different answers here too.** A folder that no longer exists was
genuinely handled by someone; a folder that will not answer was not. The first is skipped, the
second is reported `OCCUPIED` - the answer `_classify_with` already gives when `iterdir` refuses,
so the two unreadable cases finally agree.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from truestill_core.cleanup import Tier, plan_cleanup

_POSIX_ONLY = pytest.mark.skipif(
    sys.platform == "win32", reason="a mode of 000 does not deny the owner on Windows"
)


@_POSIX_ONLY
def test_a_folder_whose_parent_refuses_does_not_crash_the_plan(tmp_path: Path) -> None:
    """⚠ The regression. It **raises** on 3.13 before the fix - a traceback, not a bad plan."""
    (tmp_path / "Camera" / "2013").mkdir(parents=True)
    (tmp_path / "Camera").chmod(0o000)
    try:
        try:
            os.stat(tmp_path / "Camera" / "2013")  # noqa: PTH116 - independent of the subject
            pytest.skip("running as root, or a filesystem that ignores the mode")
        except PermissionError:
            pass

        plan = plan_cleanup(tmp_path, ["Camera/2013"])

        assert [c.relative for c in plan.candidates] == ["Camera/2013"], (
            "a folder that refused was dropped from the plan entirely, which is the answer "
            "reserved for one somebody has already dealt with"
        )
        assert plan.candidates[0].tier is Tier.OCCUPIED
        assert plan.removable == [], "a folder Truestill could not look at was offered for removal"
    finally:
        (tmp_path / "Camera").chmod(0o755)


def test_a_folder_that_is_genuinely_gone_is_still_skipped(tmp_path: Path) -> None:
    """The cry-wolf half, and the distinction the fix rests on.

    `plan_cleanup`'s docstring: *"a folder that no longer exists is simply skipped - a previous
    cleanup, or the user, may already have dealt with it."* That must keep working, or every
    re-run of cleanup grows a row for every folder it removed last time.
    """
    (tmp_path / "Camera").mkdir()

    plan = plan_cleanup(tmp_path, ["Camera/gone", "Camera/also-gone"])

    assert plan.candidates == [], "an absent folder is not the same as one that refused"


def test_an_ordinary_empty_folder_is_still_removable(tmp_path: Path) -> None:
    """The other cry-wolf half: the feature still works."""
    (tmp_path / "Camera" / "2013").mkdir(parents=True)

    plan = plan_cleanup(tmp_path, ["Camera/2013"])

    assert [c.tier for c in plan.candidates] == [Tier.EMPTY]
    assert [c.relative for c in plan.removable] == ["Camera/2013"]
