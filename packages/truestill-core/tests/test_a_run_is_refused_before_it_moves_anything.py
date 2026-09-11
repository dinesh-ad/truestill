"""The free tier's cap: the counter that survives being damaged, and the run that never half-happens.

**Two properties, and the second is the one with teeth.** D16 §4 rules that a run over the cap is
refused *before anything moves*, never stopped part-way, because half an organize run is the
worst state this product can leave a library in - some files moved, some not, and a user who
cannot tell which. The cap is therefore a pure function of two integers asked before the first
copy, which is what makes it testable without a filesystem at all.

The first property is the counter, and its whole design is that **damage is never punished**.
D16 §3 already ruled the count resettable, so a corrupt file that stopped a run would stop
someone who did nothing wrong while stopping nobody who meant to.
"""

from __future__ import annotations

import json

import pytest
from truestill_core import allowance, app_paths
from truestill_core.licence import Licence, LicenceState

CAP = allowance.FREE_FILE_ALLOWANCE


def _write_usage(raw: bytes) -> None:
    target = app_paths.allowance_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(raw)


# --- the boundary, which is the whole of the cap function --------------------------------------


@pytest.mark.parametrize(
    ("case", "will_organize", "remaining", "starts"),
    [
        ("one under the cap", 999, 1_000, True),
        ("exactly at the cap", 1_000, 1_000, True),
        ("one over the cap", 1_001, 1_000, False),
        ("one file with one left", 1, 1, True),
        ("one file with none left", 1, 0, False),
        ("nothing to do with none left", 0, 0, True),
        ("far over", 40_000, 12, False),
    ],
)
def test_the_boundary_is_at_the_cap_and_not_one_short(
    case: str, will_organize: int, remaining: int, starts: bool
) -> None:
    """**Exactly at the cap starts.** The allowance is what may be written, not what may be
    approached, and a run landing exactly on it must not be refused - that would make the
    advertised number a lie by one, which is the kind of defect nobody reports and everybody
    resents.

    ``0`` files with ``0`` remaining starts, because refusing a run that would write nothing is
    noise: there is no cap to enforce against no work.
    """
    verdict = allowance.may_start(will_organize, remaining)

    assert verdict.may_start is starts, case
    assert verdict.will_organize == will_organize, case
    assert verdict.remaining == remaining, case


def test_a_refusal_names_both_numbers_and_says_nothing_moved() -> None:
    """The refusal has to be actionable, which means the two numbers the next decision needs.

    ⚠ **"Nothing has moved" is asserted because it is the sentence that makes the refusal
    trustworthy.** A user told only "not allowed" has to go and check their library; a user told
    nothing moved does not. D16 §4's whole reason for refusing early is worthless if the message
    does not say so.
    """
    verdict = allowance.may_start(4_200, 300)

    assert verdict.may_start is False
    assert "4,200" in verdict.reason
    assert "300" in verdict.reason
    assert "nothing has moved" in verdict.reason.lower()


def test_a_permitted_run_carries_no_refusal_text() -> None:
    """The cry-wolf half. A verdict that always carried a reason would satisfy the test above
    while making every permitted run look like a refused one to whatever renders it."""
    assert allowance.may_start(10, 1_000).reason == ""
    assert allowance.may_start(10, None).reason == ""


def test_an_uncapped_allowance_never_refuses_however_large_the_run() -> None:
    """``None`` is uncapped and is not a very large number.

    A sentinel integer invites arithmetic that quietly reintroduces a ceiling, and there is no
    number that is "effectively unlimited" for a library of photographs - people have millions.
    """
    verdict = allowance.may_start(50_000_000, None)

    assert verdict.may_start is True
    assert verdict.remaining is None


# --- who is capped -----------------------------------------------------------------------------


def test_a_lapsed_licence_is_uncapped_because_it_loses_nothing_it_bought() -> None:
    """**D16 §2 followed to its conclusion, and this is where it would quietly be broken.**

    The buyer paid for an organiser with no cap. What lapses is entitlement to new versions, and
    D16 §4 enforces that by not installing them - never by taking a number away here. A future
    edit that treated LAPSED as free would pass every other test in this file.
    """
    assert allowance.remaining_for(LicenceState.LAPSED, used=999_999) is None
    assert allowance.remaining_for(LicenceState.ACTIVE, used=999_999) is None


@pytest.mark.parametrize(
    "state", [LicenceState.ABSENT, LicenceState.SIGNED_OUT, LicenceState.UNREADABLE]
)
def test_every_other_state_is_capped_and_the_remainder_is_never_negative(
    state: LicenceState,
) -> None:
    """A counter past the allowance answers ``0``, not a debt.

    A negative remainder would flow into `may_start` and refuse a run of zero files, which is the
    absurd refusal the boundary test above exists to prevent.
    """
    assert allowance.remaining_for(state, used=0) == CAP
    assert allowance.remaining_for(state, used=1) == CAP - 1
    assert allowance.remaining_for(state, used=CAP) == 0
    assert allowance.remaining_for(state, used=CAP + 10_000) == 0


