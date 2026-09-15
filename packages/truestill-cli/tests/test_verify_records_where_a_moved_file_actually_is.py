"""A verify that finds a moved copy records where it is. `(akw)`

⚠ **THE DEFECT WAS A DATE THAT COULD NEVER UPDATE.** `verify` wrote a status for VERIFIED,
MISSING and MISMATCH and **nothing at all** for MOVED, so a renamed file kept its old `relative`
*and* whatever `last_verified` it happened to have. Every later verify reported MOVED and wrote
nothing again, so that stamp froze. Measured on the installed build across three verifies: an
intact copy's date moved, a renamed copy's stayed at `21:20:52` for ever, and `truestill where`
went on naming a path that does not exist **with a verification date attached to it**.

**A confident, wrong answer with a freshness guarantee is worse than an obviously stale one** -
nothing about the output invites a reader to doubt it.

**Recording the new location is an OBSERVATION, not a repair.** It is the same class of write as
the three branches that already existed: the drive is not touched, and the catalog is corrected
to match what the drive already says. `rescan` stays report-only - its own rule, *"nothing here
writes to a catalog or to a drive, and no caller of it may"*, is not overturned by this.

**Why `relocate_copy` is safe from here**, which is the question `(abn)`'s three classes ask:
`file_copies` is `PRIMARY KEY (sha256, drive_uuid)`, so the UPDATE reaches exactly one row; and
identity is the recorded **hash** - `_locate_moved` narrows by size and decides by sha256, so a
same-named or same-sized neighbour is never mistaken for the file. That is precisely the
corrective class's safety argument: *"safe because its evidence is a content hash and not a
path"*.
"""

from __future__ import annotations

import contextlib
import io
import sqlite3
from pathlib import Path

import pytest
from truestill_cli.cli import main
from truestill_core.verify import MOVES_RECORDED, NEVER_REPAIRS_FILES


def _library(tmp_path: Path, count: int = 4) -> tuple[Path, Path, Path]:
    """A real organized library: distinct bytes per file, so none is deduped away."""
    src, dest, db = tmp_path / "src", tmp_path / "dest", tmp_path / "catalog.sqlite"
    src.mkdir()
    for i in range(count):
        (src / f"p{i}.jpg").write_bytes(b"\xff\xd8\xff" + bytes([i]) * (5000 + i))
    assert main(["organize", str(src), str(dest), "--db", str(db), "--apply"]) == 0
    return src, dest, db


def _rows(db: Path) -> dict[str, tuple[str, str | None]]:
    """`{sha: (relative, last_verified)}` - the two columns this entry is about."""
    with sqlite3.connect(db) as conn:
        return {
            r[0]: (r[1], r[2])
            for r in conn.execute("SELECT sha256, relative, last_verified FROM file_copies")
        }


def _one_photo(dest: Path) -> Path:
    return sorted(p for p in dest.rglob("*.jpg") if p.is_file())[0]


def test_a_moved_copy_is_recorded_where_it_actually_is(tmp_path: Path) -> None:
    """**The headline.** The catalog names the new path after a verify that saw the move."""
    _, dest, db = _library(tmp_path)
    assert main(["verify", str(dest), "--db", str(db)]) == 0
    photo = _one_photo(dest)
    moved = photo.with_name("RENAMED_" + photo.name)
    photo.rename(moved)

    assert main(["verify", str(dest), "--db", str(db)]) == 0

    recorded = {relative for relative, _ in _rows(db).values()}
    assert moved.relative_to(dest).as_posix() in recorded, (
        "the catalog still names a path that does not exist"
    )
    assert photo.relative_to(dest).as_posix() not in recorded


def test_the_verification_date_moves_again_instead_of_freezing(tmp_path: Path) -> None:
    """⚠ **THE DEFECT ITSELF, as it was measured: three verifies.**

    Before `(akw)` the third verify wrote nothing for the moved copy, so its stamp stayed at
    whatever the first had left - for ever, because the condition never clears on its own. The
    assertion is on the date *changing*, not on it being non-null: a frozen date is non-null too.
    """
    _, dest, db = _library(tmp_path)
    main(["verify", str(dest), "--db", str(db)])
    photo = _one_photo(dest)
    sha = next(s for s, (rel, _) in _rows(db).items() if rel == photo.relative_to(dest).as_posix())
    after_first = _rows(db)[sha][1]
    photo.rename(photo.with_name("RENAMED_" + photo.name))

    main(["verify", str(dest), "--db", str(db)])
    after_second = _rows(db)[sha][1]
    main(["verify", str(dest), "--db", str(db)])
    after_third = _rows(db)[sha][1]

    assert after_first is not None
    assert after_second is not None
    assert after_third is not None
    # ⚠ **THE MOVE'S OWN VERIFY IS THE ONE THAT MUST STAMP IT, and a vacuity check is what found
    # this.** An earlier version compared only the second and third dates - which a mutant that
    # relocated the path and skipped `mark_copy_verified` still passed, because by the third run
    # the file sits at the recorded path and is stamped as an ordinary VERIFIED. The date would
    # have been stale for exactly one run and no test could see it.
    assert after_second != after_first, (
        "the verify that OBSERVED the move did not date what it confirmed"
    )
    assert after_third != after_second, "the stamp froze - this is the defect, unchanged"


