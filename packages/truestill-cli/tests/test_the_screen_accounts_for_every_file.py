"""The screen accounts for every file the plan analysed, on every path that ends a run. `(aim)`

**The class, not an instance.** `_print_summary` prints `organized (unique): N` from the **plan**
(`partition_for_report`) before `execute` runs; `_print_execution` prints the outcome from
`ActionStatus`. Two documents, and until 2026-08-30 nothing compared them and one of them was
missing on the routes where it mattered most.

⚠ **`(aac)`'s conservation law is the right shape on the WRONG AXIS and cannot be extended in
place.** `new_unique + near_dup + exact_dup + unreadable == files` is asserted over
`partition_for_report`'s buckets by `test_summary_tally_is_disjoint.py`, which drives
`_print_summary` alone - there is no outcome in it anywhere. `(aie)` had perfectly consistent
buckets and then failed during execution. So the object here is **the rendered output of one real
`main(["organize", ..., "--apply"])`**, with a stop injected: the only place the two documents
meet is the screen.

**Reading the numbers back out of the text is deliberate**, and the technique is
`test_summary_tally_is_disjoint`'s own - *"the rendered block is what a person adds up and the two
can drift"*. `(acx)` ruled the CLI had *"no pair to compare"* because its preview is a set of
print functions rather than a function with a signature; the rendered text **is** the pair, which
is what gives this surface the assertion
`truestill-app`'s `test_the_preview_promise_equals_the_run.py` has always had.

⚠ **WHAT THIS DOES NOT GUARD, said plainly: the TENSE.** `test_the_header_names_the_document`
below asserts a literal string. That pins a string, not honesty - anyone rewording the block can
satisfy it and reintroduce the defect. Change 1 of `(aim)` is held by review, and a green run here
is not evidence otherwise.
"""

from __future__ import annotations

import errno
import random
import re
from pathlib import Path

import pytest
from PIL import Image
from truestill_cli.cli import main
from truestill_core import safe_copy
from truestill_core.destinations.local import LocalDestination

#: Dated in the name, so no exiftool is needed to give these files a `captured_at`.
_DATED = ["20240110_120000_p0.jpg", "20240111_120000_p1.jpg", "20240112_120000_p2.jpg"]


def _jpeg(path: Path, *, seed: int) -> None:
    rng = random.Random(seed)
    image = Image.new("RGB", (64, 64))
    image.putdata(
        [(rng.randrange(256), rng.randrange(256), rng.randrange(256)) for _ in range(4096)]
    )
    image.save(path, "JPEG", quality=95)


@pytest.fixture
def library(tmp_path: Path) -> tuple[Path, Path, Path]:
    src, drive, db = tmp_path / "src", tmp_path / "Drive", tmp_path / "c.sqlite"
    src.mkdir()
    for i, name in enumerate(_DATED):
        _jpeg(src / name, seed=i)
    assert main(["drives", "--init", str(drive), "--label", "Photos HDD", "--db", str(db)]) == 0
    return src, drive, db


def _organize(library: tuple[Path, Path, Path], *extra: str) -> int:
    src, drive, db = library
    return main(["organize", str(src), str(drive), "--apply", "--db", str(db), *extra])


def _figure(out: str, label: str) -> int:
    """A `SUMMARY` row's number - `  files analysed     : 3`."""
    match = re.search(rf"{re.escape(label)}\s*:\s*(\d+)", out)
    assert match is not None, f"the summary printed no {label!r} row:\n{out}"
    return int(match.group(1))


def _executed(out: str) -> dict[str, int]:
    """Every `EXECUTED` row, as ``{label: count}`` - `        1  failed`.

    Parsed from the block rather than from `Counter`, because the block is what a person adds up.
    """
    # ⚠ **The block header on its OWN LINE, not the first "EXECUTED" in the text.** The plan
    # block's header points at this one by name - "What happened is in EXECUTED, below" - so a
    # bare `split` finds the pointer and parses the plan. Caught by this test on the run that
    # introduced the pointer, which is the only reason it is written this way.
    block = out.split("\nEXECUTED\n", 1)
    assert len(block) == 2, f"there is no EXECUTED block on this screen at all:\n{out}"
    rows: dict[str, int] = {}
    for line in block[1].splitlines():
        found = re.fullmatch(r"\s+(\d+)\s\s(\S.*?)\s*", line)
        if found is None:
            if line.strip() and not line.startswith("="):
                break  # past the tally, into the prose blocks below it
            continue
        rows[found.group(2)] = int(found.group(1))
    return rows


def _refuse_every_copy(monkeypatch: pytest.MonkeyPatch, *, code: int) -> None:
    """A drive that has stopped accepting bytes - `persists_for_the_run` stops the run on it."""

    def full(*_args: object, **_kwargs: object) -> None:
        raise OSError(code, "No space left on device")

    monkeypatch.setattr(safe_copy.shutil, "copyfile", full)


def _refuse_on_the_second_look(monkeypatch: pytest.MonkeyPatch) -> None:
    """A destination that passes the CLI's preflight and fails `execute`'s.

    ⚠ **The race, not a contrivance.** `_registered_or_refused` checks `may_proceed` and returns
    `4` before `execute` is called, so `organizer._refuse_impossible_destination` - which is in
    core precisely so a third surface inherits it - is reachable from this CLI **only** when the
    answer changes between the two calls: a drive that fills in between.
    """
    real = LocalDestination.preflight
    seen = {"n": 0}

    class _Impossible:
        may_proceed = False

        def detail(self) -> str:
            return "0 bytes free; this run needs more than that."

    def flaky(self: LocalDestination, sized: object) -> object:
        seen["n"] += 1
        return real(self, sized) if seen["n"] < 2 else _Impossible()  # type: ignore[arg-type]

    monkeypatch.setattr(LocalDestination, "preflight", flaky)


