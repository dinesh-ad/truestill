"""The Import screen's apply, clicked in a real browser. D17.

⚠ **THE SCREEN IS WHERE "0 IMPORTED" CAME FROM, and no service test could have found it.** The
service was right, the route was right, and the browser handed the run the path out of the input
box - a `.zip` - because that is what the user typed. `discover()` walked an archive FILE, found
no photographs, and reported a confident zero. The first test here is that flow, clicked, with the
files on disk counted afterwards.

§2 again: these are multi-step, disk-touching paths. Asserting about the source would prove the
string exists, not that a photograph moved.
"""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

from PIL import Image
from playwright.sync_api import Page, expect

#: 2014-06-17 05:33:20 UTC. The date lives ONLY here - the jpeg bytes carry no EXIF at all.
_SIDECAR = json.dumps({"photoTakenTime": {"timestamp": "1403000000"}}).encode()


def _part(directory: Path, number: int, entries: dict[str, bytes]) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"takeout-20260801T000000Z-{number:03d}.zip"
    with zipfile.ZipFile(path, "w") as archive:
        for name, data in entries.items():
            archive.writestr(name, data)
    return path


def _jpeg(seed: int) -> bytes:
    """⚠ **A REAL jpeg, and the first fixture here was not.**

    `b"\xff\xd8" + padding` looks like one to `discover` and is refused by `exiftool`, so an
    applied import reported *"0 imported, 1 could not be imported"* - the bake is what reads the
    file, and only an APPLY reaches it. The archive-ingest suite gets away with the fake because
    it stops at the preview. Pillow writes no EXIF unless asked, so the date still exists nowhere
    but the sidecar, which is the property these tests turn on.
    """
    buffer = io.BytesIO()
    Image.new("RGB", (64, 64), (seed * 37 % 256, seed * 11 % 256, 90)).save(
        buffer, "JPEG", quality=92
    )
    return buffer.getvalue()


def _export(source: Path, count: int = 3, *, parts: int = 1) -> None:
    """A Takeout shaped like a real one: a photo and its sidecar, split across archives.

    Entries are accumulated per part before anything is written - a zip is created whole, so
    writing part 1 twice replaces it and silently drops every photo but the last.
    """
    folder = "Takeout/Google Photos/Photos from 2014"
    by_part: dict[int, dict[str, bytes]] = {n: {} for n in range(1, parts + 1)}
    for i in range(count):
        entries = by_part[(i % parts) + 1]
        entries[f"{folder}/IMG_{i:04d}.jpg"] = _jpeg(i + 1)
        entries[f"{folder}/IMG_{i:04d}.jpg.json"] = _SIDECAR
    for number, entries in by_part.items():
        _part(source, number, entries)


def _imported(destination: Path) -> list[Path]:
    """What landed in the library - never the staging tree, which is the unpack's own product."""
    return sorted(
        p for p in destination.rglob("*.jpg") if p.is_file() and ".truestill-staging" not in p.parts
    )


def _preview(ui: Page, source: Path, destination: Path) -> None:
    ui.click('button[data-screen="import"]')
    ui.fill("#rc-takeout", str(source))
    ui.fill("#rc-dest", str(destination))
    ui.click("#rc-preview")


def _apply(ui: Page) -> None:
    ui.fill("[data-typed-confirm]", "import")
    ui.click("[data-typed-go]")


def test_a_folder_of_archives_is_imported_from_its_unpacked_tree(ui: Page, tmp_path: Path) -> None:
    """⚠ **THE DEFECT, CLICKED.** Preview, unpack, type the word, import - and then count the
    files. Before the handover the run received the `.zip` path and reported "0 imported" while
    the preview above it promised three."""
    source, destination = tmp_path / "src", tmp_path / "dest"
    _export(source, 3)

    _preview(ui, source, destination)
    ui.click("[data-testid='rc-unpack']")
    expect(ui.locator("[data-testid='rc-summary']")).to_be_visible(timeout=60_000)
    _apply(ui)

    expect(ui.locator("[data-testid='rc-done']")).to_be_visible(timeout=60_000)
    assert len(_imported(destination)) == 3, "the run was handed the archive path, not the tree"


