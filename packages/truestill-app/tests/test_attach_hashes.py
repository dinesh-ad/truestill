"""Attach establishes a drive's own copy hashes by reading the drive (condition 2, option b).

**What was wrong.** ``attach_drive`` recorded ``file_copies.copy_sha256`` by copying
``files.copy_sha256`` - a *per-content* column - onto a *per-drive* row. That is sound only while
every copy of a file is byte-identical to every other, which is exactly the premise the Takeout
bake already breaks and date-rescue baking will break again. The first per-drive bake would make
the inherited value a confident lie: verify would compare a baked copy against a hash taken
before the bake and report **corruption on a file truestill itself rewrote**.

**What it does now.** Attach reads each copy on the drive and records what that drive actually
holds. Slower, and the slowness is the point: an attach that guesses is worse than an attach that
takes a while, because the guess is not detectably wrong until a user is told their photo is
damaged. `docs/PERFORMANCE.md` §1.1 carries the measured cost.

**Failure is resumable, never rolled back** - see
:func:`test_a_cancelled_attach_keeps_what_it_finished`.
"""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

import pytest
from truestill_app.service.drives import attach_drive
from truestill_core.catalog import Catalog
from truestill_core.hash_cache import HashCache, cache_path_for
from truestill_core.hashing import sha256_file
from truestill_core.models import FileHashes
from truestill_core.progress import Progress
from truestill_core.verify import CopyStatus, CopyToVerify, verify_copies

#: What the deprecated per-content column claims. Deliberately not the hash of anything on disk,
#: so a test can only pass by reading the drive - inheriting this value fails every assertion.
STALE_PER_CONTENT_HASH = "f" * 64


def _organized_library(db: Path, root: Path, names: tuple[str, ...]) -> dict[str, str]:
    """A library organized *before* its folder was registered: ``files`` rows, no ``file_copies``.

    The ordinary case: the copy is byte-identical to its source, so ``files.sha256`` is the hash
    of the bytes on disk. What is *wrong* here is the deprecated per-content
    ``files.copy_sha256``, set to a value matching nothing - an attach that inherits it rather
    than recording what it read fails every assertion below.

    Returns ``{name: on-disk sha256}``.
    """
    on_disk: dict[str, str] = {}
    with Catalog(db) as catalog:
        for name in names:
            relative = f"Camera/2014/{name}"
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(f"bytes-of-{name}".encode())
            sha = sha256_file(path)
            on_disk[name] = sha
            catalog.record_uploaded(
                source_path=f"/src/{name}",
                original_name=name,
                sha256=sha,
                copy_sha256=STALE_PER_CONTENT_HASH,
                perceptual=None,
                size=path.stat().st_size,
                captured_at="2014-08-20T14:30:00",
                category="Camera",
                relative=relative,
                # No drive_uuid: this is the pre-registration state, so no copy is recorded.
            )
    return on_disk


def _baked_copy(db: Path, root: Path, name: str) -> tuple[str, str]:
    """A Takeout-baked copy: the bytes on the drive are NOT the source bytes.

    This is the case that makes content-matching non-trivial. The copy hashes to its own
    ``copy_sha256``, so an attach that matched only ``files.sha256`` would fail to recognise
    precisely the files the dual-hash rule exists for. Returns ``(source_sha, baked_sha)``.
    """
    relative = f"Camera/2014/{name}"
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(f"baked-bytes-of-{name}".encode())
    baked = sha256_file(path)
    #: The pre-bake source hash. It is the dedup identity and it is deliberately not the hash of
    #: anything on this drive - the bake is what made the copy differ.
    source = "source-only-sha-never-on-disk"
    with Catalog(db) as catalog:
        catalog.record_uploaded(
            source_path=f"/src/{name}",
            original_name=name,
            sha256=source,
            copy_sha256=baked,
            perceptual=None,
            size=path.stat().st_size,
            captured_at="2014-08-20T14:30:00",
            category="Camera",
            relative=relative,
        )
    return source, baked


