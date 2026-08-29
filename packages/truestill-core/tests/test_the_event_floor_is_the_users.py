"""Every event-proposing entry point clusters at the floor the USER set. `(ahv)` stage 1.

``events.min_files`` was read by the app's trip review and by nothing else: `propose` and
`propose_from_catalog` clustered at the hard default of 8, so a lowered floor held on the
catalog was honoured on one surface and silently ignored on the others. `propose` now REQUIRES
the floor (no default to forget), and the catalog-owning entry points read
`EventSettings.from_catalog` themselves. Fixtures go through the catalog's own front door
(`record_uploaded`), not row inserts.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from truestill_core.catalog import CaptureContext, Catalog
from truestill_core.event_review import propose_from_catalog
from truestill_core.events import EVENT_MIN_FILES_KEY

_START = datetime(2019, 7, 12, 10, 30)


def _catalog_with_six_camera_files(db: Path) -> Catalog:
    catalog = Catalog(db)
    catalog.upsert_drive(uuid="drive-1", label="Photos HDD")
    for i in range(6):
        when = _START + timedelta(minutes=i)
        catalog.record_uploaded(
            source_path=f"/src/IMG_{i:04d}.jpg",
            original_name=f"IMG_{i:04d}.jpg",
            sha256=f"sha-{i:04d}",
            perceptual=None,
            size=8,
            captured_at=when.isoformat(),
            category="Camera",
            relative=f"Camera/IMG_{i:04d}.jpg",
            drive_uuid="drive-1",
            capture=CaptureContext(gps_latitude=None, gps_longitude=None),
        )
    return catalog


def test_propose_from_catalog_clusters_at_the_stored_floor(tmp_path: Path) -> None:
    """Six close-in-time camera files: invisible at the default floor of 8, one cluster at
    the user's stored floor of 5. Mutation proof: hard-code the default back and this dies.
    """
    with _catalog_with_six_camera_files(tmp_path / "cat.sqlite") as catalog:
        assert propose_from_catalog(catalog, "drive-1") == []

        catalog.set_setting(EVENT_MIN_FILES_KEY, "5")
        clusters = propose_from_catalog(catalog, "drive-1")

    assert [len(c.items) for c in clusters] == [6]
