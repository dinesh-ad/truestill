"""A path the filesystem refused is never reported as absent - asserted as the PRODUCT's answer.

**The defect, `(aey)`.** On Python 3.14 `Path.is_dir()`, `exists()` and `is_file()` stop raising on
``EACCES`` and return ``False`` ([cpython#144525](https://github.com/python/cpython/issues/144525));
`is_dir()` is now literally ``return os.path.isdir(self)``, and `os.path` has always swallowed
``OSError``. pathlib was the outlier this code relied on. Five sites read that ``False`` as *not
there*, and `probe_dir` - the function written to keep *absent* and *refused* apart - answered
``MISSING``, which on this product's surfaces means **creatable**.

⚠ **WHY A THIRD TEST FILE WHEN `test_unreadable_paths.py` ALREADY COVERS THIS.** Because both of
its mechanisms are blind to it, in two different ways, and one of them survives the fix:

* `_really_locked` (`test_unreadable_paths.py:62-78`) establishes *"did chmod really deny?"* by
  calling **`is_dir()` - the subject**. On 3.14 it concludes the OS did not deny and the test
  **skips**. `ENGINEERING_STANDARD.md` §4, fifty-seventh member.
* `_deny` (`:42-58`) **monkeypatches `Path.stat`/`is_dir`/`exists` to raise**, so the contract
  assertions run against a fake that simulates the *pre*-3.14 stdlib. They pass on 3.14 while the
  product is broken. That file's Windows coverage depends on the fake, so it stays - but a test
  that replaces its subject can never see the subject change.

Everything below asserts what **Truestill** answers, never what CPython does, so it stays correct
after the fix instead of needing to be inverted.
"""

from __future__ import annotations

import errno
import os
import stat as stat_module
import sys
from pathlib import Path
from typing import Any

import pytest
from truestill_app.service.path_probe import PathReach, nearest_device, probe_dir
from truestill_core.destinations.base import DestinationError
from truestill_core.destinations.local import LocalDestination
from truestill_core.path_reach import Reach, reach

_POSIX_ONLY = pytest.mark.skipif(
    sys.platform == "win32", reason="a mode of 000 does not deny the owner on Windows"
)


