"""A cleanup writes a run record that names the folders it removed - and only those.

`cleanup.py` never touches a catalog, so the record is the only durable account, and a count
cannot answer "which folder did it remove" a week later - the maintainer's ruling, 2026-09-02
(`(ahi)`). The names come from where `rmdir` succeeded, never from `plan.removable` minus
`failures`: a folder already gone before its turn is neither removed nor failed, and that
derivation over-claims. Proved here with one such folder.
"""

from __future__ import annotations

import json
from pathlib import Path

from truestill_core.app_paths import record_path_for
from truestill_core.cleanup import plan_cleanup, record_cleanup, run_cleanup


def _tree(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "drive"
    (root / "2013" / "a").mkdir(parents=True)
    (root / "2013" / "b").mkdir(parents=True)
    return root, tmp_path / "catalog.sqlite"


def test_the_record_names_what_was_removed_and_not_what_was_already_gone(tmp_path: Path) -> None:
    root, db = _tree(tmp_path)
    plan = plan_cleanup(root, ["2013/a", "2013/b"])
    assert {c.relative for c in plan.removable} == {"2013/a", "2013/b"}, "fixture check"
    (root / "2013" / "b").rmdir()  # gone before its turn: neither removed nor failed

    # `permanent=True`: the folders hold no junk, and without a trash backend on the machine
    # the non-permanent path refuses rather than removes - portable across the three lanes.
    outcome = run_cleanup(root, plan, apply=True, backend=None, permanent=True)
    assert outcome.removed == 1
    assert outcome.removed_folders == ("2013/a",)
    assert outcome.failures == []

    assert record_cleanup(db, root, plan, outcome) is None
    record = json.loads(record_path_for(db).read_text(encoding="utf-8"))
    run = record["run"]
    assert run["kind"] == "clean empty"
    assert run["intended_total"] == 2
    assert run["attempted"] == 1
    names = [(entry["relative"], entry["status"]) for entry in record["files"]]
    assert names == [("2013/a", "removed")], names
