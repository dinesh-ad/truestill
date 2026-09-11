"""Bringing photographs back from a drive. **Every test asserts the library did not lose anything.**

Stage 2 of the restore arc. The documented data-loss modes for exactly this operation are what
these tests are shaped around, and each one is a rule with a test of its own:

* *"a sync job running in the wrong direction can overwrite newer files with older versions"* -
  so **nothing at the destination is ever replaced**, and an occupied path is a named skip.
* an unmounted source reading as empty, so the destination is wiped - so **nothing is ever
  deleted**, which makes an empty source a no-op rather than a catastrophe.
* *"copy only adds files"* - so the gap is by content hash and a re-run copies nothing.

⚠ **MTIMES AND DIGESTS, NOT COUNTS.** A test that asserts "6 copied" passes just as happily on a
run that copied 6 and clobbered 34. Every test here that touches an existing library snapshots the
bytes of what was already there and compares them afterwards.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path

import pytest
from truestill_core.app_paths import RUN_RECORD_FILENAME
from truestill_core.catalog import Catalog
from truestill_core.drive import create_marker
from truestill_core.hashing import sha256_file
from truestill_core.recover import (
    RecoverPair,
    RecoverStoppedError,
    Skipped,
    plan_recovery,
    recover_into_library,
)

RELATIVE = "Camera/2014/photo-{:05d}.jpg"


def _content(index: int) -> bytes:
    """Distinct bytes per index, long enough that a truncation would change the digest."""
    return f"photograph-{index:05d}-".encode() * 64


def _snapshot(root: Path) -> dict[str, tuple[str, int]]:
    """Digest and mtime of every file under ``root``. **The evidence nothing was touched.**

    ⚠ Dotfiles included, deliberately: `.truestill-drive.json` is the drive's identity, and a run
    that rewrote it would be changing which library this is. The photograph count is asked for
    separately by :func:`_photographs` rather than by filtering here.
    """
    return {
        path.relative_to(root).as_posix(): (sha256_file(path), path.stat().st_mtime_ns)
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _photographs(root: Path) -> list[Path]:
    """Everything but the dotfiles a drive carries."""
    return [p for p in root.rglob("*") if p.is_file() and not p.name.startswith(".")]


@pytest.fixture
def world(tmp_path: Path) -> tuple[Path, RecoverPair]:
    """A drive holding 40 photographs and a library holding 34 of them, both registered."""
    db = tmp_path / "catalog.sqlite"
    drive, library = tmp_path / "Backup", tmp_path / "Library"
    drive.mkdir()
    library.mkdir()
    on_drive = create_marker(drive, label="Backup Drive")
    here = create_marker(library, label="My Library")
    with Catalog(db) as catalog:
        catalog.upsert_drive(uuid=on_drive.uuid, label=on_drive.label)
        catalog.upsert_drive(uuid=here.uuid, label=here.label)
        for index in range(40):
            _place(catalog, drive, on_drive.uuid, index)
            if index < 34:
                _place(catalog, library, here.uuid, index)
    return db, RecoverPair(drive=drive, drive_marker=on_drive, library=library, library_marker=here)


def _place(catalog: Catalog, root: Path, uuid: str, index: int, *, on_disk: bool = True) -> None:
    """Record one copy, and by default put the real bytes where the row says they are."""
    relative = RELATIVE.format(index)
    payload = _content(index)
    if on_disk:
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
    catalog.record_copy(
        sha256=f"{index:064x}",
        drive_uuid=uuid,
        relative=relative,
        size=len(payload),
        copy_sha256=None,
    )


def _run(db: Path, pair: RecoverPair) -> object:
    return recover_into_library(pair, db, progress=lambda _p: None, cancel=threading.Event())


# ------------------------------------------------------------------- it fills the gap, exactly


def test_forty_against_thirty_four_copies_six_and_touches_nothing_else(
    world: tuple[Path, RecoverPair],
) -> None:
    """**The boundary case, with the untouched files proved untouched.**

    The count is the easy half. The half that matters is that all 34 files the library already
    had are byte-for-byte and mtime-for-mtime what they were - which is what separates "copied 6"
    from "copied 6 and rewrote 34 with the drive's versions".
    """
    db, pair = world
    before = _snapshot(pair.library)
    assert len(_photographs(pair.library)) == 34, "the fixture is not the shape this test needs"

    outcome = _run(db, pair)

    assert outcome.copied == 6
    assert len(_photographs(pair.library)) == 40
    after = _snapshot(pair.library)
    assert {k: v for k, v in after.items() if k in before} == before, "existing files changed"


def test_a_second_run_copies_nothing(world: tuple[Path, RecoverPair]) -> None:
    """*"copy only adds files"*. The gap is empty now, so the second run is a no-op.

    Asserted on the whole library rather than on the count: a run that copied 0 while deleting
    something would satisfy `copied == 0` perfectly.
    """
    db, pair = world
    _run(db, pair)
    settled = _snapshot(pair.library)

    again = _run(db, pair)

    assert again.copied == 0
    assert again.skipped == []
    assert _snapshot(pair.library) == settled


def test_the_gap_is_content_not_path(world: tuple[Path, RecoverPair]) -> None:
    """A photograph already in the library under a DIFFERENT name is not a gap.

    Identity is `sha256`. A path-keyed comparison would copy it again, leaving the user a
    duplicate to clean up - and after a layout migration it would do that to everything.
    """
    db, pair = world
    with Catalog(db) as catalog:
        # The library already holds #39's bytes, filed somewhere else entirely.
        moved = pair.library / "Somewhere/Else/renamed.jpg"
        moved.parent.mkdir(parents=True, exist_ok=True)
        moved.write_bytes(_content(39))
        catalog.record_copy(
            sha256=f"{39:064x}",
            drive_uuid=pair.library_marker.uuid,
            relative="Somewhere/Else/renamed.jpg",
            size=len(_content(39)),
            copy_sha256=None,
        )

    outcome = _run(db, pair)

    assert outcome.copied == 5, "the file under another name was copied again"
    assert not (pair.library / RELATIVE.format(39)).exists()


# --------------------------------------------------------------------------- it never overwrites


def test_a_file_already_at_the_target_path_is_skipped_and_named(
    world: tuple[Path, RecoverPair],
) -> None:
    """⚠ **THE RULE, AND THE MODE THE FIELD LOSES DATA TO.**

    The catalog does not know about this file - it is at a gap's path with different bytes, which
    is exactly what an interrupted earlier run or a hand-copy leaves behind. `commit()` would
    replace it without a word, because `Path.replace` overwrites. It must not.

    The collision case is stage 4. Until then the only honest thing is to leave it and say so.
    """
    db, pair = world
    squatter = pair.library / RELATIVE.format(38)
    squatter.parent.mkdir(parents=True, exist_ok=True)
    squatter.write_bytes(b"something the user put here")
    before = _snapshot(pair.library)

    outcome = _run(db, pair)

    assert squatter.read_bytes() == b"something the user put here", "the library file was replaced"
    assert _snapshot(pair.library)[RELATIVE.format(38)] == before[RELATIVE.format(38)]
    assert (RELATIVE.format(38), Skipped.ALREADY_THERE) in outcome.skipped
    assert outcome.copied == 5


def test_a_skip_is_not_a_failure(world: tuple[Path, RecoverPair]) -> None:
    """The two are separate lists because they mean opposite things to a reader.

    A failure is Truestill unable to do what it should have managed. A skip is the product working
    correctly on a library that is not what the catalog says. Reporting six skips as six failures
    sends somebody hunting a defect that is not there.
    """
    db, pair = world
    for index in (36, 37):
        occupied = pair.library / RELATIVE.format(index)
        occupied.parent.mkdir(parents=True, exist_ok=True)
        occupied.write_bytes(b"mine")

    outcome = _run(db, pair)

    assert len(outcome.skipped) == 2
    assert outcome.failures == []


# ------------------------------------------------------------------------ a row is a claim


def test_a_row_the_drive_does_not_honour_is_a_skip_not_a_failure(
    world: tuple[Path, RecoverPair],
) -> None:
    """⚠ **The measured case: 429 rows against 124 files actually there on NTFS.**

    These rows describe a removable drive, and an interrupted backup writes a row for every copy
    the medium never took. The run must carry on, name them, and point at the command that fixes
    the records.
    """
    db, pair = world
    for index in (34, 35):
        (pair.drive / RELATIVE.format(index)).unlink()

    outcome = _run(db, pair)

    assert outcome.copied == 4
    assert sorted(outcome.skipped) == sorted(
        (RELATIVE.format(i), Skipped.NOT_ON_THE_DRIVE) for i in (34, 35)
    )
    assert outcome.failures == []


def test_a_drive_nobody_walked_plans_nothing_and_says_so(tmp_path: Path) -> None:
    """⚠ **Stage 1's worst wrong answer, and it is worse when a writer is holding it.**

    `drives --init` writes a marker and does not walk, so `file_copies` is empty while the drive
    is full. `drive_walked` is what stops "0 to copy" being reported as "nothing to bring back"
    to somebody who has just lost their library.
    """
    db = tmp_path / "c.sqlite"
    drive, library = tmp_path / "Fresh", tmp_path / "Library"
    drive.mkdir()
    library.mkdir()
    on_drive, here = create_marker(drive, label="Fresh"), create_marker(library, label="Lib")
    (drive / "a.jpg").write_bytes(_content(1))  # the drive is FULL
    with Catalog(db) as catalog:
        catalog.upsert_drive(uuid=on_drive.uuid, label=on_drive.label)
        catalog.upsert_drive(uuid=here.uuid, label=here.label)

    plan = plan_recovery(
        RecoverPair(drive=drive, drive_marker=on_drive, library=library, library_marker=here), db
    )

    assert plan.drive_walked is False
    assert plan.count == 0, "the raw count is zero - the SURFACE is what must not report it"


def test_a_walked_drive_with_a_real_zero_is_a_different_state(
    world: tuple[Path, RecoverPair],
) -> None:
    """The other side of the line, and what makes the test above mean anything.

    Without it, `drive_walked` could be hard-coded False and every test above would still pass.
    """
    db, pair = world
    _run(db, pair)

    plan = plan_recovery(pair, db)

    assert plan.drive_walked is True
    assert plan.count == 0


# ------------------------------------------------------------------------------- it never deletes


def test_the_drive_is_read_and_left_exactly_as_it_was(world: tuple[Path, RecoverPair]) -> None:
    """The source side of copy semantics. A recover reads the drive; it must not write to it."""
    db, pair = world
    before = _snapshot(pair.drive)
    assert len(before) > 1, "an empty drive would make the comparison below free"

    _run(db, pair)

    assert _snapshot(pair.drive) == before


def test_an_empty_drive_is_a_no_op_and_never_a_wipe(tmp_path: Path) -> None:
    """⚠ **The unmounted-source mode, which in other tools empties the destination.**

    A source with nothing in it must do nothing at all. This is the one where a `sync` mental
    model deletes a library, so it is asserted on the library's whole contents.
    """
    db = tmp_path / "c.sqlite"
    drive, library = tmp_path / "Empty", tmp_path / "Library"
    drive.mkdir()
    library.mkdir()
    on_drive, here = create_marker(drive, label="Empty"), create_marker(library, label="Lib")
    with Catalog(db) as catalog:
        catalog.upsert_drive(uuid=on_drive.uuid, label=on_drive.label)
        catalog.upsert_drive(uuid=here.uuid, label=here.label)
        for index in range(5):
            _place(catalog, library, here.uuid, index)
    before = _snapshot(library)
    assert _photographs(library), "an empty library would make this assertion free"

    outcome = recover_into_library(
        RecoverPair(drive=drive, drive_marker=on_drive, library=library, library_marker=here),
        db,
        progress=lambda _p: None,
        cancel=threading.Event(),
    )

    assert outcome.copied == 0
    assert _snapshot(library) == before


def test_the_same_drive_twice_is_refused_before_anything_moves(
    world: tuple[Path, RecoverPair],
) -> None:
    """Recovering a drive into itself is the one direction that cannot mean anything."""
    db, pair = world
    same = RecoverPair(
        drive=pair.library,
        drive_marker=pair.library_marker,
        library=pair.library,
        library_marker=pair.library_marker,
    )
    before = _snapshot(pair.library)

    with pytest.raises(ValueError, match="same drive"):
        _run(db, same)

    assert _snapshot(pair.library) == before


# ------------------------------------------------------------------- what lands is what is recorded


def test_the_copy_is_verified_and_its_own_digest_is_recorded(
    world: tuple[Path, RecoverPair],
) -> None:
    """The row records the hash of **what was written**, never the one inherited from the drive.

    That is what stops a recovered copy being the UNVERIFIABLE case a later `verify` cannot judge.
    """
    db, pair = world
    _run(db, pair)

    with Catalog(db) as catalog:
        rows = {
            str(r["relative"]): r["copy_sha256"]
            for r in catalog.copies_on_drive(pair.library_marker.uuid)
        }

    for index in range(34, 40):
        relative = RELATIVE.format(index)
        assert rows[relative] == sha256_file(pair.library / relative)


def test_a_drive_file_that_does_not_match_its_row_never_takes_the_name(
    world: tuple[Path, RecoverPair],
) -> None:
    """Verified BEFORE it takes the name, so a bad copy is never at the real path for any
    interval at all - `_copy_verified`'s window, kept closed on this path too."""
    db, pair = world
    with Catalog(db) as catalog:
        catalog.record_copy(
            sha256=f"{34:064x}",
            drive_uuid=pair.drive_marker.uuid,
            relative=RELATIVE.format(34),
            size=len(_content(34)),
            copy_sha256="f" * 64,  # the drive's row swears to bytes the file does not have
        )

    outcome = _run(db, pair)

    assert not (pair.library / RELATIVE.format(34)).exists()
    assert outcome.copied == 5
    assert len(outcome.failures) == 1


