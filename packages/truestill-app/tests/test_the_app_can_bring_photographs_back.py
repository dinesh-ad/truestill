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

import sys
import threading
from pathlib import Path

import pytest
from truestill_app import service
from truestill_core import carried, recover
from truestill_core.catalog import Catalog
from truestill_core.drive import create_marker, drive_path_hint, read_marker
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


# ------------------------------------------------- what the drive card knows without being asked


def _rows(db: Path) -> dict[str, dict[str, object]]:
    return {str(row["label"]): dict(row) for row in service.list_drives(db)}


def test_the_card_names_the_library_without_being_told(tmp_path: Path) -> None:
    """⚠ **ITEM 1: the app asked for a path it already knew.**

    `LIBRARY_PATH_HINT` is written by the app's own organize flow, so on a CLI-built catalog it
    is absent and the user was asked to type the absolute path of their own library. `is_library`
    comes from `organize_runs` instead, which both organize surfaces write and neither backup nor
    recover touches - so the backup drive here is not marked even though it holds a full mirror.
    """
    db, _drive, library = _world(tmp_path)
    with Catalog(db) as catalog:
        marker = read_marker(library)
        assert marker is not None
        catalog.start_organize_run(drive_uuid=marker.uuid, run_id="r1", intended_total=5)
        catalog.finish_organize_run(marker.uuid)

    rows = _rows(db)

    assert rows["My Library"]["is_library"] is True
    assert rows["Backup Drive"]["is_library"] is False


def test_a_walked_drive_says_how_much_it_carries(tmp_path: Path) -> None:
    """⚠ **ITEM 2: the button promised something it had not checked.** 8 against 5 is 3."""
    db, _drive, library = _world(tmp_path)
    with Catalog(db) as catalog:
        marker = read_marker(library)
        assert marker is not None
        catalog.start_organize_run(drive_uuid=marker.uuid, run_id="r1", intended_total=5)

    rows = _rows(db)

    assert rows["Backup Drive"]["carried"] == 3
    assert rows["Backup Drive"]["carried_lead"] == carried.NOT_RECORDED_HERE
    # ⚠ The qualifier is ALWAYS present beside the number - it is what makes the count safe to
    # print, not an advanced detail - and the full sentence is reachable rather than hidden.
    assert rows["Backup Drive"]["carried_short"] == carried.FROM_RECORDS_SHORT
    assert rows["Backup Drive"]["carried_full"] == carried.FROM_RECORDS


def test_a_drive_carrying_nothing_extra_says_so_rather_than_showing_three(
    tmp_path: Path,
) -> None:
    """A drive whose every copy is already here gets `0` and core's sentence - not a number the
    card would dress up as an offer."""
    db, _drive, library = _world(tmp_path, on_drive=5, here=5)
    with Catalog(db) as catalog:
        marker = read_marker(library)
        assert marker is not None
        catalog.start_organize_run(drive_uuid=marker.uuid, run_id="r1", intended_total=5)

    rows = _rows(db)

    assert rows["Backup Drive"]["carried"] == 0
    assert rows["Backup Drive"]["carried_lead"] == carried.CARRIES_NOTHING_EXTRA
    assert rows["Backup Drive"]["carried_short"] == carried.FROM_RECORDS_SHORT


def test_a_drive_nobody_walked_carries_no_number_at_all(tmp_path: Path) -> None:
    """⚠ **THE WORST WRONG ANSWER ON A CARD.** `drives --init` writes a marker and does not walk,
    so a drive holding a whole library has no rows. `carried` is `None`, never `0`, and the note
    says it was not checked - because a `0` here tells somebody who has just lost a library that
    their backup holds nothing."""
    db, _drive, library = _world(tmp_path)
    fresh = tmp_path / "Fresh"
    fresh.mkdir()
    (fresh / "everything.jpg").write_bytes(b"the drive is full")
    marker = create_marker(fresh, label="Never Walked")
    with Catalog(db) as catalog:
        catalog.upsert_drive(uuid=marker.uuid, label=marker.label)
        here = read_marker(library)
        assert here is not None
        catalog.start_organize_run(drive_uuid=here.uuid, run_id="r1", intended_total=5)

    row = _rows(db)["Never Walked"]

    assert row["carried"] is None
    assert row["carried_lead"] == carried.NOT_WALKED_YET
    assert row["carried_full"] == carried.NOT_WALKED_FULL


