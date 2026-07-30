"""One named test per UI bug the soak era found.

Each of these shipped, was found by a person using the app, and lived in client-side
JavaScript. They are grouped here rather than spread by screen so the list stays readable as
what it is: the record of what this layer exists to stop happening again.

Every assertion is on **text a user reads**, not on element ids. That is deliberate -- each of
these bugs was a wrong or stale *string*, and an id-based assertion would have caught none of
them.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from conftest import AppServer, make_photo
from playwright.sync_api import Page, expect
from truestill_core.destinations.base import CrossDeviceError
from truestill_core.destinations.local import LocalDestination

_EXIFTOOL = pytest.mark.skipif(
    __import__("shutil").which("exiftool") is None, reason="exiftool not installed"
)


def _organize(ui: Page, source: Path, destination: Path, *, mode: str = "copy") -> None:
    """Run a real organize through the UI and wait for the completion card."""
    ui.check(f'input[name="org-mode"][value="{mode}"]')
    ui.fill("#org-source", str(source))
    ui.fill("#org-dest", str(destination))
    ui.click("#org-preview")
    expect(ui.locator("#org-result")).to_contain_text("found")
    ui.click("#org-dedup")
    typed = ui.locator("#org-confirm [data-typed-confirm]")
    expect(typed).to_be_visible()
    typed.fill("move")
    ui.click("#org-confirm [data-typed-go]")
    expect(ui.locator("#org-result")).to_contain_text("Done")


# --- the NaN render ------------------------------------------------------------------------


def test_a_failed_job_never_renders_nan(ui: Page, tmp_path: Path) -> None:
    """Checking an ordinary folder rendered "NaN verified · NaN missing · NaN changed".

    A failure event carries `message`; the handler read `summary.error`, found nothing, and
    formatted three undefineds. Soft-fail for an unmarked folder now returns the drive-
    correction card before a job starts; the message says "drive", not "backup".
    """
    plain = tmp_path / "not-a-backup"
    plain.mkdir()

    ui.click('button[data-screen="backups"]')
    ui.fill("#verify-path", str(plain))
    ui.click("#verify-run")

    expect(ui.locator("#verify-result")).to_contain_text("truestill drive yet")
    expect(ui.locator("body")).not_to_contain_text("NaN")


# --- the two inert Cancel buttons ----------------------------------------------------------


@_EXIFTOOL
def test_look_inside_returns_before_duplicate_check(ui: Page, tmp_path: Path, library) -> None:
    """(tt) Look inside must show counts without enabling Organize; Check for duplicates is
    the explicit second step that unlocks the run."""
    source = library(5, name="Album")
    destination = tmp_path / "Out"

    ui.fill("#org-source", str(source))
    ui.fill("#org-dest", str(destination))
    ui.click("#org-preview")
    expect(ui.locator("#org-result")).to_contain_text("5 photos found")
    expect(ui.locator("#org-result")).to_contain_text("no dates or duplicates checked yet")
    expect(ui.locator("#org-run")).to_be_disabled()
    expect(ui.locator("#org-dedup")).to_be_enabled()

    ui.click("#org-dedup")
    expect(ui.locator("#org-result")).to_contain_text("new - will be organized")
    expect(ui.locator("#org-confirm [data-typed-confirm]")).to_be_visible()
    expect(ui.locator("#org-confirm")).to_contain_text("Type move to continue")


@_EXIFTOOL
def test_cancel_actually_stops_an_organize(ui: Page, tmp_path: Path) -> None:
    """The Cancel button was wired, but cancelling mid-hash crashed the job with a KeyError
    that reached the UI as a bare file path. Asserted on outcome, never on timing: the run
    must stop having placed fewer files than the source held."""
    source = tmp_path / "many"
    for i in range(400):
        make_photo(source / f"IMG_{i:04d}.jpg", i, size=(700, 520))
    destination = tmp_path / "out"

    ui.fill("#org-source", str(source))
    ui.fill("#org-dest", str(destination))
    ui.click("#org-preview")
    expect(ui.locator("#org-result")).to_contain_text("found")
    ui.click("#org-dedup")
    typed = ui.locator("#org-confirm [data-typed-confirm]")
    expect(typed).to_be_visible(timeout=60_000)
    typed.fill("move")
    ui.click("#org-confirm [data-typed-go]")
    expect(ui.locator("#org-card")).to_be_visible()
    ui.click("#org-cancel")

    expect(ui.locator("#org-card")).to_be_hidden(timeout=60_000)
    expect(ui.locator("body")).not_to_contain_text("NaN")
    organized = list(destination.rglob("*.jpg")) if destination.exists() else []
    assert len(organized) < 400, "cancel did not stop the run"


def test_organize_mode_persists_and_inplace_hides_destination(ui: Page) -> None:
    ui.check('input[name="org-mode"][value="inplace"]')
    expect(ui.locator("#org-dest-field")).to_be_hidden()
    expect(ui.locator("#org-mode-hint")).to_contain_text("never falls back to copy")

    ui.reload()
    expect(ui.locator('input[name="org-mode"][value="inplace"]')).to_be_checked()
    expect(ui.locator("#org-dest-field")).to_be_hidden()


@_EXIFTOOL
def test_move_mode_reports_mechanism_and_reversibility_before_confirm(
    ui: Page, tmp_path: Path, library
) -> None:
    source = library(3, name="Source")
    destination = tmp_path / "Library"
    ui.fill("#org-source", str(source))
    ui.fill("#org-dest", str(destination))
    ui.check('input[name="org-mode"][value="move"]')
    ui.click("#org-preview")
    ui.click("#org-dedup")

    confirm = ui.locator("#org-confirm")
    expect(confirm).to_contain_text("Before you organize")
    expect(confirm).to_contain_text("move by rename")
    expect(confirm).to_contain_text("reversible with undo-organize")


def test_cross_device_move_is_reported_as_not_reversible_before_confirm(ui: Page) -> None:
    """The reversibility line is mechanism-driven, not mode-driven."""
    ui.route(
        "**/api/organize/inventory",
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body='{"tier":"inventory","files":1,"photos":1,"videos":0,"audio":0,"by_format":{"photos":{"jpg":1},"videos":{},"audio":{}},"total_bytes":10,"skipped":{"documents":{},"unrecognized":{}}}',
        ),
    )
    ui.route(
        "**/api/organize/preview",
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body=('{"job_id":"x"}' if route.request.method == "POST" else '{"ok":false}'),
        ),
    )
    ui.route(
        "**/api/jobs/x/events**",
        lambda route: route.fulfill(
            status=200,
            content_type="text/event-stream",
            body=(
                'data: {"type":"done","status":"done","summary":{"files":1,"photos":1,'
                '"videos":0,"audio":0,"new_unique":1,"near_dup":0,"exact_dup":0,'
                '"undated":0,"folders":{"Camera":1},"skipped":{"documents":{},'
                '"unrecognized":{}},"mode":"move","mechanism":{"same_filesystem":false,'
                '"reversible":false,"uses_rename":false,"requires_destination":true}}}\n\n'
            ),
        ),
    )
    ui.fill("#org-source", "/tmp/src")
    ui.fill("#org-dest", "/tmp/dst")
    ui.check('input[name="org-mode"][value="move"]')
    ui.click("#org-preview")
    ui.click("#org-dedup")
    expect(ui.locator("#org-confirm")).to_contain_text("not reversible with undo-organize")


@_EXIFTOOL
def test_inplace_refuses_cross_device_instead_of_falling_back_to_copy(
    ui: Page, library, monkeypatch: pytest.MonkeyPatch
) -> None:
    """In-place must refuse a cross-device answer; it cannot silently copy."""

    def always_cross_device(
        _self: LocalDestination,
        _source: Path,
        _relative: str,  # pragma: no cover - mutation guard
    ) -> None:
        message = "simulated cross-device"
        raise CrossDeviceError(message)

    monkeypatch.setattr(LocalDestination, "adopt", always_cross_device)

    source = library(2, name="Source")
    ui.fill("#org-source", str(source))
    ui.check('input[name="org-mode"][value="inplace"]')
    ui.click("#org-preview")
    ui.click("#org-dedup")
    typed = ui.locator("#org-confirm [data-typed-confirm]")
    expect(typed).to_be_visible()
    typed.fill("move")
    ui.click("#org-confirm [data-typed-go]")

    expect(ui.locator("#org-result")).to_contain_text("could not be organized")
    # A copy fallback would have removed the originals from this source root.
    assert len(list(source.rglob("*.jpg"))) == 2


@_EXIFTOOL
def test_reversible_organize_shows_durable_undo_affordance(
    ui: Page, tmp_path: Path, library
) -> None:
    source = library(3, name="Source")
    destination = tmp_path / "Library"
    _organize(ui, source, destination, mode="move")

    expect(ui.locator("#org-undo-panel")).to_contain_text("Undo the last reversible organize run")
    expect(ui.locator("#org-undo-panel")).to_contain_text("undo-organize")
    ui.click("#org-undo-preview")
    expect(ui.locator("#org-undo-stage [data-typed-confirm]")).to_be_visible()
    ui.reload()
    expect(ui.locator("#org-undo-panel")).to_contain_text("Undo the last reversible organize run")


@_EXIFTOOL
def test_move_completion_reports_empty_folders_and_offers_clean_flow(
    ui: Page, tmp_path: Path
) -> None:
    source = tmp_path / "Source"
    make_photo(source / "nested" / "IMG_0001.jpg", 1)
    destination = tmp_path / "Library"

    _organize(ui, source, destination, mode="move")
    result = ui.locator("#org-result")
    expect(result).to_contain_text("empty folder")
    expect(result).to_contain_text("nested")
    ui.click("[data-org-clean-preview]")
    expect(ui.locator("[data-org-clean-stage] [data-typed-confirm]")).to_be_visible()


def test_the_verify_cancel_button_is_wired_to_something(ui: Page, app_server: AppServer) -> None:
    """Verify's Cancel handler was an empty function -- visible, enabled, and inert.

    Deliberately a wiring assertion rather than a browser race. A verify of any corpus small
    enough for CI finishes in well under the time it takes to click, so a test that presses
    Cancel mid-check is a coin toss dressed as coverage -- exactly the thing the no-retry
    policy exists to keep out. The *mechanism* (press Cancel, the job stops, the page reports
    it) is proven end to end by `test_cancel_actually_stops_an_organize`, which has enough
    work to be deterministic. What is left to guard here is that this particular button is
    connected to it, which is precisely what regressed.
    """
    app_js = ui.request.get(f"{app_server.base_url}/static/app.js").text()

    handler = app_js.split('$("verify-cancel").onclick')[1].split("\n")[0]
    assert "verifyJob" in handler  # it knows which job it is cancelling
    assert "cancel" in handler  # and it asks the server to stop it
    assert "() => {}" not in handler  # the empty function that shipped


# --- the stale message ---------------------------------------------------------------------


@_EXIFTOOL
def test_a_completed_copy_clears_the_stale_not_a_backup_message(
    ui: Page, tmp_path: Path, library
) -> None:
    """After a copy succeeded, the Check section still called the new backup "not a backup
    yet" -- the page contradicting itself about state it had just changed."""
    source = library(4)
    destination = tmp_path / "Library"
    backup = tmp_path / "Backup"
    backup.mkdir()
    _organize(ui, source, destination)

    ui.click('button[data-screen="backups"]')
    ui.fill("#verify-path", str(backup))
    ui.click("#verify-run")
    expect(ui.locator("#verify-result")).to_contain_text("truestill drive yet")

    ui.fill("#bk-source", str(destination))
    ui.fill("#bk-target", str(backup))
    ui.click("#bk-preview")
    expect(ui.locator("#bk-run")).to_be_visible()
    ui.click("#bk-run")
    expect(ui.locator("#bk-result")).to_contain_text("copied to")

    expect(ui.locator("#verify-result")).not_to_contain_text("truestill drive yet")


