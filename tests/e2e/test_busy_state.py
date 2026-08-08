"""Browser coverage for busy-state UI (backlog oo Commit 4).

Real Playwright flows - not source-string guards. Each behaviour was broken once while
authoring (button left disabled, DriveBusy rendered as a generic failure, second click
starting work) and restored so the assertion fails against the defect it names.
"""

from __future__ import annotations

import secrets
import shutil
import socket
import threading
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import uvicorn
from e2e_support import AppServer
from playwright.sync_api import Browser, Page, expect
from truestill_app.server import create_app
from truestill_app.service import migrate as service_migrate
from truestill_core.catalog import Catalog
from truestill_core.drive import create_marker
from truestill_core.hashing import sha256_file
from truestill_core.progress import ProgressCallback

_HOST = "127.0.0.1"

pytestmark = pytest.mark.skipif(shutil.which("exiftool") is None, reason="exiftool not installed")


def _seed_migrate_drive(db: Path, root: Path, *, n: int = 3) -> None:
    root.mkdir(parents=True, exist_ok=True)
    marker = create_marker(root, "Busy Drive")
    with Catalog(db) as catalog:
        catalog.upsert_drive(uuid=marker.uuid, label="Busy Drive")
        for i in range(n):
            name = f"img_{i:04d}.jpg"
            relative = f"Camera/2023/08/{name}"
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(f"payload-{i}".encode() * 8)
            sha = sha256_file(path)
            catalog.record_uploaded(
                source_path=f"/src/{name}",
                original_name=name,
                sha256=sha,
                copy_sha256=sha,
                perceptual=None,
                size=path.stat().st_size,
                captured_at=f"2023-08-{(i % 28) + 1:02d}T14:30:00",
                category="Camera",
                relative=relative,
                drive_uuid=marker.uuid,
            )


