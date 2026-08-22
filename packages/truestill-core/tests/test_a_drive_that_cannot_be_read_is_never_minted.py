"""Do not mint an identity on evidence the product could not gather. `(afn)`

Measured before the fix: a **perfect** drive - every recorded file present and byte-correct - with
30 of its 40 sampled paths behind a denied folder returned `[]` from `inspect_root`, printed
nothing, and was registered as a **second drive id for one library**. The same drive readable
returned `('proven', 40, 40)`.

⚠ **The branch had never been exercised.** No test in `test_drive_adoption.py` staged a refusal,
which is why it shipped wrong - so this file tests the matrix rather than a sample: three callers
by three states, the threshold's two neighbours, and a cry-wolf arm proving a readable drive still
registers exactly as before.

⚠ **`source_repoint`'s three cells are the CONTROL.** It refuses today on the identical empty
list, and its behaviour must not change. If one of those cells needs editing, the fix reached
further than it was meant to.
"""

from __future__ import annotations

import os
import sys
import threading
from pathlib import Path

import pytest
from truestill_core.drive_adoption import (
    PRESENCE_THRESHOLD,
    AdoptionVerdict,
    RecordedDrive,
    inspect_root,
)

_POSIX_ONLY = pytest.mark.skipif(
    sys.platform == "win32",
    reason="chmod 000 does not deny the owner on Windows; this refusal has no Windows equivalent",
)


def _echo_hasher(path: Path) -> str:
    return path.read_text()


def _library(root: Path, *, readable: int, denied: int) -> RecordedDrive:
    """A PERFECT drive: every recorded file is present and correct. Some are behind a wall.

    The point of the fixture is that nothing is missing and nothing differs - so any verdict other
    than "this is that drive" comes from the reading, never from the drive.
    """
    digests: dict[str, str] = {}
    for i in range(readable + denied):
        folder = "open" if i < readable else "denied"
        target = root / folder / f"f{i:03d}.jpg"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(f"photo-{i}")
        digests[f"{folder}/f{i:03d}.jpg"] = f"photo-{i}"
    return RecordedDrive(uuid="uuid-a", label="Photos HDD", digests=digests)


#: The first file the fixture puts behind the wall, named rather than discovered - see
#: `_really_denied`.
def _first_denied(readable: int) -> str:
    return f"denied/f{readable:03d}.jpg"


def _deny(root: Path) -> None:
    (root / "denied").chmod(0o000)


def _restore(root: Path) -> None:
    denied = root / "denied"
    if denied.exists():
        denied.chmod(0o755)


def _really_denied(child: Path) -> bool:
    """⚠ Stats a KNOWN child, never the folder and never a glob.

    Two traps, both hit while writing this. ``os.stat`` on a mode-000 directory **succeeds** - it
    needs execute on the *parent*, not on the directory - so probing the folder itself reported
    "not denied" and skipped every test here. And ``glob`` has to *read* the directory, which is
    the very thing being denied, so it returns `[]` rather than raising. The path has to be
    constructed, not discovered.
    """
    try:
        os.stat(child)  # noqa: PTH116 - independent of the subject, on purpose
    except PermissionError:
        return True
    except OSError:
        return False
    return False


# --- the discriminator: refused is not absent, and absent is not refused ----------------------


@_POSIX_ONLY
def test_a_perfect_drive_that_cannot_be_read_is_unreadable_not_absent(tmp_path: Path) -> None:
    """The measured case. 30 of 40 refused, and every readable file is exactly right."""
    drive = _library(tmp_path, readable=10, denied=30)
    _deny(tmp_path)
    try:
        if not _really_denied(tmp_path / _first_denied(10)):
            pytest.skip("running as root, or a filesystem that ignores the mode")
        offers = inspect_root(tmp_path, [drive], hasher=_echo_hasher)
    finally:
        _restore(tmp_path)

    assert offers, "a drive that could not be read vanished, and would be registered as new"
    assert offers[0].verdict is AdoptionVerdict.UNREADABLE
    assert offers[0].refused == 30
    assert offers[0].sampled == 40


def test_an_unrelated_folder_is_still_no_match_and_still_offers_nothing(tmp_path: Path) -> None:
    """⚠ THE TRAP, and it is why the filter was load-bearing for a reason nobody wrote down.

    `test_an_unrelated_folder_produces_no_offer` pinned `inspect_root(...) == []`. A fix that
    called every empty answer "unreadable" would refuse to register any new drive at all -
    reproducing the defect one layer up, in the safe-looking direction.

    Nothing here is refused: the recorded paths are simply absent.
    """
    (tmp_path / "Holiday").mkdir()
    (tmp_path / "Holiday" / "DSC_9999.jpg").write_text("someone else's photo")
    drive = RecordedDrive(
        uuid="u", label="Photos HDD", digests={f"a/{i}.jpg": "x" for i in range(40)}
    )

    assert inspect_root(tmp_path, [drive], hasher=_echo_hasher) == []


