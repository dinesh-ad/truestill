"""`truestill organize --move` says which files it did not take, and where they still are.

A move skips a file already in the library and leaves its original alone - correct, and until
now silent on both surfaces. The count reached the EXECUTED tally as `N duplicate`, which
answers "how many" and not "so where are my photos".

§9's duplicate rule is "on **every** surface that shows the count", so this is wired here and in
the app together rather than one at a time.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from PIL import Image
from truestill_cli.cli import main

_EXIFTOOL = pytest.mark.skipif(shutil.which("exiftool") is None, reason="exiftool not installed")


def _tree(root: Path) -> Path:
    """`A/` holding `B` and `D/E`, every photo distinct (noise, so no two look alike)."""
    for rel, seed, count in (("B", 10, 2), ("D/E", 40, 3)):
        folder = root / "A" / rel
        folder.mkdir(parents=True, exist_ok=True)
        for i in range(count):
            image = Image.new("RGB", (32, 32))
            image.putdata([((seed + i) * 7 % 251, j % 251, (j * 3) % 251) for j in range(1024)])
            image.save(folder / f"IMG_{seed + i:04d}.jpg", "JPEG", quality=95)
    return root / "A"


@_EXIFTOOL
def test_a_move_names_the_folder_its_leftovers_are_in(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    src, dest, db = tmp_path / "src", tmp_path / "dest", tmp_path / "c.sqlite"
    root = _tree(src)
    # Copy `E` in first, so the move that follows meets three files it already holds.
    assert main(["organize", str(root / "D" / "E"), str(dest), "--apply", "--db", str(db)]) == 0
    capsys.readouterr()

    assert main(["organize", str(root), str(dest), "--apply", "--move", "--db", str(db)]) == 0
    out = capsys.readouterr().out

    assert "3 files remain in D/E" in out, out
    assert "already in your library" in out, out
    assert sorted(p.name for p in (root / "D" / "E").iterdir()) == [
        "IMG_0040.jpg",
        "IMG_0041.jpg",
        "IMG_0042.jpg",
    ], "the sentence would be false"


@_EXIFTOOL
def test_a_move_preview_says_what_it_will_not_take(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The preview answers a different question - what will happen - so it is a different
    sentence, and it is the one that lets a user change their mind."""
    src, dest, db = tmp_path / "src", tmp_path / "dest", tmp_path / "c.sqlite"
    root = _tree(src)
    assert main(["organize", str(root / "D" / "E"), str(dest), "--apply", "--db", str(db)]) == 0
    capsys.readouterr()

    assert main(["organize", str(root), str(dest), "--move", "--db", str(db)]) == 0
    out = capsys.readouterr().out

    assert "will not be moved" in out, out
    assert "3 files here are already in your library" in out, out


@_EXIFTOOL
def test_a_copy_run_says_nothing_about_leftovers(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """CRY-WOLF HALF. A copy leaves every original where it is - that is the mode's whole
    definition - so there is nothing the user did not already ask for."""
    src, dest, db = tmp_path / "src", tmp_path / "dest", tmp_path / "c.sqlite"
    root = _tree(src)
    assert main(["organize", str(root / "D" / "E"), str(dest), "--apply", "--db", str(db)]) == 0
    capsys.readouterr()

    assert main(["organize", str(root), str(dest), "--apply", "--db", str(db)]) == 0
    out = capsys.readouterr().out

    assert "remain in" not in out, out
    assert "will not be moved" not in out, out
