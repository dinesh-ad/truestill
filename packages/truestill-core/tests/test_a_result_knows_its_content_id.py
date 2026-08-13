"""``execute`` establishes a content id for every file it places, and hands it back.

**The defect this pins.** The scan's size pre-filter deliberately skips hashing a file whose size
is unique - it cannot be an exact duplicate of anything - so a ``Resolution`` reaches execution
with ``hashes.sha256`` unset. ``execute`` then computes it, because the file is being read for
upload anyway, and wrote it to the catalog. It did **not** put it on the ``ActionResult``.

So the catalog knew each file's content id and the result did not, and every difference between
those two was invisible until something asked results-alone "which files did this run place".
The organize result grid asked, and drew **two photos for a run of four** - not an error, not a
warning, just half the run missing. The half that was missing was the half with unique sizes.

This lives in core rather than beside the grid because the hole was in core, and the next
surface to ask the same question would inherit it.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PIL import Image
from truestill_core.categorize import CategoryMatch, Confidence
from truestill_core.destinations import LocalDestination
from truestill_core.hashing import sha256_file
from truestill_core.models import ActionStatus, DateSource, Decision, FileHashes, Resolution
from truestill_core.organizer import execute

WHEN = datetime(2023, 1, 1, 12, 30)
CAT = CategoryMatch(label="Camera", reason="t", confidence=Confidence.HIGH, rule="device")


def _photo(path: Path, seed: int, size: tuple[int, int]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, ((seed * 37) % 256, (seed * 91) % 256, 40)).save(path, "JPEG")
    return path


def _resolution(source: Path, *, sha: str | None) -> Resolution:
    return Resolution(
        decision=Decision(
            source=source,
            category=CAT,
            captured_at=WHEN,
            date_source=DateSource.EXIF,
            date_tag=None,
            relative=Path("Camera/2023") / source.name,
        ),
        hashes=FileHashes(sha256=sha, perceptual=None),
        exact_duplicate=None,
        near_duplicate=None,
    )


def test_a_file_the_scan_never_hashed_still_comes_back_with_its_content_id(
    tmp_path: Path,
) -> None:
    """THE REGRESSION. ``hashes.sha256`` is None going in - as it is for every unique-size file -
    and the result must still name the content that was placed."""
    source = _photo(tmp_path / "src" / "unique.jpg", 1, (640, 480))
    destination = tmp_path / "lib"

    results = list(
        execute([_resolution(source, sha=None)], LocalDestination(destination), apply=True)
    )

    assert len(results) == 1
    outcome = results[0]
    assert outcome.status is ActionStatus.UPLOADED
    assert outcome.resolution.hashes.sha256 is None, "the fixture stopped covering the real case"
    assert outcome.sha256 == sha256_file(source), (
        "the run placed a file and did not say which content it was - anything asking results "
        "alone loses exactly the unique-size files"
    )


def test_the_id_on_the_result_is_the_one_that_was_already_known(tmp_path: Path) -> None:
    """The other half: when the scan DID hash, the result must not disagree with it. A second,
    independently computed id would be a silent fork of identity."""
    source = _photo(tmp_path / "src" / "known.jpg", 2, (500, 500))
    known = sha256_file(source)
    destination = tmp_path / "lib"

    results = list(
        execute([_resolution(source, sha=known)], LocalDestination(destination), apply=True)
    )

    assert results[0].sha256 == known


def test_an_outcome_that_placed_nothing_claims_no_content_id(tmp_path: Path) -> None:
    """A file that never reached the library has no placement to name. `None` is the honest
    answer, and it is what keeps the grid's `total` from promising a tile that cannot exist."""
    missing = tmp_path / "src" / "gone.jpg"
    missing.parent.mkdir(parents=True)
    destination = tmp_path / "lib"

    results = list(
        execute([_resolution(missing, sha=None)], LocalDestination(destination), apply=True)
    )

    assert results[0].status is ActionStatus.FAILED
    assert results[0].sha256 is None
