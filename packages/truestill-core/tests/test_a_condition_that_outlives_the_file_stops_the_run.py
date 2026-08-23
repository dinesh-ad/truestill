"""A full disk is not a per-file fact. `(agi)`

`(afw)` Stage 4 made both surfaces continue past a per-file failure, which is
`ENGINEERING_STANDARD.md` §4 Errors and is right. Neither classified the failure, so **a filling
destination was treated exactly like one unreadable photo**: N wasted attempts and N record
entries reading `failed` when the truth is one condition at file 12.

**The discriminator is not which side failed. It is whether the next file will hit it too.** The
errno table in `drive_unwritable.persists_for_the_run` is the implementation of that predicate,
never the rule - so an errno nobody has reasoned about continues, because continuing is the
recoverable mistake and aborting a good run is not.

⚠ **WHAT IS PROVEN HERE AND WHAT IS ASSUMED - read this before trusting a green lane.**

* **Proven on Linux, with a real kernel `ENOSPC`.** `/dev/full` returns `ENOSPC` on write, so the
  errno arrives through `shutil.copy2` from the kernel rather than from a constructed exception.
  A synthesised `OSError` proves the *classifier*; it says nothing about *delivery*, and those are
  two properties.
* ⚠ **Assumed on Windows, and the assumption is named.** The link from `ERROR_DISK_FULL` (112) and
  `ERROR_HANDLE_DISK_FULL` (39) to `errno.ENOSPC` is Python's, documented but **not exercised by
  any test here**. What a green Windows lane proves is that the errno-to-verdict mapping holds; it
  does **not** prove Windows delivers that errno. The gap is recorded in `(agi)`.
"""

from __future__ import annotations

import errno
import os
import shutil
import sys
from pathlib import Path

import pytest
from truestill_core.drive_unwritable import persists_for_the_run

#: `/dev/full` is Linux-specific. One condition, never two stacked decorators - each is evaluated
#: at import, so a second referencing a POSIX-only name raises on Windows and the WHOLE MODULE
#: fails to collect, taking every test above with it. `PROJECT_STATUS.md` §5.
_HAS_DEV_FULL = pytest.mark.skipif(
    not Path("/dev/full").exists(), reason="/dev/full is Linux-specific"
)


@_HAS_DEV_FULL
def test_a_real_kernel_enospc_is_classified_as_persistent(tmp_path: Path) -> None:
    """⚠ **The delivery half, and the reason this test is not a `pytest.raises` over a mock.**

    The `OSError` here is raised by the kernel, through `shutil`, on a write that genuinely had
    nowhere to go. Nothing in this test names `ENOSPC`: it asserts what the classifier says about
    an error the operating system produced.
    """
    source = tmp_path / "a.bin"
    source.write_bytes(b"x" * (1024 * 1024))

    # The errno is the subject and is asserted below; matching on the OS's own wording
    # would be testing the OS (`ENGINEERING_STANDARD.md` §4's thirty-ninth member).
    with pytest.raises(OSError) as raised:  # noqa: PT011 - errno asserted, not text
        shutil.copyfile(source, "/dev/full")

    assert raised.value.errno == errno.ENOSPC, (
        f"/dev/full did not deliver ENOSPC; the delivery half is untested: {raised.value!r}"
    )
    assert persists_for_the_run(raised.value) is True


def test_the_windows_disk_full_errno_is_persistent_too() -> None:
    """⚠ **THE MAPPING IS PROVEN; THE DELIVERY IS ASSUMED. Do not read this as more.**

    On Windows a full disk arrives as `ERROR_DISK_FULL` (112) or `ERROR_HANDLE_DISK_FULL` (39),
    and **Python** - not this code - translates those to `errno.ENOSPC`. This asserts only that an
    `ENOSPC` is judged persistent whatever produced it. **That the Windows kernel delivers
    `ENOSPC` through `shutil` is not exercised anywhere in this suite**, and a green Windows lane
    must not be read as evidence of it.

    Making it real would need a small full volume on the runner - `diskpart` can create and attach
    one and the runners do have administrator - and that is costed in `(agi)` rather than built.
    """
    assert persists_for_the_run(OSError(errno.ENOSPC, "No space left on device")) is True


