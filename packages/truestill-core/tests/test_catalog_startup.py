"""Catalog path startup: first-run is calm; wrong-catalog is loud."""

from __future__ import annotations

from pathlib import Path

import pytest
from truestill_core.app_paths import CatalogChoice
from truestill_core.catalog import Catalog
from truestill_core.catalog_startup import (
    CatalogPresence,
    CatalogStartupInfo,
    CatalogUnusableError,
    db_flag_explicit,
    format_startup_lines,
    inspect_catalog,
    refuse_unusable_catalog,
)


def test_missing_default_is_will_create_not_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Mutation: treating missing as empty/alert would fail the tone/presence asserts."""
    monkeypatch.chdir(tmp_path)
    db = Path("reports/catalog.sqlite")
    info = inspect_catalog(db, explicit_db=False)
    assert info.presence is CatalogPresence.WILL_CREATE
    assert info.tone == "info"
    assert "No catalog yet" in info.detail
    assert "error" not in info.detail.lower()
    assert "warning" not in info.detail.lower()
    assert "fail" not in info.detail.lower()
    assert str(tmp_path / "reports" / "catalog.sqlite") == info.absolute_path
    assert not db.exists()  # inspect must not create the file
    lines = format_startup_lines(info)
    assert lines[0].startswith("Catalog: ")
    assert info.absolute_path in lines[0]
    assert any("No catalog yet" in line for line in lines)


def test_empty_default_names_absolute_path(tmp_path: Path) -> None:
    db = tmp_path / "reports" / "catalog.sqlite"
    db.parent.mkdir(parents=True)
    with Catalog(db):
        pass
    info = inspect_catalog(db, explicit_db=False)
    assert info.presence is CatalogPresence.EMPTY
    assert info.tone == "notice"
    assert info.absolute_path == str(db.resolve())
    assert "Opened empty catalog" in info.detail
    assert "--db" in info.detail or "working" in info.detail.lower()


def test_empty_while_drives_registered_is_alert(tmp_path: Path) -> None:
    db = tmp_path / "c.sqlite"
    with Catalog(db) as catalog:
        catalog.upsert_drive(uuid="drive-1", label="Cabinet")
    info = inspect_catalog(db, explicit_db=False)
    assert info.presence is CatalogPresence.EMPTY_WITH_DRIVES
    assert info.tone == "alert"
    assert info.drive_count == 1
    assert info.file_count == 0
    assert "0 files but 1 drive" in info.detail
    assert "may not be the catalog" in info.detail


def test_explicit_db_honoured_in_message(tmp_path: Path) -> None:
    db = tmp_path / "elsewhere" / "mine.sqlite"
    db.parent.mkdir(parents=True)
    with Catalog(db):
        pass
    info = inspect_catalog(db, explicit_db=True)
    assert info.presence is CatalogPresence.EMPTY
    assert info.explicit_db is True
    assert "from --db" in info.detail
    assert info.absolute_path == str(db.resolve())


def test_ready_catalog_lists_count(tmp_path: Path) -> None:
    db = tmp_path / "c.sqlite"
    with Catalog(db) as catalog:
        catalog.record_uploaded(
            source_path="/src/a.jpg",
            original_name="a.jpg",
            sha256="a" * 64,
            copy_sha256="a" * 64,
            perceptual=None,
            size=1,
            captured_at=None,
            category="Camera",
            relative="2024/a.jpg",
            event_id=None,
            albums=[],
        )
    info = inspect_catalog(db, explicit_db=True)
    assert info.presence is CatalogPresence.READY
    assert info.file_count == 1
    assert format_startup_lines(info) == [f"Catalog: {db.resolve()} (1 files)"]


def test_db_flag_explicit() -> None:
    assert db_flag_explicit(["status"]) is False
    assert db_flag_explicit(["status", "--db", "x.sqlite"]) is True
    assert db_flag_explicit(["status", "--db=x.sqlite"]) is True


def test_first_run_lines_are_not_alarmist(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    info = inspect_catalog(Path("reports/catalog.sqlite"), explicit_db=False)
    blob = "\n".join(format_startup_lines(info)).lower()
    for banned in ("error", "warning", "fail", "wrong", "missing library"):
        assert banned not in blob


def test_a_zero_byte_catalog_is_not_adopted_as_an_empty_library(tmp_path: Path) -> None:
    """THE PRIMARY GUARD for `(adr)`, and the second assertion is the load-bearing one.

    `shutil.copy2` creates the destination before it writes, so a copy that fails on a full
    disk leaves a **0-byte file wearing the catalog's name**. Today `inspect_catalog` opens it,
    `Catalog._migrate` builds the full schema into it, and it is reported as EMPTY/notice - a
    valid, empty 159,744-byte catalog now exists where a failure was. The same state arrives by
    a second route: `sqlite3.connect` creates a 0-byte file before its first write, so a process
    that dies before the schema commit leaves one too.

    **Both assertions are load-bearing, and it took two mutations to show it** - the first
    proved less than it was written to prove. `scripts/mutate_once.py`, 2026-08-18, unmutated
    control green first:

    * **the branch moved below the `Catalog` open** becomes *dead code*, because the file is
      159,744 bytes by the time it is tested, so the condition can never be true again. The
      **presence** assertion catches that; the size one never gets the chance.
    * **the `stat()` hoisted above the open and acted on below** - the plausible tidy-up, and
      the one worth guarding - reports `ZERO_BYTES` **correctly** and has already destroyed the
      file. Presence passes. Only the **size** assertion catches it.

    Neither assertion catches both mutations, which is why both are here.
    """
    db = tmp_path / "catalog.sqlite"
    db.write_bytes(b"")

    info = inspect_catalog(db, explicit_db=True)

    assert info.presence is CatalogPresence.ZERO_BYTES
    assert info.tone == "alert"
    assert db.stat().st_size == 0, (
        "inspecting a 0-byte catalog built a schema into it, so the difference between 'this "
        "copy failed' and 'you started a new library' is gone. The size check must sit BEFORE "
        "the Catalog open in inspect_catalog."
    )


def test_the_zero_byte_message_names_the_remedy_and_blames_no_file(tmp_path: Path) -> None:
    """A refusal with no way out is a brick, and this one has a specific way to be dangerous.

    `catalog_move.py` tells the user *"Check the copy, then delete the old one when you are
    happy"*. If the refusal does not say the 0-byte file is the disposable one, the instruction
    that is already on screen points at the wrong file.
    """
    db = tmp_path / "catalog.sqlite"
    db.write_bytes(b"")

    detail = inspect_catalog(db, explicit_db=True).detail

    assert "0 bytes" in detail
    assert str(db.resolve()) in detail
    assert "untouched" in detail, "the refusal must say the real library is not the file at risk"
    assert "--db" in detail, "the refusal must name a way to proceed"


def test_a_journal_beside_it_says_a_write_was_interrupted(tmp_path: Path) -> None:
    """The journal is evidence in one direction only, and the wording must match that.

    Under `journal_mode=delete` (`BACKLOG.md` (ads)) SQLite removes the rollback journal on
    commit, so one still sitting there means a write did not finish. **Its ABSENCE proves
    nothing** - a failed copy never creates one - so the message must not read the empty case as
    a diagnosis. Both directions are asserted; only asserting the present case would let the
    absent case grow a claim nobody checks.
    """
    db = tmp_path / "catalog.sqlite"
    db.write_bytes(b"")
    quiet = inspect_catalog(db, explicit_db=True).detail
    assert "interrupted" not in quiet, (
        "with no journal on disk the message claimed an interrupted write, which the evidence "
        "does not support - a failed copy leaves no journal either"
    )

    db.with_name(db.name + "-journal").write_bytes(b"")
    noisy = inspect_catalog(db, explicit_db=True).detail
    assert "catalog.sqlite-journal" in noisy

    # ⚠ **CHANGED 2026-08-22 by `(afp)`, deliberately.** A journal beside a 0-byte catalog means
    # a write did not finish - which is *"was interrupted"* AND *"has not finished yet"*, the
    # same observation for opposite situations. Measured: 2 of 6 concurrent cold starts land in
    # the second, where this file is a live catalog another process is writing. So the message no
    # longer diagnoses an interruption from evidence that does not distinguish them; it says the
    # file is still empty after the wait, which is what was actually observed.
    assert "still empty after" in noisy, (
        "the message must say what was observed - it waited and nothing changed - rather than "
        "diagnose an interruption the journal cannot tell apart from a write in progress"
    )
    assert "delete this file" not in noisy, (
        "`(afp)`: this advice is given to whoever LOST a cold-start race, and the file may be a "
        "live catalog the winner is writing"
    )


def test_a_first_run_is_untouched_by_the_zero_byte_branch(tmp_path: Path) -> None:
    """The two states are disjoint at the branch, so refusing costs a new user nothing.

    WILL_CREATE is `is_file()` being false; a 0-byte file is a file. Asserted rather than
    reasoned, because the whole argument for refusing rests on it.
    """
    db = tmp_path / "catalog.sqlite"

    info = inspect_catalog(db, explicit_db=True)

    assert info.presence is CatalogPresence.WILL_CREATE
    assert info.tone == "info"
    assert not db.exists()


def test_an_ordinary_empty_catalog_is_still_a_calm_notice(tmp_path: Path) -> None:
    """The regression in the other direction: a real empty catalog must not become a refusal."""
    db = tmp_path / "catalog.sqlite"
    with Catalog(db):
        pass
    assert db.stat().st_size > 0, "a migrated catalog is not 0 bytes; this fixture proves nothing"

    info = inspect_catalog(db, explicit_db=True)

    assert info.presence is CatalogPresence.EMPTY
    assert info.tone == "notice"


def test_refuse_unusable_catalog_raises_only_for_the_zero_byte_state(tmp_path: Path) -> None:
    """The shared helper is the enforcement point, so its exact scope is pinned.

    Every other presence is a description a surface may act on however it likes. Only
    ZERO_BYTES stops the process, and widening this would refuse a first run.
    """
    db = tmp_path / "catalog.sqlite"
    db.write_bytes(b"")
    unusable = inspect_catalog(db, explicit_db=True)
    with pytest.raises(CatalogUnusableError) as caught:
        refuse_unusable_catalog(unusable)
    assert caught.value.info is unusable
    assert str(caught.value) == unusable.detail

    for presence in CatalogPresence:
        if presence is CatalogPresence.ZERO_BYTES:
            continue
        refuse_unusable_catalog(
            CatalogStartupInfo(
                absolute_path=str(db),
                presence=presence,
                file_count=0,
                drive_count=0,
                explicit_db=True,
                tone="info",
                detail="",
            )
        )


def test_a_choice_note_is_its_own_line_and_an_empty_one_is_silent(tmp_path: Path) -> None:
    """The `CatalogChoice.note` pipe is a SEAM, not scaffolding - ruled with `(aea)`.

    Nothing sets `note` since `(adw)` retired the legacy resolution, but the rendering half
    is live code and `(abd)` - the two-catalogs disclosure - is the case that would set it.
    Pinned so the pipe cannot rot silently while it waits: a note renders as its own line,
    and an empty one adds nothing.
    """
    db = tmp_path / "catalog.sqlite"
    info = inspect_catalog(db, explicit_db=False)
    said = CatalogChoice(
        path=db, reason="default", summary="why this path won", note="the surprise"
    )
    silent = CatalogChoice(path=db, reason="default", summary="why this path won", note="")

    assert "the surprise" in format_startup_lines(info, said)
    assert format_startup_lines(info, silent) == format_startup_lines(info, said)[:-1]
