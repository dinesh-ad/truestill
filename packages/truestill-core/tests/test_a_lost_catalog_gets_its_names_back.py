"""The recovery sequence, end to end: lose the catalog, rebuild, restore. `(ahv)` stage 3.

`(ahv)` was measured as a five-step sequence on a real 353-file library - name groups, publish
the document, lose the catalog, rebuild by re-organizing, restore - and the outcome was that
**all three event names were lost**. Stage 2 built the create; this file is that sequence as a
regression test, at the level where it can run in the suite: the document really is written to
and read back from a drive root, the rebuilt catalog really holds no events, and the assertions
are the user's own question - *are my names back, and are the photos under them*.

⚠ **Both arms live here on purpose.** A file proving only the create would pass a fix that
creates indiscriminately, which would be worse than the defect: it would manufacture membership
the library no longer has. The second test is the group that genuinely no longer forms, and it
must still come back honestly named as unmatched with nothing created.
"""

from __future__ import annotations

import hashlib
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from truestill_core.catalog import CaptureContext, Catalog
from truestill_core.decisions import (
    apply_documents,
    gather_decisions,
    read_decisions,
    write_decisions,
)

_DEST = "11111111-2222-3333-4444-555555555555"
_REBUILT = "99999999-8888-7777-6666-555555555555"
_START = datetime(2019, 7, 12, 10, 30)
_MARKET = tuple(f"market-{i:04d}" for i in range(8))
_TEMPLE = tuple(f"temple-{i:04d}" for i in range(8))


def _signature(shas: tuple[str, ...]) -> str:
    return hashlib.sha256("\n".join(sorted(shas)).encode("utf-8")).hexdigest()


def _record(catalog: Catalog, shas: tuple[str, ...], *, drive: str, start: datetime) -> None:
    """Camera files close in time - one cluster per group, through the catalog's front door."""
    for i, sha in enumerate(shas):
        when = start + timedelta(minutes=i)
        catalog.record_uploaded(
            source_path=f"/src/{sha}.jpg",
            original_name=f"{sha}.jpg",
            sha256=sha,
            perceptual=None,
            size=8,
            captured_at=when.isoformat(),
            category="Camera",
            relative=f"Camera/{sha}.jpg",
            drive_uuid=drive,
            capture=CaptureContext(gps_latitude=None, gps_longitude=None),
        )


def _library_with_named_groups(db: Path, root: Path) -> None:
    """Steps before the loss: organize, name a trip and two events, publish to the drive."""
    with Catalog(db) as catalog:
        catalog.upsert_drive(uuid=_DEST, label="Photos HDD")
        _record(catalog, _MARKET, drive=_DEST, start=_START)
        _record(catalog, _TEMPLE, drive=_DEST, start=_START + timedelta(days=40))
        for name, slug, shas, start in (
            ("Morning Market", "morning-market", _MARKET, _START),
            ("Temple Visit", "temple-visit", _TEMPLE, _START + timedelta(days=40)),
        ):
            catalog.record_event(
                name=name,
                slug=slug,
                start_date=start.date().isoformat(),
                file_count=len(shas),
                signature=_signature(shas),
            )
        catalog.create_trip(
            name="Bangalore Dec 2009",
            slug="bangalore-dec-2009",
            start_date=_START.date().isoformat(),
            end_date=_START.date().isoformat(),
            days=[_START.date().isoformat()],
        )
        outcome = write_decisions(root, gather_decisions(catalog, _DEST))
    assert outcome.written, outcome


def _rebuilt_catalog(db: Path, *, groups: tuple[tuple[str, ...], ...]) -> None:
    """The catalog after the loss: the same photographs re-scanned, and NO events at all."""
    with Catalog(db) as catalog:
        catalog.upsert_drive(uuid=_REBUILT, label="rebuilt")
        starts = {_MARKET: _START, _TEMPLE: _START + timedelta(days=40)}
        for shas in groups:
            _record(catalog, shas, drive=_REBUILT, start=starts[shas])
        assert catalog.event_count() == 0


