"""When a drive's remembered path still answers with the same uuid, say so. `(adx)` gap 1.

**The dangerous direction.** Cloning a drive copies `.truestill-drive.json`, so both trees carry
one uuid - which is *correct*, and `drive-identity-research.md:82-85` ruled it so: clones are
identical at clone time, and auto-disambiguating would mint a second identity for one library and
count one copy as two. **Nothing here disputes that.** What was missing is the third part of that
same proposal - *warn when one uuid is seen at two distinct mount paths* - which shipped only on
the registration path (`cli.py:893-918`) and never on the verify path. So a clone verified clean,
the remembered path silently moved to it, and `status` kept reporting one copy where two existed.
**Telling a user they have fewer copies than they do is the direction that gets photos deleted.**

**Only the case that cannot be wrong is reported.** If the remembered path still answers with this
uuid, two live copies exist and there is nothing to infer. If it does not answer - gone, moved,
unplugged, or too slow - a move and a clone-with-the-original-offline are *observationally
identical*, which `service/drives.py` already says in prose. That case stays silent.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path

import pytest
from truestill_core import drive as drive_module
from truestill_core.drive import (
    DriveMarker,
    create_marker,
    second_location_note,
)


def _a_drive(root: Path, label: str, uuid: str | None = None) -> DriveMarker:
    root.mkdir(parents=True, exist_ok=True)
    return create_marker(root, label, uuid=uuid)


def test_a_second_live_path_for_one_identity_is_reported(tmp_path: Path) -> None:
    """THE GUARD. Both trees answer to one uuid, so both copies exist and one is uncounted."""
    original = _a_drive(tmp_path / "B", "Photos")
    clone = tmp_path / "C"
    clone.mkdir()
    create_marker(clone, original.label, uuid=original.uuid)

    note = second_location_note(
        uuid=original.uuid,
        label=original.label,
        here=clone,
        remembered=str(tmp_path / "B"),
        previously_seen="2026-08-18T21:02:46",
    )

    assert note is not None, (
        "one drive identity answered at two live paths and nothing said so. Truestill counts "
        "them as one drive, so the custody claim under-reports - the direction that gets a user "
        "to delete a copy they still needed."
    )
    assert str(tmp_path / "B") in note
    assert str(clone) in note
    assert "2026-08-18T21:02:46" in note, "the note must date the other sighting"
    assert "--force-new-identity" in note, "the note must name the remedy"


def test_a_plain_move_says_nothing(tmp_path: Path) -> None:
    """The cry-wolf case, and the reason the rule is what it is.

    After `mv A B` the old path is gone. A move and a clone whose original is unplugged produce
    the identical observation, so reporting here would fire on every ordinary relocation.
    """
    moved = _a_drive(tmp_path / "B", "Photos")

    note = second_location_note(
        uuid=moved.uuid,
        label=moved.label,
        here=tmp_path / "B",
        remembered=str(tmp_path / "A"),  # never existed / already gone
        previously_seen="2026-08-18T21:02:46",
    )

    assert note is None


def test_a_different_drive_at_the_old_path_says_nothing(tmp_path: Path) -> None:
    """Someone else's marker is not a second copy of THIS drive - `drive_reach`'s own rule."""
    here = _a_drive(tmp_path / "B", "Photos")
    _a_drive(tmp_path / "A", "Something Else")

    note = second_location_note(
        uuid=here.uuid,
        label=here.label,
        here=tmp_path / "B",
        remembered=str(tmp_path / "A"),
        previously_seen=None,
    )

    assert note is None


def test_the_same_path_is_not_a_second_place(tmp_path: Path) -> None:
    """The ordinary case: verify at the path we already remembered. Must be silent and free."""
    same = _a_drive(tmp_path / "B", "Photos")

    note = second_location_note(
        uuid=same.uuid,
        label=same.label,
        here=tmp_path / "B",
        remembered=str(tmp_path / "B"),
        previously_seen="2026-08-18T21:02:46",
    )

    assert note is None


def test_no_remembered_path_says_nothing(tmp_path: Path) -> None:
    """A drive with no recorded location has no second place to disagree with."""
    fresh = _a_drive(tmp_path / "B", "Photos")
    assert (
        second_location_note(
            uuid=fresh.uuid,
            label=fresh.label,
            here=tmp_path / "B",
            remembered=None,
            previously_seen=None,
        )
        is None
    )


def test_a_probe_that_does_not_answer_in_time_stays_silent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """⚠ THE FUSE CASE, and it decides the whole design.

    A `stat` on a wedged mount cannot be interrupted - `SIGALRM` does not reach it - so the probe
    can only be *abandoned*, never cancelled. Abandoning is safe on this runtime: bpo-32186, where
    `fstat` inside `fileio_init` held the GIL and hung every thread, was fixed in 2017 - far below
    any version this project could run.

    A timeout is *"did not answer"*, which is already the silent row. `run_health` states the rule
    this follows: **crying wolf is the failure mode to fear**, and a slow-but-successful answer is
    not a bad answer. So a live-but-slow mount produces a MISSED disclosure, never a false one.
    """
    here = _a_drive(tmp_path / "C", "Photos")
    elsewhere = tmp_path / "B"
    elsewhere.mkdir()
    create_marker(elsewhere, here.label, uuid=here.uuid)

    real = drive_module.read_marker
    # ⚠ THE PROBE IS BLOCKED, NOT MERELY SLOW, AND THAT IS THE POINT OF THIS FIXTURE.
    #
    # It used to sleep `SECOND_LOCATION_PROBE_SECONDS * 3` - 0.15 s against a 0.05 s join - and
    # **failed on macOS in CI run 32279378834**. `Thread.join(timeout)` waits AT LEAST the
    # timeout, never at most: if the main thread is descheduled past the worker's sleep, the
    # worker appends first and `_marker_within` returns a real answer. The whole margin was 100 ms
    # of scheduling jitter on a loaded runner running `-n auto`, and a test whose correctness
    # depends on winning a race is a test that reports the scheduler.
    #
    # An Event nobody sets cannot answer at whatever moment the join happens to return, so the
    # assertion is about the BOUND rather than about who woke first. The same rule `(aec)` is
    # about one level up: wait for the thing itself, never against a clock.
    blocked = threading.Event()

    def never_answers(root: Path) -> DriveMarker | None:
        if root == elsewhere:
            # Bounded, and NOT because 30 s is meaningful: it is 600x the join below, so no
            # scheduling jitter can reach it. What the bound buys is the failure mode - if the
            # product ever loses its timeout, this test goes RED on the `waited` assertion
            # instead of deadlocking the suite. A guard that hangs reports nothing.
            blocked.wait(timeout=30)
        return real(root)

    monkeypatch.setattr(drive_module, "read_marker", never_answers)
    monkeypatch.setattr(drive_module, "SECOND_LOCATION_PROBE_SECONDS", 0.05)
    drive_module.forget_slow_paths()

    started = time.perf_counter()
    note = second_location_note(
        uuid=here.uuid,
        label=here.label,
        here=tmp_path / "C",
        remembered=str(elsewhere),
        previously_seen=None,
    )
    waited = time.perf_counter() - started
    # Let the abandoned probe finish so the thread is not left parked for the rest of the session.
    # Production cannot do this - a wedged mount never releases - which is why the code abandons
    # rather than joins; a test that can clean up should.
    blocked.set()

    assert note is None, "a probe that timed out reported anyway, which is the false direction"
    assert waited < 1.0, f"the probe was not bounded: waited {waited:.2f}s"


def test_a_path_that_timed_out_once_is_not_probed_again(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The parked thread never dies, so the same dead mount must not be probed twice.

    Without this, every verify against a library whose other drive is a wedged mount leaks another
    thread. Per-process only: a mount that comes back is re-probed on the next launch.
    """
    here = _a_drive(tmp_path / "C", "Photos")
    elsewhere = tmp_path / "B"
    elsewhere.mkdir()
    create_marker(elsewhere, here.label, uuid=here.uuid)
    probes: list[Path] = []
    real = drive_module.read_marker

    def slow(root: Path) -> DriveMarker | None:
        probes.append(root)
        if root == elsewhere:
            time.sleep(drive_module.SECOND_LOCATION_PROBE_SECONDS * 3)
        return real(root)

    monkeypatch.setattr(drive_module, "read_marker", slow)
    monkeypatch.setattr(drive_module, "SECOND_LOCATION_PROBE_SECONDS", 0.05)
    drive_module.forget_slow_paths()

    for _ in range(3):
        second_location_note(
            uuid=here.uuid,
            label=here.label,
            here=tmp_path / "C",
            remembered=str(elsewhere),
            previously_seen=None,
        )

    assert probes.count(elsewhere) == 1, (
        f"the wedged path was probed {probes.count(elsewhere)} times; each one parks a thread "
        "that cannot be killed"
    )
