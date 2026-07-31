"""The exiftool `_original` sidecar as a date CANDIDATE (step 6, the last of the program).

**truestill never creates these files.** Its own writes use ``-overwrite_original``
(`exif._WRITE_FLAGS`), which keeps no sidecar. Any ``*_original`` beside a user's photo came
from **their own** exiftool use, on their own terms, at a time truestill knows nothing about.
That is precisely why it can only ever be an *offer* and never an authority: truestill has no
idea whether that file holds the original truth or a mistake the user was correcting.

So the machine suggests and the human commits, and the commit path is the one step 5 already
built - `confirm_file_date`, which records ``HUMAN_CONFIRMED`` and un-bakes. Nothing here
decides a date.

**Three outcomes, and two of them are not the same.** "There is no candidate" and "truestill
could not look" are different facts about different things - the first is about the file, the
second about truestill's reach - and a user scanning a page must be able to tell them apart
without reading carefully. They are separate statuses, not two wordings of one.

**A sibling that agrees is not offered.** Accepting it would promote a machine-derived date to
``HUMAN_CONFIRMED`` on the strength of the machine agreeing with itself, which manufactures
confidence rather than establishing it - the exact failure this program exists to remove.
"""

from __future__ import annotations

import shutil
import subprocess
from datetime import datetime
from pathlib import Path

import pytest
import truestill_app.service.date_rescue as module
from PIL import Image
from truestill_app.service.date_rescue import original_candidates
from truestill_core.catalog import Catalog

pytestmark = pytest.mark.skipif(shutil.which("exiftool") is None, reason="needs exiftool")

SHA = "sha-000"


def _stamp(path: Path, when: str) -> None:
    subprocess.run(
        ["exiftool", "-q", "-overwrite_original", f"-DateTimeOriginal={when}", str(path)],
        check=True,
    )


def _library(tmp_path: Path, *, live: str, sibling: str | None) -> Path:
    """A source photo with an optional ``_original`` beside it, catalogued by sha256."""
    db = tmp_path / "c.sqlite"
    source = tmp_path / "src" / "a.jpg"
    source.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (48, 32), "navy").save(source)
    _stamp(source, live)
    if sibling is not None:
        backup = source.with_name(source.name + "_original")
        shutil.copy2(source, backup)
        _stamp(backup, sibling)
    with Catalog(db) as catalog:
        catalog.record_uploaded(
            source_path=str(source),
            original_name="a.jpg",
            sha256=SHA,
            copy_sha256=SHA,
            perceptual=None,
            size=source.stat().st_size,
            captured_at=datetime(2014, 8, 16, 10, 46, 26).isoformat(),
            category="Camera",
            relative="Camera/2014/a.jpg",
        )
    return db


# --- the offer ---------------------------------------------------------------------------------


def test_a_sibling_with_a_different_date_is_offered(tmp_path: Path) -> None:
    """The case the feature exists for: the backup still holds the date before an edit."""
    db = _library(tmp_path, live="2014:08:16 10:46:26", sibling="2011:03:04 09:15:00")

    candidate = original_candidates(db, [SHA])[SHA]

    assert candidate["status"] == "offer"
    assert candidate["captured_at"].startswith("2011-03-04")


def test_the_offer_carries_a_date_the_rescue_field_can_take(tmp_path: Path) -> None:
    """One home for the commit: the offer pre-fills the existing field, it does not accept."""
    db = _library(tmp_path, live="2014:08:16 10:46:26", sibling="2011:03:04 09:15:00")

    candidate = original_candidates(db, [SHA])[SHA]

    assert datetime.fromisoformat(candidate["captured_at"]).date().isoformat() == "2011-03-04"


# --- an offer that would change nothing is not made ----------------------------------------------


