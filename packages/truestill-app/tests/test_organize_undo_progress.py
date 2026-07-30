"""(F45) Organize-undo must park #undo-card into the panel, like migrate-undo."""

from __future__ import annotations

import re
from pathlib import Path

APP_JS = Path(__file__).resolve().parents[1] / "src" / "truestill_app" / "static" / "app.js"


def _function_body(src: str, name: str) -> str:
    match = re.search(rf"async function {name}\(\) \{{", src)
    assert match is not None, f"{name} not found"
    start = match.end()
    depth = 1
    i = start
    while i < len(src) and depth:
        if src[i] == "{":
            depth += 1
        elif src[i] == "}":
            depth -= 1
        i += 1
    return src[start : i - 1]


def test_organize_undo_preview_and_apply_refuse_ok_false() -> None:
    """(F38 latent) Organize-undo must refuse started.ok === false like migrate-undo.

    Soft-refuse lives in runJob; callers pass onRefuse with the refusal card.
    """
    src = APP_JS.read_text(encoding="utf-8")
    run_job = src.split("async function runJob(", 1)[1].split("\nasync function withBusy(", 1)[0]
    assert "started.ok === false" in run_job
    for name in ("startOrganizeUndoPreview", "startOrganizeUndoApply"):
        body = _function_body(src, name)
        assert "onRefuse:" in body, f"{name} must soft-refuse via runJob"
        assert "startRefusedCard(started" in body, f"{name} must render the refusal card"


def test_organize_undo_parks_shared_progress_card_in_the_panel() -> None:
    """Without parking, undoProgress renders below the 100vh app grid ((oo) class)."""
    src = APP_JS.read_text(encoding="utf-8")
    run_job = src.split("async function runJob(", 1)[1].split("\nasync function withBusy(", 1)[0]
    assert 'appendChild($("undo-card"))' in run_job
    assert 'document.body.appendChild($("undo-card"))' in run_job
    for name in ("startOrganizeUndoPreview", "startOrganizeUndoApply"):
        body = _function_body(src, name)
        assert "parkUndoCardIn:" in body, f"{name} must ask runJob to park #undo-card"
        assert '$("org-undo-stage")' in body, f"{name} must park into #org-undo-stage"
