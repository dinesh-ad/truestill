"""A source file that cannot be read is named, not silently dropped (`BACKLOG.md` ``(aac)``).

**The defect.** ``FileHashes(None, None)`` meant two unrelated things: *the size pre-filter
chose not to hash this file* and *we tried to read this file and could not*. Downstream nothing
could tell them apart, so on a **preview** - which attempts no copy and therefore never trips
the run's ``ActionStatus.FAILED`` - a locked or failing file was reported nowhere at all. The
user was told their library was fine.

**Why an explicit ``open`` probe and not a smarter ``perceptual_hash``.** That function already
opens every file, so reading the reason off its exception looks free. It is not: Pillow raises
a plain ``OSError`` for *"image file is truncated"*, a corrupt but perfectly readable JPEG.
Deriving "unreadable" from Pillow's taxonomy would report a corruption problem as a permission
problem - a different fact with a different remedy.
:func:`test_a_corrupt_but_readable_image_is_not_called_unreadable` exists to keep that option
permanently closed.

**Every test here runs on all three CI lanes.** The two that need a file to be unreadable
*inject* the error - one by denying ``Path.open``, one by really deleting the file - rather than
calling ``chmod``, which does not deny the owner on Windows. Only
:func:`test_a_real_chmod_000_file_is_reported` skips, and its whole job is to prove the injected
fixtures correspond to something an operating system actually does. Without it the others would
only prove that the code handles a mock.
"""

from __future__ import annotations

import errno
import os
import sys
from pathlib import Path
from typing import Any

import pytest
from PIL import Image
from truestill_core.hash_cache import HashCache, cache_path_for
from truestill_core.models import UnreadableReason
from truestill_core.scan import compute_hashes


def _jpeg(path: Path, *, colour: str = "red", size: tuple[int, int] = (64, 64)) -> None:
    Image.new("RGB", size, colour).save(path)


