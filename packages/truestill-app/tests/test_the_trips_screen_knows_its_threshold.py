"""The number the Trips empty state states has to come off the wire.

The browser tests stub `/api/events/propose`, so they cannot see a server that stops sending
`min_files` - the same blind spot `ab0a76a` found when a removed service key changed nothing any
browser test could observe. This is the half that watches the payload.

`min_files` sits on the PROPOSAL payload and not on the shared review-cards payload, because
propose is the only path that can render an empty screen: split and merge rearrange cards that
already exist and cannot reduce them to none.
"""

from __future__ import annotations

from truestill_app.service import proposed_review_cards_payload, review_cards_payload
from truestill_app.service.trips import EventProposalSuccessPayload, ExistingNames
from truestill_core.events import DEFAULT_MIN_FILES


def _proposal(min_files: int) -> EventProposalSuccessPayload:
    """An empty proposal at a given threshold - the shape `propose_events` returns."""
    return {
        "ok": True,
        "uuid": "U1",
        "label": "BackupA",
        "cards": [],
        "day_totals": {},
        "min_files": min_files,
        "declines": [],
        "existing_names": ExistingNames({}, {}),
    }


def test_the_proposal_carries_the_threshold_it_filtered_with() -> None:
    payload = proposed_review_cards_payload("sess", _proposal(25))

    assert payload["min_files"] == 25


def test_the_default_travels_too_rather_than_being_assumed_by_the_screen() -> None:
    """A screen that falls back to its own constant is a second copy of the default, and the two
    drift the day the default moves."""
    payload = proposed_review_cards_payload("sess", _proposal(DEFAULT_MIN_FILES))

    assert payload["min_files"] == DEFAULT_MIN_FILES


def test_the_empty_proposal_is_exactly_where_the_number_is_needed() -> None:
    """No cards is the state the sentence exists for, and it must not be the state that loses it."""
    payload = proposed_review_cards_payload("sess", _proposal(12))

    assert payload["cards"] == []
    assert payload["min_files"] == 12


def test_the_shared_review_payload_does_not_grow_a_key_it_has_no_use_for() -> None:
    """Split and merge answer with this shape. Adding the threshold there would put a number on
    the wire that nothing reads, which is how a payload key outlives its reason."""
    payload = review_cards_payload("sess", [], 25)

    assert "min_files" not in payload
