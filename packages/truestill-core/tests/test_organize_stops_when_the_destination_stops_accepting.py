"""Organize is the bigger instance of `(agi)`, and this is its end-to-end half.

`drive_unwritable.persists_for_the_run` is unit-tested next door. **A predicate nobody reaches is
worth nothing**, and organize runs far more often than backup - so the policy is asserted here
through `execute`, on real files, with a real kernel `ENOSPC`.

**What the two halves divide:**

* the predicate's table - `test_a_condition_that_outlives_the_file_stops_the_run.py`
* that `execute` consults it, and what the results look like on both sides - here
"""

from __future__ import annotations

import errno
import shutil
from pathlib import Path

import pytest
from truestill_core import safe_copy
from truestill_core.categorize import CategoryMatch, Confidence
from truestill_core.destinations.base import DestinationError
from truestill_core.destinations.local import LocalDestination
from truestill_core.models import (
    ActionResult,
    ActionStatus,
    DateSource,
    Decision,
    FileHashes,
    Resolution,
)
from truestill_core.organizer import _record_then_stop_if_it_will_recur, execute

_HAS_DEV_FULL = pytest.mark.skipif(
    not Path("/dev/full").exists(), reason="/dev/full is Linux-specific"
)


def _resolution(source: Path) -> Resolution:
    return Resolution(
        decision=Decision(
            source=source,
            category=CategoryMatch(
                label="Camera", reason="t", confidence=Confidence.HIGH, rule="device"
            ),
            captured_at=None,
            date_source=DateSource.NONE,
            date_tag=None,
            relative=Path("Camera/Undated") / source.name,
        ),
        hashes=FileHashes(sha256=source.name.ljust(64, "a"), perceptual=None),
        exact_duplicate=None,
        near_duplicate=None,
    )


@pytest.fixture
def sources(tmp_path: Path) -> list[Path]:
    made = []
    for i in range(4):
        p = tmp_path / "src" / f"p{i}.jpg"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(bytes([i]) * 2048)
        made.append(p)
    return made


def _wrapped(cause: OSError) -> DestinationError:
    """A `DestinationError` chained from an `OSError`, exactly as `LocalDestination.upload` builds
    it. ⚠ **The chaining is the subject**: the first draft of `(agi)` tested `isinstance(exc,
    OSError)` on this and was inert."""
    built = DestinationError("could not copy p0.jpg")
    built.__cause__ = cause
    return built


def _fail_nth(monkeypatch: pytest.MonkeyPatch, *, nth: int, code: int) -> None:
    """Fail the nth copy with a constructed errno - for the CONTINUE side only.

    ⚠ The abort side uses a **real** kernel `ENOSPC` instead (see `_real_enospc`), because a
    constructed exception proves the classifier and not the delivery.
    """
    seen = {"n": 0}
    real = safe_copy.shutil.copy2

    def flaky(src: object, dst: object, *a: object, **k: object) -> object:
        seen["n"] += 1
        if seen["n"] == nth:
            raise OSError(code, "injected")
        return real(src, dst, *a, **k)

    monkeypatch.setattr(safe_copy.shutil, "copy2", flaky)


def _real_enospc(monkeypatch: pytest.MonkeyPatch, *, nth: int) -> None:
    """Make the nth copy hit a genuine `ENOSPC` from the kernel, via `/dev/full`."""
    seen = {"n": 0}
    real = safe_copy.shutil.copy2

    def flaky(src: object, dst: object, *a: object, **k: object) -> object:
        seen["n"] += 1
        if seen["n"] == nth:
            shutil.copyfile(str(src), "/dev/full")
        return real(src, dst, *a, **k)

    monkeypatch.setattr(safe_copy.shutil, "copy2", flaky)


@_HAS_DEV_FULL
def test_a_full_destination_stops_organize(
    sources: list[Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The policy on the surface that runs most. Before `(agi)` this produced four `FAILED`
    results describing one condition."""
    _real_enospc(monkeypatch, nth=2)

    with pytest.raises(DestinationError) as raised:
        execute(
            [_resolution(p) for p in sources],
            LocalDestination(tmp_path / "dest"),
            None,
            apply=True,
        )

    # ⚠ **The ORIGINAL exception is re-raised, wrapper and all**, so the drive-worded sentence a
    # user reads survives - and the `OSError` is still reachable as its cause, which is what let
    # the predicate classify it in the first place.
    assert isinstance(raised.value.__cause__, OSError)
    assert raised.value.__cause__.errno == errno.ENOSPC, (
        f"the abort did not carry the errno through: {raised.value.__cause__!r}"
    )
    assert "no space left on the drive" in str(raised.value)


def test_the_file_that_hit_it_is_recorded_before_the_run_ends(sources: list[Path]) -> None:
    """⚠ **Q43's ordering, pinned.** The file WAS attempted and it DID fail, so it gets a `FAILED`
    result carrying the reason - recorded *before* the re-raise.

    Recording only on the continue path would make the same real event read differently depending
    on whether it happened to be persistent, and it would disagree with backup's abort, where the
    offending file is `failed` rather than `not attempted`.
    """
    seen: list[ActionResult] = []

    with pytest.raises(DestinationError):
        _record_then_stop_if_it_will_recur(
            seen.append,
            _resolution(sources[0]),
            _wrapped(OSError(errno.ENOSPC, "No space left on device")),
        )

    assert [r.status for r in seen] == [ActionStatus.FAILED], (
        "the run aborted without recording the file that caused it; the record would then say "
        "that file was never attempted, which is false"
    )


def test_one_unreadable_file_still_does_not_stop_organize(
    sources: list[Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """⚠ **CRY-WOLF HALF.** A predicate calling everything persistent passes the two rows above
    and destroys `ENGINEERING_STANDARD.md` §4 Errors on the surface it matters most on: one
    unreadable photo would end an organize of thirty thousand."""
    _fail_nth(monkeypatch, nth=2, code=errno.EACCES)

    results = execute(
        [_resolution(p) for p in sources], LocalDestination(tmp_path / "dest"), None, apply=True
    )

    assert len(results) == len(sources), "organize stopped on a per-file failure"
    assert sum(1 for r in results if r.status is ActionStatus.FAILED) == 1
    assert sum(1 for r in results if r.status is ActionStatus.UPLOADED) == 3


def test_an_unreasoned_errno_also_continues(
    sources: list[Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The default is the rule rather than an omission: an errno nobody has reasoned about
    continues, because continuing is recoverable and aborting a good run is not."""
    _fail_nth(monkeypatch, nth=3, code=errno.ENAMETOOLONG)

    results = execute(
        [_resolution(p) for p in sources], LocalDestination(tmp_path / "dest"), None, apply=True
    )

    assert len(results) == len(sources)
    assert sum(1 for r in results if r.status is ActionStatus.FAILED) == 1
