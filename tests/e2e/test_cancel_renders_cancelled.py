"""(F38 latent B) Cancel mid-run must render cancelled, never the success path.

Cancel returns ok:true with status cancelled. Without an explicit branch, verify paints
"Checked", backup paints Done, trip/migrate paint "Moved N", and undo opens confirm or
"Put N back" - the tool telling the user a run completed when they stopped it.

The correct branch already existed on previews 5/8/9/13 and organize run; it failed to
propagate. These tests drive each of the seven surfaces with a mocked cancelled terminal.
"""

from __future__ import annotations

import json

from e2e_support import open_screen
from playwright.sync_api import Page, expect

_CANCELLED = {"type": "done", "status": "cancelled"}


def _sse(summary: dict) -> str:
    return f"data: {json.dumps({**_CANCELLED, 'summary': summary})}\n\n"


def _json(route, body: dict) -> None:
    route.fulfill(status=200, content_type="application/json", body=json.dumps(body))


def _events(route, summary: dict) -> None:
    route.fulfill(status=200, content_type="text/event-stream", body=_sse(summary))


def test_verify_cancel_renders_cancelled_not_checked(ui: Page) -> None:
    """Verify is read-only: cancel changes nothing on disk, but must not claim Checked."""
    ui.route("**/api/verify/run", lambda r: _json(r, {"job_id": "verify-job"}))
    ui.route(
        "**/api/jobs/verify-job/events**",
        lambda r: _events(
            r,
            {
                "label": "Busy Drive",
                "verified": 12,
                "missing": 0,
                "mismatch": 0,
                "unreadable": 0,
                "problems": [],
            },
        ),
    )
    ui.click('button[data-screen="backups"]')
    ui.fill("#verify-path", "/tmp/backup")
    ui.click("#verify-run")
    result = ui.locator("#verify-result")
    expect(result).to_contain_text("Check cancelled")
    expect(result).not_to_contain_text("Checked")


def test_backup_run_cancel_renders_stopped_not_done(ui: Page) -> None:
    """Partial copies are real; cancelled must say Stopped / before you stopped it."""
    ui.route("**/api/backup/run", lambda r: _json(r, {"job_id": "bk-job"}))
    ui.route(
        "**/api/jobs/bk-job/events**",
        lambda r: _events(
            r,
            {
                "photos": 2,
                "videos": 0,
                "audio": 0,
                "bytes_copied": 500,
                "to": "Backup",
                "verified": False,
            },
        ),
    )
    open_screen(ui, "backups")
    ui.fill("#bk-source", "/tmp/lib")
    ui.fill("#bk-target", "/tmp/backup")
    # Preview is a separate sync call; this test owns the run's cancelled terminal only.
    # Native click: Playwright's locator click does not fire this previously-hidden button's
    # handler reliably after classList.remove('hidden') in the same turn.
    ui.evaluate(
        """() => {
          const b = document.getElementById('bk-run');
          b.classList.remove('hidden');
          b.click();
        }"""
    )
    result = ui.locator("#bk-result")
    expect(result).to_contain_text("before you stopped it")
    expect(result).to_contain_text("2 photos copied to Backup")
    # .done-mark is CSS-uppercased in the a11y tree; read the DOM textContent instead.
    assert (
        ui.evaluate("() => document.querySelector('#bk-result .done-mark')?.textContent")
        == "Stopped"
    )


