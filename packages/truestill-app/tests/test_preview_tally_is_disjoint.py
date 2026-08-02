"""The preview payload's buckets add up to the files it scanned (`(aac)` residue 1).

The shipped build reported *"organized (unique): 5"* and *"files that could not be read: 2"* for
the same seven files, and the 5 included both: a file with no hash matches nothing, so it read
as new. The user was told two contradictory things about the same photo.

Run against the **real** `organize_preview`, not a hand-built dict, because the defect lived in
the seam between two functions over the same list - `_summarize` counted the buckets and
`_unreadable_files` counted the failures, and nothing made them agree. A test that assembled the
payload itself would have reproduced the agreement it was supposed to check.
"""

from __future__ import annotations

import errno
import random
import shutil
from pathlib import Path
from typing import Any

import pytest
from PIL import Image
from truestill_app.service import organize_preview

pytestmark = pytest.mark.skipif(shutil.which("exiftool") is None, reason="exiftool not installed")


def _jpeg(path: Path, *, seed: int, size: tuple[int, int]) -> None:
    """A perceptually distinct photo.

    Noise, not a solid colour: a flat image dHashes to all zeros, so a set of solid-colour
    fixtures are all near-duplicates of each other and the near-dup bucket swallows the very
    counts this file is asserting.
    """
    rng = random.Random(seed)
    image = Image.new("RGB", size)
    image.putdata(
        [
            (rng.randrange(256), rng.randrange(256), rng.randrange(256))
            for _ in range(size[0] * size[1])
        ]
    )
    image.save(path, "JPEG", quality=95)


def _deny_open(monkeypatch: pytest.MonkeyPatch, *, names: set[str], exc: OSError) -> None:
    """Deny named files at ``Path.open``, which behaves the same on all three CI lanes."""
    real = Path.open

    def fake(self: Path, *args: Any, **kwargs: Any) -> Any:
        if self.name in names:
            raise exc
        return real(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", fake)


def _library(root: Path) -> Path:
    """Four photos: two ordinary, plus a byte-identical pair so one is an exact duplicate."""
    src = root / "src"
    src.mkdir()
    _jpeg(src / "one.jpg", seed=1, size=(64, 64))
    _jpeg(src / "two.jpg", seed=2, size=(80, 48))
    _jpeg(src / "twin-a.jpg", seed=3, size=(72, 72))
    shutil.copyfile(src / "twin-a.jpg", src / "twin-b.jpg")
    return src


def _buckets_sum(summary: dict[str, Any]) -> int:
    return (
        summary["new_unique"]
        + summary["near_dup"]
        + summary["exact_dup"]
        + summary["unreadable_files"]["total"]
    )


def test_the_preview_buckets_sum_to_the_files_it_scanned(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The conservation law over the payload the UI actually consumes.

    This is the test that retires the class. Any future bucket that forgets to be disjoint - a
    "corrupt" count for residue 2, say - breaks this the moment it is added, instead of shipping
    a preview whose numbers cannot be added up.
    """
    src = _library(tmp_path)
    _deny_open(monkeypatch, names={"one.jpg"}, exc=PermissionError(errno.EACCES, "denied"))

    summary = organize_preview(src, tmp_path / "dest", tmp_path / "c.sqlite")

    assert summary["unreadable_files"]["total"] == 1, "fixture check: one file must be unreadable"
    assert _buckets_sum(summary) == summary["files"], (
        f"buckets do not conserve: new_unique={summary['new_unique']} + "
        f"near_dup={summary['near_dup']} + exact_dup={summary['exact_dup']} + "
        f"unreadable={summary['unreadable_files']['total']} != files={summary['files']}. "
        "Every scanned file must be reported in exactly one bucket."
    )


def test_an_unreadable_file_is_not_promised_as_one_that_will_be_organized(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The defect itself: the unreadable file must leave `new_unique`, not merely be named.

    Two denied files, so an off-by-one cannot pass. `new_unique` is what the app renders as
    "new - will be organized" and what feeds the confirm control's count.
    """
    src = _library(tmp_path)
    _deny_open(
        monkeypatch, names={"one.jpg", "two.jpg"}, exc=PermissionError(errno.EACCES, "denied")
    )

    summary = organize_preview(src, tmp_path / "dest", tmp_path / "c.sqlite")

    assert summary["files"] == 4
    assert summary["unreadable_files"]["total"] == 2
    assert summary["new_unique"] == 1, (
        "only twin-a is genuinely new and organizable; twin-b is its exact duplicate and the "
        "two denied files will not be organized at all"
    )
    assert summary["exact_dup"] == 1
    assert _buckets_sum(summary) == 4


def test_an_unreadable_near_duplicate_is_counted_as_unreadable_not_as_a_look_alike(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The precedence rule, end to end through the path that actually produces it.

    An unreadable file normally has no hashes and could only ever be "unique". A **cache hit**
    gives it real ones - `HashCache` keys on size and mtime, and ``stat`` succeeds on a file
    whose bytes cannot be read - so it can genuinely match the perceptual tier while being
    unreadable now. Reporting it as a look-alike would describe it as a routine kept-and-flagged
    file when truestill could not read it at all.

    Two previews against one catalog: the first primes the cache while the pair is readable, the
    second denies one of them.
    """
    src = tmp_path / "src"
    src.mkdir()
    db = tmp_path / "c.sqlite"
    _jpeg(src / "pair-a.jpg", seed=7, size=(96, 96))
    twin = Image.open(src / "pair-a.jpg").copy()
    twin.putpixel((0, 0), (0, 0, 0))  # dHash distance 0, different bytes, different size
    twin.save(src / "pair-b.jpg", "JPEG", quality=95)

    primed = organize_preview(src, tmp_path / "dest", db)
    assert primed["near_dup"] == 1, "fixture check: the pair must register as a near-duplicate"

    _deny_open(monkeypatch, names={"pair-b.jpg"}, exc=PermissionError(errno.EACCES, "denied"))
    summary = organize_preview(src, tmp_path / "dest", db)

    assert summary["unreadable_files"]["total"] == 1
    assert summary["near_dup"] == 0, (
        "the cached perceptual hash still matches, but the file could not be read this time - "
        "unreadable wins, or the same photo is counted in two buckets"
    )
    assert _buckets_sum(summary) == summary["files"] == 2


def test_a_fully_readable_preview_is_unchanged(tmp_path: Path) -> None:
    """Cry-wolf half: the ordinary case must count exactly as it did before this change."""
    src = _library(tmp_path)

    summary = organize_preview(src, tmp_path / "dest", tmp_path / "c.sqlite")

    assert summary["unreadable_files"]["total"] == 0
    assert summary["files"] == 4
    assert summary["new_unique"] == 3
    assert summary["exact_dup"] == 1
    assert _buckets_sum(summary) == 4
