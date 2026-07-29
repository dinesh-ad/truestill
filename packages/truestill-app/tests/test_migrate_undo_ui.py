"""Source guards for the in-app migration undo affordance (backlog pp).

These assert that the shipped JS/HTML still contains the wiring strings - they are NOT a
proof that the flow works in a browser. Behaviour (reload durability, typed confirm, refusals,
cancel/resume) is covered by ``tests/e2e/test_migrate_undo.py``.
"""

from __future__ import annotations

from pathlib import Path

APP_JS = (
    Path(__file__).resolve().parents[1] / "src" / "truestill_app" / "static" / "app.js"
).read_text(encoding="utf-8")
INDEX = (
    Path(__file__).resolve().parents[1] / "src" / "truestill_app" / "templates" / "index.html"
).read_text(encoding="utf-8")


def test_typed_confirm_is_a_reusable_helper() -> None:
    """(oo)/(rr) will need the same gate - it must not be inline one-off markup."""
    assert "function typedConfirm(" in APP_JS
    assert 'word: "undo"' in APP_JS
    assert "data-typed-confirm" in APP_JS


def test_undo_affordance_is_durable_not_a_snackbar() -> None:
    """Re-query on Trips and Settings load - the record survives a tab reload."""
    assert 'if (name === "events")' in APP_JS
    assert 'if (name === "settings")' in APP_JS
    assert 'refreshUndoAffordance($("ev-source").value.trim(), $("ev-undo-panel"))' in APP_JS
    assert 'refreshUndoAffordance($("mig-path").value.trim(), $("mig-undo-panel"))' in APP_JS
    assert 'id="ev-undo-panel"' in INDEX
    assert 'id="mig-undo-panel"' in INDEX


def test_undo_affordance_is_re_queried_after_migration() -> None:
    """Supersession has no push signal - polling after apply is the only one that exists."""
    assert 'refreshUndoAffordance($("ev-source").value.trim(), $("ev-undo-panel"))' in APP_JS
    assert 'refreshUndoAffordance($("mig-path").value.trim(), $("mig-undo-panel"))' in APP_JS
    # Both the trips apply-to-disk completion and the settings migrate completion re-query.
    assert APP_JS.count("refreshUndoAffordance(") >= 4


def test_undo_states_newest_only_plainly() -> None:
    assert "Only the most recent migration on a drive is reversible" in APP_JS


def test_undo_refusals_are_rendered() -> None:
    assert "function undoRefusalList(" in APP_JS
    assert "left untouched" in APP_JS
    assert "r.reason" in APP_JS


def test_undo_disappears_when_not_armed() -> None:
    """refreshUndoAffordance clears the panel when the journal is spent or absent."""
    assert 'if (!r.ok || !r.armed) { panel.innerHTML = ""; return; }' in APP_JS


def test_undo_uses_job_endpoints_not_a_parallel_mechanism() -> None:
    assert '"/api/migrate/undo/preview"' in APP_JS
    assert '"/api/migrate/undo/apply"' in APP_JS
    assert "/api/migrate/undo?path=" in APP_JS


def test_undo_apply_outcome_does_not_wipe_armed_card_handlers() -> None:
    """innerHTML concat after refresh killed Preview onclick on a partial cancel (e2e catch)."""
    assert 'insertAdjacentHTML("afterbegin"' in APP_JS
    assert "panel.innerHTML = summaryHtml + panel.innerHTML" not in APP_JS
