"""An archive unpack writes a run record naming its parts and carrying its counts.

The staging journal holds a root and part names, is overwritten by the next unpack of the same
set, and is read by nothing in the product; the organize that follows records where files landed,
never what was unpacked. So the record is the only durable account (`(ahi)`, 2026-09-02).
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

from truestill_core.app_paths import record_path_for
from truestill_core.archive_extract import extract_archive_set, record_extraction
from truestill_core.archive_ingest import precheck_archives


def test_the_record_names_the_parts_and_counts_the_files(tmp_path: Path) -> None:
    archive = tmp_path / "Photos-001.zip"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("Takeout/Google Photos/a.txt", b"one")
        z.writestr("Takeout/Google Photos/b.txt", b"two")
    destination = tmp_path / "dest"
    destination.mkdir()
    report = precheck_archives([archive], destination)
    assert report.may_proceed, report.detail
    extraction = extract_archive_set(report.archive_set, destination)
    assert extraction.files_written == 2

    db = tmp_path / "catalog.sqlite"
    assert (
        record_extraction(
            db,
            source=archive,
            destination=destination,
            archive_set=report.archive_set,
            extraction=extraction,
        )
        is None
    )
    record = json.loads(record_path_for(db).read_text(encoding="utf-8"))
    run = record["run"]
    assert run["kind"] == "archive unpack"
    assert run["files_written"] == 2
    assert run["stopped"] is None
    assert [e["relative"] for e in record["files"]] == ["Photos-001.zip"]
    assert run["destination"] == str(extraction.staging_root)
