"""The recover surface: the route, the wording it ships, and what it refuses. Restore stage 3.

⚠ **THE WORDING IS ASSERTED AGAINST CORE'S CONSTANTS, NEVER AGAINST A COPY OF THEM.** The whole
reason `NOTHING_IS_LOST` and `DRIVE_IS_READ_ONLY` live in `truestill_core.recover` is that the
terminal and the drive card must reassure a frightened person in identical words. A literal in
this file would let the two drift and still pass.

**Why the reassurance matters enough to test.** The user arriving at this button has met restores
that destroy things: UrBackup ships restore **disabled by default**, and
Backblaze tells people to make another backup first. Truestill's never overwrites and never
deletes, and the
remedy for that inherited fear is a sentence - so the sentence is treated as a shipped artifact.
"""

from __future__ import annotations

import threading
from pathlib import Path

from truestill_app import service
from truestill_core import recover
from truestill_core.catalog import Catalog
from truestill_core.drive import create_marker, read_marker
from truestill_core.hashing import sha256_file

RELATIVE = "Camera/2014/p{:04d}.jpg"


def _content(index: int) -> bytes:
    return f"photograph-{index:04d}-".encode() * 32


def _world(tmp_path: Path, *, on_drive: int = 8, here: int = 5) -> tuple[Path, Path, Path]:
    db = tmp_path / "c.sqlite"
    drive, library = tmp_path / "Backup", tmp_path / "Library"
    drive.mkdir()
    library.mkdir()
    create_marker(drive, label="Backup Drive")
    create_marker(library, label="My Library")
    with Catalog(db) as catalog:
        for root, count in ((drive, on_drive), (library, here)):
            marker = read_marker(root)
            assert marker is not None
            catalog.upsert_drive(uuid=marker.uuid, label=marker.label)
            for index in range(count):
                target = root / RELATIVE.format(index)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(_content(index))
                catalog.record_copy(
                    sha256=f"{index:064x}",
                    drive_uuid=marker.uuid,
                    relative=RELATIVE.format(index),
                    size=len(_content(index)),
                    copy_sha256=None,
                )
    return db, drive, library


def _preview(db: Path, drive: Path, library: Path, progress: object = None) -> dict[str, object]:
    job = service.recover_preview(drive, library, db)
    return job(progress or (lambda _p: None), threading.Event())  # type: ignore[return-value]


def _run(db: Path, drive: Path, library: Path) -> dict[str, object]:
    job = service.recover_run(drive, library, db)
    return job(lambda _p: None, threading.Event())  # type: ignore[return-value]


def _photographs(root: Path) -> list[Path]:
    return [p for p in root.rglob("*") if p.is_file() and not p.name.startswith(".")]


# ------------------------------------------------------------------------------- the preview


def test_the_preview_counts_the_gap_and_writes_nothing(tmp_path: Path) -> None:
    """8 on the drive against 5 here is 3 - and the library is untouched by asking."""
    db, drive, library = _world(tmp_path)
    before = {p: sha256_file(p) for p in _photographs(library)}
    assert before, "an empty library would make the comparison below free"

    answer = _preview(db, drive, library)

    assert answer["ok"] is True
    assert answer["count"] == 3
    assert answer["drive_walked"] is True
    assert {p: sha256_file(p) for p in _photographs(library)} == before


def test_the_preview_ships_the_reassurance_from_core(tmp_path: Path) -> None:
    """⚠ **The sentence a frightened person reads, carried as payload rather than retyped.**"""
    db, drive, library = _world(tmp_path)

    answer = _preview(db, drive, library)

    assert answer["nothing_is_lost"] == recover.NOTHING_IS_LOST
    assert answer["drive_is_read_only"] == recover.DRIVE_IS_READ_ONLY


def test_a_drive_nobody_walked_withholds_the_number(tmp_path: Path) -> None:
    """⚠ **THE WORST WRONG ANSWER, and the app can make it too.**

    A drive registered but never checked has no rows, so a naive answer is "0 to bring back" -
    said to somebody who has just lost a library, about a drive holding all of it. The payload
    carries `drive_walked=False` and core's sentence, and the screen branches on it.
    """
    db, _drive, library = _world(tmp_path)
    fresh = tmp_path / "Fresh"
    fresh.mkdir()
    (fresh / "everything.jpg").write_bytes(b"the drive is full")
    marker = create_marker(fresh, label="Never Walked")
    with Catalog(db) as catalog:
        catalog.upsert_drive(uuid=marker.uuid, label=marker.label)

    answer = _preview(db, fresh, library)

    assert answer["drive_walked"] is False
    assert answer["count"] == 0, "the raw count is zero - the SCREEN is what must not report it"
    assert answer["never_walked"] == recover.NEVER_WALKED


def test_a_walked_drive_carries_no_never_walked_sentence(tmp_path: Path) -> None:
    """The cry-wolf half. Without it the sentence could ship unconditionally and still pass."""
    db, drive, library = _world(tmp_path)

    assert _preview(db, drive, library)["never_walked"] == ""


