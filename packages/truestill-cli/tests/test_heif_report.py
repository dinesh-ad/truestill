"""Graceful degradation: when pillow-heif is unavailable, the report says so -- never silent."""

from __future__ import annotations

from pathlib import Path

import pytest
from truestill_cli.cli import _print_heif_note
from truestill_core.categorize import CategoryMatch, Confidence
from truestill_core.models import DateSource, Decision, FileHashes, Resolution


def _heic_resolution() -> Resolution:
    decision = Decision(
        source=Path("/src/photo.heic"),
        category=CategoryMatch(
            label="Camera", reason="t", confidence=Confidence.HIGH, rule="device"
        ),
        captured_at=None,
        date_source=DateSource.NONE,
        date_tag=None,
        relative=Path("Camera/Undated/photo.heic"),
    )
    return Resolution(
        decision=decision,
        hashes=FileHashes(sha256="abc", perceptual=None),  # perceptual skipped -> None
        exact_duplicate=None,
        near_duplicate=None,
    )


def test_note_fires_when_plugin_unavailable(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("truestill_cli.cli.HEIF_AVAILABLE", False)
    _print_heif_note([_heic_resolution()])
    out = capsys.readouterr().out
    assert "HEIC/HEIF" in out
    assert "perceptually hashed" in out  # never silent
    assert "pillow-heif is unavailable" in out


def test_note_silent_when_plugin_available(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("truestill_cli.cli.HEIF_AVAILABLE", True)
    _print_heif_note([_heic_resolution()])
    assert capsys.readouterr().out == ""  # nothing to warn about
