"""A long `execute` notices the ground moving, on both surfaces or on neither.

`RunHealth` shipped in `56bb6f3` with tests and **no caller**. This is the wiring, and where it
goes is the whole decision: `_refuse_impossible_destination` already records why a check like
this cannot live in the CLI or the app - *"a check placed in either is a check the other silently
lacks, which is exactly how backup's free-space check ended up app-only"*. So `execute` builds
the watcher itself and neither surface can forget it.

**Why a `local_root()` hook and not an `isinstance` check.** `Destination` covers backends with
no local filesystem at all, and `preflight`'s default already argues the case: answering a
remote's free space with `shutil.disk_usage` "would refuse an upload to a 10 TB remote because
the laptop is full". A device id to watch is the same kind of fact. So the base class stands down
completely - `local_root()` returns `None`, no watcher is built, and nothing is guessed on a
remote's behalf.

**The stop is reported as a `FAILED` result, not a new `ActionStatus`.** There is no
`assert_never` over `ActionStatus`, so a new member is the "N places that must be found" hazard
with no compile-time gate - `_STATUS_LABELS`, `_ORGANIZED_STATUSES`, both surfaces' counters.
`FAILED` already means exactly *this file is not in your library, and here is the message*, and
both surfaces already show that message prominently. The honest limit is stated in
`test_the_files_after_a_stop_are_not_attempted_and_not_claimed`.
"""

from __future__ import annotations

import threading
from pathlib import Path

import pytest
from truestill_core import run_health
from truestill_core.catalog import Catalog
from truestill_core.categorize import CategoryMatch, Confidence
from truestill_core.destinations.base import Destination
from truestill_core.destinations.local import LocalDestination
from truestill_core.models import (
    ActionResult,
    ActionStatus,
    DateSource,
    Decision,
    FileHashes,
    Resolution,
)
from truestill_core.organizer import _largest_still_ahead, execute

_GB = 1024**3


class _Remote(Destination):
    """A backend with no local filesystem, like the one `preflight` stands down for."""

    def describe(self) -> str:
        return "remote:Photos"

    def exists(self, _relative_path: str) -> bool:
        return False

    def upload(self, _local: Path, _relative_path: str) -> None:
        return None

    def set_timestamp(self, _relative_path: str, _captured_at: object) -> None:
        return None

    def list(self) -> list[str]:
        return []


def _resolution(source: Path) -> Resolution:
    decision = Decision(
        source=source,
        category=CategoryMatch(
            label="Camera", reason="t", confidence=Confidence.HIGH, rule="device"
        ),
        captured_at=None,
        date_source=DateSource.NONE,
        date_tag=None,
        relative=Path("Camera/Undated") / source.name,
    )
    return Resolution(
        decision=decision,
        hashes=FileHashes(sha256="a" * 64, perceptual=None),
        exact_duplicate=None,
        near_duplicate=None,
    )


@pytest.fixture
def sources(tmp_path: Path) -> list[Path]:
    folder = tmp_path / "src"
    folder.mkdir()
    made = []
    for i in range(6):
        path = folder / f"{i}.jpg"
        path.write_bytes(b"x" * 1024)
        made.append(path)
    return made


def _run(sources: list[Path], destination: Destination, catalog_dir: Path) -> list[ActionResult]:
    """A real `Catalog`, not a stand-in.

    The watcher reads `catalog.path` to find the **local** disk to probe, which is the whole
    reason a catalog is required at all. A stub with a `path` attribute would prove the wiring
    against a fake and leave the real attribute free to be renamed.
    """
    with Catalog(catalog_dir / "c.sqlite") as catalog:
        return execute([_resolution(p) for p in sources], destination, catalog, apply=True)


def _vanishing(monkeypatch: pytest.MonkeyPatch, *, healthy_checks: int) -> None:
    """A drive that answers for ``healthy_checks`` readings and is then definitively gone.

    The baseline has to be a **real** sighting, which is the point of `healthy_checks >= 1`:
    a drive that was never there is a different situation, covered below.
    """
    monkeypatch.setattr(run_health, "TICK_SECONDS", 0.0)
    monkeypatch.setattr(run_health, "STRIKE_SPAN_SECONDS", 0.0)
    monkeypatch.setattr(run_health, "free_bytes", lambda _p: 500 * _GB)
    seen = {"n": 0}

    def _reading(_path: Path) -> run_health.DeviceReading:
        seen["n"] += 1
        return run_health.DeviceReading(7 if seen["n"] <= healthy_checks else None, definite=True)

    monkeypatch.setattr(run_health, "read_device", _reading)


# --- the drive going away ----------------------------------------------------------------------