def test_with_two_libraries_no_card_claims_a_number(tmp_path: Path) -> None:
    """⚠ **An ambiguous answer is not resolved by guessing.** Two organize destinations means the
    gap has no single subject, so every card says nothing rather than being measured against a
    library picked arbitrarily - which would be right on one machine and wrong on another."""
    db, drive, library = _world(tmp_path)
    with Catalog(db) as catalog:
        for root in (library, drive):
            marker = read_marker(root)
            assert marker is not None
            catalog.start_organize_run(
                drive_uuid=marker.uuid, run_id=f"r-{marker.uuid}", intended_total=1
            )

    rows = _rows(db)

    # `all()` over an empty dict is True, so the population is pinned before it is judged.
    assert len(rows) == 2, "the fixture is not the shape this test is about"
    assert all(row["carried"] is None for row in rows.values())
    assert all(row["carried_lead"] == "" for row in rows.values())
    # ⚠ **It says WHY, and names the remedy - ONCE.** Refusing to guess was right; going blank
    # was not. The sentence is a fact about the catalog, so it rides the payload root rather than
    # repeating 148 characters on every card.
    assert service.cannot_name_library(db) == carried.TWO_LIBRARIES
    assert "Settings" in carried.TWO_LIBRARIES


def test_the_note_never_travels_without_the_number_or_the_other_way(tmp_path: Path) -> None:
    """⚠ **The pair is the contract.** A count with no note reads as a fact about bytes; a note
    with no count says nothing. Asserted across every state this fixture can produce."""
    db, _drive, library = _world(tmp_path)
    with Catalog(db) as catalog:
        marker = read_marker(library)
        assert marker is not None
        catalog.start_organize_run(drive_uuid=marker.uuid, run_id="r1", intended_total=5)

    rows = _rows(db)

    judged = {label: row for label, row in rows.items() if not row["is_library"]}
    assert judged, "every drive is the library, so the loop below is free"
    for label, row in judged.items():
        # Words always. Which words is the count's business; having some is the contract.
        assert row["carried_lead"] or row["carried_full"], f"{label} has a state and no words"
        # And the two states that share the value `None` are told apart by the lead.
        assert (row["carried"] is None) == (row["carried_lead"] == carried.NOT_WALKED_YET), label
        # ⚠ A number never travels without the qualifier that says where it came from.
        if row["carried"]:
            assert row["carried_short"] == carried.FROM_RECORDS_SHORT, label


def test_saying_which_folder_is_the_library_resolves_the_ambiguity(tmp_path: Path) -> None:
    """⚠ **THE REMEDY THE SENTENCE NAMES, AND IT IS CHECKED RATHER THAN ASSERTED IN PROSE.**

    Saying "Settings, under 'Where your library lives'" would be a lie if the control were gated
    on a first run - the state this sentence appears in has files, so a first-run-only control
    would leave the user reading an instruction they cannot follow. `set_library_root` writes
    `library.root` unconditionally, and the payload prefers it over counting organize runs.

    So: two libraries, cards blank and explained; declare one; cards work again.
    """
    db, drive, library = _world(tmp_path)
    with Catalog(db) as catalog:
        for root in (library, drive):
            marker = read_marker(root)
            assert marker is not None
            catalog.start_organize_run(
                drive_uuid=marker.uuid, run_id=f"r-{marker.uuid}", intended_total=1
            )
            catalog.set_setting(drive_path_hint(marker.uuid), str(root))
    assert service.cannot_name_library(db) == carried.TWO_LIBRARIES

    service.set_library_root(str(library), db)

    rows = _rows(db)
    assert rows["My Library"]["is_library"] is True
    assert rows["Backup Drive"]["carried"] == 3, "the declared library did not settle it"
    assert rows["Backup Drive"]["carried_short"] == carried.FROM_RECORDS_SHORT
    assert service.cannot_name_library(db) == "", "the sentence outlived the ambiguity"


@pytest.mark.skipif(sys.platform == "win32", reason="a directory symlink needs a Windows privilege")
def test_a_library_declared_by_its_other_spelling_still_settles_the_ambiguity(
    tmp_path: Path,
) -> None:
    """⚠ **THE DEFECT THIS TURN EXISTS FOR, AND IT WAS LIVE ON THE MAINTAINER'S MACHINE.**

    `/home/dinesh/TruestillLibrary` is a symlink to `/data/TruestillLibrary`. The declared root
    and the remembered drive hint are two things a person types at different times, so they are
    routinely two spellings of one folder - and a string compare ignored the user's explicit
    declaration, leaving every card blank with the two-libraries sentence they had just answered.
    """
    db, drive, library = _world(tmp_path)
    link = tmp_path / "home-TruestillLibrary"
    link.symlink_to(library)
    with Catalog(db) as catalog:
        for root in (library, drive):
            marker = read_marker(root)
            assert marker is not None
            catalog.start_organize_run(
                drive_uuid=marker.uuid, run_id=f"r-{marker.uuid}", intended_total=1
            )
            catalog.set_setting(drive_path_hint(marker.uuid), str(root))
    assert service.cannot_name_library(db) == carried.TWO_LIBRARIES

    # The hint records the real path; the user declares the symlinked one. One folder.
    service.set_library_root(str(link), db)

    assert str(link) != str(library), "the two spellings are identical; this proves nothing"
    assert service.cannot_name_library(db) == "", "the declaration was ignored"
    assert _rows(db)["Backup Drive"]["carried"] == 3
