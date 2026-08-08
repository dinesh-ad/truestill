"""A card with no name yet arrives carrying a suggestion drawn from its own source folders.

**Its own field.** Not ``name`` - that is the browser's store for what the USER typed
(`syncEvNamesFromDom`, carried across merge/split by `takeEvNamesByKey`) - and not
``existing_name``, which answers a different question. Three meanings, three fields.

**Gated on ``existing_name is None``**, which is a real check on both card kinds since `d7c6bfc`:
a trip is looked up by its claimed day, an event by its membership signature.

**A trip card has no member identities at all.** `TripProposal` carries `start_date`, `end_date`
and `days: Mapping[date, int]` - counts, not SHA-256s - so its members are derived by DATE from
the days it claims. That is the day-claim rule (`trip-grouping-research.md` §2), not a new one,
and it is the path most likely to be quietly wrong: an event card can read `card.event.items` and
a trip card has nothing to read.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from truestill_app.service.trips import propose_events, proposed_review_cards_payload
from truestill_core.catalog import Catalog
from truestill_core.drive import create_marker
from truestill_core.event_review import EventDecision, commit_catalog, propose_from_catalog

_START = datetime(2026, 3, 4, 10, 0)


def _drive(tmp_path: Path) -> tuple[Path, Path, str]:
    root = tmp_path / "drive"
    root.mkdir()
    marker = create_marker(root, label="Backup A")
    return root, tmp_path / "c.sqlite", marker.uuid


def _add(catalog: Catalog, uuid: str, folder: str, day: int, count: int, first: int = 0) -> None:
    for index in range(first, first + count):
        sha = f"sha{day:02d}{index:03d}"
        catalog.record_uploaded(
            source_path=f"/src/{folder}/{sha}.jpg",
            original_name=f"{sha}.jpg",
            sha256=sha,
            copy_sha256=sha,
            perceptual=None,
            size=1000,
            captured_at=(_START + timedelta(days=day, minutes=index)).isoformat(),
            category="Camera",
            relative=f"2026/2026-03/{sha}.jpg",
            drive_uuid=uuid,
        )


def _cards(root: Path, db: Path) -> list[dict]:
    proposal = propose_events(root, db)
    assert proposal["ok"] is True
    return [dict(card) for card in proposed_review_cards_payload("s", proposal)["cards"]]


def _one(root: Path, db: Path, kind: str) -> dict:
    cards = [card for card in _cards(root, db) if card["kind"] == kind]
    assert len(cards) == 1, f"expected one {kind} card, got {len(cards)}"
    return cards[0]


def test_an_event_card_suggests_the_folder_its_members_came_from(tmp_path: Path) -> None:
    root, db, uuid = _drive(tmp_path)
    with Catalog(db) as catalog:
        catalog.upsert_drive(uuid=uuid, label="Backup A")
        _add(catalog, uuid, "Sea Diving", day=0, count=15)

    assert _one(root, db, "event")["suggested_name"] == "Sea Diving"


def test_a_trip_card_derives_its_members_from_the_days_it_claims(tmp_path: Path) -> None:
    """THE PATH WITH NOTHING TO READ. `TripProposal` holds day counts, never member SHA-256s.

    Four consecutive days under one folder. If the derivation were wrong - wrong drive, wrong
    days, or members silently empty - the suggester would see nothing and answer silence, so a
    plain `is not None` here is doing real work.
    """
    root, db, uuid = _drive(tmp_path)
    with Catalog(db) as catalog:
        catalog.upsert_drive(uuid=uuid, label="Backup A")
        for day in range(4):
            _add(catalog, uuid, "Wayanad '26", day=day, count=12)

    card = _one(root, db, "trip")
    assert card["active_days"] == 4
    assert card["suggested_name"] == "Wayanad"  # the year is stripped: the tree carries it


def test_a_trip_takes_only_its_own_days_not_the_whole_drive(tmp_path: Path) -> None:
    """The day filter is the whole derivation. Photos outside the claimed run must not vote."""
    root, db, uuid = _drive(tmp_path)
    with Catalog(db) as catalog:
        catalog.upsert_drive(uuid=uuid, label="Backup A")
        for day in range(4):
            _add(catalog, uuid, "Wayanad", day=day, count=12)
        # A separate, much larger day far away. It clusters on its own and must not drown the
        # trip's own folder if the trip ever read more than its claimed days.
        _add(catalog, uuid, "Somewhere Else", day=40, count=60)

    assert _one(root, db, "trip")["suggested_name"] == "Wayanad"


def test_a_card_that_already_has_a_name_is_never_suggested_to(tmp_path: Path) -> None:
    """THE GATE. A suggestion on an already-named card would offer a confident answer for a
    question `commit_catalog` discards - the §9 shape two earlier commits removed."""
    root, db, uuid = _drive(tmp_path)
    with Catalog(db) as catalog:
        catalog.upsert_drive(uuid=uuid, label="Backup A")
        _add(catalog, uuid, "Sea Diving", day=0, count=15)
    with Catalog(db) as catalog:
        clusters = propose_from_catalog(catalog, uuid)
        commit_catalog(catalog, [EventDecision(clusters[0], "Named By Hand")])

    card = _one(root, db, "event")
    assert card["existing_name"] == "Named By Hand"
    assert card["suggested_name"] is None


def test_the_same_name_on_several_cards_in_one_day_is_suggested_on_all_of_them(
    tmp_path: Path,
) -> None:
    """The maintainer's decision, kept honest. Suppressing a repeated suggestion would hide the
    strongest evidence the rule produces: the collision comes from clustering splitting one day,
    not from the suggestion, and a user facing blank cards types the same name by hand anyway.
    """
    root, db, uuid = _drive(tmp_path)
    with Catalog(db) as catalog:
        catalog.upsert_drive(uuid=uuid, label="Backup A")
        _add(catalog, uuid, "Gokul Marriage", day=0, count=12)
        # Same day, hours later, so it clusters separately but shares the source folder.
        for index in range(12):
            sha = f"late{index:03d}"
            catalog.record_uploaded(
                source_path=f"/src/Gokul Marriage/{sha}.jpg",
                original_name=f"{sha}.jpg",
                sha256=sha,
                copy_sha256=sha,
                perceptual=None,
                size=1000,
                captured_at=(_START + timedelta(hours=9, minutes=index)).isoformat(),
                category="Camera",
                relative=f"2026/2026-03/{sha}.jpg",
                drive_uuid=uuid,
            )

    events = [card for card in _cards(root, db) if card["kind"] == "event"]
    assert len(events) == 2, "fixture failed to split one day into two clusters"
    assert [card["suggested_name"] for card in events] == ["Gokul Marriage"] * 2


def test_a_drive_whose_folders_say_nothing_is_silent(tmp_path: Path) -> None:
    """Silence is the correct output, and it must reach the payload as None rather than absent."""
    root, db, uuid = _drive(tmp_path)
    with Catalog(db) as catalog:
        catalog.upsert_drive(uuid=uuid, label="Backup A")
        _add(catalog, uuid, "DCIM", day=0, count=15)

    card = _one(root, db, "event")
    assert "suggested_name" in card
    assert card["suggested_name"] is None
