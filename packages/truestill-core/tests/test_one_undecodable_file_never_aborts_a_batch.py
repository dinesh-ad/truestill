"""(aet) A file an image decoder refuses is reported, not fatal.

**The defect, measured on the first format-variety corpus.** `organize` over 1,428 media files
from `exif-samples` and `metadata-extractor-images` exited **1 with a traceback and no report** -
nothing organized, no summary, no tally. `perceptual_hash` catches
`UnidentifiedImageError`/`OSError`/`ValueError`/`DecompressionBombError`, a careful list, and
**eight files escaped it in two classes nobody would have listed**:

| escaped as | n | what it was |
|---|---:|---|
| `SyntaxError` | 7 | Pillow raises the **builtin** for a malformed PNG `zTXt` chunk |
| `EOFError` | 1 | a truncated HEIC, via `pillow_heif` |

Any one aborted the whole run. Quarantining exactly those eight made the same command exit 0 and
organize 1,398 files, which is what proved the failure is per-file rather than global.

**Why the remedy is a boundary rather than a longer list.** `ENGINEERING_STANDARD.md` §4 Errors'
partial-failure policy says *"one bad file never aborts a batch - it is logged, counted, and
reported at the end."* That is a
statement about the boundary, and **a boundary defined by enumeration is not one**: widening the
tuple fixes the eight files in hand and leaves the ninth decoder to abort a run later, identically.

**So the boundary is what is tested, not any particular decoder's exception.** Injecting the
failure at `scan.perceptual_hash` - the module that owns the call - is deliberately stronger than
a fabricated bad file: a file reproduces one decoder's behaviour on one Pillow version, while
`_ThirdPartySurprise` below is the ninth exception nobody has met yet, which is the whole claim.
The real corpus files are used too, and skip when they are absent.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image
from truestill_core.models import UnreadableReason, unreadable_label
from truestill_core.scan import compute_hashes

#: The two real classes, plus one that exists nowhere - the point being that the third is handled
#: for the same reason as the first two, rather than because anybody listed it.
_ESCAPING = [SyntaxError, EOFError, type("_ThirdPartySurprise", (Exception,), {})]

_CORPUS = Path.home() / "ad" / "application" / "metadata-extractor-images"


def _image(path: Path, colour: tuple[int, int, int]) -> Path:
    Image.new("RGB", (32, 32), colour).save(path, "PNG")
    return path


@pytest.mark.parametrize("blows_up", _ESCAPING, ids=lambda e: e.__name__)
def test_a_decoder_that_raises_anything_does_not_abort_the_batch(
    blows_up: type[Exception], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The whole of `(aet)`: the files after the bad one are still hashed.

    Patched on `truestill_core.scan`, which is where the name is CALLED - patching
    `truestill_core.hashing` would leave the worker's own binding untouched (§4, guard rule 3).
    """
    good = _image(tmp_path / "a.png", (7, 9, 11))
    bad = _image(tmp_path / "b.png", (0, 0, 0))
    third = _image(tmp_path / "c.png", (200, 30, 40))

    def refuse(path: Path) -> str | None:
        if path == bad:
            message = "the decoder refused these bytes"
            raise blows_up(message)
        return "0" * 16

    monkeypatch.setattr("truestill_core.scan.perceptual_hash", refuse)
    hashes = compute_hashes([good, bad, third], pool="thread")

    assert hashes[good].perceptual, "a healthy file BEFORE the bad one was not hashed"
    assert hashes[third].perceptual, "a healthy file AFTER the bad one was not hashed - it aborted"


def test_the_refused_file_is_named_rather_than_swallowed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """⚠ The condition the exemption rests on. An abort traded for a silence is a worse bargain.

    `UNDECODABLE` is its own reason rather than `OTHER`: the bytes read perfectly, so *"could not
    be opened"* would be false and would send the reader to check permissions on a file that has
    nothing wrong with them.
    """
    bad = _image(tmp_path / "bad.png", (1, 1, 1))

    def refuse(_path: Path) -> str | None:
        message = "Unknown compression method 120 in zTXt chunk"
        raise SyntaxError(message)

    monkeypatch.setattr("truestill_core.scan.perceptual_hash", refuse)
    hashes = compute_hashes([bad], pool="thread")

    assert hashes[bad].unreadable is UnreadableReason.UNDECODABLE, (
        f"reported as {hashes[bad].unreadable}, which describes a different failure"
    )
    worded = unreadable_label(UnreadableReason.UNDECODABLE)
    assert "decoded" in worded, f"the wording a user reads does not say what happened: {worded!r}"


def test_an_operator_interrupt_still_stops_the_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """⚠ `BaseException` is deliberately NOT caught, and the comment claims it - so it is pinned.

    A worker that ate a `KeyboardInterrupt` would make Ctrl-C stop working on the one operation
    people most want to stop: a long copy over a real library.
    """
    bad = _image(tmp_path / "bad.png", (1, 1, 1))

    def interrupt(_path: Path) -> str | None:
        raise KeyboardInterrupt

    monkeypatch.setattr("truestill_core.scan.perceptual_hash", interrupt)
    with pytest.raises(KeyboardInterrupt):
        compute_hashes([bad], pool="thread")


def test_a_healthy_image_is_untouched(tmp_path: Path) -> None:
    """The cry-wolf half. A boundary that catches everything must still let everything through."""
    good = _image(tmp_path / "fine.png", (1, 2, 3))

    hashes = compute_hashes([good], pool="thread")

    assert hashes[good].unreadable is None, "a perfectly good image was reported as unreadable"
    assert hashes[good].perceptual, "the perceptual hash was lost for a healthy image"


@pytest.mark.skipif(not _CORPUS.is_dir(), reason="the format corpus is not on this machine")
def test_the_real_corpus_files_that_found_this_are_reported_not_fatal() -> None:
    """The files that actually did it, when they are present. Skips rather than fabricates.

    `e2e_support` already rules that media does not belong in git whatever its provenance, so the
    corpus cannot be committed - the injection tests above are what run everywhere.
    """
    suite = _CORPUS / "png" / "ImageTestSuite"
    real = sorted(suite.glob("*9a3e0c7b687b526987e2270541002d47.png"))
    if not real:
        pytest.skip("the specific corpus files are not in this checkout")

    hashes = compute_hashes(real, pool="thread")

    assert len(hashes) == len(real), "a real undecodable file aborted the batch"
    assert all(h.perceptual is None for h in hashes.values())