def _swallowing_predicates(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make the boolean predicates behave the way Python 3.14 makes them behave.

    ⚠ **This simulates the NEW stdlib, which is the exact inverse of `_deny`'s mistake.** `_deny`
    freezes the old behaviour and so cannot notice it changing; this freezes the new behaviour and
    asserts our answer is the same either way. What it pins is a property - *the verdict does not
    depend on the boolean predicates* - rather than a version, which is why it kept working
    unchanged across the 3.13 to 3.14 move and why it runs on the Windows lane, where a real
    `chmod 000` proves nothing.

    ⚠ **Each replacement calls `self.stat()` rather than `os.path`, and that is load-bearing.**
    The first version delegated to `os.path.isdir`, which reaches `os.stat` directly and so walked
    straight past the refusal this fixture installs - the predicates answered *True* where real
    3.14 answers *False*, and the `nearest_device` test passed against unfixed code. Routing
    through `stat` reproduces 3.14's actual semantics (*swallow everything the stat raises*) and
    keeps the refusal visible.

    `stat` itself is deliberately left alone: it raises on both versions and is what the fix uses.
    """

    def is_dir(self: Path, **_kwargs: Any) -> bool:
        try:
            return stat_module.S_ISDIR(self.stat().st_mode)
        except (OSError, ValueError):
            return False

    def is_file(self: Path, **_kwargs: Any) -> bool:
        try:
            return stat_module.S_ISREG(self.stat().st_mode)
        except (OSError, ValueError):
            return False

    def exists(self: Path, **_kwargs: Any) -> bool:
        try:
            self.stat()
        except (OSError, ValueError):
            return False
        return True

    monkeypatch.setattr(Path, "is_dir", is_dir)
    monkeypatch.setattr(Path, "is_file", is_file)
    monkeypatch.setattr(Path, "exists", exists)


def _refuse_stat(monkeypatch: pytest.MonkeyPatch, target: Path) -> None:
    """Refuse `Path.stat` for one path, as a locked parent directory does."""
    original = Path.stat

    def patched(self: Path, *args: Any, _orig: Any = original, **kwargs: Any) -> Any:
        if self == target:
            raise PermissionError(errno.EACCES, "Permission denied", str(self))
        return _orig(self, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", patched)


def test_probe_dir_calls_a_refused_folder_unreadable_when_the_predicates_swallow(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """⚠ THE DISCRIMINATOR, and it runs on every lane including Windows.

    Written while the project ran 3.13, where it **failed against unfixed code** - that is what
    made it a discriminator rather than a restatement. The fixture is what earns that, not the
    interpreter: it makes the predicates swallow, so the test asks the same question on 3.14,
    which now behaves that way for real.

    `MISSING` is not a smaller answer than `UNREADABLE` here - it is a different one. It means
    *nothing is there, and you may create it*, so the app offers to create a folder that already
    exists and will refuse the attempt in exactly the same way. `path_probe`'s own docstring: *"a
    folder that exists and will not answer cannot be created - the create fails the same way the
    probe did - so offering it sends the user round a loop."*
    """
    denied = tmp_path / "denied"
    denied.mkdir()
    _refuse_stat(monkeypatch, denied)
    _swallowing_predicates(monkeypatch)

    assert probe_dir(denied) is PathReach.UNREADABLE, (
        "a folder the filesystem refused was reported as MISSING - absent and creatable. "
        "probe_dir's verdict must come from stat(), which raises on every supported version, "
        "not from the boolean predicates, which stopped raising in 3.14."
    )


def test_nearest_device_still_stops_at_a_refused_folder_when_the_predicates_swallow(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The second half of the same fix. Walking past it answers with a different folder's device.

    A missing folder *should* be answered from its nearest existing parent - that is the ordinary
    case, and the reason this cannot simply refuse everything it cannot stat.
    """
    denied = tmp_path / "denied"
    denied.mkdir()

    not_yet = nearest_device(tmp_path / "not-yet" / "deeper")
    assert not_yet.device_id is not None, "fixture check: a missing folder answers from its parent"

    _refuse_stat(monkeypatch, denied)
    _swallowing_predicates(monkeypatch)
    blocked = nearest_device(denied)

    assert blocked.device_id is None, "it borrowed an ancestor's device for a folder it cannot read"
    assert blocked.blocked_at == denied, "the folder that blocked the walk must be nameable"


@_POSIX_ONLY
def test_a_real_refused_folder_is_unreadable_on_this_interpreter(tmp_path: Path) -> None:
    """The same claim against a real `chmod 000`, with no monkeypatching at all.

    ⚠ **The precondition is asked through `os.stat`, which the subject does not share.** Asking
    it through `is_dir()` - as `_really_locked` does - is what turns this into a skip on 3.14:
    the probe answers *"the OS did not deny"*, which is false, and the assertion never runs.

    ⚠ **This test could not fail on 3.13, where the defect did not exist**, so its failing-first
    proof was run under 3.14 out of tree while the project still shipped 3.13. That is no longer a
    caveat: 3.14 is what runs here now, so this test meets the defect on the interpreter it was
    written for and is evidence rather than a regression guard.
    """
    locked = tmp_path / "locked"
    (locked / "inner").mkdir(parents=True)
    locked.chmod(0o000)
    try:
        try:
            # ⚠ `os.stat`, not `Path.stat` and certainly not `is_dir`: the precondition must not
            # share a mechanism with the subject. PTH116 suppressed for that reason.
            os.stat(locked / "inner")  # noqa: PTH116
            denied = False
        except PermissionError:
            denied = True
        if not denied:
            pytest.skip("running as root, or a filesystem that ignores the mode")

        assert probe_dir(locked / "inner") is PathReach.UNREADABLE
    finally:
        locked.chmod(0o755)


@_POSIX_ONLY
def test_the_absent_family_stays_absent(tmp_path: Path) -> None:
    """⚠ The cry-wolf half, and the one that keeps this a forward-fix rather than a change.

    Not every `stat` failure means *refused*. CPython 3.13's `pathlib._abc._ignore_error` treats
    ``ENOENT``, ``ENOTDIR``, ``EBADF`` and ``ELOOP`` as *not there*, and `probe_dir` inherited
    that. A fix that read "any OSError from stat" as refusal would change 3.13's answer for a
    symlink loop from `MISSING` to `UNREADABLE` - measured, it is `missing` today.
    """
    loop = tmp_path / "loop"
    other = tmp_path / "other"
    loop.symlink_to(other)
    other.symlink_to(loop)

    assert probe_dir(loop) is PathReach.MISSING, (
        "a symlink loop (ELOOP) became UNREADABLE; that is a behaviour change on the version we "
        "ship, not a forward fix"
    )
    assert probe_dir(tmp_path / "nothing-here") is PathReach.MISSING
    a_file = tmp_path / "a-file.txt"
    a_file.write_text("x", encoding="utf-8")
    assert probe_dir(a_file) is PathReach.NOT_A_DIRECTORY


def test_a_path_that_cannot_be_encoded_is_absent_not_refused() -> None:
    """The other half of the absent family, and it is a `ValueError`, not an `OSError`.

    `Path.stat()` raises `ValueError` for a NUL byte on both versions while `is_dir()` returns
    `False`. A fix that only caught `OSError` would let that escape `probe_dir` as an exception -
    a behaviour change on 3.13, in a function whose whole contract is to answer rather than raise.
    """
    assert probe_dir(Path("/tmp/truestill-nul\x00name")) is PathReach.MISSING


# --- the other three sites, each asserting its OWN answer -----------------------------------
#
# `probe_dir` is the one designed for this distinction; it is not the only one that depends on it.
# Each test below drives the real call site with the predicates made to swallow, and asserts what
# that site promises - not what pathlib does.


def test_a_destination_that_refuses_is_raised_not_reported_as_free(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`destinations/local.py` deliberately raises. Answering `False` tells the WRITE path a slot
    is free when nothing established that, and the write is the next thing that happens."""
    root = tmp_path / "dest"
    (root / "Camera").mkdir(parents=True)
    target = root / "Camera" / "a.jpg"
    target.write_bytes(b"x")

    destination = LocalDestination(root)
    assert destination.exists("Camera/a.jpg") is True, "fixture check"
    assert destination.exists("Camera/absent.jpg") is False, "a genuinely free slot stays free"

    _refuse_stat(monkeypatch, target)
    _swallowing_predicates(monkeypatch)

    with pytest.raises(DestinationError):
        destination.exists("Camera/a.jpg")


def test_a_sidecar_that_cannot_be_looked_at_is_not_reported_as_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`date_rescue`'s own words: *"cannot look, which is not 'nothing there'"*.

    Asserted through `reach` at the exact path the service probes, because the service itself
    needs a catalog and a set of shas to run and that machinery is not what changed.
    """
    sidecar = tmp_path / "photo.jpg.original"
    sidecar.write_bytes(b"x")
    assert reach(sidecar) is Reach.FILE, "fixture check"

    _refuse_stat(monkeypatch, sidecar)
    _swallowing_predicates(monkeypatch)

    assert reach(sidecar) is Reach.REFUSED, (
        "a sidecar on an unreadable mount would be reported as absent, and the run would tell "
        "the user their original is gone"
    )


def test_a_refused_sample_is_not_evidence_that_a_drive_is_not_the_library(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`drive_adoption`'s own words: *"not evidence either way"*.

    ⚠ This one changes a verdict a user acts on. The presence tally is compared against
    `PRESENCE_THRESHOLD`, so counting refusals as absences does not merely under-report - it can
    flip an adoption offer to NO_MATCH for a drive that is simply not answering.
    """
    sample = tmp_path / "Camera" / "2019" / "a.jpg"
    sample.parent.mkdir(parents=True)
    sample.write_bytes(b"x")
    assert reach(sample) is Reach.FILE, "fixture check"

    _refuse_stat(monkeypatch, sample)
    _swallowing_predicates(monkeypatch)

    assert reach(sample) is Reach.REFUSED, "a refused sample counted as absent evidence"
