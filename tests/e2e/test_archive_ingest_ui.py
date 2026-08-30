"""Archive ingest, driven in a real browser ((jj)).

§2: source assertions are not coverage of a flow. This is a multi-step, disk-touching path -
precheck, decide, confirm, cancel - so it needs a browser that actually clicks.

**Refusals are asserted by CODE (`data-refusal`), never by sentence.** Five refusals render
similar-looking prose, so matching words lets a test pass because a *different* refusal fired.
That is guard rule 8 - where two things produce the same visible outcome, assert provenance -
and it applies directly here, which is why the refusal code is in the DOM at all.
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest
from playwright.sync_api import Page, expect
from truestill_core.filesystem import FilesystemFacts

_SIDECAR = json.dumps({"photoTakenTime": {"timestamp": "1403000000"}}).encode()


def _zip(path: Path, entries: dict[str, bytes]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as archive:
        for name, data in entries.items():
            archive.writestr(name, data)
    return path


def _part(directory: Path, number: int, entries: dict[str, bytes]) -> Path:
    return _zip(directory / f"takeout-20260801T000000Z-{number:03d}.zip", entries)


def _fingerprint(root: Path) -> list[tuple[str, int]]:
    """Every file under ``root`` with its size - the byte-level discipline the other previews use."""
    if not root.exists():
        return []
    return sorted(
        (p.relative_to(root).as_posix(), p.stat().st_size) for p in root.rglob("*") if p.is_file()
    )


def _preview(ui: Page, source: Path, destination: Path) -> None:
    ui.click('button[data-screen="import"]')
    ui.fill("#rc-takeout", str(source))
    ui.fill("#rc-dest", str(destination))
    ui.click("#rc-preview")


def test_a_missing_part_is_refused_by_code(ui: Page, tmp_path: Path) -> None:
    """Asserted on `data-refusal`, not the sentence: several refusals read alike."""
    source = tmp_path / "src"
    for number in (1, 2, 4):
        _part(source, number, {f"a/IMG_{number}.jpg": b"\xff\xd8x"})

    _preview(ui, source, tmp_path / "dest")

    expect(ui.locator("[data-refusal='missing_part']")).to_be_visible()
    expect(ui.locator("[data-testid='rc-refusal-detail']")).to_contain_text("3")


def test_a_nested_archive_is_refused_by_code_and_names_the_entry(ui: Page, tmp_path: Path) -> None:
    source = tmp_path / "src"
    _zip(source / "photos.zip", {"a/IMG_1.jpg": b"\xff\xd8x", "a/inner.zip": b"PK"})

    _preview(ui, source, tmp_path / "dest")

    expect(ui.locator("[data-refusal='nested_archive']")).to_be_visible()
    expect(ui.locator("[data-testid='rc-refusal-detail']")).to_contain_text("a/inner.zip")


def test_an_unreadable_part_is_refused_by_code(ui: Page, tmp_path: Path) -> None:
    source = tmp_path / "src"
    source.mkdir(parents=True)
    (source / "broken.zip").write_bytes(b"not a zip at all")

    _preview(ui, source, tmp_path / "dest")

    expect(ui.locator("[data-refusal='unreadable']")).to_be_visible()


def test_a_folder_with_no_archives_takes_the_ordinary_path(ui: Page, tmp_path: Path) -> None:
    """A regression guard, replacing an assertion of mine that was simply wrong.

    I first asserted a `no_archives` refusal here. But an already-extracted Takeout folder is
    *also* a folder with no archives, and it must keep working exactly as before - so the
    precheck deliberately falls through rather than refusing. `no_archives` belongs to an empty
    *selection*, which is where the HTTP tests assert it.
    """
    source = tmp_path / "src"
    source.mkdir(parents=True)

    _preview(ui, source, tmp_path / "dest")

    expect(ui.locator("[data-testid='rc-summary']")).to_be_visible(timeout=60_000)
    expect(ui.locator("[data-refusal]")).to_have_count(0)


def test_the_space_figure_is_shown_as_the_archives_own_claim(ui: Page, tmp_path: Path) -> None:
    """A header field must not read as something Truestill measured."""
    source = tmp_path / "src"
    _zip(source / "photos.zip", {"a/IMG_1.jpg": b"\xff\xd8" + b"x" * 400})

    _preview(ui, source, tmp_path / "dest")

    expect(ui.locator("[data-testid='rc-claim']")).to_contain_text("claim")


def test_declining_after_the_precheck_writes_nothing(ui: Page, tmp_path: Path) -> None:
    """Byte-identical destination, same discipline as the other previews.

    The user sees the cost and walks away - that must be free.
    """
    source = tmp_path / "src"
    destination = tmp_path / "dest"
    destination.mkdir(parents=True)
    (destination / "existing.txt").write_text("untouched")
    _zip(source / "photos.zip", {"a/IMG_1.jpg": b"\xff\xd8x"})
    before = _fingerprint(destination)

    _preview(ui, source, destination)
    expect(ui.locator("[data-testid='rc-confirm']")).to_be_visible()

    assert _fingerprint(destination) == before, "the precheck wrote to the destination"


def test_confirming_unpacks_and_reports(ui: Page, tmp_path: Path) -> None:
    """The whole flow: precheck, confirm, job, summary - clicked rather than asserted about.

    The photo is in part 1 and its sidecar in part 2, so a summary reporting a recovered date is
    also proof the merge happened across the boundary.
    """
    source = tmp_path / "src"
    folder = "Takeout/Google Photos/Photos from 2014"
    _part(source, 1, {f"{folder}/IMG_0001.jpg": b"\xff\xd8jpegbytes"})
    _part(source, 2, {f"{folder}/IMG_0001.jpg.json": _SIDECAR})

    _preview(ui, source, tmp_path / "dest")
    ui.click("[data-testid='rc-confirm']")

    expect(ui.locator("[data-testid='rc-summary']")).to_be_visible(timeout=60_000)
    expect(ui.locator("[data-testid='rc-summary']")).to_contain_text("1")


def test_cancelling_leaves_a_staging_tree_the_next_run_can_clear(ui: Page, tmp_path: Path) -> None:
    """Cancel is not a special case - the journal already describes the tree.

    Asserted on the journal rather than on the card, because the card only says what happened
    and the property is what is left on disk.
    """
    source = tmp_path / "src"
    destination = tmp_path / "dest"
    entries = {
        f"Takeout/a/IMG_{i:04d}.jpg": b"\xff\xd8" + bytes([i % 251]) * 90_000 for i in range(60)
    }
    _zip(source / "photos.zip", entries)

    _preview(ui, source, destination)
    ui.click("[data-testid='rc-confirm']")
    ui.click("#rc-cancel")

    expect(ui.locator("[data-testid='rc-cancelled']")).to_be_visible(timeout=60_000)
    staging = destination / ".truestill-staging"
    assert list(staging.glob("*.json")), "cancel left a tree with no journal to attribute it"


def test_an_entry_too_large_for_the_drive_is_refused_by_code(
    ui: Page, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The FAT32 per-file ceiling, refused before the unpack rather than part way through it.

    Worth a browser test even though the refusal-rendering path is generic: what is unproven at
    the source level is that the app hands `precheck_archives` a real destination to interrogate.
    A surface passing the wrong path would detect the wrong filesystem and refuse nothing, and
    every source-level assertion would still pass.
    """
    monkeypatch.setattr(
        "truestill_core.archive_ingest.facts_for",
        lambda _target: FilesystemFacts(filesystem="vfat", max_file_bytes=1_000),
    )
    source = tmp_path / "src"
    _zip(source / "photos.zip", {"a/IMG_1.jpg": b"\xff\xd8x", "a/VID_4K.mp4": b"\0" * 5_000})

    _preview(ui, source, tmp_path / "dest")

    expect(ui.locator("[data-refusal='oversized_entry']")).to_be_visible()
    expect(ui.locator("[data-testid='rc-refusal-detail']")).to_contain_text("a/VID_4K.mp4")
