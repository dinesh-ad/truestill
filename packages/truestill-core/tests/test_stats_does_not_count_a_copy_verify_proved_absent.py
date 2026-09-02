"""The Stats rollup does not count a copy `verify` proved absent as a place the file is.

Four helpers answered "is this file in two places?"; three tested `missing_at IS NULL` and
`stats_summary` did not, so the Stats screen reported a file whose only copy was gone as "on one
drive only" - measured in a real catalog, seven files (P190, `(ajo)`). One clause in one CTE.
"""

from __future__ import annotations

from pathlib import Path

from truestill_core.catalog import Catalog

A, B = "a" * 36, "b" * 36


def _record(catalog: Catalog, sha: str, drives: tuple[str, ...]) -> None:
    for drive in drives:
        catalog.record_uploaded(
            source_path=f"/src/{sha}.jpg",
            original_name=f"{sha}.jpg",
            sha256=sha,
            copy_sha256=sha,
            perceptual=None,
            size=10,
            captured_at="2014-08-17T09:25:02",
            category="Camera",
            relative=f"Camera/{sha}.jpg",
            drive_uuid=drive,
        )


def _summary(tmp_path: Path) -> dict[str, int]:
    db = tmp_path / "catalog.sqlite"
    with Catalog(db) as catalog:
        catalog.upsert_drive(uuid=A, label="A")
        catalog.upsert_drive(uuid=B, label="B")
        _record(catalog, "twogood", (A, B))
        _record(catalog, "onegone", (A, B))
        _record(catalog, "allgone", (A,))
        catalog.mark_copy_missing(sha256="onegone", drive_uuid=B, when="2026-09-02T10:00:00")
        catalog.mark_copy_missing(sha256="allgone", drive_uuid=A, when="2026-09-02T10:00:00")
        row = catalog.stats_summary()
        return {
            k: int(row[k])
            for k in ("files_on_two_plus_drives", "files_on_one_drive", "files_on_zero_drives")
        }


def test_a_missing_copy_is_not_a_place(tmp_path: Path) -> None:
    got = _summary(tmp_path)
    assert got == {
        "files_on_two_plus_drives": 1,  # twogood
        "files_on_one_drive": 1,  # onegone: B was looked for and not found
        "files_on_zero_drives": 1,  # allgone: its only copy is gone
    }, got


def test_the_three_buckets_still_sum_to_the_files(tmp_path: Path) -> None:
    got = _summary(tmp_path)
    assert sum(got.values()) == 3