def _deny_open(monkeypatch: pytest.MonkeyPatch, *, name: str, exc: OSError) -> None:
    """Make one filename raise on ``Path.open``, on every OS.

    Aimed at ``pathlib.Path.open`` because that is the name both readers of file *contents*
    resolve through - the readability probe and ``hashing.sha256_file``. Pillow reaches the
    bytes through ``builtins.open`` instead, which is deliberate here: it keeps this fixture
    from also silencing the perceptual tier, so a test can hold the two apart.
    """
    real = Path.open

    def fake(self: Path, *args: Any, **kwargs: Any) -> Any:
        if self.name == name:
            raise exc
        return real(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", fake)


def test_an_unreadable_file_is_named_in_a_preview(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The headline case: a denied file carries a reason, and its neighbour is untouched.

    Both files are given the same byte size so the pre-filter demands SHA-256 for each. That
    routes the failure through ``_hash_one``'s own ``except OSError`` - the handler that has
    always existed and has always thrown the reason away.
    """
    good = tmp_path / "holiday.jpg"
    locked = tmp_path / "locked.jpg"
    _jpeg(good, colour="red")
    _jpeg(locked, colour="red")  # identical content -> identical size -> need_sha for both
    assert good.stat().st_size == locked.stat().st_size, "fixture needs a size collision"

    _deny_open(monkeypatch, name="locked.jpg", exc=PermissionError(errno.EACCES, "denied"))
    results = compute_hashes([good, locked])

    assert results[locked].unreadable is UnreadableReason.PERMISSION, (
        "a file that could not be read must say so; FileHashes(None, None) is the same value "
        "the size pre-filter produces for a file it legitimately skipped"
    )
    assert results[good].unreadable is None, "the readable neighbour must not be implicated"
    assert results[good].sha256 is not None, "one bad file must not cost the rest of the batch"


def test_a_unique_size_file_is_probed_even_though_nothing_else_reads_it(tmp_path: Path) -> None:
    """The hole a fix aimed only at ``_hash_one`` would leave open, and the common case.

    A file with a size no other file shares is never SHA-256'd - the pre-filter skips it - so
    ``sha256_file`` is never called and ``_hash_one``'s ``except OSError`` never fires. The only
    thing that touches the bytes is ``perceptual_hash``, and it catches ``OSError`` **itself**
    and returns ``None`` through its normal path. So the failure reached ``_hash_one`` as an
    ordinary "not an image" answer and was indistinguishable from one.

    No mock: the file is really deleted after the plan is made, which is also a real race a
    user can hit by moving files during a long preview.
    """
    kept = tmp_path / "kept.jpg"
    vanishing = tmp_path / "vanishing.jpg"
    _jpeg(kept, colour="red", size=(64, 64))
    _jpeg(vanishing, colour="blue", size=(96, 32))  # a different size, so neither needs a SHA
    assert kept.stat().st_size != vanishing.stat().st_size, "fixture needs unique sizes"

    vanishing.unlink()
    results = compute_hashes([kept, vanishing])

    assert results[vanishing].unreadable is UnreadableReason.MISSING, (
        "a unique-size file is read by nothing but perceptual_hash, which swallows the OSError "
        "itself - so a probe that lives in the worker's handler never sees this file at all"
    )
    assert results[kept].unreadable is None


def test_a_cached_file_that_became_unreadable_is_still_named(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The cache hole, and the reason the probe cannot live inside the worker.

    ``HashCache.get`` keys on size and mtime, both read with ``stat`` - and ``stat`` succeeds on
    a file whose contents cannot be read. So a file that was readable when it was last hashed
    and is unreadable now returns a cache **hit**, never reaches ``_hash_one``, and would be
    missed by any probe placed there. On a repeat preview that is the ordinary path.
    """
    photo = tmp_path / "cached.jpg"
    _jpeg(photo)
    db = tmp_path / "catalog.sqlite"
    stat = photo.stat()

    with HashCache(cache_path_for(db)) as cache:
        cache.put(photo, stat.st_size, stat.st_mtime_ns, compute_hashes([photo])[photo])

    _deny_open(monkeypatch, name="cached.jpg", exc=PermissionError(errno.EACCES, "denied"))
    with HashCache(cache_path_for(db)) as cache:
        hit = cache.get(photo, stat.st_size, stat.st_mtime_ns, need_sha=False)
        assert hit is not None, "fixture is pointless unless the cache really hits"
        results = compute_hashes([photo], cache=cache)

    assert results[photo].unreadable is UnreadableReason.PERMISSION, (
        "the cached hashes are still usable for dedup, but the file cannot be read now and the "
        "copy will fail - a preview that stays silent here is predicting the wrong run"
    )


def test_a_corrupt_but_readable_image_is_not_called_unreadable(tmp_path: Path) -> None:
    """The cry-wolf half, and the test that keeps the cheap shortcut unavailable.

    A truncated JPEG opens fine and decodes badly: ``perceptual_hash`` returns ``None`` because
    Pillow raised ``OSError("image file is truncated")`` inside it. That is a corruption
    problem, not a permission problem, and telling the user to check the file's permissions
    would send them after the wrong thing. Any future refactor that derives readability from
    Pillow's exceptions instead of from ``open`` fails here.
    """
    truncated = tmp_path / "truncated.jpg"
    _jpeg(truncated, size=(256, 256))
    whole = truncated.read_bytes()
    truncated.write_bytes(whole[: len(whole) // 2])

    result = compute_hashes([truncated])[truncated]

    assert result.unreadable is None, (
        "a corrupt file is readable; reporting it as unreadable would name the wrong remedy"
    )
    assert result.perceptual is None, (
        "fixture check: this file must actually defeat the perceptual decoder, or the test "
        "proves nothing about the two being told apart"
    )


def test_the_size_prefilters_legitimate_skip_is_not_called_unreadable(tmp_path: Path) -> None:
    """The original defect stated as a property: the two ``None`` cases are now distinguishable.

    A readable file with a size no other file shares has ``sha256 is None`` on purpose. That
    must never read as a failure - it is the pre-filter working.
    """
    only = tmp_path / "unique.jpg"
    _jpeg(only, size=(40, 70))

    result = compute_hashes([only])[only]

    assert result.sha256 is None, "fixture check: the pre-filter must have skipped this file"
    assert result.unreadable is None, (
        "an unhashed file and an unreadable file must no longer look identical"
    )


@pytest.mark.skipif(
    sys.platform == "win32" or os.geteuid() == 0,
    reason="chmod 000 does not deny the owner on Windows, nor root anywhere",
)
def test_a_real_chmod_000_file_is_reported(tmp_path: Path) -> None:
    """The injected fixtures above correspond to something an OS really does.

    This is the only test in the file that skips, and it is the one that stops the others from
    proving nothing but that the code handles a mock.
    """
    locked = tmp_path / "locked.jpg"
    _jpeg(locked)
    locked.chmod(0o000)
    try:
        result = compute_hashes([locked])[locked]
    finally:
        locked.chmod(0o600)

    assert result.unreadable is UnreadableReason.PERMISSION
