"""Reviewing trips on an organized drive must reach the same boundaries as a fresh import.

**The bug.** `cluster_camera` cuts an event boundary when consecutive photos are more than
`DEFAULT_GPS_JUMP_KM` apart. A fresh import supplies those coordinates
(`gather_camera_items` -> `EventItem.gps`); the organized-drive path built `EventItem` with
`gps` defaulting to `None` and `camera_copies_for_events` selected only `sha256, captured_at`.
Since the jump-cut needs `here is not None and nxt is not None`, **it could never fire on that
path** - so the same photos produced different trips depending on which screen you reviewed
them from. `(kk)` made the coordinates available; this makes the already-validated logic run.

**No algorithm changed.** Same jump-cut, same threshold, same clustering. The only difference is
that one of the two callers now supplies the input it was always meant to.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest
from truestill_core.catalog import Catalog
from truestill_core.event_review import propose_from_catalog
from truestill_core.events import EventCandidate, EventItem, cluster_camera
from truestill_core.models import CaptureContext
from truestill_core.trip_review import _camera_items

#: Two places far enough apart that the jump-cut must fire between them.
_HOME = (12.9716, 77.5946)  # Bengaluru
_AWAY = (11.6854, 76.1320)  # Wayanad, ~180 km
#: Same city, metres apart: a jump-cut here would be a false boundary.
_NEXT_DOOR = (12.9720, 77.5950)

_START = datetime(2014, 8, 14, 19, 46, 0)


def _plan(
    places: list[tuple[float, float] | None], *, step_s: int = 30
) -> list[tuple[str, datetime, tuple[float, float] | None]]:
    """``(sha, when, gps)`` for a run of photos taken a few seconds apart.

    The times are deliberately tight so **no time-based boundary can fire** - any split in these
    fixtures is the GPS jump-cut and nothing else.
    """
    return [
        (f"sha{i:04d}", _START + timedelta(seconds=step_s * i), place)
        for i, place in enumerate(places)
    ]


def _fresh_path(plan: list[tuple[str, datetime, tuple[float, float] | None]]) -> list[int]:
    """Cluster sizes as a fresh import produces them, straight through `cluster_camera`."""
    items = [EventItem(key=sha, captured_at=when, sha256=sha, gps=gps) for sha, when, gps in plan]
    # Production defaults on both sides. Passing a different `min_files` to one of
    # them would compare two different algorithms and call the result parity.
    return _sizes(cluster_camera(items))


def _drive_path(
    db: Path, plan: list[tuple[str, datetime, tuple[float, float] | None]]
) -> list[int]:
    """Cluster sizes as the organized-drive review produces them, out of the catalog."""
    with Catalog(db) as catalog:
        catalog.upsert_drive(uuid="drive-1", label="Photos HDD")
        for sha, when, gps in plan:
            catalog.record_uploaded(
                source_path=f"/src/{sha}.jpg",
                original_name=f"{sha}.jpg",
                sha256=sha,
                perceptual=None,
                size=8,
                captured_at=when.isoformat(),
                category="Camera",
                relative=f"Camera/{sha}.jpg",
                drive_uuid="drive-1",
                capture=CaptureContext(
                    gps_latitude=None if gps is None else gps[0],
                    gps_longitude=None if gps is None else gps[1],
                ),
            )
        return _sizes(propose_from_catalog(catalog, "drive-1"))


def _sizes(candidates: list[EventCandidate]) -> list[int]:
    """Cluster sizes in time order - the shape of the boundaries, independent of naming."""
    return [len(c.items) for c in sorted(candidates, key=lambda c: c.items[0].captured_at)]


def test_a_gps_jump_splits_the_run_on_the_organized_drive_too(tmp_path: Path) -> None:
    """The bug, stated directly: this path could not cut on distance at all."""
    plan = _plan([_HOME] * 10 + [_AWAY] * 10)

    assert _drive_path(tmp_path / "c.sqlite", plan) == [10, 10], (
        "180 km between consecutive photos must end an event, on this path as on the other"
    )


def test_both_paths_agree_on_the_same_photos(tmp_path: Path) -> None:
    """The property the bug violated. Asserted directly rather than inferred from two numbers.

    Before `(kk)`: fresh gave [10, 10] and the drive gave [20] - the same library, two answers,
    decided by which screen the user happened to open.
    """
    plan = _plan([_HOME] * 10 + [_AWAY] * 10)

    fresh = _fresh_path(plan)
    drive = _drive_path(tmp_path / "c.sqlite", plan)

    assert fresh == drive == [10, 10]


def test_photos_without_coordinates_cluster_exactly_as_before(tmp_path: Path) -> None:
    """Cry-wolf half, and it is the majority case: most libraries are mostly GPS-less.

    With no coordinates the jump-cut is inert and only time decides, which is precisely the
    behaviour this path had before the change. It must not move.
    """
    plan = _plan([None] * 20)

    fresh = _fresh_path(plan)
    drive = _drive_path(tmp_path / "c.sqlite", plan)

    assert fresh == drive == [20], "no coordinates, no distance boundary - time alone"


def test_a_short_hop_does_not_invent_a_boundary(tmp_path: Path) -> None:
    """The other cry-wolf half: coordinates that are present but close must not split a run."""
    plan = _plan([_HOME] * 10 + [_NEXT_DOOR] * 10)

    assert _drive_path(tmp_path / "c.sqlite", plan) == [20]


def test_null_island_is_a_location_and_not_a_missing_one(tmp_path: Path) -> None:
    """`0.0, 0.0` is off the coast of Africa. A reader using truthiness drops it and the
    jump-cut then silently does not fire - the same trap `(kk)`'s write side guards."""
    plan = _plan([(0.0, 0.0)] * 10 + [_AWAY] * 10)

    assert _drive_path(tmp_path / "c.sqlite", plan) == [10, 10], (
        "Null Island to Wayanad is a jump; treating 0.0 as absent would miss it"
    )


