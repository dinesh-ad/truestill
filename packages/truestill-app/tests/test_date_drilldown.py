"""The honesty view becomes addressable: a tier drills down to the files in it (step 5, part 1).

**Why this is the prerequisite and not a nicety.** `(n)` shipped a provenance *mix* - counts
grouped by tier - and `confirm_date` is keyed on **sha256**. So the screen that tells a user
their dates are guessed had no way to name a file to the API that would fix one: the only file
list on it, `stats_undated_samples`, returned ``original_name, source_path, relative`` and no
identity at all. The rescue action is unbuildable until this exists, which is why it is its own
commit and why the two land in one batch - **a drill-down that lists files a user cannot act on
is worse than no drill-down.**

Read-only throughout. This commit adds no way to change anything; it adds the ability to *refer*
to something.

**Truncation is disclosed, as everywhere else (F46).** A tier holding 2,300 files returns a page
and the count it came from, so a list can never imply it is the whole tier.
"""

from __future__ import annotations

import inspect
from datetime import datetime
from pathlib import Path

from truestill_app.service.stats import date_tier_files, library_stats
from truestill_core.catalog import Catalog
from truestill_core.models import DateSource


def _library(db: Path, rows: list[tuple[str, str | None, str | None]]) -> None:
    """``(name, date_source, date_tag)`` per file. ``captured_at`` is set unless the tier is NONE."""
    with Catalog(db) as catalog:
        for index, (name, source, tag) in enumerate(rows):
            dated = source not in {DateSource.NONE.value, None} or name.startswith("dated")
            catalog.record_uploaded(
                source_path=f"/src/{name}",
                original_name=name,
                sha256=f"sha-{index:03d}",
                copy_sha256=f"sha-{index:03d}",
                perceptual=None,
                size=10,
                captured_at=datetime(2014, 8, 16, 10, 46, 26).isoformat() if dated else None,
                category="Camera",
                relative=f"Camera/2014/{name}",
                date_source=source,
                date_tag=tag,
            )


def test_a_tier_drills_down_to_the_files_in_it(tmp_path: Path) -> None:
    """The whole point: a percentage becomes a list of files with identities."""
    db = tmp_path / "c.sqlite"
    _library(
        db,
        [
            ("a.jpg", DateSource.FILENAME.value, None),
            ("b.jpg", DateSource.FILENAME.value, None),
            ("c.jpg", DateSource.EXIF.value, "DateTimeOriginal"),
        ],
    )

    page = date_tier_files(db, DateSource.FILENAME.value)

    assert page["total"] == 2
    assert sorted(f["name"] for f in page["files"]) == ["a.jpg", "b.jpg"]


def test_every_listed_file_carries_the_identity_the_rescue_needs(tmp_path: Path) -> None:
    """`confirm_date` is keyed on sha256. Without it, this screen can describe but not act."""
    db = tmp_path / "c.sqlite"
    _library(db, [("a.jpg", DateSource.FILENAME.value, None)])

    page = date_tier_files(db, DateSource.FILENAME.value)

    assert page["files"][0]["sha256"] == "sha-000"


def test_the_not_recorded_group_is_addressable_too(tmp_path: Path) -> None:
    """The commonest tier on a real library is NULL, so it must not be the one you cannot open.

    On the maintainer's own catalog this group is every one of 2,300 rows.
    """
    db = tmp_path / "c.sqlite"
    _library(db, [("dated-legacy.jpg", None, None)])

    page = date_tier_files(db, None)

    assert page["total"] == 1
    assert page["files"][0]["sha256"] == "sha-000"


def test_an_undated_file_is_reachable_from_its_tier(tmp_path: Path) -> None:
    """The Undated bucket is (ii)'s motivating case - the rescue is the only route out of it."""
    db = tmp_path / "c.sqlite"
    _library(db, [("scan.jpg", DateSource.NONE.value, None)])

    page = date_tier_files(db, DateSource.NONE.value)

    assert [f["name"] for f in page["files"]] == ["scan.jpg"]
    assert page["files"][0]["captured_at"] is None


def test_the_list_shows_the_date_it_is_asking_the_user_to_judge(tmp_path: Path) -> None:
    """A rescue is a judgement, so the current answer and its evidence travel with the row."""
    db = tmp_path / "c.sqlite"
    _library(db, [("a.jpg", DateSource.FILENAME.value, None)])

    row = date_tier_files(db, DateSource.FILENAME.value)["files"][0]

    assert row["captured_at"] == datetime(2014, 8, 16, 10, 46, 26).isoformat()
    assert row["relative"] == "Camera/2014/a.jpg"


def test_a_long_tier_says_how_many_it_left_out(tmp_path: Path) -> None:
    """F46 at the payload: a page must carry the total it was taken from."""
    db = tmp_path / "c.sqlite"
    _library(db, [(f"f{i}.jpg", DateSource.FILENAME.value, None) for i in range(60)])

    page = date_tier_files(db, DateSource.FILENAME.value, limit=25)

    assert len(page["files"]) == 25
    assert page["total"] == 60


def test_a_short_tier_is_not_described_as_truncated(tmp_path: Path) -> None:
    """Cry-wolf half: a complete list must read as complete."""
    db = tmp_path / "c.sqlite"
    _library(db, [("a.jpg", DateSource.FILENAME.value, None)])

    page = date_tier_files(db, DateSource.FILENAME.value, limit=25)

    assert page["total"] == len(page["files"]) == 1


def test_the_undated_sample_gained_the_identity_it_lacked(tmp_path: Path) -> None:
    """The concrete gap this commit closes, asserted where it was: stats' own file list.

    It returned name / source_path / relative - everything except the one field the action
    needs. A screen that can describe a file but not name it to the API is a dead end.
    """
    db = tmp_path / "c.sqlite"
    _library(db, [("scan.jpg", DateSource.NONE.value, None)])

    samples = library_stats(db)["completeness"]["undated_samples"]

    assert samples[0]["sha256"] == "sha-000"


def test_the_drill_down_writes_nothing(tmp_path: Path) -> None:
    """Read-only (§5). This commit adds the ability to refer to a file, not to change one."""
    db = tmp_path / "c.sqlite"
    _library(db, [("a.jpg", DateSource.FILENAME.value, None)])
    with Catalog(db):
        pass
    with Catalog(db):
        pass
    before = db.read_bytes()

    date_tier_files(db, DateSource.FILENAME.value)
    library_stats(db)

    assert db.read_bytes() == before


def test_the_page_is_bounded_at_the_query_not_in_python() -> None:
    """A 100k-row tier must never be materialised and then sliced.

    Every assertion above passes against a fetch-everything-then-``[:limit]`` implementation -
    the returned page looks identical. What differs is the memory and the time, at exactly the
    scale where it matters, so the mechanism is asserted rather than the result.

    Measured on a synthetic 100k-row catalog: **18.0 ms** for a tier with rows and **16.2 ms**
    for the not-recorded tier, both bounded by SQL ``LIMIT``. No index on ``date_source`` was
    added: two O(n) scans at that speed are not a problem to buy machinery for
    (`PERFORMANCE.md` §2), and the index is the named fix if the honesty view ever is slow.
    """
    source = inspect.getsource(Catalog.files_in_date_tier)
    body = source.split('"""', 2)[-1]  # skip the docstring, which legitimately says "limit"
    assert "LIMIT ?" in body, "the page must be bounded by SQL, not by Python"
    assert "[:limit]" not in body, "rows are being sliced after fetch"
    assert "[: limit]" not in body, "rows are being sliced after fetch"