def test_the_licence_shaped_entry_point_agrees_with_the_state_one() -> None:
    """Two doors to one answer, which is exactly how two answers start."""
    for state in LicenceState:
        licence = Licence(state)
        assert allowance.remaining_for_licence(licence, used=7) == allowance.remaining_for(state, 7)


# --- the counter -------------------------------------------------------------------------------


def test_a_fresh_install_has_written_nothing() -> None:
    """No file is not an error - it is every user's first launch."""
    assert allowance.files_written() == 0
    assert not app_paths.allowance_path().exists()


def test_the_count_accumulates_across_runs_rather_than_resetting() -> None:
    """**Cumulative is the whole ruling** (D16 §1): a per-run cap is not a cap, because a user
    runs it n times and the free tier becomes the entire product."""
    assert allowance.record_files_written(400) == 400
    assert allowance.record_files_written(300) == 700
    assert allowance.record_files_written(1) == 701
    assert allowance.files_written() == 701


@pytest.mark.parametrize(
    ("case", "raw"),
    [
        ("missing field", b'{"v":1}'),
        ("not an object", b"[1,2,3]"),
        ("not json at all", b"nonsense"),
        ("empty", b""),
        ("invalid utf-8", b"\x80\x81\x82"),
        ("a negative count", b'{"v":1,"files_written":-5}'),
        ("a string count", b'{"v":1,"files_written":"9999"}'),
        ("a float count", b'{"v":1,"files_written":12.5}'),
        # `isinstance(True, int)` is True in Python, so an unguarded reader takes this as 1.
        ("a boolean count", b'{"v":1,"files_written":true}'),
        ("hand-edited to zero", b'{"v":1,"files_written":0}'),
    ],
)
def test_a_damaged_or_edited_counter_answers_zero_and_never_raises(case: str, raw: bytes) -> None:
    """**One rule for every way the file can be wrong, and the reason is asymmetric cost.**

    The counter is already resettable by deleting it (D16 §3), so treating a damaged one as
    exhausted would stop a run for a user who did nothing wrong while stopping nobody who meant
    to - corrupting a file is strictly harder than deleting it. Hand-edited to zero gets the same
    answer, and that is the speed bump working as ruled rather than a hole to be closed.
    """
    _write_usage(raw)

    assert allowance.files_written() == 0, case


def test_a_damaged_counter_is_replaced_by_a_sound_one_rather_than_compounding() -> None:
    """The read-modify-write goes through the reader, so garbage does not survive a record."""
    _write_usage(b"nonsense")

    assert allowance.record_files_written(50) == 50

    written = json.loads(app_paths.allowance_path().read_text())
    assert written["files_written"] == 50
    assert written["v"] == allowance.USAGE_VERSION


def test_the_counter_lives_beside_the_token_and_not_inside_the_catalog() -> None:
    """**The placement ruling, asserted where it can regress** (D16 §1).

    ⚠ A catalog travels when it is copied, so a counter living there would carry the cap to a
    second machine - punishing exactly the multi-drive behaviour this product exists for. A
    catalog rebuild resetting the count is acceptable under D16 §3; travelling is not.
    """
    assert app_paths.allowance_path().parent == app_paths.licence_path().parent
    assert app_paths.allowance_path().suffix != ".sqlite"
    assert app_paths.allowance_path() != app_paths.licence_path()


def test_the_counter_file_is_not_signed_or_checksummed() -> None:
    """**A guard against a future fortress**, which is an odd thing to assert and is the point.

    D16 §3 rules that hardening the counter is the refused direction, because every mechanism
    that makes the count harder to reset makes it likelier to strand someone who paid. A ruling
    with nothing holding it gets undone by the next person who notices the file is editable, so
    the shape is pinned: two keys, both plainly readable, nothing that looks like a signature.
    """
    allowance.record_files_written(3)

    record = json.loads(app_paths.allowance_path().read_text())

    assert set(record) == {"v", "files_written"}
    assert record["files_written"] == 3


def test_a_counter_that_cannot_be_written_does_not_take_the_run_down() -> None:
    """A full disk must not stop work that was already permitted.

    The write is bookkeeping and the work it records is worth more than the record, so the total
    is still returned and nothing is raised. Provoked with a directory in the file's place, which
    is what a restore tool or an unzip into the data directory actually leaves behind.
    """
    app_paths.allowance_path().mkdir(parents=True)

    assert allowance.record_files_written(25) == 25
    assert allowance.files_written() == 0


def test_the_two_halves_meet_at_the_cap() -> None:
    """The counter and the cap function together, which is the only place they are wired.

    Nothing in the product joins them yet, so without this the pair could drift apart - the cap
    could measure something the counter does not record - and every test above would stay green.
    """
    allowance.record_files_written(CAP - 10)
    remaining = allowance.remaining_for(LicenceState.ABSENT, allowance.files_written())

    assert allowance.may_start(10, remaining).may_start is True
    assert allowance.may_start(11, remaining).may_start is False
