"""An organize that stops early still writes down what it did. `(agj)`

⚠ **A REGRESSION FROM ONE COMMIT AGO, and it is named as one rather than filed as a gap.**
`(agi)` gave `execute` its first *raising* stop. Every stop before it was a `break` - the cancel
(`organizer.py:2014`), the health stop (`:2048`) and the catalog stop (`:2077`) - so `execute`
returned normally with partial results and both callers wrote the record on their ordinary path.
`(agi)`'s `raise` at `:1912` leaves that path entirely, and it took the results with it: they are
local to `execute` and nothing outside it can reach them once the frame unwinds.

**`IMPLEMENTATION_STANDARDS.md` §1 makes the record automatic** *"because the user who most needs
it is the one who did not know to ask"* - and that user is exactly this one: a run that stopped
against a full drive is when the paperwork matters most.

**The two surfaces fail differently, and the CLI's is the worse half:**

* the app (`service/organize.py:1223`) writes nothing at all - the exception leaves the function
  above `_write_the_record`;
* the CLI (`cli.py:2882`) writes a record that says **every file was never attempted**, because
  its handler was written for the pre-flight refusal, where `results` really is empty and
  `never_attempted = len(resolutions)` really is true. Mid-run those are false. ⚠ **A false
  custody record is worse than a missing one**: it is `(afa)`'s shape with the reader actively
  misled rather than uninformed.
"""

from __future__ import annotations

import json
import random
import threading
from pathlib import Path

import pytest
from PIL import Image
from truestill_app.service.organize import organize_run
from truestill_cli.cli import main
from truestill_core import safe_copy
from truestill_core.app_paths import record_path_for

_HAS_DEV_FULL = pytest.mark.skipif(
    not Path("/dev/full").exists(), reason="/dev/full is Linux-specific"
)


def _jpeg(path: Path, *, seed: int) -> None:
    rng = random.Random(seed)
    image = Image.new("RGB", (64, 64))
    image.putdata(
        [(rng.randrange(256), rng.randrange(256), rng.randrange(256)) for _ in range(4096)]
    )
    image.save(path, "JPEG", quality=95)


