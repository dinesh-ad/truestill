"""The in-place journal is written BEFORE the rename, not after. `(agk)`

A rename cannot be verified after the fact the way a copy can: there is no second copy to
re-hash, because the rename **is** the operation. So the only thing that can make it survivable
is a record written before it. `organizer._move_source` one branch away has always obeyed this -
it verifies the destination copy before unlinking the source - and this path did not.

**Measured before the fix, on real photographs from `~/TruestillLibrary/Input`**: eight
`SIGKILL`s of an `--in-place` run left a file moved with no undo row in **2 of 8**, and
`undo-organize` then printed *"Restored 27 file(s)"* and left the photograph displaced. After it,
the same eight kills score **zero**. That harness is the acceptance test; this file is the part
of it that runs in the suite.

⚠ **WHAT `outcome IS NULL` MEANS, because everything here turns on it.** It means **unknown** -
the disk has not been asked - and never "did not happen". A crash between the rename and the
write-back leaves exactly that over a file that really did move, so a reader folding it into
"nothing happened" would put the defect back one layer up. Only `undo.plan_undo` settles it, by
looking at the disk.
"""

from __future__ import annotations

import errno
import os
import random
import sqlite3
import sys
from pathlib import Path

import pytest
from PIL import Image
from truestill_cli.cli import main
from truestill_core.catalog import Catalog
from truestill_core.undo import UndoSkip, plan_undo, run_undo


def _jpeg(path: Path, *, seed: int) -> None:
    rng = random.Random(seed)
    image = Image.new("RGB", (64, 64))
    image.putdata(
        [(rng.randrange(256), rng.randrange(256), rng.randrange(256)) for _ in range(4096)]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, "JPEG", quality=95)


@pytest.fixture
def library(tmp_path: Path) -> tuple[Path, Path]:
    """A drive with four photos in a folder of their own, ready for an in-place run."""
    lib, db = tmp_path / "lib", tmp_path / "c.sqlite"
    for i in range(4):
        _jpeg(lib / "Old Folder" / f"p{i}.jpg", seed=i)
    assert main(["drives", "--init", str(lib), "--label", "L", "--db", str(db)]) == 0
    return lib, db


def _organize(lib: Path, db: Path, monkeypatch: pytest.MonkeyPatch) -> int:
    """An in-place run, confirmed. The prompt is the product refusing to move a library on a
    typo, so it is answered rather than bypassed."""
    monkeypatch.setattr("builtins.input", lambda _="": "move")
    return main(["organize", str(lib), str(lib), "--in-place", "--apply", "--db", str(db)])


def _rows(db: Path) -> list[sqlite3.Row]:
    with Catalog(db) as catalog:
        run = catalog.latest_undoable_run()
        assert run is not None, "the run was not journalled at all"
        return catalog.inplace_moves(str(run["run_id"]))


def _moved(lib: Path) -> dict[int, Path]:
    """Inode -> path for the photographs only.

    ⚠ **Dotfiles are excluded deliberately.** `.truestill-decisions.json` is rewritten by every
    run, so it gets a new inode each time and would read as "a file moved" - which is what the
    first draft of the replay test below actually asserted, and it was wrong about the product.
    """
    return {
        p.stat().st_ino: p for p in lib.rglob("*") if p.is_file() and not p.name.startswith(".")
    }


# --- the ordering itself -----------------------------------------------------------------------


