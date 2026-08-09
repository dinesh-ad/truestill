"""Gathering decisions out of a catalog, and applying them back into one.

**The privacy guard runs against a REAL catalog read here, and that is the point of this file.**
`test_decisions_document.py` asserts the document FORMAT carries nothing sensitive. That is a
guard in method and vacuous in effect if the gather then reads a column the format never
contemplated: the format test only ever sees what a test constructed. These tests seed a catalog
with GPS, camera details, source paths, filenames and a `path_hint` setting, gather from it, and
assert on the rendered text.

**`date_confirmations` is the one entry with no second source.** A confirmed date is a human
overruling the evidence, so the file itself reproduces the wrong answer. **Disagreement is the
normal case - it is why the correction exists** - which means an apply cannot use "the file says
otherwise" as a reason to skip. It must apply, and it must never overwrite a confirmation the
local catalog already holds from a LATER moment. Losing one is worse than never applying it.
"""

from __future__ import annotations

import json
from pathlib import Path

from truestill_core.catalog import Catalog
from truestill_core.decisions import (
    apply_decisions,
    gather_decisions,
    to_document,
)
from truestill_core.models import CaptureContext

_UUID = "19411f16-8a00-4873-9b32-04c595eebbe1"
_SHA = "d" * 64


def _seeded(db: Path) -> Catalog:
    """A catalog holding every decision AND every recomputable, sensitive field."""
    catalog = Catalog(db)
    catalog.upsert_drive(uuid=_UUID, label="Output")
    catalog.set_setting("layout_template", "{yyyy}/{yyyy}-{mm}")
    catalog.set_setting(f"path_hint.drive.{_UUID}", "/home/someone/Photos/Backup")
    catalog.record_uploaded(
        source_path="/home/someone/Pictures/Holiday/DSC_0001.jpg",
        original_name="DSC_0001.jpg",
        sha256=_SHA,
        copy_sha256=_SHA,
        perceptual="ff00ff00ff00ff00",
        size=1000,
        captured_at="2015-07-05T11:55:16",
        category="Camera",
        relative="2015/2015-07/DSC_0001.jpg",
        drive_uuid=_UUID,
        capture=CaptureContext(
            camera_make="HTC",
            camera_model="One M8",
            gps_latitude=10.7905,
            gps_longitude=78.7047,
        ),
    )
    catalog.create_trip(
        name="Wayanad",
        slug="wayanad",
        start_date="2014-08-14",
        end_date="2014-08-15",
        days=["2014-08-14", "2014-08-15"],
    )
    catalog.record_skip("b" * 64)
    catalog.confirm_date(_SHA, "2015-07-05T09:00:00", confirmed_by="user")
    return catalog


# --- privacy, against a real catalog read -------------------------------------------------


def test_a_gather_from_a_real_catalog_carries_nothing_sensitive(tmp_path: Path) -> None:
    """THE GUARD THAT MATTERS. Seeded with GPS, camera, a source path, a filename and a
    `path_hint`, then asserted on the rendered document text."""
    with _seeded(tmp_path / "c.sqlite") as catalog:
        gathered = gather_decisions(catalog, _UUID)
    text = json.dumps(to_document(gathered))

    # Asserted on the GATHERED OBJECT first, and that ordering is the whole point. `to_document`
    # filters settings too, so checking only the rendered text passes even when the gather stops
    # filtering - proven by a mutation that removed the gather's filter and broke nothing. Two
    # layers of defence are good; one test that can only see the outer layer is not a guard.
    assert not [k for k in gathered.settings if k.startswith("path_hint")], (
        "the GATHER read a path hint out of the catalog; the document filter is a backstop, "
        "not the guard"
    )

    for banned in (
        "path_hint",
        "/home/someone",
        "DSC_0001",
        "HTC",
        "One M8",
        "10.79",
        "78.70",
        "ff00ff00",
    ):
        assert banned not in text, f"a gather leaked {banned!r} onto a drive"


def test_the_gather_still_carries_the_decisions(tmp_path: Path) -> None:
    """The cry-wolf half: an exclusion that took everything with it would pass the test above."""
    with _seeded(tmp_path / "c.sqlite") as catalog:
        gathered = gather_decisions(catalog, _UUID)

    assert gathered.drive_label == "Output"
    assert gathered.settings["layout_template"] == "{yyyy}/{yyyy}-{mm}"
    assert [t["name"] for t in gathered.trips] == ["Wayanad"]
    assert gathered.trip_days
    assert gathered.skipped_clusters == ("b" * 64,)
    assert [d["sha256"] for d in gathered.date_confirmations] == [_SHA]


# --- idempotence --------------------------------------------------------------------------


def test_applying_twice_changes_nothing_the_second_time(tmp_path: Path) -> None:
    """Idempotence is a test, not an intention."""
    with _seeded(tmp_path / "source.sqlite") as catalog:
        gathered = gather_decisions(catalog, _UUID)

    with Catalog(tmp_path / "fresh.sqlite") as fresh:
        first = apply_decisions(fresh, gathered)
        second = apply_decisions(fresh, gathered)

    assert sum(first.applied.values()) > 0, "the first apply did nothing; the test proves nothing"
    assert sum(second.applied.values()) == 0, f"a second apply changed {second.applied}"