# --- prefill and carry-over ----------------------------------------------------------------


@_EXIFTOOL
def test_the_backup_target_carries_over_from_the_check_field(
    ui: Page, tmp_path: Path, library
) -> None:
    """Both fields name the backup drive; typing it twice on one page is the bug."""
    _organize(ui, library(3), tmp_path / "Library")
    backup = tmp_path / "Backup"
    backup.mkdir()

    ui.click('button[data-screen="backups"]')
    ui.fill("#verify-path", str(backup))
    ui.locator("#verify-path").blur()

    expect(ui.locator("#bk-target")).to_have_value(str(backup))
    expect(ui.locator("#bk-target-carried")).to_be_visible()


@_EXIFTOOL
def test_prefill_never_proposes_copying_the_library_onto_itself(
    ui: Page, tmp_path: Path, library
) -> None:
    """The guard on the carry-over.

    With no backup yet, the Check field is prefilled from the catalog with the *library* path.
    If carry-over reacted to that, "To" would fill with the library and the page would offer to
    copy it onto itself -- so only user input may carry, never a programmatic prefill.
    """
    destination = tmp_path / "Library"
    _organize(ui, library(3), destination)

    ui.reload()
    ui.click('button[data-screen="backups"]')

    expect(ui.locator("#verify-path")).to_have_value(str(destination))
    expect(ui.locator("#bk-target")).to_have_value("")