def _event_names(db: Path) -> set[str]:
    """The names a person would see. Asserted APART from the linkage below, because the two
    fail separately and mean different things - see the test's own note on `(ahv)`'s warning."""
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        return {str(r[0]) for r in conn.execute("SELECT name FROM events")}
    finally:
        conn.close()


def _linked(db: Path, name: str) -> int:
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        return int(
            conn.execute(
                "SELECT COUNT(*) FROM files WHERE event_id = "
                "(SELECT id FROM events WHERE name = ?)",
                (name,),
            ).fetchone()[0]
        )
    finally:
        conn.close()


def test_the_names_come_back_with_their_photos_under_them(tmp_path: Path) -> None:
    """The sequence `(ahv)` measured, with the outcome it asked for.

    Fails on stage 1's tree (`6ae5219`): with no create, both names land in `unmatched_events`
    and nothing is written. Mutation proofs: revert the create and the names are lost; drop
    `set_event_id` and the names come back with **no photos under them** - which is the failure
    `(ahv)` warned about, a name on screen with no folder behind it, and it fails differently.
    """
    root = tmp_path / "dest"
    root.mkdir()
    _library_with_named_groups(tmp_path / "before.sqlite", root)

    rebuilt = tmp_path / "rebuilt.sqlite"
    _rebuilt_catalog(rebuilt, groups=(_MARKET, _TEMPLE))

    document = read_decisions(root)
    assert document.found
    assert document.decisions is not None
    with Catalog(rebuilt) as catalog:
        report = apply_documents(catalog, [document.decisions], apply=True, named_root_uuid=_DEST)

    # ⚠ **THE TWO HALVES ARE ASSERTED APART, AND THE ORDER IS DELIBERATE.** The name coming back
    # and the photographs being under it are different claims that fail for different reasons,
    # and `(ahv)` named the second one as the trap: *a name on screen with no folder behind it*.
    # Proved by mutation - reverting the create fails the first assertion (the name never
    # returns), dropping `set_event_id` passes it and fails the second (the name returns empty).
    # A report-field assertion first would have failed on stage 1's tree with an `AttributeError`,
    # which proves a field was added rather than that a library was recovered, so it goes last.
    assert _event_names(rebuilt) == {"Morning Market", "Temple Visit"}
    assert _linked(rebuilt, "Morning Market") == len(_MARKET)
    assert _linked(rebuilt, "Temple Visit") == len(_TEMPLE)
    assert report.applied.unmatched_events == ()
    assert sorted(report.applied.created_events) == ["Morning Market", "Temple Visit"]
    # The trip half of the same sequence, which restore could always do: created from the days
    # the document carries. Asserted here so the sequence's two halves are one story.
    assert report.applied.applied.get("trips") == 1


def test_a_group_the_library_no_longer_forms_is_still_reported_not_invented(
    tmp_path: Path,
) -> None:
    """The other arm, and the reason both live in one file: the rebuilt library holds only ONE
    of the two groups, so the second's fingerprint matches nothing. It must be reported as
    unmatched with nothing created - a fix that created indiscriminately would pass the test
    above and fail here, having manufactured a group the photographs do not form.
    """
    root = tmp_path / "dest"
    root.mkdir()
    _library_with_named_groups(tmp_path / "before.sqlite", root)

    rebuilt = tmp_path / "rebuilt.sqlite"
    _rebuilt_catalog(rebuilt, groups=(_MARKET,))  # Temple Visit's photographs are gone

    document = read_decisions(root)
    assert document.decisions is not None
    with Catalog(rebuilt) as catalog:
        report = apply_documents(catalog, [document.decisions], apply=True, named_root_uuid=_DEST)

    assert _event_names(rebuilt) == {"Morning Market"}
    assert _linked(rebuilt, "Morning Market") == len(_MARKET)
    assert _linked(rebuilt, "Temple Visit") == 0
    assert report.applied.unmatched_events == ("Temple Visit",)
    assert report.applied.created_events == ("Morning Market",)