def test_a_sibling_that_agrees_is_not_offered(tmp_path: Path) -> None:
    """Accepting would upgrade a machine date to HUMAN_CONFIRMED on the machine agreeing with
    itself. That manufactures confidence, and it is also just noise on a trust screen."""
    db = _library(tmp_path, live="2014:08:16 10:46:26", sibling="2014:08:16 10:46:26")

    assert original_candidates(db, [SHA])[SHA]["status"] == "none"


def test_a_sibling_with_no_readable_date_is_not_offered(tmp_path: Path) -> None:
    """Nothing to suggest is not a candidate; it is the absence of one."""
    db = _library(tmp_path, live="2014:08:16 10:46:26", sibling=None)
    source = tmp_path / "src" / "a.jpg"
    backup = source.with_name(source.name + "_original")
    backup.write_bytes(b"not an image")

    assert original_candidates(db, [SHA])[SHA]["status"] == "none"


def test_no_sibling_at_all_is_none_not_unreachable(tmp_path: Path) -> None:
    """We looked and there was nothing. That is a fact about the file."""
    db = _library(tmp_path, live="2014:08:16 10:46:26", sibling=None)

    assert original_candidates(db, [SHA])[SHA]["status"] == "none"


# --- cannot look, which is a different fact ------------------------------------------------------


def test_a_missing_source_is_unreachable_not_none(tmp_path: Path) -> None:
    """The (xx) case: source_path is absolute, and in copy mode the source may be long gone.

    Reporting "no candidate" here would be a claim about the photo that truestill is not
    entitled to make - it did not look, it could not.
    """
    db = _library(tmp_path, live="2014:08:16 10:46:26", sibling="2011:03:04 09:15:00")
    shutil.rmtree(tmp_path / "src")

    assert original_candidates(db, [SHA])[SHA]["status"] == "unreachable"


def test_the_three_statuses_are_distinct_values(tmp_path: Path) -> None:
    """Pinned as separate states, so a renderer cannot collapse two into one wording.

    "no sidecar" and "cannot reach the source" must be distinguishable at a glance, which is
    only possible if they are distinguishable in the payload.
    """
    with_offer = _library(tmp_path / "a", live="2014:08:16 10:46:26", sibling="2011:03:04 09:15:00")
    without = _library(tmp_path / "b", live="2014:08:16 10:46:26", sibling=None)
    gone = _library(tmp_path / "c", live="2014:08:16 10:46:26", sibling="2011:03:04 09:15:00")
    shutil.rmtree(tmp_path / "c" / "src")

    statuses = {
        original_candidates(with_offer, [SHA])[SHA]["status"],
        original_candidates(without, [SHA])[SHA]["status"],
        original_candidates(gone, [SHA])[SHA]["status"],
    }

    assert statuses == {"offer", "none", "unreachable"}


def test_an_unknown_sha_is_unreachable(tmp_path: Path) -> None:
    """No row means no source path to check - not an assertion that the file is clean."""
    db = _library(tmp_path, live="2014:08:16 10:46:26", sibling=None)

    assert original_candidates(db, ["not-in-the-catalog"])["not-in-the-catalog"]["status"] == (
        "unreachable"
    )


# --- cost -----------------------------------------------------------------------------------------


def test_only_files_with_a_sibling_cost_an_exiftool_read(tmp_path: Path) -> None:
    """O(page) stats; exiftool proportional to HITS, not rows - which is what makes it eager.

    A tier can hold 2,300 files. Reading metadata per row would make opening the honesty view a
    multi-minute operation; a stat per row is microseconds and almost always answers.
    """
    db = _library(tmp_path, live="2014:08:16 10:46:26", sibling=None)
    reads: list[list[Path]] = []
    real = module.read_metadata
    module.read_metadata = lambda paths, **kw: (reads.append(list(paths)), real(paths, **kw))[1]
    try:
        original_candidates(db, [SHA])
    finally:
        module.read_metadata = real

    assert not any(reads), f"exiftool ran for a file with no sidecar: {reads}"
