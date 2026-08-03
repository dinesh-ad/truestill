"""`truestill analyze` -- the tier-0 census, and the promises it makes about what it is not.

Tier 0 reads directory entries and one ``stat`` per media file. No exiftool, no hashing, no
catalog, no destination, no registered drive. That last group is the whole point: the audience
is someone pointing at a folder they have never organized, and any requirement beyond "this
folder exists" would put the free tier behind the paid journey.

The tests that matter most here are the *negative* ones. The counts are arithmetic and would
survive a careless refactor; the promises would not.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from truestill_cli.cli import main
from truestill_core import binaries

#: Byte sizes are distinct primes so a total can only be right for one reason.
MIX: dict[str, int] = {
    "a/IMG_0001.jpg": 101,
    "a/IMG_0002.jpg": 103,
    "a/IMG_0003.heic": 107,
    "b/clip.mp4": 109,
    "b/old.mov": 113,
    "b/voice.m4a": 127,
    "notes.pdf": 131,
    "mystery.xyz": 137,
}
MEDIA_BYTES = 101 + 103 + 107 + 109 + 113 + 127
_NO_SUBPROCESS = "analyze must not run a subprocess"


@pytest.fixture
def library(tmp_path: Path) -> Path:
    root = tmp_path / "Photos"
    for relative, size in MIX.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x" * size)
    return root


def _run(argv: list[str], capsys: pytest.CaptureFixture[str]) -> tuple[int, str, str]:
    code = main(argv)
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def _counts(out: str, *labels: str) -> dict[str, int]:
    """Read ``label : N`` lines back out of the report, so the assertions read the real output."""
    found: dict[str, int] = {}
    for label in labels:
        line = next(line for line in out.splitlines() if line.strip().startswith(label))
        digits = line.split(":", 1)[1].strip().split(" ", 1)[0]
        found[label] = int(digits.replace(",", ""))
    return found


# --- the census -----------------------------------------------------------------------------


def test_a_known_mix_is_counted_exactly(library: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Asserted on the numbers, not on the presence of headings."""
    code, out, _ = _run(["analyze", str(library)], capsys)

    assert code == 0
    assert "files found" in out
    assert "6" in out  # 3 photos + 2 videos + 1 audio
    for label, count in (("photos", 3), ("videos", 2), ("audio", 1)):
        line = next(line for line in out.splitlines() if line.strip().startswith(label))
        assert line.rstrip().endswith(str(count)), f"{label}: {line!r}"


