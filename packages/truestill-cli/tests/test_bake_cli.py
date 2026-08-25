"""`truestill bake` writes confirmed dates from the terminal. `(ahd)` step 2.

**Why this exists.** The bake was the one mutating run with no CLI, and `(ahd)` found that was a
**gap rather than a decision**: `BACKLOG.md`'s *App-surface deferrals* register records the date
*rescue* as app-only because it is review-shaped, and does not contain the bake. A bake is not
review-shaped - it is batch execution of decisions already made, which is the shape every other
CLI mutating command has.

⚠ **THE SECOND CALLER IS THE FIRST REAL TEST OF `(ahe)`'s GUARD, and it failed it.** `(ahe)` put
the confirmation check in `truestill_app.service.bake.bake_run` and argued it belonged "where the
write happens". It did not: `bake_run` was simply the only caller then. This command calls
`truestill_core.bake.bake_confirmed_dates` directly and would have walked straight past it. The
guard moved down to the write and raises :class:`NotConfirmedError`, so a third surface cannot
miss it either - which is what `(ahe)` claimed and this file is what makes true.

**Every helper is reused, none invented**: `_typed_confirmation` (the `reclaim` shape), the
`--apply` gate, a `"bake": "path"` row in `_LOCKS_DRIVE_AT` after which `_run_holding_the_drive`
takes the lock, and `_progress_printer`.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
from PIL import Image
from truestill_cli.cli import main
from truestill_core.bake import CONFIRM_WORD, NOTHING_CONFIRMED_NOTE
from truestill_core.catalog import Catalog
from truestill_core.drive import create_marker
from truestill_core.hashing import sha256_file

CONFIRMED = datetime(2011, 3, 4, 9, 15, 0)


def _drive(tmp_path: Path, *, confirm: bool = True) -> tuple[Path, Path]:
    """One photo on a real drive, its date confirmed unless a test wants the empty case."""
    root = tmp_path / "drive"
    root.mkdir()
    marker = create_marker(root, "Drive A")
    db = tmp_path / "c.sqlite"
    with Catalog(db) as catalog:
        catalog.upsert_drive(uuid=marker.uuid, label="Drive A")
        path = root / "Camera/2014/a.jpg"
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
        if confirm:
            catalog.confirm_date(sha, CONFIRMED.isoformat(), confirmed_by="test")
    return root, db


def _baked(db: Path) -> int:
    with Catalog(db) as catalog:
        row = catalog._conn.execute(
            "SELECT COUNT(*) AS n FROM file_copies WHERE date_baked_at IS NOT NULL"
        ).fetchone()
    return int(row["n"])


# ------------------------------------------------------------------------------ the confirmation


def test_apply_without_the_typed_word_writes_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The regression: EOF on stdin is a refusal, never an assumed yes."""
    root, db = _drive(tmp_path)

    def _eof(*_: object) -> str:
        raise EOFError

    monkeypatch.setattr("builtins.input", _eof)
    code = main(["bake", str(root), "--db", str(db), "--apply"])

    assert code == 0
    assert _baked(db) == 0, "a bake ran with no confirmation"
    assert "Aborted" in capsys.readouterr().out


def test_a_wrong_word_is_refused_rather_than_ignored(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Cry-wolf half: the check compares, it does not merely test for presence."""
    root, db = _drive(tmp_path)
    monkeypatch.setattr("builtins.input", lambda *_: "yes")
    code = main(["bake", str(root), "--db", str(db), "--apply"])

    assert code == 0
    assert _baked(db) == 0, "a wrong word authorised the write"
    assert "Aborted" in capsys.readouterr().out


def test_the_right_word_bakes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Cry-wolf half: a correctly confirmed run must still write, or the guard is a wall."""
    root, db = _drive(tmp_path)
    monkeypatch.setattr("builtins.input", lambda *_: CONFIRM_WORD)
    code = main(["bake", str(root), "--db", str(db), "--apply"])

    assert code == 0, capsys.readouterr().out
    assert _baked(db) == 1, "the confirmed bake did not write"


# ------------------------------------------------------------------------- the preview writes not


def test_a_preview_writes_nothing_to_the_drive_or_the_catalog(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Dry-run is the default, and proved the way `test_bake_preview.py` proves it: by bytes.

    ⚠ The catalog is settled with two opens **before** the baseline, because a single load can
    hide a lazy first-run write inside it - schema creation, a settings default, a cleared hint.
    """
    root, db = _drive(tmp_path)
    with Catalog(db):
        pass
    with Catalog(db):
        pass
    before_db = db.read_bytes()
    before_files = {p: p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}

    def _never(*_: object) -> str:
        asked = "a preview asked for a confirmation"
        raise AssertionError(asked)

    monkeypatch.setattr("builtins.input", _never)
    assert main(["bake", str(root), "--db", str(db)]) == 0

    assert db.read_bytes() == before_db, "the preview wrote to the catalog"
    assert {p: p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()} == before_files


def test_the_preview_names_the_irreversibility_before_the_prompt(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The warning is the thing to read **before** typing, not an explanation offered after."""
    root, db = _drive(tmp_path)
    typed: list[str] = []

    def _record(*_: object) -> str:
        typed.append(capsys.readouterr().out)
        return "no"

    monkeypatch.setattr("builtins.input", _record)
    main(["bake", str(root), "--db", str(db), "--apply"])

    assert typed, "the prompt never appeared"
    assert "cannot be undone" in typed[0], (
        f"the irreversibility was not stated before the prompt: {typed[0]!r}"
    )


# ------------------------------------------------------------- the constraint, said out loud


def test_nothing_confirmed_says_so_and_says_where_confirmations_come_from(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """⚠ **"Nothing to do" would be a lie by omission.** `(ahd)`

    `confirmations_to_bake` returns zero rows both when every confirmed date is already written
    **and** when nobody has confirmed anything - opposite situations that need opposite
    sentences. `Catalog.confirmed_dates_total` is what tells them apart, and the wording lives in
    core so the app can say the same thing.
    """
    root, db = _drive(tmp_path, confirm=False)
    assert main(["bake", str(root), "--db", str(db)]) == 0

    out = capsys.readouterr().out
    assert NOTHING_CONFIRMED_NOTE in out
    assert "truestill restore" in out, "the way to get confirmations onto this machine is unnamed"


def test_a_fully_baked_drive_says_something_different(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The other zero. Cry-wolf: this must NOT claim nothing was ever confirmed."""
    root, db = _drive(tmp_path)
    monkeypatch.setattr("builtins.input", lambda *_: CONFIRM_WORD)
    main(["bake", str(root), "--db", str(db), "--apply"])
    capsys.readouterr()

    assert main(["bake", str(root), "--db", str(db)]) == 0
    out = capsys.readouterr().out
    assert NOTHING_CONFIRMED_NOTE not in out, "a baked drive was told nothing was confirmed"
    assert "already inside the files" in out
