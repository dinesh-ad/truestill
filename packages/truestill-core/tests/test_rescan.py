"""Reconciliation: the four buckets, and the two properties that make them trustworthy.

The move case is the one with evidence behind it. Measured 2026-08-07 on a scratch drive: a
hand-moved file reaches `service/drives.py` line 363 with `sha in attached`, is hashed, and is
then counted in **no** bucket -- `linked=0, unmatched=0, unreadable=0, absent=0` -- while the
catalog goes on naming the old path. `attach_drive` returns a clean result about a wrong record.
That is what `reconcile` has to see.
"""

from __future__ import annotations

from truestill_core.rescan import MovedCopy, reconcile

_A = "a" * 64
_B = "b" * 64
_C = "c" * 64


def test_a_file_where_the_catalog_says_it_is_is_placed_and_never_read() -> None:
    """PLACED is decided from paths alone: nothing is passed in `identified` for it."""
    report = reconcile(
        recorded={"Camera/2014/a.jpg": _A},
        on_disk=["Camera/2014/a.jpg"],
        identified={},
    )
    assert report.placed == ("Camera/2014/a.jpg",)
    assert report.moved == ()
    assert report.stray == ()
    assert report.unaccounted == ()
    assert report.reconciled


def test_a_hand_moved_file_is_a_move_and_not_a_loss() -> None:
    """THE CASE THIS EXISTS FOR. Same content, different path: the record is stale, not wrong.

    Reported as MOVED and never as UNACCOUNTED - calling it missing is the false alarm that
    teaches a user to ignore the report, and `verify` already makes it (`(aba)` symptom 1).
    """
    report = reconcile(
        recorded={"Camera/2014/a.jpg": _A},
        on_disk=["Camera/2015/a.jpg"],
        identified={"Camera/2015/a.jpg": _A},
    )
    assert report.moved == (
        MovedCopy(sha256=_A, recorded="Camera/2014/a.jpg", found=("Camera/2015/a.jpg",)),
    )
    assert report.unaccounted == (), "a file that is right there must never read as missing"
    assert report.stray == (), "its new path is explained by the move, so it is not also stray"


def test_content_the_catalog_does_not_know_is_stray() -> None:
    report = reconcile(recorded={}, on_disk=["Camera/x.jpg"], identified={"Camera/x.jpg": _B})
    assert report.stray == ("Camera/x.jpg",)
    assert report.moved == ()


def test_a_record_whose_content_is_nowhere_is_unaccounted_and_stays_a_question() -> None:
    report = reconcile(recorded={"Camera/gone.jpg": _C}, on_disk=[], identified={})
    assert report.unaccounted == ("Camera/gone.jpg",)
    assert report.moved == ()


def test_a_second_copy_of_placed_content_is_stray_not_silence() -> None:
    """`file_copies` holds one path per content per drive, so the extra copy has no record.

    Counting it as placed would invent a record; dropping it is the uncounted-outcome defect
    this module was written after finding in `attach_drive`.
    """
    report = reconcile(
        recorded={"Camera/a.jpg": _A},
        on_disk=["Camera/a.jpg", "Backup/a.jpg"],
        identified={"Backup/a.jpg": _A},
    )
    assert report.placed == ("Camera/a.jpg",)
    assert report.stray == ("Backup/a.jpg",)
    assert report.moved == (), "the record is not stale - the file is where it says"


def test_content_found_at_two_paths_reports_both_rather_than_choosing() -> None:
    """Ambiguity is carried, not resolved. A repair must decline it; it cannot if we pick here."""
    report = reconcile(
        recorded={"Camera/a.jpg": _A},
        on_disk=["X/a.jpg", "Y/a.jpg"],
        identified={"X/a.jpg": _A, "Y/a.jpg": _A},
    )
    assert len(report.moved) == 1
    assert report.moved[0].found == ("X/a.jpg", "Y/a.jpg")
    assert report.stray == (), "both paths are explained by the one move"


def test_the_buckets_are_disjoint_and_exhaustive_over_both_inputs() -> None:
    """Every record lands in exactly one bucket, and so does every file that was hashed.

    Written as an identity rather than as counts: a bucket added later that forgets to be
    disjoint fails here instead of double-counting on a screen (§9's report-bucket rule).
    """
    recorded = {"p.jpg": _A, "moved.jpg": _B, "gone.jpg": _C}
    identified = {"elsewhere/moved.jpg": _B, "unknown.jpg": "d" * 64}
    report = reconcile(
        recorded=recorded,
        on_disk=["p.jpg", "elsewhere/moved.jpg", "unknown.jpg"],
        identified=identified,
    )

    accounted_records = len(report.placed) + len(report.moved) + len(report.unaccounted)
    assert accounted_records == len(recorded)

    claimed = {path for entry in report.moved for path in entry.found}
    assert claimed | set(report.stray) == set(identified)
    assert not (claimed & set(report.stray)), "a path cannot be both moved-to and stray"


def test_an_unreadable_folder_makes_the_report_incomplete() -> None:
    """The interlock. UNACCOUNTED is a floor, not a count, when the walk could not see it all."""
    report = reconcile(
        recorded={"Locked/a.jpg": _A},
        on_disk=[],
        identified={},
        unreadable_dirs=["Locked"],
    )
    assert report.unaccounted == ("Locked/a.jpg",)
    assert not report.complete, "a record behind a locked folder must not read as a clean absence"
    assert not report.reconciled


def test_an_unreadable_file_makes_the_report_incomplete_too() -> None:
    report = reconcile(recorded={}, on_disk=["x.jpg"], identified={}, unreadable_files=["x.jpg"])
    assert not report.complete
    assert report.stray == (), "a file we could not hash is not evidence of anything"


def test_a_clean_drive_reports_complete_and_reconciled() -> None:
    """The cry-wolf half: an ordinary drive must produce a quiet report (§4).

    Without this, a reconciler that flagged something on every drive would pass every test
    above and be switched off the first time it ran on a healthy library.
    """
    report = reconcile(
        recorded={"Camera/a.jpg": _A, "Camera/b.jpg": _B},
        on_disk=["Camera/a.jpg", "Camera/b.jpg"],
        identified={},
    )
    assert report.reconciled
    assert report.complete
    assert len(report.placed) == 2


def test_hashing_a_placed_file_anyway_does_not_make_it_stray() -> None:
    """Robustness against the caller, not a rule the caller must remember.

    The PLACED rule says a file at its recorded path is never read. Nothing enforces that on
    `reconcile`, so a caller that hashed one anyway must not have its own library reported back
    as unrecorded - a false alarm on the whole drive, from one wrong argument.
    """
    report = reconcile(
        recorded={"Camera/a.jpg": _A},
        on_disk=["Camera/a.jpg"],
        identified={"Camera/a.jpg": _A},  # the caller ignored the PLACED rule
    )
    assert report.placed == ("Camera/a.jpg",)
    assert report.stray == ()
    assert report.reconciled
