"""The query planner's statistics, and when they are refreshed.

**`ANALYZE` had never run**, so `sqlite_stat1` did not exist and the planner guessed at every
join. Measured on the real catalog: Find 4.59 ms -> 2.15 ms with statistics, the drive listing
2.04 ms -> 1.79 ms. The numbers are small at 2,695 files; the shape is the point, because a
planner guessing on a join gets worse as the library grows.

**Not on every open**, which would pay for it on `status` and `where`. It runs when the catalog
has grown enough that the old statistics describe a different database - measured at 1.8 ms on
the real catalog and 17 ms against a 172,480-row table, so the trigger can be generous.
"""

from __future__ import annotations

from pathlib import Path

from truestill_core.catalog import ANALYZE_GROWTH_ROWS, ANALYZED_AT_KEY, Catalog
from truestill_core.catalog_session import open_catalog
from truestill_core.decisions import publishable_settings


def _has_statistics(catalog: Catalog) -> bool:
    return bool(
        catalog._conn.execute(
            "SELECT count(*) FROM sqlite_master WHERE name='sqlite_stat1'"
        ).fetchone()[0]
    )


def _add_files(catalog: Catalog, count: int, start: int = 0) -> None:
    for i in range(start, start + count):
        catalog.record_uploaded(
            source_path=f"/src/{i}.jpg",
            original_name=f"{i}.jpg",
            sha256=f"{i:064x}",
            copy_sha256=None,
            perceptual=None,
            size=10,
            captured_at="2015-01-01T00:00:00",
            category="Camera",
            relative=f"2015/{i}.jpg",
        )


def test_a_catalog_that_has_never_been_analysed_gets_statistics(tmp_path: Path) -> None:
    """The first run is the one that matters: until it happens the planner has nothing at all."""
    db = tmp_path / "c.sqlite"
    with Catalog(db) as setup:
        _add_files(setup, 3)
        assert not _has_statistics(setup)

    with open_catalog(db) as catalog:
        _add_files(catalog, 1, start=100)

    with Catalog(db) as after:
        assert _has_statistics(after)


def test_a_read_only_command_never_analyses(tmp_path: Path) -> None:
    """`status` and `where` change nothing, so there is nothing new for the planner to learn."""
    db = tmp_path / "c.sqlite"
    with Catalog(db) as setup:
        _add_files(setup, 3)

    with open_catalog(db) as catalog:
        catalog.count()

    with Catalog(db) as after:
        assert not _has_statistics(after)


def test_it_does_not_analyse_again_until_the_catalog_has_grown(tmp_path: Path) -> None:
    """THE HALF THAT KEEPS IT CHEAP. Renaming a trip writes to the catalog but tells the planner
    nothing it did not know, and re-analysing on every write would be the every-open cost this
    trigger exists to avoid."""
    db = tmp_path / "c.sqlite"
    with Catalog(db) as setup:
        _add_files(setup, 3)
    with open_catalog(db) as catalog:
        _add_files(catalog, 1, start=100)
    with Catalog(db) as mid:
        first = mid.get_setting(ANALYZED_AT_KEY)

    with open_catalog(db) as catalog:
        catalog.record_skip("b" * 64)  # a decision, not a library change

    with Catalog(db) as after:
        assert after.get_setting(ANALYZED_AT_KEY) == first, "statistics were refreshed for nothing"


def test_it_analyses_again_once_enough_rows_have_arrived(tmp_path: Path) -> None:
    """CRY-WOLF HALF. A trigger that never fires twice would leave a 150,000-file library
    describing itself with the statistics of its first thousand."""
    db = tmp_path / "c.sqlite"
    with Catalog(db) as setup:
        _add_files(setup, 2)
    with open_catalog(db) as catalog:
        _add_files(catalog, 1, start=50)
    with Catalog(db) as mid:
        first = mid.get_setting(ANALYZED_AT_KEY)
        assert first is not None

    with open_catalog(db) as catalog:
        _add_files(catalog, ANALYZE_GROWTH_ROWS + 1, start=1000)

    with Catalog(db) as after:
        assert after.get_setting(ANALYZED_AT_KEY) != first, "growth did not refresh the statistics"


def test_the_statistics_marker_never_reaches_a_drive() -> None:
    """Machine-local bookkeeping about THIS file's planner, restored onto another machine, would
    describe a database that is not there. Same rule as the decisions save marker."""
    assert publishable_settings({ANALYZED_AT_KEY: "9", "layout_template": "{yyyy}"}) == {
        "layout_template": "{yyyy}"
    }
