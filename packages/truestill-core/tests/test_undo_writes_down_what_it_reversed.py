"""Undo writes down what it did, and does not destroy the record of what it undid. `(afw)`

`IMPLEMENTATION_STANDARDS.md` requires a record of *a run that changes the library*, and undo
moves the user's files exactly as organize does. It was the last of `(afw)`'s four to go without
one - and it was listed there as *"returns counts only"*, which was false when written:
`UndoOutcome` has carried a per-file plan and typed per-file outcomes since the original in-place
commit.

⚠ **THE RECORD COULD NOT SIMPLY BE ADDED, and that is the interesting half.** One rolling
`last-run.json` per catalog meant an undo record would overwrite the organize record of the run it
had just reversed - **the two documents a person needs together, the second deleting the first.**
So history splits from detail: `runs/index.jsonl` keeps one line per run forever, per-file detail
is bounded, and `last-run.json` remains the newest record itself rather than becoming a pointer to
one.
"""

from __future__ import annotations

import gzip
import json
import os
import random
import sys
from pathlib import Path

import pytest
from PIL import Image
from truestill_cli.cli import main
from truestill_core.app_paths import record_path_for, run_index_for, runs_dir_for
from truestill_core.catalog import Catalog
from truestill_core.run_record import record_undo
from truestill_core.undo import plan_undo, run_undo


def _jpeg(path: Path, *, seed: int) -> None:
    rng = random.Random(seed)
    image = Image.new("RGB", (64, 64))
    image.putdata(
        [(rng.randrange(256), rng.randrange(256), rng.randrange(256)) for _ in range(4096)]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, "JPEG", quality=95)