@_POSIX_ONLY
def test_a_folder_that_is_unrelated_and_also_unreadable_is_unreadable(tmp_path: Path) -> None:
    """The other side of the trap: we cannot claim it is unrelated if we could not look.

    This is the cell that shows the rule is about EVIDENCE and not about the outcome - the honest
    answer here is "unknown", even though the folder really is unrelated.
    """
    (tmp_path / "denied").mkdir()
    for i in range(40):
        (tmp_path / "denied" / f"f{i:03d}.jpg").write_text("x")
    drive = RecordedDrive(
        uuid="u",
        label="Photos HDD",
        digests={f"denied/f{i:03d}.jpg": "different" for i in range(40)},
    )
    _deny(tmp_path)
    try:
        if not _really_denied(tmp_path / _first_denied(0)):
            pytest.skip("running as root, or a filesystem that ignores the mode")
        offers = inspect_root(tmp_path, [drive], hasher=_echo_hasher)
    finally:
        _restore(tmp_path)

    assert offers
    assert offers[0].verdict is AdoptionVerdict.UNREADABLE


# --- the boundary: THRESHOLD-1, THRESHOLD, THRESHOLD+1 ----------------------------------------


@_POSIX_ONLY
@pytest.mark.parametrize(
    ("denied", "expected"),
    [
        (19, "proceed"),  # one below the tipping point
        (20, "proceed"),  # exactly at it: present still meets the bar
        (21, "unreadable"),  # one above: the bar is missed only because of refusals
    ],
)
def test_the_boundary_is_where_the_refusals_change_the_answer(
    tmp_path: Path, denied: int, expected: str
) -> None:
    """⚠ A ratio fix that is off by one passes every test that samples the middle.

    Written against `PRESENCE_THRESHOLD` rather than the literals, so a threshold change moves the
    test with it - and the parametrisation is chosen from those constants, so the three cases stay
    the two neighbours of the tipping point rather than three fixed numbers.
    """
    total = 40
    assert PRESENCE_THRESHOLD * total == 20, "the cases below are the neighbours of this bar"
    drive = _library(tmp_path, readable=total - denied, denied=denied)
    _deny(tmp_path)
    try:
        if not _really_denied(tmp_path / _first_denied(total - denied)):
            pytest.skip("running as root, or a filesystem that ignores the mode")
        offers = inspect_root(tmp_path, [drive], hasher=_echo_hasher)
    finally:
        _restore(tmp_path)

    assert offers
    if expected == "proceed":
        assert offers[0].verdict is not AdoptionVerdict.UNREADABLE, (
            "a drive whose readable sample still clears the bar must not be called unreadable"
        )
    else:
        assert offers[0].verdict is AdoptionVerdict.UNREADABLE


# --- the cry-wolf arm: a readable drive behaves exactly as it did -----------------------------


def test_a_drive_with_no_refusals_is_proven_exactly_as_before(tmp_path: Path) -> None:
    """The failure mode of this ruling is refusing a legitimate action, so this is the arm that
    makes it safe. Zero refusals must reach the same verdict, by the same route, as before."""
    drive = _library(tmp_path, readable=40, denied=0)

    offers = inspect_root(tmp_path, [drive], hasher=_echo_hasher)

    assert len(offers) == 1
    assert offers[0].verdict is AdoptionVerdict.PROVEN
    assert offers[0].refused == 0
    assert (offers[0].sampled, offers[0].present) == (40, 40)


def test_a_cancelled_inspection_does_not_become_unreadable(tmp_path: Path) -> None:
    """⚠ "We stopped early" is not "the drive would not answer".

    Cancelling breaks the loop with the sample part-examined. Calling that UNREADABLE would
    fabricate a verdict out of the user's own interruption - and `test_drive_adoption.py`'s
    cancellation test says this function must offer nothing it did not prove.
    """
    drive = _library(tmp_path, readable=40, denied=0)
    cancel = threading.Event()
    cancel.set()

    assert inspect_root(tmp_path, [drive], hasher=_echo_hasher, cancel=cancel) == []


class _CancelAfter(threading.Event):
    """An Event that turns true partway through the loop, the way a person's click does."""

    def __init__(self, after: int) -> None:
        super().__init__()
        self._after = after
        self.checks = 0

    def is_set(self) -> bool:
        self.checks += 1
        return self.checks > self._after


@_POSIX_ONLY
def test_a_cancel_that_arrives_after_refusals_still_does_not_fabricate_a_verdict(
    tmp_path: Path,
) -> None:
    """⚠ Written because a mutation SURVIVED, and the survival was the finding.

    The first cancellation test set the flag before the loop began, so `refused` was 0 and the
    verdict was `NO_MATCH` whether the guard existed or not - green for a reason that had nothing
    to do with the branch it named. §4's sixtieth member, in a test written to prove a guard.

    Reaching the branch needs the cancel to arrive *after* refusals have accumulated. `denied/`
    sorts before `open/`, so the refusals come first, and this stops the run once 25 of them have
    been counted: enough to clear the bar, so without the guard the interruption itself would be
    reported as a drive that would not answer.
    """
    drive = _library(tmp_path, readable=10, denied=30)
    _deny(tmp_path)
    try:
        if not _really_denied(tmp_path / _first_denied(10)):
            pytest.skip("running as root, or a filesystem that ignores the mode")
        cancel = _CancelAfter(25)
        offers = inspect_root(tmp_path, [drive], hasher=_echo_hasher, cancel=cancel)
    finally:
        _restore(tmp_path)

    assert cancel.checks > 25, "the cancel never fired, so the branch was not reached"
    assert offers == [], "a cancelled run reported the interruption as an unreadable drive"
