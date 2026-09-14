"""The restore surface: decisions document → catalog. Not photographs (that is recover).

Confirm is checked in ``restore_run`` (`(ahe)`), against core's ``CONFIRM_WORD``. Preview writes
nothing; apply writes catalog rows and a run record with ``kind="restore"``.
"""

from __future__ import annotations

import threading
from pathlib import Path

from truestill_app import service
from truestill_app.service.restore import CONFIRM_WORD, NOT_CONFIRMED
from truestill_core.app_paths import run_index_for
from truestill_core.catalog import Catalog
from truestill_core.decisions import Decisions, write_decisions
from truestill_core.drive import create_marker, read_marker

_TRIP = {
    "name": "Wayanad",
    "slug": "wayanad",
    "start": "2020-01-15",
    "end": "2020-01-16",
    "days": ["2020-01-15", "2020-01-16"],
}


def _world(tmp_path: Path) -> tuple[Path, Path]:
    db = tmp_path / "c.sqlite"
    drive = tmp_path / "Backup"
    drive.mkdir()
    create_marker(drive, label="Backup Drive")
    marker = read_marker(drive)
    assert marker is not None
    with Catalog(db) as catalog:
        catalog.upsert_drive(uuid=marker.uuid, label=marker.label)
    write_decisions(
        drive,
        Decisions(
            drive_uuid=marker.uuid,
            drive_label=marker.label,
            trips=(_TRIP,),
            settings={"events.min_files": "3"},
        ),
    )
    return db, drive


def test_preview_reports_both_halves_and_writes_nothing(tmp_path: Path) -> None:
    db, drive = _world(tmp_path)
    before = (drive / ".truestill-decisions.json").read_text(encoding="utf-8")
    plan = service.restore_preview(drive, db)
    assert plan["ok"] is True
    assert plan["restored"] >= 1
    assert "decision" in plan["summary"]
    assert plan["confirm_word"] == CONFIRM_WORD
    assert (drive / ".truestill-decisions.json").read_text(encoding="utf-8") == before
    with Catalog(db) as catalog:
        assert catalog.all_trips() == []


def test_run_refuses_without_the_typed_word(tmp_path: Path) -> None:
    db, drive = _world(tmp_path)
    refused = service.restore_run(drive, db, confirmation="")
    assert isinstance(refused, dict)
    assert refused["code"] == NOT_CONFIRMED
    refused_wrong = service.restore_run(drive, db, confirmation="yes")
    assert isinstance(refused_wrong, dict)
    assert refused_wrong["code"] == NOT_CONFIRMED


def test_run_applies_names_and_writes_a_run_record(tmp_path: Path) -> None:
    db, drive = _world(tmp_path)
    target = service.restore_run(drive, db, confirmation=CONFIRM_WORD)
    assert callable(target)
    summary = target(lambda _p: None, threading.Event())
    assert summary["restored"] >= 1
    assert summary["finished_clean"] is True
    with Catalog(db) as catalog:
        names = [str(r["name"]) for r in catalog.all_trips()]
        assert "Wayanad" in names
        assert catalog.get_setting("events.min_files") == "3"
    index = run_index_for(db)
    assert index.is_file()
    assert "restore" in index.read_text(encoding="utf-8")


def test_conflict_lines_are_actionable_when_trips_clash(tmp_path: Path) -> None:
    db, drive = _world(tmp_path)
    with Catalog(db) as catalog:
        catalog.create_trip(
            name="Other trip",
            slug="other",
            start_date="2020-01-15",
            end_date="2020-01-15",
            days=["2020-01-15"],
        )
    plan = service.restore_preview(drive, db)
    assert plan["ok"] is True
    actionable = [line for line in plan["lines"] if line["actionable"]]
    assert actionable, "a conflicting trip must surface as an actionable banner line"
    assert any("could not be applied" in line["text"] for line in actionable)
