"""Completion and drive-card honesty: damage on the payload must be rendered, not collapsed.

Source-shape guards for the three unread completion fields and the three drive-card check states.
Behaviour under a real browser is covered where e2e already opens those surfaces; these assert
the binding cannot silently drop again.
"""

from __future__ import annotations

import re
from pathlib import Path

APP_JS = Path(__file__).resolve().parents[1] / "src" / "truestill_app" / "static" / "app.js"


def _function_body(src: str, name: str) -> str:
    match = re.search(rf"(?:async )?function {name}\([^)]*\) \{{", src)
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


def test_bake_completion_renders_absent() -> None:
    body = _function_body(APP_JS.read_text(encoding="utf-8"), "bakeCompletion")
    assert "s.absent" in body
    assert "could not be found on this drive" in body


def test_backup_completion_renders_failed() -> None:
    body = _function_body(APP_JS.read_text(encoding="utf-8"), "backupCompletion")
    assert "r.failed" in body
    assert "could not be copied" in body


def test_migration_preview_renders_pending_drives() -> None:
    src = APP_JS.read_text(encoding="utf-8")
    # The success arm of the migrate preview job - not a named function.
    assert "r.pending_drives" in src
    assert "Other drives still need this layout" in src
    assert "has copies too" in src


def test_drive_card_carries_three_check_states() -> None:
    src = APP_JS.read_text(encoding="utf-8")
    assert 'data-kind="never">Never checked</span>' in src
    assert 'data-kind="gaps">Checked, found gaps</span>' in src
    assert 'data-kind="ok">Checked, clean</span>' in src
    assert "d.was_checked" in src


def test_rc_run_archives_refuses_with_the_card() -> None:
    body = _function_body(APP_JS.read_text(encoding="utf-8"), "rcRunArchives")
    assert "onRefuse:" in body
    assert 'startRefusedCard(started, "rc-dest")' in body