def test_a_run_stopped_mid_flight_still_says_what_it_did(
    library: tuple[Path, Path, Path],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """THE DETECTOR, and the absence it catches was invisible on every green run.

    Reproduced before the fix: three photographs, `ENOSPC` on the first copy, and the screen was
    the plan's `organized (unique): 3`, one `error:` line and exit 4 - **the plan number was the
    only count on it**. `last-run.json` meanwhile held `attempted: 1`, one `failed` and two
    `not attempted`, because `(agi)` records the offending file *before* re-raising and `(agj)`
    carries the results out on the exception. Both arrived at `_stopped_run_exit` and stopped.
    """
    _refuse_every_copy(monkeypatch, code=errno.ENOSPC)

    code = _organize(library)

    out = capsys.readouterr().out
    rows = _executed(out)
    assert code == 4, "a run stopped by a full drive is still an unusable destination"
    assert rows == {"failed": 1, "not attempted": 2}, (
        f"the outcome of a stopped run is not on the screen: {rows}"
    )


def test_a_destination_that_refuses_before_the_first_byte_says_nothing_was_tried(
    library: tuple[Path, Path, Path],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The other raising route, where `results` really is empty.

    An empty block plus `3 not attempted` is the honest account: nothing was attempted, and the
    screen says so rather than omitting the block and leaving the plan's `3` as the last word.
    """
    _refuse_on_the_second_look(monkeypatch)

    code = _organize(library)

    out = capsys.readouterr().out
    assert code == 4
    assert _executed(out) == {"not attempted": len(_DATED)}


@pytest.mark.parametrize("stop", ["mid-flight", "before-the-first-byte", "none"])
def test_the_two_documents_account_for_the_same_files(
    library: tuple[Path, Path, Path],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    stop: str,
) -> None:
    """`(aac)`'S LAW ON THE PLAN-VERSUS-OUTCOME AXIS, which is the whole point of the entry.

    Every file `SUMMARY` analysed is accounted for exactly once in `EXECUTED` - as an outcome or
    as one never attempted. It is checkable **only because both documents are now on one screen**;
    on the stopped routes the second one did not exist.

    The clean case is the cry-wolf half: the law must hold when nothing went wrong, or it is
    asserting the injection rather than the property.
    """
    if stop == "mid-flight":
        _refuse_every_copy(monkeypatch, code=errno.ENOSPC)
    elif stop == "before-the-first-byte":
        _refuse_on_the_second_look(monkeypatch)

    _organize(library)

    out = capsys.readouterr().out
    analysed = _figure(out, "files analysed")
    accounted = sum(_executed(out).values())
    assert accounted == analysed == len(_DATED), (
        f"the screen accounts for {accounted} of the {analysed} files it analysed:\n{out}"
    )


def test_a_clean_run_does_not_claim_it_missed_anything(
    library: tuple[Path, Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    """CRY-WOLF. Nothing is stubbed, so the divergence line must be absent, not zero.

    `stop_block` answers `None` when the run reached everything, and never-silent is about what
    happened - a `0 not attempted` row on a clean run is a number invented to fill a slot.
    """
    assert _organize(library) == 0

    out = capsys.readouterr().out
    assert "not attempted" not in out, "a run that reached every file said it had missed some"
    assert _executed(out) == {"organized": len(_DATED)}


def test_the_promise_falls_when_undated_files_are_skipped(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`(acx)` ON THIS SURFACE - the overstating direction, and the worse one.

    `--skip-undated` leaves undated files in `buckets.unique`, so the four conserved rows promise
    files the run will not take. ⚠ **The correction is a FIFTH ROW, never a subtraction inside the
    four**: taking undated out of `unique` would repair this law by breaking `(aac)`'s. Both hold
    here, on one screen, which is the assertion that pins the shape of the fix and not just its
    result.

    The app has had this since `(acx)`; the CLI's summary never called `will_organize` at all.
    """
    src, drive, db = tmp_path / "src", tmp_path / "Drive", tmp_path / "c.sqlite"
    src.mkdir()
    _jpeg(src / _DATED[0], seed=0)
    # PIL writes no EXIF, and this name carries no date - so it is genuinely undateable.
    _jpeg(src / "holiday.jpg", seed=9)
    assert main(["drives", "--init", str(drive), "--label", "Photos HDD", "--db", str(db)]) == 0

    code = main(["organize", str(src), str(drive), "--apply", "--skip-undated", "--db", str(db)])

    out = capsys.readouterr().out
    assert code == 0
    assert _figure(out, "to organize") == 1, "the promise still counts the undated file"
    assert _executed(out)["organized"] == _figure(out, "to organize"), (
        "the run organized a different number of files than the screen promised"
    )
    # `(aac)`'s law, unbroken by the fix to `(acx)`'s.
    conserved = sum(
        _figure(out, label)
        for label in (
            "organized (unique)",
            "organized (near-dup)",
            "skipped (exact dup)",
            "could not be read",
        )
    )
    assert conserved == _figure(out, "files analysed") == 2


def test_the_header_names_the_document(
    library: tuple[Path, Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    """⚠ **A STRING ASSERTION, AND IT IS ONLY THAT.** It cannot see whether the wording is honest.

    Kept because the header is the one thing telling a reader that the block above `EXECUTED` is a
    plan; deleting it is a silent regression of `(aim)`'s change 1. Anyone rewording it will have
    to come here and decide deliberately, which is the whole of what a string assertion buys.
    """
    assert _organize(library) == 0

    out = capsys.readouterr().out
    assert "SUMMARY - the plan." in out, "the plan block does not say it is a plan"
    assert out.index("SUMMARY") < out.index("\nEXECUTED\n"), "the plan must precede the outcome"
