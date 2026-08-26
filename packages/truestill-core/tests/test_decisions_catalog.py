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
    Decisions,
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
    # ⚠ **`confirmed_at` is pinned, because `confirm_date` stamps it with the CURRENT time and the
    # leak test below is a substring scan.** A live timestamp renders as
    # `...T06:45:10.790587+00:00`, so whenever the seconds are `10` and the microseconds open `79`
    # the document literally contains `10.79` - the banned GPS latitude seeded above. Roughly one
    # run in six thousand: it went red on Windows on 2026-08-26, on a commit that touched none of
    # this. **A substring assertion needs a deterministic subject**, so the fixture supplies one
    # rather than the test excluding a field - excluding it would also stop the scan from ever
    # seeing a real leak into that column.
    catalog._conn.execute(
        "UPDATE date_confirmations SET confirmed_at = ?", ("2026-01-02T03:04:05.000006+00:00",)
    )
    catalog._conn.commit()
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
    assert gathered.trips[0]["days"] == ["2014-08-14", "2014-08-15"]
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
    # `awaiting_content`, not `already_newer_locally`: nothing here is newer, this catalog has
    # simply never seen the photo. The two used to share one field, so this assertion passed
    # whichever branch fired - see `(abx)`.
    assert report.awaiting_content == {"date_confirmations": 1}
    assert report.already_newer_locally == {}


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
    # The opposite meaning to the test above, and now a different field: the local copy is newer,
    # so there is nothing for the user to do. Both assertions used to read the same field.
    assert report.already_newer_locally == {"date_confirmations": 1}
    assert report.awaiting_content == {}


# --- trips: identity has to survive leaving this catalog -----------------------------------


def _days_by_trip(catalog: Catalog) -> dict[str, list[str]]:
    """Trip name -> the days it claims, read straight out of the tables.

    Asserted on days rather than on names because a trip that came back under the right name
    holding the WRONG days is the failure this file exists to catch, and a name-only assertion
    is satisfied by it.
    """
    rows = catalog._conn.execute(
        "SELECT t.name AS name, d.day AS day FROM trip_days d"
        " JOIN trips t ON t.id = d.trip_id ORDER BY d.day"
    )
    days: dict[str, list[str]] = {}
    for row in rows:
        days.setdefault(str(row["name"]), []).append(str(row["day"]))
    return days


def _two_trips(db: Path) -> Catalog:
    """Two trips on disjoint days. **One trip proves nothing here**: the day -> trip mapping is
    only exercised when there is more than one trip to map to, and both the fixture above and the
    real library hold exactly one."""
    catalog = Catalog(db)
    catalog.upsert_drive(uuid=_UUID, label="Output")
    catalog.create_trip(
        name="Wayanad",
        slug="wayanad",
        start_date="2014-08-14",
        end_date="2014-08-15",
        days=["2014-08-14", "2014-08-15"],
    )
    catalog.create_trip(
        name="Goa",
        slug="goa",
        start_date="2015-01-01",
        end_date="2015-01-02",
        days=["2015-01-01", "2015-01-02"],
    )
    return catalog


def test_two_trips_come_back_holding_their_own_days(tmp_path: Path) -> None:
    """A TRIP'S IDENTITY MUST SURVIVE LEAVING THIS CATALOG, and a rowid does not.

    `trip_days` maps a day to `trips.id`, which is local to the catalog that minted it. A
    document that carries those ids and no way to resolve them has lost the mapping, and the
    damage is not that a trip goes missing - it is that the FIRST trip comes back claiming every
    other trip's days. A missing trip is visible to the user; a trip that quietly absorbed
    another's days renders those photos under the wrong folder and looks like a successful
    restore.

    Events do not have this problem and the difference is structural: `events.signature` travels
    inside the event's own row, so identity is self-contained. Whatever identifies a trip has to
    do the same.
    """
    with _two_trips(tmp_path / "source.sqlite") as catalog:
        original = _days_by_trip(catalog)
        gathered = gather_decisions(catalog, _UUID)

    assert original == {
        "Wayanad": ["2014-08-14", "2014-08-15"],
        "Goa": ["2015-01-01", "2015-01-02"],
    }, "the source catalog is not the one this test describes"

    with Catalog(tmp_path / "fresh.sqlite") as fresh:
        report = apply_decisions(fresh, gathered)
        restored = _days_by_trip(fresh)

    assert restored.get("Wayanad") == original["Wayanad"], (
        "a restored trip absorbed another trip's days - it did not merely fail to restore"
    )
    assert restored == original, "trips did not come back as they went out"
    assert report.applied.get("trips") == 2, (
        f"the report claims {report.applied.get('trips')} trips restored out of 2, so a user "
        "reading it would not learn that anything was lost"
    )


