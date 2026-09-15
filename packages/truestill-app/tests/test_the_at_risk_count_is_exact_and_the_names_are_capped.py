"""The custody claim is exact; the names beside it are a sample. `(akt)`

⚠ **THE DEFECT WAS STRUCTURAL, NOT SLOW.** `/api/drives` sent one entry per at-risk file, and the
browser used **`rows.length` as the count** - so *"83 files exist in only one place"* was the
length of an array that had to carry every file to stay true. Measured on a catalog whose files
all sit on one drive:

| one-copy files | payload | build |
|---|---|---|
| 2,574 | 159,954 B | 9.4 ms |
| 300,000 | **18,600,370 B** | **1,198.7 ms** |

18.6 MB, on a screen that opens by default, to render twelve names. After: **561 bytes at
300,000** - the payload is bounded by the number of drives, not by the size of the library.

🔑 **CAP THE NAMES, NEVER THE COUNT.** The band, the banner title and the chip all rest on the
number; it is the product's central custody claim and may never be a sample. The names exist only
to make the claim actionable. `OrganizedSample` is the same shape one surface over, and its
docstring is the rule: *"tiles plus the count they were taken from, so truncation is never
silent."*

**These tests exist because the two are now carried separately and nothing else would notice them
drifting apart.** A `total` quietly computed from `len(shown)` would pass every other test in the
suite and would report 6 files at risk on a library with 300,000.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from truestill_app.service.drives import AT_RISK_SAMPLE_LIMIT, at_risk
from truestill_core.catalog import Catalog


def _library(db: Path, *, at_risk_files: int, safe_files: int = 0) -> None:
    """``at_risk_files`` on one drive only; ``safe_files`` on two, so they must NOT be counted."""
    with Catalog(db) as catalog:
        conn = catalog._conn
        conn.execute("INSERT INTO drives (uuid, label) VALUES ('D1', 'BackupA')")
        conn.execute("INSERT INTO drives (uuid, label) VALUES ('D2', 'BackupB')")
        for index in range(at_risk_files + safe_files):
            sha = f"{index:064x}"
            relative = f"2014/2014-08/IMG_{index:06d}.jpg"
            conn.execute(
                "INSERT INTO files (sha256, original_name, size, source_path, category,"
                " relative, upload_status, processed_at)"
                " VALUES (?, ?, ?, ?, 'Camera', ?, 'uploaded', '2026-09-15T00:00:00+00:00')",
                (sha, f"IMG_{index:06d}.jpg", index, f"/in/IMG_{index:06d}.jpg", relative),
            )
            conn.execute(
                "INSERT INTO file_copies (sha256, drive_uuid, relative) VALUES (?, 'D1', ?)",
                (sha, relative),
            )
            if index >= at_risk_files:
                conn.execute(
                    "INSERT INTO file_copies (sha256, drive_uuid, relative) VALUES (?, 'D2', ?)",
                    (sha, relative),
                )
        conn.commit()


@pytest.fixture
def many(tmp_path: Path) -> Path:
    db = tmp_path / "c.sqlite"
    _library(db, at_risk_files=200, safe_files=25)
    return db


def test_the_count_is_exact_and_is_not_the_length_of_the_sample(many: Path) -> None:
    """**The headline.** 200 at risk, a handful of names, and the number says 200.

    ⚠ The two numbers are asserted to DIFFER, not merely to exist. An implementation that set
    `total = len(shown)` would satisfy "total is present" and every count on the screen would be
    wrong by a factor of thirty.
    """
    summary = at_risk(many)

    assert summary["total"] == 200
    shown = summary["drives"][0]["shown"]
    assert len(shown) == AT_RISK_SAMPLE_LIMIT
    assert summary["total"] != len(shown), "the count is being derived from the sample"
    assert summary["drives"][0]["total"] == 200


def test_the_payload_does_not_grow_with_the_library(tmp_path: Path) -> None:
    """⚠ **THE STRUCTURAL PROPERTY, and the only one that actually matters.**

    Ten times the at-risk files must not mean ten times the payload. The old shape was one entry
    per file, so this ratio was 10; the drive count is what bounds it now.
    """
    small, large = tmp_path / "s.sqlite", tmp_path / "l.sqlite"
    _library(small, at_risk_files=50)
    _library(large, at_risk_files=500)

    entries = lambda db: sum(len(d["shown"]) for d in at_risk(db)["drives"])  # noqa: E731
    assert at_risk(small)["total"] == 50
    assert at_risk(large)["total"] == 500
    assert entries(small) == entries(large), (
        f"the sample grew with the library: {entries(small)} names at 50 files, "
        f"{entries(large)} at 500 - the payload is not bounded"
    )


def test_a_file_safe_on_two_drives_is_not_counted(many: Path) -> None:
    """The count must be *at risk*, not *every copy*. 25 of the 225 files sit on both drives.

    Without this the cap could be correct while the claim was inflated, and an inflated custody
    number is the more alarming failure of the two.
    """
    summary = at_risk(many)
    assert summary["total"] == 200, "files with a second copy leaked into the at-risk count"
    assert [d["drive"] for d in summary["drives"]] == ["BackupA"], (
        "a drive holding only second copies was reported as holding files at risk"
    )


def test_the_sample_is_capped_at_the_declared_limit(tmp_path: Path) -> None:
    """The cap is the constant, not a number that happens to be small today."""
    db = tmp_path / "c.sqlite"
    _library(db, at_risk_files=AT_RISK_SAMPLE_LIMIT * 4)
    drive = at_risk(db)["drives"][0]
    assert len(drive["shown"]) == AT_RISK_SAMPLE_LIMIT
    assert drive["total"] == AT_RISK_SAMPLE_LIMIT * 4


def test_a_library_smaller_than_the_cap_sends_every_name(tmp_path: Path) -> None:
    """⚠ **The cry-wolf half.** A cap that always truncated would be indistinguishable from one
    that never fired, and the ordinary library is far below it - three at-risk files must send
    three names and say three, with nothing elided."""
    db = tmp_path / "c.sqlite"
    _library(db, at_risk_files=3)
    drive = at_risk(db)["drives"][0]
    assert drive["total"] == 3
    assert len(drive["shown"]) == 3, "a small library was truncated by a cap it never reached"


def test_a_library_with_nothing_at_risk_reports_zero_rather_than_nothing(tmp_path: Path) -> None:
    """The empty case is a zero total, never an absent one: the screen branches on the number."""
    db = tmp_path / "c.sqlite"
    _library(db, at_risk_files=0, safe_files=8)
    summary = at_risk(db)
    assert summary == {"total": 0, "drives": []}


def test_the_total_is_the_sum_of_the_drives(tmp_path: Path) -> None:
    """Two drives, each holding files whose only copy is there. The headline is the whole."""
    db = tmp_path / "c.sqlite"
    with Catalog(db) as catalog:
        conn = catalog._conn
        conn.execute("INSERT INTO drives (uuid, label) VALUES ('D1', 'BackupA')")
        conn.execute("INSERT INTO drives (uuid, label) VALUES ('D2', 'BackupB')")
        for index in range(30):
            sha = f"{index:064x}"
            relative = f"2014/IMG_{index:06d}.jpg"
            conn.execute(
                "INSERT INTO files (sha256, original_name, size, source_path, category,"
                " relative, upload_status, processed_at)"
                " VALUES (?, ?, ?, ?, 'Camera', ?, 'uploaded', '2026-09-15T00:00:00+00:00')",
                (sha, f"IMG_{index:06d}.jpg", index, f"/in/IMG_{index:06d}.jpg", relative),
            )
            conn.execute(
                "INSERT INTO file_copies (sha256, drive_uuid, relative) VALUES (?, ?, ?)",
                (sha, "D1" if index < 18 else "D2", relative),
            )
        conn.commit()

    summary = at_risk(db)
    assert summary["total"] == 30
    assert sum(d["total"] for d in summary["drives"]) == summary["total"]
    assert sorted((d["drive"], d["total"]) for d in summary["drives"]) == [
        ("BackupA", 18),
        ("BackupB", 12),
    ]
