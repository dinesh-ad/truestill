"""A re-run must repair a copy the medium never took, not report it as already there. `(aja)`

**Measured on real removable media (soak eleven), not imagined.** A stick pulled mid-`organize`
left **836 zero-byte files** on exFAT against 2,062 confident `file_copies` rows. The user
re-ran - the obvious remedy - and got ``2,068 already on this drive``, **exit 0**, and 838 of 839
files unchanged.

🔑 **The row written too early was the same row that suppressed the repair.** Dedup asked
`copies_on_drive` and nothing asked the drive, so the files most in need of re-copying were
exactly the ones skipped. Every automatic path reported success; only `verify` dissented.

**The fix is `dedup.credible_copies`**: a recorded copy is believed only while the destination
still holds a file of the recorded size - the stat `Destination.sizes()` already does.
"""

from __future__ import annotations

import random
import sqlite3
from contextlib import closing
from pathlib import Path

import pytest
from PIL import Image
from truestill_cli.cli import main
from truestill_core.dedup import credible_copies


def _jpeg(path: Path, *, seed: int) -> None:
    rng = random.Random(seed)
    image = Image.new("RGB", (64, 64))
    image.putdata([(rng.randrange(256), 90, 200) for _ in range(4096)])
    image.save(path, "JPEG", quality=95)


@pytest.fixture
def library(tmp_path: Path) -> tuple[Path, Path, Path]:
    src, drive, db = tmp_path / "src", tmp_path / "Drive", tmp_path / "c.sqlite"
    src.mkdir()
    for i in range(4):
        _jpeg(src / f"2024011{i}_120000_p{i}.jpg", seed=i)
    assert main(["drives", "--init", str(drive), "--label", "D", "--db", str(db)]) == 0
    assert main(["organize", str(src), str(drive), "--apply", "--db", str(db)]) == 0
    return src, drive, db


def _copies(db: Path) -> dict[str, int]:
    with closing(sqlite3.connect(db)) as con:
        return {str(r[0]): int(r[1]) for r in con.execute("SELECT relative, size FROM file_copies")}


def _ruin(drive: Path, relative: str) -> None:
    """What an interrupted write leaves on exFAT and FAT32: the entry, none of the bytes."""
    (drive / relative).write_bytes(b"")


def test_a_zero_byte_copy_is_re_copied_rather_than_skipped(
    library: tuple[Path, Path, Path],
) -> None:
    """THE DETECTOR. Against today's code this file stays 0 bytes and the run says it is fine."""
    src, drive, db = library
    rows = _copies(db)
    victim, want = next(iter(rows.items()))
    _ruin(drive, victim)
    assert (drive / victim).stat().st_size == 0

    assert main(["organize", str(src), str(drive), "--apply", "--db", str(db)]) == 0

    assert (drive / victim).stat().st_size == want, (
        "the re-run skipped a copy the drive does not hold - the row defended itself"
    )
    # ⚠ **At the RECORDED path, not beside it.** A repair that lands as `…_1.jpg` leaves the
    # corpse on the drive and the row pointing at it - `(ain)`'s shape from the dedup side.
    assert not list(drive.rglob("*_1.jpg")), "the repair landed beside the ruined file"


def test_a_copy_that_is_gone_is_re_copied(library: tuple[Path, Path, Path]) -> None:
    """The other shape an interruption leaves: NTFS rolled the entry out of existence."""
    src, drive, db = library
    rows = _copies(db)
    victim, want = next(iter(rows.items()))
    (drive / victim).unlink()

    assert main(["organize", str(src), str(drive), "--apply", "--db", str(db)]) == 0

    assert (drive / victim).exists(), "a recorded copy that is absent was still skipped"
    assert (drive / victim).stat().st_size == want


def test_an_intact_library_is_still_deduplicated(
    library: tuple[Path, Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    """⚠ THE CRY-WOLF HALF. Nothing is damaged, so nothing may be re-copied.

    A fix that re-copies an undamaged library would be worse than the defect: it would turn every
    ordinary re-run into a full rewrite of the drive.
    """
    src, drive, db = library
    before = {p: p.stat().st_mtime_ns for p in sorted(drive.rglob("*.jpg"))}

    assert main(["organize", str(src), str(drive), "--apply", "--db", str(db)]) == 0

    after = {p: p.stat().st_mtime_ns for p in sorted(drive.rglob("*.jpg"))}
    assert after == before, "an intact copy was rewritten"
    assert "already on this drive" in capsys.readouterr().out


def test_a_destination_that_cannot_report_sizes_keeps_every_row() -> None:
    """⚠ THE SECOND CRY-WOLF, and it was UNPROVEN until a mutation survived.

    ``sizes is None`` means *"this destination cannot answer cheaply"* - an rclone remote - and
    must read as **no evidence**, never as *"nothing is credible"*. Discarding every row there
    would re-copy an entire remote on every run, which is `(aei)` inverted.

    Pinned as a unit rather than through the CLI because no rclone remote exists in a test, and
    a claim about the third branch has to be asserted on the third branch.
    """
    recorded = {"a": "x.jpg", "b": "y.jpg"}
    expected: dict[str, int | None] = {"a": 100, "b": 100}

    assert credible_copies(recorded, sizes=None, expected=expected) == recorded

    # And the contrast, so the two branches are pinned against each other in one place.
    assert credible_copies(recorded, sizes={"x.jpg": 100, "y.jpg": 0}, expected=expected) == {
        "a": "x.jpg"
    }


def test_a_row_with_no_recorded_size_is_still_believed() -> None:
    """A pre-`(aei)` row can carry ``size = NULL``; absence of evidence is not evidence.

    Discarding those would re-copy every old library on its next run.
    """
    assert credible_copies({"a": "x.jpg"}, sizes={"x.jpg": 0}, expected={"a": None}) == {
        "a": "x.jpg"
    }
