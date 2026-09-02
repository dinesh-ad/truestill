"""Reversing a migration reports what it did, even when it stops. `(agx)`

⚠ **THE FORWARD PATH AND ITS OWN UNDO DISAGREED, WHICH IS WORSE THAN BOTH BEING WRONG.** `(agm)`
gave `run_migration` a `MigrationStop` and a `refused` list; `undo_migration` still **raised** on a
verification failure, and `done`/`refused` are locals - so a reversal that put 900 files back and
then met one bad file reported **nothing it did**. A reader who checked the forward half would
conclude the pattern was followed. That is `(agj)`'s shape - *"a stopped organize took its own
paperwork down with it"* - on the surface `(agm)` had just corrected beside it.

**The data was never at risk, re-verified against today's code rather than inherited from the
entry** (`(agx)` was filed in P46 and migrate has changed twice since): `LocalDestination.relocate`
is `copy_leaving_nothing`, a **copy**, so at the raise the file exists at *both* paths; and every
catalog write - `relocate_copy`, `forget_migration_move`, `remove` - is strictly downstream of the
verify. The catalog therefore still names the path the file is really at, the journal row survives,
and a re-run resumes. **The loss was the report, and only the report.**

⚠ **AND THE RAISE HAD WIDENED SINCE THE ENTRY WAS FILED.** `(agm)` stopped `_matches` swallowing
`DestinationError`, so `checksum` on a failing drive now propagates out of `undo_migration` too -
a second, unclassified way to lose the report that did not exist when `(agx)` was written.

**This file also writes the happy path**, because `undo_migration`'s failure branch had **zero
coverage** (grepped: no test constructed a hash mismatch against it) and a regression test for a
path nothing else exercises is half a test.
"""

from __future__ import annotations

import errno
import json
import threading
from pathlib import Path, PurePosixPath

import pytest
from truestill_core.app_paths import record_path_for
from truestill_core.catalog import Catalog
from truestill_core.destinations.base import DestinationError
from truestill_core.destinations.local import LocalDestination
from truestill_core.hashing import sha256_file
from truestill_core.layout import LayoutScheme, LayoutTemplate
from truestill_core.migrate import (
    CANCELLED_REASON,
    MigrationStopKind,
    run_migration,
    undo_migration,
)
from truestill_core.progress import Phase, Progress, ProgressCallback

_DDL = "{category}/{yyyy}"


def _scheme() -> LayoutScheme:
    parsed = LayoutTemplate.parse(_DDL)
    return LayoutScheme.of(timeline=parsed, timeline_evented=parsed, side_bin=parsed)


def _migrated(tmp_path: Path, count: int = 4) -> tuple[Path, Path, LocalDestination]:
    """A drive whose files have been migrated, so there is something to reverse."""
    root, db = tmp_path / "drive", tmp_path / "c.sqlite"
    with Catalog(db) as catalog:
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
        outcome = run_migration(catalog, LocalDestination(root), "D1", _scheme(), apply=True)
        assert outcome.migrated == count, "fixture check: the migration must have moved everything"
    return root, db, LocalDestination(root)


class _WrongBytesOnRestore(LocalDestination):
    """A drive that stores something other than what it was handed, on the way back only."""

    def __init__(self, root: Path, *, only: str | None = None) -> None:
        super().__init__(root)
        self._only = only

    def checksum(self, relative_path: str) -> str:
        restoring = relative_path.startswith("Camera/2023/08/")
        hit = self._only is None or PurePosixPath(relative_path).name == self._only
        return "0" * 64 if restoring and hit else super().checksum(relative_path)


class _FailingReads(LocalDestination):
    """A drive whose reads raise, with the `OSError` chained as the real backend chains it."""

    def __init__(self, root: Path, *, code: int) -> None:
        super().__init__(root)
        self._code = code

    def checksum(self, relative_path: str) -> str:
        reason = OSError(self._code, "injected")
        message = f"cannot checksum {relative_path!r}: {reason}"
        raise DestinationError(message) from reason


def _cancel_on_first(cancel: threading.Event) -> ProgressCallback:
    def on_progress(progress: Progress) -> None:
        if progress.phase == Phase.RESTORING:
            cancel.set()

    return on_progress


# --- §4: the happy path, which had no test at all -------------------------------------------


