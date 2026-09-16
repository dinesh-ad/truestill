"""End to end: the repair branch fires on a corpse and refuses on a photograph. `(alc)`

The unit tests beside this exercise `_free_relative` and `_reclaimable_target` with strings. This
drives the real command against a real drive, because the thing being asserted is what is **on
the disk afterwards** - and the failure mode is a photograph that is no longer there.

⚠ **Nothing here touches a real library.** Every destination is a `tmp_path`.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from truestill_cli.cli import main
from truestill_core import organizer
from truestill_core.destinations import local

JPEG = b"\xff\xd8\xff\xe0"


def _organized(tmp_path: Path) -> tuple[Path, Path, Path]:
    """One photograph, organized into a library. Returns (library, db, the placed file)."""
    source, library, db = tmp_path / "src", tmp_path / "Lib", tmp_path / "catalog.sqlite"
    source.mkdir()
    (source / "holiday.jpg").write_bytes(JPEG + b"original" * 512)
    assert main(["organize", str(source), str(library), "--db", str(db), "--apply"]) == 0
    placed = next(p for p in library.rglob("*.jpg"))
    return library, db, placed


def _recorded(db: Path) -> list[tuple[str, int]]:
    with sqlite3.connect(db) as conn:
        return [
            (str(r[0]), int(r[1] or 0))
            for r in conn.execute("SELECT relative, size FROM file_copies")
        ]


def _reorganize(tmp_path: Path, library: Path, db: Path, body: bytes) -> int:
    """Organize the same content again, as a user re-running after an interruption would."""
    again = tmp_path / "again"
    again.mkdir(exist_ok=True)
    (again / "holiday.jpg").write_bytes(body)
    return main(["organize", str(again), str(library), "--db", str(db), "--apply"])


def test_a_corpse_at_our_own_path_is_repaired_in_place(tmp_path: Path) -> None:
    """The behaviour `(aja)` built this branch for, asserted end to end.

    An interrupted write left zero bytes where the catalog records a photograph. The re-run must
    replace it **at that path** - not beside it, which is `(ain)`'s measured nine-files-from-three.
    """
    library, db, placed = _organized(tmp_path)
    body = placed.read_bytes()
    placed.write_bytes(b"")  # the interruption's corpse

    assert _reorganize(tmp_path, library, db, body) == 0

    assert placed.read_bytes() == body, "the corpse was not repaired"
    assert len(list(library.rglob("*.jpg"))) == 1, "a duplicate was created beside it"
    assert len(_recorded(db)) == 1


def test_a_photograph_the_catalog_knows_is_kept_and_the_copy_lands_beside_it(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """⚠ **THE DEFECT THIS ENTRY EXISTS FOR.**

    A user replaced an organized photograph with another photograph of their own - one this
    catalog has a row for. The catalog row still names that path, so before `(alc)` the re-run
    renamed onto it and the user's file was gone. It is now kept, the copy is placed beside it,
    and the run says which file it declined to overwrite.
    """
    library, db, placed = _organized(tmp_path)
    body = placed.read_bytes()

    # A second photograph, organized so the catalog knows it, then moved onto the first's path.
    other = tmp_path / "other"
    other.mkdir()
    (other / "beach.jpg").write_bytes(JPEG + b"a different photograph" * 512)
    assert main(["organize", str(other), str(library), "--db", str(db), "--apply"]) == 0
    beach = next(p for p in library.rglob("beach*.jpg") if p != placed)
    theirs = beach.read_bytes()
    beach.unlink()
    placed.write_bytes(theirs)

    assert _reorganize(tmp_path, library, db, body) == 0

    assert placed.read_bytes() == theirs, "a photograph the catalog knows was destroyed"
    # ⚠ **`stderr`, and that is `_print_capped`'s own ruling** - clig.dev: errors and messaging
    # belong there so a run piped into a file does not swallow them. Asserted on the stream the
    # product chose rather than on the one I first guessed.
    said = capsys.readouterr()
    assert "KEPT, NOT OVERWRITTEN" in said.err
    assert "did not overwrite" in said.err
    assert sorted(p.read_bytes() for p in library.rglob("*.jpg")) == sorted([theirs, body])


def test_an_intact_copy_is_left_alone_even_when_dedup_sends_us_here(tmp_path: Path) -> None:
    """The third outcome, and it is reachable through a bug one layer up.

    `credible_copies` compares sizes **by path** (`(alb)` item 9), so on a folding filesystem a
    case drift makes a perfectly good copy look incredible and we arrive with nothing to repair.
    Rewriting it would be harmless and wasteful; the branch declines instead.
    """
    library, db, placed = _organized(tmp_path)
    body = placed.read_bytes()
    mtime = placed.stat().st_mtime_ns

    assert _reorganize(tmp_path, library, db, body) == 0

    assert placed.read_bytes() == body
    assert placed.stat().st_mtime_ns == mtime, "an intact copy was rewritten"


def test_an_ordinary_run_into_an_empty_library_reads_nothing_extra(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The cry-wolf half. The branch must not fire, and must not cost a read, in normal use.

    Counted at the destination's own `checksum`, so a version that hashed every target would
    fail here rather than merely being slow.
    """
    reads: list[str] = []
    real = local.LocalDestination.checksum

    def spy(self: local.LocalDestination, relative_path: str) -> str:
        reads.append(relative_path)
        return real(self, relative_path)

    monkeypatch.setattr(local.LocalDestination, "checksum", spy)

    _organized(tmp_path)

    assert reads == [], f"an ordinary organize hashed a destination file: {reads}"


def test_the_run_asks_the_destination_whether_it_folds_case(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """⚠ **Written because a mutation deleting the question survived every other test.**

    Replacing `fold_case=_destination_folds_case(destination)` with a bare `False` is invisible
    on ext4 and tmpfs, because the probe answers `False` there anyway - so every CI lane that
    matters agrees with the mutant. What can be asserted on any filesystem is that the run **asks**,
    and asks once, which is the wiring the answer travels through.

    ⚠ **And that it does NOT ask on a dry run**: a preview decides nothing destructive, so it
    owes the destination no extra question.
    """
    asked: list[object] = []
    real = organizer._destination_folds_case

    # A function, not a `lambda (append, real)[1]`: mypy rejects the latter, and this is the
    # third time in one session I have written it.
    def counting_probe(destination: object) -> bool:
        asked.append(destination)
        return real(destination)

    monkeypatch.setattr(organizer, "_destination_folds_case", counting_probe)

    source, library, db = tmp_path / "src", tmp_path / "Lib", tmp_path / "catalog.sqlite"
    source.mkdir()
    (source / "holiday.jpg").write_bytes(JPEG + b"x" * 512)

    assert main(["organize", str(source), str(library), "--db", str(db)]) == 0
    assert asked == [], "a dry run asked the destination a question it did not need"

    assert main(["organize", str(source), str(library), "--db", str(db), "--apply"]) == 0
    assert len(asked) == 1, "the run asked the destination none or more than once"
