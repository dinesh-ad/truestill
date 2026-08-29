"""A file the drive has accepted gets a catalog row, whatever happens to its timestamp. `(ain)`

**The measured defect, reproduced before it was fixed (P143).** `organizer._upload_copy` uploads
and **then** calls `Destination.set_timestamp`, a bare `os.utime`. On a mount that refuses it -
SMB/CIFS, NFS with `root_squash`, FUSE and cloud mounts, or simply not owning the destination
file - the upload had already **committed the file by rename**, the exception propagated, and the
catalog row, which is written *after* the bytes, was never reached. Verbatim, three files:

    FAILED: p0.jpg: cannot set timestamp on 'Saved/2024/...': [Errno 1] Operation not permitted
    >>> files on the drive:  3        >>> file_copies rows: 0        >>> exit code: 1

So the drive held photographs the catalog had never heard of.

🔑 **AND THE NEXT RUN MADE IT WORSE - measured, not inferred, which is what makes this rank.**
With no row for the sha, `_free_relative` finds the target name occupied by a file it cannot
recognise as its own and suffixes around it. Run two wrote `…_1.jpg`; run three, with the refusal
lifted, wrote `…_2.jpg` and **exited 0 with a clean summary**. Nine files on the drive from three
photographs, six of them orphans no catalog will ever mention. `(afe)`'s shape, confirmed live.

**The ruling: keep the file and record it, never roll it back.** Deleting a committed, complete
copy to tidy up after a cosmetic failure is the one thing this product refuses everywhere else -
`_move_source` *"never deletes on doubt"*, `safe_copy` is built so nothing at the target is ours
to remove, and `(aie)` ruled exactly this for the copy that had **not** committed yet. The case
where it **has** cannot be the one that deletes.

**`(aie)`'s mirror image, and the two are separate**: there the bytes never took the name, so the
drive and catalog agreed (both empty); here they disagree, which is why `--no-timestamps` escapes
this one and not that one. The test at the bottom pins that asymmetry.
"""

from __future__ import annotations

import errno
import os
import random
import sqlite3
from contextlib import closing
from pathlib import Path

import pytest
from PIL import Image
from truestill_cli.cli import main

#: A date in the name is enough to make `captured_at` non-`None`, which is what puts
#: `set_timestamp` on the path at all. ⚠ **An undated file never reaches this defect** - worth
#: knowing before anyone concludes from a green run that the whole path is covered.
_NAMES = ["20240110_120000_p0.jpg", "20240111_120000_p1.jpg", "20240112_120000_p2.jpg"]


def _jpeg(path: Path, *, seed: int) -> None:
    rng = random.Random(seed)
    image = Image.new("RGB", (64, 64))
    image.putdata(
        [(rng.randrange(256), rng.randrange(256), rng.randrange(256)) for _ in range(4096)]
    )
    image.save(path, "JPEG", quality=95)


