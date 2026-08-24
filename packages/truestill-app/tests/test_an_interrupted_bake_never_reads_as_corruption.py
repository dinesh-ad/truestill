"""A bake killed mid-write leaves the copy UNVERIFIABLE, never MISMATCH. `(agv)`

⚠ **THE HARM IS THE SENTENCE, NOT THE MISSING RECORD, and this file asserts the sentence.**
Measured in P47 over real 16-23 MB camera files: kill a bake between `write_metadata_batch` and
`record_bake` and the photograph carries exactly the date its owner asked for, while
`file_copies.copy_sha256` still holds the pre-bake hash. `verify` then re-reads it, reports
**MISMATCH** - documented in `truestill_core.verify` as *"the file is present but its bytes
changed (corruption)"* - exits **1**, and prints *"re-copy the source to restore a bad file"*.
**Following that advice overwrites a correct bake with the pre-bake source, and appears to work**,
because re-copying restores the hash the stale catalog expects.

`(agv)`'s own constraint, honoured here: **a test aimed at `date_baked_at` would pass against a fix
that leaves `verify` still calling the photograph corrupt.** So every assertion below is about
what `verify` concludes.

**The kill is real** (`os._exit(9)` in a child process), not a synthesised catalog state: a
constructed row proves the classifier and says nothing about whether the window is reachable
through the code that actually runs.

**Why UNVERIFIABLE rather than a new status.** `verify` already distinguishes *"we did not check"*
from *"we found no damage"*, and during a bake the catalog genuinely does not know what the bytes
should be - the expected value is being replaced. `file_copies.bake_started_at` (schema v22) is the
fact that had nowhere to go, the same reasoning `(abg)` used for `missing_at` and `(agk)` for
`inplace_moves.outcome`: an unknown must not be spelled as one of the answers.
"""

from __future__ import annotations

import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path

import pytest
from PIL import Image
from truestill_app.service.bake import bake_run
from truestill_core.catalog import Catalog
from truestill_core.drive import create_marker
from truestill_core.hashing import sha256_file
from truestill_core.verify import CopyStatus, CopyToVerify, verify_copies

CONFIRMED = datetime(2014, 8, 16, 10, 46, 26)
_RELATIVE = "Camera/2014/a.jpg"


def _library(tmp_path: Path) -> tuple[Path, Path, str, str]:
    """A registered drive holding one photo with a confirmed date, ready to bake."""
    db, root = tmp_path / "c.sqlite", tmp_path / "drive"
    root.mkdir()
    marker = create_marker(root, label="Memory Drive")
    path = root / _RELATIVE
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (48, 32), "navy").save(path)
    sha = sha256_file(path)
    with Catalog(db) as catalog:
        catalog.upsert_drive(uuid=marker.uuid, label=marker.label)
        catalog.record_uploaded(
            source_path=f"/src/{Path(_RELATIVE).name}",
            original_name=Path(_RELATIVE).name,
            sha256=sha,
            copy_sha256=sha,
            perceptual=None,
            size=path.stat().st_size,
            captured_at="2014-08-16T10:46:26",
            category="Camera",
            relative=_RELATIVE,
            drive_uuid=marker.uuid,
        )
        catalog.confirm_date(sha, CONFIRMED.isoformat(), confirmed_by="test")
    return db, root, marker.uuid, sha


def _verify(db: Path, root: Path, drive_uuid: str) -> dict[str, CopyStatus]:
    with Catalog(db) as catalog:
        copies = [CopyToVerify.from_row(r) for r in catalog.copies_on_drive(drive_uuid)]
    return {r.copy.relative: r.status for r in verify_copies(copies, root)}


def _bake(db: Path, root: Path) -> dict:
    target = bake_run(root, db)
    assert callable(target), f"bake_run refused: {target}"
    return target(lambda _p: None, threading.Event())  # type: ignore[no-any-return]


_KILLED_BAKE = """
import os, sys, threading
from pathlib import Path
sys.path[:0] = {paths!r}
from truestill_core.catalog import Catalog
# THE REAL KILL: an uncatchable death at exactly the point between the exiftool write and the
# catalog write. No finally, no atexit, no rollback - what a power loss or a SIGKILL leaves.
Catalog.record_bake = lambda self, *a, **k: os._exit(9)
from truestill_app.service.bake import bake_run
target = bake_run(Path({root!r}), Path({db!r}))
assert callable(target), target
target(lambda _p: None, threading.Event())
"""