def test_the_completion_states_how_many_dates_were_rescued(ui: Page, tmp_path: Path) -> None:
    """The row that proves the feature worked. The jpegs carry no EXIF; the date exists only in
    the sidecar JSON, so a non-zero count here cannot have come from the files."""
    source, destination = tmp_path / "src", tmp_path / "dest"
    _export(source, 2)

    _preview(ui, source, destination)
    ui.click("[data-testid='rc-unpack']")
    expect(ui.locator("[data-testid='rc-summary']")).to_be_visible(timeout=60_000)
    _apply(ui)

    tally = ui.locator("[data-testid='rc-done-tally']")
    expect(tally).to_be_visible(timeout=60_000)
    expect(tally).to_contain_text("dates rescued from the export")
    assert tally.get_attribute("data-imported") == "2"


def test_the_repeats_are_explained_before_the_word_is_typed(ui: Page, tmp_path: Path) -> None:
    """⚠ **The fear people arrive with, answered where they decide.** An export holds the same
    photo once per album; a user who does not know Truestill collapses them is deciding whether to
    let something duplicate their library. It must be readable BEFORE the confirm, not after."""
    source, destination = tmp_path / "src", tmp_path / "dest"
    _export(source, 2)

    _preview(ui, source, destination)
    ui.click("[data-testid='rc-unpack']")
    expect(ui.locator("[data-testid='rc-summary']")).to_be_visible(timeout=60_000)

    note = ui.locator("[data-testid='rc-repeats']")
    expect(note).to_be_visible()
    expect(note).to_contain_text("same photo once for every album")
    expect(note).to_contain_text("Only one copy of each is kept")
    # It is INSIDE the confirm block, so it cannot be scrolled away from the decision it informs.
    assert ui.locator("#rc-confirm [data-testid='rc-repeats']").count() == 1
    expect(ui.locator("[data-typed-go]")).to_be_disabled()

    # ⚠ **AND IT IS MEASURED, because `.k` is a measure class that does nothing outside a card.**
    # Measured at 944px in a 1280px window before `.confirm-block` existed, against 622px after -
    # the cap is the whole of what `.k` carries, and the note was silently getting none of it.
    # Asserted against its own container rather than a pixel count, which a wider monitor moves.
    note_box = note.bounding_box()
    host_box = ui.locator("#rc-confirm").bounding_box()
    assert note_box is not None
    assert host_box is not None
    assert note_box["width"] < host_box["width"] * 0.9, (
        f"the note runs {note_box['width']:.0f}px of a {host_box['width']:.0f}px block, uncapped"
    )


def test_the_two_confirms_are_different_controls(ui: Page, tmp_path: Path) -> None:
    """⚠ **They shared an `id` until 2026-09-12**, so `document.getElementById` answered with
    whichever came first in the document and the unpack button shadowed the apply host. It worked
    by the order the two happened to be written in. One id, one control."""
    source, destination = tmp_path / "src", tmp_path / "dest"
    _export(source, 1)

    _preview(ui, source, destination)
    expect(ui.locator("#rc-unpack")).to_be_visible(timeout=60_000)

    assert ui.locator("#rc-unpack").count() == 1
    assert ui.locator("#rc-confirm").count() == 1
    ui.click("#rc-unpack")
    expect(ui.locator("[data-testid='rc-summary']")).to_be_visible(timeout=60_000)
    # The unpack button is gone with the card that held it; the apply host is the only one left.
    assert ui.locator("#rc-unpack").count() == 0
    expect(ui.locator("#rc-confirm [data-typed-confirm]")).to_be_visible()


# ------------------------------------------------------- a real Takeout arrives in many archives


