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
from truestill_core import organizer, safe_copy
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
from truestill_core.organizer import (
    RunStoppedError,
    _record_then_stop_if_it_will_recur,
    execute,
)

_HAS_DEV_FULL = pytest.mark.skipif(
    not Path("/dev/full").exists(), reason="/dev/full is Linux-specific"
)


class _Exploding(LocalDestination):
    """A destination whose first write raises whatever it was given."""

    def __init__(self, boom: BaseException) -> None:
        super().__init__(Path("/nonexistent-and-never-touched"))
        self._boom = boom

    def upload(self, local: Path, relative_path: str) -> None:  # noqa: ARG002 - the signature is the contract
        raise self._boom

    def exists(self, relative_path: str) -> bool:  # noqa: ARG002 - same
        return False


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

    with pytest.raises(RunStoppedError) as raised:
        execute(
            [_resolution(p) for p in sources],
            LocalDestination(tmp_path / "dest"),
            None,
            apply=True,
        )

    # ⚠ **`RunStoppedError` since `(agj)`, and the two properties this row exists for are
    # unchanged by it.** The wrapper carries the partial results out, which is the only way the
    # caller can write a truthful record; it reports its cause's own sentence, and the cause is
    # the original chain, so the `OSError` is still reachable - which is what let the predicate
    # classify it in the first place, and what keeps every classifier downstream working.
    inner = raised.value.__cause__
    assert isinstance(inner, DestinationError), f"the original was replaced, not wrapped: {inner!r}"
    assert isinstance(inner.__cause__, OSError)
    assert inner.__cause__.errno == errno.ENOSPC, (
        f"the abort did not carry the errno through: {inner.__cause__!r}"
    )
    assert "no space left on the drive" in str(raised.value), (
        "the wrapper does not report the sentence the user reads"
    )
    # The whole point of the type: what the run had already done, out with the exception.
    assert [r.status for r in raised.value.results] == [
        ActionStatus.UPLOADED,
        ActionStatus.FAILED,
    ], f"the stop did not carry out what the run managed: {raised.value.results}"


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


# --- what the stop must not take with it -------------------------------------------------------


@_HAS_DEV_FULL
def test_the_metadata_baker_is_closed_even_when_the_run_stops(
    sources: list[Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """⚠ **A stopped run used to leak a temporary directory.** `(agj)`

    `_MetadataBaker` holds a lazily-made `TemporaryDirectory`, and `baker.close()` sat after the
    loop on the ordinary return path only - so `(agi)`'s raise skipped it. A Takeout ingest that
    stopped against a full drive left the staging directory behind, on the very drive that had
    just run out of room.
    """
    closed: list[bool] = []
    real = organizer._MetadataBaker

    class Watched(real):  # type: ignore[misc, valid-type]
        def close(self) -> None:
            closed.append(True)
            super().close()

    monkeypatch.setattr(organizer, "_MetadataBaker", Watched)
    _real_enospc(monkeypatch, nth=2)

    with pytest.raises(RunStoppedError):
        execute(
            [_resolution(p) for p in sources],
            LocalDestination(tmp_path / "dest"),
            None,
            apply=True,
        )

    assert closed == [True], "the run stopped without closing its metadata baker"


def test_a_run_that_finishes_closes_it_too(
    sources: list[Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """⚠ **CRY-WOLF HALF.** Moving the close into a `finally` must not have moved it off the
    ordinary path, which is where it always ran and where nearly every run ends."""
    closed: list[bool] = []
    real = organizer._MetadataBaker

    class Watched(real):  # type: ignore[misc, valid-type]
        def close(self) -> None:
            closed.append(True)
            super().close()

    monkeypatch.setattr(organizer, "_MetadataBaker", Watched)

    execute(
        [_resolution(p) for p in sources], LocalDestination(tmp_path / "dest"), None, apply=True
    )

    assert closed == [True]


def test_a_defect_is_carried_out_the_same_way_as_a_drive_answer(sources: list[Path]) -> None:
    """`execute` wraps `Exception`, not just the two types `(agi)` re-raises.

    A record of what a run did is worth no less when what stopped it was a bug of ours - and the
    caller can still tell the two apart, because the cause is right there. ⚠ **`BaseException` is
    deliberately not caught**: a `KeyboardInterrupt` must not become something a caller might
    handle and continue past, which the row below is what proves.
    """
    boom = ValueError("a defect, not a destination")

    with pytest.raises(RunStoppedError) as raised:
        execute(
            [_resolution(sources[0])],
            _Exploding(boom),
            None,
            apply=True,
        )

    assert raised.value.__cause__ is boom
    assert str(raised.value) == "a defect, not a destination"


def test_a_keyboard_interrupt_is_not_turned_into_a_stop(sources: list[Path]) -> None:
    """⚠ **CRY-WOLF HALF for the wrapper's width.** `except Exception` was chosen over
    `BaseException` on purpose; widening it would swallow the one exception that must reach the
    top of the process unchanged."""
    with pytest.raises(KeyboardInterrupt):
        execute(
            [_resolution(sources[0])],
            _Exploding(KeyboardInterrupt()),
            None,
            apply=True,
        )
