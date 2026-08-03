"""Every surface that counts duplicates must also say where their twins are.

The split is asserted **out of the rendered block**, not from the helper that computes it, for
the reason `test_summary_tally_is_disjoint.py` gives: the rendered block is what a person reads,
and the two can drift. `test_duplicate_origin_split.py` covers the counting itself.

Three surfaces, because a user meets the number in three places and one of them saying less than
the others is how a report becomes untrustworthy: the preview's EXACT DUPLICATES block, the
EXECUTED tally after `--apply`, and Analyze's deep pass.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from truestill_cli.cli import _print_deep, _print_execution, _print_report
from truestill_core.categorize import CategoryMatch, Confidence
from truestill_core.duplicate_explain import origin_phrase
from truestill_core.models import (
    ActionResult,
    ActionStatus,
    DateSource,
    Decision,
    DuplicateKind,
    DuplicateMatch,
    DuplicateOrigin,
    FileHashes,
    Resolution,
)

LIBRARY = origin_phrase(DuplicateOrigin.CATALOG)  # "already in your library"
BATCH = origin_phrase(DuplicateOrigin.RUN)  # "earlier in this batch"


def _resolution(name: str, origin: DuplicateOrigin | None) -> Resolution:
    decision = Decision(
        source=Path("/src") / name,
        category=CategoryMatch(
            label="Camera", reason="t", confidence=Confidence.HIGH, rule="device"
        ),
        captured_at=None,
        date_source=DateSource.NONE,
        date_tag=None,
        relative=Path("Camera/Undated") / name,
    )
    return Resolution(
        decision=decision,
        hashes=FileHashes(sha256="a" * 64, perceptual=None),
        exact_duplicate=(
            None
            if origin is None
            else DuplicateMatch(
                kind=DuplicateKind.EXACT, matched_path="/lib/twin.jpg", origin=origin
            )
        ),
        near_duplicate=None,
    )


def _mixed() -> list[Resolution]:
    """Two already in the library, one duplicated inside the batch, one new."""
    return [
        _resolution("a.jpg", DuplicateOrigin.CATALOG),
        _resolution("b.jpg", DuplicateOrigin.CATALOG),
        _resolution("c.jpg", DuplicateOrigin.RUN),
        _resolution("d.jpg", None),
    ]


def _executed(resolutions: list[Resolution]) -> list[ActionResult]:
    return [
        ActionResult(
            resolution=r,
            status=(
                ActionStatus.DUPLICATE if r.exact_duplicate is not None else ActionStatus.UPLOADED
            ),
            final_relative=None if r.exact_duplicate is not None else r.decision.relative,
            detail="",
        )
        for r in resolutions
    ]


# --- the three surfaces ------------------------------------------------------------------------


def test_the_preview_names_where_each_duplicate_group_matched(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """`EXACT DUPLICATES (3) - skipped` is true and answers nothing a person is asking."""
    _print_report(_mixed(), "DRIVE")
    out = capsys.readouterr().out
    assert f"2 {LIBRARY}" in out
    assert f"1 matched another file {BATCH}" in out


def test_the_executed_tally_names_them_too(capsys: pytest.CaptureFixture[str]) -> None:
    """The apply run is where the number is largest and the question most pressing."""
    _print_execution(_executed(_mixed()))
    out = capsys.readouterr().out
    assert f"2 {LIBRARY}" in out
    assert f"1 matched another file {BATCH}" in out


def test_analyze_names_them_as_within_the_folder(capsys: pytest.CaptureFixture[str]) -> None:
    """Analyze seeds no catalog rows, so *every* match it can find is inside the folder.

    Printing "already in your library" there would be a plain falsehood, and printing an
    unqualified count invites the reader to assume the opposite of the truth.
    """
    _print_deep([_resolution("c.jpg", DuplicateOrigin.RUN)], {Path("/src/c.jpg"): 10})
    out = capsys.readouterr().out
    assert BATCH in out
    assert LIBRARY not in out


# --- cry-wolf ----------------------------------------------------------------------------------


def test_a_run_with_no_duplicates_says_nothing_about_origins(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A clean run must not grow a block of zeroes explaining what did not happen."""
    _print_report([_resolution("d.jpg", None)], "DRIVE")
    out = capsys.readouterr().out
    assert LIBRARY not in out
    assert BATCH not in out


def test_one_origin_only_prints_one_line(capsys: pytest.CaptureFixture[str]) -> None:
    """The common case - a re-run of a folder already organized - reads as one statement."""
    _print_report(
        [_resolution("a.jpg", DuplicateOrigin.CATALOG)],
        "DRIVE",
    )
    out = capsys.readouterr().out
    assert f"1 {LIBRARY}" in out
    assert BATCH not in out


def test_the_split_sums_to_the_count_above_it(capsys: pytest.CaptureFixture[str]) -> None:
    """The reason this is computed from every match rather than from a displayed sample."""
    resolutions = [_resolution(f"{i}.jpg", DuplicateOrigin.CATALOG) for i in range(5)]
    resolutions += [_resolution(f"r{i}.jpg", DuplicateOrigin.RUN) for i in range(3)]
    _print_report(resolutions, "DRIVE")
    out = capsys.readouterr().out
    assert "EXACT DUPLICATES (8)" in out
    assert f"5 {LIBRARY}" in out
    assert f"3 matched another file {BATCH}" in out