def test_five_archives_pointed_at_by_their_folder_all_arrive(ui: Page, tmp_path: Path) -> None:
    """A real Takeout is 10 GB a part, so five is the ordinary case rather than the edge one."""
    source, destination = tmp_path / "src", tmp_path / "dest"
    _export(source, 10, parts=5)
    assert len(list(source.glob("*.zip"))) == 5, "the fixture is not a multi-part export"

    _preview(ui, source, destination)
    ui.click("[data-testid='rc-unpack']")
    expect(ui.locator("[data-testid='rc-summary']")).to_be_visible(timeout=60_000)
    _apply(ui)

    expect(ui.locator("[data-testid='rc-done']")).to_be_visible(timeout=60_000)
    assert len(_imported(destination)) == 10, "parts were dropped between the folder and the run"


def test_pointing_at_one_part_still_imports_the_whole_export(ui: Page, tmp_path: Path) -> None:
    """⚠ **EVERY GUIDE ON THE INTERNET SAYS `takeout-*.zip`, so people point at one part.**

    `archives_at` answers a FILE with its siblings of the same format, deliberately: forgetting a
    part would not fail, it would succeed and quietly leave those photographs undated. The user
    never enumerates parts on either surface. Asserted through the screen, because that promise is
    only worth anything if the path the box accepts reaches it.
    """
    source, destination = tmp_path / "src", tmp_path / "dest"
    _export(source, 10, parts=5)
    one_of_five = sorted(source.glob("*.zip"))[2]

    _preview(ui, one_of_five, destination)
    ui.click("[data-testid='rc-unpack']")
    expect(ui.locator("[data-testid='rc-summary']")).to_be_visible(timeout=60_000)
    _apply(ui)

    expect(ui.locator("[data-testid='rc-done']")).to_be_visible(timeout=60_000)
    assert len(_imported(destination)) == 10, "only the part the user named was imported"


def test_the_import_says_what_it_is_doing_while_it_does_it(ui: Page, tmp_path: Path) -> None:
    """⚠ **THE PHASE WORDING WAS DEAD CODE, and only watching a run found it.**

    `rcRun` emptied the confirm block before starting, so `runJob` had no button, `setStatus`
    wrote nowhere, and three carefully chosen phase labels reached no screen at all. Nothing went
    red: a label nobody reads still passes every assertion about the numbers.

    This is the longest operation in the product - "insanely slow" is the title of immich-go's
    most-read issue, written by a user counting timestamps - so silence is the failure mode.
    """
    source, destination = tmp_path / "src", tmp_path / "dest"
    _export(source, 120, parts=2)

    _preview(ui, source, destination)
    ui.click("[data-testid='rc-unpack']")
    expect(ui.locator("[data-testid='rc-summary']")).to_be_visible(timeout=60_000)
    ui.fill("[data-typed-confirm]", "import")
    trigger = ui.locator("[data-typed-go]")
    ui.click("[data-typed-go]")

    # The anchor, and it is the regression itself: a button that is being driven at all.
    expect(trigger).to_have_attribute("data-busy", "1", timeout=10_000)

    # Read through `evaluate`, not `inner_text`: the button is removed the instant the run ends,
    # and a `count()` that is true can be false again before the text arrives - which raised a
    # TimeoutError here under load. One synchronous DOM read cannot lose that race.
    seen: set[str] = set()
    while not ui.locator("[data-testid='rc-done']").count():
        said = ui.evaluate(
            "() => { const b = document.querySelector('[data-typed-go]');"
            " return b ? b.textContent.replace(/\\s+/g, ' ').trim() : ''; }"
        )
        if said:
            seen.add(said)
        ui.wait_for_timeout(40)
    expect(ui.locator("[data-testid='rc-done']")).to_be_visible(timeout=60_000)

    said = " | ".join(sorted(seen))
    assert any(w in said for w in ("Reading photos", "Checking for duplicates", "Copying")), (
        f"the run named no phase while it ran; the button only ever said: {said}"
    )
    assert "Import them" not in seen, "the button never changed, so nothing was driving it"