def test_trip_apply_to_disk_cancel_renders_stopped_with_partial_count(ui: Page) -> None:
    """Apply-to-disk moves real files; cancelled must name how many moved before stop."""
    ui.route(
        "**/api/events/propose",
        lambda r: _json(
            r,
            {
                "ok": True,
                "session": "sess",
                "label": "Drive",
                "declines": [],
                "collapsed": None,
                "cards": [
                    {
                        "kind": "event",
                        "start": "2021-01-01",
                        "end": "2021-01-01",
                        "count": 3,
                        "active_days": 1,
                        "days": [],
                        "location": None,
                        "collapsed": False,
                    }
                ],
            },
        ),
    )
    ui.route(
        "**/api/events/sess/apply",
        lambda r: _json(r, {"events": 1, "trips": 0}),
    )
    ui.route(
        "**/api/events/sess/preview",
        lambda r: _json(r, {"job_id": "preview-job"}),
    )
    ui.route(
        "**/api/jobs/preview-job/events**",
        lambda r: r.fulfill(
            status=200,
            content_type="text/event-stream",
            body=(
                'data: {"type":"done","status":"done","summary":'
                '{"ok":true,"moves":[{"old":"a.jpg","new":"Trip/a.jpg"}]}}\n\n'
            ),
        ),
    )
    ui.route(
        "**/api/events/sess/apply-to-disk",
        lambda r: _json(r, {"job_id": "apply-job"}),
    )
    ui.route(
        "**/api/jobs/apply-job/events**",
        lambda r: _events(r, {"migrated": 2, "groups": []}),
    )
    open_screen(ui, "events")
    ui.fill("#ev-source", "/tmp/src")
    ui.click("#ev-propose")
    ui.fill('.ev-name[data-i="0"]', "Trip")
    ui.click("#ev-apply")
    ui.click("#ev-apply-disk")
    result = ui.locator("#ev-disk-result")
    expect(result).to_contain_text("Stopped")
    expect(result).to_contain_text("Moved 2 photos before you stopped it")
    expect(result).not_to_contain_text("into trip and event folders")


def test_migrate_run_cancel_renders_stopped_with_partial_count(ui: Page) -> None:
    """Migrate apply leaves completed moves; cancelled must not claim a finished move."""
    ui.route(
        "**/api/migrate/preview",
        lambda r: _json(r, {"job_id": "mig-preview"}),
    )
    ui.route(
        "**/api/jobs/mig-preview/events**",
        lambda r: r.fulfill(
            status=200,
            content_type="text/event-stream",
            body=(
                'data: {"type":"done","status":"done","summary":{"ok":true,"moves":'
                '[{"old":"a.jpg","new":"2021/a.jpg"}],"unchanged":0,"warnings":[],'
                '"day_folder_reasons":[]}}\n\n'
            ),
        ),
    )
    ui.route("**/api/migrate/run", lambda r: _json(r, {"job_id": "mig-run"}))
    ui.route(
        "**/api/jobs/mig-run/events**",
        lambda r: _events(r, {"migrated": 1}),
    )
    ui.click('button[data-screen="settings"]')
    ui.fill("#mig-path", "/tmp/drive")
    ui.click("#mig-preview")
    typed = ui.locator("#mig-confirm [data-typed-confirm]")
    expect(typed).to_be_visible()
    typed.fill("move")
    ui.click("#mig-confirm [data-typed-go]")
    result = ui.locator("#mig-result")
    expect(result).to_contain_text("Stopped")
    expect(result).to_contain_text("Moved 1 file before you stopped it")
    expect(result).not_to_contain_text("Moved 1 file.")


def test_migrate_undo_preview_cancel_renders_cancelled_not_confirm(ui: Page) -> None:
    """Undo preview is dry-run; cancel must not open the typed-confirm success path."""
    # Playwright checks last-registered first: broad GET first, then specific preview.
    ui.route(
        "**/api/migrate/undo?**",
        lambda r: _json(r, {"ok": True, "armed": True, "file_count": 4}),
    )
    ui.route(
        "**/api/migrate/undo/preview",
        lambda r: _json(r, {"job_id": "undo-preview"}),
    )
    ui.route(
        "**/api/jobs/undo-preview/events**",
        lambda r: _events(r, {"reversed_files": 4, "refused": []}),
    )
    ui.click('button[data-screen="settings"]')
    ui.fill("#mig-path", "/tmp/drive")
    ui.locator("#mig-path").blur()
    expect(ui.locator("#mig-undo-panel")).to_contain_text("Undo the last migration")
    ui.locator("#mig-undo-panel button", has_text="Preview undo").click()
    stage = ui.locator("#mig-undo-panel [data-undo-stage]")
    expect(stage).to_contain_text("Preview cancelled")
    expect(stage.locator("[data-typed-confirm]")).to_have_count(0)
    expect(stage).not_to_contain_text("can be put back")


