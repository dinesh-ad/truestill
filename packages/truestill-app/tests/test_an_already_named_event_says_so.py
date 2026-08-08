"""An event already named must say so - and a cluster that merely overlaps one must not.

**"Already named" is two questions wearing one phrase**, because an event's identity is its
membership: `EventCandidate.signature` is a SHA-256 over its sorted member SHA-256s, and
`events.signature` is the UNIQUE key `event_by_signature` looks up.

* **Same signature** - the identical set of files, already named. `commit_catalog` takes the
  existing row's id and never reads ``decision.name``, so a name typed here is discarded exactly
  as it was for trips before ``3ffb8d5``. The card must show the name and invite nothing.
* **Different signature** - membership changed, so this is a NEW object that merely overlaps
  something named. It is not that event. Inviting a name is correct here, and suppressing it
  would silence a genuinely new cluster.

Collapsing the two either silences new clusters or claims named-ness for something that is not
named. Both are pinned below, and the behaviour differs between them: that difference IS the
feature, not an edge case of it.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from truestill_app.service.trips import propose_events, proposed_review_cards_payload
from truestill_core.catalog import Catalog
from truestill_core.drive import create_marker
from truestill_core.event_review import EventDecision, commit_catalog, propose_from_catalog

_START = datetime(2026, 3, 4, 10, 0)
_NAME = "Sivaram's Farewell"


def _drive_with_one_cluster(tmp_path: Path, count: int = 15) -> tuple[Path, Path, str]:
    root = tmp_path / "drive"
    root.mkdir()
    marker = create_marker(root, label="Backup A")
    db = tmp_path / "c.sqlite"
    with Catalog(db) as catalog:
        catalog.upsert_drive(uuid=marker.uuid, label=marker.label)
        _add_photos(catalog, marker.uuid, range(count))
    return root, db, marker.uuid


def _add_photos(catalog: Catalog, drive_uuid: str, indices: range) -> None:
    for index in indices:
        sha = f"sha{index:03d}"
        catalog.record_uploaded(
            source_path=f"/src/{sha}.jpg",
            original_name=f"{sha}.jpg",
            sha256=sha,
            copy_sha256=sha,
            perceptual=None,
            size=1000,
            captured_at=(_START + timedelta(minutes=index)).isoformat(),
            category="Camera",
            relative=f"2026/2026-03/{sha}.jpg",
            drive_uuid=drive_uuid,
        )


def _name_the_only_cluster(db: Path, drive_uuid: str, name: str = _NAME) -> str:
    """Name it, and return the signature that naming recorded."""
    with Catalog(db) as catalog:
        clusters = propose_from_catalog(catalog, drive_uuid)
        assert len(clusters) == 1, f"fixture expects one cluster, got {len(clusters)}"
        signature = clusters[0].signature
        assert commit_catalog(catalog, [EventDecision(clusters[0], name)]) == 1
    return signature


def _event_card(root: Path, db: Path) -> dict:
    proposal = propose_events(root, db)
    assert proposal["ok"] is True
    payload = proposed_review_cards_payload("sess", proposal)
    cards = [card for card in payload["cards"] if card["kind"] == "event"]
    assert len(cards) == 1, f"expected one event card, got {len(cards)}"
    return dict(cards[0])


def test_the_same_files_named_before_come_back_carrying_that_name(tmp_path: Path) -> None:
    """CASE ONE, and the defect: identical membership, already named, still asked."""
    root, db, uuid = _drive_with_one_cluster(tmp_path)
    _name_the_only_cluster(db, uuid)

    card = _event_card(root, db)

    assert card["existing_name"] == _NAME, (
        "an event whose exact membership is already named came back with no name, so the screen "
        "offers a box for an answer `commit_catalog` will discard"
    )


def test_a_cluster_that_grew_is_a_new_event_and_is_still_asked(tmp_path: Path) -> None:
    """CASE TWO, and the one that stops the fix over-claiming.

    One more photo joins the cluster, so its signature changes and `event_by_signature` finds
    nothing. This is a different object that overlaps a named one - not that event. It must still
    be invited to be named, or a fix for case one silences every cluster that ever grew.
    """
    root, db, uuid = _drive_with_one_cluster(tmp_path)
    before = _name_the_only_cluster(db, uuid)

    with Catalog(db) as catalog:
        # One minute after the last member, so it JOINS the cluster rather than starting its own.
        # Placing it 85 minutes later instead put it past `MAX_WITHIN_EVENT_GAP_S` and produced a
        # second cluster, leaving the first one's signature unchanged - the fixture guard below
        # is what caught that, and it stays for the next person who moves this number.
        _add_photos(catalog, uuid, range(15, 16))
        after = propose_from_catalog(catalog, uuid)[0].signature
    assert after != before, "fixture failed to change membership; the two cases are not distinct"

    card = _event_card(root, db)

    assert card["existing_name"] is None, (
        "a cluster whose membership changed was reported as already named; it merely overlaps "
        "one, and claiming otherwise hides a genuinely un-named group of photos"
    )


def test_an_event_nobody_has_named_is_asked_as_before(tmp_path: Path) -> None:
    """The plain cry-wolf half: nothing named at all, so nothing may claim a name."""
    root, db, _uuid = _drive_with_one_cluster(tmp_path)

    assert _event_card(root, db)["existing_name"] is None


def test_naming_one_event_does_not_mark_an_unrelated_one(tmp_path: Path) -> None:
    """The lookup is keyed on THIS card's signature, not on 'some event is named'."""
    root, db, _uuid = _drive_with_one_cluster(tmp_path)
    with Catalog(db) as catalog:
        catalog.record_event(
            name="Somewhere Else",
            slug="somewhere-else",
            start_date="2013-09-15",
            file_count=9,
            signature="a-signature-no-cluster-here-has",
        )

    assert _event_card(root, db)["existing_name"] is None
