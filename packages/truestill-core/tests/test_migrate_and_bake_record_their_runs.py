"""Migrate leaves a record; bake leaves a line and no detail. `(agm)`

⚠ **THE ENTRY WAS CARRIED ON TWO ARGUMENTS AND BOTH WERE WRONG.** It said migrate needed no record
because `migration_journal` already held per-file state durably. `start_migration_run` **deletes
the previous run's journal** (`catalog.py:1486`) - *"exactly one run's worth of reversal record
exists per drive"* - so that store has retention ONE and its consumer is undo. Migrate was the
surface with the history gap, and the entry led with the argument against it.

And bake's answer was right for a reason never given: not *"returns counts"* but
`file_copies.date_baked_at`, a **permanent per-copy timestamp** that outlives every later run.
That is why bake writes a line and no detail - `BakeOutcome` names only drives and `relative` is
discarded each pass, so `files` would be `[]` at any size, while which copies it wrote is held
permanently somewhere a byte budget cannot prune.

⚠ **NOTHING IN THE PRODUCT READS EITHER ARTEFACT YET**, checked rather than assumed: `grep -rn
"record_path_for\\|run_index_for"` over `packages/*/src` returns writers only. So these tests read
the files directly, and `run_record.py`'s *"a state every reader already handles"* is a design
intent rather than a measured property. Recorded because it bounds what this file proves.
"""

from __future__ import annotations

import errno
import json
import threading
from datetime import datetime
from pathlib import Path, PurePosixPath

import pytest
from PIL import Image
from truestill_core.app_paths import record_path_for, run_index_for
from truestill_core.bake import CONFIRM_WORD, bake_confirmed_dates
from truestill_core.catalog import Catalog
from truestill_core.destinations.base import DestinationError
from truestill_core.destinations.local import LocalDestination
from truestill_core.drive import create_marker
from truestill_core.hashing import sha256_file
from truestill_core.layout import LayoutScheme, LayoutTemplate
from truestill_core.migrate import run_migration
from truestill_core.progress import Phase, Progress

_DDL = "{category}/{yyyy}"  # drops the month the default adds -> every dated file must move


def _scheme() -> LayoutScheme:
    parsed = LayoutTemplate.parse(_DDL)
    return LayoutScheme.of(timeline=parsed, timeline_evented=parsed, side_bin=parsed)


def _seed(catalog: Catalog, root: Path, count: int) -> None:
    catalog.upsert_drive(uuid="D1", label="Drive A")
    for index in range(count):
        relative = f"Camera/2023/08/p{index}.jpg"
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(f"content-{index}".encode())
        catalog.record_uploaded(
            source_path=f"/src/p{index}.jpg",
            original_name=f"p{index}.jpg",
            sha256=sha256_file(path),
            copy_sha256=sha256_file(path),
            perceptual=None,
            size=path.stat().st_size,
            captured_at="2023-08-20T14:30:00",
            category="Camera",
            relative=relative,
            drive_uuid="D1",
        )


class _RaisesOnChecksum(LocalDestination):
    """One file nobody can read. `ENOENT` is refused-and-continue, not a reason to stop."""

    def __init__(self, root: Path, *, only: str) -> None:
        super().__init__(root)
        self._only = only

    def checksum(self, relative_path: str) -> str:
        if PurePosixPath(relative_path).name == self._only:
            reason = OSError(errno.ENOENT, "injected")
            message = f"cannot checksum {relative_path!r}"
            raise DestinationError(message) from reason
        return super().checksum(relative_path)


def _lines(db: Path) -> list[dict[str, object]]:
    index = run_index_for(db)
    if not index.is_file():
        return []
    return [json.loads(line) for line in index.read_text(encoding="utf-8").splitlines() if line]


# --- migrate -------------------------------------------------------------------------------