@pytest.mark.parametrize(
    ("code", "why"),
    [
        (errno.EDQUOT if hasattr(errno, "EDQUOT") else errno.ENOSPC, "a quota is external"),
        (errno.EIO, "a failing device is not a property of one file"),
        (errno.EROFS, "a read-only mount stays read-only"),
    ],
)
def test_conditions_that_outlive_the_file_stop_the_run(code: int, why: str) -> None:
    assert persists_for_the_run(OSError(code, "x")) is True, why


@pytest.mark.parametrize(
    ("code", "why"),
    [
        (errno.EACCES, "one file's permissions are one file's"),
        (errno.EPERM, "same, and it shares `REFUSED` with EROFS which does NOT continue"),
        (errno.ENOENT, "a vanished source is one file somebody moved"),
        (errno.ENAMETOOLONG, "unreasoned errnos continue - that is the rule, not an omission"),
        (errno.EFBIG, "the FAT32 size ceiling is a fact about this file"),
    ],
)
def test_conditions_local_to_one_file_do_not(code: int, why: str) -> None:
    """⚠ **CRY-WOLF HALF.** A predicate returning `True` for everything satisfies every row above
    and is far worse than the defect: it turns one unreadable photo into a stopped backup."""
    assert persists_for_the_run(OSError(code, "x")) is False, why


def test_eacces_and_erofs_share_a_classification_and_must_not_share_a_verdict() -> None:
    """The one branch `classify_unwritable` cannot decide alone.

    Both are `Unwritable.REFUSED`. Collapsing them - either way - is a single-character change
    that looks tidy and is wrong in one direction or the other.
    """
    assert persists_for_the_run(OSError(errno.EROFS, "read-only")) is True
    assert persists_for_the_run(OSError(errno.EACCES, "denied")) is False


@pytest.mark.skipif(
    sys.platform == "win32" or os.geteuid() == 0,
    reason="chmod 000 does not deny the owner on Windows, and root ignores it",
)
def test_a_real_permission_error_is_not_persistent(tmp_path: Path) -> None:
    """The other delivery half: a real `EACCES` from the kernel, not a constructed one.

    Without this, every non-persistent row rests on an `OSError` this test built - which proves
    the table and not that the table is ever reached with these codes.
    """
    locked = tmp_path / "locked.bin"
    locked.write_bytes(b"x" * 64)
    locked.chmod(0o000)
    try:
        with pytest.raises(OSError) as raised:  # noqa: PT011 - errno asserted, not text
            shutil.copyfile(locked, tmp_path / "dest.bin")
        assert raised.value.errno == errno.EACCES
        assert persists_for_the_run(raised.value) is False
    finally:
        locked.chmod(0o644)


def test_an_exception_with_no_oserror_in_its_chain_is_not_persistent() -> None:
    """⚠ **Found by a surviving mutation, not by design.** Flipping the no-`OSError` branch to
    `True` killed nothing, because every other test hands in a chain that contains one.

    The branch is reachable: `execute`'s handler also catches `DestinationError`, which may be
    raised **without** a cause - `check_contained`'s path-escape refusal is one. Treating an
    unclassifiable exception as persistent would stop a run over a condition nobody has shown
    outlives the file, which is the wrong direction for the default this whole predicate rests on.
    """
    bare = ValueError("not an OSError at all")

    assert persists_for_the_run(bare) is False

    chained_to_nothing = RuntimeError("wrapper")
    chained_to_nothing.__cause__ = ValueError("still no OSError")
    assert persists_for_the_run(chained_to_nothing) is False


def test_an_oserror_reached_through_two_wrappers_is_still_classified() -> None:
    """The other side of the same branch: the walk must not stop at the first wrapper.

    `LocalDestination.upload` wraps once today, but nothing guarantees one layer - and a walk that
    only checked `__cause__` once would be inert the moment a second wrapper appeared, which is
    exactly how the first draft of this predicate was inert at zero layers.
    """
    inner = OSError(errno.ENOSPC, "No space left on device")
    middle = RuntimeError("middle")
    middle.__cause__ = inner
    outer = RuntimeError("outer")
    outer.__cause__ = middle

    assert persists_for_the_run(outer) is True
