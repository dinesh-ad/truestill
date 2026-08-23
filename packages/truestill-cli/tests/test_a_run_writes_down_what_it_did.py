"""After the terminal scrolls, something can answer "which photos failed?". `(afl)`

Before this, nothing could. `--report` wrote a *plan* built from `resolutions` before execution -
no status, no detail, no outcome of any kind - and it only ran when asked for. Nothing else
persisted an outcome either: `files.upload_status` only ever holds ``'uploaded'``, so a row exists
only for a file that succeeded, and there is no logging anywhere in the product.

⚠ That is why `(afd)`'s cap was uncomfortable: the elided failure lines were **the only copy**.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import pytest
from PIL import Image
from truestill_cli.cli import main
from truestill_core.app_paths import record_path_for
from truestill_core.catalog import Catalog
from truestill_core.categorize import CategoryMatch, Confidence
from truestill_core.destinations import LocalDestination
from truestill_core.models import DateSource, Decision, FileHashes, Resolution
from truestill_core.organizer import execute
from truestill_core.run_record import (
    RunHeader,
    build_run_record,
    files_from_resolutions,
    stop_block,
)

_POSIX_ONLY = pytest.mark.skipif(
    sys.platform == "win32",
    reason="chmod 555 does not deny the owner on Windows; this refusal has no Windows equivalent",
)


def _jpeg(path: Path, seed: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (48 + seed, 48), (seed * 7 % 255, 90, 140)).save(path, "JPEG", quality=95)


@pytest.fixture
def library(tmp_path: Path) -> tuple[Path, Path, Path]:
    src, dest, db = tmp_path / "src", tmp_path / "dest", tmp_path / "cat" / "c.sqlite"
    for i in range(4):
        _jpeg(src / f"p{i}.jpg", seed=i)
    return src, dest, db


def _record(db: Path) -> dict:
    return json.loads(record_path_for(db).read_text(encoding="utf-8"))


def test_a_run_records_itself_without_being_asked(
    library: tuple[Path, Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    """⚠ Automatic, because opt-in gets it wrong for exactly one user: the one who did not know.

    `--report` used to decide *whether* a record existed. It now decides only where it goes.
    """
    src, dest, db = library

    assert main(["organize", str(src), str(dest), "--apply", "--db", str(db)]) == 0

    record = _record(db)
    # 2 since `(afw)`: the `run` block gained `kind` and a `files` entry's shape now
    # depends on it. A literal rather than the constant, deliberately - this is the
    # line that makes a format bump an edit somebody made on purpose.
    # ⚠ **3 since undo joined**: a `files` entry's shape depends on `run.kind`, and undo is a
    # third shape. `(afw)`
    assert record["format"] == 3
    assert record["run"]["intended_total"] == 4
    assert record["run"]["attempted"] == 4
    assert record["run"]["stopped"] is None
    assert len(record["files"]) == 4
    assert "This run is recorded in" in capsys.readouterr().out, "it does not name the file"


def test_the_record_says_what_happened_not_what_was_planned(
    library: tuple[Path, Path, Path],
) -> None:
    """The whole point. A plan report cannot carry an outcome, and this one does."""
    src, dest, db = library

    main(["organize", str(src), str(dest), "--apply", "--db", str(db)])

    row = _record(db)["files"][0]
    assert row["status"] == "uploaded", "the record carries no outcome"
    assert row["landed_at"], "where the file actually went is not recorded"
    # And it keeps everything the plan report carried, so nothing was traded away.
    for key in ("category", "confidence", "rule", "captured_at", "date_source", "is_unique"):
        assert key in row


@_POSIX_ONLY
def test_a_stopped_run_records_what_it_never_attempted(tmp_path: Path) -> None:
    """⚠ A record silent about what was never tried READS AS COMPLETE AND IS NOT.

    The same shape as `unreachable` meaning four things in `(afa)`.

    ⚠ **Driven through `execute` rather than `main`, and that is stated rather than skipped.**
    The stop needs the catalog to open and *then* become unwritable, which through the CLI needs a
    watcher racing a real run - `(afe)`'s own regression uses the progress callback for exactly
    this reason. Everything here is real: a real refusal, real results from a real stop, and the
    record built by the same function the CLI calls. Only `main`'s argument parsing is bypassed.
    """
    src, cat_dir = tmp_path / "src", tmp_path / "cat"
    cat_dir.mkdir()
    resolutions = []
    for i in range(12):
        path = src / f"p{i:02d}.jpg"
        _jpeg(path, seed=i)
        category = CategoryMatch(
            label="Camera", reason="t", confidence=Confidence.MEDIUM, rule="device"
        )
        resolutions.append(
            Resolution(
                decision=Decision(
                    source=path,
                    category=category,
                    captured_at=datetime(2013, 10, 3, 6, 51),
                    date_source=DateSource.EXIF,
                    date_tag="DateTimeOriginal",
                    relative=Path(f"Camera/2013/10/p{i:02d}.jpg"),
                ),
                hashes=FileHashes(sha256=f"{i:064d}", perceptual=None),
                exact_duplicate=None,
                near_duplicate=None,
            )
        )

    catalog = Catalog(cat_dir / "catalog.sqlite")

    def deny_once_files_are_landing(progress: object) -> None:
        if getattr(progress, "done", 0) == 4:
            cat_dir.chmod(0o555)

    try:
        results = execute(
            resolutions,
            LocalDestination(tmp_path / "dest"),
            catalog=catalog,
            apply=True,
            progress=deny_once_files_are_landing,
        )
    finally:
        cat_dir.chmod(0o755)

    if len(results) == len(resolutions):
        pytest.skip("running as root, or a filesystem that ignores the mode")

    record = build_run_record(
        RunHeader(kind="organize", source=str(src), destination=str(tmp_path / "dest")),
        files=files_from_resolutions(resolutions, results),
        intended_total=len(resolutions),
        attempted=len(results),
        stopped=stop_block(resolutions, results),
    )
    stopped = record["run"]["stopped"]
    assert stopped is not None, "a run that stopped early reported itself as complete"
    assert record["run"]["intended_total"] == 12
    assert stopped["never_attempted"] == 12 - record["run"]["attempted"]
    assert "catalog could not be written" in stopped["reason"]
    assert any(f["status"] == "not attempted" for f in record["files"]), (
        "the files the run never reached are absent, so the record reads as complete"
    )


def test_a_run_that_finished_records_no_stop(library: tuple[Path, Path, Path]) -> None:
    """The cry-wolf half: an ordinary run must not report a stop it did not have."""
    src, dest, db = library

    main(["organize", str(src), str(dest), "--apply", "--db", str(db)])

    assert _record(db)["run"]["stopped"] is None


def test_a_preview_writes_nothing(library: tuple[Path, Path, Path]) -> None:
    """⚠ THE BEHAVIOUR CHANGE, pinned deliberately.

    `--report` used to write a plan report during a dry run, while the DRY RUN banner said
    *"nothing was written or recorded"*. The plan report answered "what would happen" and the
    record answers "what happened"; one file cannot honestly be both, so the preview writes
    neither and the banner is true in every case.
    """
    src, dest, db = library

    main(["organize", str(src), str(dest), "--db", str(db)])

    assert not record_path_for(db).exists()


def test_report_moves_the_record_and_does_not_make_a_second(
    library: tuple[Path, Path, Path], tmp_path: Path
) -> None:
    """`--report` says WHERE, never WHETHER. One record, one shape, one code path."""
    src, dest, db = library
    elsewhere = tmp_path / "elsewhere" / "run.json"

    main(["organize", str(src), str(dest), "--apply", "--db", str(db), "--report", str(elsewhere)])

    assert elsewhere.exists()
    assert not record_path_for(db).exists(), "it wrote two records"


@_POSIX_ONLY
def test_a_record_that_cannot_be_written_does_not_break_the_run(
    library: tuple[Path, Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    """⚠ Never-raising matters more now than it did for `--report`.

    This is written on every applied run rather than on request, so an unwritable location would
    turn a successful organize into a traceback about its own paperwork.
    """
    src, dest, db = library
    denied = src.parent / "denied"
    denied.mkdir()
    denied.chmod(0o555)
    try:
        try:
            (denied / "probe").touch()
            pytest.skip("running as root, or a filesystem that ignores the mode")
        except PermissionError:
            pass
        code = main(
            [
                "organize",
                str(src),
                str(dest),
                "--apply",
                "--db",
                str(db),
                "--report",
                str(denied / "run.json"),
            ]
        )
    finally:
        denied.chmod(0o755)

    assert code == 0, "a successful run failed because its record could not be written"
    assert "Could not write the run record" in capsys.readouterr().err
    assert (dest).exists(), "the run did not do its actual job"
