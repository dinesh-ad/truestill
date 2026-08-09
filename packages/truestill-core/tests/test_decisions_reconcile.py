"""Merging the documents from several drives into one set of decisions to restore.

**Newest wins PER DECISION, never per document.** That distinction is the whole file. "Take the
newest document's sections" is the obvious implementation and it is how a freshly formatted
backup drive, whose empty document is by definition the newest, erases a full one.

**`date_confirmations` is the exception, and it is not a detail.** Every other decision is
resolved by the document's `written` stamp, because that is when the drive last heard about it.
A corrected date carries its own `confirmed_at` - a drive written last week can hold a
correction a human made today on another machine - and it is the one decision with no second
source, so losing it is unrecoverable. It resolves on `confirmed_at`.

Pure: no drives, no catalogs, no files. Every disagreement case is a value in and a value out.
"""

from __future__ import annotations

from truestill_core.decisions import Decisions, reconcile_documents

_A = "19411f16-8a00-4873-9b32-04c595eebbe1"
_B = "7641a720-2c1f-4f0e-9a5f-2b1d3c4e5f60"
_SHA = "d" * 64


def _doc(
    *,
    uuid: str = _A,
    label: str = "Output",
    written: str = "2026-08-01T00:00:00+00:00",
    **sections: object,
) -> Decisions:
    return Decisions(drive_uuid=uuid, drive_label=label, written=written, **sections)  # type: ignore[arg-type]


def _confirmation(captured_at: str, confirmed_at: str) -> dict[str, str]:
    return {"sha256": _SHA, "captured_at": captured_at, "confirmed_at": confirmed_at}


# --- the case the obvious implementation gets wrong -----------------------------------------


def test_a_stale_drive_can_carry_the_newer_correction() -> None:
    """THE FIRST TEST, AND THE ONE THAT DECIDES THE DESIGN.

    A drive that has not been written to since last week can hold a date correction a human made
    TODAY on another machine - the document is old, the decision inside it is not. Resolving this
    on the document stamp, the way every other section is resolved, silently restores the older
    correction and discards the newer one. It is the only decision with no second source: the
    file reproduces the wrong answer the human overruled, so there is nothing to recompute it
    from.
    """
    stale_drive_new_correction = _doc(
        uuid=_A,
        label="Old backup",
        written="2026-08-01T00:00:00+00:00",
        date_confirmations=(_confirmation("2015-07-05T09:00:00", "2026-08-09T10:00:00"),),
    )
    fresh_drive_old_correction = _doc(
        uuid=_B,
        label="Yesterday",
        written="2026-08-08T00:00:00+00:00",
        date_confirmations=(_confirmation("2015-07-05T11:00:00", "2026-07-01T10:00:00"),),
    )

    merged, _ = reconcile_documents([fresh_drive_old_correction, stale_drive_new_correction])

    assert [c["captured_at"] for c in merged.date_confirmations] == ["2015-07-05T09:00:00"], (
        "the newer correction lost to a fresher document carrying an older one"
    )


# --- newest wins, per decision --------------------------------------------------------------


def test_the_newest_document_wins_a_renamed_trip() -> None:
    """A trip's identity is its DAY SET, not its name - `(abv)`'s lesson. Same days with a
    different name is a RENAME, so the newer name wins; it is not a conflict to report as one."""
    older = _doc(
        uuid=_A,
        written="2026-08-01T00:00:00+00:00",
        trips=({"name": "Kerala", "slug": "kerala", "days": ["2014-08-14", "2014-08-15"]},),
    )
    newer = _doc(
        uuid=_B,
        label="Backup B",
        written="2026-08-09T00:00:00+00:00",
        trips=({"name": "Wayanad", "slug": "wayanad", "days": ["2014-08-14", "2014-08-15"]},),
    )

    merged, report = reconcile_documents([older, newer])

    assert [t["name"] for t in merged.trips] == ["Wayanad"]
    assert [(s.section, s.drive_label, s.count) for s in report.superseded] == [
        ("trips", "Output", 1)
    ], "the loser was not reported"


def test_trips_on_different_days_are_both_kept() -> None:
    """The cry-wolf half: a merge that kept only the newest document's trips would pass the test
    above and lose every trip the other drive knew about."""
    a = _doc(uuid=_A, trips=({"name": "Wayanad", "days": ["2014-08-14"]},))
    b = _doc(
        uuid=_B,
        written="2026-08-09T00:00:00+00:00",
        trips=({"name": "Goa", "days": ["2015-01-01"]},),
    )

    merged, report = reconcile_documents([a, b])

    assert sorted(t["name"] for t in merged.trips) == ["Goa", "Wayanad"]
    assert report.superseded == (), "two trips on different days were treated as a disagreement"


