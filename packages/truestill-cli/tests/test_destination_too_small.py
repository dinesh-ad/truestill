"""The CLI's half of the FAT32 refusal: a message and an exit code, never a traceback.

The refusal itself lives in `organizer.execute` so both surfaces inherit it. What is asserted
here is the part the CLI owns: that a `DestinationError` raised before the run turns into a
sentence on stderr and a non-zero exit code, and that the preview *names the problem* rather
than reporting a clean plan the apply will then reject.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from truestill_cli.cli import main
from truestill_core.filesystem import FilesystemFacts

_FAT = FilesystemFacts(filesystem="vfat", max_file_bytes=1_000)


@pytest.fixture
def fat_destination(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make every local destination answer as FAT32 with a small stand-in ceiling.

    Patched on `destinations.local`, the module that *uses* the detection, rather than on
    `filesystem`, which merely defines it - guard rule 3. A 4 GiB fixture would cost minutes
    and 4 GiB of disk to assert a comparison that the constant's own test already pins.
    """
    monkeypatch.setattr(
        "truestill_core.destinations.local.facts_for", lambda _target: _FAT, raising=True
    )


def _library(tmp_path: Path) -> Path:
    """One ordinary photo and one video over the stand-in ceiling."""
    source = tmp_path / "src"
    source.mkdir()
    (source / "IMG_0001.jpg").write_bytes(b"\xff\xd8" + b"x" * 200)
    (source / "VID_4K.mp4").write_bytes(b"\x00" * 4_000)
    return source


@pytest.mark.usefixtures("fat_destination")
def test_apply_refuses_and_names_the_file_rather_than_tracebacking(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    destination = tmp_path / "out"

    code = main(
        [
            "organize",
            str(_library(tmp_path)),
            str(destination),
            "--db",
            str(tmp_path / "c.sqlite"),
            "--apply",
        ]
    )

    captured = capsys.readouterr()
    assert code == 4, captured.err
    assert "VID_4K.mp4" in captured.err, "the file that would fail was not named"
    assert "FAT32" in captured.err, "the reason was not explained, only the failure"


@pytest.mark.usefixtures("fat_destination")
def test_the_refusal_happens_before_any_file_is_written(tmp_path: Path) -> None:
    """The point of a preflight: not nine thousand files organized and then N failures."""
    destination = tmp_path / "out"

    main(
        [
            "organize",
            str(_library(tmp_path)),
            str(destination),
            "--db",
            str(tmp_path / "c.sqlite"),
            "--apply",
        ]
    )

    written = list(destination.rglob("*.jpg")) if destination.exists() else []
    assert written == [], f"the run wrote {written} before refusing"


@pytest.mark.usefixtures("fat_destination")
def test_a_preview_says_so_instead_of_reporting_a_plan_that_cannot_run(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A preview that looks clean and then fails on ``--apply`` is the worse outcome: it moves
    the discovery to the point where the user has already committed."""
    code = main(
        ["organize", str(_library(tmp_path)), str(tmp_path / "out"), "--db", str(tmp_path / "c.db")]
    )

    output = capsys.readouterr().out
    assert code == 0, "a preview writes nothing, so it reports rather than fails"
    assert "VID_4K.mp4" in output
    assert "FAT32" in output


def test_an_ordinary_destination_is_not_warned_about(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The cry-wolf direction. ext4/NTFS/exFAT runs must read exactly as they did before."""
    code = main(
        ["organize", str(_library(tmp_path)), str(tmp_path / "out"), "--db", str(tmp_path / "c.db")]
    )

    assert code == 0
    assert "FAT32" not in capsys.readouterr().out
