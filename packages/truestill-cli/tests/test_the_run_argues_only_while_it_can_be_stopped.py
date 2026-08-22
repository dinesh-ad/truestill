"""A preview argues file by file; a run the user already authorised does not. `(afm)`

**The defect was that one function served two documents.** `_print_report` produced *the plan, in
full, while the user can still stop it* - and produced it identically under `--apply`, when there
is nothing left to stop. Measured on the way in: **7 lines per file**, so a 15,082-file library
printed 105,585 lines of argument to someone who had already decided, ahead of the result they
asked for.

⚠ **What may be dropped is what something else still holds, and that is the only rule here.**
Under `--apply` every file reaches the record with what actually happened to it, the counts are in
`SUMMARY`, and the duplicate origins are in `EXECUTED`. Under a preview **no record is written**
(`(afl)`), so the terminal is the only copy and the listing stays whole however long it is. The
volume was never the defect on its own; `(afd)`'s cap was uncomfortable for exactly this reason,
and there the elided lines *were* the only copy.

**These run the real command end to end** rather than calling the printer, because the decision
under test is the wiring - `listing=not args.apply` - and a test that passes `listing=` itself
cannot see it. `test_the_plan_block_is_unbounded.py` holds the per-block measurements.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from PIL import Image
from truestill_cli.cli import main

_EXIFTOOL = pytest.mark.skipif(shutil.which("exiftool") is None, reason="exiftool not installed")


def _source(tmp_path: Path, count: int) -> Path:
    source = tmp_path / f"src{count}"
    source.mkdir(parents=True, exist_ok=True)
    for i in range(count):
        # ⚠ Distinct DIMENSIONS, not just colour. Neighbouring colours at 32x32 compress to
        # byte-identical JPEGs, and an exact duplicate is short-circuited before the
        # `--skip-undated` branch it is meant to reach - which cost this file a false failure.
        Image.new("RGB", (32 + i, 32), (i * 60 % 255, 40, 90)).save(source / f"p{i}.jpg", "JPEG")
    return source


def _run(tmp_path: Path, count: int, *, apply: bool) -> str:
    """One real `organize`, in its own destination and catalog, returning what it printed."""
    tag = f"{count}{'a' if apply else 'p'}"
    argv = [
        "organize",
        str(_source(tmp_path, count)),
        str(tmp_path / f"dest{tag}"),
        "--db",
        str(tmp_path / f"c{tag}.sqlite"),
    ]
    main([*argv, "--apply"] if apply else argv)
    return tag


def _lines_for(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], count: int, *, apply: bool
) -> int:
    capsys.readouterr()
    _run(tmp_path, count, apply=apply)
    return len(capsys.readouterr().out.splitlines())


@_EXIFTOOL
def test_an_authorised_run_does_not_grow_with_the_library(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """⚠ **The decision, stated as the measurement that would catch its reversal.**

    Slope zero: 30 files must cost an `--apply` run the same number of lines as 5. Restore the
    per-file listing and this fails by 175 lines.
    """
    small = _lines_for(tmp_path, capsys, 5, apply=True)
    large = _lines_for(tmp_path, capsys, 60, apply=True)

    # ⚠ Bounded, not identical. `_print_largest` shows up to `_LARGEST_PREVIEW` files and five
    # files cannot fill it, so a handful of lines legitimately appear between 5 and 60. What must
    # not appear is 385 - the 55 extra files at seven lines each.
    assert large - small < 20, (
        f"an --apply run printed {small} lines for 5 files and {large} for 60: the per-file "
        "argument is back in front of a user who already decided"
    )


@_EXIFTOOL
def test_a_preview_still_argues_for_every_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The other half, and the one that makes the first half a split rather than a deletion.

    A preview is read *instead of* running the command, so it keeps the whole argument.
    """
    small = _lines_for(tmp_path, capsys, 5, apply=False)
    large = _lines_for(tmp_path, capsys, 30, apply=False)

    assert large > small, (
        "a preview stopped naming the files it would organize - it is the only document a user "
        "has before committing, and no record is written for it"
    )
    # ⚠ A floor, not the number. A real entry costs MORE than the seven lines
    # `test_the_plan_block_is_unbounded.py` measures on a minimal resolution - these files cost
    # nine, because an entry with a date source has more to say. The exact figure belongs to the
    # unit test, where the input is fixed; pinning it here would couple this to the fixture.
    assert (large - small) / 25 >= 7.0, (
        "a preview must still cost a whole entry per file - the argument, not a summary"
    )


@_EXIFTOOL
def test_the_authorised_run_still_says_what_it_did(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """⚠ **Shorter is only correct if nothing was lost**, so the survivors are asserted by name.

    Each of these is the reason one part of the plan block could go: the counts, the outcome
    tally, and the pointer to the file that holds the per-file detail.
    """
    capsys.readouterr()
    _run(tmp_path, 6, apply=True)
    out = capsys.readouterr().out

    # `files analysed` rather than `organized (unique)`: these six synthetic images are
    # near-duplicates of each other, which is a fact about the fixture and not about the report.
    assert "files analysed     : 6" in out, "the counts must survive; SUMMARY carries them"
    assert "EXECUTED" in out, "the outcome tally must survive"
    assert "This run is recorded in" in out, (
        "the run must name the record - it is now the only per-file account of an --apply run"
    )
    # ⚠ Against the BLOCK, never the whole report: `_print_largest` names files too, from a
    # capped sample, so `"p3.jpg" not in out` would pass or fail for reasons that are not the
    # subject. The heading is the thing that exists only when the argument is printed.
    assert "NEW UNIQUE" not in out, (
        "the per-file argument is back on a run that was already authorised"
    )


@_EXIFTOOL
def test_a_preview_names_every_undated_file_and_an_authorised_run_counts_them(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`--skip-undated`'s block follows the same rule, and for the same reason.

    ⚠ These files never get copied, so it would be easy to assume nothing records them. They do
    reach the record - `ActionStatus.SKIPPED_UNDATED` with its detail - which is precisely what
    permits the names to be dropped once the run is authorised. A preview writes no record, so
    there they stay.
    """
    source = _source(tmp_path, 4)  # generated JPEGs carry no capture date
    base = [
        "organize",
        str(source),
        str(tmp_path / "destu"),
        "--db",
        str(tmp_path / "cu.sqlite"),
        "--skip-undated",
    ]

    capsys.readouterr()
    main(base)
    preview = capsys.readouterr().out
    assert "SKIPPED (undated" in preview, "a preview must show the --skip-undated block at all"
    assert "p3.jpg" in preview.split("SKIPPED (undated")[1], (
        "a preview must name each file --skip-undated will leave behind"
    )

    main([*base, "--apply"])
    applied = capsys.readouterr().out
    assert "SKIPPED (undated" not in applied, (
        "an authorised run must not re-list them; the record and EXECUTED carry them"
    )
    # The literal a person reads, per §4's twenty-ninth member - importing `status_label` would
    # make this a tautology. This is the line that PERMITS the names above to be dropped.
    assert "4  skipped, no date" in applied, (
        "an authorised run must still say how many were skipped, or the names went nowhere"
    )