def test_an_applied_migration_leaves_a_line_and_a_detail_file(tmp_path: Path) -> None:
    """The record itself, at both layers the split created."""
    db, root = tmp_path / "c.sqlite", tmp_path / "drive"
    with Catalog(db) as catalog:
        _seed(catalog, root, 3)
        outcome = run_migration(catalog, LocalDestination(root), "D1", _scheme(), apply=True)

    assert outcome.migrated == 3
    (line,) = _lines(db)
    assert line["kind"] == "migrate"
    assert line["intended_total"] == 3
    assert line["attempted"] == 3
    assert line["stopped"] is False
    assert isinstance(line["run_id"], str), "migrate is the only surface that passes a run_id"
    assert line["run_id"], "without it a superseded detail file cannot identify itself"

    detail = json.loads(record_path_for(db).read_text(encoding="utf-8"))
    assert detail["run"]["kind"] == "migrate"
    assert detail["run"]["destination_uuid"] == "D1"


def test_a_preview_records_nothing(tmp_path: Path) -> None:
    """⚠ **A run that moved nothing must not appear in the history**, or the index stops meaning
    *"what happened to this library"* and starts meaning *"what was considered"*."""
    db, root = tmp_path / "c.sqlite", tmp_path / "drive"
    with Catalog(db) as catalog:
        _seed(catalog, root, 3)
        outcome = run_migration(catalog, LocalDestination(root), "D1", _scheme(), apply=False)

    assert outcome.applied is False
    assert _lines(db) == []
    assert not record_path_for(db).is_file()


def test_the_record_names_what_it_refused_and_not_what_it_moved(tmp_path: Path) -> None:
    """**Failures-only is the ruling** (`(afd)`: *a failure list is one fact, not two thousand*).

    ⚠ **The assertion that matters is the NEGATIVE one.** An every-file record would cost 10-15
    MiB of a 64 MiB budget on a 33,000-file library to say "moved" thirty-three thousand times,
    and push out a record somebody needs. So this checks both that the refusal is named **and**
    that the three successes are absent.
    """
    db, root = tmp_path / "c.sqlite", tmp_path / "drive"
    with Catalog(db) as catalog:
        _seed(catalog, root, 4)
        outcome = run_migration(
            catalog, _RaisesOnChecksum(root, only="p1.jpg"), "D1", _scheme(), apply=True
        )

    assert outcome.stopped is None, "one vanished file is not a reason to stop"
    assert outcome.migrated == 3
    detail = json.loads(record_path_for(db).read_text(encoding="utf-8"))
    files = detail["files"]

    assert len(files) == 1, f"failures-only, and this holds {len(files)}"
    assert files[0]["status"] == "failed"
    assert "p1.jpg" in str(files[0]["relative"])
    assert not any("p0.jpg" in str(entry["relative"]) for entry in files), (
        "a moved file must not appear; `migrated` counts them and `plan.moves` names them"
    )
    (line,) = _lines(db)
    assert line["attempted"] == 4, "attempted counts the refusal too - it was reached"


def test_a_stopped_migration_records_why_and_how_much_it_never_reached(tmp_path: Path) -> None:
    """⚠ **`(agj)`'s lesson**: the runs that most need a record are the ones that stopped, and its
    record call sat where a stop went around it. This one is written after the loop, on every
    applied path."""
    db, root = tmp_path / "c.sqlite", tmp_path / "drive"
    cancel = threading.Event()

    def _stop_after_the_first_move(progress: Progress) -> None:
        # ⚠ Driven from the MOVING tick, not from a `Destination` override: a local move goes
        # through `relocate`, so hooking `upload` cancels nothing and the test passes vacuously
        # by migrating everything. Planning ticks too, and cancelling there returns applied=False.
        if progress.phase is Phase.MOVING:
            cancel.set()

    with Catalog(db) as catalog:
        _seed(catalog, root, 4)
        outcome = run_migration(
            catalog,
            LocalDestination(root),
            "D1",
            _scheme(),
            apply=True,
            cancel=cancel,
            progress=_stop_after_the_first_move,
        )

    assert outcome.stopped is not None
    detail = json.loads(record_path_for(db).read_text(encoding="utf-8"))
    stopped = detail["run"]["stopped"]
    assert stopped["kind"] == "cancelled", "a user's cancel must never read as a failing drive"
    assert stopped["never_attempted"] > 0
    assert _lines(db)[0]["stopped"] is True


# --- bake ----------------------------------------------------------------------------------


