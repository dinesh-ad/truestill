"""What the drive card knows about the decisions on each drive.

**Job 1b's gap closes here.** The save has recorded `decisions.problem.<uuid>` since `c5f36ff`
and the app has been silent about it by agreement - a failed or refused save was invisible on the
one screen that shows drives. No new plumbing was needed: the data was already being written.

**Two kinds of fact, two rules, and the card already draws the line.** `last_verified` and
`last_seen` are facts about what Truestill DID - recorded here, and legitimately shown for a
drive that is not plugged in. The decisions date is a fact about WHAT IS ON THE DRIVE, and the
drive is the only authority for it, so it is read when the drive is here and simply absent when
it is not. Caching it would be the stored second representation this project has now rejected
three times.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from truestill_app.service import drives as drives_module
from truestill_app.service.drives import list_drives
from truestill_core.catalog import Catalog
from truestill_core.catalog_session import problem_key
from truestill_core.decisions import (
    DECISIONS_NAME,
    DECISIONS_SAVED_AT_KEY,
    Decisions,
    write_decisions,
)
from truestill_core.drive import create_marker, drive_path_hint

_TRIP = {
    "name": "Wayanad",
    "slug": "wayanad",
    "start": "2014-08-14",
    "end": "2014-08-14",
    "days": ["2014-08-14"],
}
_WRITTEN = "2026-08-09T12:00:00+00:00"


def _registered(tmp_path: Path, db: Path, *, connected: bool = True) -> str:
    root = tmp_path / "drive"
    root.mkdir(exist_ok=True)
    marker = create_marker(root, "Output")
    with Catalog(db) as catalog:
        catalog.upsert_drive(uuid=marker.uuid, label="Output")
        if connected:
            catalog.set_setting(drive_path_hint(marker.uuid), str(root))
        # The FIRST catalog open of a catalog that predates this feature writes its decisions to
        # every reachable drive - see `ensure_decisions_on_drives`. `list_drives` opens the
        # catalog, so without this every test here would measure the card against a document the
        # act of rendering the card had just rewritten. Pinned as behaviour by
        # `test_the_first_listing_after_upgrade_refreshes_the_drive` below.
        catalog.set_setting(DECISIONS_SAVED_AT_KEY, "2026-08-01T00:00:00+00:00")
    return marker.uuid


def _only(db: Path) -> dict:
    rows = list_drives(db)
    assert len(rows) == 1
    return dict(rows[0])


def test_the_card_carries_the_date_the_drive_says_it_was_saved(tmp_path: Path) -> None:
    """ "Decisions saved here 9 August" is the whole lesson from the Adobe threads: obvious that
    it exists, obvious how old it is. Read from the drive, never stored."""
    db = tmp_path / "c.sqlite"
    _registered(tmp_path, db)
    write_decisions(tmp_path / "drive", Decisions(written=_WRITTEN, trips=(_TRIP,)))
    with Catalog(db) as catalog:
        catalog.create_trip(
            name="Wayanad",
            slug="wayanad",
            start_date="2014-08-14",
            end_date="2014-08-14",
            days=["2014-08-14"],
        )

    decisions = _only(db)["decisions"]

    assert decisions["saved_at"] == _WRITTEN
    assert decisions["stale"] == []
    assert decisions["awaiting_restore"] == []


def test_a_drive_missing_what_this_catalog_has_is_reported_stale(tmp_path: Path) -> None:
    """The line that says the copy is behind, computed by comparing copies rather than clocks."""
    db = tmp_path / "c.sqlite"
    _registered(tmp_path, db)
    write_decisions(tmp_path / "drive", Decisions(written=_WRITTEN))
    with Catalog(db) as catalog:
        catalog.create_trip(
            name="Wayanad",
            slug="wayanad",
            start_date="2014-08-14",
            end_date="2014-08-14",
            days=["2014-08-14"],
        )

    assert _only(db)["decisions"]["stale"] == ["trips"]


def test_a_failed_save_finally_reaches_the_screen(tmp_path: Path) -> None:
    """JOB 1B'S GAP. The save has been recording this since c5f36ff and nothing showed it."""
    db = tmp_path / "c.sqlite"
    uuid = _registered(tmp_path, db)
    write_decisions(tmp_path / "drive", Decisions(written=_WRITTEN))
    with Catalog(db) as catalog:
        catalog.set_setting(
            problem_key(uuid), "the drive is read-only, or this account cannot write to it"
        )

    assert "read-only" in _only(db)["decisions"]["problem"]


def test_a_problem_is_shown_even_when_the_drive_is_not_plugged_in(tmp_path: Path) -> None:
    """A recorded failure is a fact about what Truestill DID, like `last_verified` - so it
    survives the drive being unplugged. The date is not, and the test below is its opposite."""
    db = tmp_path / "c.sqlite"
    uuid = _registered(tmp_path, db, connected=False)
    with Catalog(db) as catalog:
        catalog.set_setting(problem_key(uuid), "there is no space left on the drive")

    decisions = _only(db)["decisions"]
    assert "no space" in decisions["problem"]
    assert decisions["saved_at"] is None, "a date was reported for a drive nobody could read"


def test_an_unreachable_drive_reports_no_date_rather_than_a_remembered_one(
    tmp_path: Path,
) -> None:
    """THE DISTINCTION, PINNED. The drive is the only authority for what is written on it, so a
    card that cannot reach it says nothing rather than showing the last thing it knew. A cached
    value would be a second representation of a fact the drive owns - rejected here for the same
    reason the duplicate `trip_days` map was."""
    db = tmp_path / "c.sqlite"
    _registered(tmp_path, db, connected=False)
    write_decisions(tmp_path / "drive", Decisions(written=_WRITTEN, trips=(_TRIP,)))

    row = _only(db)
    assert row["reach"] != "connected"
    assert row["decisions"] is None