def test_the_document_carries_a_trip_s_days_and_no_catalog_rowid(tmp_path: Path) -> None:
    """WHAT MAKES IT SURVIVE: the days ride inside the trip, the way a signature rides inside an
    event. A rowid is meaningless on a machine that has never seen this catalog, so carrying one
    is not merely useless - it is the thing that looked like a mapping and was not."""
    with _two_trips(tmp_path / "source.sqlite") as catalog:
        gathered = gather_decisions(catalog, _UUID)
    document = to_document(gathered)

    by_name = {str(t["name"]): t for t in document["trips"]}
    assert by_name["Wayanad"]["days"] == ["2014-08-14", "2014-08-15"]
    assert by_name["Goa"]["days"] == ["2015-01-01", "2015-01-02"]
    assert "trip_days" not in document, (
        "a second representation of trip membership; the two can disagree and the one that wins "
        "is the one that caused this defect"
    )


def test_applying_two_trips_twice_changes_nothing_and_reports_no_conflict(tmp_path: Path) -> None:
    """Idempotence has to hold PER TRIP, not just in total. The obvious implementation of the
    conflict check reports every trip as conflicting on the second run - the days really are
    claimed by then - which would make an honest restore look like a broken one."""
    with _two_trips(tmp_path / "source.sqlite") as catalog:
        gathered = gather_decisions(catalog, _UUID)

    with Catalog(tmp_path / "fresh.sqlite") as fresh:
        first = apply_decisions(fresh, gathered)
        second = apply_decisions(fresh, gathered)

    assert first.applied.get("trips") == 2
    assert second.applied.get("trips", 0) == 0, "a second apply re-created trips"
    assert second.conflicting_trips == (), (
        f"a trip already restored was reported as a conflict: {second.conflicting_trips}"
    )


def test_a_trip_whose_days_another_trip_already_claims_is_reported_not_absorbed(
    tmp_path: Path,
) -> None:
    """THE CHANNEL THAT DID NOT EXIST. A day is claimed by at most one trip, so a document whose
    trip wants a day this catalog has already given to another trip cannot be applied at all.

    Skipping silently is exactly how the absorbed-days defect stayed invisible: the count said
    what it restored and nothing said what it did not. The local trip must also come out
    untouched - refusing must not become its own quieter way of rewriting somebody's days.
    """
    with _two_trips(tmp_path / "source.sqlite") as catalog:
        gathered = gather_decisions(catalog, _UUID)

    with Catalog(tmp_path / "local.sqlite") as local:
        local.create_trip(
            name="Kerala",
            slug="kerala",
            start_date="2014-08-14",
            end_date="2014-08-14",
            days=["2014-08-14"],  # one day Wayanad also wants
        )
        report = apply_decisions(local, gathered)
        after = _days_by_trip(local)

    assert report.conflicting_trips == ("Wayanad",), (
        f"the conflict was not reported: {report.conflicting_trips}"
    )
    assert after["Kerala"] == ["2014-08-14"], "the local trip's days were rewritten"
    assert "Wayanad" not in after, "a trip was half-created over a day it could not have"
    assert after["Goa"] == ["2015-01-01", "2015-01-02"], (
        "one trip's conflict stopped an unrelated trip from being restored"
    )


