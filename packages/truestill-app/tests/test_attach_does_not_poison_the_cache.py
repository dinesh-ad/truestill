"""Attaching a drive must not cost its files their near-duplicate detection.

**Measured before it was fixed**, on a scratch drive holding one photograph saved twice at
different JPEG quality - different bytes, perceptual distance 4 against a threshold of 5:

    without the attach   files=2  new_unique=1  near_dup=1
    after the attach     files=2  new_unique=2  near_dup=0

`attach_drive` opened `HashCache.beside(db)` **writable** while `_copy_hash` computes only
SHA-256, so every file with no prior row got `perceptual=None` - which the cache cannot tell
from *"not an image"*. `HashCache.get` has `need_sha` and **no `need_perceptual`**, so a later
full pass took that row as a hit and never perceptually hashed the file.

`scan.compute_hashes` already refuses exactly this pairing with a `ValueError` (§8, *"Refused
rather than documented"*). `_copy_hash` calls `cache.put` directly and walked around the door.

The user-visible shape is what makes it worth a test rather than a note: no error, no count, no
degraded-mode notice. Look-alikes simply stop being found.
"""

from __future__ import annotations

import random
from pathlib import Path

import pytest
from PIL import Image
from truestill_app.service import organize_preview
from truestill_app.service.drives import attach_drive
from truestill_core.catalog import Catalog
from truestill_core.drive import create_marker
from truestill_core.hash_cache import HashCache, cache_path_for
from truestill_core.hashing import DEFAULT_PHASH_THRESHOLD, perceptual_hash, sha256_file

_UUID = "DRIVE-CACHE-1"


def _twins(folder: Path) -> None:
    """One photograph saved twice at different quality: same picture, different bytes.

    Noise rather than a flat colour - a flat image dHashes to all zeros, which would make every
    fixture a near-duplicate of every other and the assertion meaningless.
    """
    folder.mkdir(parents=True, exist_ok=True)
    rng = random.Random(7)
    image = Image.new("RGB", (128, 128))
    image.putdata(
        [(rng.randrange(256), rng.randrange(256), rng.randrange(256)) for _ in range(128 * 128)]
    )
    image.save(folder / "twin-a.jpg", "JPEG", quality=95)
    image.save(folder / "twin-b.jpg", "JPEG", quality=30)


@pytest.fixture
def drive(tmp_path: Path) -> tuple[Path, Path]:
    """A registered drive holding a near-duplicate pair the catalog knows nothing about."""
    root, db = tmp_path / "drive", tmp_path / "c.sqlite"
    root.mkdir(parents=True)
    create_marker(root, label="Scratch", uuid=_UUID)
    _twins(root / "Camera")
    with Catalog(db) as catalog:
        catalog.upsert_drive(uuid=_UUID, label="Scratch")
    return root, db


def test_the_fixture_really_is_a_near_duplicate_pair(drive: tuple[Path, Path]) -> None:
    """Validated against the thing it is meant to detect, or every assertion below is empty.

    A pair that is not perceptually close would give `near_dup == 0` for reasons having nothing
    to do with the cache, and the guard would pass against the defect it exists to catch.
    """
    root, _db = drive
    a, b = root / "Camera/twin-a.jpg", root / "Camera/twin-b.jpg"
    assert sha256_file(a) != sha256_file(b), "the pair is byte-identical: an exact duplicate"
    first, second = perceptual_hash(a), perceptual_hash(b)
    assert first is not None
    assert second is not None
    distance = bin(int(first, 16) ^ int(second, 16)).count("1")
    assert 0 < distance <= DEFAULT_PHASH_THRESHOLD, (
        f"distance {distance} is not a near-duplicate at threshold {DEFAULT_PHASH_THRESHOLD}"
    )


def test_a_preview_finds_the_look_alike_without_an_attach(drive: tuple[Path, Path]) -> None:
    """The control. Without it, the test below cannot tell a fix from a broken fixture."""
    root, db = drive
    summary = organize_preview(root, root.parent / "dest", db)
    assert summary["near_dup"] == 1, summary
    assert summary["new_unique"] == 1, summary


def test_attaching_the_drive_does_not_lose_the_look_alike(drive: tuple[Path, Path]) -> None:
    """THE DEFECT. Same drive, same files - only an attach happened in between.

    A user attaches a drive (the app does it inside every backup) and near-duplicate detection
    silently stops working for everything the attach read.
    """
    root, db = drive
    attach_drive(root, db, write=True)

    summary = organize_preview(root, root.parent / "dest", db)

    assert summary["near_dup"] == 1, (
        f"attaching the drive lost near-duplicate detection for its files: {summary}"
    )
    assert summary["new_unique"] == 1, summary


def test_attach_never_writes_a_row_it_cannot_complete(drive: tuple[Path, Path]) -> None:
    """The rule, asserted directly rather than only through its consequence.

    Stated on the cache rather than on the preview so it still holds if near-duplicate matching
    is ever reworked: a pass that computes one hash and not the other must contribute nothing.
    """
    root, db = drive
    attach_drive(root, db, write=True)

    if not cache_path_for(db).exists():
        return  # nothing was written at all, which is the strongest form of the rule
    with HashCache.beside_readonly(db) as cache:
        for name in ("twin-a.jpg", "twin-b.jpg"):
            path = root / "Camera" / name
            stat = path.stat()
            hit = cache.get(path, stat.st_size, stat.st_mtime_ns, need_sha=False)
            assert hit is None or hit.perceptual is not None, (
                f"{name} has a cached row whose perceptual hash was never computed; "
                "a later run will take it as a hit and skip near-duplicate detection"
            )