def test_a_drive_with_no_document_says_nothing_at_all(tmp_path: Path) -> None:
    """Most drives are not carrying decisions yet. Silence, not a line about the absence."""
    db = tmp_path / "c.sqlite"
    _registered(tmp_path, db)

    assert _only(db)["decisions"] is None


def test_the_refusal_is_the_one_from_core_rather_than_the_screen_s_own_words(
    tmp_path: Path,
) -> None:
    """One wording, three places. A screen that paraphrases it is a fourth dialect, and this is
    the message a mid-crisis user reads."""
    db = tmp_path / "c.sqlite"
    _registered(tmp_path, db)
    (tmp_path / "drive" / DECISIONS_NAME).write_text(json.dumps({"format": 9}), encoding="utf-8")

    refusal = _only(db)["decisions"]["refusal"]

    assert refusal is not None
    lines = refusal.splitlines()
    assert next(i for i, x in enumerate(lines) if "safe" in x.lower()) < next(
        i for i, x in enumerate(lines) if "cannot use" in x.lower()
    )
    assert "truestill restore" in refusal


def test_the_first_listing_after_upgrade_refreshes_the_drive(tmp_path: Path) -> None:
    """A REAL INTERACTION, found by these tests failing for a reason that was not their own.

    Opening the drive screen opens the catalog, and the first open of a catalog that predates
    this feature writes its decisions to every reachable drive. So the very first card a user
    sees after upgrading says "saved just now" - which is the upgrade write doing exactly its
    job, and is why every other test here takes it out of the picture rather than working around
    it.
    """
    db = tmp_path / "c.sqlite"
    root = tmp_path / "drive"
    root.mkdir()
    marker = create_marker(root, "Output")
    with Catalog(db) as catalog:  # no DECISIONS_SAVED_AT_KEY: this catalog predates the feature
        catalog.upsert_drive(uuid=marker.uuid, label="Output")
        catalog.set_setting(drive_path_hint(marker.uuid), str(root))
        catalog.create_trip(
            name="Wayanad",
            slug="wayanad",
            start_date="2014-08-14",
            end_date="2014-08-14",
            days=["2014-08-14"],
        )
    assert not (root / DECISIONS_NAME).exists()

    decisions = _only(db)["decisions"]

    assert decisions is not None
    assert decisions["stale"] == [], "the drive was not brought up to date by the first listing"
    assert (root / DECISIONS_NAME).exists()


def test_the_catalog_is_gathered_once_however_many_drives_are_connected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A PERFORMANCE CLAIM NOTHING ENFORCED until a mutation moved the gather inside the loop and
    killed no test. Ten connected drives must cost one catalog read, not ten - and the obvious
    wiring, resolving it per drive, looks identical from the outside.
    """
    db = tmp_path / "c.sqlite"
    with Catalog(db) as catalog:
        catalog.set_setting(DECISIONS_SAVED_AT_KEY, "2026-08-01T00:00:00+00:00")
        for n in (1, 2):
            root = tmp_path / f"drive{n}"
            root.mkdir()
            marker = create_marker(root, f"Drive {n}")
            write_decisions(root, Decisions(written=_WRITTEN))
            catalog.upsert_drive(uuid=marker.uuid, label=f"Drive {n}")
            catalog.set_setting(drive_path_hint(marker.uuid), str(root))

    calls = 0
    real = drives_module.gather_decisions

    def counted(*args: object, **kwargs: object) -> object:
        nonlocal calls
        calls += 1
        return real(*args, **kwargs)

    monkeypatch.setattr(drives_module, "gather_decisions", counted)
    rows = list_drives(db)

    assert len(rows) == 2
    assert calls == 1, f"the catalog was gathered {calls} times for 2 drives"


def test_an_offline_drive_is_never_handed_a_root_to_read(tmp_path: Path) -> None:
    """The guard is that an unreachable drive gets no path, and this aims at THAT rather than at
    the absent date - a listing of only offline drives never gathers the catalog either, so a
    test on the date alone passes for the wrong reason.
    """
    db = tmp_path / "c.sqlite"
    root = tmp_path / "drive"
    root.mkdir()
    marker = create_marker(root, "Output")
    write_decisions(root, Decisions(written=_WRITTEN, trips=(_TRIP,)))
    with Catalog(db) as catalog:
        catalog.set_setting(DECISIONS_SAVED_AT_KEY, "2026-08-01T00:00:00+00:00")
        catalog.upsert_drive(uuid=marker.uuid, label="Output")
        catalog.set_setting(drive_path_hint(marker.uuid), str(root))
        # A second drive keeps the catalog gather alive, so the offline one is not spared by the
        # laziness rather than by the rule under test.
        other = tmp_path / "other"
        other.mkdir()
        second = create_marker(other, "Other")
        write_decisions(other, Decisions(written=_WRITTEN))
        catalog.upsert_drive(uuid=second.uuid, label="Other")
        catalog.set_setting(drive_path_hint(second.uuid), str(other))
    (root / ".truestill-drive.json").unlink()  # unplugged: the marker is what makes it reachable

    rows = {r["label"]: r for r in list_drives(db)}

    assert rows["Output"]["reach"] != "connected"
    assert rows["Output"]["path"] is None
    assert rows["Output"]["decisions"] is None
    assert rows["Other"]["decisions"] is not None, "the reachable drive was not read either"