# --- what the completion cards say ---------------------------------------------------------


@_EXIFTOOL
def test_a_finished_organize_says_organized_and_never_uploaded(
    ui: Page, tmp_path: Path, library
) -> None:
    """ "Done · 2,269 uploaded" was backend vocabulary for an event that did not happen on a
    local disk, and it contradicts the promise the product is built on."""
    _organize(ui, library(5), tmp_path / "Library")

    result = ui.locator("#org-result")
    expect(result).to_contain_text("organized")
    expect(result).not_to_contain_text("uploaded")
    expect(result).not_to_contain_text("nothing to do")


@_EXIFTOOL
def test_a_successful_organize_never_says_nothing_to_do(ui: Page, tmp_path: Path, library) -> None:
    """The original B1 blocker, pinned in the layer it lived in: a run that placed files
    reported that nothing had happened."""
    destination = tmp_path / "Library"
    _organize(ui, library(4), destination)

    expect(ui.locator("#org-result")).to_contain_text("4 files organized")
    assert len(list(destination.rglob("*.jpg"))) == 4  # and the screen matches the disk


@_EXIFTOOL
def test_a_finished_copy_splits_photos_and_videos_without_form_letter_grammar(
    ui: Page, tmp_path: Path, library
) -> None:
    """ "Copied 2,269 photo(s)" folded videos into photos and used "(s)" grammar."""
    source = library(3)
    (source / "clip.mp4").write_bytes(b"a-unique-video-file")
    destination = tmp_path / "Library"
    backup = tmp_path / "Backup"
    backup.mkdir()
    _organize(ui, source, destination)

    ui.click('button[data-screen="backups"]')
    # Organize's loadCustody prefills bk-source with the library path. Filling again races that
    # async write (clear → prefill → type) and has doubled the path on CI. Assert the prefill,
    # same as the golden-path handoff, instead of re-typing it.
    expect(ui.locator("#bk-source")).to_have_value(str(destination))
    ui.fill("#bk-target", str(backup))
    ui.click("#bk-preview")
    expect(ui.locator("#bk-run")).to_be_visible()
    ui.click("#bk-run")

    result = ui.locator("#bk-result")
    expect(result).to_contain_text("3 photos · 1 video")
    expect(result).not_to_contain_text("(s)")
    expect(result).to_contain_text("Every copy verified")


