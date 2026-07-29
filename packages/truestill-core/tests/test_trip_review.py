"""The detection-to-persistence join (Stage 2d, sub-stage 13.1): catalog-only, no layout.

`propose_trips_from_catalog` runs `detect_trips` (2b, pure) against the catalog's dated Camera
copies; `commit_trips` persists reviewed decisions through the Stage 2c CRUD. Mirrors
`event_review.py`'s already-organized-drive path one layer up.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path

import pytest
from truestill_core.catalog import Catalog
from truestill_core.events import EventCandidate, EventItem
from truestill_core.trip_review import (
    ReviewCard,
    TripDecision,
    TripMergeError,
    assemble_trip_review,
    collapsed_event_cards,
    commit_trips,
    decline_message,
    merge_review_cards,
    order_review_cards,
    propose_trips_from_catalog,
    small_event_limit,
    split_trip,
)
from truestill_core.trips import TripDecline, TripDeclineReason, TripProposal


def _seed_day(catalog: Catalog, drive_uuid: str, day: datetime, start_index: int) -> None:
    """Ten Camera copies on one day, 20 minutes apart -- one cluster, comfortably over min_files.

    The same shape `test_event_review.py`'s `_one_cluster` already uses for the day-event layer.
    """
    for i in range(10):
        when = day + timedelta(minutes=20 * i)
        sha = f"sha{start_index + i:04d}"
        catalog.record_uploaded(
            source_path=f"/src/img{start_index + i}.jpg",
            original_name=f"img{start_index + i}.jpg",
            sha256=sha,
            copy_sha256=sha,
            perceptual=None,
            size=1000,
            captured_at=when.isoformat(),
            category="Camera",
            relative=f"2026/2026-08/img{start_index + i}.jpg",
            drive_uuid=drive_uuid,
        )


def test_re_ingest_one_photo_into_a_named_trip_does_not_re_ask(tmp_path: Path) -> None:
    """The identity fixture Stage 2c deferred (`trip-grouping-research.md` §6/§12), built here.

    Fails against a mutation that skips the "already claimed" check and always re-creates: with
    that check removed, the second `commit_trips` call below would either raise
    (`trip_days.day`'s primary key refuses re-claiming an already-claimed day) or, if the insert
    were instead silently tolerant, produce a second `trips` row and orphan the original name --
    either way the assertions on row count, id and name below catch it. Confirmed by actually
    removing the `claims == {None}` branch and re-running: `sqlite3.IntegrityError`, as predicted.
    """
    with Catalog(tmp_path / "c.sqlite") as catalog:
        catalog.upsert_drive(uuid="D1", label="Drive A")
        _seed_day(catalog, "D1", datetime(2026, 8, 15, 9, 0), start_index=0)
        _seed_day(catalog, "D1", datetime(2026, 8, 16, 9, 0), start_index=10)

        result = propose_trips_from_catalog(catalog, "D1")
        assert len(result.proposals) == 1
        assert result.declines == []

        named = commit_trips(catalog, [TripDecision(result.proposals[0], name="Wayanad")])
        assert named == 1
        trip_id = catalog.trip_for_day("2026-08-15")
        assert trip_id is not None
        assert trip_id == catalog.trip_for_day("2026-08-16")

        # A decoy created AFTER the trip under test, so a delete-then-reinsert bug cannot land
        # back on the same id by rowid-reuse coincidence -- the identical discipline
        # test_edge_adjust_keeps_trip_id_and_name_stable (test_catalog_trips.py) already needed;
        # see its docstring for why the ordering matters.
        catalog.create_trip(
            name="Decoy",
            slug="decoy",
            start_date="2013-09-15",
            end_date="2013-09-15",
            days=["2013-09-15"],
        )

        # Re-ingest: one more photo into the already-claimed Aug 15 cluster, then re-propose from
        # scratch -- the exact scenario this fixture was deferred for (§10/§12). Placed right
        # after the existing cluster's last photo (not a separate late-night burst), so it joins
        # the same cluster rather than exercising within-day segmentation, which is Stage 1's
        # concern, not this one's.
        catalog.record_uploaded(
            source_path="/src/img_new.jpg",
            original_name="img_new.jpg",
            sha256="shaNEW0",
            copy_sha256="shaNEW0",
            perceptual=None,
            size=1000,
            captured_at=datetime(2026, 8, 15, 12, 20).isoformat(),
            category="Camera",
            relative="2026/2026-08/img_new.jpg",
            drive_uuid="D1",
        )
        second = propose_trips_from_catalog(catalog, "D1")
        assert len(second.proposals) == 1

        # A caller who doesn't know it is already named passes a DIFFERENT one -- proving it is
        # ignored, never used to rename or duplicate.
        named_again = commit_trips(
            catalog, [TripDecision(second.proposals[0], name="Some Other Name")]
        )
        assert named_again == 0  # nothing NEW was named -- it was already claimed

        rows = catalog._conn.execute(
            "SELECT id, name FROM trips WHERE id = ?", (trip_id,)
        ).fetchall()
        assert len(rows) == 1  # no duplicate row under the original id
        assert rows[0]["name"] == "Wayanad"  # name not overwritten
        assert catalog.trip_for_day("2026-08-15") == trip_id  # identity stable
        assert catalog.trip_for_day("2026-08-16") == trip_id

        total = catalog._conn.execute("SELECT COUNT(*) AS n FROM trips").fetchone()["n"]
        assert total == 2  # the real trip plus the decoy -- no third row


def test_confirmed_edges_are_what_get_stored_not_the_raw_proposal(tmp_path: Path) -> None:
    """§5: "the proposal is the run; the edges belong to the user" -- never silently trimmed or
    padded by the detector itself, but the *reviewer's* trim must actually take.

    A 3-day run is proposed; the decision narrows it to the last two days (as if a user decided
    the first evening was not really part of the trip). Asserts the persisted `trip_days` reflect
    exactly the confirmed two days, not the raw three-day proposal -- `create_trip` is called
    with the caller-confirmed set, never `proposal.days` directly.
    """
    with Catalog(tmp_path / "c.sqlite") as catalog:
        catalog.upsert_drive(uuid="D1", label="Drive A")
        # Midday bursts on all three days -- a consistent ~21h gap between each, so every day
        # cuts reliably (a burst placed right after the prior day's, e.g. an evening-into-morning
        # span, can merge across midnight under the relative density test -- see the sibling
        # re-ask fixture above, which hit exactly this and was redesigned around it).
        _seed_day(catalog, "D1", datetime(2026, 8, 14, 9, 0), start_index=0)
        _seed_day(catalog, "D1", datetime(2026, 8, 15, 9, 0), start_index=10)
        _seed_day(catalog, "D1", datetime(2026, 8, 16, 9, 0), start_index=20)

        result = propose_trips_from_catalog(catalog, "D1")
        assert len(result.proposals) == 1
        proposal = result.proposals[0]
        assert sorted(proposal.days) == [
            date(2026, 8, 14),
            date(2026, 8, 15),
            date(2026, 8, 16),
        ]

        confirmed = [date(2026, 8, 15), date(2026, 8, 16)]  # user drops Aug 14
        named = commit_trips(
            catalog, [TripDecision(proposal, name="Wayanad", confirmed_days=confirmed)]
        )
        assert named == 1

        assert catalog.trip_for_day("2026-08-14") is None  # never claimed -- not raw padding
        trip_id = catalog.trip_for_day("2026-08-15")
        assert trip_id is not None
        assert catalog.trip_for_day("2026-08-16") == trip_id

        row = catalog._conn.execute(
            "SELECT start_date, end_date FROM trips WHERE id = ?", (trip_id,)
        ).fetchone()
        assert row["start_date"] == "2026-08-15"  # the confirmed start, not the proposal's
        assert row["end_date"] == "2026-08-16"


def test_a_declined_run_persists_nothing(tmp_path: Path) -> None:
    """Declines never reach `commit_trips` at all -- there is no decision to make for one.

    `TripDecision` wraps a `TripProposal`, never a `TripDecline`, so a decline cannot be turned
    into a decision by construction. This confirms the *catalog* side of that guarantee: a run
    over `DEFAULT_MAX_SPAN_DAYS` produces zero proposals and one decline, and zero `trips` rows
    exist regardless of what a caller does with the (empty) proposal list.
    """
    with Catalog(tmp_path / "c.sqlite") as catalog:
        catalog.upsert_drive(uuid="D1", label="Drive A")
        start = datetime(2026, 1, 1, 9, 0)
        for day_offset in range(31):  # one more than DEFAULT_MAX_SPAN_DAYS (30) -> declined
            _seed_day(
                catalog, "D1", start + timedelta(days=day_offset), start_index=day_offset * 10
            )

        result = propose_trips_from_catalog(catalog, "D1")
        assert result.proposals == []
        assert len(result.declines) == 1

        count = catalog._conn.execute("SELECT COUNT(*) AS n FROM trips").fetchone()["n"]
        assert count == 0


# --- 13.3b: the assembled review surface -----------------------------------------------


def test_assemble_trip_review_bundles_a_multi_day_run_into_one_card(tmp_path: Path) -> None:
    """The inversion (§13.3b): a multi-day run assembles into ONE card, a standalone day into
    its own -- never one card per raw Stage-1 cluster regardless of which run it belongs to.

    Fails against the pre-13.3b bug this replaces: rendering one card per cluster produces
    THREE cards here (two trip days plus the standalone), not two.
    """
    with Catalog(tmp_path / "c.sqlite") as catalog:
        catalog.upsert_drive(uuid="D1", label="Drive A")
        _seed_day(catalog, "D1", datetime(2026, 8, 15, 9, 0), start_index=0)
        _seed_day(catalog, "D1", datetime(2026, 8, 16, 9, 0), start_index=10)
        _seed_day(catalog, "D1", datetime(2026, 8, 25, 9, 0), start_index=20)  # standalone

        review = assemble_trip_review(catalog, "D1")

        assert len(review.cards) == 2  # NOT three -- the bug this stage replaces
        by_kind = {card.kind: card for card in review.cards}
        assert set(by_kind) == {"trip", "event"}

        trip_card = by_kind["trip"]
        assert trip_card.trip is not None
        assert sorted(trip_card.trip.days) == [date(2026, 8, 15), date(2026, 8, 16)]
        assert trip_card.trip.days[date(2026, 8, 15)] == 10  # per-day breakdown, not just a total

        event_card = by_kind["event"]
        assert event_card.event is not None
        assert event_card.event.start.date() == date(2026, 8, 25)


def _event_candidate(day: date, count: int) -> EventCandidate:
    items = tuple(
        EventItem(
            key=f"k{day.isoformat()}-{i}",
            captured_at=datetime(day.year, day.month, day.day, 9, i % 60),
            sha256=f"s{day.isoformat()}-{i}",
        )
        for i in range(count)
    )
    return EventCandidate(items=items)


def test_review_order_and_small_set_are_derived_and_trips_never_collapse() -> None:
    min_files = 8
    trip = ReviewCard(
        trip=TripProposal(
            start_date=date(2026, 8, 5),
            end_date=date(2026, 8, 5),
            days={date(2026, 8, 5): 1},
        )
    )
    cards = [
        ReviewCard(event=_event_candidate(date(2026, 8, 1), 8)),
        ReviewCard(event=_event_candidate(date(2026, 8, 2), 32)),
        ReviewCard(event=_event_candidate(date(2026, 8, 3), 31)),
        ReviewCard(event=_event_candidate(date(2026, 8, 4), 100)),
        trip,
    ]

    ordered = order_review_cards(cards)
    collapsed = collapsed_event_cards(ordered, min_files)

    assert [card.count for card in ordered] == [100, 32, 31, 8, 1]
    assert small_event_limit(min_files) == 32  # two doublings above the configured floor
    assert [card.count for card in collapsed] == [31, 8]  # exactly below, not at, the limit
    assert trip not in collapsed  # underlying TripProposal wins even when display kind is "event"


def test_merge_review_cards_combines_two_gap_separated_runs() -> None:
    """The gap case (§4/§10): two runs a few days apart the detector did not join."""
    trip_a = TripProposal(
        start_date=date(2026, 8, 1),
        end_date=date(2026, 8, 2),
        days={date(2026, 8, 1): 10, date(2026, 8, 2): 10},
    )
    trip_b = TripProposal(
        start_date=date(2026, 8, 5), end_date=date(2026, 8, 5), days={date(2026, 8, 5): 8}
    )
    day_totals = {date(2026, 8, 1): 10, date(2026, 8, 2): 10, date(2026, 8, 5): 8}

    merged = merge_review_cards([ReviewCard(trip=trip_a), ReviewCard(trip=trip_b)], day_totals)

    assert merged.start_date == date(2026, 8, 1)
    assert merged.end_date == date(2026, 8, 5)
    assert sorted(merged.days) == [date(2026, 8, 1), date(2026, 8, 2), date(2026, 8, 5)]


def test_merge_review_cards_refuses_across_a_year_boundary() -> None:
    """§3e: the layout has no way to express a trip folder spanning two year parents."""
    trip_a = TripProposal(
        start_date=date(2026, 12, 30),
        end_date=date(2026, 12, 31),
        days={date(2026, 12, 30): 5, date(2026, 12, 31): 5},
    )
    trip_b = TripProposal(
        start_date=date(2027, 1, 1), end_date=date(2027, 1, 1), days={date(2027, 1, 1): 5}
    )
    day_totals = {date(2026, 12, 30): 5, date(2026, 12, 31): 5, date(2027, 1, 1): 5}

    with pytest.raises(TripMergeError, match="year boundary"):
        merge_review_cards([ReviewCard(trip=trip_a), ReviewCard(trip=trip_b)], day_totals)


def test_merge_review_cards_declines_past_max_span() -> None:
    """§3f: decline, never silently split or truncate -- the same rule detection obeys."""
    trip_a = TripProposal(
        start_date=date(2026, 1, 1), end_date=date(2026, 1, 1), days={date(2026, 1, 1): 5}
    )
    trip_b = TripProposal(
        start_date=date(2026, 2, 15), end_date=date(2026, 2, 15), days={date(2026, 2, 15): 5}
    )  # 46 days apart -- over DEFAULT_MAX_SPAN_DAYS
    day_totals = {date(2026, 1, 1): 5, date(2026, 2, 15): 5}

    with pytest.raises(TripMergeError, match="too long to propose as one trip"):
        merge_review_cards([ReviewCard(trip=trip_a), ReviewCard(trip=trip_b)], day_totals)


def test_merge_reclaims_the_whole_day_for_a_merged_in_event() -> None:
    """§2: once a day joins a trip, ALL its photos belong to it -- not just the clustered ones."""
    trip = TripProposal(
        start_date=date(2026, 8, 1), end_date=date(2026, 8, 1), days={date(2026, 8, 1): 10}
    )
    event = _event_candidate(
        date(2026, 8, 3), count=8
    )  # a solo cluster: only 8 of that day's photos
    day_totals = {
        date(2026, 8, 1): 10,
        date(2026, 8, 3): 15,
    }  # the day really has 15 (7 stragglers)

    merged = merge_review_cards([ReviewCard(trip=trip), ReviewCard(event=event)], day_totals)

    assert merged.days[date(2026, 8, 3)] == 15  # the full day total, not the cluster's 8


def test_split_trip_breaks_a_run_into_the_expected_pieces() -> None:
    proposal = TripProposal(
        start_date=date(2026, 8, 15),
        end_date=date(2026, 8, 17),
        days={date(2026, 8, 15): 10, date(2026, 8, 16): 10, date(2026, 8, 17): 10},
    )

    first, second = split_trip(proposal, date(2026, 8, 15))

    assert sorted(first.days) == [date(2026, 8, 15)]
    assert sorted(second.days) == [date(2026, 8, 16), date(2026, 8, 17)]


def test_split_trip_rejects_an_invalid_split_point() -> None:
    proposal = TripProposal(
        start_date=date(2026, 8, 15),
        end_date=date(2026, 8, 16),
        days={date(2026, 8, 15): 10, date(2026, 8, 16): 10},
    )
    with pytest.raises(ValueError, match="not a valid split point"):
        split_trip(proposal, date(2026, 8, 16))  # the last day -- nothing left after it


def test_decline_message_matches_the_section_3f_wording() -> None:
    decline = TripDecline(
        start_date=date(2018, 6, 3),
        end_date=date(2018, 8, 3),
        day_count=62,
        reason=TripDeclineReason.MAX_SPAN,
    )
    message = decline_message(decline, max_span_days=30)
    assert message == (
        "62 consecutive days of photos (2018-06-03 to 2018-08-03) - too long to propose as "
        "one trip. Raise trips.max_span_days (currently 30) if this really was one trip."
    )
