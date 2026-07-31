"""The (n) honesty view: read-only, and honest about what it does not know (step 2).

Validated against the real library before these were written. Two findings shaped them:

* Dinesh's catalog is **2,300 rows, every one of them NULL** - the not-recorded group is the
  common case on the only real library we have, not an edge. It must read as the ordinary thing
  it is.
* A 600-file sample of real photos came out 598 EXIF / 2 undated, and the 2 rendered as **"0%"**.
  A screen whose whole purpose is honesty about dates cannot report "none" for a group it is
  simultaneously listing.
"""

from __future__ import annotations

from pathlib import Path

from starlette.testclient import TestClient
from truestill_core.catalog import Catalog
from truestill_core.models import DateSource


def _row(catalog: Catalog, sha: str, *, source: str | None, tag: str | None = None) -> None:
    catalog.record_uploaded(
        source_path=f"/src/{sha}.jpg",
        original_name=f"{sha}.jpg",
        sha256=sha,
        copy_sha256=sha,
        perceptual=None,
        size=1,
        captured_at="2014-08-20T14:30:00",
        category="Camera",
        relative=f"2014/{sha}.jpg",
        date_source=source,
        date_tag=tag,
    )


def _dates(client: TestClient) -> dict:
    body = client.get("/api/library/stats").json()
    return body["dates"]


def test_a_library_with_no_recorded_provenance_says_so_calmly(
    client: TestClient, db_path: Path
) -> None:
    """The real-catalog case: every row NULL. Not an error, not a gap, not the user's fault."""
    with Catalog(db_path) as catalog:
        for i in range(3):
            _row(catalog, f"{i:064x}", source=None)

    dates = _dates(client)
    assert dates["total"] == 3
    assert dates["not_recorded"] == 3
    assert dates["recorded"] == 0

    row = dates["rows"][0]
    assert row["label"] == "Not recorded"
    assert row["not_recorded"] is True
    assert row["review"] is False, "the ordinary state of an older library is not a warning"
    assert "unaffected" in row["detail"], "it must say the photos themselves are fine"


def test_the_not_recorded_group_is_never_a_share_of_the_recorded_total(
    client: TestClient, db_path: Path
) -> None:
    """``recorded`` excludes it, so a renderer computing a share must be told to skip it.

    Without the flag the not-recorded row divides by a total that omits itself, printing a
    confident percentage for the one group whose entire meaning is "we do not know".
    """
    with Catalog(db_path) as catalog:
        _row(catalog, "a" * 64, source=None)
        _row(catalog, "b" * 64, source=DateSource.EXIF.value, tag="DateTimeOriginal")

    dates = _dates(client)
    assert dates["total"] == 2
    assert dates["recorded"] == 1
    flagged = [r for r in dates["rows"] if r["not_recorded"]]
    assert len(flagged) == 1


def test_the_view_shows_the_evidence_not_only_the_tier(client: TestClient, db_path: Path) -> None:
    """ "Why this date?" is the question. The tier answers "what kind"; the tag answers "which"."""
    with Catalog(db_path) as catalog:
        _row(catalog, "c" * 64, source=DateSource.EXIF.value, tag="DateTimeOriginal")

    row = next(r for r in _dates(client)["rows"] if r["label"] == "From the photo's own data")
    assert row["evidence"] == "tag: DateTimeOriginal"


def test_an_inferred_video_shows_its_offset_and_the_rung_that_proved_it(
    client: TestClient, db_path: Path
) -> None:
    """The shift is the part a user can check: "we moved your video by 5 hours 30, because...".

    A bare tier would say only "worked out from the video's clock", which is unfalsifiable.
    """
    with Catalog(db_path) as catalog:
        _row(
            catalog,
            "d" * 64,
            source=DateSource.INFERRED_LOCAL.value,
            tag="CreateDate|filename:VID_|+05:30",
        )

    row = next(r for r in _dates(client)["rows"] if "video" in r["label"])
    assert "+05:30" in row["evidence"]
    assert "filename:VID_" in row["evidence"]


def test_filename_and_undated_are_flagged_for_review_in_plain_language(
    client: TestClient, db_path: Path
) -> None:
    """(ccc): say what it means, not which enum member won."""
    with Catalog(db_path) as catalog:
        _row(catalog, "e" * 64, source=DateSource.FILENAME.value)
        _row(catalog, "f" * 64, source=DateSource.NONE.value)

    rows = {r["label"]: r for r in _dates(client)["rows"]}
    assert rows["From the filename"]["review"] is True
    assert "worth a look" in rows["From the filename"]["detail"]
    assert rows["No date found"]["review"] is True
    assert "Undated" in rows["No date found"]["detail"]
    # No enum values, no tier names, no jargon in anything a user reads.
    for row in rows.values():
        assert "DateSource" not in row["detail"]
        assert "_" not in row["label"]


def test_viewing_the_stats_writes_nothing(client: TestClient, db_path: Path) -> None:
    """Read-only, proven the way the migration/trips previews prove it: catalog bytes.

    The honesty view runs on every Stats load. If it could write, simply looking at your library
    would change it - and the (ii) rescue that lands on this same screen would have no clean
    before-state to compare against.
    """
    with Catalog(db_path) as catalog:
        _row(catalog, "0" * 64, source=DateSource.EXIF.value, tag="DateTimeOriginal")
        _row(catalog, "1" * 64, source=None)

    before = db_path.read_bytes()
    assert client.get("/api/library/stats").status_code == 200
    assert client.get("/api/library/stats").status_code == 200  # twice: no lazy first-run write
    assert db_path.read_bytes() == before, "the honesty view wrote to the catalog"