# --- custody strip honesty -----------------------------------------------------------------


def test_the_custody_strip_is_honest_when_the_catalog_is_empty(ui: Page) -> None:
    expect(ui.locator("#custody-line")).to_contain_text("0 photos")
    expect(ui.locator("#custody-line")).to_contain_text("not backed up yet")


@_EXIFTOOL
def test_the_custody_strip_counts_places_not_wishes(ui: Page, tmp_path: Path, library) -> None:
    """One organized library is one place -- and says so, rather than implying safety."""
    _organize(ui, library(4), tmp_path / "Library")

    expect(ui.locator("#custody-line")).to_contain_text("4 photos")
    expect(ui.locator("#custody-line")).to_contain_text("safe in 1 place")


def test_catalog_path_stays_inside_custody_at_a_narrow_viewport(
    ui: Page, app_server: AppServer
) -> None:
    """Absolute catalog path must not spill the custody strip (announce-path layout bug).

    Middle-ellipsis keeps the start and the filename; the full path stays in ``title`` /
    ``data-full`` so it remains unambiguous and copyable.
    """
    path = ui.locator("#custody-catalog")
    expect(path).to_be_visible()
    full = str(app_server.db.resolve())
    expect(path).to_have_attribute("data-full", full)
    expect(path).to_have_attribute("title", full)

    ui.set_viewport_size({"width": 360, "height": 720})
    ui.evaluate("() => window.dispatchEvent(new Event('resize'))")
    expect(path).to_be_visible()
    # Auto-waiting geometry check: painted box inside the strip, no horizontal overflow.
    ui.wait_for_function(
        """() => {
          const path = document.getElementById('custody-catalog');
          const strip = document.getElementById('custody');
          if (!path || !strip) return false;
          const p = path.getBoundingClientRect();
          const s = strip.getBoundingClientRect();
          return (
            p.left >= s.left - 0.5
            && p.right <= s.right + 0.5
            && path.scrollWidth <= path.clientWidth + 1
          );
        }"""
    )
    # Selectable so a user can copy the unambiguous absolute path.
    assert ui.evaluate(
        "() => getComputedStyle(document.getElementById('custody-catalog')).userSelect"
    ) in {"text", "auto", "all"}


