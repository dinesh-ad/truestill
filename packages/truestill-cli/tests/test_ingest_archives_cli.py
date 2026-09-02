"""Pointing `ingest` at one archive part ingests the whole download ((jj)).

**Why one part is enough, and why requiring all of them would be worse.** Google splits an
export across numbered files *by size, not by folder*, so a ``Photos from 2014`` folder can
straddle two of them. If the command line required every part, forgetting one would not fail -
it would **succeed** and quietly leave the photos in the missing part without their real dates.
An easy mistake with a silent, permanent cost is the worst shape a CLI can have, so the siblings
are gathered from the directory instead.

The archive route refuses on its preconditions **before writing anything**, which is the same
preview-then-confirm discipline every other path that touches a user's disk follows.
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest
from truestill_cli.cli import _source_root_or_none, main

_JPEG = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00" + b"\x00" * 64 + b"\xff\xd9"
_SIDECAR = json.dumps({"photoTakenTime": {"timestamp": "1403000000"}}).encode()


def _part(directory: Path, number: int, entries: dict[str, bytes]) -> Path:
    path = directory / f"takeout-20260801T000000Z-{number:03d}.zip"
    with zipfile.ZipFile(path, "w") as archive:
        for name, data in entries.items():
            archive.writestr(name, data)
    return path


def test_a_directory_is_passed_straight_through(tmp_path: Path) -> None:
    """The pre-existing route must keep working exactly as it did."""
    extracted = tmp_path / "Takeout"
    extracted.mkdir()

    assert _source_root_or_none(extracted, tmp_path / "dest", tmp_path / "c.sqlite") == extracted


def test_pointing_at_one_part_gathers_its_siblings(tmp_path: Path) -> None:
    """The photo is in part 1 and its sidecar in part 2; naming only part 1 must still find both."""
    folder = "Takeout/Google Photos/Photos from 2014"
    first = _part(tmp_path, 1, {f"{folder}/IMG_0001.jpg": b"\xff\xd8jpeg"})
    _part(tmp_path, 2, {f"{folder}/IMG_0001.jpg.json": _SIDECAR})

    root = _source_root_or_none(first, tmp_path / "dest", tmp_path / "c.sqlite")

    assert root is not None
    assert (root / folder / "IMG_0001.jpg").exists()
    assert (root / folder / "IMG_0001.jpg.json").exists(), "the sibling part was not unpacked"


def test_a_refusal_writes_nothing_and_reports_why(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A missing part must stop the run rather than produce a library with a hole in it."""
    for number in (1, 3):
        _part(tmp_path, number, {f"Takeout/a/IMG_{number}.jpg": b"\xff\xd8x"})
    destination = tmp_path / "dest"

    result = _source_root_or_none(
        tmp_path / "takeout-20260801T000000Z-001.zip", destination, tmp_path / "c.sqlite"
    )

    assert result is None
    assert not destination.exists(), "a refused ingest still touched the destination"
    printed = capsys.readouterr().out
    assert "missing part 2" in printed, f"the refusal did not say what was wrong: {printed}"


def test_a_path_that_is_neither_file_nor_directory_is_named(tmp_path: Path) -> None:
    assert (
        _source_root_or_none(tmp_path / "nope.zip", tmp_path / "dest", tmp_path / "c.sqlite")
        is None
    )


# --- and the same thing through the command line, which is where it broke. `(ahp)` -------


def test_an_archive_ingest_survives_the_command_line(tmp_path: Path) -> None:
    """⚠ **THE TEST ABOVE COULD NOT HAVE CAUGHT `(ahp)`, AND THAT IS THIS FILE'S LESSON.**

    `test_a_directory_is_passed_straight_through` calls `_source_root_or_none(extracted,
    tmp_path / "dest")` - a **`Path`**. The real caller passes `args.destination`, which argparse
    produces as a **`str`** because `cli.py:373` declares it without `type=Path` (correctly: it is
    a local path *or* an rclone spec). So `facts_for` called `.exists()` on a `str` and **every
    archive ingest died with an `AttributeError`** - a traceback, not a refusal, on the invocation
    `--help` documents.

    ⚠ **mypy could not see it either**: `argparse.Namespace` attributes are `Any`, so strict mode
    type-checked the call and learnt nothing. The argparse boundary is where `Any` enters this
    program, and a test that constructs its own input never crosses it.

    **So this drives `main()`.** A helper-level test cannot see this class and never will -
    proved by mutation: reverting the fix leaves the helper test green and turns this one red.
    """
    archive = _part(tmp_path, 1, {"Takeout/Google Photos/Photos from 2014/IMG_0001.jpg": _JPEG})

    code = main(
        [
            "ingest",
            str(tmp_path / "dest"),
            "--source",
            str(archive),
            "--db",
            str(tmp_path / "c.sqlite"),
        ]
    )

    assert code == 0, "an archive ingest did not survive argparse"


def test_an_archive_to_an_rclone_remote_is_refused_not_staged(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """⚠ **The half a bare `type=Path` would have got WRONG.** `(ahp)`

    `destination` is a local path *or* an rclone spec, so converting it in the parser would wrap
    `remote:bucket` in a `Path` and `extract_archive_set` would unpack 1.6 GB into a local folder
    **named after the remote**. A crash turned into silent wrong behaviour is not a fix, so the
    archive route refuses instead - the `rclone -> None` convention `_shas_on_destination` already
    uses for the same reason: a remote has no filesystem to stage into or size-check against.
    """
    archive = _part(tmp_path, 1, {"Takeout/Google Photos/Photos from 2014/IMG_0001.jpg": _JPEG})

    code = main(
        [
            "ingest",
            "remote:bucket",
            "--rclone",
            "--source",
            str(archive),
            "--db",
            str(tmp_path / "c.sqlite"),
        ]
    )

    assert code == 2, "an archive to a remote was not refused"
    assert "rclone remote" in capsys.readouterr().err
    assert not (tmp_path / "remote:bucket").exists(), "it staged into a folder named for the remote"
