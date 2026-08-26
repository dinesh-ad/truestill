"""`restore` states what it observed, never why it thinks it happened. `(aia)`

Six sentences asserted a cause the code had not established. The worst told a user whose catalog
had just been rebuilt that *"its photos have changed"* - measured false: 353 byte-identical files,
all still `Camera`, and the re-derived signatures matched the drive document exactly.

⚠ **A TEST PINNING THE OLD WORDING WOULD HAVE PASSED THROUGHOUT THE DEFECT.** Every one of the six
was a *correct string*; what was wrong was the claim inside it. So this file asserts structure -
that the table is exhaustive, that the CLI holds no sentences of its own, and that each note's
words survive a round trip - and **not** the words themselves.

⚠ **WHICH HALF IS MECHANICAL, AND WHICH IS A HUMAN READ**, stated rather than implied:

* **Mechanical, and asserted here**: `RESTORE_WORDING` covers every `RestoreNote`;
  `SUPERSEDED_NOTE` covers every `SupersededReason`; the CLI reads the table rather than holding
  strings; the two choosers return the right arm for each discriminator.
* **A human read, and NOT asserted here**: whether a sentence asserts a cause at all. A regex over
  *"because"*, *"so"* and *"have changed"* was considered and refused - it would **miss** the two
  worst instances (*"These sections exist there and NOT here"* and *"The drive now matches this
  catalog"* assert causes with no connective) and **cry wolf** on the two clean ones, which use
  *"so"* correctly for a mechanism the code enforces. Shipping that regex would be a guard-shaped
  object, which `ENGINEERING_STANDARD.md` §4 is about. The comment beside each table entry names
  what the code checked; keeping the wording inside that is review, not automation.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from truestill_core.decisions import (
    RESTORE_WORDING,
    SUPERSEDED_NOTE,
    ApplyReport,
    Decisions,
    RestoreNote,
    SupersededReason,
    nothing_applied_note,
    reconcile_documents,
    unmatched_events_note,
)

_CLI = Path(__file__).resolve().parents[3] / "packages/truestill-cli/src/truestill_cli/cli.py"


def test_every_note_is_worded() -> None:
    """The DERIVED inventory is the enum; the DECLARATION is the table. `(ago)`'s direction.

    Indexing rather than `.get` is the point: a member added tomorrow raises `KeyError` at the
    call site instead of being worded by an `else` nobody wrote for it - `STOP_WORDING`'s reason.
    """
    missing = [note for note in RestoreNote if note not in RESTORE_WORDING]
    assert not missing, f"{missing} has no wording, so a surface would raise on it"
    assert len(RESTORE_WORDING) == len(RestoreNote)


def test_every_superseded_reason_has_a_note() -> None:
    """A new reason with no sentence must fail here, not fall through to the old one."""
    missing = [reason for reason in SupersededReason if reason not in SUPERSEDED_NOTE]
    assert not missing, f"{missing} would be reported with another reason's words"
    assert len(SUPERSEDED_NOTE) == len(SupersededReason)


def test_no_wording_is_empty_or_a_placeholder() -> None:
    """⚠ Anti-vacuity. A table of empty strings satisfies every count assertion above."""
    for note, wording in RESTORE_WORDING.items():
        assert wording.text.strip(), f"{note} is worded with nothing"
        assert len(wording.text) > 20, f"{note}'s wording is too short to say anything"


#: The six claims the census found, verbatim. ⚠ **This is a REGRESSION list, not a detector**: it
#: stops these six returning and cannot recognise a seventh. Recognising a new causal claim is the
#: human read this module's docstring names.
_RETRACTED = (
    "its photos have changed",
    "were older and were not used",
    "exist there and NOT here",
    "now matches this catalog",
    "were older than this",
    "so membership changed",
)


def test_no_retracted_claim_returns_anywhere() -> None:
    """Checked in BOTH homes, and the second was added when a mutation walked past the first.

    The first draft read only `cli.py`. Putting *"its photos have changed"* back into
    `RESTORE_WORDING` then changed what a user sees and **killed no test** - the sentence had moved
    to core and the guard had not. A guard shaped like the old location cannot see the new one,
    which is `(ahu)`'s and `(ahw)`'s shape a third time.
    """
    cli = _CLI.read_text(encoding="utf-8")
    assert len(cli) > 100_000, "the CLI was not actually read"
    worded = " ".join(w.text for w in RESTORE_WORDING.values())
    for gone in _RETRACTED:
        assert gone not in cli, f"{gone!r} is spelled in the CLI; wording lives in RESTORE_WORDING"
        assert gone not in worded, f"{gone!r} is back in RESTORE_WORDING - it was retracted"
    assert "RESTORE_WORDING[" in cli, "the CLI no longer reads the shared table at all"


@pytest.mark.parametrize(
    ("events_here", "expected"),
    [(0, RestoreNote.NO_EVENTS_HERE), (1, RestoreNote.NO_SUCH_GROUP)],
)
def test_an_unmatched_event_names_the_reason_it_can_establish(
    events_here: int, expected: RestoreNote
) -> None:
    """The discriminator `ApplyReport.events_here` exists to tell these two apart.

    With no events here, every document event misses and the reason is THIS CATALOG. With events
    here, the reason is genuinely unknown - and the wording says so rather than picking one.
    """
    report = ApplyReport(unmatched_events=("Sam Wedding",), events_here=events_here)
    assert unmatched_events_note(report) is expected


def test_the_two_zeroes_are_told_apart() -> None:
    """`NOTHING_CONFIRMED_NOTE`'s defect, in restore: an empty `applied` has two causes."""
    assert nothing_applied_note(ApplyReport()) is RestoreNote.NOTHING_NEW
    assert (
        nothing_applied_note(ApplyReport(unmatched_events=("Sam Wedding",)))
        is RestoreNote.NOTHING_APPLIED
    )
    assert nothing_applied_note(ApplyReport(not_applied=("albums",))) is RestoreNote.NOTHING_APPLIED