def test_an_apply_reports_what_it_changed(tmp_path: Path) -> None:
    """A restore that says 'done' tells the user nothing about what came back.

    The content is seeded first, because a confirmation for a file this catalog has never scanned
    is deliberately NOT applied - see the test below.
    """
    with _seeded(tmp_path / "source.sqlite") as catalog:
        gathered = gather_decisions(catalog, _UUID)
    with Catalog(tmp_path / "fresh.sqlite") as fresh:
        fresh.record_uploaded(
            source_path="/src/x.jpg",
            original_name="x.jpg",
            sha256=_SHA,
            copy_sha256=_SHA,
            perceptual=None,
            size=1000,
            captured_at="2015-07-05T11:55:16",
            category="Camera",
            relative="2015/x.jpg",
        )
        report = apply_decisions(fresh, gathered)

    assert report.applied.get("trips") == 1
    assert report.applied.get("skipped_clusters") == 1
    assert report.applied.get("date_confirmations") == 1


def test_a_confirmation_for_content_this_catalog_has_not_scanned_is_kept_not_lost(
    tmp_path: Path,
) -> None:
    """A drive can carry a correction for a photo that lives on ANOTHER drive.

    Applying it would mean inventing a `files` row for content this catalog has never seen.
    Instead it is skipped and reported - the document still holds it, so a later scan plus a
    re-apply lands it. Silence here would look identical to success and lose the one decision
    that has no second source.
    """
    with _seeded(tmp_path / "source.sqlite") as catalog:
        gathered = gather_decisions(catalog, _UUID)
    with Catalog(tmp_path / "empty.sqlite") as empty:
        report = apply_decisions(empty, gathered)

    assert report.applied.get("date_confirmations", 0) == 0
    assert "date_confirmations" in report.skipped_newer_locally


# --- date confirmations: the entry with no second source ----------------------------------


def test_a_corrected_date_is_applied_even_though_the_file_disagrees(tmp_path: Path) -> None:
    """DISAGREEMENT IS THE NORMAL CASE - it is why the correction exists. A fresh scan records the
    evidence date; applying must overrule it, exactly as the human did."""
    with _seeded(tmp_path / "source.sqlite") as catalog:
        gathered = gather_decisions(catalog, _UUID)

    db = tmp_path / "rescanned.sqlite"
    with Catalog(db) as fresh:
        fresh.upsert_drive(uuid=_UUID, label="Output")
        fresh.record_uploaded(  # the evidence date, as a rescan would find it
            source_path="/src/DSC_0001.jpg",
            original_name="DSC_0001.jpg",
            sha256=_SHA,
            copy_sha256=_SHA,
            perceptual=None,
            size=1000,
            captured_at="2015-07-05T11:55:16",
            category="Camera",
            relative="2015/2015-07/DSC_0001.jpg",
            drive_uuid=_UUID,
        )
        apply_decisions(fresh, gathered)
        row = fresh._conn.execute(
            "SELECT captured_at, date_source FROM files WHERE sha256=?", (_SHA,)
        ).fetchone()

    assert row["captured_at"] == "2015-07-05T09:00:00", "the human's correction was not restored"
    assert row["date_source"] == "human_confirmed"


def test_a_newer_local_confirmation_is_never_overwritten_by_an_older_one(tmp_path: Path) -> None:
    """LOSING ONE IS WORSE THAN NEVER APPLYING IT. A drive carrying a stale correction must not
    undo a later one the user made on this machine - it is the only decision with no second
    source, so an overwrite is unrecoverable."""
    with _seeded(tmp_path / "source.sqlite") as catalog:
        stale = gather_decisions(catalog, _UUID)

    db = tmp_path / "local.sqlite"
    with Catalog(db) as local:
        local.upsert_drive(uuid=_UUID, label="Output")
        local.record_uploaded(
            source_path="/src/x.jpg",
            original_name="x.jpg",
            sha256=_SHA,
            copy_sha256=_SHA,
            perceptual=None,
            size=1000,
            captured_at="2015-07-05T11:55:16",
            category="Camera",
            relative="2015/x.jpg",
            drive_uuid=_UUID,
        )
        local.confirm_date(_SHA, "2020-01-01T00:00:00", confirmed_by="user")  # later correction
        report = apply_decisions(local, stale)
        kept = local._conn.execute(
            "SELECT captured_at FROM date_confirmations WHERE sha256=?", (_SHA,)
        ).fetchone()

    assert kept["captured_at"] == "2020-01-01T00:00:00", "an older correction overwrote a newer one"
    assert "date_confirmations" in report.skipped_newer_locally


# --- events re-attach only on a signature match -------------------------------------------


def test_an_event_name_re_attaches_only_where_the_signature_matches(tmp_path: Path) -> None:
    """A mismatch means membership changed, which is exactly when the name must not be applied."""
    with Catalog(tmp_path / "source.sqlite") as catalog:
        catalog.upsert_drive(uuid=_UUID, label="Output")
        catalog.record_event(
            name="Gokul Marriage",
            slug="gokul-marriage",
            start_date="2015-10-25",
            file_count=3,
            signature="a" * 64,
        )
        gathered = gather_decisions(catalog, _UUID)

    with Catalog(tmp_path / "fresh.sqlite") as fresh:
        report = apply_decisions(fresh, gathered)

    assert "Gokul Marriage" in report.unmatched_events
    assert report.applied.get("events", 0) == 0
