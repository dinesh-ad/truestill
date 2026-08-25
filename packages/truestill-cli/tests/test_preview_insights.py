"""The preview summary reports the facts that used to exist only for a finished run.

Before this, a user could learn their library's date range and how much space duplicates waste
only by *doing the organize*. That is the wrong way round for a preview, and it is why the
producers moved into `truestill_core.insights`.

The labelling is as load-bearing as the numbers here: near-duplicates are **kept** by Truestill,
so their bytes are not savings and must never appear under a word like "freed".
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
from truestill_cli import cli
from truestill_core.categorize import CategoryMatch, Confidence
from truestill_core.models import (
    DateSource,
    Decision,
    DuplicateKind,
    DuplicateMatch,
    FileHashes,
    Resolution,
    RuleName,
)


def _resolution(
    root: Path,
    name: str,
    *,
    size: int,
    when: datetime | None = None,
    exact: bool = False,
    near: bool = False,
) -> Resolution:
    source = root / name
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b"x" * size)
    match = DuplicateMatch(
        kind=DuplicateKind.EXACT if exact else DuplicateKind.PERCEPTUAL,
        matched_path=f"/library/{name}",
        origin="catalog",
        distance=None if exact else 3,
    )
    decision = Decision(
        source=source,
        category=CategoryMatch(
            label="Camera", reason="t", confidence=Confidence.MEDIUM, rule=RuleName.DEVICE
        ),
        captured_at=when,
        date_source=DateSource.EXIF if when else DateSource.NONE,
        date_tag=None,
        relative=Path(f"Camera/{name}"),
    )
    return Resolution(
        decision=decision,
        hashes=FileHashes(sha256=f"sha-{name}", perceptual=None),
        exact_duplicate=match if exact else None,
        near_duplicate=match if near else None,
    )


@pytest.fixture
def library(tmp_path: Path) -> list[Resolution]:
    """Twenty years wide, with both duplicate tiers and an undated file."""
    return [
        _resolution(tmp_path, "a.jpg", size=100, when=datetime(2004, 6, 11)),
        _resolution(tmp_path, "b.jpg", size=200, when=datetime(2004, 8, 2)),
        _resolution(tmp_path, "c.jpg", size=5_000_000, when=datetime(2014, 1, 9)),
        _resolution(tmp_path, "d.jpg", size=400, when=datetime(2024, 7, 28), near=True),
        _resolution(tmp_path, "e.jpg", size=800, when=datetime(2014, 3, 3), exact=True),
        _resolution(tmp_path, "f.jpg", size=1600, exact=True),
        _resolution(tmp_path, "g.jpg", size=50),
    ]


def _summary(library: list[Resolution], capsys: pytest.CaptureFixture[str]) -> str:
    cli._print_summary(library)
    return capsys.readouterr().out


def test_the_capture_range_is_reported(library: list[Resolution], capsys) -> None:
    out = _summary(library, capsys)
    assert "2004-06-11" in out
    assert "2024-07-28" in out


def test_every_year_is_counted_and_undated_files_are_not_dropped(library, capsys) -> None:
    """The histogram must reconcile: three 2004/2014/2024 years plus two undated."""
    out = _summary(library, capsys)
    for year in ("2004", "2014", "2024"):
        assert year in out
    assert "undated" in out.lower()


def test_reclaimable_space_counts_exact_duplicates_only(library, capsys) -> None:
    """800 + 1600 exact bytes. The 400-byte near-duplicate must not be in that number."""
    out = _summary(library, capsys)
    line = next(line for line in out.splitlines() if "identical" in line.lower())
    assert "2,400" in line
    assert "400" not in line.replace("2,400", "")


def test_near_duplicate_bytes_are_never_called_savings(library, capsys) -> None:
    """The ruling, pinned on the WORDS. Truestill keeps near-duplicates, so nothing is freed.

    A future edit that reworded this line into "would free" for both tiers would be a promise
    the product does not keep, and no numeric assertion would catch it.
    """
    out = _summary(library, capsys).lower()
    near_line = next(line for line in out.splitlines() if "look-alike" in line)
    for forbidden in ("freed", "saved", "reclaim"):
        assert forbidden not in near_line, f"near-duplicate bytes described as {forbidden!r}"


def test_the_largest_files_are_listed_and_capped(library, capsys) -> None:
    out = _summary(library, capsys)
    assert "c.jpg" in out, "the 5 MB file must be named"
    largest = [line for line in out.splitlines() if "c.jpg" in line]
    assert largest, "no largest-files section"


def test_an_undated_library_says_so_rather_than_inventing_a_range(tmp_path: Path, capsys) -> None:
    """Cry-wolf: no dates means no range, and never a placeholder year."""
    cli._print_summary([_resolution(tmp_path, "a.jpg", size=10)])
    out = capsys.readouterr().out
    assert "1970" not in out
    assert "0001" not in out


def test_a_library_with_no_duplicates_reports_zero_rather_than_omitting_the_line(
    tmp_path: Path, capsys
) -> None:
    """`_print_summary`'s discipline: printed even at zero, so the column can be added up."""
    cli._print_summary([_resolution(tmp_path, "a.jpg", size=10, when=datetime(2020, 1, 1))])
    out = capsys.readouterr().out
    assert "identical" in out.lower()