def _baked_library(tmp_path: Path) -> tuple[Path, Path, object]:
    """One confirmed photo on a real drive."""
    db, here = tmp_path / "c.sqlite", tmp_path / "Everyday"
    here.mkdir()
    marker = create_marker(here, label="Everyday")
    with Catalog(db) as catalog:
        catalog.upsert_drive(uuid=marker.uuid, label=marker.label)
        path = here / "Camera/2014/a.jpg"
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (48, 32), "navy").save(path)
        sha = sha256_file(path)
        catalog.record_uploaded(
            source_path="/src/a.jpg",
            original_name="a.jpg",
            sha256=sha,
            copy_sha256=sha,
            perceptual=None,
            size=path.stat().st_size,
            captured_at="2014-08-16T10:46:26",
            category="Camera",
            relative="Camera/2014/a.jpg",
            drive_uuid=marker.uuid,
        )
        catalog.confirm_date(sha, datetime(2011, 3, 4, 9, 15).isoformat(), confirmed_by="test")
    return db, here, marker


def test_a_bake_leaves_a_line_and_writes_no_detail(tmp_path: Path) -> None:
    """⚠ **The absent detail file IS the assertion.** `BakeOutcome` names only drives, so a detail
    file would hold `files: []` at any size - and writing one would demote whatever real record
    `last-run.json` currently holds in order to say nothing."""
    db, here, marker = _baked_library(tmp_path)
    outcome = bake_confirmed_dates(
        here,
        db,
        marker,  # type: ignore[arg-type]
        confirmation=CONFIRM_WORD,
        progress=None,
        cancel=threading.Event(),
    )

    assert outcome.baked == 1
    (line,) = _lines(db)
    assert line["kind"] == "bake"
    assert line["intended_total"] == 1
    assert line["attempted"] == 1
    assert line["stopped"] is False
    assert not record_path_for(db).is_file(), "bake must write a line and no detail"


def test_a_bake_does_not_demote_the_record_already_there(tmp_path: Path) -> None:
    """The half that is easy to get wrong: `detail=False` must skip the **supersede** too.

    A bake that rotated `last-run.json` into `runs/` and wrote no replacement would leave the name
    meaning nothing, which is worse than the staleness it was trying to avoid.
    """
    db, here, marker = _baked_library(tmp_path)
    record_path_for(db).parent.mkdir(parents=True, exist_ok=True)
    record_path_for(db).write_text('{"format": 3, "run": {"kind": "organize"}}', encoding="utf-8")

    bake_confirmed_dates(
        here,
        db,
        marker,  # type: ignore[arg-type]
        confirmation=CONFIRM_WORD,
        progress=None,
        cancel=threading.Event(),
    )

    kept = json.loads(record_path_for(db).read_text(encoding="utf-8"))
    assert kept["run"]["kind"] == "organize", "the bake demoted a real record to write nothing"


# --- the rule that outranks both -----------------------------------------------------------


@pytest.mark.parametrize("surface", ["migrate", "bake"])
def test_the_records_own_failure_never_fails_the_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, surface: str
) -> None:
    """⚠ **`IMPLEMENTATION_STANDARDS.md`'s record rule, proved rather than read.**

    A run that moved 33,000 files must not end in a traceback about its own paperwork.
    `record_organize` returns its errors instead of raising, but the payload is built at the call
    site, so the rule is only true if the whole write is guarded - which is what this forces.
    """

    def _explode(*_args: object, **_kwargs: object) -> str | None:
        message = "the runs directory went away mid-write"
        raise OSError(message)

    monkeypatch.setattr(f"truestill_core.{surface}.record_organize", _explode)

    if surface == "migrate":
        db, root = tmp_path / "c.sqlite", tmp_path / "drive"
        with Catalog(db) as catalog:
            _seed(catalog, root, 3)
            outcome = run_migration(catalog, LocalDestination(root), "D1", _scheme(), apply=True)
        assert outcome.migrated == 3, "the migration was failed by its own record"
    else:
        db, here, marker = _baked_library(tmp_path)
        baked = bake_confirmed_dates(
            here,
            db,
            marker,  # type: ignore[arg-type]
            confirmation=CONFIRM_WORD,
            progress=None,
            cancel=threading.Event(),
        )
        assert baked.baked == 1, "the bake was failed by its own record"
