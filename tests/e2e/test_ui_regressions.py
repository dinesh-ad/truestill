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
from conftest import make_photo
from playwright.sync_api import Page, expect

_EXIFTOOL = pytest.mark.skipif(
    __import__("shutil").which("exiftool") is None, reason="exiftool not installed"
)


def _organize(ui: Page, source: Path, destination: Path) -> None:
    """Run a real organize through the UI and wait for the completion card."""
    ui.fill("#org-source", str(source))
    ui.fill("#org-dest", str(destination))
    ui.click("#org-preview")
    expect(ui.locator("#org-run")).to_be_enabled()
    ui.click("#org-run")
    expect(ui.locator("#org-result")).to_contain_text("Done")


# --- the NaN render ------------------------------------------------------------------------


def test_a_failed_job_never_renders_nan(ui: Page, tmp_path: Path) -> None:
    """Checking an ordinary folder rendered "NaN verified · NaN missing · NaN changed".

    A failure event carries `message`; the handler read `summary.error`, found nothing, and
    formatted three undefineds.
    """
    plain = tmp_path / "not-a-backup"
    plain.mkdir()

    ui.click('button[data-screen="backups"]')
    ui.fill("#verify-path", str(plain))
    ui.click("#verify-run")

    expect(ui.locator("#verify-result")).to_contain_text("truestill backup yet")
    expect(ui.locator("body")).not_to_contain_text("NaN")


# --- the two inert Cancel buttons ----------------------------------------------------------


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
    expect(ui.locator("#org-run")).to_be_enabled(timeout=60_000)
    ui.click("#org-run")
    expect(ui.locator("#org-card")).to_be_visible()
    ui.click("#org-cancel")

    expect(ui.locator("#org-card")).to_be_hidden(timeout=60_000)
    expect(ui.locator("body")).not_to_contain_text("NaN")
    organized = list(destination.rglob("*.jpg")) if destination.exists() else []
    assert len(organized) < 400, "cancel did not stop the run"


@_EXIFTOOL
def test_cancel_actually_stops_a_verify(ui: Page, tmp_path: Path) -> None:
    """Verify's Cancel handler was an empty function -- visible, enabled, and inert.

    Cancelling needs something to cancel, so this verifies a real library rather than an empty
    folder: an empty check finishes before the button can be pressed, which makes the test
    race rather than test.
    """
    source = tmp_path / "many"
    for i in range(300):
        make_photo(source / f"IMG_{i:04d}.jpg", i, size=(700, 520))
    destination = tmp_path / "Library"
    _organize(ui, source, destination)

    ui.click('button[data-screen="backups"]')
    ui.fill("#verify-path", str(destination))
    ui.click("#verify-run")
    expect(ui.locator("#verify-card")).to_be_visible()
    ui.click("#verify-cancel")

    # It stops, and stopping is reported as stopping -- never as a result with holes in it.
    expect(ui.locator("#verify-card")).to_be_hidden(timeout=60_000)
    expect(ui.locator("body")).not_to_contain_text("NaN")


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
    expect(ui.locator("#verify-result")).to_contain_text("truestill backup yet")

    ui.fill("#bk-source", str(destination))
    ui.fill("#bk-target", str(backup))
    ui.click("#bk-preview")
    expect(ui.locator("#bk-run")).to_be_visible()
    ui.click("#bk-run")
    expect(ui.locator("#bk-result")).to_contain_text("copied to")

    expect(ui.locator("#verify-result")).not_to_contain_text("truestill backup yet")


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
    ui.fill("#bk-source", str(destination))
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