@pytest.fixture
def holding_server(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[tuple[AppServer, threading.Event]]:
    """App whose migrate preview blocks until ``hold`` is set - for DriveBusy / cancel races.

    Patched on ``service.migrate``, **not** on the ``service`` facade. ``migration_preview_run``
    calls ``migration_preview`` through its own module globals, so rebinding the facade's
    re-export changed nothing: from the F10 split (``46cd403``) until this line was corrected,
    the wrapper below never ran, the preview finished instantly, and all three tests using this
    fixture lost the race they exist to pin - one failing outright, the others passing without
    exercising the lock. A monkeypatch aimed at a re-export is a guard that silently stops
    guarding the moment its target moves.
    """
    hold = threading.Event()
    original = service_migrate.migration_preview

    def blocked(
        path: Path,
        db: Path,
        *,
        progress: ProgressCallback | None = None,
        cancel: threading.Event | None = None,
    ) -> dict[str, Any]:
        # Honour cancel while held so the cancel e2e can unlock without releasing hold first.
        deadline = time.monotonic() + 30
        while not hold.is_set():
            if cancel is not None and cancel.is_set():
                break
            if time.monotonic() > deadline:
                break
            time.sleep(0.05)
        return original(path, db, progress=progress, cancel=cancel)

    monkeypatch.setattr(service_migrate, "migration_preview", blocked)

    token = f"e2e-{secrets.token_urlsafe(16)}"
    db = tmp_path / "catalog.sqlite"
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((_HOST, 0))
    port = sock.getsockname()[1]
    server = uvicorn.Server(
        uvicorn.Config(create_app(token=token, db=db), log_level="warning", lifespan="off")
    )
    thread = threading.Thread(target=lambda: server.run(sockets=[sock]), daemon=True)
    thread.start()
    boot = threading.Event()
    while not server.started and thread.is_alive():
        if boot.wait(0.05):
            break
        if not thread.is_alive():
            pytest.fail("holding server died at boot")
    if not server.started:
        pytest.fail("holding server did not start")

    yield AppServer(base_url=f"http://{_HOST}:{port}", token=token, db=db), hold

    hold.set()
    server.should_exit = True
    thread.join(timeout=10)
    sock.close()


def test_migrate_preview_disables_trigger_shows_progress_and_re_enables(
    ui: Page, app_server: AppServer, tmp_path: Path
) -> None:
    """Guards the freeze: button must look busy, progress must render, then unlock."""
    drive = tmp_path / "drive"
    _seed_migrate_drive(app_server.db, drive, n=4)
    ui.click('button[data-screen="settings"]')
    ui.fill("#mig-path", str(drive))
    btn = ui.locator("#mig-preview")
    btn.click()
    # Either still busy or already finished - progress card or result must appear.
    expect(ui.locator("#mig-card:not(.hidden), #mig-result .headline")).to_be_visible()
    # Gated by the same unsound `to_be_enabled` as the backup test below, so it carries its own
    # timeout rather than inheriting the 5 s default behind it.
    expect(btn).to_be_enabled(timeout=30_000)
    expect(ui.locator("#mig-result")).to_contain_text("to move", timeout=30_000)


def test_migrate_preview_re_enables_after_cancel(
    browser: Browser, holding_server: tuple[AppServer, threading.Event], tmp_path: Path
) -> None:
    """An error/cancel path that left the button dead would be worse than the original freeze."""
    app, _hold = holding_server
    drive = tmp_path / "drive"
    _seed_migrate_drive(app.db, drive, n=2)
    page = browser.new_page()
    page.set_default_timeout(15_000)
    page.goto(app.url)
    page.click('button[data-screen="settings"]')
    page.fill("#mig-path", str(drive))
    btn = page.locator("#mig-preview")
    btn.click()
    expect(btn).to_be_disabled()
    expect(btn).to_have_attribute("aria-busy", "true")
    page.click("#mig-cancel")
    expect(btn).to_be_enabled(timeout=15_000)
    page.close()


def test_migrate_preview_re_enables_after_drive_error(ui: Page, tmp_path: Path) -> None:
    """Soft-fail (not a drive) must unlock the trigger so the user can correct the path."""
    plain = tmp_path / "not-a-drive"
    plain.mkdir()
    ui.click('button[data-screen="settings"]')
    ui.fill("#mig-path", str(plain))
    btn = ui.locator("#mig-preview")
    btn.click()
    expect(ui.locator("#mig-result")).to_contain_text("drive")
    expect(btn).to_be_enabled()


def test_second_click_while_busy_starts_no_second_run(
    browser: Browser, holding_server: tuple[AppServer, threading.Event], tmp_path: Path
) -> None:
    """Client withBusy no-ops a second click; server lock is the cross-tab authority."""
    app, hold = holding_server
    drive = tmp_path / "drive"
    _seed_migrate_drive(app.db, drive, n=2)
    page = browser.new_page()
    page.set_default_timeout(15_000)
    page.goto(app.url)
    page.click('button[data-screen="settings"]')
    page.fill("#mig-path", str(drive))
    btn = page.locator("#mig-preview")
    btn.click()
    expect(btn).to_be_disabled()
    # Disabled buttons do not receive clicks in the browser - that is the UX half of the guard.
    assert btn.is_disabled()
    hold.set()
    expect(btn).to_be_enabled(timeout=15_000)
    page.close()


def test_drive_busy_from_server_renders_actionable_message(
    browser: Browser, holding_server: tuple[AppServer, threading.Event], tmp_path: Path
) -> None:
    """Second tab must see DriveBusy's own copy, not a generic failure (backlog oo)."""
    app, hold = holding_server
    drive = tmp_path / "drive"
    _seed_migrate_drive(app.db, drive, n=2)

    page1 = browser.new_page()
    page1.set_default_timeout(15_000)
    page1.goto(app.url)
    page1.click('button[data-screen="settings"]')
    page1.fill("#mig-path", str(drive))
    page1.click("#mig-preview")
    expect(page1.locator("#mig-preview")).to_be_disabled()

    page2 = browser.new_page()
    page2.set_default_timeout(15_000)
    page2.goto(app.url)
    page2.click('button[data-screen="settings"]')
    page2.fill("#mig-path", str(drive))
    page2.click("#mig-preview")
    expect(page2.locator("#mig-result")).to_contain_text("Already running")
    expect(page2.locator("#mig-result")).to_contain_text("migrate preview")
    expect(page2.locator("#mig-result")).to_contain_text("Busy Drive")
    expect(page2.locator("#mig-preview")).to_be_enabled()

    hold.set()
    page1.close()
    page2.close()


def test_backup_preview_busy_re_enables(ui: Page, tmp_path: Path, library) -> None:
    """Sync busy-only path: disable for the request, unlock after (success or soft-fail)."""
    source = library(3, name="Lib")
    dest = tmp_path / "Out"
    ui.fill("#org-source", str(source))
    ui.fill("#org-dest", str(dest))
    ui.click("#org-preview")
    # Each of the three waits below guards real work on a shared CI runner - a directory walk, an
    # exiftool+hashing pass, then a run that copies files. The 5 s default is sized for a laptop
    # and is the same defect the backup assertion at the end of this test hit.
    expect(ui.locator("#org-result")).to_contain_text("photos found", timeout=30_000)
    ui.click("#org-dedup")
    expect(ui.locator("#org-confirm [data-typed-confirm]")).to_be_visible(timeout=60_000)
    # `copy`, not `move`: the confirm word names the operation the run performs, and this
    # flow is in the default copy mode. Changed with the fix that made the word mode-aware.
    ui.fill("#org-confirm [data-typed-confirm]", "copy")
    ui.click("#org-confirm [data-typed-go]")
    expect(ui.locator("#org-result")).to_contain_text("organized", timeout=60_000)

    ui.click('button[data-screen="backups"]')
    target = tmp_path / "Backup"
    target.mkdir()
    # Prefill can name the library drive; set both ends explicitly so the preview is about
    # copying Out -> Backup, not whatever custody last remembered.
    ui.fill("#bk-source", str(dest))
    ui.fill("#bk-target", str(target))
    btn = ui.locator("#bk-preview")
    btn.click()
    # ORDER MATTERS HERE, and reversing it is what made this test flaky.
    #
    # `to_be_enabled` is not a sound completion signal on its own: it is also true in the window
    # between `click()` returning and the handler synchronously disabling the button, so it can
    # pass before the work has even STARTED. The next assertion then races a request still in
    # flight, and backup preview is not cheap - `attach_drive` walks the library and hashes what
    # it finds.
    #
    # The result text IS sound. `withBusy` re-enables in a `finally` that runs after the handler
    # has written `#bk-result`, so the text can only appear once the work is done. Waiting on it
    # first removes the race rather than tolerating it, and the button check that follows is then
    # instant and can keep the default timeout. Same shape as
    # `test_migrate_preview_re_enables_after_drive_error` above.
    #
    # STILL FLAKY ON CI, AND THE TIMEOUT IS NOT WHY - do not raise it. Backlog `(abq)`, proven
    # 2026-08-07 from run `31208332669`'s trace: the click below is LOST. No
    # `/api/backup/preview` request is issued at all, and `"Checking what to copy…"` - the label
    # `withBusy` sets before any work - never appears. Thirty seconds of a request that was
    # never made. Reordering (above) fixed a different, real race; it did not fix this one.
    expect(ui.locator("#bk-result")).to_contain_text("to copy", timeout=30_000)
    expect(btn).to_be_enabled()