def test_a_recorded_move_stops_being_a_move(tmp_path: Path) -> None:
    """Once recorded it is an ordinary copy again. Before this, a renamed file reported MOVED on
    every verify for the rest of the library's life - a permanent line of noise about a fact the
    product had already been told."""
    _, dest, db = _library(tmp_path)
    main(["verify", str(dest), "--db", str(db)])
    photo = _one_photo(dest)
    photo.rename(photo.with_name("RENAMED_" + photo.name))
    main(["verify", str(dest), "--db", str(db)])

    out = _run_verify(dest, db)
    assert "MOVED    : 0" in out, "the same move is still being reported after it was recorded"


def _run_verify(dest: Path, db: Path) -> str:
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        main(["verify", str(dest), "--db", str(db)])
    return buffer.getvalue()


def test_the_rewrite_is_named_in_the_output(tmp_path: Path) -> None:
    """⚠ **NOT SILENTLY.** A catalog rewrite the user did not ask for must be named: how many,
    and that the catalog now points where the files are. This product does not change things
    quietly, and *"verify"* does not sound like a command that writes."""
    _, dest, db = _library(tmp_path)
    main(["verify", str(dest), "--db", str(db)])
    photo = _one_photo(dest)
    photo.rename(photo.with_name("RENAMED_" + photo.name))

    out = _run_verify(dest, db)

    assert MOVES_RECORDED.format(count=1) in out
    assert "Nothing on the drive was touched" in out


def test_a_clean_verify_claims_no_rewrite_it_did_not_make(tmp_path: Path) -> None:
    """The cry-wolf half: a run that moved nothing must not announce a correction."""
    _, dest, db = _library(tmp_path)
    out = _run_verify(dest, db)

    assert "moved file(s)" not in out
    assert NEVER_REPAIRS_FILES in out


def test_the_closing_line_no_longer_claims_to_be_read_only_outright(tmp_path: Path) -> None:
    """⚠ **`(akw)` MADE THE OLD SENTENCE FALSE.** It read *"read-only: Truestill never repairs"*,
    and a verify that relocates a copy writes to the catalog. The promise about a user's FILES is
    unchanged and still absolute; the blanket claim is what had to go, because an untrue sentence
    in a report is the class of defect this walkthrough keeps finding."""
    _, dest, db = _library(tmp_path)
    out = _run_verify(dest, db)

    assert "read-only on your files" in out
    assert "(read-only: Truestill never repairs" not in out


def test_a_file_moved_off_the_drive_is_missing_and_never_relocated(tmp_path: Path) -> None:
    """⚠ **A DRIVE CANNOT TESTIFY ABOUT SOMEWHERE ELSE.** The search is `os.walk(root)`, so a
    file carried off the drive is not found - and MISSING is the honest answer, because from this
    drive's point of view the content is gone. Recording a path outside the root would also
    break the invariant that `relative` is drive-relative."""
    _, dest, db = _library(tmp_path)
    main(["verify", str(dest), "--db", str(db)])
    outside = tmp_path / "outside"
    outside.mkdir()
    photo = _one_photo(dest)
    before = photo.relative_to(dest).as_posix()
    photo.rename(outside / photo.name)

    out = _run_verify(dest, db)

    assert "MISSING  : 1" in out
    assert "MOVED    : 1" not in out
    assert before in {relative for relative, _ in _rows(db).values()}, (
        "the recorded path was rewritten to somewhere off the drive"
    )


def test_a_move_is_recorded_even_when_the_drive_cannot_be_written_to(tmp_path: Path) -> None:
    """The catalog is not on the drive, so a read-only drive does not stop the observation -
    and *"Nothing on the drive was touched"* is then literally true rather than merely intended.
    """
    _, dest, db = _library(tmp_path)
    main(["verify", str(dest), "--db", str(db)])
    photo = _one_photo(dest)
    moved = photo.with_name("RENAMED_" + photo.name)
    photo.rename(moved)
    for path in sorted(dest.rglob("*"), reverse=True):
        path.chmod(0o555 if path.is_dir() else 0o444)
    dest.chmod(0o555)
    try:
        out = _run_verify(dest, db)
        assert MOVES_RECORDED.format(count=1) in out
        assert moved.relative_to(dest).as_posix() in {r for r, _ in _rows(db).values()}
    finally:
        dest.chmod(0o755)
        for path in sorted(dest.rglob("*")):
            path.chmod(0o755 if path.is_dir() else 0o644)


@pytest.mark.parametrize("twins", [2, 3])
def test_identical_content_elsewhere_relocates_to_one_of_them(tmp_path: Path, twins: int) -> None:
    """Two byte-identical files and the recorded one deleted: **either is a true answer**, and
    the catalog holds one row per (content, drive) so only one can be named. The assertion is
    that it names a path that exists and holds those bytes - not which one."""
    _, dest, db = _library(tmp_path)
    main(["verify", str(dest), "--db", str(db)])
    photo = _one_photo(dest)
    payload = photo.read_bytes()
    for n in range(twins):
        photo.with_name(f"twin{n}_{photo.name}").write_bytes(payload)
    photo.unlink()

    main(["verify", str(dest), "--db", str(db)])

    named = [dest / relative for relative, _ in _rows(db).values()]
    landed = [p for p in named if p.name.startswith("twin")]
    assert len(landed) == 1
    assert landed[0].read_bytes() == payload
