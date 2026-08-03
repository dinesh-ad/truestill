"""Backup's free-space check measured the wrong disk, and now a second one measures the right one.

The check that was already here reads ``shutil.disk_usage(target).free``. On a mounted cloud
drive that is the **remote's** free space; the disk that actually fills is this computer's,
because the client caches everything written to it. That is exactly the confusion `RunHealth`
was written to correct, and backup had its own copy of it.

**What backup does not gain, said plainly:** the device watch. This loop already calls
`DestinationDevice.check` per file, which **fails closed on the first bad reading** and is
therefore stricter than a periodic three-strike watch. The watcher's device half will
essentially never be the thing that fires here; the space half is why it is wired in.

Driven through `backup_run` rather than against the helper, because the defect is that a real
run keeps writing - a helper returning the right verdict to nobody is what was already true.
"""

from __future__ import annotations

import random
import threading
from pathlib import Path

import pytest
from PIL import Image
from truestill_app.service.backup import backup_run
from truestill_cli.cli import main
from truestill_core import run_health
from truestill_core.run_health import ABSOLUTE_FLOOR_BYTES

_GB = 1024**3


def _jpeg(path: Path, *, seed: int) -> None:
    rng = random.Random(seed)
    image = Image.new("RGB", (64, 64))
    image.putdata(
        [(rng.randrange(256), rng.randrange(256), rng.randrange(256)) for _ in range(4096)]
    )
    image.save(path, "JPEG", quality=95)


@pytest.fixture
def library(tmp_path: Path) -> tuple[Path, Path, Path]:
    """An organized drive and an empty second drive. Returns (source, target, db)."""
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


def _run(library: tuple[Path, Path, Path]) -> object:
    source, target, db = library
    return backup_run(source, target, db)(lambda _p: None, threading.Event())


def test_a_backup_stops_when_this_computer_fills_up(
    library: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The drive has room; the computer does not. Backup could not previously tell."""
    monkeypatch.setattr(run_health, "TICK_SECONDS", 0.0)
    monkeypatch.setattr(
        run_health, "read_device", lambda _p: run_health.DeviceReading(7, definite=True)
    )
    monkeypatch.setattr(run_health, "free_bytes", lambda _p: ABSOLUTE_FLOOR_BYTES // 2)

    with pytest.raises(ValueError, match="this computer's disk"):
        _run(library)


def test_the_stop_points_at_the_cache_and_not_at_the_drive(
    library: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A user looking at a half-empty 4 TB drive needs to be sent to the right place."""
    monkeypatch.setattr(run_health, "TICK_SECONDS", 0.0)
    monkeypatch.setattr(
        run_health, "read_device", lambda _p: run_health.DeviceReading(7, definite=True)
    )
    monkeypatch.setattr(run_health, "free_bytes", lambda _p: ABSOLUTE_FLOOR_BYTES // 2)

    with pytest.raises(ValueError, match="Stopped") as caught:
        _run(library)
    assert "cache" in str(caught.value)


def test_a_healthy_backup_is_untouched(library: tuple[Path, Path, Path]) -> None:
    """Cry-wolf, with the real clock and the real disk: every file copied, nothing raised."""
    summary = _run(library)
    assert summary["copied"] == 4  # type: ignore[index]
    assert summary["verified"] is True  # type: ignore[index]


def test_what_was_already_copied_stays_recorded(
    library: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A stop must not undo the run. Raising loses the *summary*, never the custody rows: each
    copy is recorded as it is made, so the next run resumes from there rather than starting over.
    """
    source, target, db = library
    monkeypatch.setattr(run_health, "TICK_SECONDS", 0.0)
    monkeypatch.setattr(
        run_health, "read_device", lambda _p: run_health.DeviceReading(7, definite=True)
    )
    free = {"bytes": 500 * _GB}
    monkeypatch.setattr(run_health, "free_bytes", lambda _p: free["bytes"])

    calls = {"n": 0}
    real_check = run_health.RunHealth.check

    def _tighten(self, **kwargs: int):  # type: ignore[no-untyped-def]
        calls["n"] += 1
        if calls["n"] > 2:  # let a couple of files land, then fill the disk
            free["bytes"] = ABSOLUTE_FLOOR_BYTES // 2
        return real_check(self, **kwargs)

    monkeypatch.setattr(run_health.RunHealth, "check", _tighten)

    with pytest.raises(ValueError, match="this computer's disk"):
        backup_run(source, target, db)(lambda _p: None, threading.Event())

    assert list(target.rglob("*.jpg")), "the files copied before the stop are still there"
