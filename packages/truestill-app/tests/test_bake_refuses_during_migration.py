"""A bake refuses while a migration is unfinished on that drive (date-provenance step 4, cond. 3).

**The window, traced.** `run_migration` snapshots each copy's `copy_sha256` at *plan* time into
`migration_journal` (`Catalog.record_migration_moves`), and `_apply_move` verifies the relocated
file against that **journalled** value, never a fresh read. A bake rewrites the file's bytes and
updates `file_copies.copy_sha256` in the same transaction (O1), which makes the snapshot stale.

**The concrete failure, not the category.** `_apply_move` finds the new path absent, calls
`destination.relocate(old, new)` - which is `shutil.copy2`, not a rename - then re-checks the
copy against the stale hash, mismatches, and raises `DestinationError("verification failed after
relocating to ...")`. End state: the file is still at ``old`` (no data loss), an orphan copy sits
at ``new``, `file_copies.relative` still says ``old``, and the journal row is still pending. It
does **not** self-heal: a resume repeats the identical comparison and raises again, forever. Undo
cannot clear it either - `reversible_migration` walks *completed* rows. So the user sees a
permanent stall, a duplicate on the drive, and the words "verification failed" about a file
truestill itself rewrote.

**Why a refusal rather than a proof.** The app's per-drive job lock already covers app-vs-app
fully - every job route goes through `_start_drive_job`, which keys on `uuid:<marker uuid>`. It
is process-local by design (`BACKLOG.md` **(vv)**), so a CLI `migrate-layout` running beside an
app bake is not serialized at all, and there is nothing to prove closed for that pair.

**How the bake knows across processes.** The journal is in the shared catalog:
`Catalog.pending_migration(drive_uuid)` returns rows with ``completed_at IS NULL``, which every
process can read. That is durable shared state, not process memory. It is also right for the
*interrupted* case - pending rows outlive a crash, and a later resume still compares against the
stale snapshot - so one predicate covers both, and the message offers both ways out.

**It narrows, it does not close.** See :func:`test_the_toctou_gap_is_narrowed_not_closed`.
"""

from __future__ import annotations

import ast
from pathlib import Path

from truestill_app.service import bake
from truestill_app.service.bake import bake_preconditions, migration_unfinished_message
from truestill_core.catalog import Catalog
from truestill_core.drive import create_marker

_UUID_LABEL = "Memory Drive"


def _drive(tmp_path: Path) -> tuple[Path, Path, str]:
    """A registered drive with one recorded copy. Returns (db, root, drive_uuid)."""
    db, root = tmp_path / "c.sqlite", tmp_path / "drive"
    root.mkdir()
    marker = create_marker(root, label=_UUID_LABEL)
    with Catalog(db) as catalog:
        catalog.upsert_drive(uuid=marker.uuid, label=marker.label)
        catalog.record_uploaded(
            source_path="/src/a.jpg",
            original_name="a.jpg",
            sha256="sha-a",
            copy_sha256="sha-a",
            perceptual=None,
            size=10,
            captured_at="2014-08-16T10:46:26",
            category="Camera",
            relative="Camera/2014/a.jpg",
            drive_uuid=marker.uuid,
        )
    return db, root, marker.uuid


def _journal_a_pending_move(db: Path, drive_uuid: str) -> None:
    """Exactly what an in-flight (or interrupted) migration leaves behind."""
    with Catalog(db) as catalog:
        catalog.start_migration_run("run-1", drive_uuid)
        catalog.record_migration_moves(
            [("sha-a", drive_uuid, "Camera/2014/a.jpg", "2014/2014-08/a.jpg", "sha-a", "run-1")]
        )


def test_a_bake_refuses_while_a_migration_is_unfinished(tmp_path: Path) -> None:
    """The refusal itself, on the state that makes the journal snapshot stale."""
    db, root, drive_uuid = _drive(tmp_path)
    _journal_a_pending_move(db, drive_uuid)

    refusal = bake_preconditions(root, db)

    assert refusal is not None, "a bake started while a migration was unfinished"
    assert refusal["ok"] is False


def test_a_bake_proceeds_when_no_migration_is_unfinished(tmp_path: Path) -> None:
    """Cry-wolf half. A guard that refuses a clean drive is one someone will switch off."""
    db, root, _uuid = _drive(tmp_path)

    assert bake_preconditions(root, db) is None


