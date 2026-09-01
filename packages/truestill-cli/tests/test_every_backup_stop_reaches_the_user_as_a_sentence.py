"""Every way a backup can stop reaches the user as a sentence, not a traceback. `(ajg)`

**Why this exists rather than one more arm.** `(ajd)` shipped on 2026-08-31 to stop a stopped
backup printing a stack trace. It caught `BackupStoppedError`. On 2026-09-01 soak twelve's app half
measured `backup` on a vanished drive and got an **eight-frame traceback** anyway, because
`device.check` raises `DestinationError` - a `RuntimeError`, which neither of that commit's two
arms could see.

🔑 **The correction is the UNIT, not the arm.** The surfaces had been enumerated per *defect*: find
the class that escaped, catch it, stop. What catches this is per **(surface x class that can reach
it)** - so this file drives every member of `cli._BACKUP_STOPS` through the real boundary and
asserts the same contract for each. A fifth class added to core with no arm fails here, which a
tuple on its own could never notice.

**The contract, one sentence:** a stop exits 4, says something a person can act on, and never
shows them a traceback.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
import truestill_core.backup as backup_module
from truestill_cli.cli import _BACKUP_STOPS, main
from truestill_core.backup import BackupStoppedError
from truestill_core.catalog import Catalog
from truestill_core.destinations.base import DestinationError
from truestill_core.drive import create_marker
from truestill_core.hashing import sha256_file


def _library(tmp_path: Path) -> tuple[Path, Path, Path]:
    db = tmp_path / "c.sqlite"
    src, dst = tmp_path / "source", tmp_path / "target"
    src.mkdir()
    dst.mkdir()
    src_uuid = create_marker(src, label="source").uuid
    dst_uuid = create_marker(dst, label="target").uuid
    with Catalog(db) as catalog:
        catalog.upsert_drive(uuid=src_uuid, label="source")
        catalog.upsert_drive(uuid=dst_uuid, label="target")
        for n in range(4):
            rel = f"a/{n}.jpg"
            path = src / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(bytes([n]) * (400 + n))
            catalog.record_uploaded(
                source_path=f"/src/{rel}",
                original_name=f"{n}.jpg",
                sha256=sha256_file(path),
                copy_sha256=sha256_file(path),
                perceptual=None,
                size=path.stat().st_size,
                captured_at="2024-01-01T00:00:00",
                category="Camera",
                relative=rel,
                drive_uuid=src_uuid,
            )
    return src, dst, db


#: One instance per class core can raise past `_copy_missing`, with the guard that raises it.
#: `BackupStoppedError` is absent on purpose - it is not raised by a guard, it is the wrapper
#: `_copy_missing` builds around an `OSError`, and `test_a_stopped_backup_says_what_landed.py`
#: already drives that path end to end. Raising an `OSError` here produces it.
_STOPS = [
    pytest.param(OSError(5, "Input/output error"), id="oserror-wrapped-as-BackupStoppedError"),
    pytest.param(ValueError("this computer's disk is nearly full"), id="ValueError-health-stop"),
    pytest.param(
        DestinationError("no longer the drive this run started on"), id="DestinationError"
    ),
    pytest.param(sqlite3.OperationalError("database is locked"), id="sqlite3.Error"),
]


def _raise_on_check(monkeypatch: pytest.MonkeyPatch, exc: BaseException, *, after: int) -> None:
    """Make the drive guard fail the way each real one does: partway through, not at the door."""
    real = backup_module.DestinationDevice.check
    seen = {"n": 0}

    def patched(self: object, root: Path) -> None:
        seen["n"] += 1
        if seen["n"] > after:
            raise exc
        real(self, root)  # type: ignore[arg-type]

    monkeypatch.setattr(backup_module.DestinationDevice, "check", patched)


@pytest.mark.parametrize("exc", _STOPS)
def test_a_stop_exits_4_and_shows_no_traceback(
    exc: BaseException,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """⚠ THE DETECTOR. Before `(ajg)` the `DestinationError` case escaped `main` entirely."""
    src, dst, db = _library(tmp_path)
    _raise_on_check(monkeypatch, exc, after=2)

    code = main(["backup", str(src), str(dst), "--apply", "--db", str(db)])

    printed = capsys.readouterr()
    assert code == 4, f"{type(exc).__name__} did not use the stopped-run exit code"
    assert "error:" in printed.err, f"{type(exc).__name__} said nothing a person can act on"
    assert "Traceback" not in printed.out + printed.err


@pytest.mark.parametrize("exc", _STOPS)
def test_a_stop_never_invents_a_count_the_type_cannot_supply(
    exc: BaseException,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """`(ajg)`'s own ruling: *"Do not print a count the type cannot supply."*

    Only the `OSError` path is wrapped into `BackupStoppedError`, which carries `copied`. The
    others are raised by a guard that runs **before** a copy, so the run may have copied many
    files or none - and `0 copied` would be the false custody record `_stopped_run_exit` calls
    worse than no record.
    """
    src, dst, db = _library(tmp_path)
    _raise_on_check(monkeypatch, exc, after=2)

    main(["backup", str(src), str(dst), "--apply", "--db", str(db)])

    out = capsys.readouterr().out
    if isinstance(exc, OSError):
        assert "copied before the run stopped" in out
    else:
        assert "copied before the run stopped" not in out, (
            f"{type(exc).__name__} carries no count and the surface printed one anyway"
        )


def test_the_enumeration_and_the_handler_cannot_drift_apart() -> None:
    """Every class this file drives is one `_BACKUP_STOPS` names, and vice versa.

    Without this, adding a case here and forgetting the tuple - or the reverse - leaves the two
    halves of the same claim disagreeing, which is `(ajd)`'s failure with a different shape.
    """
    # ⚠ **What is RAISED is not always what ARRIVES**, and getting this backwards is what the
    # first draft of this test did. `_copy_missing` wraps an `OSError` cause into
    # `BackupStoppedError` and bare-re-raises everything else, so the class at the boundary is
    # `BackupStoppedError` for the `OSError` case and the raised class for every other.
    arriving = {
        BackupStoppedError if isinstance(param.values[0], OSError) else type(param.values[0])
        for param in _STOPS
    }
    for cls in arriving:
        assert issubclass(cls, _BACKUP_STOPS), f"{cls.__name__} is not caught by _BACKUP_STOPS"
    assert len(_BACKUP_STOPS) == len(arriving), (
        "_BACKUP_STOPS and this file's cases have drifted; one of them was updated alone"
    )
