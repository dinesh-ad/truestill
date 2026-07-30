"""CLI never-silent line for videos shifted from UTC CreateDate."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
from truestill_cli.cli import _print_inferred_local_shifts
from truestill_core.categorize import CategoryMatch, Confidence
from truestill_core.models import DateSource, Decision, FileHashes, Resolution


def _shifted(name: str) -> Resolution:
    decision = Decision(
        source=Path(name),
        category=CategoryMatch(
            label="Saved", reason="t", confidence=Confidence.HIGH, rule="filename_convention"
        ),
        captured_at=datetime(2014, 8, 17, 10, 21, 45),
        date_source=DateSource.INFERRED_LOCAL,
        date_tag="CreateDate|filename:VID_|+05:30",
        relative=Path(name),
        inferred_from=datetime(2014, 8, 17, 4, 54, 24),
    )
    return Resolution(
        decision=decision,
        hashes=FileHashes(sha256="abc", perceptual=None),
        exact_duplicate=None,
        near_duplicate=None,
    )


def _not_proven(name: str) -> Resolution:
    decision = Decision(
        source=Path(name),
        category=CategoryMatch(
            label="Saved", reason="t", confidence=Confidence.HIGH, rule="filename_convention"
        ),
        captured_at=datetime(2025, 8, 4, 11, 16, 38),
        date_source=DateSource.EXIF,
        date_tag="CreateDate|not_proven_utc",
        relative=Path(name),
    )
    return Resolution(
        decision=decision,
        hashes=FileHashes(sha256="def", perceptual=None),
        exact_duplicate=None,
        near_duplicate=None,
    )


def test_cli_names_each_shifted_video(capsys: pytest.CaptureFixture[str]) -> None:
    _print_inferred_local_shifts([_shifted("VID_20140817_102145.mp4"), _not_proven("clip.mp4")])
    out = capsys.readouterr().out
    assert "1 video(s) shifted from UTC CreateDate" in out
    assert "VID_20140817_102145.mp4  04:54:24 -> 10:21:45  (+05:30, filename)" in out
    assert "clip.mp4" not in out  # not_proven_utc is not a problem listing
    assert "not_proven" not in out
