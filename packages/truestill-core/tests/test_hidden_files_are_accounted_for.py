"""A hidden file or folder is skipped, and now it is also **counted and named**.

**Two different silences, and the second is the one that matters.**

* A dot-file was skipped with no bucket to land in - `.picasa.ini` is real user metadata and it
  vanished from the report entirely.
* A hidden *directory* was pruned before the walk descended, so **a user with photos inside one
  saw nothing at all**: not a count, not a name, not a warning. Their photos were simply absent
  from a census that claims to say what is in a folder.

Neither is a policy problem. Skipping remains right - `.Trash`, `.thumbnails`, `.git`,
`.Spotlight-V100` and AppleDouble `._` files are exactly what a photo tool should not sweep into
someone's library, and a flag that pulled all of them in would be a footgun aimed at the library
the product exists to protect. **The defect is the silence**, which is `(aac)`'s shape on a third
surface, so this commit fixes the accounting and leaves the policy alone.

**Files are counted; folders are named without a count.** That asymmetry is not an oversight and
is already the established convention here - `cli._print_unreadable` states it: *"for a folder
the number of files inside is exactly what could not be read, so printing one would invent the
missing figure"*. The walk never descends into a hidden folder, so Truestill genuinely does not
know what is in it, and any number would be fabricated. It costs nothing either: reporting the
folder is free, while counting its contents would mean walking `.git` on every scan.

**Our own marker is named separately.** `.truestill-drive.json` is hidden too, and folding it
into the user's tally would make every scan of an organized drive report a hidden file the user
did not create and cannot act on. It is counted under its own label so the arithmetic still
reconciles and nobody has to work out which one was ours.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from truestill_core.drive import LEGACY_MARKER_NAMES, MARKER_NAME
from truestill_core.organizer import (
    HIDDEN_LABEL,
    TRUESTILL_MARKER_LABEL,
    inventory_source,
    scan_source,
)


@pytest.fixture
def source(tmp_path: Path) -> Path:
    """A folder shaped like a real one: visible photos, user metadata, and a hidden album."""
    root = tmp_path / "pics"
    (root / "sub").mkdir(parents=True)
    (root / "a.jpg").write_bytes(b"a")
    (root / "sub" / "b.jpg").write_bytes(b"b")
    (root / ".picasa.ini").write_text("[Picasa]\n")  # real user metadata, not a photo
    (root / ".DS_Store").write_bytes(b"\x00")
    hidden_album = root / ".old photos"
    hidden_album.mkdir()
    (hidden_album / "c.jpg").write_bytes(b"c")
    (hidden_album / "d.jpg").write_bytes(b"d")
    return root


# --- the accounting the report was missing ------------------------------------------------------


def test_hidden_files_are_still_skipped(source: Path) -> None:
    """The policy does not change. A dot-file is not a photo and is not organized."""
    scan = scan_source(source)

    assert [p.name for p in scan.media] == ["a.jpg", "b.jpg"]
    assert not any(p.name.startswith(".") for p in scan.media)


def test_a_hidden_file_is_counted_by_its_name(source: Path) -> None:
    """`.picasa.ini` used to vanish. It is user metadata and it belongs in the tally.

    **By name, not by extension**, which is not a detail: `.DS_Store` has no suffix at all by
    `Path`'s rules, so an extension census reports it as `(no ext)` and tells the reader
    nothing. The name is the thing a person recognises - and recognising `.picasa.ini` as
    their own Picasa metadata is the difference between a useful row and a puzzle.
    """
    inventory = inventory_source(source)

    hidden = inventory.skipped[HIDDEN_LABEL]
    assert hidden == {".picasa.ini": 1, ".DS_Store": 1}, hidden


def test_a_hidden_folder_is_named_and_deliberately_not_counted(source: Path) -> None:
    """**The case that matters: photos inside a hidden folder.**

    Named, so the user learns they exist. Without a file count, because the walk never went in
    and any number would be invented - the same rule `unreadable_dirs` already follows.
    """
    scan = scan_source(source)

    assert [p.name for p in scan.hidden_dirs] == [".old photos"]
    assert not any("c.jpg" in str(p) for p in scan.hidden_dirs), "contents must not be enumerated"


def test_the_walk_still_does_not_descend_into_a_hidden_folder(source: Path) -> None:
    """Naming the folder must not have turned into walking it.

    On a real tree that would mean descending `.git` and `.cache` on every scan - the cost this
    prune exists to avoid, and a regression no count-based assertion would reveal.
    """
    scan = scan_source(source)

    inside = [p for group in (scan.media, scan.documents, scan.unrecognized) for p in group]
    assert not any(".old photos" in str(p) for p in inside)


# --- our own marker is not the user's file -------------------------------------------------------


@pytest.mark.parametrize("marker", [MARKER_NAME, *LEGACY_MARKER_NAMES])
def test_our_marker_is_named_apart_from_the_user_hidden_files(marker: str, source: Path) -> None:
    """**"One of the hidden files is ours" is what makes a count confusing.**

    Folded into the tally, every scan of an organized drive reports a hidden file the user did
    not create and cannot act on. Dropped silently, the number stops matching what `ls -a`
    shows. Counted under its own label, both problems go away. The legacy `.vaeon-drive.json`
    is ours too - a drive written before the rename is still a Truestill drive.
    """
    (source / marker).write_text("{}")
    inventory = inventory_source(source)

    assert inventory.skipped[TRUESTILL_MARKER_LABEL] == {marker: 1}
    assert marker not in inventory.skipped[HIDDEN_LABEL]
    assert sum(inventory.skipped[HIDDEN_LABEL].values()) == 2, "the user's two, and only those"


# --- reconciliation: no arithmetic required -----------------------------------------------------


def test_every_file_on_disk_lands_in_exactly_one_bucket(source: Path) -> None:
    """**The whole point: a user must not have to do arithmetic to notice a skip.**

    Every non-hidden-folder entry is either media, a document, unrecognized, an exiftool backup,
    or hidden. Nothing falls between the buckets, which is what made a hidden file invisible
    rather than merely uninteresting.
    """
    (source / ".truestill-drive.json").write_text("{}")
    scan = scan_source(source)

    on_disk = {p for p in source.iterdir() if p.is_file()}
    on_disk |= {p for p in (source / "sub").iterdir() if p.is_file()}
    bucketed = set(scan.media) | set(scan.documents) | set(scan.unrecognized)
    bucketed |= set(scan.exiftool_backups) | set(scan.hidden) | set(scan.markers)

    assert on_disk == bucketed, f"unbucketed: {on_disk ^ bucketed}"


def test_a_folder_with_nothing_hidden_grows_no_hidden_entries(tmp_path: Path) -> None:
    """Cry-wolf: the ordinary folder must not sprout an empty bucket explaining what is absent."""
    plain = tmp_path / "plain"
    plain.mkdir()
    (plain / "a.jpg").write_bytes(b"a")

    inventory = inventory_source(plain)

    assert not inventory.skipped.get(HIDDEN_LABEL)
    assert not inventory.skipped.get(TRUESTILL_MARKER_LABEL)
    assert not scan_source(plain).hidden_dirs