@pytest.fixture
def library(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Three dated photos, an initialised drive, and a catalog."""
    src, drive, db = tmp_path / "src", tmp_path / "Drive", tmp_path / "c.sqlite"
    src.mkdir()
    for i, name in enumerate(_NAMES):
        _jpeg(src / name, seed=i)
    assert main(["drives", "--init", str(drive), "--label", "Photos HDD", "--db", str(db)]) == 0
    return src, drive, db


def _refuse_the_stamp(monkeypatch: pytest.MonkeyPatch, drive: Path, *, code: int) -> None:
    """Refuse `os.utime` on the COMMITTED file only - `set_timestamp`'s call.

    ⚠ **Scoped away from the staged name on purpose.** `copystat` stamps the staged sibling and
    this stamps the final path; refusing both would prove `(aie)` and `(ain)` at once and stay
    green while either regressed.
    """
    real = os.utime

    def patched(path: object, *args: object, **kwargs: object) -> None:
        target = Path(str(path))
        if target.is_relative_to(drive) and not target.name.endswith(".partial"):
            raise OSError(code, os.strerror(code))
        real(str(path), *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(os, "utime", patched)


def _rows(db: Path) -> list[str]:
    # `closing`, not `sqlite3.connect(...)` as a context manager - that one commits a transaction
    # and leaves the connection open, which is a `ResourceWarning` per call under this suite.
    with closing(sqlite3.connect(db)) as con:
        return [
            str(r[0]) for r in con.execute("SELECT relative FROM file_copies ORDER BY relative")
        ]


def _on_disk(drive: Path) -> list[str]:
    return sorted(str(p.relative_to(drive)) for p in drive.rglob("*.jpg"))


def test_a_refused_stamp_still_records_the_copy(
    library: tuple[Path, Path, Path],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """THE DETECTOR. The row is the assertion - the file on disk was never the problem.

    Before the fix this run put three photographs on the drive and **zero** rows in the catalog.
    A file with no row is not merely unreported: `verify` cannot check it, `undo` cannot reverse
    it, `reclaim` cannot see it, and the next organize writes a second copy beside it.
    """
    src, drive, db = library
    _refuse_the_stamp(monkeypatch, drive, code=errno.EPERM)

    code = main(["organize", str(src), str(drive), "--apply", "--db", str(db)])

    assert _on_disk(drive) != [], "nothing was placed, so this test proves nothing"
    assert _rows(db) == _on_disk(drive), (
        "the drive holds photographs the catalog has never heard of"
    )
    assert code == 0, "a placed and recorded file was reported as a failed run"
    printed = capsys.readouterr()
    assert "failed" not in printed.out, "a complete, recorded copy was counted as a failure"
    assert "METADATA NOT SET" in printed.err, "the degradation is silent"
    assert "is safe" in printed.err, "the note does not say the file survived"


def test_a_second_run_does_not_write_the_photograph_again(
    library: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """THE SELF-WORSENING HALF, and the one that measures the harm rather than naming it.

    Every run against an orphan adds another copy: `_free_relative` suffixes around a file it
    cannot recognise. Three runs made nine files from three photographs, and the last exited 0.
    A run that placed nothing new must leave the drive exactly as it found it.
    """
    src, drive, db = library
    _refuse_the_stamp(monkeypatch, drive, code=errno.EPERM)
    assert main(["organize", str(src), str(drive), "--apply", "--db", str(db)]) == 0
    after_one = _on_disk(drive)

    assert main(["organize", str(src), str(drive), "--apply", "--db", str(db)]) == 0

    assert _on_disk(drive) == after_one, (
        "the second run wrote a suffixed second copy of every photograph"
    )
    assert not [p for p in after_one if "_1." in p], "a suffixed duplicate was written"
    assert len(after_one) == len(_NAMES), "one file per source photograph, and no more"


def test_a_copy_that_is_not_there_is_still_a_failure(
    library: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """CRY-WOLF HALF ONE, and the reason the destination is asked rather than the errno read.

    A `file_copies` row for a copy that does not exist is a false custody claim - this entry's own
    defect inverted, and the worse direction: `verify` would report a photograph as held. So the
    keep is conditional on the copy actually being there, and here it is not.
    """
    src, drive, db = library
    real = os.utime

    def vanishes(path: object, *args: object, **kwargs: object) -> None:
        target = Path(str(path))
        if target.is_relative_to(drive) and not target.name.endswith(".partial"):
            # What a mount going away between the rename and the stamp actually looks like.
            target.unlink(missing_ok=True)
            raise OSError(errno.ENOENT, "No such file or directory")
        real(str(path), *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(os, "utime", vanishes)

    code = main(["organize", str(src), str(drive), "--apply", "--db", str(db)])

    assert code == 1, "a copy that is not on the drive was reported as a successful run"
    assert _rows(db) == [], "the catalog claims copies that are not there"


def test_an_ordinary_run_records_and_says_nothing_about_metadata(
    library: tuple[Path, Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    """CRY-WOLF HALF TWO. Nothing is stubbed: `os.utime` really runs and really succeeds."""
    src, drive, db = library

    code = main(["organize", str(src), str(drive), "--apply", "--db", str(db)])

    assert code == 0
    assert _rows(db) == _on_disk(drive) != []
    assert "METADATA NOT SET" not in capsys.readouterr().err, (
        "a working drive was reported as refusing"
    )


def test_no_timestamps_escapes_this_one(
    library: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """⚠ THE ASYMMETRY THAT PROVES `(aie)` AND `(ain)` ARE DIFFERENT DEFECTS, pinned.

    `--no-timestamps` gates `set_timestamp` and therefore escapes this entirely. It could never
    help `(aie)`, because `safe_copy` does not take `set_timestamps` at all - the `copystat`
    inside the copy has already raised before the flag is consulted. Re-checked after the copy
    path changed under it (`e8eda35`): a flag that escaped yesterday is not assumed to escape
    today.
    """
    src, drive, db = library
    _refuse_the_stamp(monkeypatch, drive, code=errno.EPERM)

    code = main(["organize", str(src), str(drive), "--apply", "--no-timestamps", "--db", str(db)])

    assert code == 0
    assert _rows(db) == _on_disk(drive) != [], "the flag did not escape the refusal"