def test_a_clean_reversal_puts_everything_back_and_stops_nothing(tmp_path: Path) -> None:
    """Happy path. `undo_migration`'s success is what every other assertion is measured against."""
    root, db, destination = _migrated(tmp_path)

    with Catalog(db) as catalog:
        outcome = undo_migration(catalog, destination, "D1", apply=True)

    assert outcome.reversed_files == 4
    assert outcome.refused == []
    assert outcome.stopped is None
    assert outcome.clean
    for index in range(4):
        assert (root / f"Camera/2023/08/p{index}.jpg").exists(), f"p{index} did not come home"


def test_a_preview_reverses_nothing_and_reports_what_it_would(tmp_path: Path) -> None:
    """The other half of the happy path: a preview counts without touching the drive."""
    root, db, destination = _migrated(tmp_path)

    with Catalog(db) as catalog:
        outcome = undo_migration(catalog, destination, "D1", apply=False)

    assert outcome.reversed_files == 4
    assert outcome.stopped is None
    assert (root / "Camera/2023/p0.jpg").exists(), "a preview must not move anything"
    assert not (root / "Camera/2023/08/p0.jpg").exists()


# --- the property: a stop reports what it managed --------------------------------------------


def test_a_verification_failure_returns_an_outcome_instead_of_raising(tmp_path: Path) -> None:
    """⚠ **FAILS BEFORE THE FIX** - the raise took `done` and `refused` down with it."""
    root, db, _destination = _migrated(tmp_path)
    destination = _WrongBytesOnRestore(root)

    with Catalog(db) as catalog:
        outcome = undo_migration(catalog, destination, "D1", apply=True)

    assert outcome.stopped is not None, "a reversal that stopped must say so, not raise past it"
    assert outcome.stopped.kind is MigrationStopKind.COULD_NOT_CONTINUE
    assert len(outcome.refused) == 1, "the move it died on is named once, not four times"
    assert not outcome.clean


def test_a_stop_keeps_the_count_of_what_it_already_put_back(tmp_path: Path) -> None:
    """The whole point of the entry: 900 files back and one bad file must not report nothing.

    The failure is aimed at the LAST file, so the three before it are genuinely reversed and the
    outcome has to carry them.
    """
    root, db, _destination = _migrated(tmp_path)
    destination = _WrongBytesOnRestore(root, only="p0.jpg")

    with Catalog(db) as catalog:
        outcome = undo_migration(catalog, destination, "D1", apply=True)

    assert outcome.reversed_files > 0, (
        "the reversal put files back and then reported none of them - the defect verbatim"
    )
    assert outcome.stopped is not None
    assert outcome.reversed_files + len(outcome.refused) + outcome.stopped.never_attempted == 4


def test_a_failing_drive_stops_the_run_rather_than_escaping_it(tmp_path: Path) -> None:
    """`(agm)` stopped `_matches` swallowing `DestinationError`, which widened this raise.

    `EIO` is a property of the device, so `persists_for_the_run` calls it persistent and the run
    stops - the same predicate the forward path uses, not a second errno table.
    """
    root, db, _destination = _migrated(tmp_path)

    with Catalog(db) as catalog:
        outcome = undo_migration(catalog, _FailingReads(root, code=errno.EIO), "D1", apply=True)

    assert outcome.stopped is not None
    assert outcome.stopped.kind is MigrationStopKind.COULD_NOT_CONTINUE
    assert outcome.reversed_files == 0


def test_a_cancel_says_the_user_stopped_it(tmp_path: Path) -> None:
    """The cancel already broke the loop and reported **nothing about why**.

    Reuses `MigrationStopKind.CANCELLED` and `CANCELLED_REASON` - one vocabulary across both
    halves of the command, never a second.
    """
    _root, db, destination = _migrated(tmp_path)
    cancel = threading.Event()

    with Catalog(db) as catalog:
        outcome = undo_migration(
            catalog,
            destination,
            "D1",
            apply=True,
            cancel=cancel,
            progress=_cancel_on_first(cancel),
        )

    assert outcome.stopped is not None
    assert outcome.stopped.kind is MigrationStopKind.CANCELLED
    assert outcome.stopped.reason == CANCELLED_REASON
    assert outcome.reversed_files == 1, "the move in flight completes; the next does not start"
    assert outcome.refused == [], "a cancel refuses no individual move"
    assert not outcome.clean, (
        "⚠ **THE ONLY CASE THAT DISCRIMINATES, and a mutation found it missing.** Every other "
        "stop here also carries a refusal, so `clean` reading `not self.refused` alone survived "
        "them all. A cancel is the one stop with an empty `refused` list - if `clean` ignores "
        "`stopped`, this is where it reports a half-finished reversal as a complete one."
    )


