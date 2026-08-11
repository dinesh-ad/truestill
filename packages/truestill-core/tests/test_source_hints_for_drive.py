"""The rows a folder-name suggestion is derived from, and the query it must not disturb.

`camera_copies_for_events` is the CLUSTERING input. Widening it to carry `source_path` would let
a display concern change what clusters, so this is a separate read over the same population.
The duplication is deliberate and the test below is what keeps the two honest about it.
"""

from __future__ import annotations

from pathlib import Path

from truestill_core.catalog import Catalog

_WHEN = "2015-10-25T19:08:00"


def _seed(catalog: Catalog) -> None:
    catalog.upsert_drive(uuid="D1", label="Drive A")
    catalog.upsert_drive(uuid="D2", label="Drive B")
    rows = [
        ("a", "/src/Rock Climbing/a.jpg", _WHEN, "Camera", "D1"),
        ("b", "/src/Rock Climbing/b.jpg", _WHEN, "Camera", "D1"),
        ("c", "", _WHEN, "Camera", "D1"),  # source path recorded EMPTY
        ("d", "/src/Screenshots/d.png", _WHEN, "Screenshots", "D1"),  # not Camera
        ("e", "/src/Rock Climbing/e.jpg", None, "Camera", "D1"),  # undated
        ("f", "/src/Elsewhere/f.jpg", _WHEN, "Camera", "D2"),  # another drive
    ]
    for sha, source, captured, category, drive in rows:
        catalog.record_uploaded(
            source_path=source,
            original_name=f"{sha}.jpg",
            sha256=sha,
            copy_sha256=sha,
            perceptual=None,
            size=10,
            captured_at=captured,
            category=category,
            relative=f"2015/{sha}.jpg",
            drive_uuid=drive,
        )


def _hints(catalog: Catalog, drive: str = "D1") -> dict[str, tuple[str, str]]:
    return {
        str(row["sha256"]): (str(row["source_path"]), str(row["captured_at"]))
        for row in catalog.source_hints_for_drive(drive)
    }


def test_it_returns_the_source_path_and_capture_date_the_suggester_needs(tmp_path: Path) -> None:
    with Catalog(tmp_path / "c.sqlite") as catalog:
        _seed(catalog)
        hints = _hints(catalog)

    assert hints["a"] == ("/src/Rock Climbing/a.jpg", _WHEN)
    assert hints["b"] == ("/src/Rock Climbing/b.jpg", _WHEN)


def test_a_row_whose_source_path_is_empty_is_still_returned(tmp_path: Path) -> None:
    """It must count in the DENOMINATOR. Dropping it here would silently strengthen every
    majority, which is the opposite of "missing evidence weakens a claim".

    EMPTY, not NULL: `files.source_path` is `TEXT NOT NULL`, so the absent case the suggester
    guards against cannot arrive as NULL - it arrives as `''`, which the schema does accept. The
    fallback was designed against a shape the schema forbids; this pins the shape it permits.
    """
    with Catalog(tmp_path / "c.sqlite") as catalog:
        _seed(catalog)
        hints = _hints(catalog)

    assert "c" in hints
    assert hints["c"][0] == ""


def test_it_matches_the_clustering_population_exactly(tmp_path: Path) -> None:
    """Same drive, same Camera-and-dated filter. A suggestion may only describe what clustered:
    a hint for a file no cluster contains could never be shown, and a cluster member with no hint
    would silently leave the denominator."""
    with Catalog(tmp_path / "c.sqlite") as catalog:
        _seed(catalog)
        hinted = set(_hints(catalog))
        clustered = {str(row["sha256"]) for row in catalog.camera_copies_for_events("D1")}

    assert hinted == clustered
    assert hinted == {"a", "b", "c"}  # not the screenshot, not the undated, not the other drive


def test_the_clustering_query_is_not_widened_to_carry_display_data(tmp_path: Path) -> None:
    """PROVENANCE, not outcome. `camera_copies_for_events` decides what CLUSTERS; adding
    `source_path` to it would let a suggestion change the grouping it is supposed to describe.
    Asserting its exact column set is what makes that impossible to do by accident.
    """
    with Catalog(tmp_path / "c.sqlite") as catalog:
        _seed(catalog)
        row = catalog.camera_copies_for_events("D1")[0]

    assert set(row.keys()) == {"sha256", "captured_at", "gps_latitude", "gps_longitude"}
