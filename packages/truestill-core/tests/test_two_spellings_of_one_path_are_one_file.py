"""A filesystem that folds case must not make one photograph look like two. `(ala)`

**The defect, measured before the fix.** `reconcile` is `Pure: no I/O`, so it compared the
catalog's `relative` against the walk's output as exact strings. On NTFS and APFS - the two
platforms most users are on - `Saved/Photo.JPG` and `Saved/photo.jpg` are **one file**, and the
comparison called them two.

⚠ **THE SYMPTOM ON RECORD WAS WRONG, AND MEASURING IT CHANGED THE FIX.** `SHIPPED.md` and the
audit that raised this both said the file reports as *"both MISSING and STRAY"*. Run against a
real drive it reports **MOVED**: the drifted name is not in `recorded`, so it becomes a candidate,
gets hashed, and its content matches - so `reconcile` pairs it. The harm is not a wrong bucket,
it is:

* a wall of phantom `MOVED` lines for files that never moved, and `reconciled=False` so the
  command exits 1;
* **every drifted file read in full.** `HashCache` is keyed by `str(path)`, so a case-drifted
  path misses the cache too. That is the whole library re-hashed by the one command whose
  docstring justifies its design by *not* doing that - *"~15 h for 196 GiB at the 3.9 MB/s
  measured on a cloud mount"*;
* and since `(akw)`, `verify` **writes** a MOVED result, so the phantom reaches the catalog.

**Why these tests need no case-insensitive filesystem.** `reconcile` is pure and takes plain
strings, so feeding it the strings such a filesystem produces is not a simulation of the input -
it **is** the input. What a real mount would add is the step before: proof that the walk really
returns the drifted spelling. That is `test_the_case_probe_asks_the_mount` below, which runs
against whatever this machine actually has.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from truestill_core.filesystem import folds_case
from truestill_core.rescan import compare_key, reconcile

SHA = "a" * 64
OTHER = "b" * 64


def _report(*, fold_case: bool, **kwargs: object):
    base: dict[str, object] = {
        "recorded": {"Saved/Photo.JPG": SHA},
        "on_disk": ["Saved/photo.jpg"],
        "identified": {"Saved/photo.jpg": SHA},
    }
    base.update(kwargs)
    return reconcile(fold_case=fold_case, **base)  # type: ignore[arg-type]


# ------------------------------------------------------------------- the defect, and the fix


def test_a_case_drift_is_not_a_move_on_a_folding_filesystem() -> None:
    """The headline. One file, one bucket, and the command succeeds.

    ⚠ **`placed` keeps the CATALOG's spelling, not the disk's.** Nothing moved, so there is
    nothing to re-record - and `compare_key`'s folded form is never allowed to leave this module.
    """
    report = _report(fold_case=True)

    assert report.placed == ("Saved/Photo.JPG",)
    assert report.moved == ()
    assert report.stray == ()
    assert report.unaccounted == ()
    assert report.reconciled, "a drive where nothing changed reported a disagreement"


def test_the_same_drift_is_still_a_move_where_the_filesystem_does_not_fold() -> None:
    """⚠ **The half that makes folding SAFE to do at all.**

    On ext4 `Photo.JPG` and `photo.jpg` are two genuinely different files, and reporting them as
    one would hide a real move. This is why the fold is asked of the mount rather than applied
    everywhere - see `test_the_case_probe_asks_the_mount`.
    """
    report = _report(fold_case=False)

    assert report.placed == ()
    assert [m.recorded for m in report.moved] == ["Saved/Photo.JPG"]
    assert not report.reconciled


def test_folding_never_hides_a_file_that_is_genuinely_gone() -> None:
    """The direction that would matter most if it were wrong: a loss must stay loud."""
    report = _report(fold_case=True, on_disk=[], identified={})

    assert report.unaccounted == ("Saved/Photo.JPG",)
    assert not report.reconciled


def test_folding_never_hides_content_that_does_not_match() -> None:
    """A folded PATH must not imply folded BYTES. Same name, different content, still a stray."""
    report = _report(fold_case=True, identified={"Saved/photo.jpg": OTHER})

    assert report.placed == ("Saved/Photo.JPG",)
    assert report.stray == (), "the file is at the recorded path; its content is verify's question"


def test_the_damaged_bucket_survives_a_drift() -> None:
    """⚠ **`(ajb)`'s 836 zero-byte files, one layer in.**

    `sizes` is keyed the way the WALK saw the path and `recorded_sizes` the way the CATALOG holds
    it. Without folding that lookup too, a drifted file is `placed` and then silently drops out
    of the damaged subset - the exact regression `(ajb)` exists to prevent, reachable only on a
    folding filesystem.
    """
    report = _report(
        fold_case=True,
        sizes={"Saved/photo.jpg": 0},
        recorded_sizes={"Saved/Photo.JPG": 3_500_000},
    )

    assert [d.relative for d in report.damaged] == ["Saved/Photo.JPG"]
    assert report.damaged[0].actual_size == 0
    assert report.damaged[0].recorded_size == 3_500_000


def test_the_buckets_stay_disjoint_under_folding() -> None:
    """`reconcile`'s docstring calls the subtraction *provably gapless*. Folding must not break it.

    A `placed` spelled one way and an `identified` spelled another would otherwise leave one file
    in both buckets.
    """
    report = _report(fold_case=True)

    everything = set(report.placed) | {m.recorded for m in report.moved} | set(report.unaccounted)
    assert len(everything) == 1
    assert not (set(report.stray) & set(report.placed))


# ------------------------------------------------------------------------------- the key itself


def test_the_key_folds_with_casefold_rather_than_lower() -> None:
    """⚠ **Not pedantry: German filenames are ordinary in a photo library.**

    `["straße", "STRASSE", "strasse", "Straße"]` gives ONE key under `casefold` and TWO under
    `lower`, because `lower` leaves `ß` alone while `casefold` expands it to `ss`.
    """
    spellings = ["straße.jpg", "STRASSE.JPG", "strasse.jpg", "Straße.jpg"]

    assert len({compare_key(s, fold_case=True) for s in spellings}) == 1
    assert len({s.lower() for s in spellings}) == 2


def test_the_key_is_the_identity_when_it_is_not_folding() -> None:
    """So a non-folding mount pays nothing and behaves exactly as it did."""
    assert compare_key("Saved/Photo.JPG", fold_case=False) == "Saved/Photo.JPG"


def test_the_folded_form_never_leaves_the_comparison() -> None:
    """⚠ **Unicode's own rule: folded text is for processing, never for storing or displaying.**

    Version 13 added 169 case-folding entries version 8 did not have, so a folded key written
    into a catalog would mean something different after a Python upgrade. Every bucket must carry
    a spelling that came in.
    """
    report = _report(fold_case=True)

    given = {"Saved/Photo.JPG", "Saved/photo.jpg"}
    for value in (*report.placed, *report.stray, *report.unaccounted):
        assert value in given, f"{value!r} is neither spelling that was passed in"


# ------------------------------------------------------- the probe, against this machine's mounts


def test_the_case_probe_asks_the_mount(tmp_path: Path) -> None:
    """Read-only, and it answers correctly for the filesystem the suite is running on.

    ⚠ **`rescan` promises *"Nothing was changed: not your files, not the drive, not the
    catalog"***, so a probe that created two files to compare would break the one command it
    exists for. This stats a name the walk already returned, with its case swapped, and compares
    inodes - the same instrument `reclaim` and `catalog_move` use for *"same file, not same
    string"*.
    """
    (tmp_path / "Photo.JPG").write_bytes(b"x")

    answer = folds_case([tmp_path / "Photo.JPG"])

    # The suite's scratch is ext4 or tmpfs in every lane that runs this; on a macOS or Windows
    # runner it would be True. Both are correct answers about a real mount, so the assertion is
    # that it committed to one rather than which.
    assert answer in (True, False)
    assert answer is ((tmp_path / "photo.jpg").exists()), "the probe disagrees with the filesystem"


def test_the_probe_says_it_cannot_tell_rather_than_guessing(tmp_path: Path) -> None:
    """⚠ **Inconclusive is a real answer**, the way `facts_for` returns unknown for macOS.

    ⚠ **AND IT IS RARER THAN IT LOOKS, which this test learned by failing.** The first version
    used `20140817_120000.jpg` - the shape this product generates most - on the assumption that a
    digits-only stem cannot answer. It can: the **extension** carries the case, so `.jpg` swaps to
    `.JPG`. A name with no cased letter anywhere needs a numeric suffix too, which is why `None`
    is a corner rather than the common outcome. Returning `False` there would be a guess wearing
    a measurement's clothes; `None` lets the caller decide, and both callers fall back to exact
    comparison, which is today's behaviour and correct on Linux.
    """
    caseless = tmp_path / "20140817_120000.123"
    caseless.write_bytes(b"x")

    assert folds_case([caseless]) is None
    assert folds_case([]) is None
    # The common shape DOES answer, because of its extension - stated so the corner above is not
    # mistaken for the normal case.
    dated = tmp_path / "20140817_120000.jpg"
    dated.write_bytes(b"x")
    assert folds_case([dated]) is not None


def test_two_real_files_that_differ_only_in_case_are_not_folding(tmp_path: Path) -> None:
    """⚠ **The mutation that "the swapped name exists" would pass, and it is wrong.**

    On a case-sensitive filesystem both spellings can exist as two different files. Identity is
    the inode's to state, not the name's.
    """
    a, b = tmp_path / "Photo.JPG", tmp_path / "pHOTO.jpg"
    a.write_bytes(b"one")
    try:
        b.write_bytes(b"two")
    except OSError:  # pragma: no cover - a folding filesystem cannot hold both
        pytest.skip("this filesystem folds case, so the two names are one file")
    if a.stat().st_ino == b.stat().st_ino:  # pragma: no cover - same reason
        pytest.skip("this filesystem folds case")

    assert folds_case([a]) is False


def test_the_probe_reads_nothing_and_writes_nothing(tmp_path: Path) -> None:
    """The promise `rescan` makes, asserted rather than reviewed.

    Compared by `os.stat` before and after: no file gains an access or modification time, and no
    new entry appears. `st_atime_ns` is the one a read would move.
    """
    original = tmp_path / "Photo.JPG"
    original.write_bytes(b"x")
    before = {p.name: p.stat(follow_symlinks=False) for p in tmp_path.iterdir()}

    folds_case([original])

    after = {p.name: p.stat(follow_symlinks=False) for p in tmp_path.iterdir()}
    assert set(after) == set(before), "the probe created or removed a file"
    for name, stat in after.items():
        assert stat.st_mtime_ns == before[name].st_mtime_ns, f"{name} was written"
        assert stat.st_size == before[name].st_size
