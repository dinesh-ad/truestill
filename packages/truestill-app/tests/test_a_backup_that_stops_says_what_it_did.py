"""A backup that stops still writes down what it did. `(afw)`

`IMPLEMENTATION_STANDARDS.md` §1's run-record invariant - *"a run that changes the library writes
down what it did"* - is **not conditional on the run finishing**. Backup builds its summary at the
`return`, so a raise part-way through left nothing at all: the files already copied had
`file_copies` rows, and nothing anywhere said which file stopped the run, why, or how many were
never attempted.

**Driven through `backup_run` rather than against a helper**, because the defect is what a real
run leaves behind. A helper that returns the right object to nobody is what was already true.

⚠ **This asserts the RECORD, never merely that the run raised.** The raise already happens today;
a test that stops at `pytest.raises` passes against the defect and proves nothing. It is the
`(afa)` shape that decides the rest: naming the file without the reason would be one word standing
in for four different causes, so the reason is asserted too.

**Out of scope here, and both are Stage 4** (`(afw)`): whether backup should carry on past a bad
file at all - `ENGINEERING_STANDARD.md` §4 Errors' *"one bad file never aborts a batch"* - and
whether the app tells the user where the record went.
"""

from __future__ import annotations

import json
import random
import threading
from pathlib import Path

import pytest
from PIL import Image
from truestill_app.service import backup
from truestill_app.service.backup import backup_run
from truestill_cli.cli import main
from truestill_core import safe_copy
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


def _fail_on_copy_number(monkeypatch: pytest.MonkeyPatch, *, nth: int) -> None:
    """Make the ``nth`` staged copy fail the way a disk going read-only does.

    ⚠ **Injected at `shutil.copy2` inside `safe_copy`, not at backup's own helper.** The failure
    has to arrive the way a real one does - through `staged_copy`'s single `except OSError`, which
    is the site that cannot tell a source read from a destination write (`(afw)` Stage 1). A test
    that patched `_copy_verified_or_raise` would assert that this test can raise.
    """
    seen = {"n": 0}
    real = safe_copy.shutil.copy2

    def flaky(src: object, dst: object, *args: object, **kwargs: object) -> object:
        seen["n"] += 1
        if seen["n"] == nth:
            raise OSError(30, "Read-only file system")
        return real(src, dst, *args, **kwargs)

    monkeypatch.setattr(safe_copy.shutil, "copy2", flaky)


def test_a_backup_that_stops_still_says_what_it_did(
    library: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The record exists, names the file that stopped it, and says how many were never tried."""
    source, target, db = library
    _fail_on_copy_number(monkeypatch, nth=2)

    with pytest.raises(OSError, match="Read-only file system"):
        backup_run(source, target, db)(lambda _p: None, threading.Event())

    record = record_path_for(db)
    assert record.exists(), (
        "a backup that stopped wrote no record at all; the files it had already copied and the "
        "file that stopped it are recoverable from nothing"
    )
    payload = json.loads(record.read_text(encoding="utf-8"))

    statuses = {entry["relative"]: entry["status"] for entry in payload["files"]}
    assert "uploaded" in statuses.values(), "the copies that succeeded are absent from the record"
    failed = [rel for rel, status in statuses.items() if status == "failed"]
    assert len(failed) == 1, f"expected exactly one failed entry, got {failed}"

    stopped = payload["run"]["stopped"]
    assert stopped is not None, "the record does not say the run stopped early"
    assert stopped["never_attempted"] >= 1, (
        "a record silent about what was never tried reads as complete and is not"
    )


def test_the_record_says_why_and_not_only_which(
    library: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """⚠ **The `(afa)` half.** A record naming the file and not the cause is one word standing in
    for four - a source that vanished, a destination that refused, a full disk and a hash mismatch
    all read identically, and the reader cannot tell which happened to them."""
    source, target, db = library
    _fail_on_copy_number(monkeypatch, nth=2)

    with pytest.raises(OSError, match="Read-only file system"):
        backup_run(source, target, db)(lambda _p: None, threading.Event())

    payload = json.loads(record_path_for(db).read_text(encoding="utf-8"))
    failed = [entry for entry in payload["files"] if entry["status"] == "failed"]

    assert failed, "no failed entry to carry a reason"
    assert failed[0]["detail"], "the failed entry names the file and not why it failed"
    assert "Read-only file system" in failed[0]["detail"], (
        f"the reason does not carry what the filesystem actually said: {failed[0]['detail']!r}"
    )
    assert payload["run"]["stopped"]["reason"], "the stop block carries no reason"


def test_the_record_identifies_the_drive_by_uuid_not_only_by_label(
    library: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """⚠ **The uuid is authoritative and the label is the human name.**

    A label can be renamed in Settings; the marker uuid is what this product already treats as
    drive identity everywhere else. A record naming a since-relabelled drive is unresolvable,
    which defeats the record.
    """
    source, target, db = library
    _fail_on_copy_number(monkeypatch, nth=2)

    with pytest.raises(OSError, match="Read-only file system"):
        backup_run(source, target, db)(lambda _p: None, threading.Event())

    run = json.loads(record_path_for(db).read_text(encoding="utf-8"))["run"]
    marker = json.loads((target / ".truestill-drive.json").read_text(encoding="utf-8"))

    assert run["destination_uuid"] == marker["uuid"], (
        "the record does not identify the destination drive by its marker uuid"
    )
    assert run["destination_label"] == "Backup HDD"


def test_a_record_that_cannot_be_written_does_not_replace_the_real_failure(
    library: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """⚠ **The cry-wolf half, and the reason `_recorder` catches `Exception` not `OSError`.**

    The record is written from inside an `except` block. Anything it raises there **replaces the
    exception being handled** - so a run stopped by a read-only disk would surface as a
    `TypeError` about paperwork, which is this stage's own defect one level up.
    `IMPLEMENTATION_STANDARDS.md` §1: *"Its own failure must never fail the run."*
    """
    source, target, db = library
    _fail_on_copy_number(monkeypatch, nth=2)

    message = "Object of type Path is not JSON serializable"

    def explode(*_a: object, **_k: object) -> None:
        raise TypeError(message)

    monkeypatch.setattr(backup, "build_run_record", explode)

    with pytest.raises(OSError, match="Read-only file system"):
        backup_run(source, target, db)(lambda _p: None, threading.Event())
