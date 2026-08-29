"""Restore CREATES the event it can match. `(ahv)` stage 2.

After a catalog rebuild the ``events`` table is empty, so `apply_decisions` found nothing by
signature and every event name was lost - the measured data-loss half of `(ahv)`. The document
deliberately carries no members (a name attached to a fingerprint), so the material to create
from comes from re-clustering this catalog's own timeline: a freshly proposed cluster whose
signature equals the document's IS the membership, and the create takes the document's name plus
the cluster's members. Fixtures go through the front doors throughout: `record_uploaded`,
`record_event`, `gather_decisions`.
"""

from __future__ import annotations

import hashlib
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from truestill_core.catalog import CaptureContext, Catalog
from truestill_core.decisions import Decisions, apply_decisions, apply_documents, gather_decisions
from truestill_core.events import EVENT_MIN_FILES_KEY

_UUID = "11111111-2222-3333-4444-555555555555"
_START = datetime(2019, 7, 12, 10, 30)
_SHAS = tuple(f"sha-{i:04d}" for i in range(6))


def _signature(shas: tuple[str, ...] = _SHAS) -> str:
    return hashlib.sha256("\n".join(sorted(shas)).encode("utf-8")).hexdigest()


def _library(db: Path, *, floor: str | None = "5") -> Catalog:
    """Six close-in-time camera files on one drive - a cluster at floor 5, invisible at 8."""
    catalog = Catalog(db)
    catalog.upsert_drive(uuid=_UUID, label="Photos HDD")
    if floor is not None:
        catalog.set_setting(EVENT_MIN_FILES_KEY, floor)
    for i, sha in enumerate(_SHAS):
        when = _START + timedelta(minutes=i)
        catalog.record_uploaded(
            source_path=f"/src/IMG_{i:04d}.jpg",
            original_name=f"IMG_{i:04d}.jpg",
            sha256=sha,
            perceptual=None,
            size=8,
            captured_at=when.isoformat(),
            category="Camera",
            relative=f"Camera/IMG_{i:04d}.jpg",
            drive_uuid=_UUID,
            capture=CaptureContext(gps_latitude=None, gps_longitude=None),
        )
    return catalog


def _document_with_named_event(tmp_path: Path, name: str = "Morning Market") -> Decisions:
    with _library(tmp_path / "source.sqlite") as source:
        source.record_event(
            name=name,
            slug="morning-market",
            start_date=_START.date().isoformat(),
            file_count=len(_SHAS),
            signature=_signature(),
        )
        return gather_decisions(source, _UUID)


def _linked_shas(db: Path) -> set[str]:
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        rows = conn.execute("SELECT sha256 FROM files WHERE event_id IS NOT NULL")
        return {str(r[0]) for r in rows}
    finally:
        conn.close()


def test_a_rebuilt_catalog_gets_its_named_event_back(tmp_path: Path) -> None:
    """The `(ahv)` scenario: empty events table, same photos, restore - the name returns,
    the row is created from the document's name plus the re-clustered members, and the files
    are LINKED - `(ahv)`'s own warning is a name on screen with no folder behind it.
    Mutation proofs: skip the create and the name is lost; create without `set_event_id`
    and the link assertion dies.
    """
    document = _document_with_named_event(tmp_path)
    db = tmp_path / "rebuilt.sqlite"

    with _library(db) as fresh:
        preview = apply_decisions(fresh, document, apply=False)
        # Preview computed the create and wrote NOTHING - record_event and set_event_id
        # must be unreachable with apply=False.
        assert preview.created_events == ("Morning Market",)
        assert fresh.event_count() == 0
        assert fresh.event_by_signature(_signature()) is None

        report = apply_decisions(fresh, document, apply=True)

        assert report.created_events == ("Morning Market",)
        assert report.unmatched_events == ()
        assert report.applied.get("events") == 1
        row = fresh.event_by_signature(_signature())
        assert row is not None
        assert row["name"] == "Morning Market"
        assert int(row["file_count"]) == len(_SHAS)

    assert _linked_shas(db) == set(_SHAS)


def test_the_floor_comes_from_the_document_not_this_catalog(tmp_path: Path) -> None:
    """The rebuilt catalog holds NO floor setting (default 8); the document carries the user's
    5. A six-file group is proposable only at the document's floor - and the PREVIEW pass runs
    before any setting is written, so reading the catalog there loses the event on the one run
    where the document is authoritative. Mutation proof: prefer the catalog and this dies.
    """
    document = _document_with_named_event(tmp_path)
    assert document.settings.get(EVENT_MIN_FILES_KEY) == "5"

    with _library(tmp_path / "rebuilt.sqlite", floor=None) as fresh:
        preview = apply_decisions(fresh, document, apply=False)

    assert preview.created_events == ("Morning Market",)
    assert preview.unmatched_events == ()


def test_a_second_restore_finds_the_event_and_creates_nothing(tmp_path: Path) -> None:
    """Idempotent, as `apply_decisions` promises of every branch: the second run matches by
    signature, creates no duplicate row, and reports nothing created."""
    document = _document_with_named_event(tmp_path)

    with _library(tmp_path / "rebuilt.sqlite") as fresh:
        apply_decisions(fresh, document, apply=True)
        second = apply_decisions(fresh, document, apply=True)

        assert second.created_events == ()
        assert second.applied.get("events", 0) == 0
        assert fresh.event_count() == 1


def test_the_created_event_takes_the_name_the_authority_rule_chose(tmp_path: Path) -> None:
    """Where `(ahz)`'s named-root authority meets the create: two documents disagree about the
    signature's name, the named root's wins the merge, and the CREATE consumes the merged row -
    so the winner's name is what lands, by construction rather than by a second rule.
    """
    real = _document_with_named_event(tmp_path, name="Morning Market")
    placeholder_events = tuple(
        {**event, "name": "placeholder B", "slug": "placeholder-b"} for event in real.events
    )
    placeholder = Decisions(
        drive_uuid="99999999-8888-7777-6666-555555555555",
        drive_label="rebuilt",
        settings=dict(real.settings),
        events=placeholder_events,
        written="2026-08-27T00:00:00+00:00",
    )
    named_root = Decisions(
        drive_uuid=_UUID,
        drive_label="Photos HDD",
        settings=dict(real.settings),
        events=real.events,
        written="2026-08-26T00:00:00+00:00",  # OLDER - only authority can make it win
    )

    with _library(tmp_path / "rebuilt.sqlite") as fresh:
        report = apply_documents(
            fresh, [placeholder, named_root], apply=True, named_root_uuid=_UUID
        )
        row = fresh.event_by_signature(_signature())

    assert row is not None
    assert row["name"] == "Morning Market"
    assert report.applied.created_events == ("Morning Market",)


def test_a_group_the_library_no_longer_forms_stays_honestly_unmatched(tmp_path: Path) -> None:
    """The never-invent-membership arm: a signature matching neither an event row nor any
    freshly proposed cluster is reported, not guessed at - the code cannot tell a shifted
    membership from a group never named here, and the sentence does not claim to."""
    document = _document_with_named_event(tmp_path)
    shifted = Decisions(
        drive_uuid=document.drive_uuid,
        drive_label=document.drive_label,
        settings=dict(document.settings),
        events=({**document.events[0], "signature": "a" * 64},),
        written=document.written,
    )

    with _library(tmp_path / "rebuilt.sqlite") as fresh:
        report = apply_decisions(fresh, shifted, apply=True)

    assert report.created_events == ()
    assert report.unmatched_events == ("Morning Market",)
