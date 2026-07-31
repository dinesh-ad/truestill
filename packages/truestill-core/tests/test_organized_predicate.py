"""What makes a file "organized" is its upload status, not that it has a remembered path.

Three queries asked ``WHERE relative IS NOT NULL``. That is a *proxy*: it happens to be true of
every row `record_uploaded` writes, because that one insert site always sets both. But the column
it tests is `files.relative` - per-content data that `migrate-layout` leaves stale (see
`test_attach_after_migrate.py`) - and the question being asked is "was this file organized?",
which `upload_status` answers directly and by definition.

**The two predicates are not merely interchangeable; one is correct and one is a coincidence.**
The case below is constructed rather than sampled: on the real catalog all 2,300 rows have both,
so measuring it there proves nothing except that the coincidence currently holds. A row with a
path and a non-uploaded status is representable in the schema (``relative`` is nullable,
``upload_status`` is ``NOT NULL`` and unconstrained), and is exactly what a partially-processed
or legacy row looks like. The proxy counts it as organized. The direct question does not.
"""

from __future__ import annotations

from pathlib import Path

from truestill_core.catalog import Catalog


def _uploaded(catalog: Catalog, sha: str, relative: str) -> None:
    catalog.record_uploaded(
        source_path=f"/src/{sha}.jpg",
        original_name=f"{sha}.jpg",
        sha256=sha,
        copy_sha256=sha,
        perceptual=None,
        size=10,
        captured_at="2014-08-16T10:46:26",
        category="Camera",
        relative=relative,
    )


def _half_processed(catalog: Catalog, sha: str, relative: str) -> None:
    """A row with a path but no completed upload. Not reachable through `record_uploaded`,
    which hardcodes ``'uploaded'`` - so it is written directly, the way a legacy catalog or a
    future second insert path would leave it."""
    catalog._conn.execute(
        "INSERT INTO files (source_path, original_name, sha256, category, relative, "
        "upload_status, processed_at) VALUES (?, ?, ?, 'Camera', ?, 'pending', '2026-07-31')",
        (f"/src/{sha}.jpg", f"{sha}.jpg", sha, relative),
    )
    catalog._conn.commit()


def test_a_row_with_a_path_but_no_upload_is_not_organized(tmp_path: Path) -> None:
    """The constructed difference, and the whole argument for the swap.

    ``relative IS NOT NULL`` says yes because the row has a path. It was never organized.
    """
    db = tmp_path / "c.sqlite"
    with Catalog(db) as catalog:
        _uploaded(catalog, "sha-real", "Camera/2014/a.jpg")
        _half_processed(catalog, "sha-half", "Camera/2014/b.jpg")

        proxy = catalog._conn.execute(
            "SELECT COUNT(*) FROM files WHERE relative IS NOT NULL"
        ).fetchone()[0]
        assert proxy == 2, "the fixture must reproduce the disagreement, or it proves nothing"

        assert {str(r["sha256"]) for r in catalog.organized_files()} == {"sha-real"}
        assert set(catalog.organized_sizes()) == {"sha-real"}
        assert {str(r["sha256"]) for r in catalog.attachable_hashes()} == {"sha-real"}


def test_the_ordinary_row_is_unaffected(tmp_path: Path) -> None:
    """Cry-wolf half: every row the real pipeline writes must still count as organized.

    The swap must narrow the answer to the wrong rows only. If this ever fails, the three
    queries have stopped seeing the library.
    """
    db = tmp_path / "c.sqlite"
    with Catalog(db) as catalog:
        for index in range(3):
            _uploaded(catalog, f"sha-{index}", f"Camera/2014/{index}.jpg")

        assert len(catalog.organized_files()) == 3
        assert len(catalog.organized_sizes()) == 3
        assert {str(r["sha256"]) for r in catalog.attachable_hashes()} == {
            "sha-0",
            "sha-1",
            "sha-2",
        }


def test_a_stale_path_does_not_stop_a_file_counting_as_organized(tmp_path: Path) -> None:
    """The migrated case: `files.relative` may be wrong, and the file is still organized.

    This is why the proxy was the wrong question rather than merely a redundant one - it tests a
    column whose value is not maintained, to answer something that does not depend on it.
    """
    db = tmp_path / "c.sqlite"
    with Catalog(db) as catalog:
        _uploaded(catalog, "sha-moved", "Camera/2014/08/original.jpg")
        catalog._conn.execute(
            "UPDATE files SET relative = 'nowhere/on/disk/original.jpg' WHERE sha256 = ?",
            ("sha-moved",),
        )
        catalog._conn.commit()

        assert {str(r["sha256"]) for r in catalog.organized_files()} == {"sha-moved"}