def test_a_completed_migration_does_not_block_a_bake(tmp_path: Path) -> None:
    """Cry-wolf half, the one that matters: completed rows *stay* in the journal by design.

    `complete_migration_move` marks rather than deletes - the row is what undo reverses from. A
    guard keying on row *presence* would refuse every bake on every drive that had ever been
    migrated, which is most of them, forever.
    """
    db, root, drive_uuid = _drive(tmp_path)
    _journal_a_pending_move(db, drive_uuid)
    with Catalog(db) as catalog:
        catalog.complete_migration_move("sha-a", drive_uuid)
        catalog.finish_migration_run("run-1")

    assert bake_preconditions(root, db) is None


def test_another_drives_migration_does_not_block_this_one(tmp_path: Path) -> None:
    """Cry-wolf half: the journal is per drive, and so is the refusal."""
    db, root, _uuid = _drive(tmp_path)
    with Catalog(db) as catalog:
        catalog.upsert_drive(uuid="OTHER-DRIVE", label="Elsewhere")
        catalog.start_migration_run("run-2", "OTHER-DRIVE")
        catalog.record_migration_moves([("sha-z", "OTHER-DRIVE", "a", "b", "sha-z", "run-2")])

    assert bake_preconditions(root, db) is None


def test_the_refusal_names_the_drive_and_both_ways_out() -> None:
    """§9: a refusal states what is wrong and what to do, not just that it refused."""
    message = migration_unfinished_message(_UUID_LABEL)

    assert _UUID_LABEL in message, "the user has more than one drive"
    lowered = message.lower()
    assert "migration" in lowered
    assert "unfinished" in lowered
    assert "finish" in lowered, "the first way out is not named"
    assert "undo" in lowered, "the second way out is not named"


def test_the_toctou_gap_is_narrowed_not_closed() -> None:
    """The limit, asserted rather than left in prose so deleting it breaks a test.

    Checking before each file shrinks the exposure from the length of a run to the gap between
    one file's check and its write. It is a check, not a mutex: closing it needs an on-disk lock
    across processes, which is **(vv)**'s design and is deliberately not smuggled in here.
    """
    assert bake.CHECKS_PER_FILE is True, (
        "the guard must re-check before every file, or the window is the whole run"
    )
    assert "does not close" in bake.__doc__.lower(), (
        "the module must state that this narrows rather than closes the race"
    )


def test_every_drive_touching_route_starts_through_the_locked_helper() -> None:
    """BINDING: a bake must start via ``_start_drive_job``, or it opts out of existing coverage.

    The app-vs-app half of this problem is *already solved* - `_start_drive_job` calls
    `jobs.start(drives=[drive_ref_for(path)])`, keyed on ``uuid:<marker uuid>``, and
    `JobManager` refuses a second job on an occupied drive. A bake wired straight to
    `jobs.start`, or to no job at all, would silently forfeit that and leave only the journal
    check standing.

    Asserted structurally rather than left as a comment: every ``jobs.start`` in the server goes
    through the one helper. If a future route calls it directly, this fails and says why.
    """
    server = (
        Path(__file__).resolve().parents[3] / "packages/truestill-app/src/truestill_app/server.py"
    )
    tree = ast.parse(server.read_text(encoding="utf-8"))

    def _own_calls(fn: ast.AST) -> list[ast.Call]:
        """Calls made by this function, not by functions nested inside it.

        `_start_drive_job` is defined *inside* `create_app`, so a plain `ast.walk` attributes
        the inner call to both and the guard reports its own helper as an offender.
        """
        found: list[ast.Call] = []
        for child in ast.iter_child_nodes(fn):
            if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            for node in ast.walk(child):
                if isinstance(node, ast.Call):
                    found.append(node)
        return found

    callers: list[str] = []
    for fn in ast.walk(tree):
        if not isinstance(fn, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        for call in _own_calls(fn):
            func = call.func
            if (
                isinstance(func, ast.Attribute)
                and func.attr == "start"
                and isinstance(func.value, ast.Name)
                and func.value.id == "jobs"
            ):
                callers.append(fn.name)
    assert callers == ["_start_drive_job"], (
        "jobs.start must be reached only through _start_drive_job, which takes the per-drive "
        f"lock; these functions call it directly: {sorted(set(callers))}"
    )
