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

from dataclasses import fields
from pathlib import Path

import pytest
from truestill_core.decisions import (
    REPORT_FIELD_EXCEPTIONS,
    REPORT_FIELD_NOTE,
    RESTORE_WORDING,
    SUPERSEDED_NOTE,
    ApplyReport,
    Decisions,
    NameSwap,
    RestoreNote,
    SupersededReason,
    nothing_applied_note,
    reconcile_documents,
    render_swaps,
    restored_count,
    superseded_note,
    unmatched_events_note,
    withheld_count,
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


def test_every_report_field_reaches_the_reader() -> None:
    """The DERIVED inventory is the dataclass; the DECLARATION is the two tables. `(ahx)`

    ⚠ **This is the guard the loop needs to be a fix rather than a repair.** Three fields were
    computed and printed by nobody because the printer named five and there were eight. A new field
    now fails here rather than being silently unprinted, which is the only difference between this
    and the state it replaced.
    """
    names = {f.name for f in fields(ApplyReport)}
    declared = set(REPORT_FIELD_NOTE) | set(REPORT_FIELD_EXCEPTIONS)

    unhandled = sorted(names - declared)
    assert not unhandled, (
        f"{unhandled} is computed by ApplyReport and reaches no reader. Give it a wording in "
        "REPORT_FIELD_NOTE, or declare it in REPORT_FIELD_EXCEPTIONS WITH the reason it cannot "
        "be looped - a declared exception is a decision, an unhandled field is the defect."
    )
    stale = sorted(declared - names)
    assert not stale, f"{stale} is declared and no longer exists on ApplyReport"


def test_no_field_is_both_worded_and_excepted() -> None:
    """⚠ Anti-vacuity: the two tables must partition, or the count above can be met by overlap."""
    both = sorted(set(REPORT_FIELD_NOTE) & set(REPORT_FIELD_EXCEPTIONS))
    assert not both, f"{both} is in both tables, so neither says what happens to it"


def test_every_declared_exception_states_a_reason() -> None:
    """A skip-list with empty strings would pass every assertion above and mean nothing."""
    for name, reason in REPORT_FIELD_EXCEPTIONS.items():
        assert len(reason) > 40, f"{name} is excepted without a reason worth reading"


def test_every_worded_field_has_wording() -> None:
    """The second hop: a field mapped to a note that has no sentence still reaches nobody."""
    for name, note in REPORT_FIELD_NOTE.items():
        assert note in RESTORE_WORDING, f"{name} maps to {note}, which has no wording"


def test_both_halves_are_counted_from_the_fields_not_a_list() -> None:
    """The pair rule's second number must move when a new omission appears. `CPF3773`'s shape."""
    empty = ApplyReport()
    assert restored_count(empty) == 0
    assert withheld_count(empty) == 0

    full = ApplyReport(
        applied={"trips": 2, "settings": 1},
        unmatched_events=("Sam",),
        conflicting_trips=("Ooty",),
        trips_without_days=("Dayless",),
        not_applied=("albums",),
        awaiting_content={"date_confirmations": 3},
    )
    assert restored_count(full) == 3
    # 1 event + 1 conflict + 1 dayless + 1 not-applied + 3 awaiting
    assert withheld_count(full) == 7


def test_a_superseded_loss_names_the_values_it_withheld() -> None:
    """⚠ **A count is not a report.** `(ahz)` §6

    `Superseded` carried `section, drive_label, count, reason` and no values, so the user read
    *"3 events on dest were older and were not used"* and never learned WHICH names - the one
    detail that would have made the line alarming, withheld by the one line that could have
    alerted them.
    """
    a = _doc("aaa", "Drive A", "2026-01-02T00:00:01+00:00", "Kept")
    b = _doc("bbb", "Drive B", "2026-01-01T00:00:00+00:00", "Beaten")
    _, report = reconcile_documents([a, b])

    loss = report.superseded[0]
    assert loss.swaps == (NameSwap(lost="Beaten", kept="Kept"),)
    assert render_swaps(loss.swaps) == "'Beaten' -> 'Kept'"


def test_the_drive_the_user_named_wins_its_keys_over_a_newer_document() -> None:
    """⚠ **The fix.** `(ahz)` step 2.

    `restore <root>` is an explicit act - the user typed that path - and until this, a document
    found through a stored *hint* outranked it by carrying a fresher clock. That is how
    re-organizing to recover from a lost catalog destroyed the names it was recovering.
    """
    named = _doc("aaa", "Your drive", "2026-01-01T00:00:00+00:00", "Bangalore Dec 2009")
    newer = _doc("bbb", "Rebuilt", "2026-01-02T00:00:01+00:00", "placeholder A")

    merged, report = reconcile_documents([named, newer], named_root_uuid="aaa")
    assert [t["name"] for t in merged.trips] == ["Bangalore Dec 2009"], (
        "the drive the user named did not win its own key"
    )

    # ⚠ And the overruled newer value is REPORTED, not swallowed: it is the one case a user may
    # need to reverse, because it may be a change they made on another machine.
    loss = report.superseded[0]
    assert loss.by_authority is True
    assert loss.swaps == (NameSwap(lost="placeholder A", kept="Bangalore Dec 2009"),)
    assert superseded_note(loss) is RestoreNote.OVERRULED_BY_NAMED_ROOT
    assert RESTORE_WORDING[RestoreNote.OVERRULED_BY_NAMED_ROOT].actionable


def test_without_a_named_root_the_ranking_is_unchanged() -> None:
    """⚠ Anti-vacuity, and the cry-wolf half: authority applies only when a root was named."""
    a = _doc("aaa", "Drive A", "2026-01-01T00:00:00+00:00", "Older")
    b = _doc("bbb", "Drive B", "2026-01-02T00:00:01+00:00", "Newer")
    merged, report = reconcile_documents([a, b])
    assert [t["name"] for t in merged.trips] == ["Newer"], "rank stopped deciding"
    assert report.superseded[0].by_authority is False
    assert superseded_note(report.superseded[0]) is RestoreNote.LOST_OLDER


def test_the_named_root_winning_on_rank_is_not_called_authority() -> None:
    """`by_authority` marks a DISAGREEMENT between rank and authority, not merely a named root."""
    named = _doc("aaa", "Your drive", "2026-01-02T00:00:01+00:00", "Bangalore Dec 2009")
    older = _doc("bbb", "Rebuilt", "2026-01-01T00:00:00+00:00", "placeholder A")
    _, report = reconcile_documents([named, older], named_root_uuid="aaa")
    assert report.superseded[0].by_authority is False, (
        "the named root won on rank; calling that authority would cry wolf on every ordinary merge"
    )


def test_authority_is_per_key_so_another_drive_still_contributes() -> None:
    """🔑 **PER KEY, NOT PER SECTION**, and a mutation is why this test is here. `(ahz)`

    Per-section authority would let the named root answer for decisions it does not carry - every
    trip another drive holds and it has never heard of would vanish. That is the
    freshly-formatted-drive failure `_merge_section` already refuses, arriving by a new route.
    """
    named = Decisions(
        drive_uuid="aaa",
        drive_label="Your drive",
        written="2026-01-01T00:00:00+00:00",
        trips=({"name": "Ooty", "slug": "o", "days": ["2013-01-01"]},),
    )
    other = Decisions(
        drive_uuid="bbb",
        drive_label="Rebuilt",
        written="2026-01-02T00:00:01+00:00",
        trips=(
            {"name": "placeholder", "slug": "p", "days": ["2013-01-01"]},
            {"name": "Wayanad", "slug": "w", "days": ["2014-08-14"]},
        ),
    )
    merged, _ = reconcile_documents([named, other], named_root_uuid="aaa")
    names = sorted(t["name"] for t in merged.trips)
    assert names == ["Ooty", "Wayanad"], (
        f"a trip only the other drive holds was discarded: {names}. Authority is per key."
    )


def test_the_sentence_serves_the_legitimate_case_too() -> None:
    """⚠ **The side effect, named before it is built.** `(ahz)` step 2 inherits Microsoft's own
    warning about an authoritative restore: *you lose all changes to the restore object that
    occurred after the backup.*

    If a user renamed a trip on a SECOND MACHINE after the named drive's document was written, the
    named root would beat that legitimate newer change. The sentence has to serve both readings, so
    it names both values and lets the reader decide which is theirs.
    """
    words = RESTORE_WORDING[RestoreNote.OVERRULED_BY_NAMED_ROOT].text
    assert "{swaps}" in words, "the values are not shown, so the two cases cannot be told apart"
    assert "another machine" in words, "the legitimate case is not offered to the reader at all"
    assert "restore from THAT" in words, "the reader is told the risk and given no way to act"
