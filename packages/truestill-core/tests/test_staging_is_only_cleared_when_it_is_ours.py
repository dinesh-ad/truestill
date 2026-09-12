"""`clear_staging` removes a tree this product made, and refuses everything else. `(aht)`.

⚠ **`staging_root` IS A STRING OUT OF A FILE ON A DRIVE ANYONE CAN WRITE.** A journal naming
`/home/you/Photos` is two lines in a text editor, and the only thing between that and
`shutil.rmtree` is `is_our_staging`. So the refusals are tested as hard as the removal, and each
one asserts **the directory still exists** rather than just that the call returned False - a
guard that only reads the return value would pass on a function that deleted and then said no.
"""

from __future__ import annotations

import json
from pathlib import Path

from truestill_core.archive_extract import (
    STAGING_DIRNAME,
    StagingRecord,
    clear_staging,
    is_our_staging,
    pending_staging,
)


def _journalled(destination: Path, stem: str = "part1") -> StagingRecord:
    """A staging tree in exactly the shape `_write_journal` writes one."""
    root = destination / STAGING_DIRNAME
    tree = root / stem
    (tree / "Takeout").mkdir(parents=True)
    (tree / "Takeout" / "IMG_0001.jpg").write_bytes(b"\xff\xd8photo")
    journal = root / f"{stem}.json"
    journal.write_text(json.dumps({"staging_root": str(tree), "sources": [f"{stem}.zip"]}))
    return pending_staging(destination)[0]


def test_a_tree_this_product_made_is_removed(tmp_path: Path) -> None:
    """The positive anchor. Without it every refusal below could be satisfied by a no-op."""
    record = _journalled(tmp_path / "dest")

    assert clear_staging(record) is True
    assert not record.staging_root.exists()
    assert not record.journal_path.exists()
    assert pending_staging(tmp_path / "dest") == []


def test_a_journal_pointing_at_a_users_own_folder_is_refused(tmp_path: Path) -> None:
    """⚠ **THE ONE THAT MATTERS.** The payload is edited to name a real folder of photographs
    outside the staging directory. Nothing is removed and the folder is still there."""
    destination = tmp_path / "dest"
    record = _journalled(destination)
    photos = tmp_path / "Photos"
    photos.mkdir()
    (photos / "wedding.jpg").write_bytes(b"\xff\xd8irreplaceable")
    record.journal_path.write_text(json.dumps({"staging_root": str(photos), "sources": []}))
    tampered = pending_staging(destination)[0]

    assert is_our_staging(tampered) is False
    assert clear_staging(tampered) is False
    assert (photos / "wedding.jpg").exists(), "a hand-edited journal deleted a user's photographs"


def test_a_symlink_out_of_the_staging_directory_is_refused(tmp_path: Path) -> None:
    """Resolved before comparing, so a tree that is a doorway to somewhere else is refused
    rather than followed. Containment on the spelling alone would pass this."""
    destination = tmp_path / "dest"
    record = _journalled(destination)
    photos = tmp_path / "Photos"
    photos.mkdir()
    (photos / "wedding.jpg").write_bytes(b"\xff\xd8irreplaceable")
    link = destination / STAGING_DIRNAME / "part2"
    link.symlink_to(photos, target_is_directory=True)
    (destination / STAGING_DIRNAME / "part2.json").write_text(
        json.dumps({"staging_root": str(link), "sources": []})
    )
    through_the_link = next(r for r in pending_staging(destination) if r.staging_root == link)

    assert clear_staging(through_the_link) is False
    assert (photos / "wedding.jpg").exists(), "the symlink was followed out of staging"
    assert record.staging_root.exists(), "an unrelated real tree was removed"


def test_a_parent_traversal_is_refused(tmp_path: Path) -> None:
    """`..` in the payload, which resolves above the staging directory."""
    destination = tmp_path / "dest"
    _journalled(destination)
    (destination / "Saved").mkdir()
    (destination / "Saved" / "organized.jpg").write_bytes(b"\xff\xd8organized")
    journal = destination / STAGING_DIRNAME / "part1.json"
    journal.write_text(
        json.dumps({"staging_root": str(destination / STAGING_DIRNAME / ".." / "Saved")})
    )

    assert clear_staging(pending_staging(destination)[0]) is False
    assert (destination / "Saved" / "organized.jpg").exists(), "traversal reached the library"


def test_the_staging_directory_itself_is_refused(tmp_path: Path) -> None:
    """A payload naming the container rather than one tree inside it. Removing it would take
    every other export's tree with it, and the journals that attribute them."""
    destination = tmp_path / "dest"
    _journalled(destination)
    root = destination / STAGING_DIRNAME
    (root / "part1.json").write_text(json.dumps({"staging_root": str(root)}))

    assert clear_staging(pending_staging(destination)[0]) is False
    assert root.exists()


def test_a_journal_outside_a_staging_directory_is_refused(tmp_path: Path) -> None:
    """The other structural half: the journal itself must have been found where we write them.
    A record built by hand, pointing at a tidy-looking tree, is still not ours."""
    elsewhere = tmp_path / "Downloads"
    tree = elsewhere / "part1"
    tree.mkdir(parents=True)
    (tree / "IMG.jpg").write_bytes(b"\xff\xd8photo")
    journal = elsewhere / "part1.json"
    journal.write_text(json.dumps({"staging_root": str(tree)}))

    record = StagingRecord(journal_path=journal, staging_root=tree, source_names=())

    assert clear_staging(record) is False
    assert tree.exists()