def _bake_then_die(db: Path, root: Path) -> None:
    """Run a bake in a child that dies between the write and the record. `(agv)`'s window."""
    script = _KILLED_BAKE.format(paths=sys.path, root=str(root), db=str(db))
    done = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, check=False
    )
    assert done.returncode == 9, (
        f"the child did not die at the window (exit {done.returncode}): {done.stderr[-400:]}"
    )


# --- the property: what verify concludes ---------------------------------------------------


def test_a_killed_bake_is_never_reported_as_corruption(tmp_path: Path) -> None:
    """⚠ **FAILS BEFORE THE FIX** - `verify` reported MISMATCH on an intact photograph."""
    db, root, uuid, _sha = _library(tmp_path)

    _bake_then_die(db, root)

    assert _verify(db, root, uuid)[_RELATIVE] is not CopyStatus.MISMATCH, (
        "verify called an intact photograph corrupt. Its own docstring defines MISMATCH as "
        "'its bytes changed (corruption)', and the CLI then advises re-copying the source - "
        "which discards the date the user asked for and appears to work."
    )


def test_a_killed_bake_reads_as_unverifiable(tmp_path: Path) -> None:
    """The positive half: not-MISMATCH is not enough, it must be the honest state.

    Without this, a fix that reported VERIFIED - silently blessing bytes nothing has checked -
    would satisfy the assertion above while being worse than the defect.
    """
    db, root, uuid, _sha = _library(tmp_path)

    _bake_then_die(db, root)

    assert _verify(db, root, uuid)[_RELATIVE] is CopyStatus.UNVERIFIABLE


def test_the_photograph_itself_is_untouched_by_the_kill(tmp_path: Path) -> None:
    """The premise the whole entry rests on: the file is fine, only the record is behind.

    ⚠ **Asserted through the DATE the user asked for**, not through a hash - a hash comparison
    would only restate that the bytes differ from the catalog, which is the thing under dispute.
    """
    db, root, _uuid, _sha = _library(tmp_path)

    _bake_then_die(db, root)

    stamped = subprocess.run(
        ["exiftool", "-s3", "-DateTimeOriginal", str(root / _RELATIVE)],
        capture_output=True,
        text=True,
        check=False,
    ).stdout.strip()
    assert stamped == CONFIRMED.strftime("%Y:%m:%d %H:%M:%S"), (
        f"the file does not carry the confirmed date ({stamped!r}); the fixture proves nothing"
    )


# --- §4's checklist: the re-run, wherever state is touched ---------------------------------


def test_a_second_bake_finishes_the_job_and_the_copy_verifies_again(tmp_path: Path) -> None:
    """Idempotency/re-run, which `ENGINEERING_STANDARD.md` §4 requires wherever state is touched.

    Measured in P47: a re-bake is **byte-identical**, so the heal is the ordinary path rather than
    a repair - `confirmations_to_bake` still offers the file because `date_baked_at IS NULL`, and
    `record_bake` restores the hash it could not write the first time.
    """
    db, root, uuid, _sha = _library(tmp_path)
    _bake_then_die(db, root)
    assert _verify(db, root, uuid)[_RELATIVE] is CopyStatus.UNVERIFIABLE

    summary = _bake(db, root)

    assert summary["baked"] == 1, "the interrupted file must still be offered to the next bake"
    assert _verify(db, root, uuid)[_RELATIVE] is CopyStatus.VERIFIED, (
        "a completed re-bake must leave the copy verifiable again"
    )


# --- cry-wolf ------------------------------------------------------------------------------


def test_an_uninterrupted_bake_verifies_clean(tmp_path: Path) -> None:
    """The happy path. A guard that reports UNVERIFIABLE for everything would pass without it."""
    db, root, uuid, _sha = _library(tmp_path)

    assert _bake(db, root)["baked"] == 1
    assert _verify(db, root, uuid)[_RELATIVE] is CopyStatus.VERIFIED