def test_a_drive_that_disappears_stops_the_run_and_says_so(
    sources: list[Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The whole point: a run stops instead of writing the rest onto the local disk."""
    dest = tmp_path / "drive"
    dest.mkdir()
    _vanishing(monkeypatch, healthy_checks=2)

    results = _run(sources, LocalDestination(dest), tmp_path)

    failed = [r for r in results if r.status is ActionStatus.FAILED]
    assert len(failed) == 1, "exactly one result carries the stop"
    assert "disconnected or unmounted" in failed[0].detail
    assert "run again to continue" in failed[0].detail


def test_the_files_after_a_stop_are_not_attempted_and_not_claimed(
    sources: list[Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """**The honest limit, stated rather than glossed.**

    A stop leaves the remaining files unattempted and therefore absent from the results - the
    same shape `cancel` has always had. What must never happen is the opposite: a file counted
    as organized that was not written. So the assertion is that the run got *shorter*, and that
    nothing after the stop claims success.
    """
    dest = tmp_path / "drive"
    dest.mkdir()
    _vanishing(monkeypatch, healthy_checks=1)

    results = _run(sources, LocalDestination(dest), tmp_path)

    assert len(results) < len(sources), "the run stopped early"
    assert results[-1].status is ActionStatus.FAILED
    organized = [r for r in results if r.status is ActionStatus.UPLOADED]
    for result in organized:
        assert result.final_relative is not None, "an uploaded result must say where it landed"
        assert (dest / result.final_relative).exists(), "a claimed file must really be there"


# --- crying wolf is the failure mode to fear ---------------------------------------------------


def test_a_healthy_run_is_untouched(sources: list[Path], tmp_path: Path) -> None:
    """The real drive, the real clock, no stubs: every file organized, nothing reported."""
    dest = tmp_path / "drive"
    dest.mkdir()
    results = _run(sources, LocalDestination(dest), tmp_path)

    assert len(results) == len(sources)
    assert all(r.status is ActionStatus.UPLOADED for r in results)


def test_a_transient_reading_does_not_stop_a_healthy_run(
    sources: list[Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One bad reading is a hiccup, not a verdict. This is the guard's whole posture."""
    dest = tmp_path / "drive"
    dest.mkdir()
    monkeypatch.setattr(run_health, "TICK_SECONDS", 0.0)
    monkeypatch.setattr(run_health, "free_bytes", lambda _p: 500 * _GB)
    seen = {"n": 0}

    def _reading(_path: Path) -> run_health.DeviceReading:
        seen["n"] += 1
        # An indefinite failure (a transient EIO), then healthy again.
        if seen["n"] == 2:
            return run_health.DeviceReading(None, definite=False)
        return run_health.DeviceReading(7, definite=True)

    monkeypatch.setattr(run_health, "read_device", _reading)

    results = _run(sources, LocalDestination(dest), tmp_path)
    assert len(results) == len(sources)
    assert not [r for r in results if r.status is ActionStatus.FAILED]


def test_a_preview_never_watches_anything(
    sources: list[Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A dry run writes nothing, so there is no ground under it to move.

    Watching one would cost a `stat` per file for an answer that cannot matter, and could
    refuse a preview - which is the cry-wolf case at its most pointless.
    """
    dest = tmp_path / "drive"
    dest.mkdir()

    def _boom(_path: Path) -> run_health.DeviceReading:
        message = "a preview must not probe the destination's device"
        raise AssertionError(message)

    monkeypatch.setattr(run_health, "read_device", _boom)
    results = execute([_resolution(p) for p in sources], LocalDestination(dest), None, apply=False)
    assert all(r.status is ActionStatus.PLANNED for r in results)


def test_a_cancelled_run_is_not_reported_as_unhealthy(sources: list[Path], tmp_path: Path) -> None:
    """Cancel is the user's decision and must not be dressed up as a drive problem."""
    dest = tmp_path / "drive"
    dest.mkdir()
    cancel = threading.Event()
    cancel.set()
    results = execute(
        [_resolution(p) for p in sources], LocalDestination(dest), None, apply=True, cancel=cancel
    )
    assert results == []


# --- the destinations that have no ground to watch ---------------------------------------------


def test_a_remote_destination_is_not_watched_at_all(
    sources: list[Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The reason this is a hook and not an `isinstance` check.

    A remote has no local filesystem, so it has no device id to lose - exactly the argument
    `Destination.preflight` already makes about free space. Standing down completely beats
    guessing, because the only thing a guess can do here is refuse work that would have worked.
    """

    def _boom(_path: Path) -> run_health.DeviceReading:
        message = "a remote destination has no local device to watch"
        raise AssertionError(message)

    monkeypatch.setattr(run_health, "read_device", _boom)
    results = _run(sources, _Remote(), tmp_path)
    assert len(results) == len(sources)


def test_the_base_class_stands_down_and_the_local_backend_does_not() -> None:
    """Pinned as a property of the protocol, so a new backend inherits the safe answer."""
    assert _Remote().local_root() is None
    assert LocalDestination(Path("/tmp/x")).local_root() == Path("/tmp/x")


def test_a_drive_that_answers_late_does_not_get_a_healthy_run_stopped(
    sources: list[Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """**Found by wiring this up**, and worse than "the guard switches itself off".

    The baseline used to be whatever the very first reading gave, including `None` - two
    meanings in one value, "not yet established" and "the device id is None". The visible
    consequence is not silence. It is the opposite: every later `None` compares *equal* to that
    baseline and reads healthy, and then the moment the drive **does** answer, its real device
    id compares *unequal* - so the watcher strikes three times and stops a run whose drive is
    working perfectly. Crying wolf, from a watcher built one moment too early.

    `DestinationDevice` already latched on the first real sighting. These two differ in what
    they do afterwards, not in what counts as a baseline.

    The first reading is the constructor's, which is why the sequence starts unreadable: a
    watcher built while the mount was still settling is precisely the case.
    """
    dest = tmp_path / "drive"
    dest.mkdir()
    monkeypatch.setattr(run_health, "TICK_SECONDS", 0.0)
    monkeypatch.setattr(run_health, "STRIKE_SPAN_SECONDS", 0.0)
    monkeypatch.setattr(run_health, "free_bytes", lambda _p: 500 * _GB)
    seen = {"n": 0}

    def _reading(_path: Path) -> run_health.DeviceReading:
        seen["n"] += 1
        # Unreadable while the mount settles, then answering normally for the rest of the run.
        return run_health.DeviceReading(None if seen["n"] <= 2 else 7, definite=True)

    monkeypatch.setattr(run_health, "read_device", _reading)

    results = _run(sources, LocalDestination(dest), tmp_path)

    assert len(results) == len(sources), "a working drive must not have its run stopped"
    assert not [r for r in results if r.status is ActionStatus.FAILED]


def test_a_destination_that_never_answers_is_left_to_the_write_to_report(
    sources: list[Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The other half: with nothing ever seen, there is no movement to detect.

    Standing down is right rather than merely safe - the write itself fails per file with the
    real `OSError`, which **names the file**, where a stop invented from an absence would not.
    """
    dest = tmp_path / "drive"
    dest.mkdir()
    monkeypatch.setattr(run_health, "TICK_SECONDS", 0.0)
    monkeypatch.setattr(run_health, "STRIKE_SPAN_SECONDS", 0.0)
    monkeypatch.setattr(run_health, "free_bytes", lambda _p: 500 * _GB)
    monkeypatch.setattr(
        run_health, "read_device", lambda _p: run_health.DeviceReading(None, definite=True)
    )

    results = _run(sources, LocalDestination(dest), tmp_path)
    assert len(results) == len(sources)
    assert not [r for r in results if r.status is ActionStatus.FAILED]


# --- the number the space floor is built on -----------------------------------------------------


def test_the_largest_still_ahead_shrinks_as_the_run_advances(tmp_path: Path) -> None:
    """A suffix maximum, and the *suffix* is the point.

    `RunHealth` reserves `largest_remaining * 2`. A plain maximum over the whole run would keep
    reserving space for a 4 GB video long after it had been written, so a run could refuse to
    finish its last few small files on a disk with ample room for them - the cry-wolf case, from
    a number that looks harmless.
    """
    folder = tmp_path / "s"
    folder.mkdir()
    paths = [folder / f"{i}.jpg" for i in range(3)]
    for path in paths:
        path.write_bytes(b"x")
    sizes = {paths[0]: 10, paths[1]: 900, paths[2]: 5}

    ahead = _largest_still_ahead([_resolution(p) for p in paths], sizes)

    assert ahead == [900, 900, 5, 0]


def test_a_file_the_run_would_not_write_contributes_nothing(tmp_path: Path) -> None:
    """`sizes` holds write candidates only, so a duplicate falls out without a second predicate.

    Two predicates for "would this be written" is how a preflight and a run come to disagree
    about what the run is; `write_candidates` is the one both use.
    """
    folder = tmp_path / "s"
    folder.mkdir()
    kept, skipped = folder / "a.jpg", folder / "b.jpg"
    for path in (kept, skipped):
        path.write_bytes(b"x")

    ahead = _largest_still_ahead([_resolution(kept), _resolution(skipped)], {kept: 42})

    assert ahead == [42, 0, 0]
