"""Analyze reports each tier as it completes, on a terminal and through a pipe alike.

**Measured, on the maintainer's 192 GB library.** `truestill analyze` took **54 minutes at 3%
CPU** - about 105 s of computation stretched over 54 minutes of waiting on a cloud mount, ~31x
I/O to CPU. Tier 0 finished in 21 s and **the remaining 53 minutes produced nothing at all.**

**The sequencing was already right, and that is the point of this file.** `test_analyze_deep.py`
has pinned since Analyze 3a that the census prints before the expensive work begins. The report
was invisible anyway, for two independent reasons that had nothing to do with ordering:

1. **Nothing reported progress during the slow tiers.** `_analyze_deep` called `read_metadata`
   and `resolve` without a `progress=` callback at all, so even on a terminal those 53 minutes
   were silent.
2. **stdout is block-buffered when it is not a terminal.** Demonstrated before writing this:
   a script printing tier 0, sleeping, then printing tier 2 leaves the redirect file **empty**
   for the whole sleep. Ordering the writes correctly achieves nothing if they all land at exit.

So the fix is progress, a stream split, and a flush - not a re-ordering.

**Why stderr for progress.** `truestill analyze <path> > report.txt` should leave a clean report
in the file while the terminal still shows the run. That is the split git and docker use, and
`(r)` records it as the ruling the rest depends on. **Nothing that reads this output moves**:
every result line stays on stdout, which is where all 42 existing analyze assertions read it.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from PIL import Image
from truestill_cli import cli
from truestill_cli.cli import _NOT_YET_ANALYSED, main
from truestill_core import organizer, scan


@pytest.fixture
def library(tmp_path: Path) -> Path:
    """A folder with a few real images, enough for the expensive tiers to have work."""
    folder = tmp_path / "pics"
    folder.mkdir()
    for i in range(6):
        Image.new("RGB", (32 + i, 32), (i * 7 % 256, 40, 90)).save(folder / f"p{i}.jpg", "JPEG")
    return folder


def _run(library: Path, capsys: pytest.CaptureFixture[str]) -> tuple[int, str, str]:
    code = main(["analyze", str(library)])
    captured = capsys.readouterr()
    return code, captured.out, captured.err


# --- ruling 1: results to stdout, progress to stderr --------------------------------------------


def test_the_report_is_on_stdout_and_the_progress_is_not(
    library: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`analyze <path> > report.txt` must leave a report, not a report full of counters."""
    code, out, _err = _run(library, capsys)

    assert code == 0
    assert "files found" in out, "the census belongs in the report"
    assert "NOT YET ANALYSED" in out
    # The counter is progress, not a result. Its phase names come from `progress.Phase`.
    assert not re.search(r"\b(scanning|hashing)\b:", out), (
        "a progress counter reached the report file:\n" + out
    )


