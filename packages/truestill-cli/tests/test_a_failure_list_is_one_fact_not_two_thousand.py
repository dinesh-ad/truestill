"""A refused destination printed one fact 2,096 times. `(afd)`

Measured 2026-08-22 on the real library: 2,110 files, a destination denied after ten had landed.
**2,096 `FAILED` lines on stderr, carrying ONE distinct reason**, beside an `EXECUTED` summary
that already said ``2096  failed``. Redirecting stdout did not help, because the flood was on the
other stream.

⚠ **The stream was never the defect.** clig.dev puts errors and messaging on ``stderr`` on
purpose - moving a failure report to ``stdout`` would feed it into whatever the run was piped
into. What clig also says is *"don't treat stderr like a log file, at least not by default"*, and
2,096 lines is precisely that. So the cap is the fix and the stream is unchanged.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
from truestill_cli.cli import _STATUS_PREVIEW, _print_execution, _reason_key
from truestill_core.categorize import CategoryMatch, Confidence
from truestill_core.destinations.local import _upload_failure
from truestill_core.drive_unwritable import metadata_not_preserved_note
from truestill_core.models import (
    ActionResult,
    ActionStatus,
    DateSource,
    Decision,
    FileHashes,
    Resolution,
)
from truestill_core.safe_copy import CopyOutcome


def _reported(results: list[ActionResult]) -> int:
    """`_print_execution` over results whose plan is exactly these files.

    It takes the plan as well as the outcome, for one line: the files that produced no result at
    all. Here every file was attempted, so `stop_block` answers `None` and nothing is claimed
    about a divergence - which is what these tests are about. `(aim)`
    """
    return _print_execution(results, [r.resolution for r in results])


def _result(name: str, status: ActionStatus, detail: str) -> ActionResult:
    category = CategoryMatch(
        label="Camera", reason="t", confidence=Confidence.MEDIUM, rule="device"
    )
    decision = Decision(
        source=Path(f"/src/{name}"),
        category=category,
        captured_at=datetime(2014, 1, 5, 18, 12),
        date_source=DateSource.EXIF,
        date_tag="DateTimeOriginal",
        relative=Path(f"Camera/2014/01/{name}"),
    )
    resolution = Resolution(
        decision=decision,
        hashes=FileHashes(sha256="a" * 64, perceptual=None),
        exact_duplicate=None,
        near_duplicate=None,
    )
    return ActionResult(resolution, status, None, detail)


def _refused(count: int) -> list[ActionResult]:
    """What one refused destination really produces: a different path per file, one cause."""
    return [
        _result(
            f"IMG_{i:05d}.jpg",
            ActionStatus.FAILED,
            f"cannot upload to 'Camera/2014/01/IMG_{i:05d}.jpg': "
            f"[Errno 13] Permission denied: '/dest/Camera/2014/01'",
        )
        for i in range(count)
    ]


def test_a_flood_of_failures_is_capped_and_counted(capsys: pytest.CaptureFixture[str]) -> None:
    """The measured case, in miniature: many failures, one reason, one elision line."""
    _reported(_refused(2096))

    err = capsys.readouterr().err
    named = [line for line in err.splitlines() if line.startswith("  FAILED:")]
    assert len(named) == _STATUS_PREVIEW, "the list is uncapped again"
    assert f"... and {2096 - _STATUS_PREVIEW:,} more FAILED (all the same reason)." in err


def test_the_elision_says_how_many_reasons_when_they_differ(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """⚠ The cry-wolf half. "All the same reason" must not be printed over a mixed tail.

    Eliding 2,000 lines is only safe because they said one thing; if they said three, the count
    is the only thing standing between the reader and a hidden second cause.
    """
    results = _refused(60)
    results[40] = _result("odd.jpg", ActionStatus.FAILED, "[Errno 28] No space left on device")
    results[41] = _result("odd2.jpg", ActionStatus.FAILED, "[Errno 5] Input/output error")

    _reported(results)

    err = capsys.readouterr().err
    assert "3 distinct reasons in total" in err
    assert "all the same reason" not in err


def test_a_short_list_is_not_elided(capsys: pytest.CaptureFixture[str]) -> None:
    """The ordinary case must not gain a line that says nothing."""
    _reported(_refused(3))

    err = capsys.readouterr().err
    assert len([line for line in err.splitlines() if line.startswith("  FAILED:")]) == 3
    assert "... and" not in err


def test_move_kept_shares_the_cap(capsys: pytest.CaptureFixture[str]) -> None:
    """⚠ Two sites, one fix: they were the same six lines twice, two lines apart.

    `MOVE KEPT`'s own worst case is **UNMEASURED** - it needs a per-file removal failure after a
    verified copy, which a whole-destination refusal does not produce - so this asserts the shape
    it shares, not a volume anyone has seen.
    """
    kept = [
        _result(f"K_{i:05d}.jpg", ActionStatus.MOVE_KEPT, "source kept: could not remove it")
        for i in range(50)
    ]
    _reported(kept)

    err = capsys.readouterr().err
    assert len([line for line in err.splitlines() if line.startswith("  MOVE KEPT:")]) == (
        _STATUS_PREVIEW
    )
    assert f"... and {50 - _STATUS_PREVIEW} more MOVE KEPT" in err


def test_the_report_stays_on_stderr(capsys: pytest.CaptureFixture[str]) -> None:
    """Errors belong on stderr (clig.dev); the volume was the defect, not the stream."""
    _reported(_refused(40))

    captured = capsys.readouterr()
    assert "FAILED:" in captured.err
    assert "FAILED:" not in captured.out


def test_one_cause_with_many_paths_counts_as_one_reason() -> None:
    """⚠ Why the count needs normalising at all, and why it is labelled an approximation.

    A detail names its own source and target, so 2,096 failures from one refusal carry 2,096
    *distinct* strings. Counting them verbatim would report 2,096 reasons for one fact - the
    opposite of what the elision is for. A genuinely different cause stays distinct, because the
    part that differs is not quoted.
    """
    same = {
        _reason_key(f"cannot upload to 'a/{i}.jpg': [Errno 13] Permission denied: '/dest/a'")
        for i in range(500)
    }
    assert len(same) == 1

    assert _reason_key("[Errno 13] Permission denied: 'x'") != _reason_key(
        "[Errno 28] No space left on device: 'x'"
    )


def test_both_real_producers_collapse_to_one_reason() -> None:
    """`(aiv)`: the key strips QUOTED parts, and both producers led with an unquoted source name,
    so 2,519 files failing for one condition counted as 2,519 reasons. Pinned against the real
    templates, not a stand-in - a template that stops quoting the name fails here."""

    error = PermissionError(1, "Operation not permitted")
    notes = {
        _reason_key(metadata_not_preserved_note(f"{i}.jpg", f"x/{i}.jpg", error)) for i in range(3)
    }
    assert len(notes) == 1, notes

    full = OSError(28, "No space left on device")
    uploads = {
        _reason_key(
            _upload_failure(
                Path(f"/src/{i}.jpg"),
                Path(f"/dest/x/{i}.jpg"),
                f"x/{i}.jpg",
                CopyOutcome(ok=False, error=full),
            )
        )
        for i in range(3)
    }
    assert len(uploads) == 1, uploads


def test_the_near_duplicate_annotation_does_not_split_a_reason_by_path() -> None:
    """The third producer, found on a real run: three near-duplicates among 45 refused-timestamps
    files carried *"; near-duplicate of <path> [...]"* with the path unquoted, so one condition read
    as four reasons. The path is quoted now; the distance is a fact and may still differ."""
    tails = {
        _reason_key(
            f"'{i}.jpg' was copied to 'x/{i}.jpg' and is safe, but refused; near-duplicate of '/src/{i}.jpg' [run, distance=2]"
        )
        for i in range(3)
    }
    assert len(tails) == 1, tails
