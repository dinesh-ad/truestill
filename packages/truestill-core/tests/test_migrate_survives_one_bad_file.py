"""A migration counts and names a bad file, and stops only for a condition that outlives it.

`(agi)`'s ruled policy arriving on the **fifth** surface and the fourth to get it: *"one bad file
never aborts a batch"* (`ENGINEERING_STANDARD.md` §4 Errors), and a condition that will hit the
next file too must stop the run. `organizer.execute`, `service/backup.py` and `undo.run_undo` all
call `persists_for_the_run`; `migrate.run_migration` did not.

⚠ **THE ROOT CAUSE WAS A DISCARDED `__cause__`, NOT A MISSING TRY/EXCEPT.** `_matches` caught the
`DestinationError` that `LocalDestination.checksum` raises **with its `OSError` chained**
(`destinations/local.py:258`, `from exc`) and returned a bare `False`. So by the time
`_apply_move` raised *"verification failed after relocating to ..."* there was nothing left to
classify, and `drive_unwritable.persists_for_the_run` - which walks `__cause__` looking for an
`OSError` - answered `False` for a **failing drive**. Adding a `try/except` around `_apply_move`
without repairing that chain would have produced a handler that classified every I/O failure as a
one-file problem, which is the `(agi)` defect wearing a fix.

⚠ **AND ONE FAILURE GENUINELY HAS NO CAUSE TO CHAIN**: the destination is readable and simply
returns bytes that are not what was written. `VerificationFailedError` names it, so it is classified by
**type** rather than by matching the message text - `IMPLEMENTATION_STANDARDS.md` §9's rule about
matching on an exception name.
"""

from __future__ import annotations

import errno
from pathlib import Path, PurePosixPath

import pytest
from truestill_core.catalog import Catalog
from truestill_core.destinations.base import DestinationError
from truestill_core.destinations.local import LocalDestination
from truestill_core.drive_unwritable import persists_for_the_run
from truestill_core.hashing import sha256_file
from truestill_core.layout import LayoutScheme, LayoutTemplate
from truestill_core.migrate import MigrationStopKind, run_migration

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
    """A drive whose reads fail. The `OSError` is chained exactly as the real backend chains it."""

    def __init__(self, root: Path, *, code: int, only: str | None = None) -> None:
        super().__init__(root)
        self._code = code
        self._only = only

    def checksum(self, relative_path: str) -> str:
        hit = self._only is None or PurePosixPath(relative_path).name == self._only
        if hit:
            reason = OSError(self._code, "injected")
            message = f"cannot checksum {relative_path!r}: {reason}"
            raise DestinationError(message) from reason
        return super().checksum(relative_path)


class _ReturnsWrongBytes(LocalDestination):
    """A drive that reads fine and stores something other than what it was given."""

    def checksum(self, _relative_path: str) -> str:
        return "0" * 64


# --- the property -------------------------------------------------------------------------


def test_a_failing_drive_stops_the_run_instead_of_failing_every_file(tmp_path: Path) -> None:
    """⚠ **FAILS BEFORE THE FIX** - the bare `DestinationError` escaped `run_migration`."""
    root = tmp_path / "drive"
    with Catalog(tmp_path / "c.sqlite") as catalog:
        _seed(catalog, root, 4)
        outcome = run_migration(
            catalog, _RaisesOnChecksum(root, code=errno.EIO), "D1", _scheme(), apply=True
        )

    assert outcome.stopped is not None, "a failing drive must stop the run, not raise past it"
    assert outcome.stopped.kind is MigrationStopKind.COULD_NOT_CONTINUE
    assert outcome.migrated == 0
    assert len(outcome.refused) == 1, "the file it died on is named once, not four times"
    assert outcome.stopped.never_attempted == 3


def test_one_bad_file_is_counted_and_named_and_the_rest_still_move(tmp_path: Path) -> None:
    """§4 Errors: one bad file never aborts a batch. `ENOENT` is one file somebody moved."""
    root = tmp_path / "drive"
    with Catalog(tmp_path / "c.sqlite") as catalog:
        _seed(catalog, root, 4)
        outcome = run_migration(
            catalog,
            _RaisesOnChecksum(root, code=errno.ENOENT, only="p1.jpg"),
            "D1",
            _scheme(),
            apply=True,
        )

    assert outcome.stopped is None, "a single vanished file is not a reason to stop"
    assert outcome.migrated == 3
    assert [name for name, _reason in outcome.refused] == ["Camera/2023/p1.jpg"]
    assert outcome.refused[0][1], "a refusal without a reason is a silent skip"


def test_a_destination_that_stores_wrong_bytes_stops_the_run(tmp_path: Path) -> None:
    """The failure with **no cause to chain**, and the reason `VerificationFailedError` has a name.

    Nothing raised: the drive read back cleanly and returned a hash that is not what was written.
    That is a statement about the destination, not about this file - every remaining file would
    be written to the same place - so it is persistent by classification rather than by counting
    strikes. See the module docstring for why a threshold was considered and refused.
    """
    root = tmp_path / "drive"
    with Catalog(tmp_path / "c.sqlite") as catalog:
        _seed(catalog, root, 4)
        outcome = run_migration(catalog, _ReturnsWrongBytes(root), "D1", _scheme(), apply=True)

    assert outcome.stopped is not None
    assert outcome.stopped.kind is MigrationStopKind.COULD_NOT_CONTINUE
    assert outcome.migrated == 0
    assert len(outcome.refused) == 1, "it stops on the first one rather than proving it four times"


def test_the_cause_survives_matches_so_a_failing_drive_can_be_classified(tmp_path: Path) -> None:
    """The root cause, asserted directly rather than only through its consequence.

    `_matches` returned `False` for *"could not be read"* and for *"does not match"* alike, and
    `persists_for_the_run` walks `__cause__`. With the chain broken it answered `False` for
    `EIO`; the run then continued into a drive that had already given up.
    """
    root = tmp_path / "drive"
    root.mkdir()
    (root / "a.jpg").write_bytes(b"x")
    destination = _RaisesOnChecksum(root, code=errno.EIO)

    with pytest.raises(DestinationError) as caught:
        destination.checksum("a.jpg")

    assert persists_for_the_run(caught.value), (
        "the chained OSError must survive to be classified - a bare False here is the defect"
    )


# --- cry-wolf -----------------------------------------------------------------------------


def test_a_clean_migration_moves_everything_and_stops_nothing(tmp_path: Path) -> None:
    """The half that goes red if the handler fires on a healthy run."""
    root = tmp_path / "drive"
    with Catalog(tmp_path / "c.sqlite") as catalog:
        _seed(catalog, root, 4)
        outcome = run_migration(catalog, LocalDestination(root), "D1", _scheme(), apply=True)

    assert outcome.migrated == 4
    assert outcome.stopped is None
    assert outcome.refused == []
    assert catalog_is_drained(tmp_path / "c.sqlite")


def catalog_is_drained(db: Path) -> bool:
    with Catalog(db) as catalog:
        return catalog.pending_migration("D1") == []


def test_a_preview_neither_stops_nor_refuses(tmp_path: Path) -> None:
    """A preview never enters the loop, so it can report neither - and must not invent them."""
    root = tmp_path / "drive"
    with Catalog(tmp_path / "c.sqlite") as catalog:
        _seed(catalog, root, 4)
        outcome = run_migration(catalog, _ReturnsWrongBytes(root), "D1", _scheme(), apply=False)

    assert outcome.applied is False
    assert outcome.stopped is None
    assert outcome.refused == []
