"""Applying the documents from several drives: reconcile, apply, and report what did not land.

**Why this is one function rather than three steps a caller sequences.** The reconciled result
carries no drive block by design - each document describes a different drive, so there is no
single answer - which means the drive labels are only restored by looping over the documents
themselves. A restore command that has to *remember* that loop is a restore command that will
one day not, and the symptom is a drive coming back unnamed, which looks like the user never
named it. `apply_documents` does both halves, so there is no sequence to get wrong.
"""

from __future__ import annotations

from pathlib import Path

from truestill_core.catalog import Catalog
from truestill_core.decisions import Decisions, apply_documents, reconcile_documents

_A = "19411f16-8a00-4873-9b32-04c595eebbe1"
_B = "7641a720-2c1f-4f0e-9a5f-2b1d3c4e5f60"


def test_the_reconciled_result_carries_no_drive_block() -> None:
    """The property `apply_documents` is built on. Pinned so nobody later 'fixes' the empty drive
    block by populating it from whichever document happened to be newest - that would invent a
    drive, and quietly stop the per-document loop from being necessary."""
    merged, _ = reconcile_documents(
        [
            Decisions(drive_uuid=_A, drive_label="Output", written="2026-08-01T00:00:00+00:00"),
            Decisions(drive_uuid=_B, drive_label="Backup", written="2026-08-09T00:00:00+00:00"),
        ]
    )

    assert merged.drive_uuid == ""
    assert merged.drive_label == ""


def test_every_drive_gets_its_own_label_back(tmp_path: Path) -> None:
    """A LABEL IS A DECISION - the user typed it - and it is the one decision that cannot be
    merged, because each document is about a different drive. Two drives in, two labels back."""
    documents = [
        Decisions(drive_uuid=_A, drive_label="Output", written="2026-08-01T00:00:00+00:00"),
        Decisions(drive_uuid=_B, drive_label="Backup", written="2026-08-09T00:00:00+00:00"),
    ]

    with Catalog(tmp_path / "fresh.sqlite") as fresh:
        report = apply_documents(fresh, documents)
        labels = {str(r["uuid"]): str(r["label"]) for r in fresh.registered_drives()}

    assert labels == {_A: "Output", _B: "Backup"}
    assert report.applied.applied.get("drive") == 2


def test_an_unmatched_event_survives_the_reconciled_path(tmp_path: Path) -> None:
    """Reported, never guessed - already true of `apply_decisions`, and this proves it still
    holds once the decisions have been through the merge, which is a new path for it."""
    documents = [
        Decisions(
            drive_uuid=_A,
            drive_label="Output",
            written="2026-08-01T00:00:00+00:00",
            events=(
                {
                    "name": "Gokul Marriage",
                    "slug": "g",
                    "start": "2015-10-25",
                    "signature": "a" * 64,
                },
            ),
        )
    ]

    with Catalog(tmp_path / "fresh.sqlite") as fresh:
        report = apply_documents(fresh, documents)

    assert report.applied.unmatched_events == ("Gokul Marriage",)
    assert report.applied.applied.get("events", 0) == 0


def test_a_restore_can_say_what_it_did_not_do(tmp_path: Path) -> None:
    """40 APPLIED AND SILENCE ABOUT 12 UNSCANNED is the same silence class as a preview that
    tallies only part of what it organizes. The counts a surface needs to say "12 corrections are
    waiting for photos this catalog has not scanned yet" have to survive the whole path."""
    documents = [
        Decisions(
            drive_uuid=_A,
            drive_label="Output",
            written="2026-08-01T00:00:00+00:00",
            skipped_clusters=("b" * 64,),
            date_confirmations=(
                {
                    "sha256": "e" * 64,
                    "captured_at": "2015-01-01T00:00:00",
                    "confirmed_at": "2026-01-01",
                },
            ),
        )
    ]

    with Catalog(tmp_path / "fresh.sqlite") as fresh:
        report = apply_documents(fresh, documents)

    assert report.applied.applied.get("skipped_clusters") == 1
    assert report.applied.awaiting_content == {"date_confirmations": 1}
    assert report.applied.already_newer_locally == {}


def test_the_disagreement_between_drives_reaches_the_caller(tmp_path: Path) -> None:
    """The loser is reported, never discarded - and it has to survive being handed back through
    the restore, not only out of `reconcile_documents`."""
    days = ["2014-08-14", "2014-08-15"]
    documents = [
        Decisions(
            drive_uuid=_A,
            drive_label="Old backup",
            written="2026-08-01T00:00:00+00:00",
            trips=(
                {
                    "name": "Kerala",
                    "slug": "kerala",
                    "start": days[0],
                    "end": days[1],
                    "days": days,
                },
            ),
        ),
        Decisions(
            drive_uuid=_B,
            drive_label="Backup B",
            written="2026-08-09T00:00:00+00:00",
            trips=(
                {
                    "name": "Wayanad",
                    "slug": "wayanad",
                    "start": days[0],
                    "end": days[1],
                    "days": days,
                },
            ),
        ),
    ]

    with Catalog(tmp_path / "fresh.sqlite") as fresh:
        report = apply_documents(fresh, documents)
        names = [str(r["name"]) for r in fresh.all_trips()]

    assert names == ["Wayanad"]
    assert [(s.section, s.drive_label, s.count) for s in report.reconciled.superseded] == [
        ("trips", "Old backup", 1)
    ]


def test_restoring_twice_reports_nothing_the_second_time(tmp_path: Path) -> None:
    """Idempotence is a test, not an intention - and a restore is a command people re-run when
    they are not sure it worked the first time, which is exactly when a count that says "2 drives
    restored" again is a lie about what just happened.

    Added after a mutation that re-upserted every drive unconditionally killed no test: the first
    restore looks identical either way, and only the second one tells them apart.
    """
    documents = [
        Decisions(drive_uuid=_A, drive_label="Output", written="2026-08-01T00:00:00+00:00"),
        Decisions(drive_uuid=_B, drive_label="Backup", written="2026-08-09T00:00:00+00:00"),
    ]

    with Catalog(tmp_path / "fresh.sqlite") as fresh:
        first = apply_documents(fresh, documents)
        second = apply_documents(fresh, documents)

    assert first.applied.applied.get("drive") == 2
    assert second.applied.applied.get("drive", 0) == 0, "a second restore re-counted every drive"
    assert sum(second.applied.applied.values()) == 0
