"""Both migrate surfaces report a stop, and neither calls a stopped run a success. `(agm)` D1.

⚠ **`MigrationOutcome.stopped` WAS READ BY NOBODY.** `(agi)`'s ground watcher has set it since it
shipped; the app summary took only `migrated`/`resumed`, and the CLI printed *"Migrated N file(s).
Sources were never touched."* and returned **0**. So a migration stopped because the disk was
filling reported success on both surfaces - on the one command that rewrites every byte of the
library. `IMPLEMENTATION_STANDARDS.md` §9 never-silent, and `(agl)`'s defect one module over.

⚠ **They did not DISAGREE, and that is the uncomfortable part**: they agreed, because both ignored
the same field. The disagreement risk is created by fixing one, which is why both move together -
`(agc)`'s shape, where one fact is declared in two places.

The engine policy - one bad file never aborts a batch, a persistent condition stops - is pinned in
`packages/truestill-core/tests/test_migrate_survives_one_bad_file.py`. This file pins only what
each surface says about it.
"""

from __future__ import annotations

import errno
import json
import threading
from pathlib import Path, PurePosixPath

import pytest
from truestill_app.service.migrate import migration_apply
from truestill_cli.cli import _report_migration_shortfall
from truestill_core.catalog import Catalog
from truestill_core.destinations.base import DestinationError
from truestill_core.destinations.local import LocalDestination
from truestill_core.drive import MARKER_NAME
from truestill_core.hashing import sha256_file
from truestill_core.migrate import (
    STOP_WORDING,
    MigrationOutcome,
    MigrationPlan,
    MigrationStop,
    MigrationStopKind,
)


def _outcome(
    *, migrated: int, stopped: MigrationStop | None, refused: list[tuple[str, str]]
) -> MigrationOutcome:
    plan = MigrationPlan(drive_uuid="D1", moves=[], unchanged=0, warnings=[])
    return MigrationOutcome(
        plan=plan, resumed=0, migrated=migrated, applied=True, stopped=stopped, refused=refused
    )


def _shortfall(outcome: MigrationOutcome) -> int:
    """The reporter takes the two facts it needs, not a whole outcome. `(agx)`

    It serves **both directions of one command** now - `run_migration` returns a
    `MigrationOutcome`, `undo_migration` an `UndoOutcome`, and they share only the stop and the
    refusals. Passing an outcome would have meant a second reporter or a Protocol invented for
    two call sites; `(afe)` binds the two halves to one voice, and two reporters is how they
    drift apart.
    """
    return _report_migration_shortfall(outcome.stopped, outcome.refused)


# --- the CLI half ---------------------------------------------------------------------------


def test_a_stopped_migration_does_not_exit_zero(capsys: pytest.CaptureFixture[str]) -> None:
    """⚠ **FAILS BEFORE THE FIX** - this surface returned 0 after every run."""
    stop = MigrationStop(
        kind=MigrationStopKind.COULD_NOT_CONTINUE,
        reason="there is no space left on the drive",
        never_attempted=31_196,
    )

    code = _shortfall(_outcome(migrated=12, stopped=stop, refused=[]))
    captured = capsys.readouterr()

    assert code == 4, "a run the destination stopped takes the destination code, not success"
    assert "Stopped: there is no space left on the drive" in captured.err
    assert "31196 move(s) were not reached." in captured.err


def test_a_cancelled_migration_reads_as_a_choice(capsys: pytest.CaptureFixture[str]) -> None:
    """A cancel is the user's own act: stdout, exit 0, and it names the way forward.

    Same ruling `undo-organize` already carries - P24's rule that the exit code is spent on the
    right outcome, and a deliberate stop is not a fault to chain against.
    """
    stop = MigrationStop(
        kind=MigrationStopKind.CANCELLED, reason="you stopped it. migrate again", never_attempted=3
    )

    code = _shortfall(_outcome(migrated=1, stopped=stop, refused=[]))
    captured = capsys.readouterr()

    assert code == 0
    assert "Cancelled:" in captured.out
    assert captured.err == "", "a cancel is not something that went wrong"


