"""(F38 latent B) Cancel arrives as ok:true - each surface must say cancelled, not success.

The correct branch already existed on organize preview/run and Takeout/trip/migrate
previews; it failed to propagate to the seven sites below. Source guards pin the wiring;
e2e asserts the words a user reads.
"""

from __future__ import annotations

import re
from pathlib import Path

APP_JS = Path(__file__).resolve().parents[1] / "src" / "truestill_app" / "static" / "app.js"


def _slice_between(src: str, start_marker: str, end_marker: str) -> str:
    start = src.index(start_marker)
    end = src.index(end_marker, start + len(start_marker))
    return src[start:end]


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


def test_seven_sites_branch_on_cancelled_before_success() -> None:
    """Each of the seven missing sites must treat d.status === cancelled before d.ok success."""
    src = APP_JS.read_text(encoding="utf-8")
    sites: list[tuple[str, str]] = [
        ("startUndoPreview", _function_body(src, "startUndoPreview")),
        ("startUndoApply", _function_body(src, "startUndoApply")),
        ("startOrganizeUndoPreview", _function_body(src, "startOrganizeUndoPreview")),
        ("startOrganizeUndoApply", _function_body(src, "startOrganizeUndoApply")),
        (
            "verify-run",
            _slice_between(src, '$("verify-run").onclick', '$("verify-cancel").onclick'),
        ),
        (
            "ev-apply-disk",
            _slice_between(src, '$("ev-apply-disk").onclick', '$("ev-cancel").onclick'),
        ),
        (
            "bk-run",
            _slice_between(src, '$("bk-run").onclick', '$("bk-cancel").onclick'),
        ),
        ("startMigrateRun", _function_body(src, "startMigrateRun")),
    ]
    for label, body in sites:
        assert 'd.status === "cancelled"' in body, (
            f"{label} must branch on cancelled (ok:true would otherwise paint success)"
        )


def test_reference_sites_still_say_cancelled() -> None:
    """Four previews + organize run already did this; extraction must keep that behaviour."""
    src = APP_JS.read_text(encoding="utf-8")
    assert (
        src.count('d.status === "cancelled"') >= 12
    )  # 5 reference + 7 fixed (+ organize undo pair)
    assert "Check cancelled" in src
    assert "Preview cancelled" in src
    assert "before you stopped it" in src