# --- a blank screen is never an acceptable answer to a failure -----------------------------


def test_a_server_error_shows_a_visible_error_not_a_blank_screen(ui: Page) -> None:
    """Found for real: a long-running server process pinned to old code answered Trips &
    events with a response shape the shipped app.js no longer understood - the screen showed
    no cards, no error and no "none found" message. Nothing checked the response before using
    it, and nothing caught the exception that followed.

    This is the HTTP-error half of that defect: `api()` now rejects any non-2xx response with
    a legible error, and every handler that calls it is wrapped (`guarded()`) so the error
    lands in the visible global banner instead of vanishing.
    """
    ui.route(
        "**/api/events/propose",
        lambda route: route.fulfill(status=500, content_type="text/plain", body="boom"),
    )
    ui.click('button[data-screen="events"]')
    ui.fill("#ev-source", "/anything")
    ui.click("#ev-propose")

    expect(ui.locator("#global-error")).to_be_visible()
    expect(ui.locator("#global-error")).to_contain_text("500")


def test_a_wrong_shape_response_shows_a_visible_error_not_a_blank_screen(ui: Page) -> None:
    """The other half of the same defect, reproduced exactly: a 200 response in the pre-13.3b
    shape (`clusters`, not today's `cards`) makes `renderCards(undefined)` throw - previously
    an uncaught `TypeError` with nothing to see. Now it lands in the same visible banner.
    """
    ui.route(
        "**/api/events/propose",
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body='{"ok": true, "session": "x", "clusters": []}',
        ),
    )
    ui.click('button[data-screen="events"]')
    ui.fill("#ev-source", "/anything")
    ui.click("#ev-propose")

    expect(ui.locator("#global-error")).to_be_visible()
    expect(ui.locator("#global-error")).to_contain_text("undefined")