def test_verify_reports_nothing_wrong_when_nothing_is(tmp_path: Path) -> None:
    """A library nobody baked verifies clean - `verify` must not invent a MISMATCH."""
    db, root, uuid, _sha = _library(tmp_path)

    assert _verify(db, root, uuid)[_RELATIVE] is CopyStatus.VERIFIED


def test_a_genuine_mismatch_is_still_reported(tmp_path: Path) -> None:
    """⚠ **THE DANGEROUS DIRECTION.** Silencing real corruption is far worse than the defect.

    No bake was ever started here, so nothing explains the changed bytes and `verify` must still
    say so. A fix that widened UNVERIFIABLE to cover any disagreement would pass every assertion
    above and destroy the guarantee the command exists for.
    """
    db, root, uuid, _sha = _library(tmp_path)
    (root / _RELATIVE).write_bytes(b"not the photograph any more")

    assert _verify(db, root, uuid)[_RELATIVE] is CopyStatus.MISMATCH


def test_corruption_after_a_completed_bake_is_still_reported(tmp_path: Path) -> None:
    """The subtler dangerous direction: a finished bake must not leave a permanent excuse.

    If `bake_started_at` were set and never cleared, this copy would read UNVERIFIABLE for the
    rest of its life and real damage after a bake would be invisible.
    """
    db, root, uuid, _sha = _library(tmp_path)
    assert _bake(db, root)["baked"] == 1

    (root / _RELATIVE).write_bytes(b"corrupted after the bake finished")

    assert _verify(db, root, uuid)[_RELATIVE] is CopyStatus.MISMATCH


def test_a_bake_that_fails_cleanly_leaves_the_copy_verifiable(tmp_path: Path) -> None:
    """A refusal is not an interruption: exiftool declining leaves the file untouched.

    ⚠ **This is the defect the fix could introduce** - marking intent before the write and never
    clearing it on a clean failure would make a good, unmodified copy unverifiable for nothing.

    ⚠ **DRIVEN THROUGH THE REAL LOOP, because the first draft was not and a mutation proved it
    hollow.** That draft called `begin_bake` and `abandon_bake` directly, so deleting the loop's
    `abandon_bake` call killed nothing - a valid mutant surviving a test that never entered the
    path. §4's thirteenth member: assert the subject entered the path. The file here is bytes
    exiftool will not accept, so the refusal is genuine rather than injected.
    """
    db, root = tmp_path / "c.sqlite", tmp_path / "drive"
    root.mkdir()
    marker = create_marker(root, label="Memory Drive")
    path = root / _RELATIVE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"not a JPEG, and exiftool will say so")
    sha = sha256_file(path)
    with Catalog(db) as catalog:
        catalog.upsert_drive(uuid=marker.uuid, label=marker.label)
        catalog.record_uploaded(
            source_path="/src/a.jpg",
            original_name="a.jpg",
            sha256=sha,
            copy_sha256=sha,
            perceptual=None,
            size=path.stat().st_size,
            captured_at="2014-08-16T10:46:26",
            category="Camera",
            relative=_RELATIVE,
            drive_uuid=marker.uuid,
        )
        catalog.confirm_date(sha, CONFIRMED.isoformat(), confirmed_by="test")

    summary = _bake(db, root)

    assert summary["failed"] == 1, "fixture check: exiftool must have refused this file"
    assert summary["baked"] == 0
    assert sha256_file(path) == sha, "a refused write must leave the bytes alone"
    assert _verify(db, root, marker.uuid)[_RELATIVE] is CopyStatus.VERIFIED, (
        "a copy exiftool declined to write is unchanged, so it is still verifiable - holding the "
        "mark here would trade a false alarm for a false silence"
    )


@pytest.mark.parametrize("relative", [_RELATIVE])
def test_paths_compare_posix_across_platforms(tmp_path: Path, relative: str) -> None:
    """Cross-platform-safe assertions (§4): the catalog's key is a POSIX relative, never a str."""
    db, root, uuid, _sha = _library(tmp_path)

    assert relative in _verify(db, root, uuid)
    assert Path(relative).as_posix() == relative
