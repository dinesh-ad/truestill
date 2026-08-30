"""A name that will not fit is named and refused, not handed to the OS to garble. `(aid)`

**The measured defect (P140, re-measured P146).** `safe_copy` stages every copy at
``<name>.<token>.partial`` with the suffix appended **LAST**, so the file a run creates is longer
than the file it becomes. A name legal at the source, legal after `naming.dated_filename` adds its
sixteen-character stamp, and legal at the destination still failed - at the OS, with raw words:

    FAILED: holidayxxx....jpg: could not copy holidayxxx....jpg to
    'Saved/Undated/holidayxxx....jpg': File name too long 0 bytes of it are still at
    .../holidayxxx....jpg.5580514b3be.partial, and could not be removed.

Three defects in one line: two sentences run together with no punctuation, a `.partial` reported
as *"could not be removed"* when it could not be **created**, and no remedy anywhere.

🔑 **AND THE BUDGET IS NOT A CONSTANT, WHICH IS WHY NOTHING HERE HARDCODES ONE.** The staging
token carries the pid in hex, so its width follows whatever pid the OS handed the process. `(aid)`
records **219** from a P140 run with an 11-character token; P146 measured **220** with a
10-character one. On this machine's `pid_max` the true threshold moves over **218-223**. Every
test below asks `layout.name_shortfall_bytes` where the edge is rather than asserting a number,
which is the only form that can be right on both runs.
"""

from __future__ import annotations

import random
import subprocess
import sys
from pathlib import Path

import pytest
from PIL import Image
from truestill_cli.cli import main
from truestill_core.layout import MAX_COMPONENT_BYTES, name_shortfall_bytes
from truestill_core.safe_copy import copy_leaving_nothing, staging_overhead_bytes

_STAMP = len("20190712_103000_")
_EXIFTOOL = pytest.mark.skipif(
    __import__("shutil").which("exiftool") is None, reason="exiftool not installed"
)


def _photo(path: Path, *, seed: int = 1) -> None:
    rng = random.Random(seed)
    image = Image.new("RGB", (32, 32))
    image.putdata([(rng.randrange(256),) * 3 for _ in range(1024)])
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, "JPEG")


def _dated(path: Path) -> None:
    """A real EXIF date, so `dated_filename` adds the full sixteen-character stamp."""
    subprocess.run(
        ["exiftool", "-overwrite_original", "-DateTimeOriginal=2019:07:12 10:30:00", str(path)],
        capture_output=True,
        check=True,
    )


def _budget() -> int:
    """The longest original name that still fits, asked rather than assumed."""
    return MAX_COMPONENT_BYTES - _STAMP - staging_overhead_bytes()


def _name(length: int) -> str:
    return "x" * (length - len(".jpg")) + ".jpg"


def _library(tmp_path: Path, *names: str) -> tuple[Path, Path, Path]:
    src, drive, db = tmp_path / "src", tmp_path / "Drive", tmp_path / "c.sqlite"
    src.mkdir()
    # ⚠ **A DISTINCT SEED PER FILE, AND THE FIRST DRAFT DID NOT HAVE ONE.** With identical bytes
    # the second photograph is an exact duplicate, and `_organize_each` skips a duplicate *before*
    # it composes anything - correctly, since a file that is never written has no name to check.
    # So the boundary test passed its landing assertion while never reaching the code under test.
    for seed, name in enumerate(names):
        _photo(src / name, seed=seed)
        _dated(src / name)
    assert main(["drives", "--init", str(drive), "--label", "Photos HDD", "--db", str(db)]) == 0
    return src, drive, db


def _organize(src: Path, drive: Path, db: Path, *extra: str) -> int:
    return main(["organize", str(src), str(drive), "--db", str(db), *extra])


