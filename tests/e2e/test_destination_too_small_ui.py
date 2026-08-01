"""The screen says the drive cannot hold the run, before the button that starts it.

**Why a browser test and not a payload assertion.** The payload is already asserted in
`test_destination_limit_preview`. What can only be checked here is that the warning *reaches
the screen* and that the confirm control is still the thing the user sees next - a banner the
renderer drops on the floor would pass every source-level assertion in the repo.

**How FAT32 is simulated.** The e2e harness runs the server in-process (see `conftest`), so a
monkeypatch of `destinations.local.facts_for` - the module that uses the detection, guard rule
3 - reaches the request handler. A real FAT32 filesystem would need root and a loopback mount.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from playwright.sync_api import Page, expect
from truestill_core.filesystem import FilesystemFacts

pytestmark = pytest.mark.skipif(shutil.which("exiftool") is None, reason="exiftool not installed")

_FAT = FilesystemFacts(filesystem="vfat", max_file_bytes=1_000)


@pytest.fixture
def fat_destination(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "truestill_core.destinations.local.facts_for", lambda _target: _FAT, raising=True
    )


@pytest.mark.usefixtures("fat_destination")
def test_the_check_screen_names_the_file_that_will_not_fit(
    ui: Page, tmp_path: Path, library
) -> None:
    source = library(3, name="Pictures")
    (source / "VID_4K.mp4").write_bytes(b"\x00" * 4_000)

    ui.fill("#org-source", str(source))
    ui.fill("#org-dest", str(tmp_path / "SDCard"))
    ui.click("#org-preview")
    expect(ui.locator("#org-result")).to_contain_text("found", timeout=60_000)
    ui.click("#org-dedup")

    limit = ui.locator("[data-testid='org-destination-limit']")
    expect(limit).to_be_visible(timeout=60_000)
    expect(limit).to_contain_text("VID_4K.mp4")
    expect(limit).to_contain_text("FAT32")


def test_an_ordinary_destination_shows_no_such_warning(ui: Page, tmp_path: Path, library) -> None:
    """The cry-wolf direction, in the place a user would actually see it."""
    source = library(3, name="Pictures")

    ui.fill("#org-source", str(source))
    ui.fill("#org-dest", str(tmp_path / "Output"))
    ui.click("#org-preview")
    expect(ui.locator("#org-result")).to_contain_text("found", timeout=60_000)
    ui.click("#org-dedup")

    expect(ui.locator("#org-confirm [data-typed-confirm]")).to_be_visible(timeout=60_000)
    expect(ui.locator("[data-testid='org-destination-limit']")).to_have_count(0)
