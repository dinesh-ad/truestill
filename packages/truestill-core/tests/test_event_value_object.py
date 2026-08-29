"""Golden proof for the Event value object: paths and catalog rows stay byte-equal.

Captured against the three-dict implementation (assignments / names / event_ids) before
``Event`` landed, then re-asserted after the cutover. Same discipline as
``GOLDEN_PLACEMENTS`` for the Placement refactor: expected values are hand-authored from the
pre-refactor output, not dumped from the code under test.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from truestill_core.catalog import Catalog
from truestill_core.categorize import CategoryMatch, Confidence
from truestill_core.destinations import LocalDestination
from truestill_core.event_review import EventDecision, commit, propose, run_event_stage
from truestill_core.layout import PRESETS
from truestill_core.models import DateSource, Decision, Event, FileHashes, Resolution
from truestill_core.organizer import apply_events, execute

YEAR_FIRST = PRESETS["year-month-event"].scheme()

#: Named-event relatives from ``run_event_stage(..., prompt="Goa Trip")`` on a 10-file cluster
#: starting 2026-06-14 09:00. Pre-``Event`` capture.
GOLDEN_NAMED_PATHS = (
    "2026/2026-06/2026-06-14 - Goa Trip/img0.jpg",
    "2026/2026-06/2026-06-14 - Goa Trip/img1.jpg",
    "2026/2026-06/2026-06-14 - Goa Trip/img2.jpg",
    "2026/2026-06/2026-06-14 - Goa Trip/img3.jpg",
    "2026/2026-06/2026-06-14 - Goa Trip/img4.jpg",
    "2026/2026-06/2026-06-14 - Goa Trip/img5.jpg",
    "2026/2026-06/2026-06-14 - Goa Trip/img6.jpg",
    "2026/2026-06/2026-06-14 - Goa Trip/img7.jpg",
    "2026/2026-06/2026-06-14 - Goa Trip/img8.jpg",
    "2026/2026-06/2026-06-14 - Goa Trip/img9.jpg",
)

#: Catalog ``events`` row for that same naming (id is assigned 1 on a fresh catalog).
GOLDEN_NAMED_EVENT_ROW = ("Goa Trip", "goa-trip", "2026-06-14T09:00:00", 10)

#: ``apply_events`` with no human name: slug folder fallback, default scheme, cross-month
#: consolidation under the start month.
GOLDEN_SLUG_FALLBACK_PATHS = (
    "2026/2026-06/20260630_goa-trip/img0.jpg",
    "2026/2026-06/20260630_goa-trip/img1.jpg",
)

#: Same sources with a recorded name under year-month-event.
GOLDEN_NAMED_YEAR_FIRST_PATHS = (
    "2026/2026-06/2026-06-30 - Goa Trip/img0.jpg",
    "2026/2026-06/2026-06-30 - Goa Trip/img1.jpg",
)

#: On-disk tree + ``files.event_id`` after ``apply_events`` + ``execute(..., events=...)``.
GOLDEN_EXECUTE_DISK_PATHS = (
    "2014/2014-08/2014-08-20 - Goa Trip/IMG_0.jpg",
    "2014/2014-08/2014-08-20 - Goa Trip/IMG_1.jpg",
)
GOLDEN_EXECUTE_EVENT_ROW = ("Goa Trip", "goa-trip", "2014-08-20T14:30:00", 2)

#: Two same-day clusters stay two events (``(ll)``: a day key must not collapse them).
GOLDEN_SAME_DAY_FOLDERS = (
    "2014/2014-08/2014-08-16 - Evening",
    "2014/2014-08/2014-08-16 - Morning",
)
GOLDEN_SAME_DAY_EVENT_ROWS = (
    ("Morning", "morning", "2014-08-16T09:00:00", 12),
    ("Evening", "evening", "2014-08-16T20:00:00", 12),
)


def _camera(i: int, when: datetime) -> Resolution:
    category = CategoryMatch(
        label="Camera", reason="t", confidence=Confidence.MEDIUM, rule="device"
    )
    decision = Decision(
        source=Path(f"/src/img{i}.jpg"),
        category=category,
        captured_at=when,
        date_source=DateSource.EXIF,
        date_tag="DateTimeOriginal",
        relative=Path(f"Camera/{when:%Y}/{when:%m}/img{i}.jpg"),
    )
    return Resolution(decision, FileHashes(f"sha{i:04d}", None), None, None)


def _event_rows(catalog: Catalog) -> tuple[tuple[str, str, str, int], ...]:
    rows = catalog._conn.execute(
        "SELECT name, slug, start_date, file_count FROM events ORDER BY id"
    ).fetchall()
    return tuple(
        (str(r["name"]), str(r["slug"]), str(r["start_date"]), int(r["file_count"])) for r in rows
    )


def test_golden_named_stage_paths_and_catalog_rows(tmp_path: Path) -> None:
    base = datetime(2026, 6, 14, 9, 0)
    resolutions = [_camera(i, base + timedelta(minutes=20 * i)) for i in range(10)]
    with Catalog(tmp_path / "c.sqlite") as catalog:
        out = run_event_stage(resolutions, {}, catalog, apply=True, prompt=lambda _c: "Goa Trip")
        paths = tuple(sorted(r.decision.relative.as_posix() for r in out.resolutions))
        assert paths == GOLDEN_NAMED_PATHS
        assert _event_rows(catalog) == (GOLDEN_NAMED_EVENT_ROW,)
        assert {e.id for e in out.events.values()} == {1}
        assert all(e.name == "Goa Trip" and e.slug == "goa-trip" for e in out.events.values())


def test_golden_slug_fallback_when_name_is_absent() -> None:
    r_jun = _camera(0, datetime(2026, 6, 30, 23, 0))
    r_jul = _camera(1, datetime(2026, 7, 2, 10, 0))
    start = datetime(2026, 6, 30, 23, 0)
    events = {
        str(r_jun.decision.source): Event(start=start, slug="goa-trip", name=None, id=1),
        str(r_jul.decision.source): Event(start=start, slug="goa-trip", name=None, id=1),
    }
    updated = apply_events([r_jun, r_jul], events)
    paths = tuple(sorted(r.decision.relative.as_posix() for r in updated))
    assert paths == GOLDEN_SLUG_FALLBACK_PATHS


def test_golden_named_year_first_paths() -> None:
    r_jun = _camera(0, datetime(2026, 6, 30, 23, 0))
    r_jul = _camera(1, datetime(2026, 7, 2, 10, 0))
    start = datetime(2026, 6, 30, 23, 0)
    events = {
        str(r_jun.decision.source): Event(start=start, slug="goa-trip", name="Goa Trip", id=1),
        str(r_jul.decision.source): Event(start=start, slug="goa-trip", name="Goa Trip", id=1),
    }
    updated = apply_events([r_jun, r_jul], events, scheme=YEAR_FIRST)
    paths = tuple(sorted(r.decision.relative.as_posix() for r in updated))
    assert paths == GOLDEN_NAMED_YEAR_FIRST_PATHS


def test_golden_execute_disk_and_files_event_id(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    photos = []
    for i in range(2):
        path = src / f"IMG_{i}.jpg"
        path.write_bytes(b"photo-%d" % i)
        photos.append(path)
    base = datetime(2014, 8, 20, 14, 30)
    resolutions = []
    for i, path in enumerate(photos):
        category = CategoryMatch(
            label="Camera", reason="t", confidence=Confidence.MEDIUM, rule="device"
        )
        decision = Decision(
            source=path,
            category=category,
            captured_at=base,
            date_source=DateSource.EXIF,
            date_tag="DateTimeOriginal",
            relative=Path(f"Camera/2014/08/{path.name}"),
        )
        resolutions.append(Resolution(decision, FileHashes(f"sha-real-{i}", None), None, None))

    with Catalog(tmp_path / "c.sqlite") as catalog:
        event_id = catalog.record_event(
            name="Goa Trip",
            slug="goa-trip",
            start_date=base.isoformat(),
            file_count=2,
            signature="sig-baseline",
        )
        events = {
            str(p): Event(start=base, slug="goa-trip", name="Goa Trip", id=event_id) for p in photos
        }
        routed = apply_events(resolutions, events, scheme=YEAR_FIRST)
        dest = tmp_path / "out"
        execute(routed, LocalDestination(dest), catalog, apply=True, events=events)
        landed = tuple(sorted(p.relative_to(dest).as_posix() for p in dest.rglob("*.jpg")))
        assert landed == GOLDEN_EXECUTE_DISK_PATHS
        assert _event_rows(catalog) == (GOLDEN_EXECUTE_EVENT_ROW,)
        file_rows = catalog._conn.execute(
            "SELECT original_name, event_id, relative FROM files ORDER BY original_name"
        ).fetchall()
        assert [(r["original_name"], r["event_id"], r["relative"]) for r in file_rows] == [
            ("IMG_0.jpg", 1, GOLDEN_EXECUTE_DISK_PATHS[0]),
            ("IMG_1.jpg", 1, GOLDEN_EXECUTE_DISK_PATHS[1]),
        ]


def test_golden_same_day_clusters_stay_separate_events(tmp_path: Path) -> None:
    """``(ll)``: 2014-08-16 alone can hold two clusters; a day key would silently merge them."""
    morning = [
        _camera(i, datetime(2014, 8, 16, 9, 0) + timedelta(minutes=2 * i)) for i in range(12)
    ]
    evening = [
        _camera(100 + i, datetime(2014, 8, 16, 20, 0) + timedelta(minutes=2 * i)) for i in range(12)
    ]
    with Catalog(tmp_path / "c.sqlite") as catalog:
        clusters = propose(morning + evening, {}, min_files=8)
        assert len(clusters) == 2
        assert clusters[0].start.date() == clusters[1].start.date()
        out = commit(
            morning + evening,
            [EventDecision(clusters[0], "Morning"), EventDecision(clusters[1], "Evening")],
            catalog,
            scheme=YEAR_FIRST,
        )
        folders = tuple(sorted({r.decision.relative.parent.as_posix() for r in out.resolutions}))
        assert folders == GOLDEN_SAME_DAY_FOLDERS
        assert _event_rows(catalog) == GOLDEN_SAME_DAY_EVENT_ROWS
        assert {e.id for e in out.events.values()} == {1, 2}
        assert {e.start for e in out.events.values()} == {clusters[0].start, clusters[1].start}
