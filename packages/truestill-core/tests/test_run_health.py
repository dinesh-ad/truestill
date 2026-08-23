"""A long run must notice the ground moving under it, without crying wolf.

Two hazards, both observed on a real 192 GB migration and both invisible to the run itself:

* **The drive drops.** A cloud FUSE mount that dies leaves its mountpoint as an ordinary empty
  directory, and the mount table can still say "mounted" with no process behind it.
* **The local disk fills.** The cloud client caches everything written to it. Preflight measures
  the *destination*, which on a mounted drive is the remote 2 TB, while the disk that actually
  fills is the local one.

**Crying wolf is the failure mode to fear here**, more than either hazard. A check that stops a
healthy 30-minute run gets switched off, and takes its real coverage with it. So the device
half demands three consecutive bad answers spanning fifteen seconds before it declares
anything, and a slow-but-successful answer is not a bad answer at all.

**Free space is judged differently, on purpose.** One reading below the floor is enough, because
waiting for three would mean watching the disk fill while declining to say so.

⚠ **That paragraph continued *"it is a local read that does not fail transiently"* until
2026-08-23, and it was false** (`(aft)`). A deleted probe directory answers ``ENOENT`` and an
unsearchable parent answers ``EACCES``, neither needing root - and the probe is
``catalog_path.parent``, where ``--db`` takes any path at all. The reading can be **absent**, which
is a third answer from *"plenty"* and *"nearly none"*, and it now fails **open**. The tests at the
end of this file are the ones that call the real `free_bytes`: every other space test here
monkeypatches it to a number, which is exactly why the sentinel survived a mutation across 2,560
tests.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from truestill_core import run_health
from truestill_core.run_health import (
    ABSOLUTE_FLOOR_BYTES,
    STRIKES_TO_STOP,
    TICK_SECONDS,
    RunHealth,
)

_GB = 1024**3


class _Clock:
    """A monotonic clock the test drives. No sleeping, so no timing flake."""

    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@pytest.fixture
def clock() -> _Clock:
    return _Clock()


def _healthy(monkeypatch: pytest.MonkeyPatch, *, device: int = 42, free: int = 500 * _GB) -> None:
    monkeypatch.setattr(
        run_health, "read_device", lambda _p: run_health.DeviceReading(device, True)
    )
    monkeypatch.setattr(run_health, "free_bytes", lambda _p: free)


def _health(clock: _Clock, tmp_path: Path) -> RunHealth:
    return RunHealth(root=tmp_path, local_probe=tmp_path, clock=clock)


def _check(health: RunHealth, *, largest: int = 10 * 1024**2, written: int = 0):
    return health.check(largest_remaining=largest, written_bytes=written)


# --- the tick ---------------------------------------------------------------------------------


def test_nothing_is_read_before_the_tick_elapses(
    clock: _Clock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Per-file would cost ~20 s on a FUSE library; the tick is what makes this affordable."""
    reads: list[Path] = []
    monkeypatch.setattr(
        run_health, "read_device", lambda p: reads.append(p) or run_health.DeviceReading(42, True)
    )
    monkeypatch.setattr(run_health, "free_bytes", lambda _p: 500 * _GB)

    health = _health(clock, tmp_path)
    for _ in range(1000):
        _check(health)

    assert len(reads) == 1, "only the baseline reading should have happened"