@_EXIFTOOL
def test_the_boundary_is_the_staged_name_not_the_final_one(tmp_path: Path) -> None:
    """THE DETECTOR, on both sides of an edge no final name ever approaches.

    At the budget the copy lands; one byte over it is refused. ⚠ **The refused name's *final*
    form is still comfortably under 255** - that is the entire defect, and asserting it here is
    what stops someone "simplifying" this to a check on the organized name.
    """
    budget = _budget()
    fits, over = _name(budget), _name(budget + 1)
    src, drive, db = _library(tmp_path, fits, over)

    code = _organize(src, drive, db, "--apply")

    landed = sorted(p.name for p in drive.rglob("*.jpg"))
    assert landed == [f"20190712_103000_{fits}"], f"the wrong file landed: {landed}"
    assert len(f"20190712_103000_{over}".encode()) < MAX_COMPONENT_BYTES, (
        "the refused name's final form must be UNDER the component limit, or this test is "
        "asserting an ordinary too-long name and not this defect"
    )
    assert code == 1


@_EXIFTOOL
def test_a_refused_name_leaves_nothing_behind_and_claims_nothing_it_cannot_see(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The wording, and the false debris claim inside it. `(aid)`'s second and third defects.

    `_size_of` answered `0` for both *"the partial is empty"* and *"there is no answer"*, so a
    name too long to create - and therefore too long to `stat` and too long to `unlink` - was
    reported as `0 bytes ... could not be removed`. It had never been created.
    """
    src, drive, db = _library(tmp_path, _name(_budget() + 8))

    _organize(src, drive, db, "--apply")

    printed = capsys.readouterr()
    assert not list(drive.rglob("*.partial")), "a staged file was left on the drive"
    assert "could not be removed" not in printed.err, "debris was claimed for a file never created"
    assert "File name too long" not in printed.err, "the raw OS words reached the user"
    assert "Shorten the file's name by at least 8 bytes" in printed.err, (
        "the remedy does not name the shortfall"
    )
    assert "the original is untouched" in printed.err


@_EXIFTOOL
def test_a_preview_predicts_the_refusal_and_exits_one(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """⚠ **The exit code is part of the rule, not decoration.**

    `IMPLEMENTATION_STANDARDS.md` states it for the unreadable case and it is the same argument
    here: predicting `0` for a run that will exit `1` makes `organize && next_step` chain past a
    library Truestill could not fully account for. The check is made at composition time, so the
    preview's answer *is* the run's answer rather than a second opinion.
    """
    src, drive, db = _library(tmp_path, _name(_budget() + 3))

    code = _organize(src, drive, db)

    assert code == 1, "a preview predicted success for a run that will fail"
    assert "NAMES TOO LONG FOR THE DESTINATION (1)" in capsys.readouterr().out
    assert not list(drive.rglob("*.jpg")), "a preview wrote something"


@_EXIFTOOL
def test_an_ordinary_library_is_never_told_about_lengths(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """CRY-WOLF. Silent when nothing is over, and silent at the boundary rather than near it."""
    src, drive, db = _library(tmp_path, _name(_budget()), "holiday.jpg")

    code = _organize(src, drive, db, "--apply")

    printed = capsys.readouterr()
    assert code == 0
    assert "TOO LONG" not in printed.out
    assert "Shorten" not in printed.err
    assert len(list(drive.rglob("*.jpg"))) == 2


def test_the_budget_follows_the_staging_token_rather_than_a_written_down_number() -> None:
    """⚠ **`(aid)` records 219 as "the real budget" and there is no such constant.**

    The overhead is `.` + `f"{os.getpid():x}"` + six hex characters + `.partial`, so it is
    16 bytes for a one-digit pid and 21 for a six-digit one - and `pid_max` is 4,194,304 on an
    ordinary Linux box. A hardcoded 219 is wrong in the *unsafe* direction on any run whose pid
    happens to be wider than the one that was measured.
    """
    overhead = staging_overhead_bytes()
    assert 16 <= overhead <= 21, (
        f"the staging suffix is not the shape this budget assumes: {overhead}"
    )
    edge = "y" * (MAX_COMPONENT_BYTES - overhead)
    assert name_shortfall_bytes(edge) == 0, "the widest name that fits was refused"
    assert name_shortfall_bytes(edge + "y") == 1, "one byte over must be one byte short"


def test_a_multibyte_name_is_measured_in_bytes_not_characters() -> None:
    """The case a character count gets wrong, and the one the field reports most.

    rsync #891 names it exactly: CJK and Cyrillic names that are legal as UTF-16 on NTFS and
    over 255 **bytes** as UTF-8. One character here costs three.
    """
    name = "日" * 90  # 270 bytes, 90 characters
    assert len(name) < MAX_COMPONENT_BYTES < len(name.encode("utf-8"))
    assert name_shortfall_bytes(name) > 0, "a 270-byte name was measured as 90 characters"


@pytest.mark.xfail(
    sys.platform == "win32",
    strict=False,
    reason="`:` is legal on ext4/APFS and refused by NTFS - the fact this instrument exists to get",
)
def test_a_name_legal_at_the_source_is_carried_to_the_destination_verbatim(tmp_path: Path) -> None:
    """⚠ **THE CHARACTER HALF, AND THE SEAM CANNOT BE FORCED LOCALLY - so this is an xfail.**

    P145 closed a sibling seam on *every* lane by forcing the decode (`encoding="cp1252"` in
    place of `text=True`). **That move is not available here.** A colon is refused by the NTFS
    *driver*; no environment variable, locale or flag makes ext4 refuse one, and no flag makes
    NTFS accept one. There is nothing to force - the fact lives in a filesystem, not in a
    decoding decision - so a test that runs everywhere would be testing something else.

    So this is `(aif)`'s instrument rather than P145's: it does the real thing and lets the
    Windows lane answer. On Linux it passes and documents that the original name is carried
    through **unsanitised**, which is deliberate. On Windows the source file cannot even be
    created, and the `XFAIL` is `(aid)`'s character premise returning a real answer from the one
    place that can give one. ⚠ `strict=False`, so an XPASS is information rather than a red
    build - if Windows ever accepts it, that is a fact worth reading, not a failure.
    """
    src, drive, db = tmp_path / "src", tmp_path / "Drive", tmp_path / "c.sqlite"
    src.mkdir()
    _photo(src / "Trip: day 1.jpg")
    assert main(["drives", "--init", str(drive), "--label", "Photos HDD", "--db", str(db)]) == 0

    assert _organize(src, drive, db, "--apply") == 0

    landed = [p.name for p in drive.rglob("*.jpg")]
    assert landed == ["Trip: day 1.jpg"], f"the source's own name was not carried through: {landed}"


# --- the copy door itself, which organize no longer reaches but backup and extract still do ----


def test_a_copy_that_could_never_be_created_reports_no_debris(tmp_path: Path) -> None:
    """⚠ **`safe_copy` IS NOT REACHED BY THE ORGANIZE PATH ANY MORE, AND IS STILL LIVE.**

    Found by mutation: reverting `_discard`'s fix killed nothing, because organize now refuses a
    long name at composition time and never calls `copyfile`. That is the fix working - and it
    would have left the door itself unguarded, since `service/backup.py` and `archive_extract`
    copy through here **without** going near `organizer`'s composition check.

    The original mechanism, exactly: a name too long to create is also too long to `stat` and too
    long to `unlink`, so every step fails with the same errno. `_size_of` answered `0` for *"there
    is no answer"*, and the caller then told the user `0 bytes ... could not be removed` about a
    file that had never existed.
    """
    source = tmp_path / "src.jpg"
    _photo(source)
    target = tmp_path / ("z" * (MAX_COMPONENT_BYTES - 4) + ".jpg")

    outcome = copy_leaving_nothing(source, target)

    assert not outcome.ok, "the fixture is not over the limit once staged, so it proves nothing"
    assert outcome.leftover is None, "debris was reported for a file that was never created"
    assert outcome.leftover_bytes == 0
    assert not list(tmp_path.glob("*.partial"))
