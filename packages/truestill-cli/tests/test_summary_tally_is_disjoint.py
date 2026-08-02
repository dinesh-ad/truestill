"""The CLI SUMMARY block's buckets add up to the files it analysed (`(aac)` residue 1).

The same defect as the app's, on the surface where it was first measured: *"organized (unique):
5"* printed above *"files that could not be read: 2"* for seven files, with both unreadable
photos inside the 5.

The numbers are read back out of the rendered block rather than from the helper that produced
them, because the rendered block is what a person adds up and the two can drift.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from truestill_cli.cli import _print_report, _print_summary
from truestill_core.categorize import CategoryMatch, Confidence
from truestill_core.models import (
    DateSource,
    Decision,
    DuplicateKind,
    DuplicateMatch,
    FileHashes,
    Resolution,
    UnreadableReason,
)


def _resolution(
    name: str, *, unreadable: UnreadableReason | None = None, exact: bool = False
) -> Resolution:
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
        hashes=FileHashes(sha256="a" * 64, perceptual=None, unreadable=unreadable),
        exact_duplicate=(
            DuplicateMatch(kind=DuplicateKind.EXACT, matched_path="/lib/twin.jpg", origin="run")
            if exact
            else None
        ),
        near_duplicate=None,
    )


def _figure(out: str, label: str) -> int:
    match = re.search(rf"{re.escape(label)}\s*:\s*(\d+)", out)
    assert match is not None, f"the summary printed no {label!r} line:\n{out}"
    return int(match.group(1))


_MIXED = [
    _resolution("new.jpg"),
    _resolution("twin.jpg", exact=True),
    _resolution("locked.jpg", unreadable=UnreadableReason.PERMISSION),
    _resolution("failing.jpg", unreadable=UnreadableReason.IO_ERROR),
]


def test_the_printed_summary_conserves(capsys: pytest.CaptureFixture[str]) -> None:
    """Every line a reader would add up, added up. The law, on the rendered text."""
    _print_summary(_MIXED)
    out = capsys.readouterr().out

    analysed = _figure(out, "files analysed")
    parts = (
        _figure(out, "organized (unique)")
        + _figure(out, "organized (near-dup)")
        + _figure(out, "skipped (exact dup)")
        + _figure(out, "could not be read")
    )
    assert parts == analysed == len(_MIXED), (
        f"the summary's own numbers do not add up: parts={parts}, analysed={analysed}\n{out}"
    )


def test_an_unreadable_file_leaves_the_organized_count(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The reported defect, on the exact line that reported it."""
    _print_summary(_MIXED)
    out = capsys.readouterr().out

    assert _figure(out, "organized (unique)") == 1, "only new.jpg will actually be organized"
    assert _figure(out, "could not be read") == 2


def test_the_zero_line_is_always_printed(capsys: pytest.CaptureFixture[str]) -> None:
    """Cry-wolf half, inverted: the term must be present even at zero.

    Unlike the standalone "Files that could not be read" block, which stays silent on a clean
    run, this is one line in a tally that already prints ``skipped (exact dup): 0``. The law is
    only checkable by a reader if every term is on screen.
    """
    _print_summary([_resolution("a.jpg"), _resolution("b.jpg")])
    out = capsys.readouterr().out

    assert _figure(out, "could not be read") == 0
    assert _figure(out, "organized (unique)") == 2


def test_the_per_file_listing_does_not_call_an_unreadable_file_organizable(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The listing above the summary must agree with it.

    `_print_report` heads its first section *"NEW UNIQUE (n) - would be organized"* and listed
    unreadable files under it. A summary that excluded them while the list above still promised
    them would just move the contradiction up the screen.
    """
    _print_report(_MIXED, root_label="/src")
    out = capsys.readouterr().out

    assert "NEW UNIQUE (1)" in out, f"unreadable files must not be listed as organizable:\n{out}"
    assert "locked.jpg" not in out
    assert "failing.jpg" not in out
    assert "new.jpg" in out