def test_the_tick_lets_a_check_through(
    clock: _Clock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _healthy(monkeypatch)
    health = _health(clock, tmp_path)
    _check(health)
    clock.advance(TICK_SECONDS + 0.1)
    assert _check(health).ok


# --- a healthy run is never disturbed -----------------------------------------------------------


def test_a_healthy_run_never_trips(
    clock: _Clock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The cry-wolf half that matters most: an hour of healthy ticks says nothing."""
    _healthy(monkeypatch)
    health = _health(clock, tmp_path)
    for _ in range(720):  # an hour at a 5 s tick
        clock.advance(TICK_SECONDS + 0.1)
        assert _check(health).ok


def test_a_slow_but_successful_answer_is_not_a_bad_answer(
    clock: _Clock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Slow is not gone. A FUSE stat that takes seconds and then answers is a healthy drive."""
    _healthy(monkeypatch)
    health = _health(clock, tmp_path)
    for _ in range(10):
        clock.advance(30.0)  # each check took ages
        assert _check(health).ok


# --- transient errors must not stop a run --------------------------------------------------------


def test_one_transient_error_does_not_trip(
    clock: _Clock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Transient EIO on bulk reads over a cloud FUSE mount is documented behaviour. One is not
    evidence of anything."""
    _healthy(monkeypatch)
    health = _health(clock, tmp_path)
    clock.advance(TICK_SECONDS + 0.1)

    monkeypatch.setattr(run_health, "read_device", lambda _p: run_health.DeviceReading(None, False))
    assert _check(health).ok


def test_two_consecutive_errors_still_do_not_trip(
    clock: _Clock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _healthy(monkeypatch)
    health = _health(clock, tmp_path)
    monkeypatch.setattr(run_health, "read_device", lambda _p: run_health.DeviceReading(None, False))
    for _ in range(STRIKES_TO_STOP - 1):
        clock.advance(TICK_SECONDS + 0.1)
        assert _check(health).ok


def test_a_success_between_errors_resets_the_count(
    clock: _Clock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Consecutive means consecutive. A drive that answers once is not two-thirds dead."""
    _healthy(monkeypatch)
    health = _health(clock, tmp_path)
    bad = run_health.DeviceReading(None, False)
    good = run_health.DeviceReading(42, True)

    for reading in (bad, bad, good, bad, bad):
        clock.advance(TICK_SECONDS + 0.1)
        monkeypatch.setattr(run_health, "read_device", lambda _p, r=reading: r)
        assert _check(health).ok


def test_three_consecutive_errors_spanning_the_window_do_trip(
    clock: _Clock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The other side of the boundary, or the cry-wolf tests would pass against a check that
    never fires at all."""
    _healthy(monkeypatch)
    health = _health(clock, tmp_path)
    monkeypatch.setattr(run_health, "read_device", lambda _p: run_health.DeviceReading(None, False))

    verdict = None
    for _ in range(8):
        clock.advance(TICK_SECONDS + 0.1)
        verdict = _check(health)
        if not verdict.ok:
            break

    assert verdict is not None
    assert not verdict.ok
    assert "drive" in verdict.detail.lower()


def test_three_errors_too_close_together_do_not_trip(
    clock: _Clock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Count AND span. Three checks in two seconds is one hiccup observed thrice."""
    _healthy(monkeypatch)
    health = _health(clock, tmp_path)
    monkeypatch.setattr(run_health, "read_device", lambda _p: run_health.DeviceReading(None, False))

    for _ in range(STRIKES_TO_STOP + 2):
        clock.advance(0.5)  # a burst inside one hiccup, nowhere near the span window
        health._due = 0.0  # force the tick so only the SPAN rule can decide
        assert _check(health).ok


def test_a_definitely_changed_device_still_needs_its_strikes(
    clock: _Clock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Even a definite answer is polled rather than trusted once - a remount races a check."""
    _healthy(monkeypatch)
    health = _health(clock, tmp_path)
    monkeypatch.setattr(run_health, "read_device", lambda _p: run_health.DeviceReading(999, True))

    clock.advance(TICK_SECONDS + 0.1)
    assert _check(health).ok, "one definite mismatch is still only one strike"


# --- free space: one reading is enough -----------------------------------------------------------


def test_free_space_below_the_floor_stops_at_once(
    clock: _Clock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No strikes here: a local read does not fail transiently, and the disk is draining."""
    _healthy(monkeypatch)
    health = _health(clock, tmp_path)
    clock.advance(TICK_SECONDS + 0.1)

    monkeypatch.setattr(run_health, "free_bytes", lambda _p: ABSOLUTE_FLOOR_BYTES - 1)
    verdict = _check(health)

    assert not verdict.ok
    assert "disk" in verdict.detail.lower()


def test_the_floor_rises_with_the_largest_remaining_file(
    clock: _Clock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`max(2 GB, largest x 2)` - the floor must survive the copy currently in flight."""
    _healthy(monkeypatch)
    health = _health(clock, tmp_path)
    clock.advance(TICK_SECONDS + 0.1)

    huge = 8 * _GB  # x2 = 16 GB, well above the 2 GB absolute floor
    monkeypatch.setattr(run_health, "free_bytes", lambda _p: 10 * _GB)
    assert not _check(health, largest=huge).ok, "10 GB free is not enough for an 8 GB file"


def test_a_small_largest_file_leaves_the_absolute_floor_in_charge(
    clock: _Clock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Cry-wolf: an ordinary photo library must not be stopped by a 2 GB disk reserve."""
    _healthy(monkeypatch)
    health = _health(clock, tmp_path)
    clock.advance(TICK_SECONDS + 0.1)

    monkeypatch.setattr(run_health, "free_bytes", lambda _p: ABSOLUTE_FLOOR_BYTES + 1)
    assert _check(health, largest=5 * 1024**2).ok


def test_the_floor_is_compared_in_bytes_and_never_truncated(
    clock: _Clock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The migration's own off-by-one: a watchdog truncated GB, so 15.9 GB read as 15 and the
    trigger never fired while the disk drained. One byte either side must decide it."""
    _healthy(monkeypatch)
    health = _health(clock, tmp_path)

    clock.advance(TICK_SECONDS + 0.1)
    monkeypatch.setattr(run_health, "free_bytes", lambda _p: ABSOLUTE_FLOOR_BYTES)
    assert _check(health).ok, "exactly at the floor is not below it"

    clock.advance(TICK_SECONDS + 0.1)
    monkeypatch.setattr(run_health, "free_bytes", lambda _p: ABSOLUTE_FLOOR_BYTES - 1)
    assert not _check(health).ok


# --- the message ----------------------------------------------------------------------------------


def test_the_disk_message_names_the_delta_not_a_vendor(
    clock: _Clock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The deliverable. "Local free space fell by more than we wrote" points at the cause
    without a per-vendor path table we would have to maintain forever."""
    monkeypatch.setattr(run_health, "read_device", lambda _p: run_health.DeviceReading(42, True))
    monkeypatch.setattr(run_health, "free_bytes", lambda _p: 100 * _GB)
    health = _health(clock, tmp_path)

    clock.advance(TICK_SECONDS + 0.1)
    monkeypatch.setattr(run_health, "free_bytes", lambda _p: ABSOLUTE_FLOOR_BYTES - 1)
    verdict = _check(health, written=12 * _GB)

    detail = verdict.detail.lower()
    assert "fell by" in detail
    assert "cache" in detail, "the non-obvious cause must be named"
    for vendor in ("pcloud", "icedrive", "dropbox", "onedrive"):
        assert vendor not in detail, f"named a vendor: {vendor}"


# --- the probe that cannot be read at all -----------------------------------------------------
#
# ⚠ THESE ARE THE ONLY SPACE TESTS THAT CALL THE REAL `free_bytes`. Every other one above hands
# `_check_space` a number, which is how `return 0` survived being mutated to
# `return 999_999_999_999` against 2,560 passing tests: nothing executed the branch. A guard for a
# failure path has to produce the failure, not describe it.

#: `chmod 000` does not deny the owner on Windows, and root ignores it everywhere - so the
#: unsearchable-parent case cannot be staged on either. **One condition, never two stacked
#: `skipif` decorators**: each is evaluated at import, so a second one referencing `os.geteuid`
#: raises `AttributeError` on Windows and the WHOLE MODULE fails to collect, taking the tests
#: above with it. `PROJECT_STATUS.md` §5.
_CAN_DENY_ITSELF = pytest.mark.skipif(
    sys.platform == "win32" or os.geteuid() == 0,
    reason="chmod 000 does not deny the owner on Windows, and root ignores it",
)


def test_a_readable_probe_measures(tmp_path: Path) -> None:
    """The positive control. Without it every assertion below passes against a function that
    returns `None` unconditionally, which would switch the space guard off entirely."""
    measured = run_health.free_bytes(tmp_path)
    assert measured is not None, "a readable directory could not be measured"
    assert measured > 0


def test_a_deleted_probe_directory_cannot_be_measured(tmp_path: Path) -> None:
    """`ENOENT`. The probe is `catalog_path.parent`, and `--db` may name a removable drive."""
    probe = tmp_path / "gone"
    probe.mkdir()
    probe.rmdir()
    assert run_health.free_bytes(probe) is None


@_CAN_DENY_ITSELF
def test_a_probe_whose_parent_refuses_cannot_be_measured(tmp_path: Path) -> None:
    """`EACCES`, and it needs no removable media at all - which is what makes the old docstring's
    *"a local read does not fail transiently"* wrong on an ordinary machine."""
    parent = tmp_path / "locked"
    parent.mkdir()
    probe = parent / "catalog"
    probe.mkdir()
    parent.chmod(0o000)
    try:
        assert run_health.free_bytes(probe) is None
    finally:
        parent.chmod(0o700)


def test_a_probe_that_cannot_be_read_does_not_stop_the_run(
    clock: _Clock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The defect itself, from a real unreadable path rather than a monkeypatch.

    At HEAD before `(aft)` this returned `ok=False` carrying *"this computer's disk is nearly full
    (0.00 GB free)"* about a disk with room to spare.
    """
    _healthy(monkeypatch)
    probe = tmp_path / "gone"
    probe.mkdir()
    health = RunHealth(root=tmp_path, local_probe=probe, clock=clock)
    probe.rmdir()
    monkeypatch.undo()
    monkeypatch.setattr(run_health, "read_device", lambda _p: run_health.DeviceReading(42, True))
    clock.advance(TICK_SECONDS + 0.1)

    verdict = _check(health)

    assert verdict.ok, verdict.detail
    assert verdict.detail == "", "a run that was not stopped must not carry a stop sentence"


def test_a_probe_that_cannot_be_read_is_not_latched_as_the_baseline(
    clock: _Clock, tmp_path: Path
) -> None:
    """`_check_device`'s rule, applied to the axis that lacked it: never let an absence serve as
    the baseline. A `0` here clamps `fell` to `0` for the whole run, so the stop message's
    diagnostic half dies silently."""
    probe = tmp_path / "gone"
    probe.mkdir()
    probe.rmdir()

    health = RunHealth(root=tmp_path, local_probe=probe, clock=clock)

    assert health._baseline_free is None, "an unreadable first reading was latched as a measurement"


def test_the_baseline_latches_on_the_first_reading_that_worked_and_says_so(
    clock: _Clock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A late baseline covers less than the run, so the sentence must not set it against what the
    run wrote - that would state a rate nobody measured."""
    # The device half only - the constructor must reach the REAL `free_bytes` against the deleted
    # probe, or the baseline it fails to latch is the thing this test cannot observe.
    monkeypatch.setattr(run_health, "read_device", lambda _p: run_health.DeviceReading(42, True))
    probe = tmp_path / "gone"
    probe.mkdir()
    probe.rmdir()
    health = RunHealth(root=tmp_path, local_probe=probe, clock=clock)
    assert health._baseline_free is None, "precondition: the baseline must be absent"
    monkeypatch.setattr(run_health, "free_bytes", lambda _p: ABSOLUTE_FLOOR_BYTES - 1)
    clock.advance(TICK_SECONDS + 0.1)

    verdict = _check(health, written=40 * _GB)

    assert not verdict.ok
    assert "since it could first be measured" in verdict.detail
    assert "while this run wrote" not in verdict.detail, (
        "a fall measured over part of the run was set against the whole run's written total"
    )


def test_a_measured_zero_still_stops_the_run(
    clock: _Clock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """⚠ THE CRY-WOLF HALF, and the one that fails in the direction nobody looks.

    A genuinely full disk answers **successfully** with `0` - that is the whole reason `None` is
    the sentinel and `0` is not. A fix that treated every `0` as "could not measure" would pass
    every other test in this file and switch the space guard off for the case it exists for.
    """
    _healthy(monkeypatch)
    health = _health(clock, tmp_path)
    monkeypatch.setattr(run_health, "free_bytes", lambda _p: 0)
    clock.advance(TICK_SECONDS + 0.1)

    verdict = _check(health, written=40 * _GB)

    assert not verdict.ok, "a measured zero was read as an unmeasurable probe"
    assert "nearly full" in verdict.detail