def test_a_mixed_library_only_cuts_where_both_ends_are_known(tmp_path: Path) -> None:
    """Missing GPS is ordinary, so a gap in coverage must not become a boundary.

    The jump-cut requires both neighbours to have coordinates. Two known-and-distant photos
    separated by an unlocated one produce no cut between them, which is the honest answer:
    nothing was measured across that pair.
    """
    plan = _plan([_HOME] * 5 + [None] + [_AWAY] * 5)

    assert _drive_path(tmp_path / "c.sqlite", plan) == [11]


@pytest.mark.parametrize("path_name", ["fresh", "drive"])
def test_neither_path_needs_the_photo_files_to_exist(tmp_path: Path, path_name: str) -> None:
    """Anti-vacuity: these fixtures never write a JPEG, so a test that quietly re-read the
    source would fail rather than pass on data it fetched a second way."""
    plan = _plan([_HOME] * 10 + [_AWAY] * 10)
    sizes = _fresh_path(plan) if path_name == "fresh" else _drive_path(tmp_path / "c.sqlite", plan)

    assert sizes == [10, 10]
    assert not list(tmp_path.glob("*.jpg"))


def test_the_trip_reviewers_shared_builder_carries_the_coordinates(tmp_path: Path) -> None:
    """`trip_review._camera_items` is a second copy of the same builder and needs its own test.

    A mutation proof showed it was uncovered: every test above goes through
    `event_review.propose_from_catalog`, and dropping `gps` from *this* builder changed nothing
    they assert. That is the "repair reached one copy and not its twin" defect this repo names.

    **Asserted on the builder rather than through `propose_trips_from_catalog`, deliberately.**
    A GPS split within one day changes the Stage-1 clusters but not the *trips* - a trip needs
    consecutive days - so the difference is invisible at that level and a test written there
    would pass while the bug was present. It is visible here, and to `assemble_trip_review`,
    which is the other consumer of these items.
    """
    db = tmp_path / "c.sqlite"
    _drive_path(db, _plan([_HOME] * 10 + [_AWAY] * 10))

    with Catalog(db) as catalog:
        items = _camera_items(catalog, "drive-1")

    assert len(items) == 20
    assert all(item.gps is not None for item in items), (
        "this builder must hand coordinates to the clusterer, exactly as its twin does"
    )
    assert _sizes(cluster_camera(items)) == [10, 10]
