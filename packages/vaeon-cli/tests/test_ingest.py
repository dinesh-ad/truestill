"""End-to-end Takeout ingestion: dedup album copies, recover dates, bake metadata."""

from __future__ import annotations

import json
import shutil
import sqlite3
from pathlib import Path

import pytest
from PIL import Image
from vaeon_cli.cli import main

pytestmark = pytest.mark.skipif(shutil.which("exiftool") is None, reason="exiftool not installed")

_TAKEN = 1692113136  # 2023-08-15 14:25:36 UTC


def _image(path: Path, colour: tuple[int, int, int]) -> None:
    Image.new("RGB", (64, 64), colour).save(path, "JPEG")  # no EXIF date


def _sidecar(path: Path, taken: int) -> None:
    path.write_text(json.dumps({"photoTakenTime": {"timestamp": str(taken)}}), encoding="utf-8")


def _mini_takeout(root: Path) -> None:
    year = root / "Photos from 2023"
    album = root / "Trip"
    year.mkdir(parents=True)
    album.mkdir(parents=True)

    _image(year / "A.jpg", (10, 20, 30))
    _sidecar(year / "A.jpg.supplemental-metadata.json", _TAKEN)
    _image(year / "B.jpg", (200, 100, 50))
    _sidecar(year / "B.jpg.json", _TAKEN)

    # album copy of A: byte-identical duplicate
    shutil.copy(year / "A.jpg", album / "A.jpg")
    _sidecar(album / "A.jpg.json", _TAKEN)


def test_ingest_dedups_recovers_dates_and_bakes_metadata(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    takeout = tmp_path / "Takeout"
    dest = tmp_path / "out"
    db = tmp_path / "catalog.sqlite"
    _mini_takeout(takeout)

    code = main(["ingest", str(dest), "--takeout", str(takeout), "--apply", "--db", str(db)])
    assert code == 0

    # The album duplicate of A collapsed: exactly two unique files landed.
    landed = [p for p in dest.rglob("*") if p.is_file()]
    assert len(landed) == 2

    # Dates recovered from the sidecar -> filed under 2023/08.
    assert all("2023/08" in str(p) for p in landed)

    report = capsys.readouterr().out
    assert "TAKEOUT RESCUE REPORT" in report

    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    rows = {row["original_name"]: row for row in conn.execute("SELECT * FROM files")}
    assert set(rows) == {"A.jpg", "B.jpg"}

    a = rows["A.jpg"]
    assert a["captured_at"].startswith("2023-08-15")  # recovered from photoTakenTime
    # metadata was baked into the copy -> its hash differs from the source's dedup hash.
    assert a["copy_sha256"] is not None
    assert a["copy_sha256"] != a["sha256"]

    # album membership recorded for A (kept copy aggregates the album copy's membership).
    album_names = {
        row["name"]
        for row in conn.execute(
            "SELECT al.name FROM albums al "
            "JOIN file_albums fa ON fa.album_id = al.id WHERE fa.file_id = ?",
            (a["id"],),
        )
    }
    conn.close()
    assert album_names == {"Trip"}