def _recorded_copies(db: Path) -> dict[str, str | None]:
    """``{relative: copy_sha256}`` as the catalog now holds it."""
    with Catalog(db) as catalog:
        rows: list[sqlite3.Row] = list(
            catalog._conn.execute("SELECT relative, copy_sha256 FROM file_copies")
        )
    return {row["relative"]: row["copy_sha256"] for row in rows}


@pytest.fixture
def library(tmp_path: Path) -> tuple[Path, Path, dict[str, str]]:
    db, root = tmp_path / "c.sqlite", tmp_path / "drive"
    return db, root, _organized_library(db, root, ("a.jpg", "b.jpg", "c.jpg"))


# --- the promise --------------------------------------------------------------------------


def test_attach_records_what_the_drive_actually_holds(
    library: tuple[Path, Path, dict[str, str]],
) -> None:
    """Every recorded copy hash is the hash of the bytes sitting on that drive."""
    db, root, on_disk = library

    result = attach_drive(root, db, write=True)

    assert result.linked == 3
    recorded = _recorded_copies(db)
    assert recorded == {f"Camera/2014/{name}": digest for name, digest in on_disk.items()}


def test_attach_does_not_inherit_the_deprecated_per_content_column(
    library: tuple[Path, Path, dict[str, str]],
) -> None:
    """The defect, stated as its own assertion: no recorded copy carries the inherited value.

    Separate from the test above because they fail differently. That one fails if the hashing is
    wrong; this one fails if the hashing is skipped and the old value copied through - which is
    what a revert would look like.
    """
    db, root, _on_disk = library

    attach_drive(root, db, write=True)

    assert STALE_PER_CONTENT_HASH not in set(_recorded_copies(db).values())


def test_an_attached_drive_then_verifies_clean(
    library: tuple[Path, Path, dict[str, str]],
) -> None:
    """End to end, and the reason this change exists: verify must not cry corruption.

    With the inherited per-content hash these three copies verified as MISMATCH - truestill
    reporting damage on files it had written itself.
    """
    db, root, _on_disk = library
    attach_drive(root, db, write=True)

    with Catalog(db) as catalog:
        uuid = catalog.list_drives()[0]["uuid"]
        copies = [CopyToVerify.from_row(r) for r in catalog.copies_on_drive(uuid)]
    results = verify_copies(copies, root)

    assert [r.status for r in results] == [CopyStatus.VERIFIED] * 3


# --- scale, progress, cancel ----------------------------------------------------------------


def test_attach_reports_the_scale_from_its_first_tick(
    library: tuple[Path, Path, dict[str, str]],
) -> None:
    """A full read must not begin as an unexplained wait: the total is known before the work.

    ``total`` is settled by stat-ing the copies first, so the very first progress event can say
    "1 of 3" rather than counting up to a number the user learns at the end.
    """
    db, root, _on_disk = library
    ticks: list[Progress] = []

    attach_drive(root, db, write=True, progress=ticks.append)

    assert ticks, "a full read of the drive reported no progress at all"
    assert [t.total for t in ticks] == [3, 3, 3]
    assert [t.done for t in ticks] == [1, 2, 3]


