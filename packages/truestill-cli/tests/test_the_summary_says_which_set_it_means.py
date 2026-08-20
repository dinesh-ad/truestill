"""A summary line about the organized set must not read as a claim about the analysed set. `(aej)`.

**The defect, from the first soak.** Re-organizing an already-organized folder - 4,111 files
analysed, 0 organized, all skipped as duplicates - printed verbatim::

    date sources (organized files):
    capture dates      : none of these files carries a capture date
        undated x0

⚠ **Two defects in three lines.** The sentence is FALSE about *"these files"* - the same 4,111
files had reported `exif 3793`, `inferred_local 2` and a range of 2013-08-30 to 2020-12-31 on the
first run - and it CONTRADICTS `undated x0` directly below it: if none carried a date, undated
would be 4,111.

**Both come from one empty list.** `capture_span` returns `None` for *"no file had a date"* **and**
for *"there were no files"*, and the `None` branch prints the sentence; `capture_years` loops zero
times and prints the true `undated x0`. They can only disagree when the population is empty, which
is exactly a re-run.

**And the block changes denominator three times** without saying so: `files analysed` and
`largest files` are the analysed set, `folders derived` and every date line are the organized set,
and only one line carries the label `(organized files)`.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image
from truestill_cli.cli import main


def _photo(folder: Path, seed: int = 10) -> None:
    """One distinct photo, built the way the other CLI tests build them."""
    folder.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (32, 32))
    image.putdata([((seed * 7) % 251, j % 251, (j * 3) % 251) for j in range(1024)])
    image.save(folder / f"IMG_{seed:04d}.jpg", "JPEG", quality=95)


def _run(source: Path, dest: Path, db: Path, capsys: pytest.CaptureFixture[str]) -> str:
    assert main(["organize", str(source), str(dest), "--db", str(db), "--apply"]) == 0
    return capsys.readouterr().out


def test_a_run_that_organized_nothing_says_so_instead_of_dating_an_empty_set(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """⚠ THE REGRESSION, IN THE SOAK'S SHAPE: organize twice into the same destination.

    The second run organizes nothing, so there is no set to make a date claim about. It must say
    that, rather than describing the capture dates of no files.
    """
    source = tmp_path / "source"
    _photo(source)
    dest, db = tmp_path / "dest", tmp_path / "c.sqlite"

    _run(source, dest, db, capsys)
    out = _run(source, dest, db, capsys)

    assert "none of these files carries a capture date" not in out, (
        "a claim about the capture dates of an EMPTY set. The files analysed do carry dates; "
        "the set being described has no members. `(aej)`."
    )
    assert "no files were organized" in out, (
        f"the run organized nothing and did not say so: {out!r}"
    )


def test_the_contradiction_with_undated_zero_is_gone(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The two lines could only ever disagree on an empty population, and they did."""
    source = tmp_path / "source"
    _photo(source)
    dest, db = tmp_path / "dest", tmp_path / "c.sqlite"

    _run(source, dest, db, capsys)
    out = _run(source, dest, db, capsys)

    said_none_dated = "none of these files carries a capture date" in out
    said_zero_undated = "undated x0" in out
    assert not (said_none_dated and said_zero_undated), (
        "the summary says no file carries a capture date AND that zero files are undated. "
        f"Both cannot be true of a non-empty set:\n{out}"
    )


def test_a_run_that_organized_something_still_reports_its_dates(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """⚠ THE CRY-WOLF HALF. The date block is the useful part of the summary on a real run and
    must not be suppressed by a fix aimed at the empty case."""
    source = tmp_path / "source"
    _photo(source)

    out = _run(source, tmp_path / "dest", tmp_path / "c.sqlite", capsys)

    assert "date sources" in out, f"the date block vanished from a real run: {out!r}"
    assert "no files were organized" not in out
    assert "capture dates" in out
