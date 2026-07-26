"""Takeout intake: sidecar matching edge cases, parsing, and folder scan."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from truestill_core.takeout import (
    SidecarIndex,
    is_year_folder,
    local_naive,
    parse_sidecar,
    scan_takeout,
)


@pytest.mark.parametrize(
    ("media", "sidecars", "expected"),
    [
        # classic: full name + .json
        ("IMG_1234.jpg", ["IMG_1234.jpg.json"], "IMG_1234.jpg.json"),
        # classic: extension stripped
        ("IMG_1234.jpg", ["IMG_1234.json"], "IMG_1234.json"),
        # current form, supplemental metadata
        (
            "IMG_1234.jpg",
            ["IMG_1234.jpg.supplemental-metadata.json"],
            "IMG_1234.jpg.supplemental-metadata.json",
        ),
        # truncated supplemental
        (
            "PXL_20240817.mp4",
            ["PXL_20240817.mp4.supplemental-metada.json"],
            "PXL_20240817.mp4.supplemental-metada.json",
        ),
        (
            "PXL_20240817.mp4",
            ["PXL_20240817.mp4.supplementa.json"],
            "PXL_20240817.mp4.supplementa.json",
        ),
        # -edited variant uses the original's sidecar
        ("IMG_1234-edited.jpg", ["IMG_1234.jpg.json"], "IMG_1234.jpg.json"),
        # "(1)" duplicate: suffix relocates after the extension
        ("IMG_1234(1).jpg", ["IMG_1234.jpg(1).json"], "IMG_1234.jpg(1).json"),
        # "(1)" duplicate with supplemental naming
        (
            "IMG_1234(1).jpg",
            ["IMG_1234.jpg.supplemental-metadata(1).json"],
            "IMG_1234.jpg.supplemental-metadata(1).json",
        ),
        # no sidecar
        ("orphan.jpg", ["something-else.json"], None),
    ],
)
def test_sidecar_matching(media: str, sidecars: list[str], expected: str | None) -> None:
    assert SidecarIndex(sidecars).find(media) == expected


def test_index_prefers_exact_over_supplemental() -> None:
    index = SidecarIndex(["IMG.jpg.json", "IMG.jpg.supplemental-metadata.json"])
    assert index.find("IMG.jpg") == "IMG.jpg.json"


def test_is_year_folder() -> None:
    assert is_year_folder("Photos from 2020")
    assert not is_year_folder("Goa Trip")
    assert not is_year_folder("Untitled(3)")


def _write_sidecar(
    path: Path, *, taken: int | None = None, created: int | None = None, gps=None, desc=""
) -> None:
    data: dict[str, object] = {"description": desc}
    if taken is not None:
        data["photoTakenTime"] = {"timestamp": str(taken)}
    if created is not None:
        data["creationTime"] = {"timestamp": str(created)}
    if gps is not None:
        data["geoData"] = {"latitude": gps[0], "longitude": gps[1], "altitude": 0.0}
    path.write_text(json.dumps(data), encoding="utf-8")


def test_parse_sidecar_fields(tmp_path: Path) -> None:
    sidecar = tmp_path / "x.json"
    _write_sidecar(sidecar, taken=1692113136, created=1692200000, gps=(36.7, -119.4), desc="beach")
    parsed = parse_sidecar(sidecar)
    assert parsed is not None
    assert parsed.taken_at == datetime(2023, 8, 15, 15, 25, 36, tzinfo=UTC)
    assert parsed.created_at is not None
    assert parsed.gps == (36.7, -119.4)
    assert parsed.description == "beach"


def test_parse_sidecar_zero_gps_is_absent(tmp_path: Path) -> None:
    sidecar = tmp_path / "x.json"
    _write_sidecar(sidecar, taken=1692113136, gps=(0.0, 0.0))
    parsed = parse_sidecar(sidecar)
    assert parsed is not None
    assert parsed.gps is None  # (0,0) means no GPS, not Null Island


def test_local_naive_single_conversion() -> None:
    """Aware-UTC -> local naive is exactly one conversion; no double-localization."""
    aware = datetime(2023, 8, 15, 14, 25, 36, tzinfo=UTC)
    assert local_naive(aware, None) == datetime(2023, 8, 15, 14, 25, 36)
    assert local_naive(aware, timedelta(hours=5, minutes=30)) == datetime(2023, 8, 15, 19, 55, 36)
    assert local_naive(aware, timedelta(hours=-8)) == datetime(2023, 8, 15, 6, 25, 36)


def test_scan_mini_takeout(tmp_path: Path) -> None:
    """A mini Takeout: year folders + album folders with duplicate copies and mixed sidecars."""
    root = tmp_path / "Takeout" / "Google Photos"
    year = root / "Photos from 2023"
    album = root / "Goa Trip"
    year.mkdir(parents=True)
    album.mkdir(parents=True)

    # year folder: a photo with supplemental sidecar, plus a -edited variant (no own sidecar)
    (year / "IMG_1.jpg").write_bytes(b"one")
    _write_sidecar(year / "IMG_1.jpg.supplemental-metadata.json", taken=1692113136)
    (year / "IMG_1-edited.jpg").write_bytes(b"one-edited")
    # a truncated-name "(1)" duplicate and a file with a missing sidecar
    (year / "IMG_2(1).jpg").write_bytes(b"two")
    _write_sidecar(year / "IMG_2.jpg(1).json", taken=1692200000)
    (year / "IMG_3.jpg").write_bytes(b"three")  # no sidecar
    # an orphan sidecar with no media
    _write_sidecar(year / "ghost.jpg.json", taken=1)

    # album folder: byte-identical duplicate copy of IMG_1
    (album / "IMG_1.jpg").write_bytes(b"one")
    _write_sidecar(album / "IMG_1.jpg.json", taken=1692113136)

    scan = scan_takeout(root)

    year_img1 = year / "IMG_1.jpg"
    assert year_img1 in scan.sidecars
    assert (year / "IMG_1-edited.jpg") in scan.sidecars  # matched original's sidecar
    assert (year / "IMG_2(1).jpg") in scan.sidecars  # relocated (1)
    assert (year / "IMG_3.jpg") in scan.missing_sidecar
    # album membership recorded only for the album-folder copy
    assert scan.albums[album / "IMG_1.jpg"] == "Goa Trip"
    assert year_img1 not in scan.albums