def test_the_preview_announces_the_phase_it_is_working_in(tmp_path: Path) -> None:
    """⚠ **Against silence, which is the recorded complaint.** Time Machine's restore is faulted
    for a minute of nothing during preparation; the gap computation here stats the whole library.

    It announces rather than ticks - one blocking call inside the reused engine - so what is
    asserted is that *something* names the phase and the library, which is what the status line
    renders. A run that emitted no progress at all would leave the card silent.
    """
    db, drive, library = _world(tmp_path)
    seen: list[tuple[str, str]] = []

    _preview(db, drive, library, lambda p: seen.append((p.phase, p.item)))

    assert ("scanning", "My Library") in seen


# ----------------------------------------------------------------------------------- refusals


def test_the_same_folder_twice_is_refused_with_a_sentence(tmp_path: Path) -> None:
    db, _drive, library = _world(tmp_path)

    answer = _preview(db, library, library)

    assert answer["ok"] is False
    assert "same drive" in str(answer["error"])


def test_a_drive_that_is_not_there_is_refused(tmp_path: Path) -> None:
    """The commonest state for this question: the disk is not plugged in."""
    db, drive, library = _world(tmp_path)
    for path in sorted(drive.rglob("*"), reverse=True):
        path.unlink() if path.is_file() else path.rmdir()
    drive.rmdir()

    answer = _preview(db, drive, library)

    assert answer["ok"] is False
    assert "plugged in" in str(answer["error"])


def test_an_unregistered_folder_is_refused_rather_than_registered(tmp_path: Path) -> None:
    """`_cmd_recover`'s rule. Unlike `backup_preview`, nothing here may be OFFERED registration:
    there is nothing to recover from a folder truestill has never recorded."""
    db, _drive, library = _world(tmp_path)
    stranger = tmp_path / "NotADrive"
    stranger.mkdir()

    answer = _preview(db, stranger, library)

    assert answer["ok"] is False
    assert not (stranger / ".truestill-drive.json").exists()


# --------------------------------------------------------------------------------------- the run


def test_the_run_copies_the_gap_and_leaves_everything_else_alone(tmp_path: Path) -> None:
    """The property the whole feature rests on, asserted on digests rather than on a count."""
    db, drive, library = _world(tmp_path)
    before = {p.relative_to(library).as_posix(): sha256_file(p) for p in _photographs(library)}
    # Two empty dicts compare equal, so an empty library would make the comparison below free.
    assert before, "the fixture is empty, so 'nothing else was touched' proves nothing"

    summary = _run(db, drive, library)

    assert summary["copied"] == 3
    after = {p.relative_to(library).as_posix(): sha256_file(p) for p in _photographs(library)}
    assert {k: v for k, v in after.items() if k in before} == before
    assert summary["finished_clean"] is True
    assert summary["nothing_is_lost"] == recover.NOTHING_IS_LOST


def test_an_occupied_path_is_reported_as_a_skip_in_core_s_words(tmp_path: Path) -> None:
    """⚠ **A person who asked for three and got two must be told which rule accounts for the
    third**, or the shortfall reads as a defect. The reason sentence is core's, keyed by core."""
    db, drive, library = _world(tmp_path)
    squatter = library / RELATIVE.format(7)
    squatter.parent.mkdir(parents=True, exist_ok=True)
    squatter.write_bytes(b"something the user put here")

    summary = _run(db, drive, library)

    assert squatter.read_bytes() == b"something the user put here"
    assert summary["copied"] == 2
    assert summary["skipped"] == {recover.SKIP_REASONS[recover.Skipped.ALREADY_THERE]: 1}


def test_a_skip_does_not_make_the_run_unclean(tmp_path: Path) -> None:
    """⚠ **The split that stops the never-overwrite rule reading as a fault.**

    `jobs.py` reads `finished_clean` for the terminal status. Leaving a file alone because
    something is already at its path is the rule working; reporting it as unfinished would teach
    a user to distrust the one behaviour that makes this operation safe.
    """
    db, drive, library = _world(tmp_path)
    for index in (5, 6, 7):
        occupied = library / RELATIVE.format(index)
        occupied.parent.mkdir(parents=True, exist_ok=True)
        occupied.write_bytes(b"mine")

    summary = _run(db, drive, library)

    assert summary["copied"] == 0
    assert sum(summary["skipped"].values()) == 3  # type: ignore[union-attr]
    assert summary["failed"] == 0
    assert summary["finished_clean"] is True


def test_every_skip_class_has_a_sentence() -> None:
    """⚠ **Keyed on the enum, so a new member cannot ship unworded.** A skip that rendered as an
    empty bullet would be the product declining to say what it did."""
    assert set(recover.SKIP_REASONS) == set(recover.Skipped)
    assert all(recover.SKIP_REASONS[member].strip() for member in recover.Skipped)
