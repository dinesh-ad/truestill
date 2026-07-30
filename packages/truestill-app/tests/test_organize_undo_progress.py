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


def test_organize_undo_parks_shared_progress_card_in_the_panel() -> None:
    """Without parking, undoProgress renders below the 100vh app grid ((oo) class)."""
    src = APP_JS.read_text(encoding="utf-8")
    for name in ("startOrganizeUndoPreview", "startOrganizeUndoApply"):
        body = _function_body(src, name)
        assert 'appendChild($("undo-card"))' in body, f"{name} must park #undo-card into the stage"
        assert 'document.body.appendChild($("undo-card"))' in body, (
            f"{name} must return #undo-card to document.body afterwards"
        )