def test_an_empty_document_cannot_erase_a_full_one_by_being_newest() -> None:
    """A FRESHLY FORMATTED BACKUP DRIVE IS THE NEWEST DOCUMENT THERE IS. If "newest wins" is
    applied per document rather than per decision, plugging in a blank drive erases the library's
    names - the exact loss this feature exists to prevent, performed by its own restore."""
    full = _doc(
        uuid=_A,
        written="2026-01-01T00:00:00+00:00",
        trips=({"name": "Wayanad", "days": ["2014-08-14"]},),
        events=({"name": "Gokul Marriage", "signature": "a" * 64},),
        skipped_clusters=("b" * 64,),
        date_confirmations=(_confirmation("2015-07-05T09:00:00", "2020-01-01T00:00:00"),),
        settings={"layout_template": "{yyyy}"},
    )
    blank = _doc(uuid=_B, label="New drive", written="2026-12-31T00:00:00+00:00")

    merged, report = reconcile_documents([full, blank])

    assert [t["name"] for t in merged.trips] == ["Wayanad"]
    assert [e["name"] for e in merged.events] == ["Gokul Marriage"]
    assert merged.skipped_clusters == ("b" * 64,)
    assert len(merged.date_confirmations) == 1
    assert merged.settings == {"layout_template": "{yyyy}"}
    assert report.superseded == (), "an empty drive was reported as superseding anything"


def test_skipped_clusters_are_a_union_because_a_dismissal_cannot_conflict() -> None:
    """Two drives each holding half the dismissals must produce both halves. A signature is
    present or absent; there is no older or newer version of it to lose."""
    a = _doc(uuid=_A, skipped_clusters=("b" * 64,))
    b = _doc(uuid=_B, written="2026-08-09T00:00:00+00:00", skipped_clusters=("c" * 64,))

    merged, _ = reconcile_documents([a, b])

    assert merged.skipped_clusters == ("b" * 64, "c" * 64)


# --- the three cases that had to be decided rather than emerge -------------------------------


def test_a_tie_is_broken_by_drive_uuid_and_not_by_argument_order() -> None:
    """ONE SAVE WRITES TO TWO DRIVES WITH THE SAME STAMP, so ties are ordinary rather than
    exotic. Falling back to argument order would make the answer depend on the order drives
    happened to be listed in, which is dict order wearing a different hat."""
    lower = _doc(uuid=_A, label="A", trips=({"name": "From A", "days": ["2014-08-14"]},))
    higher = _doc(uuid=_B, label="B", trips=({"name": "From B", "days": ["2014-08-14"]},))

    one, _ = reconcile_documents([lower, higher])
    other, _ = reconcile_documents([higher, lower])

    assert [t["name"] for t in one.trips] == ["From A"]
    assert [t["name"] for t in other.trips] == ["From A"], "the answer moved with the input order"


def test_a_document_with_no_stamp_contributes_but_never_overrules() -> None:
    """A hand-edited or truncated document is still someone's names, so it is not discarded - but
    it cannot be trusted to overrule a dated one, so it sorts last. It supplies only what nothing
    else has."""
    undated = _doc(
        uuid=_A,
        label="Hand edited",
        written="",
        trips=(
            {"name": "Wrong", "days": ["2014-08-14"]},
            {"name": "Only here", "days": ["2013-09-13"]},
        ),
    )
    dated = _doc(
        uuid=_B,
        written="2026-08-09T00:00:00+00:00",
        trips=({"name": "Right", "days": ["2014-08-14"]},),
    )

    merged, report = reconcile_documents([undated, dated])

    names = sorted(t["name"] for t in merged.trips)
    assert names == ["Only here", "Right"], "an undated document overruled a dated one"
    assert report.undated == ("Hand edited",)


def test_identical_copies_from_one_save_are_not_reported_as_disagreement() -> None:
    """THE NOISE THIS WOULD OTHERWISE MAKE. One save writes the same document to every drive, so
    most reconciles see several identical copies. Reporting each as a superseded loser would bury
    the one real disagreement in a list of non-events."""
    trips = ({"name": "Wayanad", "days": ["2014-08-14"]},)
    a = _doc(uuid=_A, label="A", trips=trips)
    b = _doc(uuid=_B, label="B", trips=trips)

    merged, report = reconcile_documents([a, b])

    assert [t["name"] for t in merged.trips] == ["Wayanad"]
    assert report.superseded == ()


def test_the_newest_document_wins_a_setting_and_the_others_still_contribute() -> None:
    """Untested until a mutation reversed the precedence and killed nothing.

    Settings are the one section whose disagreements are NOT reported - UI preferences churn per
    machine and per version, so a difference is not evidence of a decision being overruled - and
    that silence is exactly why the precedence itself needs pinning. Nothing else would notice.
    """
    older = _doc(
        uuid=_A,
        written="2026-08-01T00:00:00+00:00",
        settings={"layout_template": "{yyyy}", "ui.text.size": "small"},
    )
    newer = _doc(
        uuid=_B,
        label="Backup B",
        written="2026-08-09T00:00:00+00:00",
        settings={"layout_template": "{yyyy}/{yyyy}-{mm}"},
    )

    merged, report = reconcile_documents([older, newer])

    assert merged.settings["layout_template"] == "{yyyy}/{yyyy}-{mm}", "the older setting won"
    assert merged.settings["ui.text.size"] == "small", "a setting only the older drive had was lost"
    assert report.superseded == (), "a settings difference was reported as an overruled decision"