def test_the_media_total_is_the_sum_of_the_media_files(
    library: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Documents and unrecognized files are counted separately and must not inflate the size."""
    _code, out, _ = _run(["analyze", str(library)], capsys)
    assert f"{MEDIA_BYTES:,} bytes" in out


def test_the_kind_counts_add_up_to_the_file_count(
    library: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The conservation rule `_print_summary` established, applied to this report.

    A reader must be able to add the column up. If a later change lets a media file belong to
    no kind, this fails rather than quietly printing three numbers that do not reconcile.
    """
    _code, out, _ = _run(["analyze", str(library)], capsys)
    numbers = _counts(out, "files found", "photos", "videos", "audio")
    assert numbers["photos"] + numbers["videos"] + numbers["audio"] == numbers["files found"]


def test_each_extension_is_named_with_its_count(
    library: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _code, out, _ = _run(["analyze", str(library)], capsys)
    for token in ("jpg x2", "heic x1", "mp4 x1", "mov x1", "m4a x1"):
        assert token in out, token


def test_skipped_files_are_accounted_for_not_dropped(
    library: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Never-silent: a `.pdf` and an unknown extension are named, not quietly omitted."""
    _code, out, _ = _run(["analyze", str(library)], capsys)
    assert ".pdf" in out
    assert ".xyz" in out


# --- what it must not require -----------------------------------------------------------------


def test_no_destination_no_catalog_and_no_registered_drive_are_needed(
    library: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The funnel, pinned. A refactor that adds a destination parameter fails here.

    Asserted by *absence*: no catalog or cache file is created anywhere under the isolated
    roots, and the command is given nothing but a folder. If Analyze ever needs a library to
    exist, the first-time user it exists for cannot run it.

    The `--db` flag is checked too. Every catalog-touching subcommand declares one; `analyze`
    must not, because accepting it would be the first step toward needing it.
    """
    before = {p for p in tmp_path.rglob("*") if p.suffix in {".sqlite", ".db"}}

    code, _out, err = _run(["analyze", str(library)], capsys)

    assert code == 0, err
    assert {p for p in tmp_path.rglob("*") if p.suffix in {".sqlite", ".db"}} == before

    with pytest.raises(SystemExit):
        main(["analyze", str(library), "--db", str(tmp_path / "c.sqlite")])
    assert "--db" in capsys.readouterr().err


def test_no_file_is_opened_and_exiftool_is_never_invoked(
    library: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Tier 0's cost claim, enforced rather than documented.

    `binaries.run` is the one door to exiftool. Made to explode, so a change that quietly adds
    a metadata pass to this report fails here instead of turning a sub-second command into a
    multi-minute one on someone's library.
    """

    def explode(*_args: object, **_kwargs: object) -> object:
        raise AssertionError(_NO_SUBPROCESS)

    monkeypatch.setattr(binaries, "run", explode)
    code, _out, err = _run(["analyze", str(library)], capsys)
    assert code == 0, err


# --- honesty about what it did not do ---------------------------------------------------------


def test_the_report_says_what_it_has_not_analysed(
    library: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`(aac)`'s discipline: a tier that has not run is named, never rendered as zero."""
    _code, out, _ = _run(["analyze", str(library)], capsys)
    lowered = out.lower()
    assert "not yet analysed" in lowered
    for absent in ("duplicate", "look-alike", "date"):
        assert absent in lowered, f"{absent} must be named as not-yet-analysed"


@pytest.mark.parametrize("forbidden", ["duplicates         : 0", "duplicates: 0", "0 duplicates"])
def test_no_zero_is_printed_for_a_tier_that_did_not_run(
    library: Path, capsys: pytest.CaptureFixture[str], forbidden: str
) -> None:
    """The cry-wolf half of the rule above, and the defect it prevents.

    Saying "duplicates: 0" would be a lie of exactly the shape `(aac)` was filed for: nothing
    looked, so zero is not the answer -- it is the absence of one.
    """
    _code, out, _ = _run(["analyze", str(library)], capsys)
    assert forbidden not in out


def test_the_read_only_promise_is_stated(library: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Worded to be true: working files may be created, photos and the library are untouched."""
    _code, out, _ = _run(["analyze", str(library)], capsys)
    assert "never changes your photos" in out
    assert "never adds anything to your library" in out


# --- edges ------------------------------------------------------------------------------------


def test_an_empty_folder_reports_zero_rather_than_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A silent success is indistinguishable from a broken command."""
    empty = tmp_path / "empty"
    empty.mkdir()

    code, out, _ = _run(["analyze", str(empty)], capsys)

    assert code == 0
    assert "files found" in out
    assert "0" in out


def test_a_folder_that_does_not_exist_is_a_usage_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Exit `2`, the usage family: nothing was attempted and no waiting would fix it."""
    missing = tmp_path / "nope"

    code, _out, err = _run(["analyze", str(missing)], capsys)

    assert code == 2
    assert str(missing) in err


def test_a_file_is_not_a_folder(library: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Cry-wolf for the check above: it must reject a file, not merely a missing path."""
    code, _out, err = _run(["analyze", str(library / "notes.pdf")], capsys)
    assert code == 2
    assert "notes.pdf" in err


@pytest.mark.skipif(os.name == "nt", reason="POSIX permission bits; Windows ACLs differ")
@pytest.mark.skipif(os.getuid() == 0, reason="root can list any directory")
def test_a_folder_that_cannot_be_listed_is_named_not_counted_as_empty(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The worst answer this report could give is "nothing here" when it could not look.

    The count inside is *precisely* what is unknown, so the folder is named and no number is
    invented for it -- the rule `_print_skipped` already applies on the organize surface.
    """
    root = tmp_path / "Photos"
    (root / "readable").mkdir(parents=True)
    (root / "readable" / "IMG_0001.jpg").write_bytes(b"x" * 11)
    locked = root / "locked"
    locked.mkdir()
    (locked / "hidden.jpg").write_bytes(b"x" * 13)
    locked.chmod(0o000)
    try:
        code, out, _ = _run(["analyze", str(root)], capsys)
    finally:
        locked.chmod(0o755)

    assert code == 0
    assert "locked" in out
    assert "contents unknown" in out


def test_the_command_exists_and_is_discoverable(capsys: pytest.CaptureFixture[str]) -> None:
    """`analyze` must appear in `--help`, or the funnel's entry point is unfindable."""
    with pytest.raises(SystemExit) as raised:
        main(["--help"])
    assert raised.value.code == 0
    out = capsys.readouterr().out
    assert "analyze" in out


def test_analyze_is_not_a_flag_on_organize(capsys: pytest.CaptureFixture[str]) -> None:
    """Ruling 1, pinned: a separate command, so it can never inherit organize's destination.

    Given organize's required arguments, so the error is the unknown flag rather than the
    missing positionals -- otherwise this passes without testing anything.
    """
    with pytest.raises(SystemExit):
        main(["organize", "src", "dst", "--analyze"])
    assert "--analyze" in capsys.readouterr().err


def test_sys_argv_is_not_consulted(library: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """The argv passed in wins, so a test's own command line cannot leak into the run."""
    original = list(sys.argv)
    try:
        sys.argv = ["truestill", "organize", "/nonexistent"]
        code, _out, _err = _run(["analyze", str(library)], capsys)
    finally:
        sys.argv = original
    assert code == 0
