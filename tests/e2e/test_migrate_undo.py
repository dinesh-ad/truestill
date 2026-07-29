"""Browser coverage for in-app migration undo (backlog pp).

These are real Playwright tests: they open the app, seed a reversible journal in the same
catalog the server uses, and assert on text a user reads. They are the durability / typed-
confirm / refusal / cancel coverage that ``test_migrate_undo_ui.py`` (source string guards)
cannot provide.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from conftest import AppServer
from playwright.sync_api import Page, expect
from truestill_core.catalog import Catalog
from truestill_core.destinations.local import LocalDestination
from truestill_core.drive import create_marker
from truestill_core.hashing import sha256_file
from truestill_core.layout import LayoutScheme, LayoutTemplate
from truestill_core.migrate import run_migration

_YEAR_MONTH = "{yyyy}/{yyyy}-{mm}"
_YEAR_MONTH_DAY = "{yyyy}/{yyyy}-{mm}/{dd}"


def _scheme(template: str) -> LayoutScheme:
    parsed = LayoutTemplate.parse(template)
    return LayoutScheme.of(timeline=parsed, timeline_evented=parsed, side_bin=parsed)


def _seed_armed_drive(
    db: Path,
    root: Path,
    *,
    n: int = 2,
    payload_bytes: int = 32,
    template: str = _YEAR_MONTH,
) -> str:
    """Write ``n`` files under category-first paths, migrate them, return the drive uuid.

    The journal is the same reversible record the UI reads - no session flag, no snackbar.
    """
    root.mkdir(parents=True, exist_ok=True)
    marker = create_marker(root, "E2E Undo Drive")
    with Catalog(db) as catalog:
        catalog.upsert_drive(uuid=marker.uuid, label="E2E Undo Drive")
        for i in range(n):
            name = f"img_{i:04d}.jpg"
            relative = f"Camera/2023/08/{name}"
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            # Unique content so checksums differ; size tunable for cancel races.
            path.write_bytes((f"{i:04d}".encode() * (payload_bytes // 4 + 1))[:payload_bytes])
            sha = sha256_file(path)
            catalog.record_uploaded(
                source_path=f"/src/{name}",
                original_name=name,
                sha256=sha,
                copy_sha256=sha,
                perceptual=None,
                size=payload_bytes,
                captured_at=f"2023-08-{(i % 28) + 1:02d}T14:30:00",
                category="Camera",
                relative=relative,
                drive_uuid=marker.uuid,
            )
        run_migration(
            catalog,
            LocalDestination(root),
            marker.uuid,
            _scheme(template),
            apply=True,
        )
        assert catalog.reversible_migration(marker.uuid) is not None
    return marker.uuid


def _open_settings_drive(ui: Page, drive: Path) -> None:
    ui.click('button[data-screen="settings"]')
    ui.fill("#mig-path", str(drive))
    ui.locator("#mig-path").blur()


def _armed_panel(ui: Page):
    return ui.locator("#mig-undo-panel", has_text="Undo the last migration")


# --- durability --------------------------------------------------------------------------


def test_armed_panel_appears_and_survives_a_page_reload(
    ui: Page, app_server: AppServer, tmp_path: Path
) -> None:
    """The journal lives in the catalog: a reload must still find it after the path is re-entered.

    Guards the snackbar failure mode - an undo that only exists in the session is not a safety
    mechanism (backlog pp / research).
    """
    drive = tmp_path / "drive"
    _seed_armed_drive(app_server.db, drive, n=2)

    _open_settings_drive(ui, drive)
    expect(_armed_panel(ui)).to_be_visible()
    expect(_armed_panel(ui)).to_contain_text("2 files")
    expect(_armed_panel(ui)).to_contain_text(
        "Only the most recent migration on a drive is reversible"
    )

    ui.reload()
    _open_settings_drive(ui, drive)
    expect(_armed_panel(ui)).to_be_visible()
    expect(_armed_panel(ui)).to_contain_text("2 files")


def test_armed_panel_does_not_appear_when_nothing_is_armed(ui: Page, tmp_path: Path) -> None:
    """A connected drive with no reversible journal must not invent an undo card."""
    drive = tmp_path / "empty"
    drive.mkdir()
    create_marker(drive, "Empty")

    _open_settings_drive(ui, drive)
    expect(ui.locator("#mig-undo-panel")).to_be_empty()
    expect(ui.locator("#mig-undo-panel")).not_to_contain_text("Undo the last migration")


def test_armed_panel_disappears_after_a_superseding_migration_is_spent(
    ui: Page, app_server: AppServer, tmp_path: Path
) -> None:
    """A newer migration replaces the prior run_id; undoing that newest run spends the record.

    Supersession alone leaves the panel armed for the *new* run (that is the product rule:
    only the most recent migration is reversible). What must disappear is the prior run's
    undo - proven by run_id change - and the panel itself once that newest record is spent.
    """
    drive = tmp_path / "drive"
    uuid = _seed_armed_drive(app_server.db, drive, n=2, template=_YEAR_MONTH)
    with Catalog(app_server.db) as catalog:
        first = catalog.reversible_migration(uuid)
        assert first is not None
        first_run = first[0]

    _open_settings_drive(ui, drive)
    expect(_armed_panel(ui)).to_be_visible()

    # Change the layout so a second migrate has real moves, then run it through the UI.
    layout = ui.request.post(
        f"{app_server.base_url}/api/layout",
        headers={
            "x-truestill-token": app_server.token,
            "content-type": "application/json",
        },
        data=json.dumps({"template": _YEAR_MONTH_DAY}),
    )
    assert layout.ok, layout.text()

    ui.click("#mig-preview")
    expect(ui.locator("#mig-run")).to_be_visible()
    ui.click("#mig-run")
    expect(ui.locator("#mig-result")).to_contain_text("Moved", timeout=60_000)

    with Catalog(app_server.db) as catalog:
        second = catalog.reversible_migration(uuid)
        assert second is not None
        assert second[0] != first_run, "the prior undo record must be gone after supersession"
        # Rows must belong to the new run - a broken supersession that kept the old
        # migration_runs row would still advertise the first run_id.
        assert all(str(row["run_id"]) == second[0] for row in second[1])

    # Newest record is still armed - panel stays for *this* run.
    expect(_armed_panel(ui)).to_be_visible()

    # Spend it via the UI undo flow so the affordance itself goes away.
    ui.locator("#mig-undo-panel button", has_text="Preview undo").click()
    expect(ui.locator("#mig-undo-panel [data-typed-confirm]")).to_be_visible(timeout=60_000)
    ui.fill("#mig-undo-panel [data-typed-confirm]", "undo")
    ui.locator("#mig-undo-panel [data-typed-go]").click()
    expect(ui.locator("#mig-undo-panel")).to_contain_text("Put", timeout=60_000)
    expect(ui.locator("#mig-undo-panel")).to_contain_text("back")
    expect(_armed_panel(ui)).to_have_count(0)
    with Catalog(app_server.db) as catalog:
        assert catalog.reversible_migration(uuid) is None


# --- typed confirm -----------------------------------------------------------------------


def test_typed_confirm_rejects_wrong_and_empty_and_accepts_exact_undo(
    ui: Page, app_server: AppServer, tmp_path: Path
) -> None:
    """Wrong word and empty input must leave Put them back disabled; only exact ``undo`` applies."""
    drive = tmp_path / "drive"
    uuid = _seed_armed_drive(app_server.db, drive, n=2)

    _open_settings_drive(ui, drive)
    ui.locator("#mig-undo-panel button", has_text="Preview undo").click()
    confirm = ui.locator("#mig-undo-panel [data-typed-confirm]")
    go = ui.locator("#mig-undo-panel [data-typed-go]")
    expect(confirm).to_be_visible(timeout=60_000)
    expect(go).to_be_disabled()

    confirm.fill("redo")
    expect(go).to_be_disabled()
    confirm.fill("")
    expect(go).to_be_disabled()
    confirm.fill("UNDO")  # case-sensitive: CLI word is lowercase undo
    expect(go).to_be_disabled()

    # Still armed - nothing was applied.
    with Catalog(app_server.db) as catalog:
        assert catalog.reversible_migration(uuid) is not None

    confirm.fill("undo")
    expect(go).to_be_enabled()
    go.click()
    expect(ui.locator("#mig-undo-panel")).to_contain_text("Put 2 files back", timeout=60_000)
    with Catalog(app_server.db) as catalog:
        assert catalog.reversible_migration(uuid) is None


# --- refusals ----------------------------------------------------------------------------


def test_undo_preview_surfaces_refusals_with_reasons(
    ui: Page, app_server: AppServer, tmp_path: Path
) -> None:
    """A file edited after migrate must be named and reasoned - never silently skipped."""
    drive = tmp_path / "drive"
    uuid = _seed_armed_drive(app_server.db, drive, n=2)
    with Catalog(app_server.db) as catalog:
        record = catalog.reversible_migration(uuid)
        assert record is not None
        edited = drive / str(record[1][0]["new_relative"])
    edited.write_bytes(b"changed after the migration")

    _open_settings_drive(ui, drive)
    ui.locator("#mig-undo-panel button", has_text="Preview undo").click()
    panel = ui.locator("#mig-undo-panel")
    expect(panel).to_contain_text("1 file can be put back", timeout=60_000)
    expect(panel).to_contain_text("1 file left untouched")
    expect(panel).to_contain_text("changed since the migration")
    expect(panel.locator("[data-typed-confirm]")).to_be_visible()


# --- cancel ------------------------------------------------------------------------------


def test_cancel_during_undo_apply_stops_and_leaves_the_journal_resumable(
    ui: Page, app_server: AppServer, tmp_path: Path
) -> None:
    """Cancel mid-apply must stop short of spending every row so a later undo can finish."""
    drive = tmp_path / "drive"
    # Many modest files: relocate+re-hash per row is what Cancel races. A small corpus finishes
    # from page cache between Preview and Apply before the click lands.
    uuid = _seed_armed_drive(app_server.db, drive, n=250, payload_bytes=32_768)
    with Catalog(app_server.db) as catalog:
        before = catalog.reversible_migration(uuid)
        assert before is not None
        before_count = len(before[1])

    _open_settings_drive(ui, drive)
    ui.locator("#mig-undo-panel button", has_text="Preview undo").click()
    expect(ui.locator("#mig-undo-panel [data-typed-confirm]")).to_be_visible(timeout=180_000)
    # Drop page cache so apply cannot finish from RAM before Cancel is pressed.
    for path in drive.rglob("*.jpg"):
        fd = os.open(path, os.O_RDONLY)
        try:
            os.posix_fadvise(fd, 0, 0, os.POSIX_FADV_DONTNEED)
        finally:
            os.close(fd)

    ui.fill("#mig-undo-panel [data-typed-confirm]", "undo")
    ui.locator("#mig-undo-panel [data-typed-go]").click()
    expect(ui.locator("#undo-card")).to_be_visible()
    ui.click("#undo-cancel")
    expect(ui.locator("#undo-card")).to_be_hidden(timeout=180_000)

    with Catalog(app_server.db) as catalog:
        mid = catalog.reversible_migration(uuid)
        assert mid is not None, "cancel must leave a resumable journal, not spend every row"
        assert 0 < len(mid[1]) < before_count, (
            f"expected a partial spend, got {len(mid[1])} of {before_count} remaining"
        )

    # Resume: preview + confirm again finishes the rest.
    expect(_armed_panel(ui)).to_be_visible()
    ui.locator("#mig-undo-panel button", has_text="Preview undo").click()
    expect(ui.locator("#mig-undo-panel [data-typed-confirm]")).to_be_visible(timeout=180_000)
    ui.fill("#mig-undo-panel [data-typed-confirm]", "undo")
    ui.locator("#mig-undo-panel [data-typed-go]").click()
    expect(_armed_panel(ui)).to_have_count(0, timeout=180_000)
    with Catalog(app_server.db) as catalog:
        assert catalog.reversible_migration(uuid) is None
