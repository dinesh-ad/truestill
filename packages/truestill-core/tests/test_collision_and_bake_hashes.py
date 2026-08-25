"""Two data-loss invariants the §9 audit found unpinned (2026-08-03).

Neither was broken. Both were true by the behaviour of one function with nothing asserting it,
which is the state a refactor turns into a defect silently -- so each is proven here by
mutation rather than by a natural red.

* **A collision never overwrites unrelated content.** Dedup handles identical bytes, so a
  collision at the destination means two *different* files landed on one name. `_free_relative`
  suffixes the newcomer. If it ever returned the taken path, `upload` would `copy2` straight
  over a photo already organized -- with no error, and nothing in the report to read.
* **A bake keeps the two hashes distinct.** `sha256` is the source; `copy_sha256` is what was
  actually written, which a metadata bake deliberately makes different. `verify` compares
  against `copy_sha256`. Writing the source hash into both would make every baked file compare
  against bytes that were never on the drive -- healthy backups reported corrupt, or real
  corruption masked. `test_surface_parity.py` pins that *verify reads the right column*; this
  pins that the two columns hold different things in the first place.
"""

from __future__ import annotations

import hashlib
import shutil
from datetime import datetime
from pathlib import Path

import pytest
from PIL import Image
from truestill_core.catalog import Catalog
from truestill_core.categorize import CategoryMatch, Confidence
from truestill_core.destinations import LocalDestination
from truestill_core.models import (
    ActionStatus,
    DateSource,
    Decision,
    FileHashes,
    Resolution,
    RuleName,
)
from truestill_core.organizer import execute
from truestill_core.takeout import IngestContext, MetadataWrite

WHEN = datetime(2019, 4, 3, 8, 15)
#: Every file organized here lands on this one relative path, which is the point.
CONTESTED = f"Camera/{WHEN:%Y}/{WHEN:%m}/IMG_0001.jpg"


def _jpeg(path: Path, tint: int) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (48, 32), (tint, 40, 90)).save(path, "JPEG")
    return path


def _resolution(source: Path, sha: str, relative: str = CONTESTED) -> Resolution:
    decision = Decision(
        source=source,
        category=CategoryMatch(
            label="Camera", reason="t", confidence=Confidence.MEDIUM, rule=RuleName.DEVICE
        ),
        captured_at=WHEN,
        date_source=DateSource.EXIF,
        date_tag=None,
        relative=Path(relative),
    )
    return Resolution(
        decision=decision,
        hashes=FileHashes(sha256=sha, perceptual=None),
        exact_duplicate=None,
        near_duplicate=None,
    )


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# --- a collision never overwrites unrelated content ---------------------------------------


def test_two_different_files_on_one_name_both_survive(tmp_path: Path) -> None:
    """The invariant, asserted on the bytes rather than on the status label.

    A status of RENAMED would be reported by an implementation that overwrote anyway, so the
    assertion that matters is that both originals are readable at the destination afterwards.
    """
    first = _jpeg(tmp_path / "src" / "a" / "IMG_0001.jpg", 10)
    second = _jpeg(tmp_path / "src" / "b" / "IMG_0001.jpg", 200)
    assert first.read_bytes() != second.read_bytes(), "the fixture must supply distinct content"
    dest = tmp_path / "out"

    results = execute(
        [_resolution(first, _sha(first)), _resolution(second, _sha(second))],
        LocalDestination(dest),
        apply=True,
        catalog=None,
    )

    assert [r.status for r in results] == [ActionStatus.UPLOADED, ActionStatus.RENAMED]
    written = sorted(p for p in dest.rglob("*.jpg") if p.is_file())
    assert len(written) == 2, "one file was overwritten by the other"
    assert {p.read_bytes() for p in written} == {first.read_bytes(), second.read_bytes()}
    assert {p.name for p in written} == {"IMG_0001.jpg", "IMG_0001_1.jpg"}


def test_a_third_file_on_the_same_name_keeps_counting(tmp_path: Path) -> None:
    """The suffix must keep searching, not stop at the first alternative it tries."""
    sources = [_jpeg(tmp_path / "src" / str(i) / "IMG_0001.jpg", i * 60 + 10) for i in range(3)]
    dest = tmp_path / "out"

    execute(
        [_resolution(s, _sha(s)) for s in sources],
        LocalDestination(dest),
        apply=True,
        catalog=None,
    )

    written = sorted(p for p in dest.rglob("*.jpg") if p.is_file())
    assert {p.name for p in written} == {"IMG_0001.jpg", "IMG_0001_1.jpg", "IMG_0001_2.jpg"}
    assert len({p.read_bytes() for p in written}) == 3


def test_an_uncontested_name_is_not_suffixed(tmp_path: Path) -> None:
    """Cry-wolf: the ordinary case must keep the name the layout chose."""
    only = _jpeg(tmp_path / "src" / "IMG_0001.jpg", 10)
    dest = tmp_path / "out"

    results = execute(
        [_resolution(only, _sha(only))], LocalDestination(dest), apply=True, catalog=None
    )

    assert [r.status for r in results] == [ActionStatus.UPLOADED]
    assert [p.name for p in dest.rglob("*.jpg")] == ["IMG_0001.jpg"]


# --- source and copy hashes keep their distinct meanings across a bake ---------------------


@pytest.mark.skipif(shutil.which("exiftool") is None, reason="exiftool not installed")
def test_a_bake_records_the_copy_hash_of_what_it_actually_wrote(tmp_path: Path) -> None:
    """`copy_sha256` must describe the bytes on the drive, not the bytes we read.

    A bake writes metadata into a staged copy, so the uploaded file genuinely differs from the
    source. Asserted three ways, because "they differ" alone would pass for an implementation
    that stored two unrelated wrong values: the source hash still describes the source, the
    copy hash still describes the copy, and the two are not equal.
    """
    source = _jpeg(tmp_path / "src" / "IMG_0001.jpg", 10)
    source_sha = _sha(source)
    source_bytes_before = source.read_bytes()
    dest = tmp_path / "out"
    db = tmp_path / "catalog.sqlite"
    ingest = IngestContext(
        writes={str(source): MetadataWrite(taken_at_local=WHEN, gps=None, description="baked")}
    )

    with Catalog(db) as catalog:
        results = execute(
            [_resolution(source, source_sha)],
            LocalDestination(dest),
            apply=True,
            ingest=ingest,
            catalog=catalog,
        )
        assert [r.status for r in results] == [ActionStatus.UPLOADED]
        row = catalog.find_by_sha256(source_sha)

    assert row is not None
    written = dest / CONTESTED
    assert written.is_file()

    assert row["sha256"] == source_sha, "the source hash must still describe the source"
    assert row["copy_sha256"] == _sha(written), "the copy hash must describe what was written"
    assert row["copy_sha256"] != row["sha256"], "a bake changes the bytes; the hashes must differ"
    assert source.read_bytes() == source_bytes_before, "the original must be untouched"
