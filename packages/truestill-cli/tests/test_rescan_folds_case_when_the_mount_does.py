"""`truestill rescan` asks the mount, and the answer reaches the expensive decision. `(ala)`

**What this covers that the core tests cannot.** `rescan.reconcile` is pure and its tests feed it
strings directly. The CLI's own half is the **PLACED subtraction** - `candidates = {rel: path ...
if key(rel) not in recorded_keys}` - which decides what gets hashed, and that is where the cost
is: `HashCache` is keyed by `str(path)`, so a case-drifted path misses the cache too and is read
in full. A fold that reached `reconcile` and not this line would fix the report and leave the
whole library being re-read.

⚠ **THE FLAG IS FORCED RATHER THAN THE FILESYSTEM FAKED.** Every CI lane runs on ext4 or tmpfs,
where `Photo.JPG` and `photo.jpg` are two genuinely different files - so no temporary directory
can produce the input this guards. `folds_case` is the one seam that carries the filesystem's
answer, and overriding it is exactly the injection `(ais)`'s resolution calls for: the seam is
forceable in process, so the test needs no `skipif` and runs on every lane. What it does not
prove is that a real folding mount returns the drifted spelling from its walk - that is
`test_the_case_probe_asks_the_mount`, which runs against whatever this machine has.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from truestill_cli import cli
from truestill_cli.cli import main


@pytest.fixture
def drive(tmp_path: Path) -> tuple[Path, Path]:
    """A registered drive holding one organized photograph, and its catalog."""
    source, library, db = tmp_path / "src", tmp_path / "Lib", tmp_path / "catalog.sqlite"
    source.mkdir()
    (source / "holiday.jpg").write_bytes(b"\xff\xd8\xff\xe0" + b"x" * 4096)
    assert main(["organize", str(source), str(library), "--db", str(db), "--apply"]) == 0
    return library, db


def _only_photo(library: Path) -> Path:
    found = list(library.rglob("*.jpg"))
    assert len(found) == 1, found
    return found[0]


def test_a_drifted_name_is_placed_rather_than_moved_when_the_mount_folds(
    drive: tuple[Path, Path], capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The headline: nothing moved, so nothing is reported as having moved, and the run succeeds."""
    library, db = drive
    photo = _only_photo(library)
    photo.rename(photo.with_suffix(".JPG"))
    monkeypatch.setattr(cli, "folds_case", lambda _walked: True)

    code = main(["rescan", str(library), "--db", str(db)])

    out = capsys.readouterr().out
    assert code == 0, "a drive where nothing changed exited non-zero"
    assert "MOVED" not in out
    assert "in place           : 1" in out


def test_the_same_drift_is_a_move_when_the_mount_does_not_fold(
    drive: tuple[Path, Path], capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """⚠ **The half that makes the fold safe.** On ext4 the two names are two files, and a rename
    is a real event that must stay visible."""
    library, db = drive
    photo = _only_photo(library)
    photo.rename(photo.with_suffix(".JPG"))
    monkeypatch.setattr(cli, "folds_case", lambda _walked: False)

    code = main(["rescan", str(library), "--db", str(db)])

    assert code == 1
    assert "MOVED: 1" in capsys.readouterr().out


def test_the_drifted_file_is_not_hashed_when_the_mount_folds(
    drive: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """⚠ **THE COST, WHICH IS THE LARGER HALF OF THIS DEFECT.**

    `rescan`'s own docstring justifies the PLACED rule by the price of breaking it - *"~15 h for
    196 GiB at the 3.9 MB/s measured on a cloud mount"*. On a folding filesystem a library whose
    case drifted matched nothing, so **every** file became a candidate and was read in full.
    Counted at the one function that reads bytes, so a fix that corrected the report and left the
    reads in place fails here.
    """
    library, db = drive
    photo = _only_photo(library)
    photo.rename(photo.with_suffix(".JPG"))
    read: list[Path] = []
    real = cli.sha256_file

    def spy(path: Path) -> str:
        read.append(path)
        return real(path)

    monkeypatch.setattr(cli, "sha256_file", spy)

    monkeypatch.setattr(cli, "folds_case", lambda _walked: True)
    assert main(["rescan", str(library), "--db", str(db)]) == 0
    assert read == [], f"a placed file was read: {read}"

    monkeypatch.setattr(cli, "folds_case", lambda _walked: False)
    assert main(["rescan", str(library), "--db", str(db)]) == 1
    assert len(read) == 1, "the non-folding run must still identify the candidate by content"


def test_an_unchanged_drive_is_unaffected_either_way(
    drive: tuple[Path, Path], capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The cry-wolf half: a library nobody touched reads the same with the fold on or off."""
    library, db = drive
    for answer in (True, False):
        monkeypatch.setattr(cli, "folds_case", lambda _walked, a=answer: a)
        assert main(["rescan", str(library), "--db", str(db)]) == 0
        assert "in place           : 1" in capsys.readouterr().out