@pytest.fixture
def library(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Four organizable photos, an initialised drive, and a catalog."""
    src, drive, db = tmp_path / "src", tmp_path / "Drive", tmp_path / "c.sqlite"
    src.mkdir()
    for i in range(4):
        _jpeg(src / f"p{i}.jpg", seed=i)
    assert main(["drives", "--init", str(drive), "--label", "Photos HDD", "--db", str(db)]) == 0
    return src, drive, db


def _real_enospc(monkeypatch: pytest.MonkeyPatch, *, nth: int) -> None:
    """Make the nth copy hit a **real kernel `ENOSPC`** by writing to `/dev/full`.

    ⚠ Not a constructed `OSError`: the errno arrives from the kernel through `shutil`, so this
    exercises delivery as well as classification. `(agi)` records why those are two properties.
    """
    seen = {"n": 0}
    real = safe_copy.shutil.copyfile

    def flaky(src: str | Path, dst: str | Path) -> str | Path:
        seen["n"] += 1
        if seen["n"] == nth:
            # ⚠ **`real`, not `safe_copy.shutil.copyfile`.** Since `(aie)` the injection replaces
            # `copyfile` itself, so reaching for it by name inside the stub calls the stub.
            real(str(src), "/dev/full")
        return real(src, dst)

    monkeypatch.setattr(safe_copy.shutil, "copyfile", flaky)


def _record(db: Path) -> dict[str, object]:
    path = record_path_for(db)
    assert path.exists(), "the run stopped and left no record of what it had already done"
    parsed = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(parsed, dict)
    return parsed


# --- the CLI half ----------------------------------------------------------------------------


@_HAS_DEV_FULL
def test_the_cli_records_the_files_it_had_already_organized(
    library: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """⚠ **The false-record half.** Today this writes `attempted: 0` over a run that copied one
    file and failed a second, because the handler it lands in was written for a refusal that
    happens before the first byte."""
    src, drive, db = library
    _real_enospc(monkeypatch, nth=2)

    main(["organize", str(src), str(drive), "--apply", "--db", str(db)])

    payload = _record(db)
    run = payload["run"]
    assert isinstance(run, dict)
    assert run["attempted"] >= 2, (
        f"the record claims the run attempted {run['attempted']} files; it copied one and "
        "failed one before it stopped"
    )
    files = payload["files"]
    assert isinstance(files, list)
    assert sum(1 for e in files if e["status"] == "uploaded") >= 1, (
        "not one of the files that reached the drive is named in the record"
    )
    assert sum(1 for e in files if e["status"] == "failed") == 1


@_HAS_DEV_FULL
def test_the_cli_record_names_the_condition_that_stopped_it(
    library: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The reason must be the drive's, not a generic early stop - and `stop_block` can derive it
    without help, because `(agi)` records the offending file as `FAILED` *before* it re-raises."""
    src, drive, db = library
    _real_enospc(monkeypatch, nth=2)

    main(["organize", str(src), str(drive), "--apply", "--db", str(db)])

    run = _record(db)["run"]
    assert isinstance(run, dict)
    stopped = run["stopped"]
    assert isinstance(stopped, dict), "a run that stopped early reported itself as complete"
    assert "no space left on the drive" in str(stopped["reason"]), (
        f"the record does not say what stopped the run: {stopped['reason']!r}"
    )
    # ⚠ **EXACT, and that is what makes this row fail against today's code.** The old handler
    # hardcoded `len(resolutions)` - 4 - because a pre-flight refusal really has attempted none.
    # Two were attempted here, so two were not.
    assert stopped["never_attempted"] == 2, (
        f"the record says {stopped['never_attempted']} files were never attempted; two were"
    )


# --- the app half ----------------------------------------------------------------------------


@_HAS_DEV_FULL
def test_the_app_writes_a_record_at_all(
    library: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """⚠ **The missing-record half.** `_write_the_record` sits below the `execute` call with
    nothing between them, so the exception carries the run past its own paperwork."""
    src, drive, db = library
    _real_enospc(monkeypatch, nth=2)

    with pytest.raises(Exception):  # noqa: B017, PT011 - the abort itself is `(agi)`'s subject
        organize_run(src, drive, db)(lambda _p: None, threading.Event())

    payload = _record(db)
    run = payload["run"]
    assert isinstance(run, dict)
    assert run["attempted"] >= 2
    stopped = run["stopped"]
    assert isinstance(stopped, dict)
    assert "no space left on the drive" in str(stopped["reason"])


# --- the cry-wolf halves ----------------------------------------------------------------------


def test_a_run_that_finishes_still_records_itself_as_finished(
    library: tuple[Path, Path, Path],
) -> None:
    """⚠ **CRY-WOLF HALF ONE.** A change that reported every run as stopped would satisfy every
    row above and make `stopped` meaningless - the field exists to separate two facts."""
    src, drive, db = library

    assert main(["organize", str(src), str(drive), "--apply", "--db", str(db)]) == 0

    run = _record(db)["run"]
    assert isinstance(run, dict)
    assert run["stopped"] is None, f"a completed run reported itself as stopped: {run['stopped']}"
    assert run["attempted"] == run["intended_total"] == 4


def test_a_per_file_failure_does_not_make_the_run_look_stopped(
    library: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """⚠ **CRY-WOLF HALF TWO.** Recording on abort must not turn organize's ordinary
    partial-failure policy into a stop: one unreadable photo is `failed`, and the run finished."""
    src, drive, db = library
    seen = {"n": 0}
    real = safe_copy.shutil.copyfile

    def flaky(source: str | Path, dest: str | Path) -> str | Path:
        seen["n"] += 1
        if seen["n"] == 2:
            raise OSError(13, "Permission denied")
        return real(source, dest)

    monkeypatch.setattr(safe_copy.shutil, "copyfile", flaky)

    main(["organize", str(src), str(drive), "--apply", "--db", str(db)])

    payload = _record(db)
    run = payload["run"]
    assert isinstance(run, dict)
    assert run["stopped"] is None, "a per-file failure was recorded as a stopped run"
    assert run["attempted"] == 4
    files = payload["files"]
    assert isinstance(files, list)
    assert sum(1 for e in files if e["status"] == "failed") == 1