def test_a_refusal_that_did_not_stop_the_run_is_named_and_costs_the_code(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The plan is unfinished even though nothing stopped: the journal keeps those moves."""
    code = _shortfall(
        _outcome(migrated=3, stopped=None, refused=[("Camera/2023/p1.jpg", "it vanished")])
    )
    captured = capsys.readouterr()

    assert code == 1
    assert "refused: Camera/2023/p1.jpg -- it vanished" in captured.err


# --- the app half ---------------------------------------------------------------------------


class _RaisesOnChecksum(LocalDestination):
    def checksum(self, relative_path: str) -> str:
        reason = OSError(errno.EIO, "injected")
        message = f"cannot checksum {relative_path!r}: {reason}"
        raise DestinationError(message) from reason


def _seed(catalog: Catalog, root: Path) -> None:
    catalog.upsert_drive(uuid="D1", label="Drive A")
    for index in range(3):
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


def test_the_app_summary_carries_the_stop_and_the_refusals(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The payload a screen reads, taken from a **real run** rather than from the type.

    ⚠ **THE FIRST DRAFT ASSERTED `"stopped" in MigrationApplySummary.__required_keys__` AND WAS
    VACUOUS.** Under `from __future__ import annotations` the annotations are strings, so
    `TypedDict` cannot see through `NotRequired[...]`: this module's `__required_keys__` lists
    **every** key, `elapsed_seconds` and `groups` included, and `__optional_keys__` is empty. The
    assertion was true of any key whatever - a guard agreeing with its subject's own declaration.
    A mutation that made `stopped` `NotRequired` survived it, which is how it was found.

    So this drives `migration_apply` and reads what actually comes back. §4's thirteenth member:
    assert the subject entered the path.
    """
    root = tmp_path / "drive"
    db = tmp_path / "c.sqlite"
    with Catalog(db) as catalog:
        _seed(catalog, root)
    (root / MARKER_NAME).write_text(
        json.dumps({"uuid": "D1", "label": "Drive A", "created": "2026-08-24T00:00:00"}),
        encoding="utf-8",
    )
    monkeypatch.setattr("truestill_app.service.migrate.LocalDestination", _RaisesOnChecksum)

    summary = migration_apply(root, db)(lambda _p: None, threading.Event())

    assert "stopped" in summary, "a stopped run must be reportable, not inferred from a shortfall"
    assert "refused" in summary
    assert summary["stopped"] is not None
    assert summary["stopped"]["kind"] == "could_not_continue"
    assert [item["relative"] for item in summary["refused"]], "the refusal is named"

    # ⚠ `(ahc)`: the WORDS travel with the payload, from the one table the CLI reads. A screen
    # that mapped the kind itself would be a second vocabulary in a second language, with
    # nothing to make the two agree - which is how this surface came to say nothing at all.
    wording = STOP_WORDING[MigrationStopKind.COULD_NOT_CONTINUE]
    assert summary["stopped"]["headline"] == wording.headline
    assert summary["stopped"]["fault"] is wording.fault is True, (
        "a run the destination stopped is a fault; a screen styles its banner from this"
    )


def test_a_clean_run_reports_neither(capsys: pytest.CaptureFixture[str]) -> None:
    """Cry-wolf: the reporter must stay silent and return 0 when nothing went wrong."""
    code = _shortfall(_outcome(migrated=4, stopped=None, refused=[]))
    captured = capsys.readouterr()

    assert code == 0
    assert captured.out == ""
    assert captured.err == ""


def test_unused_fixtures_are_wired(tmp_path: Path) -> None:
    """Fixture check: the seeding helper and the failing backend really build a migratable drive.

    §4's thirteenth member - assert the subject entered the path - applied to this file's own
    scaffolding, so a broken `_seed` cannot make a later end-to-end assertion vacuous.
    """
    root = tmp_path / "drive"
    with Catalog(tmp_path / "c.sqlite") as catalog:
        _seed(catalog, root)
        assert len(catalog.copies_on_drive("D1")) == 3

    destination = _RaisesOnChecksum(root)
    with pytest.raises(DestinationError):
        destination.checksum(PurePosixPath("Camera/2023/08/p0.jpg").as_posix())
