"""One bad file does not abort a backup. `(afw)` Stage 4

`ENGINEERING_STANDARD.md` §4 Errors: *"Partial-failure policy: one bad file never aborts a batch -
it is logged, counted, and reported at the end."* Backup was the surface that did not obey it.
Organize always has - its `except (OSError, DestinationError)` records a `FAILED` result and does
**not** break - so the product carried two policies for one user action, and this closes that by
backup catching up rather than organize changing.

**Two things stay true and are asserted here as the cry-wolf half**, because a change that made
everything continue would satisfy the rows above and be much worse than the defect:

* a **destination-level** failure still ends the run, and
* `verified` is still `True` when nothing failed.

⚠ **`verified` is the reason this could not wait.** It was a hardcoded `True` typed
`Literal[True]`, justified by a comment reading *"a copy that failed that check aborts the run"*.
The moment one bad file stopped aborting, that became a false statement in a custody record -
BackInTime #1587's shape, where per-file failures reported only through an exit code left users
believing the backup was fine.
"""

from __future__ import annotations

import errno
import json
import random
import threading
from pathlib import Path

import pytest
from PIL import Image
from truestill_app.service.backup import backup_run
from truestill_cli.cli import main
from truestill_core import run_health, safe_copy
from truestill_core.app_paths import record_path_for


def _jpeg(path: Path, *, seed: int) -> None:
    rng = random.Random(seed)
    image = Image.new("RGB", (64, 64))
    image.putdata(
        [(rng.randrange(256), rng.randrange(256), rng.randrange(256)) for _ in range(4096)]
    )
    image.save(path, "JPEG", quality=95)


@pytest.fixture
def library(tmp_path: Path) -> tuple[Path, Path, Path]:
    """An organized drive of four files and an empty second drive."""
    src, drive, target, db = (
        tmp_path / "src",
        tmp_path / "DriveA",
        tmp_path / "DriveB",
        tmp_path / "c.sqlite",
    )
    src.mkdir()
    for i in range(4):
        _jpeg(src / f"p{i}.jpg", seed=i)
    assert main(["drives", "--init", str(drive), "--label", "Photos HDD", "--db", str(db)]) == 0
    assert main(["drives", "--init", str(target), "--label", "Backup HDD", "--db", str(db)]) == 0
    assert main(["organize", str(src), str(drive), "--apply", "--db", str(db)]) == 0
    return drive, target, db


def _run(library: tuple[Path, Path, Path]) -> dict[str, object]:
    source, target, db = library
    result = backup_run(source, target, db)(lambda _p: None, threading.Event())
    assert isinstance(result, dict)
    return result


def _fail_copies(monkeypatch: pytest.MonkeyPatch, *, which: set[int]) -> None:
    """Fail the copies at these 1-based positions, the way a source read failure arrives.

    ⚠ **Injected at `shutil.copy2` inside `safe_copy`**, so the failure arrives through
    `staged_copy`'s own `except OSError` - the real path. Patching backup's helper would assert
    that this test can fail.

    ⚠ **`EACCES`, and it was `EIO` until `(agi)`.** `EIO` is a failing *device*, which outlives
    the file and now stops the run - so these tests would have been asserting the continue policy
    against an errno that no longer continues. A permission on one source file is the honest
    per-file case.
    """
    seen = {"n": 0}
    real = safe_copy.shutil.copy2

    def flaky(src: object, dst: object, *args: object, **kwargs: object) -> object:
        seen["n"] += 1
        if seen["n"] in which:
            raise OSError(errno.EACCES, "Permission denied")
        return real(src, dst, *args, **kwargs)

    monkeypatch.setattr(safe_copy.shutil, "copy2", flaky)


