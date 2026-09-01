"""`verify` must not call a tidied file lost, and must still call a lost file lost. `(aba)`

**The harm is not only the sentence.** `MISSING` drives `mark_copy_missing` at both surfaces -
`cli.py` and `service/verify.py` each carry
``elif result.status is CopyStatus.MISSING and still_here is not None:`` - so a false alarm writes
``missing_at`` into the catalog, and that column feeds `single_copy_shas` and `custody_floor`. A
user who tidies one folder by hand gets told twelve files are missing **and** has their library
quietly reported as less redundant than it is.

⚠ **THE FALSE NEGATIVE IS THE REGRESSION TO FEAR, and it is the reason half this file exists.**
`verify` is the feature whose whole product is being trustworthy; a search that relocates
everything would make a genuinely vanished file read as fine, which is far worse than the defect
being fixed. Both directions are mutation-proved.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from truestill_core.hashing import sha256_file
from truestill_core.verify import VERIFY_WORDING, CopyStatus, CopyToVerify, verify_copies

PHOTO = b"a photograph, several bytes long" * 40


def _drive(tmp_path: Path) -> Path:
    root = tmp_path / "drive"
    (root / "Saved").mkdir(parents=True)
    return root


def _copy_of(path: Path, relative: str) -> CopyToVerify:
    return CopyToVerify(
        sha256="c" * 64,
        relative=relative,
        expected_hash=sha256_file(path),
        size=path.stat().st_size,
    )


def test_a_file_moved_by_hand_is_found_and_named(tmp_path: Path) -> None:
    """The defect, in the shape it was found: a file tidied out of `Saved/` into its trip folder."""
    root = _drive(tmp_path)
    moved_to = root / "Trips" / "Wayanad"
    moved_to.mkdir(parents=True)
    photo = moved_to / "a.jpg"
    photo.write_bytes(PHOTO)

    results = verify_copies([_copy_of(photo, "Saved/a.jpg")], root)

    assert [r.status for r in results] == [CopyStatus.MOVED]
    assert results[0].detail == "found at Trips/Wayanad/a.jpg", results[0].detail


def test_a_file_that_really_vanished_is_still_reported_missing(tmp_path: Path) -> None:
    """⚠ **THE REGRESSION THIS FILE EXISTS TO PREVENT.** Loud must stay loud."""
    root = _drive(tmp_path)
    gone = root / "Saved" / "gone.jpg"
    gone.write_bytes(PHOTO)
    copy = _copy_of(gone, "Saved/gone.jpg")
    gone.unlink()

    results = verify_copies([copy], root)

    assert [r.status for r in results] == [CopyStatus.MISSING]
    assert results[0].detail is None


def test_a_same_sized_file_elsewhere_is_not_accepted_as_the_same_photograph(
    tmp_path: Path,
) -> None:
    """🔑 **Size narrows; SHA-256 decides.** A same-sized neighbour is not evidence."""
    root = _drive(tmp_path)
    original = root / "Saved" / "gone.jpg"
    original.write_bytes(PHOTO)
    copy = _copy_of(original, "Saved/gone.jpg")
    original.unlink()

    impostor = root / "Trips" / "other.jpg"
    impostor.parent.mkdir(parents=True)
    impostor.write_bytes(b"x" * len(PHOTO))  # same size, different bytes
    assert impostor.stat().st_size == copy.size, "fixture check: the sizes must collide"

    results = verify_copies([copy], root)

    assert [r.status for r in results] == [CopyStatus.MISSING]


def test_a_copy_with_no_recorded_hash_is_never_relocated(tmp_path: Path) -> None:
    """Unknown is not a match. With no ``expected_hash`` there is no identity to search by."""
    root = _drive(tmp_path)
    elsewhere = root / "Trips" / "a.jpg"
    elsewhere.parent.mkdir(parents=True)
    elsewhere.write_bytes(PHOTO)

    copy = CopyToVerify(
        sha256="c" * 64, relative="Saved/a.jpg", expected_hash=None, size=len(PHOTO)
    )
    results = verify_copies([copy], root)

    assert [r.status for r in results] == [CopyStatus.MISSING]


def test_a_changed_file_at_the_recorded_path_stays_a_mismatch(tmp_path: Path) -> None:
    """⚠ **MISMATCH is a different fact and the search must not touch it.**

    Present-but-changed has its own remedy. Looking elsewhere for good bytes would report a file
    as fine while the copy at the recorded path is still damaged.
    """
    root = _drive(tmp_path)
    at_path = root / "Saved" / "a.jpg"
    at_path.write_bytes(PHOTO)
    copy = _copy_of(at_path, "Saved/a.jpg")
    at_path.write_bytes(b"corrupted" * 4)

    good_copy_elsewhere = root / "Trips" / "a.jpg"
    good_copy_elsewhere.parent.mkdir(parents=True)
    good_copy_elsewhere.write_bytes(PHOTO)

    results = verify_copies([copy], root)

    assert [r.status for r in results] == [CopyStatus.MISMATCH]


def test_a_mismatch_is_not_relocated_even_when_a_miss_opens_the_search(tmp_path: Path) -> None:
    """⚠ **FOUND BY A SURVIVING MUTATION, and the gap was in the test rather than the code.**

    `test_a_changed_file_at_the_recorded_path_stays_a_mismatch` cannot reach the search at all:
    with nothing MISSING the outer gate never opens, so a mutant widening the search to every
    non-VERIFIED status passed it untouched. This drive carries **both** - one real loss to open
    the gate, and one corrupted file whose good bytes sit elsewhere - which is the only shape that
    can tell the two claims apart.
    """
    root = _drive(tmp_path)

    lost = root / "Saved" / "lost.jpg"
    lost.write_bytes(PHOTO + b"lost")
    lost_copy = _copy_of(lost, "Saved/lost.jpg")
    lost.unlink()

    damaged = root / "Saved" / "damaged.jpg"
    damaged.write_bytes(PHOTO)
    damaged_copy = _copy_of(damaged, "Saved/damaged.jpg")
    damaged.write_bytes(b"corrupted" * 4)
    intact_twin = root / "Trips" / "damaged.jpg"
    intact_twin.parent.mkdir(parents=True)
    intact_twin.write_bytes(PHOTO)  # the ORIGINAL bytes, findable by the search

    results = verify_copies([lost_copy, damaged_copy], root)

    assert len(results) == 2, f"a result was duplicated or dropped: {results}"
    by_relative = {r.copy.relative: r.status for r in results}
    assert by_relative["Saved/damaged.jpg"] is CopyStatus.MISMATCH, (
        "a corrupted file was reported as merely moved, so the damage at the recorded path "
        "would never be repaired"
    )
    assert by_relative["Saved/lost.jpg"] is CopyStatus.MISSING


def test_a_second_copy_elsewhere_does_not_disturb_a_verified_one(tmp_path: Path) -> None:
    """Two copies of one photograph, one of them at the recorded path: nothing changes."""
    root = _drive(tmp_path)
    at_path = root / "Saved" / "a.jpg"
    at_path.write_bytes(PHOTO)
    twin = root / "Trips" / "a.jpg"
    twin.parent.mkdir(parents=True)
    twin.write_bytes(PHOTO)

    results = verify_copies([_copy_of(at_path, "Saved/a.jpg")], root)

    assert [r.status for r in results] == [CopyStatus.VERIFIED]


def test_a_clean_verify_never_walks_the_drive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """🔑 **THE COST GATE.** `verify` never walked before `(aba)`; a clean run must still not.

    Measured on a real 109,431-file library the walk is 1.73 s, which is cheap but not free, and
    it is charged only to the run that is about to claim a loss.
    """
    root = _drive(tmp_path)
    photo = root / "Saved" / "a.jpg"
    photo.write_bytes(PHOTO)

    walked: list[str] = []

    def spy(path: object, *_args: object, **_kwargs: object) -> object:
        walked.append(str(path))
        return iter(())

    monkeypatch.setattr(os, "walk", spy)
    results = verify_copies([_copy_of(photo, "Saved/a.jpg")], root)

    assert [r.status for r in results] == [CopyStatus.VERIFIED]
    assert walked == [], f"a clean verify walked the drive: {walked}"


def test_one_missing_copy_walks_the_drive_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The other half of the gate: many misses must not mean many walks."""
    root = _drive(tmp_path)
    copies = []
    for i in range(5):
        photo = root / "Saved" / f"{i}.jpg"
        photo.write_bytes(PHOTO + bytes([i]))
        copies.append(_copy_of(photo, f"Saved/{i}.jpg"))
        photo.unlink()

    real_walk = os.walk
    walks: list[str] = []

    def spy(path: object, *args: object, **kwargs: object):  # type: ignore[no-untyped-def]
        walks.append(str(path))
        return real_walk(path, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(os, "walk", spy)
    results = verify_copies(copies, root)

    assert {r.status for r in results} == {CopyStatus.MISSING}
    assert len(walks) == 1, f"five misses caused {len(walks)} walks"


def test_the_two_claims_have_one_wording_home_and_say_different_things() -> None:
    """`(aba)`'s design: different facts, different remedies, neither surface composing its own."""
    missing = VERIFY_WORDING[CopyStatus.MISSING]
    moved = VERIFY_WORDING[CopyStatus.MOVED]

    assert missing != moved
    assert "gone" in missing
    assert "restoring" in missing
    assert "nothing was lost" in moved
    assert set(VERIFY_WORDING) == set(CopyStatus), "every status needs a sentence"
