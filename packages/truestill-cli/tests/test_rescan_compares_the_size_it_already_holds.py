"""`rescan` must not call a zero-byte file "in place". `(ajb)`

**Measured on removable media in soak eleven.** A stick pulled mid-write left **836 files at zero
bytes on exFAT** against a catalog recording 3.5 MB each. `rescan` reported `in place: 2538` in
0.28 s - correct about location, silent about the lie - and its own disclaimer sent the user away:
*"Silent damage to a file changes neither its name nor its size."* **True of bit-rot, false for
what an interrupted write actually produces.**

🔑 **The filesystem's own checker structurally cannot find this.** `fsck` on the same volume said
*corrupted, 1 file* - it caught the one genuinely incoherent entry and was blind to the 836
coherent ones, because a zero-byte file with zero clusters **agrees with itself**. Only the
catalog, which lives outside the filesystem, knows they should be 3.5 MB. **So this is not a
convenience; it is the only instrument that can hold both numbers at once.**

⚠ **Scope, measured across three filesystems**: the gap exists where the filesystem KEEPS the
directory entry - exFAT (2 of 838 caught) and FAT32 (1 of 39) - and not where a journal rolls the
entry out of existence, as NTFS did (304 of 304 already caught). Removable media is overwhelmingly
the first kind.
"""

from __future__ import annotations

import random
from pathlib import Path

import pytest
from PIL import Image
from truestill_cli.cli import main


def _jpeg(path: Path, *, seed: int) -> None:
    rng = random.Random(seed)
    image = Image.new("RGB", (48, 48))
    image.putdata([(rng.randrange(256), 40, 90) for _ in range(2304)])
    image.save(path, "JPEG", quality=95)


@pytest.fixture
def drive(tmp_path: Path) -> tuple[Path, Path]:
    src, dest, db = tmp_path / "src", tmp_path / "Drive", tmp_path / "c.sqlite"
    src.mkdir()
    for i in range(3):
        _jpeg(src / f"2024011{i}_120000_p{i}.jpg", seed=i)
    assert main(["drives", "--init", str(dest), "--label", "D", "--db", str(db)]) == 0
    assert main(["organize", str(src), str(dest), "--apply", "--db", str(db)]) == 0
    return dest, db


def _ruin(drive_root: Path) -> Path:
    victim = next(p for p in sorted(drive_root.rglob("*.jpg")))
    victim.write_bytes(b"")
    return victim


def test_a_zero_byte_copy_is_named_and_not_called_in_place(
    drive: tuple[Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    """THE DETECTOR. Against today's code this is reported as `in place` and nothing else."""
    root, db = drive
    victim = _ruin(root)

    code = main(["rescan", str(root), "--db", str(db)])

    out = capsys.readouterr().out
    assert "THE WRONG SIZE ON THE DRIVE: 1" in out, "a zero-byte copy was reported as in place"
    assert victim.relative_to(root).as_posix() in out, "the damaged file was not named"
    assert "0 bytes, recorded as" in out, "the user was not told what the size should have been"
    assert code == 1, "a drive with a damaged copy reconciled successfully"


def test_the_disclaimer_no_longer_says_size_would_not_help(
    drive: tuple[Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    """⚠ The sentence that sent the user away, and why it had to change with the behaviour.

    It read *"Silent damage to a file changes neither its name nor its size"* - which is what a
    user reads when deciding whether the fast check was enough.
    """
    root, db = drive
    main(["rescan", str(root), "--db", str(db)])

    out = capsys.readouterr().out
    assert "changes neither its name nor its size" not in out
    assert "whether they are the SIZE the catalog" in out
    assert "'truestill verify' can find it" in out, "verify is still named for the harder case"


def test_an_intact_drive_reports_nothing_and_still_exits_zero(
    drive: tuple[Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    """⚠ CRY-WOLF. Nothing is damaged, so the new section must not appear at all."""
    root, db = drive

    code = main(["rescan", str(root), "--db", str(db)])

    out = capsys.readouterr().out
    assert code == 0
    assert "THE WRONG SIZE ON THE DRIVE" not in out
    assert "Everything the catalog records for this drive is where it says it is." in out