# ------------------------------------------------------------- stopped part way, and the record


def test_a_stop_records_what_landed_and_never_claims_what_did_not(
    world: tuple[Path, RecoverPair],
) -> None:
    """⚠ **THE FAILURE A RUN RECORD EXISTS TO SURVIVE, and the one it is easiest to get wrong.**

    A record built from the PLAN would name all six files as handled. Organize's own handler calls
    that *"a false custody record, which is worse than no record"* - a person reading it would
    believe photographs are in their library that are not.

    The drive is pulled after the third copy. What must be true afterwards: three files on disk,
    three entries in the record, `attempted` equal to what was reached, and `never_attempted`
    accounting for the rest. Nothing may claim a fourth.
    """
    db, pair = world
    landed: list[str] = []

    def pull_the_drive_after_three(progress: object) -> None:
        landed.append(str(getattr(progress, "name", "")))
        if len(landed) == 3:
            # Renaming the drive out from under the run is what an unplug looks like to the
            # copy loop: the next `staged_copy` gets ENOENT on its source.
            pair.drive.rename(pair.drive.with_name("GONE"))

    with pytest.raises((RecoverStoppedError, OSError)):
        recover_into_library(
            pair, db, progress=pull_the_drive_after_three, cancel=threading.Event()
        )

    on_disk = sorted(p.name for p in _photographs(pair.library))
    record = json.loads((db.parent / RUN_RECORD_FILENAME).read_text(encoding="utf-8"))
    copied_entries = [e for e in record["files"] if e["status"] == "copied"]
    assert len(on_disk) == 37, "three of the six should have landed before the pull"
    assert len(copied_entries) == 3
    assert record["run"]["kind"] == "recover"
    for entry in copied_entries:
        assert (pair.library / str(entry["relative"])).is_file(), (
            "the record claims a file that is not on disk"
        )
    assert record["run"]["attempted"] + record["run"]["stopped"]["never_attempted"] == 6