# --- §4: the data claim, and the re-run ------------------------------------------------------


def test_a_stop_leaves_the_catalog_naming_the_path_the_file_is_really_at(tmp_path: Path) -> None:
    """⚠ **Q311, re-verified against today's code rather than inherited from the entry.**

    `relocate` is `copy_leaving_nothing` - a COPY - so at the moment of the failure the file is at
    **both** paths, and every catalog write is downstream of the verify. The catalog therefore
    still names the migrated path, which is where the file demonstrably still is. Nothing is lost
    and nothing is inconsistent: the loss is the report.
    """
    root, db, _destination = _migrated(tmp_path)
    destination = _WrongBytesOnRestore(root, only="p0.jpg")

    with Catalog(db) as catalog:
        undo_migration(catalog, destination, "D1", apply=True)
        recorded = {str(row["relative"]) for row in catalog.copies_on_drive("D1")}

    for relative in recorded:
        assert (root / relative).exists(), (
            f"the catalog names {relative}, which is not on the drive - the stop left it "
            "inconsistent, and this entry stops being report-only"
        )


def test_a_second_undo_finishes_what_a_stop_left(tmp_path: Path) -> None:
    """Idempotency/re-run, which §4 requires wherever state is touched.

    The journal row survives a stop, so a re-run against a healthy drive completes the reversal -
    which is the claim that makes stopping safer than raising.
    """
    root, db, healthy = _migrated(tmp_path)
    with Catalog(db) as catalog:
        first = undo_migration(catalog, _WrongBytesOnRestore(root, only="p0.jpg"), "D1", apply=True)
    assert first.stopped is not None

    with Catalog(db) as catalog:
        second = undo_migration(catalog, healthy, "D1", apply=True)

    assert second.stopped is None, "a healthy re-run has nothing to stop for"
    for index in range(4):
        assert (root / f"Camera/2023/08/p{index}.jpg").exists(), f"p{index} never came home"


# --- cry-wolf --------------------------------------------------------------------------------


def test_a_stop_is_never_reported_as_a_clean_reversal(tmp_path: Path) -> None:
    """⚠ **The dangerous direction: a stop that reads as success.**

    `clean` decides what a caller believes. A stop that left it true would tell the CLI to exit 0
    and the screen to say the reversal finished, which is the defect wearing a fix.
    """
    root, db, _destination = _migrated(tmp_path)

    with Catalog(db) as catalog:
        outcome = undo_migration(catalog, _WrongBytesOnRestore(root), "D1", apply=True)

    assert not outcome.clean, "a stopped reversal reported itself clean"


def test_a_genuine_refusal_is_still_reported_when_nothing_stopped(tmp_path: Path) -> None:
    """The other dangerous direction: a report that swallows a real failure.

    A copy that vanished is refused and named, and the run continues - that behaviour predates
    this entry and must survive it.
    """
    root, db, destination = _migrated(tmp_path)
    (root / "Camera/2023/p1.jpg").unlink()

    with Catalog(db) as catalog:
        outcome = undo_migration(catalog, destination, "D1", apply=True)

    assert outcome.stopped is None, "one vanished copy is not a reason to stop"
    assert [name for name, _reason in outcome.refused] == ["Camera/2023/p1.jpg"]
    assert outcome.reversed_files == 3
    assert not outcome.clean


@pytest.mark.parametrize("relative", ["Camera/2023/08/p0.jpg"])
def test_paths_compare_posix_across_platforms(tmp_path: Path, relative: str) -> None:
    """Cross-platform-safe assertions (§4): journal paths are POSIX relatives, never `str(Path)`."""
    root, db, destination = _migrated(tmp_path)

    with Catalog(db) as catalog:
        undo_migration(catalog, destination, "D1", apply=True)

    assert (root / relative).exists()
    assert PurePosixPath(relative).as_posix() == relative


def test_a_reversal_writes_its_own_record(tmp_path: Path) -> None:
    """`(ahi)`'s undo half shipped 2026-08-29 and was pinned by a static census row and nothing
    else (P191). This is the behavioural half: the record exists, says what it is, and names the
    run it reversed."""
    _root, db, destination = _migrated(tmp_path)
    with Catalog(db) as catalog:
        undo_migration(catalog, destination, "D1", apply=True)
    run = json.loads(record_path_for(db).read_text(encoding="utf-8"))["run"]
    assert run["kind"] == "migrate undo"
    assert run["undid_run_id"], "the record must name the run it reversed"
