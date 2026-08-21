"""(aer) `organize` names what it did not look at, the way `analyze` already does.

**The defect, from soak two rather than reasoned about.** A folder holding 21 photos, 18 of them
in `.MyAlbum`:

    organize --apply  ->  "files analysed: 3 · organized (unique): 3"   and SUCCESS
    analyze           ->  "hidden folders (not looked inside): 1
                             .../.MyAlbum  (contents unknown)
                           (rename one without the leading dot, then run again ...)"

Same folder, same moment, opposite answers - and the wrong one is on the **happy path, with a
success message**. `(aek)` was at least loud. This is §1's *"nothing is discarded without appearing
in a report"* and §9's never-silent rule, both broken quietly.

⚠ **FOLDERS ARE NAMED WITHOUT A COUNT, AND THAT IS NOT AN OVERSIGHT TO TIDY.** `c027dd3` records
it: the walk never descends into a hidden or unreadable folder, so *the number of files inside is
precisely what is unknown* and any figure would be invented. `_print_unreadable` says the same for
its own case. The third test below pins it, so nobody "improves" `1 hidden folder` into `18 files`.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from PIL import Image
from truestill_cli.cli import main

_EXIFTOOL = pytest.mark.skipif(shutil.which("exiftool") is None, reason="exiftool not installed")


def _photo(path: Path, colour: tuple[int, int, int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (32, 32), colour).save(path, "JPEG")


def _the_soak_shape(tmp_path: Path) -> Path:
    """The 21-photo case reduced: one visible photo, one hidden file, one hidden album."""
    source = tmp_path / "src"
    _photo(source / "visible.jpg", (10, 20, 30))
    (source / ".picasa.ini").write_text("[Picasa]\n", encoding="utf-8")
    for index in range(3):
        _photo(source / ".MyAlbum" / f"held-{index}.jpg", (index + 40, 50, 60))
    return source


@_EXIFTOOL
def test_organize_names_the_hidden_file_it_skipped(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`.picasa.ini` is real user metadata, and it vanished from the organize report entirely."""
    source = _the_soak_shape(tmp_path)

    assert (
        main(["organize", str(source), str(tmp_path / "dest"), "--db", str(tmp_path / "c.sqlite")])
        == 0
    )

    report = capsys.readouterr().out
    assert ".picasa.ini" in report, f"the hidden file was not named:\n{report}"


@_EXIFTOOL
def test_organize_names_the_hidden_folder_it_did_not_enter(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """⚠ The worse half: a folder can hold an entire album, and the run said success."""
    source = _the_soak_shape(tmp_path)

    main(["organize", str(source), str(tmp_path / "dest"), "--db", str(tmp_path / "c.sqlite")])

    report = capsys.readouterr().out
    assert ".MyAlbum" in report, f"a hidden folder holding photos was not named:\n{report}"
    assert "contents unknown" in report, "the folder was named without saying what is unknown"
    assert "rename" in report, "named the problem without the remedy, which is half a report"


@_EXIFTOOL
def test_a_skipped_folder_is_never_given_a_file_count(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """⚠ The cry-wolf half, and the rule `c027dd3` wrote down.

    The album holds **3** photos. The walk never entered it, so that number is exactly what is
    unknown and the report must not state it. A fix that "improved" the folder line into a file
    count would pass the test above and be a fabrication.
    """
    source = _the_soak_shape(tmp_path)

    main(["organize", str(source), str(tmp_path / "dest"), "--db", str(tmp_path / "c.sqlite")])

    line = next((row for row in capsys.readouterr().out.splitlines() if ".MyAlbum" in row), "")
    assert line, "the folder was not named at all"
    # ⚠ THE PATH IS NOT THE SUBJECT, and it cost a red run to say so: `tmp_path` is
    # `/tmp/pytest-of-<user>/pytest-<N>/...`, so the assertion below read pytest's own run
    # counter and failed on run 193 against correct output. §4's thirty-ninth member - a test
    # whose subject is an OS-produced value tests the OS. What this pins is the RENDERED part
    # of the line, so the source path is removed before it is scanned.
    rendered = line.replace(str(source), "")
    assert "3" not in rendered, f"the folder line invented a count of what is inside it: {line!r}"
    assert not any(c.isdigit() for c in rendered), (
        f"the folder line carries a number at all, and any number here is about files it never "
        f"saw: {line!r}"
    )


@_EXIFTOOL
def test_an_ordinary_source_says_nothing_about_skipping(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The other cry-wolf half. A never-silent rule is about what happened, not what did not.

    An ordinary folder must not sprout a row explaining that it has no hidden files - the census's
    own docstring says a group with nothing in it is **absent**, not zero.
    """
    source = tmp_path / "plain"
    _photo(source / "a.jpg", (1, 2, 3))

    main(["organize", str(source), str(tmp_path / "dest"), "--db", str(tmp_path / "c.sqlite")])

    report = capsys.readouterr().out
    assert "hidden" not in report.lower(), (
        f"an ordinary folder was told about hidden files:\n{report}"
    )
    assert "Skipped" not in report, "an ordinary folder printed a skipped section"