def test_a_finished_run_writes_a_record_with_no_stop_block(
    world: tuple[Path, RecoverPair],
) -> None:
    """The anti-vacuity half. `stopped` is present ONLY on an abort, which is what lets a reader
    tell *"it ended with failures"* from *"it was cut off"*."""
    db, pair = world

    _run(db, pair)

    record = json.loads((db.parent / RUN_RECORD_FILENAME).read_text(encoding="utf-8"))
    assert record["run"]["stopped"] is None
    assert record["run"]["attempted"] == 6
    assert record["run"]["intended_total"] == 6
    assert len([e for e in record["files"] if e["status"] == "copied"]) == 6


def test_the_record_names_a_skip_as_a_skip(world: tuple[Path, RecoverPair]) -> None:
    """A file left alone must be legible in the record as left alone, not as copied or failed -
    otherwise the document cannot answer the one question it is kept for."""
    db, pair = world
    occupied = pair.library / RELATIVE.format(39)
    occupied.parent.mkdir(parents=True, exist_ok=True)
    occupied.write_bytes(b"mine")

    _run(db, pair)

    record = json.loads((db.parent / RUN_RECORD_FILENAME).read_text(encoding="utf-8"))
    entry = next(e for e in record["files"] if e["relative"] == RELATIVE.format(39))
    assert entry["status"] == "skipped"
    assert entry["detail"] == Skipped.ALREADY_THERE.value
    assert entry["copy_sha256"] is None