def test_two_trips_in_one_document_claiming_the_same_day_do_not_crash_a_restore(
    tmp_path: Path,
) -> None:
    """A DOCUMENT IS A FILE ON A DISK THE USER CAN EDIT, so it can say things a catalog cannot.

    `trip_days.day` is a primary key, so a second trip claiming a day the first just took raises
    `IntegrityError` from `create_trip` - a restore that dies part way through, with some
    decisions applied and no report. The conflict check has to see trips created earlier in this
    same apply, not just the ones the catalog held when it started.

    Added after a mutation that deleted exactly that bookkeeping did not fire.
    """
    hand_edited = Decisions(
        trips=(
            {
                "name": "Wayanad",
                "slug": "wayanad",
                "start": "2014-08-14",
                "end": "2014-08-15",
                "days": ["2014-08-14", "2014-08-15"],
            },
            {
                "name": "Goa",
                "slug": "goa",
                "start": "2014-08-15",
                "end": "2014-08-16",
                "days": ["2014-08-15", "2014-08-16"],  # 08-15 is Wayanad's
            },
        ),
    )

    with Catalog(tmp_path / "fresh.sqlite") as fresh:
        report = apply_decisions(fresh, hand_edited)
        after = _days_by_trip(fresh)

    assert report.applied.get("trips") == 1
    assert report.conflicting_trips == ("Goa",), (
        f"the second claim on 2014-08-15 was not reported: {report.conflicting_trips}"
    )
    assert after == {"Wayanad": ["2014-08-14", "2014-08-15"]}


def test_a_trip_the_document_carries_no_days_for_is_reported(tmp_path: Path) -> None:
    """A trip with no days cannot be placed - `create_trip` refuses one, correctly. Reported
    under its own name rather than as a conflict: nothing is competing for those days, the
    document simply does not say which they are, and the two need different words to a user."""
    with _two_trips(tmp_path / "source.sqlite") as catalog:
        gathered = gather_decisions(catalog, _UUID)
    stripped = Decisions(
        trips=({"name": "Wayanad", "slug": "wayanad", "start": "2014-08-14", "end": "2014-08-15"},),
        written=gathered.written,
    )

    with Catalog(tmp_path / "fresh.sqlite") as fresh:
        report = apply_decisions(fresh, stripped)

    assert report.trips_without_days == ("Wayanad",)
    assert report.conflicting_trips == (), "a missing day list was reported as a conflict"
    assert report.applied.get("trips", 0) == 0


# --- events re-attach only on a signature match -------------------------------------------


def test_an_event_name_re_attaches_only_where_the_signature_matches(tmp_path: Path) -> None:
    """A mismatch means membership changed, which is exactly when the name must not be applied."""
    with Catalog(tmp_path / "source.sqlite") as catalog:
        catalog.upsert_drive(uuid=_UUID, label="Output")
        catalog.record_event(
            name="Sam Wedding",
            slug="gokul-marriage",
            start_date="2015-10-25",
            file_count=3,
            signature="a" * 64,
        )
        gathered = gather_decisions(catalog, _UUID)

    with Catalog(tmp_path / "fresh.sqlite") as fresh:
        report = apply_decisions(fresh, gathered)

    assert "Sam Wedding" in report.unmatched_events
    assert report.applied.get("events", 0) == 0


def test_the_two_reasons_a_correction_was_not_applied_are_counted_apart(tmp_path: Path) -> None:
    """(abx) IN ONE TEST. One restore can hit both reasons at once, and they need opposite words:
    "your machine has a later correction, the drive's was ignored" needs no action, while "this
    drive holds a correction for a photo you have not scanned" means plug in the other drive and
    re-apply. They shared one field, and `dict.fromkeys` then collapsed them to one entry, so a
    restore hitting both reported a single indistinguishable line.
    """
    known, unknown = "e" * 64, "f" * 64
    document = Decisions(
        date_confirmations=(
            {"sha256": known, "captured_at": "2015-01-01T00:00:00", "confirmed_at": "2019-01-01"},
            {"sha256": unknown, "captured_at": "2016-01-01T00:00:00", "confirmed_at": "2026-01-01"},
        ),
    )

    with Catalog(tmp_path / "local.sqlite") as local:
        local.record_uploaded(
            source_path="/src/known.jpg",
            original_name="known.jpg",
            sha256=known,
            copy_sha256=known,
            perceptual=None,
            size=10,
            captured_at="2015-06-01T00:00:00",
            category="Camera",
            relative="2015/known.jpg",
        )
        local.confirm_date(known, "2015-09-09T00:00:00", confirmed_by="user")  # later than the doc
        report = apply_decisions(local, document)

    assert report.already_newer_locally == {"date_confirmations": 1}
    assert report.awaiting_content == {"date_confirmations": 1}
    assert report.applied.get("date_confirmations", 0) == 0