def test_a_preview_attach_reports_the_scale_and_hashes_nothing(
    library: tuple[Path, Path, dict[str, str]], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Preview purity (§5): the count is what the user is shown *before* agreeing to the read."""
    db, root, _on_disk = library
    monkeypatch.setattr(
        "truestill_app.service.drives.sha256_file",
        lambda path: pytest.fail(f"a preview read {path}"),
    )

    result = attach_drive(root, db, write=False)

    assert result.linked == 3, "the preview must still say how many files the run will read"
    assert _recorded_copies(db) == {}


def test_a_cancelled_attach_keeps_what_it_finished(
    library: tuple[Path, Path, dict[str, str]],
) -> None:
    """**Resumable, not rolled back** - the decision, with its reason.

    Each recorded copy is independently true: that file was on that drive and hashed to that
    value. A rollback would delete true facts and throw away a read that can cost hours on a
    real drive, to reach a state that is strictly less informative. Nothing was written to the
    *drive* (attach is catalog-only), so there is no half-finished change on disk to undo - the
    only thing a rollback could undo is knowledge.
    """
    db, root, _on_disk = library
    cancel = threading.Event()

    attach_drive(root, db, write=True, progress=lambda _p: cancel.set(), cancel=cancel)

    partial = _recorded_copies(db)
    assert len(partial) == 1, "a cancelled attach should keep exactly the work it completed"

    # ... and the next attach finishes the rest rather than starting over.
    resumed = attach_drive(root, db, write=True)

    assert resumed.linked == 2, "a resumed attach re-did work it had already recorded"
    assert len(_recorded_copies(db)) == 3


# --- the baked copy, which is why matching accepts more than one digest ----------------------


def test_a_baked_copy_is_recognised_by_the_hash_it_actually_has(tmp_path: Path) -> None:
    """A Takeout-baked copy does not hash to ``files.sha256``, and must still be found.

    Matching only the source hash would fail on exactly the files the dual-hash rule exists for -
    the ones truestill itself rewrote. The recorded copy digest is an accepted identity for the
    same content, which is what makes the drive walk work on a baked library.
    """
    db, root = tmp_path / "c.sqlite", tmp_path / "drive"
    source, baked = _baked_copy(db, root, "takeout.jpg")

    result = attach_drive(root, db, write=True)

    assert result.linked == 1, "the baked copy was not recognised"
    assert result.unmatched == 0
    assert _recorded_copies(db) == {"Camera/2014/takeout.jpg": baked}
    with Catalog(db) as catalog:
        assert catalog.copy_relative(source, catalog.list_drives()[0]["uuid"]) is not None


def test_a_baked_copy_then_verifies_clean(tmp_path: Path) -> None:
    """End to end: what attach recorded for a baked copy must satisfy verify, not alarm it."""
    db, root = tmp_path / "c.sqlite", tmp_path / "drive"
    _baked_copy(db, root, "takeout.jpg")
    attach_drive(root, db, write=True)

    with Catalog(db) as catalog:
        uuid = catalog.list_drives()[0]["uuid"]
        copies = [CopyToVerify.from_row(r) for r in catalog.copies_on_drive(uuid)]

    assert [r.status for r in verify_copies(copies, root)] == [CopyStatus.VERIFIED]


# --- the hash cache -------------------------------------------------------------------------


def test_a_re_attach_is_warm(
    library: tuple[Path, Path, dict[str, str]], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Re-attaching an unchanged drive must not re-read it.

    Re-attach is a real path - it happens whenever a drive is registered again after the copies
    were forgotten - and without the cache it would cost a second full read of the whole drive.
    """
    db, root, _on_disk = library
    attach_drive(root, db, write=True)

    with Catalog(db) as catalog:
        catalog._conn.execute("DELETE FROM file_copies")
        catalog._conn.commit()

    reads: list[Path] = []
    real = sha256_file
    monkeypatch.setattr(
        "truestill_app.service.drives.sha256_file",
        lambda path: (reads.append(path), real(path))[1],
    )
    result = attach_drive(root, db, write=True)

    assert result.linked == 3
    assert reads == [], f"a warm re-attach re-read the drive: {reads}"


def test_attach_does_not_evict_a_cached_perceptual_hash(
    library: tuple[Path, Path, dict[str, str]],
) -> None:
    """Cry-wolf half: writing the SHA into the cache must not throw away the expensive half.

    A perceptual hash costs a full image decode (~70 ms/file, `hash_cache` docstring) against
    ~8.5 ms for SHA-256. Storing ``FileHashes(sha256=..., perceptual=None)`` would blank it and
    make the next organize preview pay for a decode attach had no reason to discard.
    """
    db, root, _on_disk = library
    target = root / "Camera/2014/a.jpg"
    stat = target.stat()
    with HashCache(cache_path_for(db)) as cache:
        cache.put(target, stat.st_size, stat.st_mtime_ns, FileHashes(None, "phash-abc"))

    attach_drive(root, db, write=True)

    with HashCache(cache_path_for(db)) as cache:
        hit = cache.get(target, stat.st_size, stat.st_mtime_ns, need_sha=True)
    assert hit is not None, "attach did not record the sha it just computed"
    assert hit.perceptual == "phash-abc", "attach evicted a perceptual hash it did not compute"
