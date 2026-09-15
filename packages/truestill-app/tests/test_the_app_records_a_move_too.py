"""The app's verify records a move, exactly as the CLI's does. `(akw)`

⚠ **`(aku)` SET THE PRECEDENT AND THE REASON IS DRIFT.** The MISMATCH branch was added *"on BOTH
surfaces in one commit"* because a write branch that exists on one surface and not the other is a
catalog that means different things depending on which window the user had open. This is the same
write, so it lands the same way.
"""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

from truestill_app.service.verify import VerifyJobSummary, verify_run
from truestill_cli.cli import main


def _library(tmp_path: Path) -> tuple[Path, Path]:
    src, dest, db = tmp_path / "src", tmp_path / "dest", tmp_path / "catalog.sqlite"
    src.mkdir()
    for i in range(3):
        (src / f"a{i}.jpg").write_bytes(b"\xff\xd8\xff" + bytes([i]) * (4000 + i))
    assert main(["organize", str(src), str(dest), "--db", str(db), "--apply"]) == 0
    return dest, db


def _verify(dest: Path, db: Path) -> VerifyJobSummary:
    """Run the app's verify target the way its job runner does."""
    target = verify_run(dest, db)
    assert callable(target), f"verify_run soft-failed: {target}"
    return target(lambda _p: None, threading.Event())


def _rows(db: Path) -> list[tuple[str, str | None]]:
    with sqlite3.connect(db) as conn:
        return list(conn.execute("SELECT relative, last_verified FROM file_copies"))


def test_the_app_records_the_new_location(tmp_path: Path) -> None:
    dest, db = _library(tmp_path)
    _verify(dest, db)
    photo = sorted(p for p in dest.rglob("*.jpg") if p.is_file())[0]
    photo.rename(photo.with_name("RENAMED_" + photo.name))

    _verify(dest, db)

    recorded = {relative for relative, _ in _rows(db)}
    assert "RENAMED_" in " ".join(recorded), f"the app left the old path behind: {recorded}"


def test_the_app_lets_the_stamp_move_again(tmp_path: Path) -> None:
    """The frozen date, on the surface most people use."""
    dest, db = _library(tmp_path)
    _verify(dest, db)
    photo = sorted(p for p in dest.rglob("*.jpg") if p.is_file())[0]
    photo.rename(photo.with_name("RENAMED_" + photo.name))

    _verify(dest, db)
    second = dict(_rows(db))
    _verify(dest, db)
    third = dict(_rows(db))

    moved = next(r for r in third if "RENAMED_" in r)
    assert third[moved] != second[moved], "the app's stamp froze"


def test_both_surfaces_write_the_same_columns() -> None:
    """⚠ **The anti-drift assertion.** Read the two source files rather than trusting that a
    reviewer noticed: whatever the CLI writes for a MOVED result, the app writes too."""
    root = Path(__file__).resolve().parents[3]
    cli = (root / "packages/truestill-cli/src/truestill_cli/cli.py").read_text(encoding="utf-8")
    app = (root / "packages/truestill-app/src/truestill_app/service/verify.py").read_text(
        encoding="utf-8"
    )

    for surface in (cli, app):
        assert "CopyStatus.MOVED and result.moved_to is not None" in surface
        assert "catalog.relocate_copy(" in surface
