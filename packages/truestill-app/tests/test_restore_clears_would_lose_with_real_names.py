"""Prove restore against a POPULATED decisions document, and that it clears WOULD_LOSE.

The 297-byte files on real trees are empty shells. A preview that says "nothing to restore"
against one of those passes every count assertion while proving nothing about names. This file
builds a catalog with real trip / event / album / settings names, publishes them to a drive,
wipes the catalog, restores, and asserts the sections that came back. It then proves the save
path's "restore first" refusal stops after restore - the two halves agreeing on what restore means.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path

from truestill_app import service
from truestill_app.service.restore import CONFIRM_WORD
from truestill_core.catalog import Catalog
from truestill_core.decisions import (
    DECISIONS_NAME,
    SaveOutcome,
    gather_decisions,
    notice_for,
    read_decisions,
    save_decisions_to_reachable_drives,
)
from truestill_core.drive import create_marker, drive_path_hint, read_marker

_SHA_A = "a" * 64
_SHA_B = "b" * 64
_SHA_C = "c" * 64
_EVENT_SIG = "e" * 64
_STAMP = "2026-09-14T12:00:00+00:00"


def _put_file(catalog: Catalog, sha: str, *, relative: str = "Camera/2014/p.jpg") -> None:
    catalog._conn.execute(
        "INSERT INTO files (source_path, sha256, category, relative, upload_status, processed_at) "
        "VALUES (?, ?, 'image', ?, 'uploaded', datetime('now'))",
        (f"/src/{sha[:8]}.jpg", sha, relative),
    )
    catalog._conn.commit()


def _seed_named_catalog(db: Path, drive: Path) -> str:
    """A catalog with real human names, published onto ``drive``. Returns the drive uuid."""
    create_marker(drive, label="Memory Cabinet")
    marker = read_marker(drive)
    assert marker is not None
    with Catalog(db) as catalog:
        catalog.upsert_drive(uuid=marker.uuid, label=marker.label)
        catalog.set_setting(drive_path_hint(marker.uuid), str(drive.resolve()))
        catalog.set_setting("events.min_files", "3")
        _put_file(catalog, _SHA_A, relative="2014/08/14/a.jpg")
        _put_file(catalog, _SHA_B, relative="2014/08/14/b.jpg")
        _put_file(catalog, _SHA_C, relative="2015/10/25/c.jpg")
        catalog.create_trip(
            name="Wayanad",
            slug="wayanad",
            start_date="2014-08-14",
            end_date="2014-08-15",
            days=["2014-08-14", "2014-08-15"],
        )
        catalog.record_event(
            name="Morning Market",
            slug="morning-market",
            start_date="2015-10-25",
            file_count=1,
            signature=_EVENT_SIG,
        )
        catalog.record_album_members("Kerala favourites", [_SHA_A, _SHA_B])
        catalog.confirm_date(_SHA_C, "2015-10-25T09:30:00", confirmed_by="human")
        results = save_decisions_to_reachable_drives(catalog, stamp=_STAMP)
    assert results
    assert results[0].outcome is SaveOutcome.WRITTEN, results
    doc = json.loads((drive / DECISIONS_NAME).read_text(encoding="utf-8"))
    assert doc["trips"]
    assert doc["trips"][0]["name"] == "Wayanad"
    assert doc["events"]
    assert doc["events"][0]["name"] == "Morning Market"
    assert doc["albums"]
    assert doc["albums"][0]["name"] == "Kerala favourites"
    assert doc["settings"].get("events.min_files") == "3"
    assert len((drive / DECISIONS_NAME).read_bytes()) > 400, (
        "this must not be the 297-byte empty shell"
    )
    return marker.uuid


def _rebuild_inventory_without_names(db: Path, drive: Path, uuid: str) -> None:
    """Lost-catalog drill: same photographs recorded, none of the human names."""
    with Catalog(db) as catalog:
        catalog.upsert_drive(uuid=uuid, label="Memory Cabinet")
        catalog.set_setting(drive_path_hint(uuid), str(drive.resolve()))
        _put_file(catalog, _SHA_A, relative="2014/08/14/a.jpg")
        _put_file(catalog, _SHA_B, relative="2014/08/14/b.jpg")
        _put_file(catalog, _SHA_C, relative="2015/10/25/c.jpg")
        # Event row with the SAME signature but a placeholder name - the lost-catalog shape
        # `(ahz)` measured, so restore renames rather than creating.
        catalog.record_event(
            name="placeholder B",
            slug="placeholder-b",
            start_date="2015-10-25",
            file_count=1,
            signature=_EVENT_SIG,
        )


def test_populated_wipe_restore_brings_real_names_back(tmp_path: Path) -> None:
    """Build → save → wipe → preview → apply. Sections and counts must name real work."""
    drive = tmp_path / "Cabinet"
    drive.mkdir()
    rich = tmp_path / "rich.sqlite"
    uuid = _seed_named_catalog(rich, drive)
    size = (drive / DECISIONS_NAME).stat().st_size

    wiped = tmp_path / "wiped.sqlite"
    _rebuild_inventory_without_names(wiped, drive, uuid)

    with Catalog(wiped) as catalog:
        mine = gather_decisions(catalog, uuid)
        notice = notice_for(drive, mine)
    assert notice is not None
    # `settings` are deliberately absent from would_lose / awaiting_restore (UI churn per
    # machine) - but trips, events, albums and date confirmations must be offered.
    assert set(notice.awaiting_restore) >= {"trips", "albums", "date_confirmations", "events"}, (
        notice.awaiting_restore
    )

    plan = service.restore_preview(drive, wiped)
    assert plan["ok"] is True
    assert plan["restored"] >= 3, plan
    assert plan["applied"].get("trips") == 1
    assert plan["applied"].get("albums") == 1
    assert plan["applied"].get("settings") == 1
    assert "decision" in plan["summary"]
    assert str(plan["restored"]) in plan["summary"] or "decision" in plan["summary"]

    target = service.restore_run(drive, wiped, confirmation=CONFIRM_WORD)
    assert callable(target)
    summary = target(lambda _p: None, threading.Event())
    assert summary["restored"] >= 3
    assert summary["finished_clean"] is True

    with Catalog(wiped) as catalog:
        trip_names = [str(r["name"]) for r in catalog.all_trips()]
        assert "Wayanad" in trip_names
        event = catalog._conn.execute(
            "SELECT name FROM events WHERE signature = ?", (_EVENT_SIG,)
        ).fetchone()
        assert event is not None
        assert str(event["name"]) == "Morning Market"
        albums = catalog.album_members()
        assert "Kerala favourites" in albums
        assert catalog.get_setting("events.min_files") == "3"
        held = catalog.date_confirmation_for(_SHA_C)
        assert held is not None

    # Card-facing offer clears once catalog holds what the drive carried.
    with Catalog(wiped) as catalog:
        mine = gather_decisions(catalog, uuid)
        after = notice_for(drive, mine)
    assert after is not None
    assert after.awaiting_restore == (), after.awaiting_restore

    # Keep the size in the assertion message so a future empty-shell fixture fails loudly.
    assert size > 400


def test_restore_clears_would_lose_so_the_next_save_writes(tmp_path: Path) -> None:
    """Refuse → restore → save cleanly. The two halves must agree on what restore means."""
    drive = tmp_path / "Cabinet"
    drive.mkdir()
    rich = tmp_path / "rich.sqlite"
    uuid = _seed_named_catalog(rich, drive)
    before = (drive / DECISIONS_NAME).read_text(encoding="utf-8")

    # Fresh catalog that knows the drive but none of its names - the lost-machine save path.
    empty = tmp_path / "empty.sqlite"
    with Catalog(empty) as catalog:
        catalog.upsert_drive(uuid=uuid, label="Memory Cabinet")
        catalog.set_setting(drive_path_hint(uuid), str(drive.resolve()))
        # A DIFFERENT trip so the catalog is not empty-of-decisions (which can still WOULD_LOSE
        # on trips the drive holds) - same shape as test_a_document_holding_decisions_...
        catalog.create_trip(
            name="Local only",
            slug="local-only",
            start_date="2020-01-01",
            end_date="2020-01-01",
            days=["2020-01-01"],
        )
        refused = save_decisions_to_reachable_drives(catalog, stamp="2026-09-14T13:00:00+00:00")

    assert refused[0].outcome is SaveOutcome.WOULD_LOSE, refused
    assert "restore first" in refused[0].detail
    assert (drive / DECISIONS_NAME).read_text(encoding="utf-8") == before

    # Put the photographs back so albums / date confirmations can apply (inventory rebuild),
    # keeping the local-only trip that made the catalog non-empty of decisions.
    with Catalog(empty) as catalog:
        _put_file(catalog, _SHA_A, relative="2014/08/14/a.jpg")
        _put_file(catalog, _SHA_B, relative="2014/08/14/b.jpg")
        _put_file(catalog, _SHA_C, relative="2015/10/25/c.jpg")
        catalog.record_event(
            name="placeholder B",
            slug="placeholder-b",
            start_date="2015-10-25",
            file_count=1,
            signature=_EVENT_SIG,
        )
    target = service.restore_run(drive, empty, confirmation=CONFIRM_WORD)
    assert callable(target)
    applied = target(lambda _p: None, threading.Event())
    assert applied["restored"] >= 1, applied

    with Catalog(empty) as catalog:
        written = save_decisions_to_reachable_drives(catalog, stamp="2026-09-14T14:00:00+00:00")
    assert written[0].outcome is SaveOutcome.WRITTEN, (
        f"after restore the save still refused: {written[0].outcome} {written[0].detail!r}"
    )
    found = read_decisions(drive)
    assert found.decisions is not None
    trip_names = {str(t["name"]) for t in found.decisions.trips}
    assert "Wayanad" in trip_names


def test_card_payload_names_the_sections_a_populated_drive_carries(tmp_path: Path) -> None:
    """What `DriveDecisions.awaiting_restore` - the card sentence - actually lists."""
    drive = tmp_path / "Cabinet"
    drive.mkdir()
    rich = tmp_path / "rich.sqlite"
    uuid = _seed_named_catalog(rich, drive)
    wiped = tmp_path / "wiped.sqlite"
    _rebuild_inventory_without_names(wiped, drive, uuid)

    drives = service.list_drives(wiped)
    card = next(d for d in drives if d["uuid"] == uuid)
    assert card["decisions"] is not None
    awaiting = card["decisions"]["awaiting_restore"]
    assert "trips" in awaiting
    assert "albums" in awaiting
    # The screen renders: "this drive is carrying trips, albums, … this computer does not have"
    # and the Restore names button only when awaiting_restore is non-empty.
    assert awaiting