def test_two_bad_files_do_not_stop_the_other_two(
    library: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The policy itself. Before this, file 2 ended the run and files 3 and 4 were never tried."""
    _fail_copies(monkeypatch, which={2, 3})

    summary = _run(library)

    assert summary["copied"] == 2, f"the run did not carry on past the bad files: {summary}"
    assert summary["failed"] == 2


def test_every_failure_is_named_in_the_record_not_just_counted(
    library: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """⚠ A count without names is the `(afa)` shape: the reader cannot act on *two failed*."""
    _fail_copies(monkeypatch, which={2, 3})

    _run(library)

    payload = json.loads(record_path_for(library[2]).read_text(encoding="utf-8"))
    failed = [e for e in payload["files"] if e["status"] == "failed"]
    assert len(failed) == 2, f"the record does not name both failures: {failed}"
    assert all(e["detail"] for e in failed), "a failure is named without a reason"


def test_a_completed_run_with_failures_reports_nothing_never_attempted(
    library: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """⚠ **`failed` and `never_attempted` are different facts and must not blur.**

    Under the old fail-fast the two moved together: a failure ended the run, so everything after
    it was unattempted. Under the policy a run that finishes has attempted **everything**, so
    `stopped` is absent and only `failed` is non-zero. A reader tells a finished-with-failures run
    from a stopped one by exactly that.

    ⚠ **TWO failures, not one, and that is load-bearing.** With one, `len(failures)` and the old
    `1 if failures else 0` are the same number, so a test using one failure cannot see the
    arithmetic at all - proved by mutation: the old expression survived against a single-failure
    test and dies against this one.
    """
    _fail_copies(monkeypatch, which={2, 3})

    _run(library)

    run = json.loads(record_path_for(library[2]).read_text(encoding="utf-8"))["run"]
    assert run["stopped"] is None, f"a completed run reported itself as stopped: {run['stopped']}"
    assert run["attempted"] == run["intended_total"], (
        "a run that reached every file did not report attempting them all"
    )
    assert not any(
        e["status"] == "not attempted"
        for e in json.loads(record_path_for(library[2]).read_text(encoding="utf-8"))["files"]
    )


def test_verified_is_false_when_anything_failed(
    library: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """⚠ **The custody claim.** `verified` was a hardcoded `True` typed `Literal[True]`.

    A product whose core promise is verified custody cannot report a verified run while files
    failed. BackInTime #1587 is the case: per-file failures visible only in an exit code, and
    users believing the backup was fine.
    """
    _fail_copies(monkeypatch, which={2})

    assert _run(library)["verified"] is False


def test_verified_is_still_true_when_nothing_failed(library: tuple[Path, Path, Path]) -> None:
    """⚠ **CRY-WOLF HALF ONE.** A `verified` hardwired to `False`, or derived from the wrong
    thing, would satisfy the row above and quietly retire the banner for every healthy run."""
    summary = _run(library)

    assert summary["failed"] == 0
    assert summary["verified"] is True
    assert summary["copied"] == 4


def test_a_destination_level_failure_still_ends_the_run(
    library: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """⚠ **CRY-WOLF HALF TWO, and the one that matters most.**

    A change that made *everything* continue would pass every row above and be far worse than the
    defect: a run would keep writing into a filling disk, one wasted attempt per remaining file.
    The abort is `_stop_if_ground_moved`'s, unchanged by this stage - what the policy relaxes is
    the per-file case only.
    """
    monkeypatch.setattr(run_health, "TICK_SECONDS", 0.0)
    monkeypatch.setattr(
        run_health, "read_device", lambda _p: run_health.DeviceReading(7, definite=True)
    )
    monkeypatch.setattr(run_health, "free_bytes", lambda _p: 1)

    with pytest.raises(ValueError, match="nearly full"):
        _run(library)


# --- and a condition that outlives the file DOES stop it -------------------------------------


def _real_enospc(monkeypatch: pytest.MonkeyPatch, *, nth: int) -> None:
    """Make the ``nth`` copy hit a **real kernel ENOSPC** by writing to `/dev/full`. `(agi)`

    ⚠ **Not a constructed `OSError`.** The errno comes from the kernel through `shutil`, so this
    exercises delivery as well as classification - two properties, and a synthesised exception
    proves only the second.
    """
    seen = {"n": 0}
    real = safe_copy.shutil.copy2

    def flaky(src: object, dst: object, *args: object, **kwargs: object) -> object:
        seen["n"] += 1
        if seen["n"] == nth:
            safe_copy.shutil.copyfile(str(src), "/dev/full")
        return real(src, dst, *args, **kwargs)

    monkeypatch.setattr(safe_copy.shutil, "copy2", flaky)


@pytest.mark.skipif(not Path("/dev/full").exists(), reason="/dev/full is Linux-specific")
def test_a_full_disk_stops_the_backup_instead_of_failing_every_remaining_file(
    library: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """⚠ **CRY-WOLF HALF TWO for `(afw)`, and the whole of `(agi)`.**

    Before this, a full disk produced one `failed` entry per remaining file - N wasted attempts
    describing one condition, which is `(afa)`'s shape at run scale. It now stops at the file that
    hit it.
    """
    _real_enospc(monkeypatch, nth=2)

    with pytest.raises(OSError, match="No space left"):
        _run(library)

    payload = json.loads(record_path_for(library[2]).read_text(encoding="utf-8"))
    failed = [e for e in payload["files"] if e["status"] == "failed"]
    assert len(failed) == 1, (
        f"the run kept trying after a condition that outlives the file: {failed}"
    )
    assert payload["run"]["stopped"] is not None, "an aborted run reported itself as complete"
    assert payload["run"]["stopped"]["never_attempted"] >= 1


@pytest.mark.skipif(not Path("/dev/full").exists(), reason="/dev/full is Linux-specific")
def test_the_stop_reason_says_which_guard_stopped_it(
    library: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """⚠ **A reader must not need arithmetic to tell the two abort paths apart** (`(agi)` Q44).

    The watcher's abort and the classifier's abort produce the same record SHAPE - deliberately,
    so nothing downstream branches - and `never_attempted` differs by one between them, because
    the watcher stops before attempting a file and the classifier stops after. The **reason** is
    what distinguishes them, and it must, or the two are only tellable apart by counting.
    """
    _real_enospc(monkeypatch, nth=2)

    with pytest.raises(OSError, match="No space left"):
        _run(library)

    reason = json.loads(record_path_for(library[2]).read_text(encoding="utf-8"))["run"]["stopped"][
        "reason"
    ]
    assert "No space left" in reason, f"the classifier's abort is not identifiable: {reason!r}"
    assert "nearly full" not in reason, "the classifier's abort reads as the watcher's"
