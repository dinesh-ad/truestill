"""A trip that already has a name must arrive at the screen carrying it.

**The defect.** `trip_review.assemble_trip_review` never consults :meth:`Catalog.trip_for_day` -
its ``claimed_days`` set means "claimed by a proposal in THIS run", not "claimed by a trip the
catalog already holds". So an already-named trip is re-offered on every visit, and
``ReviewCardPayload`` carried no name for the screen to show it with, leaving an empty box that
reads exactly like an unnamed card.

**Why an empty box is worse than a cosmetic slip.** `commit_trips` ignores a name on the
already-claimed branch (recorded as an open item; the invariant that ignores it is deliberate and
pinned by `test_re_ingest_one_photo_into_a_named_trip_does_not_re_ask`). So the screen invited an
answer it would discard without a word - a question asked and the reply thrown away while
reporting success (§9 never-silent). Carrying the name is what lets the screen stop asking.

The name travels on the payload rather than being looked up by the browser: the screen already
has a ``c.name`` branch (`app.js`) that has never had a value to render, and a second source of
truth for "is this named" is how the two drift.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from truestill_app.service.trips import propose_events, proposed_review_cards_payload
from truestill_core.catalog import Catalog
from truestill_core.drive import create_marker

_START = datetime(2026, 8, 14, 9, 0)
_DAYS = 4
_PER_DAY = 12  # comfortably over DEFAULT_MIN_FILES so every day clusters


def _drive_with_a_four_day_run(tmp_path: Path) -> tuple[Path, Path]:
    """A connected drive whose photos form one multi-day trip proposal."""
    root = tmp_path / "drive"
    root.mkdir()
    marker = create_marker(root, label="Backup A")
    db = tmp_path / "c.sqlite"
    with Catalog(db) as catalog:
        catalog.upsert_drive(uuid=marker.uuid, label=marker.label)
        for day in range(_DAYS):
            for index in range(_PER_DAY):
                when = _START + timedelta(days=day, minutes=index)
                sha = f"sha{day:02d}{index:02d}"
                catalog.record_uploaded(
                    source_path=f"/src/{sha}.jpg",
                    original_name=f"{sha}.jpg",
                    sha256=sha,
                    copy_sha256=sha,
                    perceptual=None,
                    size=1000,
                    captured_at=when.isoformat(),
                    category="Camera",
                    relative=f"2026/2026-08/{sha}.jpg",
                    drive_uuid=marker.uuid,
                )
    return root, db


def _name_the_trip(db: Path, name: str) -> None:
    days = [(_START + timedelta(days=day)).date().isoformat() for day in range(_DAYS)]
    with Catalog(db) as catalog:
        catalog.create_trip(
            name=name, slug=name.lower(), start_date=days[0], end_date=days[-1], days=days
        )


def _trip_card(root: Path, db: Path) -> dict:
    """The card as the SCREEN receives it - proposal, then the serialisation the route returns.

    Asserting on `propose_events`' own `ReviewCard` objects would test one layer short of the
    wire, which is the gap that let a missing payload key survive (`ab0a76a`'s blind spot).
    """
    proposal = propose_events(root, db)
    assert proposal["ok"] is True
    payload = proposed_review_cards_payload("sess", proposal)
    cards = [card for card in payload["cards"] if card["kind"] == "trip"]
    assert len(cards) == 1, f"expected one trip card, got {len(cards)}"
    return dict(cards[0])


def test_a_trip_the_catalog_has_already_named_arrives_carrying_that_name(tmp_path: Path) -> None:
    """THE DEFECT. Before the fix the card came back with no name at all."""
    root, db = _drive_with_a_four_day_run(tmp_path)
    _name_the_trip(db, "Wayanad")

    card = _trip_card(root, db)

    assert card.get("existing_name") == "Wayanad", (
        "the card for an already-named trip carries no name, so the screen shows an empty box "
        "for a question it will not accept an answer to"
    )


def test_an_unnamed_trip_carries_no_name_and_is_still_asked(tmp_path: Path) -> None:
    """The cry-wolf half. A fix that labelled every trip 'named' would silence the real question.

    This is the state the screen exists for, and it must be untouched: no name recorded, so the
    card must still invite one.
    """
    root, db = _drive_with_a_four_day_run(tmp_path)

    card = _trip_card(root, db)

    assert card.get("existing_name") is None


def test_naming_one_trip_does_not_mark_a_different_one(tmp_path: Path) -> None:
    """The lookup must be keyed on this card's own days, not on 'any trip exists'."""
    root, db = _drive_with_a_four_day_run(tmp_path)
    with Catalog(db) as catalog:
        catalog.create_trip(
            name="Somewhere Else",
            slug="somewhere-else",
            start_date="2013-09-15",
            end_date="2013-09-16",
            days=["2013-09-15", "2013-09-16"],
        )

    card = _trip_card(root, db)

    assert card.get("existing_name") is None