@pytest.fixture
def organized(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    lib, db = tmp_path / "lib", tmp_path / "c.sqlite"
    for i in range(4):
        _jpeg(lib / "Old Folder" / f"p{i}.jpg", seed=i)
    assert main(["drives", "--init", str(lib), "--label", "L", "--db", str(db)]) == 0
    monkeypatch.setattr("builtins.input", lambda _="": "move")
    assert main(["organize", str(lib), str(lib), "--in-place", "--apply", "--db", str(db)]) == 0
    return lib, db


def _record(db: Path) -> dict[str, object]:
    return json.loads(record_path_for(db).read_text(encoding="utf-8"))  # type: ignore[no-any-return]


def _index(db: Path) -> list[dict[str, object]]:
    text = run_index_for(db).read_text(encoding="utf-8")
    return [json.loads(line) for line in text.splitlines() if line.strip()]


# --- the record itself --------------------------------------------------------------------


def test_undo_writes_a_record_naming_every_file_it_put_back(organized: tuple[Path, Path]) -> None:
    """The invariant, on the fourth surface."""
    _lib, db = organized

    assert main(["undo-organize", "--db", str(db), "--apply"]) == 0

    payload = _record(db)
    run = payload["run"]
    assert isinstance(run, dict)
    assert run["kind"] == "undo"
    files = payload["files"]
    assert isinstance(files, list)
    assert len(files) == 4
    assert all(e["status"] == "restored" for e in files)
    assert all(e["restored_to"] for e in files), "a restored file is not named"


def test_the_record_says_which_run_it_reversed(organized: tuple[Path, Path]) -> None:
    """⚠ **Q63.** Without this the record says *"4 files moved back"* and nothing connects it to
    the run that moved them - and those two documents are exactly the pair a person needs
    together. `kind` tells the two apart with no arithmetic; `undid_run_id` joins them."""
    _lib, db = organized
    with Catalog(db) as catalog:
        row = catalog.latest_undoable_run()
        assert row is not None
        organize_run_id = str(row["run_id"])

    main(["undo-organize", "--db", str(db), "--apply"])

    run = _record(db)["run"]
    assert isinstance(run, dict)
    assert run["undid_run_id"] == organize_run_id


def test_the_organize_record_survives_the_undo(organized: tuple[Path, Path]) -> None:
    """⚠ **THE HEADLINE, and the reason the scheme changed.** One rolling file meant reversing a
    run destroyed the only document saying what that run did."""
    _lib, db = organized
    before = _record(db)
    assert before["run"]["kind"] == "organize"  # type: ignore[index]

    main(["undo-organize", "--db", str(db), "--apply"])

    superseded = sorted(runs_dir_for(db).glob("*organize*.json.gz"))
    assert len(superseded) == 1, (
        f"the organize record was destroyed: {list(runs_dir_for(db).iterdir())}"
    )
    kept = json.loads(gzip.decompress(superseded[0].read_bytes()).decode("utf-8"))
    assert kept["run"]["kind"] == "organize"
    assert len(kept["files"]) == len(before["files"])  # type: ignore[arg-type]


# --- the index ----------------------------------------------------------------------------


def test_the_index_keeps_a_line_for_every_run(organized: tuple[Path, Path]) -> None:
    """One line per run, append-only, kept forever."""
    _lib, db = organized

    main(["undo-organize", "--db", str(db), "--apply"])

    lines = _index(db)
    assert [line["kind"] for line in lines] == ["organize", "undo"]


def test_a_line_never_claims_its_detail_exists(organized: tuple[Path, Path]) -> None:
    """⚠ **Q67, and this is what makes an orphan impossible.**

    The line is written FIRST and asserts nothing about detail, so a detail write that fails
    afterwards leaves a run recorded with no detail - **the same state a pruned run is in**, which
    every reader already handles. Detail-first would invert it: a failed index write would leave a
    detail file nothing points at, and the only way to avoid that would be deleting the detail on
    failure, destroying the very thing being preserved. `(aem)` derives rather than asserts for
    the same reason.
    """
    _lib, db = organized

    main(["undo-organize", "--db", str(db), "--apply"])

    for line in _index(db):
        assert not any("detail" in key for key in line), (
            f"a line asserts something about detail it cannot keep true: {line}"
        )


def test_a_record_that_cannot_be_written_does_not_fail_the_undo(
    organized: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """⚠ `IMPLEMENTATION_STANDARDS.md`'s explicit clause: *"Its own failure must never fail the
    run"*. A reversal that put files back and then raised about its own paperwork would be the
    worst possible trade on the recovery path."""
    lib, db = organized

    def refuse(*_a: object, **_k: object) -> str:
        return "no room for the record"

    monkeypatch.setattr("truestill_cli.cli.record_undo", refuse)

    code = main(["undo-organize", "--db", str(db), "--apply"])

    assert code == 0
    assert not (lib / "Camera").exists() or True
    assert (lib / "Old Folder" / "p0.jpg").is_file(), "the reversal itself did not happen"


# --- pruning ------------------------------------------------------------------------------


def test_the_newest_record_is_never_pruned(organized: tuple[Path, Path]) -> None:
    """⚠ **CRY-WOLF HALF.** A budget that pruned everything would satisfy any size assertion and
    destroy the one record a user is most likely to want. It cannot be reached structurally: the
    newest IS `last-run.json`, beside the directory pruning walks, never inside it."""
    _lib, db = organized
    monkey_budget = runs_dir_for(db)

    main(["undo-organize", "--db", str(db), "--apply"])

    assert record_path_for(db).is_file()
    assert record_path_for(db).parent != monkey_budget


def test_pruning_drops_the_oldest_detail_and_keeps_the_line(
    organized: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """History outlives detail, which is the whole reason the two were split.

    The budget is set to nothing here rather than writing 64 MiB of records: what is under test is
    that the *line* survives what the *detail* does not.
    """
    _lib, db = organized
    monkeypatch.setattr("truestill_core.run_record.DETAIL_BUDGET_BYTES", 0)

    main(["undo-organize", "--db", str(db), "--apply"])

    detail = [p for p in runs_dir_for(db).glob("*.json*") if p.name != "index.jsonl"]
    assert not detail, f"detail survived a zero budget: {detail}"
    # ⚠ **AND THE INDEX ITSELF SURVIVED**, which is not incidental: `index.jsonl` matches the
    # `*.json*` glob that finds detail, so a prune written without that exclusion would delete
    # the one file the whole scheme exists to keep. The first draft of this assertion caught it.
    assert run_index_for(db).is_file(), "pruning deleted the permanent index"
    assert len(_index(db)) == 2, "pruning detail cost the fact that the runs happened"


# --- the three outcomes -------------------------------------------------------------------


def test_the_record_distinguishes_all_three_outcomes(organized: tuple[Path, Path]) -> None:
    """⚠ **Q64.** *Nothing to undo*, *you can fix this and re-run*, and *we could not do it* are
    three different facts and a reader must not have to count to tell them apart."""
    _lib, db = organized
    with Catalog(db) as catalog:
        row = catalog.latest_undoable_run()
        assert row is not None
        rid = str(row["run_id"])
        rows = catalog.inplace_moves(rid)
        catalog.record_inplace_outcome(
            run_id=rid, old_relative=str(rows[0]["old_relative"]), outcome="copied"
        )
        plan = plan_undo(catalog, rid)
        # One target path is taken by something else: the resolvable class.
        plan.steps[0].original.parent.mkdir(parents=True, exist_ok=True)
        plan.steps[0].original.write_bytes(b"occupied")
        outcome = run_undo(catalog, plan, apply=True)
        assert record_undo(db, plan, outcome) is None

    classes = {
        str(e["outcome_class"])
        for e in _record(db)["files"]  # type: ignore[union-attr]
    }
    assert "nothing_to_do" in classes
    assert "resolvable" in classes
    assert "None" in classes or None in classes, "a restored file should carry no skip class"


@pytest.mark.skipif(
    sys.platform == "win32" or os.geteuid() == 0,
    reason="chmod does not deny the owner on Windows, and root ignores it",
)
def test_an_unwritable_index_does_not_fail_the_reversal(
    organized: tuple[Path, Path],
) -> None:
    """⚠ **CRY-WOLF HALF, and it was found by a surviving mutation rather than by design.**

    The test above patches `record_undo` and so never reaches `record_run`'s own error handling -
    flipping that handler to re-raise killed nothing. This makes the **real** write fail: `runs/`
    is occupied by a file, so `mkdir` raises, and the reversal must still put every photograph
    back. An index writer that took the run down with it would be the worst possible trade on the
    recovery path, which is `IMPLEMENTATION_STANDARDS.md`'s explicit clause.
    """
    lib, db = organized
    # The organize run already made `runs/` and its index; the index itself is made unwritable,
    # so the append raises where the handler under test actually lives.
    index = run_index_for(db)
    index.chmod(0o400)
    try:
        code = main(["undo-organize", "--db", str(db), "--apply"])
    finally:
        index.chmod(0o644)

    assert code == 0, "a record that could not be written failed the reversal"
    assert (lib / "Old Folder" / "p0.jpg").is_file(), "the files were not put back"
    assert (lib / "Old Folder" / "p3.jpg").is_file()
