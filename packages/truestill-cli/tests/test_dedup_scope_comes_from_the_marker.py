"""(aek) Moving the marker WRITE behind the space check must not restore `(aei)`.

`(aei)` is the soak's headline: organize into a fresh second drive copied **nothing**, registered a
0-file drive and reported success, because it deduped against the whole catalog instead of the
destination. The repair made the destination's identity an **input** to the dedup decision, and
`service/organize.py` carries a warning that moving registration later "would restore the defect".

`(aek)` moves the marker write later. This file is the proof that it does not, and it asserts the
mechanism rather than the outcome so it cannot pass for a coincidental reason:

**The uuid used for scoping now comes from the MARKER, not from registration** - and
`_local_drive_marker` reads that marker off disk before the pipeline starts, with no write. So:

| destination | scope before the move | scope after |
|---|---|---|
| already marked | the real uuid -> real `file_copies` | identical, read from the same marker |
| no marker | a freshly minted uuid -> `{}` (a new drive holds nothing) | `None` -> `{}` |
| rclone | `None` -> catalog-global | identical |

The middle row is the load-bearing one: registering a brand-new drive and not registering it at
all produce the **same** dedup input, which is why the write is free to move and the decision is
not.

`test_a_second_destination_receives_the_files.py` is `(aei)`'s own pin and must stay green
unedited; if it ever needs editing to accommodate this, the move is wrong.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from PIL import Image
from truestill_cli.cli import _shas_on_destination, main
from truestill_core.catalog import Catalog
from truestill_core.drive import create_marker, read_marker

_EXIFTOOL = pytest.mark.skipif(shutil.which("exiftool") is None, reason="exiftool not installed")


class _Args:
    def __init__(self, *, rclone: bool = False) -> None:
        self.rclone = rclone


def _source(tmp_path: Path, name: str, count: int = 3) -> Path:
    """Photos that are distinguishable to a PERCEPTUAL hash, not merely to `==`.

    Three near-identical solid colours are exact-distinct and perceptual near-duplicates, so the
    run legitimately skips two of them and a copy count then measures the dedup index rather than
    the scope under test. A count of one is not a fixture (ENGINEERING_STANDARD.md §4,
    seventeenth member) and neither is a count of three that collapses to one.
    """
    src = tmp_path / name
    src.mkdir()
    for i in range(count):
        image = Image.new("RGB", (64, 64), (0, 0, 0))
        for x in range(64):
            for y in range(64):
                image.putpixel((x, y), ((x * (i + 1)) % 256, (y * (i + 3)) % 256, (x ^ y) % 256))
        image.save(src / f"photo{i}.jpg", "JPEG", quality=95)
    return src


def test_an_unregistered_destination_and_a_freshly_registered_one_scope_alike(
    tmp_path: Path,
) -> None:
    """The middle row, asserted directly on the function that answers it.

    A minted uuid has no `file_copies` rows, and `None` is answered with `{}` for a local
    destination - *it provably holds no recorded copies*. Two routes, one answer, which is what
    makes moving the write between them a no-op for dedup.
    """
    db = tmp_path / "c.sqlite"
    root = tmp_path / "fresh"
    root.mkdir()
    with Catalog(db) as catalog:
        before = _shas_on_destination(_Args(), None, catalog)
        minted = create_marker(root, label="Fresh")
        catalog.upsert_drive(uuid=minted.uuid, label=minted.label)
        after = _shas_on_destination(_Args(), minted.uuid, catalog)

    assert before == {}
    assert after == {}
    assert before == after, "registering a NEW drive changed the dedup scope; the move is unsafe"


def test_an_rclone_destination_still_scopes_against_the_whole_catalog(tmp_path: Path) -> None:
    """The third row, and the one that must NOT become `{}`.

    An rclone remote is never drive-tracked, so `file_copies` can say nothing about it and the
    catalog-global answer is the only one available. Conflating it with "nothing is here" would
    re-copy the whole remote every run - the opposite defect from `(aei)`, and the reason
    `_shas_on_destination` is three-valued rather than two.
    """
    db = tmp_path / "c.sqlite"
    with Catalog(db) as catalog:
        assert _shas_on_destination(_Args(rclone=True), None, catalog) is None


@_EXIFTOOL
def test_a_marked_destination_still_scopes_against_what_that_drive_holds(tmp_path: Path) -> None:
    """The first row, end to end: a re-run into the SAME drive still skips what is on it.

    Asserted through the CLI rather than the helper, because the claim is about where the uuid
    comes from now - the marker on disk, read before the pipeline runs - and only a real run
    exercises that path.
    """
    src = _source(tmp_path, "src")
    dest = tmp_path / "drive"
    db = tmp_path / "c.sqlite"

    assert main(["organize", str(src), str(dest), "--apply", "--db", str(db)]) == 0
    marker = read_marker(dest)
    assert marker is not None
    with Catalog(db) as catalog:
        first = _shas_on_destination(_Args(), marker.uuid, catalog)
    assert len(first) == 3, "the first run recorded nothing to scope against"

    # Second run, same drive: everything is already there, so nothing is written again.
    assert main(["organize", str(src), str(dest), "--apply", "--db", str(db)]) == 0
    with Catalog(db) as catalog:
        second = _shas_on_destination(_Args(), marker.uuid, catalog)
    assert second == first, "a re-run into the same drive changed what the drive is said to hold"


@_EXIFTOOL
def test_a_second_drive_still_receives_every_file(tmp_path: Path) -> None:
    """`(aei)` itself, through the CLI, after the move. The regression this file exists to forbid.

    Organizing the same source into a SECOND, fresh destination must copy everything again - the
    files are on drive one and drive two holds nothing. Before `(aei)` this copied zero and
    reported success.
    """
    src = _source(tmp_path, "src")
    one = tmp_path / "drive-one"
    two = tmp_path / "drive-two"
    db = tmp_path / "c.sqlite"

    assert main(["organize", str(src), str(one), "--apply", "--db", str(db)]) == 0
    assert main(["organize", str(src), str(two), "--apply", "--db", str(db)]) == 0

    second = read_marker(two)
    assert second is not None
    with Catalog(db) as catalog:
        on_two = {str(r["sha256"]) for r in catalog.copies_on_drive(second.uuid)}
    assert len(on_two) == 3, f"the second drive received {len(on_two)} of 3 files"
    assert sum(1 for _ in two.rglob("*.jpg")) == 3
