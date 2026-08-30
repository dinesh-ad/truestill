"""The Trips card offers a rename, previews it, and only then commits. `(aix)` stage 3

**The sentence this replaces was on screen for three stages**: *"already named - renaming is not
available here"*. `plan_rename` and `apply_rename` had shipped and the CLI called them; the card
said no.

🔑 **PREVIEW BEFORE COMMIT, and the browser lane is the only thing that can see it.** The gate is
in the DOM - the commit button is hidden until a preview comes back clean - so a Python test over
the routes would pass with the gate deleted. That is exactly the direction `(aer)` names: a change
that makes a screen stop showing something.

**Waits.** Every assertion waits on something only the state under test can PRODUCE - the control
itself, the refusal sentence, the button's own text - never on `to_have_count(0)` of a container
the render empties first, and never on text a previous render could have left behind
(`ENGINEERING_STANDARD.md` §4, sixteenth member).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from e2e_support import AppServer
from PIL import Image
from playwright.sync_api import Page, expect
from truestill_app.service import set_event_settings
from truestill_core.catalog import Catalog
from truestill_core.drive import create_marker
from truestill_core.hashing import sha256_file

_DAYS = ["2015-06-02", "2015-06-03", "2015-06-04", "2015-06-05"]
_PER_DAY = 3


def _drive_with_a_named_trip(db: Path, root: Path) -> None:
    """One four-day trip called ``Holiday``, as REAL photographs.

    ⚠ **Real JPEGs with real camera EXIF, not placeholder bytes.** `Camera` is ambiguous by
    construction, so the app resolves it by re-reading metadata; a file with no metadata resolves
    to `fallback`, routes to the side bin, and renders with **no trip folder at all** - so the
    rename would move nothing and the commit button would never appear. The fixture has to be
    photographs for there to be a trip to rename.
    """
    root.mkdir(parents=True, exist_ok=True)
    marker = create_marker(root, label="Photos HDD")
    # The screen's own floor is 8 and each day here clusters separately, so three a day would
    # propose no card at all. Set through the same service the settings screen posts to.
    set_event_settings(_PER_DAY, db)
    with Catalog(db) as catalog:
        catalog.upsert_drive(uuid=marker.uuid, label=marker.label)
        for index, day in enumerate(_DAYS):
            written: list[Path] = []
            for shot in range(_PER_DAY):
                path = root / f"Camera/2015/2015-06/{day} - Holiday/{day}_{shot}.jpg"
                path.parent.mkdir(parents=True, exist_ok=True)
                seed = index * _PER_DAY + shot
                Image.new("RGB", (32, 32), (seed * 20 % 256, 90, 200)).save(path, "JPEG")
                written.append(path)
            subprocess.run(
                [
                    "exiftool",
                    "-overwrite_original",
                    "-Make=Canon",
                    "-Model=Canon EOS 5D",
                    f"-DateTimeOriginal={day.replace('-', ':')} 09:00:00",
                    *[str(path) for path in written],
                ],
                check=True,
                capture_output=True,
            )
            for shot, path in enumerate(written):
                catalog.record_uploaded(
                    source_path=f"/src/{path.name}",
                    original_name=path.name,
                    sha256=sha256_file(path),
                    copy_sha256=sha256_file(path),
                    perceptual=None,
                    size=path.stat().st_size,
                    captured_at=f"{day}T09:0{shot}:00",
                    category="Camera",
                    relative=path.relative_to(root).as_posix(),
                    drive_uuid=marker.uuid,
                )
        catalog.create_trip(
            name="Holiday", slug="holiday", start_date=_DAYS[0], end_date=_DAYS[-1], days=_DAYS
        )


@pytest.fixture
def drive(app_server: AppServer, tmp_path: Path) -> Path:
    root = tmp_path / "drive"
    _drive_with_a_named_trip(app_server.db, root)
    return root


def _propose(ui: Page, root: Path) -> None:
    ui.click('button[data-screen="events"]')
    ui.fill("#ev-source", str(root))
    ui.click("#ev-propose")


def _open_rename(ui: Page, root: Path) -> None:
    _propose(ui, root)
    expect(ui.locator(".ev-rename-open")).to_be_visible(timeout=30_000)
    ui.click(".ev-rename-open")
    expect(ui.locator(".ev-rename-name")).to_be_visible()


def test_an_already_named_card_offers_a_rename(ui: Page, drive: Path) -> None:
    """⚠ **THE SENTENCE IS GONE AND A CONTROL IS THERE.** The one direction the standing rule
    names: a screen that stopped showing something.
    """
    _propose(ui, drive)

    expect(ui.locator(".ev-named")).to_be_visible(timeout=30_000)
    expect(ui.locator(".ev-named")).to_contain_text("Holiday")
    expect(ui.locator(".ev-rename-open")).to_be_visible()
    expect(ui.locator(".ev-named")).not_to_contain_text("renaming is not available here")


def test_the_commit_is_hidden_until_a_preview_says_it_may_proceed(ui: Page, drive: Path) -> None:
    """🔑 **THE GATE, and it lives in the DOM.** Opening the control offers no way to commit;
    only a clean preview produces one, and it says what it will cost.
    """
    _open_rename(ui, drive)

    expect(ui.locator(".ev-rename-go")).to_be_hidden()

    ui.fill(".ev-rename-name", "Corsica 2015")
    ui.click(".ev-rename-preview")

    # Waits on the button's own TEXT, which only a completed preview can produce.
    expect(ui.locator(".ev-rename-go")).to_contain_text("Rename, moving", timeout=60_000)
    expect(ui.locator(".ev-rename-go")).to_contain_text("12 photos")
    expect(ui.locator(".ev-rename-note")).to_contain_text("Corsica 2015")


def test_editing_the_name_again_withdraws_the_commit(ui: Page, drive: Path) -> None:
    """⚠ **The one way a preview-then-commit flow can lie**: leaving a button that would move the
    files the PREVIOUS name planned. Any edit takes it away.
    """
    _open_rename(ui, drive)
    ui.fill(".ev-rename-name", "Corsica 2015")
    ui.click(".ev-rename-preview")
    expect(ui.locator(".ev-rename-go")).to_contain_text("Rename, moving", timeout=60_000)

    ui.fill(".ev-rename-name", "Corsica 2016")

    expect(ui.locator(".ev-rename-go")).to_be_hidden()


def test_a_refusal_is_shown_and_offers_no_commit(ui: Page, drive: Path) -> None:
    """⚠ **Q1012 AT THE SURFACE: core's sentence reaches the screen.** A refusal the CLI shows and
    the app swallows is `(afe)`'s shape - and the refusal must not leave a commit button behind.
    """
    _open_rename(ui, drive)

    ui.fill(".ev-rename-name", "Holiday")  # unchanged: refused before anything is planned
    ui.click(".ev-rename-preview")

    expect(ui.locator(".ev-rename-note")).to_contain_text(
        "that is already the name; nothing would move", timeout=60_000
    )
    expect(ui.locator(".ev-rename-go")).to_be_hidden()


def test_the_rename_runs_and_the_card_says_what_it_did(ui: Page, drive: Path) -> None:
    """END TO END THROUGH THE SCREEN: preview, commit, and the name read back from the catalog."""
    _open_rename(ui, drive)
    ui.fill(".ev-rename-name", "Corsica 2015")
    ui.click(".ev-rename-preview")
    expect(ui.locator(".ev-rename-go")).to_contain_text("Rename, moving", timeout=60_000)

    ui.click(".ev-rename-go")

    expect(ui.locator(".ev-rename-note")).to_contain_text(
        "Renamed to Corsica 2015", timeout=120_000
    )
    assert any("Corsica 2015" in str(p) for p in drive.rglob("*.jpg")), (
        "the screen said it renamed, and no photograph is under the new name"
    )