def test_the_row_exists_before_the_rename_does(
    library: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """⚠ **THE HEADLINE, and it fails against the old ordering.**

    The outcome write-back is suppressed, which is exactly what a crash in that window leaves:
    the file has moved and no outcome was ever recorded. Under the old code there was no row at
    all at this point, because the only journal write happened after the rename **and** after the
    catalog row. Here the row is present and says `NULL` - unknown, not "nothing happened".
    """
    lib, db = library
    monkeypatch.setattr(Catalog, "record_inplace_outcome", lambda *_a, **_k: None)

    _organize(lib, db, monkeypatch)

    rows = _rows(db)
    assert len(rows) == 4, f"the run did not record what it set out to do: {rows}"
    assert all(r["outcome"] is None for r in rows), "the suppression did not take"
    # ...and the files really did move, which is what makes the missing outcome dangerous.
    assert not (lib / "Old Folder" / "p0.jpg").exists()


def test_a_journal_that_cannot_be_written_moves_nothing(
    library: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """⚠ **THE POINT OF DOING IT IN THIS ORDER.** If the row cannot be written, no rename is
    attempted, so there is nothing to undo - which is why guarding the *old* call site was not
    the fix: it would have made the loss loud rather than impossible."""
    lib, db = library

    def refuse(*_args: object, **_kwargs: object) -> None:
        unwritable = "disk I/O error"
        raise sqlite3.OperationalError(unwritable)

    monkeypatch.setattr(Catalog, "record_inplace_intent", refuse)

    _organize(lib, db, monkeypatch)

    assert (lib / "Old Folder" / "p0.jpg").is_file(), (
        "a file moved even though its journal row could not be written"
    )


def test_a_completed_run_records_the_outcome(
    library: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """⚠ **CRY-WOLF HALF.** An implementation that never wrote the outcome back would pass every
    row above and leave every healthy run reading as unreconciled forever."""
    lib, db = library

    _organize(lib, db, monkeypatch)

    rows = _rows(db)
    assert len(rows) == 4
    assert [r["outcome"] for r in rows] == ["renamed"] * 4
    assert all(r["size"] for r in rows), "the free half of identity was not recorded"


# --- undo reconciles against the disk, never the row -------------------------------------------


def test_a_file_that_moved_with_no_outcome_is_still_restored(
    library: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """⚠ **CRY-WOLF HALF, and the one the maintainer named.** An `outcome` of `NULL` read as
    *"the rename did not happen"* would skip exactly the files the crash endangered - the whole
    defect, reintroduced one layer up and much harder to see."""
    lib, db = library
    before = {p.stat().st_ino: p for p in (lib / "Old Folder").iterdir()}
    monkeypatch.setattr(Catalog, "record_inplace_outcome", lambda *_a, **_k: None)
    _organize(lib, db, monkeypatch)
    monkeypatch.undo()

    with Catalog(db) as catalog:
        run = catalog.latest_undoable_run()
        assert run is not None
        plan = plan_undo(catalog, str(run["run_id"]))
        assert len(plan.steps) == 4, f"unknown was read as nothing-to-do: {plan.skipped}"
        outcome = run_undo(catalog, plan, apply=True)

    assert outcome.restored == 4
    assert {p.stat().st_ino: p for p in (lib / "Old Folder").iterdir()} == before


def test_a_row_whose_rename_never_happened_is_not_a_failure(
    library: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """An intent with no rename behind it reads as `NEVER_MOVED`, and that is not a refusal.

    ⚠ **It was `MOVED_AWAY` in the first draft**, which says *"no longer at the path this run
    left it"* about a file the run never moved - false, and it spent the exit code on it. The
    disk distinguishes them: nothing at the new path **and** the file still at the old one.
    """
    lib, db = library
    _organize(lib, db, monkeypatch)

    # A fifth photo the run never reached, with an intent recorded for it: exactly the state a
    # crash between the journal write and the rename leaves. Built through the product's own API
    # rather than by hand-written SQL, so it cannot describe a row the product could not produce.
    stranded = lib / "Old Folder" / "p4.jpg"
    _jpeg(stranded, seed=4)
    with Catalog(db) as catalog:
        run = catalog.latest_undoable_run()
        assert run is not None
        rid = str(run["run_id"])
        catalog.record_inplace_intent(
            run_id=rid,
            sha256="e" * 64,
            old_relative="Old Folder/p4.jpg",
            new_relative="2026/2026-01/p4.jpg",
            size=stranded.stat().st_size,
        )
        plan = plan_undo(catalog, rid)

    never = [s for s in plan.skipped if s.reason is UndoSkip.NEVER_MOVED]
    assert len(never) == 1, f"a file that was never moved was misreported: {plan.skipped}"
    assert "still where it started" in never[0].detail
    assert len(plan.steps) == 4, "the four real moves stopped being restorable"


def test_a_row_that_records_a_copy_is_skipped(
    library: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A cross-device fallback leaves an intent that became a copy. `organizer._move_source`
    verified the destination before removing the source, so there is no rename to reverse."""
    lib, db = library
    _organize(lib, db, monkeypatch)
    with Catalog(db) as catalog:
        run = catalog.latest_undoable_run()
        assert run is not None
        rid = str(run["run_id"])
        for row in catalog.inplace_moves(rid):
            catalog.record_inplace_outcome(
                run_id=rid, old_relative=str(row["old_relative"]), outcome="copied"
            )
        plan = plan_undo(catalog, rid)

    assert not plan.steps
    assert [s.reason for s in plan.skipped] == [UndoSkip.WAS_A_COPY] * 4


# --- Q59: identity, not position ---------------------------------------------------------------


def test_undo_refuses_to_move_a_different_file_that_took_the_path(
    library: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """⚠ **Q59 - the sequence that makes Ruling 2 necessary, built rather than described.**

    Once a row can describe a rename that did not happen, this is reachable:

    1. an intent row is written for ``new_relative = X``;
    2. that rename does not happen;
    3. a **different** file legitimately takes ``X`` later, because `_free_relative` finds it free;
    4. the first file's original path is emptied by something else, so `ORIGIN_OCCUPIED` no longer
       fires;
    5. undo, checking only position, moves the **wrong file** to the first file's old path.

    Position is not identity, and `organizer._move_source` has always re-hashed before unlinking
    a source. Undo checking less would be a second divergence on the same user action.
    """
    lib, db = library
    _organize(lib, db, monkeypatch)

    with Catalog(db) as catalog:
        run = catalog.latest_undoable_run()
        assert run is not None
        rid = str(run["run_id"])
        rows = catalog.inplace_moves(rid)

    victim = rows[0]
    placed = lib / str(victim["new_relative"])
    original = lib / str(victim["old_relative"])
    assert placed.is_file(), "fixture check: the run placed it"
    assert not original.exists(), "fixture check: it left the old path"

    # Step 3: a different file is now at that path. Step 4: the original stays empty.
    placed.unlink()
    _jpeg(placed, seed=999)

    with Catalog(db) as catalog:
        plan = plan_undo(catalog, rid)

    refused = [s for s in plan.skipped if s.step.current == placed]
    assert len(refused) == 1, f"undo did not notice the substitution: {plan.skipped}"
    assert refused[0].reason is UndoSkip.NOT_THE_SAME_FILE
    assert not original.exists(), "undo moved a file it had not identified"


def test_the_size_pre_filter_rejects_without_reading(
    library: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Size can **reject** for free and can never confirm. A different length is a different
    file, and saying so costs one `stat` rather than a full read."""
    lib, db = library
    _organize(lib, db, monkeypatch)
    with Catalog(db) as catalog:
        run = catalog.latest_undoable_run()
        assert run is not None
        rid = str(run["run_id"])
        rows = catalog.inplace_moves(rid)

    placed = lib / str(rows[0]["new_relative"])
    placed.write_bytes(b"a different length entirely")

    with Catalog(db) as catalog:
        plan = plan_undo(catalog, rid)

    refused = [s for s in plan.skipped if s.step.current == placed]
    assert refused[0].reason is UndoSkip.NOT_THE_SAME_FILE
    assert "bytes, not" in refused[0].detail, "the free rejection did not name the sizes"


def test_identity_checking_does_not_refuse_an_ordinary_restore(
    library: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """⚠ **CRY-WOLF HALF, and the maintainer named this one too.** An undo that hashed everything
    and then refused - a comparison against the wrong digest, a check that fails closed on a
    match - would satisfy every row above and quietly retire the feature that is in-place
    organize's entire safety story."""
    lib, db = library
    before = {p.stat().st_ino: p for p in (lib / "Old Folder").iterdir()}
    _organize(lib, db, monkeypatch)

    with Catalog(db) as catalog:
        run = catalog.latest_undoable_run()
        assert run is not None
        plan = plan_undo(catalog, str(run["run_id"]))
        assert len(plan.steps) == 4, f"a legitimate restore was refused: {plan.skipped}"
        outcome = run_undo(catalog, plan, apply=True)

    assert outcome.restored == 4
    assert not outcome.skipped
    assert {p.stat().st_ino: p for p in (lib / "Old Folder").iterdir()} == before


# --- Q58: replay ------------------------------------------------------------------------------


def test_a_second_run_over_the_same_folder_does_not_move_anything_again(
    library: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """⚠ **Q58 - idempotence is against the DISK, not the row**, and that is what makes it safe.

    `_execute_one_write`'s `_already_at_target` check runs **before** the intent is recorded, so
    a replay of an in-place run over an organized folder writes no new intent and moves nothing.
    A guard keyed on the journal instead would be wrong in both directions: a row exists for
    renames that did not happen, and no row exists for a folder organized by an earlier install.
    """
    lib, db = library
    _organize(lib, db, monkeypatch)
    after_first = _moved(lib)
    with Catalog(db) as catalog:
        first = sum(int(r["intended"]) for r in catalog.inplace_runs())

    _organize(lib, db, monkeypatch)

    assert _moved(lib) == after_first, "a replay moved files that were already in place"
    with Catalog(db) as catalog:
        assert sum(int(r["intended"]) for r in catalog.inplace_runs()) == first, (
            "the replay journalled intents for files that were already where they belong"
        )


@pytest.mark.skipif(
    sys.platform == "win32" or os.geteuid() == 0,
    reason="chmod 000 does not deny the owner on Windows, and root ignores it",
)
def test_a_file_that_cannot_be_read_is_refused_rather_than_moved(
    library: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """⚠ **Unreadable is a REFUSAL, not a pass.** Failing open here would move a file whose
    identity could not be established - the one outcome undo must never produce, and the
    direction every other guard in this file leans away from."""
    lib, db = library
    _organize(lib, db, monkeypatch)
    with Catalog(db) as catalog:
        run = catalog.latest_undoable_run()
        assert run is not None
        rid = str(run["run_id"])
        rows = catalog.inplace_moves(rid)

    placed = lib / str(rows[0]["new_relative"])
    original = lib / str(rows[0]["old_relative"])
    placed.chmod(0o000)
    try:
        with Catalog(db) as catalog:
            plan = plan_undo(catalog, rid)
            run_undo(catalog, plan, apply=True)
        refused = [s for s in plan.skipped if s.step.current == placed]
        assert len(refused) == 1, f"an unreadable file was not refused: {plan.skipped}"
        assert refused[0].reason is UndoSkip.UNREADABLE
        assert not original.exists(), "undo moved a file it could not identify"
    finally:
        placed.chmod(0o644)


def test_a_file_that_vanishes_mid_check_is_refused(
    library: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The TOCTOU half, and it needed its own test because the other one cannot reach it.

    ⚠ **`chmod 000` does not stop `stat`** - the parent directory grants that - so the unreadable
    test above fails at the *hash* and leaves the `stat` guard unproven. Found by a surviving
    mutation, not by design: flipping that guard to fail open killed nothing.

    The branch is reachable only as a race - `_why_not` has already called `is_file()`, so the
    file existed a moment ago and something removed it in between. `Path.stat` is patched for
    exactly that path rather than a file being deleted mid-call, because the race cannot be
    scheduled reliably and the property under test is the handler, not the timing.
    """
    lib, db = library
    _organize(lib, db, monkeypatch)
    with Catalog(db) as catalog:
        run = catalog.latest_undoable_run()
        assert run is not None
        rid = str(run["run_id"])
        rows = catalog.inplace_moves(rid)

    placed = lib / str(rows[0]["new_relative"])
    original = lib / str(rows[0]["old_relative"])
    real_stat = Path.stat

    def vanishing(self: Path, *args: object, **kwargs: object) -> os.stat_result:
        if self == placed:
            raise OSError(errno.ENOENT, "No such file or directory")
        return real_stat(self, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(Path, "stat", vanishing)
    with Catalog(db) as catalog:
        plan = plan_undo(catalog, rid)
    monkeypatch.undo()

    refused = [s for s in plan.skipped if s.step.current == placed]
    assert len(refused) == 1, f"a file that vanished mid-check was not refused: {plan.skipped}"
    assert refused[0].reason is UndoSkip.UNREADABLE
    assert not original.exists()