def test_a_real_loss_is_never_printed_in_the_nothing_to_do_register() -> None:
    """⚠ The marker is derived from `actionable`, so it cannot be typed wrongly at a call site."""
    assert RESTORE_WORDING[RestoreNote.NO_EVENTS_HERE].actionable
    assert RESTORE_WORDING[RestoreNote.NO_SUCH_GROUP].actionable
    assert RESTORE_WORDING[RestoreNote.NOTHING_APPLIED].actionable
    assert RESTORE_WORDING[RestoreNote.DRIVE_HOLDS_MORE].actionable
    assert not RESTORE_WORDING[RestoreNote.NOTHING_NEW].actionable
    assert not RESTORE_WORDING[RestoreNote.DRIVE_WRITTEN].actionable


def test_a_tie_and_an_undated_document_are_not_called_older() -> None:
    """The half of the "were older" sentence that stays here; the recovery half is `(ahz)`."""
    words = {reason: RESTORE_WORDING[SUPERSEDED_NOTE[reason]].text for reason in SupersededReason}
    assert "earlier" in words[SupersededReason.OLDER]
    for reason in (SupersededReason.TIE, SupersededReason.UNDATED):
        assert "older" not in words[reason].lower(), (
            f"{reason} is reported as an age, and it is not one"
        )
    assert len(set(words.values())) == len(SupersededReason), "two reasons share one sentence"


def _doc(uuid: str, label: str, written: str, trip: str) -> Decisions:
    """Two drives disagreeing about one trip's name, over the same days."""
    return Decisions(
        drive_uuid=uuid,
        drive_label=label,
        written=written,
        trips=({"name": trip, "slug": trip.lower(), "days": ["2014-08-14"]},),
    )


@pytest.mark.parametrize(
    ("a_written", "b_written", "expected"),
    [
        ("2026-01-02T00:00:01+00:00", "2026-01-01T00:00:00+00:00", SupersededReason.OLDER),
        ("2026-01-02T00:00:01+00:00", "2026-01-02T00:00:01+00:00", SupersededReason.TIE),
        ("2026-01-02T00:00:01+00:00", "", SupersededReason.UNDATED),
    ],
)
def test_the_reason_a_value_lost_is_classified_not_assumed(
    a_written: str, b_written: str, expected: SupersededReason
) -> None:
    """⚠ **The behaviour half, and a mutation is why it exists.**

    Asserting only that the three sentences differ let `_why_it_lost` be replaced by a bare
    ``return OLDER`` with nothing failing - the words were right and the choice among them was
    never checked. `_ranked` calls ties *"ordinary, not exotic"*, so `TIE` is the common case and
    was the common wrong answer.
    """
    # `drive_uuid` ascending is `_ranked`'s tiebreak, so "aaa" wins the tie and "bbb" is the loss.
    documents = [
        _doc("aaa", "Drive A", a_written, "Kept"),
        _doc("bbb", "Drive B", b_written, "Beaten"),
    ]
    _, report = reconcile_documents(documents)
    assert len(report.superseded) == 1, "the disagreement was not reported at all"
    loss = report.superseded[0]
    assert loss.drive_label == "Drive B"
    assert loss.reason is expected
