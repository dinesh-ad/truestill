"""The moved facts must answer identically to the code they moved out of.

`bytes_saved`, `bytes_near_dup`, `oldest` and `newest` were computed inside `_completion` and
were therefore unavailable to a preview. Moving them to `truestill_core.insights` is only safe
if the answers do not change, and "it looks equivalent" is not a measurement -- especially here,
where the two sides select their inputs differently: `_completion` filters on `ActionStatus`,
while the core producers partition on the resolution's own duplicate fields.

This is a characterization test. It was green before the refactor and must stay green after; if
it ever fails, the move changed an answer and that is the defect, not the test.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from truestill_app.service.organize import _completion
from truestill_core.categorize import CategoryMatch, Confidence
from truestill_core.insights import capture_span, duplicate_bytes
from truestill_core.models import (
    ActionResult,
    ActionStatus,
    DateSource,
    Decision,
    DuplicateKind,
    DuplicateMatch,
    FileHashes,
    Resolution,
    RuleName,
)


def _result(
    root: Path,
    name: str,
    status: ActionStatus,
    *,
    size: int,
    when: datetime | None = None,
    exact: bool = False,
    near: bool = False,
) -> ActionResult:
    source = root / "src" / name
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
    resolution = Resolution(
        decision=decision,
        hashes=FileHashes(sha256=f"sha-{name}", perceptual=None),
        exact_duplicate=match if exact else None,
        near_duplicate=match if near else None,
    )
    return ActionResult(resolution=resolution, status=status, final_relative=None)


def _mixed_run(root: Path) -> list[ActionResult]:
    """A run with every shape that matters: uploads, exact dups, near dups, dated and not."""
    return [
        _result(root, "a.jpg", ActionStatus.UPLOADED, size=100, when=datetime(2011, 3, 2)),
        _result(root, "b.jpg", ActionStatus.UPLOADED, size=200, when=datetime(2019, 7, 14)),
        _result(
            root, "c.jpg", ActionStatus.UPLOADED, size=400, when=datetime(2015, 1, 1), near=True
        ),
        _result(
            root, "d.jpg", ActionStatus.DUPLICATE, size=800, when=datetime(2013, 5, 5), exact=True
        ),
        _result(root, "e.jpg", ActionStatus.DUPLICATE, size=1600, exact=True),
        _result(root, "f.jpg", ActionStatus.UPLOADED, size=50),
    ]


def _sizes(results: list[ActionResult]) -> dict[Path, int]:
    return {
        r.resolution.decision.source: r.resolution.decision.source.stat().st_size for r in results
    }


def test_duplicate_bytes_matches_the_run_summary(tmp_path: Path) -> None:
    """`bytes_saved` and `bytes_near_dup`, from both sides, on the same run."""
    results = _mixed_run(tmp_path)
    summary = _completion(results, tmp_path / "dest")

    counted = duplicate_bytes([r.resolution for r in results], _sizes(results))

    assert counted.exact_bytes == summary["bytes_saved"]
    assert counted.near_bytes == summary["bytes_near_dup"]
    assert counted.exact_files == summary["duplicates"]
    assert counted.near_files == summary["near_dup"]


def test_the_capture_span_matches_the_run_summary(tmp_path: Path) -> None:
    """`oldest`/`newest` are taken from the ORGANIZED files, and the core call must match.

    The selection is the subtle half: a duplicate that was skipped is not part of what the run
    put in the library, so its date must not widen the range. Passing every resolution here
    would silently stretch `oldest` to 2013 and this test is what says so.
    """
    results = _mixed_run(tmp_path)
    summary = _completion(results, tmp_path / "dest")
    organized = [
        r.resolution
        for r in results
        if r.status in {ActionStatus.UPLOADED, ActionStatus.RENAMED, ActionStatus.MOVED}
    ]

    span = capture_span(organized)

    assert span is not None
    assert span.oldest.isoformat() == summary["oldest"]
    assert span.newest.isoformat() == summary["newest"]


def test_an_all_undated_run_agrees_that_there_is_no_range(tmp_path: Path) -> None:
    """Both sides must say `None` rather than one inventing a placeholder."""
    results = [_result(tmp_path, "a.jpg", ActionStatus.UPLOADED, size=10)]
    summary = _completion(results, tmp_path / "dest")

    assert summary["oldest"] is None
    assert summary["newest"] is None
    assert capture_span([r.resolution for r in results]) is None


def test_near_duplicate_bytes_are_never_folded_into_the_saved_total(tmp_path: Path) -> None:
    """The ruling, asserted against the real summary as well as the core type.

    `bytes_saved` is what an organize run avoided writing. A near-duplicate IS written, so its
    400 bytes belong to `bytes_near_dup` and to neither `bytes_saved` nor `reclaimable_bytes`.
    """
    results = _mixed_run(tmp_path)
    summary = _completion(results, tmp_path / "dest")
    counted = duplicate_bytes([r.resolution for r in results], _sizes(results))

    assert summary["bytes_saved"] == 800 + 1600
    assert summary["bytes_near_dup"] == 400
    assert counted.reclaimable_bytes == 800 + 1600
    assert counted.reclaimable_bytes != counted.exact_bytes + counted.near_bytes