def test_migrate_undo_apply_cancel_renders_stopped_with_partial_count(ui: Page) -> None:
    """Undo apply can put files back before cancel; must say Stopped, not Put N back."""
    ui.route(
        "**/api/migrate/undo?**",
        lambda r: _json(r, {"ok": True, "armed": True, "file_count": 4}),
    )
    ui.route(
        "**/api/migrate/undo/preview",
        lambda r: _json(r, {"job_id": "undo-preview"}),
    )
    ui.route(
        "**/api/jobs/undo-preview/events**",
        lambda r: r.fulfill(
            status=200,
            content_type="text/event-stream",
            body=(
                'data: {"type":"done","status":"done","summary":'
                '{"reversed_files":4,"refused":[]}}\n\n'
            ),
        ),
    )
    ui.route(
        "**/api/migrate/undo/apply",
        lambda r: _json(r, {"job_id": "undo-apply"}),
    )
    ui.route(
        "**/api/jobs/undo-apply/events**",
        lambda r: _events(r, {"reversed_files": 2, "refused": []}),
    )
    open_screen(ui, "settings")
    ui.fill("#mig-path", "/tmp/drive")
    ui.locator("#mig-path").blur()
    ui.locator("#mig-undo-panel button", has_text="Preview undo").click()
    typed = ui.locator("#mig-undo-panel [data-typed-confirm]")
    expect(typed).to_be_visible()
    typed.fill("undo")
    ui.locator("#mig-undo-panel [data-typed-go]").click()
    panel = ui.locator("#mig-undo-panel")
    expect(panel).to_contain_text("Stopped")
    expect(panel).to_contain_text("Put 2 files back before you stopped it")
    expect(panel).not_to_contain_text("Put 2 files back.")


def test_organize_undo_path_cancel_renders_cancelled_not_success(ui: Page) -> None:
    """Organize-undo preview (dry) and apply (partial restores) are the remaining organize path."""
    armed = {
        "ok": True,
        "armed": True,
        "source_root": "/tmp/src",
        "dest_root": "/tmp/dst",
        "restorable": 3,
        "run_id": "run-1",
        "status": "complete",
        "skipped": [],
    }
    ui.route("**/api/organize/undo", lambda r: _json(r, armed))
    ui.route(
        "**/api/organize/undo/preview",
        lambda r: _json(r, {"job_id": "org-undo-preview"}),
    )
    ui.route(
        "**/api/jobs/org-undo-preview/events**",
        lambda r: _events(r, {"restorable": 3, "skipped": [], "applied": False}),
    )
    ui.reload()
    expect(ui.locator("#org-undo-preview")).to_be_visible()
    ui.click("#org-undo-preview")
    panel = ui.locator("#org-undo-panel")
    expect(panel).to_contain_text("Preview cancelled")
    expect(ui.locator("#org-undo-stage [data-typed-confirm]")).to_have_count(0)

    # Apply path: successful preview first, then cancelled apply with partial restores.
    ui.unroute("**/api/jobs/org-undo-preview/events**")
    ui.route(
        "**/api/jobs/org-undo-preview/events**",
        lambda r: r.fulfill(
            status=200,
            content_type="text/event-stream",
            body=(
                'data: {"type":"done","status":"done","summary":'
                '{"restorable":3,"skipped":[],"applied":false,"restored":0}}\n\n'
            ),
        ),
    )
    ui.route(
        "**/api/organize/undo/apply",
        lambda r: _json(r, {"job_id": "org-undo-apply"}),
    )
    ui.route(
        "**/api/jobs/org-undo-apply/events**",
        lambda r: _events(
            r,
            {"restored": 1, "restorable": 3, "skipped": [], "applied": True, "still_armed": True},
        ),
    )
    ui.reload()
    ui.click("#org-undo-preview")
    typed = ui.locator("#org-undo-stage [data-typed-confirm]")
    expect(typed).to_be_visible()
    typed.fill("undo")
    ui.locator("#org-undo-stage [data-typed-go]").click()
    expect(panel).to_contain_text("Stopped")
    expect(panel).to_contain_text("Restored 1 file before you stopped it")
    expect(panel).not_to_contain_text("Restored 1 file.")
