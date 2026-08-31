"""A backup that stops mid-copy must say what landed, not print a traceback. `(ajd)`

**Measured in soak eleven, twice, on two code paths.** A stick pulled during `backup --apply` gave
the user this:

    OSError: [Errno 5] copying 2014/…/20140815_155529.jpg failed: [Errno 5] Input/output error
      File ".../backup.py", line 490, in _copy_missing
      File ".../backup.py", line 338, in _stop_the_run

**`organize` met the identical accident four hours earlier** and answered with a named file, a
cause in English, ``2062 organized / 1 failed / 478 not attempted`` and exit 4.

🔑 **The core was right to raise; the SURFACE had no arm for it.** `_stop_the_run` re-raises on
purpose so the run record is written. The CLI caught only `ValueError`, so every `OSError` walked
past it. **`backup` is the command a user runs when they are already worried**, and a stack trace
is the worst possible answer to *"is my second copy safe?"*
"""

from __future__ import annotations

import threading
from pathlib import Path

import pytest
import truestill_core.backup as backup_module
from truestill_cli.cli import main
from truestill_core.backup import BackupPair, BackupStoppedError, copy_to_drive
from truestill_core.catalog import Catalog
from truestill_core.drive import create_marker, read_marker
from truestill_core.hashing import sha256_file


def _silent(*_args: object, **_kwargs: object) -> None:
    """A progress sink: these tests are about the ending, not the ticking."""


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


def _vanish_after(monkeypatch: pytest.MonkeyPatch, *, after: int) -> None:
    """Make the target stop responding part way, the way a pulled stick does."""
    real = backup_module.DestinationDevice.check
    seen = {"n": 0}

    def patched(self: object, root: Path) -> None:
        seen["n"] += 1
        if seen["n"] > after:
            raise OSError(5, "Input/output error")
        real(self, root)  # type: ignore[arg-type]

    monkeypatch.setattr(backup_module.DestinationDevice, "check", patched)


def test_the_stop_carries_what_landed_instead_of_a_bare_oserror(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """THE DETECTOR. Against today's code this raises a bare `OSError` with no counts on it."""
    src, dst, db = _library(tmp_path)
    _vanish_after(monkeypatch, after=2)
    src_marker, dst_marker = read_marker(src), read_marker(dst)
    assert src_marker is not None
    assert dst_marker is not None

    with pytest.raises(BackupStoppedError) as caught:
        copy_to_drive(
            BackupPair(src, src_marker, dst, dst_marker),
            db,
            progress=_silent,
            cancel=threading.Event(),
        )

    assert caught.value.copied == 2, "the stop did not carry how many had landed"
    assert isinstance(caught.value.__cause__, OSError), "the original errno was lost"
    assert "Input/output error" in caught.value.detail


def test_the_cli_prints_the_count_and_exits_4_rather_than_a_traceback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """⚠ THE SURFACE, which is where the defect lived. A correct core nobody catches still crashes."""
    src, dst, db = _library(tmp_path)
    _vanish_after(monkeypatch, after=2)

    code = main(["backup", str(src), str(dst), "--apply", "--db", str(db)])

    printed = capsys.readouterr()
    assert code == 4, "a stopped backup did not use the destination exit code"
    assert "copied before the run stopped" in printed.out, "the user was not told what landed"
    assert "2" in printed.out
    assert "not attempted" in printed.err, "the user was not told what was skipped"
    assert "Traceback" not in printed.out + printed.err


def test_an_ordinary_backup_still_says_nothing_about_stopping(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """⚠ CRY-WOLF. Nothing went wrong, so no stop language may appear."""
    src, dst, db = _library(tmp_path)

    code = main(["backup", str(src), str(dst), "--apply", "--db", str(db)])

    printed = capsys.readouterr()
    assert code == 0
    assert "copied before the run stopped" not in printed.out
    assert "not attempted" not in printed.err