def test_a_finished_import_takes_its_unpacked_copy_with_it(ui: Page, tmp_path: Path) -> None:
    """⚠ **THE 200 GB.** Until 2026-09-12 a successful import left a second full copy of the
    export on the user's photo drive, where no OS cleaner will ever reach it, and the card said
    nothing. `(aht)`'s *"untidiness, not a disk a user runs out of"* was written about a preview.

    Clicked, and asserted on the bytes: the tree has to exist after the unpack, or the deletion
    afterwards would prove nothing.
    """
    source, destination = tmp_path / "src", tmp_path / "dest"
    _export(source, 6)
    staging = destination / ".truestill-staging"

    _preview(ui, source, destination)
    ui.click("[data-testid='rc-unpack']")
    expect(ui.locator("[data-testid='rc-summary']")).to_be_visible(timeout=60_000)
    assert [p for p in staging.rglob("*") if p.is_file()], "the unpack staged nothing"

    _apply(ui)
    expect(ui.locator("[data-testid='rc-done']")).to_be_visible(timeout=60_000)

    assert len(_imported(destination)) == 6, "nothing was imported, so deleting staging is wrong"
    assert [p for p in staging.rglob("*") if p.is_file()] == []
    expect(ui.locator("[data-testid='rc-staging']")).to_have_count(0)


def test_a_plain_folder_import_says_nothing_about_staging(ui: Page, tmp_path: Path) -> None:
    """The anchor: an already-extracted folder unpacks nothing, so there is no copy to name and
    the card must not invent one. A sentence about a folder that does not exist is worse than
    the silence it replaced."""
    source, destination = tmp_path / "Takeout" / "Photos from 2014", tmp_path / "dest"
    source.mkdir(parents=True)
    for i in range(3):
        (source / f"IMG_{i}.jpg").write_bytes(_jpeg(i + 1))
        (source / f"IMG_{i}.jpg.json").write_bytes(_SIDECAR)

    _preview(ui, tmp_path / "Takeout", destination)
    expect(ui.locator("[data-testid='rc-summary']")).to_be_visible(timeout=60_000)
    _apply(ui)

    expect(ui.locator("[data-testid='rc-done']")).to_be_visible(timeout=60_000)
    assert not (destination / ".truestill-staging").exists()
    expect(ui.locator("[data-testid='rc-staging']")).to_have_count(0)


def test_a_cancelled_import_keeps_the_unpacked_copy_and_says_why(ui: Page, tmp_path: Path) -> None:
    """⚠ **THE HALF THAT KEEPS THIS FROM BECOMING GitLab's SECOND MISTAKE.**

    Their cron swept backup temporaries by age and ate imports that were still running. Here the
    rule is ownership, not age - and a run the user stopped keeps its extraction, because
    unpacking a 200 GB export again is not a way to retry. The sentence has to say so, or a user
    looking at a half-finished import and a folder full of files cannot tell which is rubbish.
    """
    source, destination = tmp_path / "src", tmp_path / "dest"
    _export(source, 200, parts=2)
    staging = destination / ".truestill-staging"

    _preview(ui, source, destination)
    ui.click("[data-testid='rc-unpack']")
    expect(ui.locator("[data-testid='rc-summary']")).to_be_visible(timeout=120_000)
    _apply(ui)
    ui.click("#rc-cancel")

    expect(ui.locator("[data-testid='rc-done']")).to_be_visible(timeout=120_000)
    assert [p for p in staging.rglob("*") if p.is_file()], "the cancel threw the extraction away"

    note = ui.locator("[data-testid='rc-staging']")
    expect(note).to_be_visible()
    expect(note).to_contain_text(str(staging))
    expect(note).to_contain_text("kept because this run did not finish")