@pytest.mark.parametrize(
    ("phase", "tier"),
    [("scanning", "tier 1, reading dates"), ("hashing", "tier 2a, identical copies")],
)
def test_each_expensive_tier_reports_progress(
    phase: str,
    tier: str,
    library: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """**The 53 silent minutes.** `_analyze_deep` passed no `progress=` to either expensive
    call, so both were silent even on a terminal.

    **One assertion per tier, and that is the point.** A single "some progress appeared" check
    was written first and a mutation proved it worthless: deleting tier 1's callback left tier
    2a's counter behind and the test still passed, so the slower of the two tiers could go
    silent again unnoticed. Terminal mode, because that is where every update prints - a piped
    run legitimately throttles a short tier down to nothing.
    """
    monkeypatch.setattr(cli, "_stderr_is_terminal", lambda: True)
    _code, _out, err = _run(library, capsys)

    assert re.search(rf"\b{phase}\b", err), f"{tier} reported no progress:\n{err}"


# --- ruling 2: TTY detection ---------------------------------------------------------------------


def test_a_piped_run_writes_no_carriage_returns(
    library: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """**The 127 KB of unreadable scrollback**, asserted on the bytes.

    `\\r` overwrites a line on a terminal and is simply *stored* in a file, so a redirected run
    left one padded 60-column counter per file - 127 KB of it on the real library. pytest's
    capture is not a tty, which is exactly the condition under test.
    """
    _code, out, err = _run(library, capsys)

    assert "\r" not in err, "a carriage return reached a non-terminal stream"
    assert "\r" not in out
    assert err == "" or err.endswith("\n"), "piped progress must be newline-delimited"


def test_a_piped_run_does_not_print_a_line_per_file(
    library: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Cadence, not just line endings. Without `\\r` to overwrite with, one line per file is the
    same flood in a different shape - the cure has to be fewer lines, not tidier ones."""
    _code, _out, err = _run(library, capsys)

    counters = [line for line in err.splitlines() if re.search(r"\d+/\d+", line)]
    assert len(counters) <= 4, (
        f"{len(counters)} counter lines for 6 files - a piped run must throttle:\n" + err
    )


def test_a_terminal_run_animates_in_place(
    library: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The other half of the same branch: on a real terminal the in-place counter is right, and
    removing the animation everywhere would be a regression rather than a fix."""
    monkeypatch.setattr(cli, "_stderr_is_terminal", lambda: True)
    _code, _out, err = _run(library, capsys)

    assert "\r" in err, "a terminal run lost its in-place counter"


# --- ruling 3: flush after each tier -------------------------------------------------------------


def test_each_tier_is_flushed_before_the_next_one_starts(
    library: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """**Ordering the writes is not enough if they all land at exit.**

    Captured at the moment the first expensive call happens, like
    `test_the_census_prints_before_the_expensive_work_starts` - but asserting the *flush*, which
    is what makes the already-correct ordering visible through a pipe. Proven necessary before
    this was written: a redirect file stays empty for the whole of the slow tier without it.
    """
    flushed_before_hashing: list[int] = []
    flushes = {"n": 0}
    real_end_of_tier = cli._end_of_tier

    def counting_end_of_tier() -> None:
        flushes["n"] += 1
        real_end_of_tier()

    real_hashes = scan.compute_hashes

    def spy(*args: object, **kwargs: object) -> object:
        flushed_before_hashing.append(flushes["n"])
        return real_hashes(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(cli, "_end_of_tier", counting_end_of_tier)
    monkeypatch.setattr(scan, "compute_hashes", spy)
    monkeypatch.setattr(organizer, "compute_hashes", spy)
    _run(library, capsys)

    assert flushed_before_hashing, "hashing never ran"
    # **Two, not one, and a mutation is why.** `>= 1` was written first and it was worthless:
    # the forecast's own flush satisfied it, so tier 0's census could stop being flushed and
    # nothing would notice. Both points are deliberate - the census, then the forecast that is
    # the last thing printed before a wait measured at 53 minutes - so both are counted.
    assert flushed_before_hashing[0] >= 2, (
        f"only {flushed_before_hashing[0]} flush(es) before the slow tier: the census and the "
        "forecast must each reach the pipe before the wait, not at exit"
    )


# --- the correctness core: absent-or-tagged, never defaulted -------------------------------------


@pytest.mark.parametrize("field", [name for name, _description in _NOT_YET_ANALYSED])
def test_a_tier_that_did_not_run_reads_as_not_analysed_and_never_as_zero(
    field: str, library: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """**A `duplicates: 0` where tier 2a never ran is the `ReportBuckets` defect again.**

    Zero means "none found". Not-run means nothing looked. Parametrized over the real field
    list so a field added to `_NOT_YET_ANALYSED` is covered the day it is added, rather than
    the day someone remembers to write its test.
    """

    def interrupted(*_args: object, **_kwargs: object) -> object:
        raise KeyboardInterrupt

    monkeypatch.setattr(organizer, "compute_hashes", interrupted)
    _code, out, _err = _run(library, capsys)

    assert not re.search(rf"{re.escape(field)}\s*:?\s+0\b", out), (
        f"{field!r} rendered as a zero in a report where its tier did not run:\n" + out
    )


def test_the_unrun_tier_of_a_completed_run_is_named_without_a_number(
    library: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The same rule on the path that actually reaches `_print_not_yet_analysed`.

    **A mutation is why this exists separately.** The parametrized test above interrupts, and
    `_cmd_analyze` returns from the interrupt branch *before* that block is ever reached - so
    tagging could have been deleted from it wholesale and the test above would still have
    passed. This drives a run that completes tiers 1 and 2a and leaves only look-alikes unrun,
    which is the one path that renders the block.
    """
    _code, out, _err = _run(library, capsys)

    assert "NOT YET ANALYSED" in out
    assert "look-alikes" in out, "the tier that did not run must still be named"
    assert not re.search(r"look-alikes\s*:?\s+[\d,]+", out), (
        "the unrun tier was given a number, which reads as a measurement:\n" + out
    )


def test_an_interrupted_tier_says_so_and_keeps_what_printed(
    library: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The interrupt ruling, carried through unchanged: a partial duplicate count is a **wrong**
    answer rather than an incomplete one, because an unscanned file may be the twin of a
    scanned one."""

    def interrupted(*_args: object, **_kwargs: object) -> object:
        raise KeyboardInterrupt

    monkeypatch.setattr(organizer, "compute_hashes", interrupted)
    code, out, _err = _run(library, capsys)

    assert code == 0, "an interrupt is a supported outcome"
    assert "files found" in out, "what printed before the interrupt is kept"
    assert "Stopped" in out
    assert "Traceback" not in out


# --- the conservation law only holds once tier 2 completed ---------------------------------------

#: The organize surface's summing block, which `test_summary_tally_is_disjoint` guards there.
#: Analyze must not grow one for a run whose tiers did not all complete.
_SUMMING_LABELS = ("new unique", "near-dup", "exact dup", "unreadable")


def test_a_partial_report_prints_no_block_that_claims_to_sum(
    library: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """`new_unique + near_dup + exact_dup + unreadable == files` holds **only once tier 2
    completed**. Until then a block in that shape is a set of numbers a reader can add up and
    get a wrong answer from - the failure `test_summary_tally_is_disjoint` exists to prevent on
    the organize surface, which is where this shape would be copied from."""

    def interrupted(*_args: object, **_kwargs: object) -> object:
        raise KeyboardInterrupt

    monkeypatch.setattr(organizer, "compute_hashes", interrupted)
    _code, out, _err = _run(library, capsys)

    lowered = out.lower()
    present = [label for label in _SUMMING_LABELS if label in lowered]
    assert not present, f"a partial analyze printed a summing block: {present}\n{out}"
