"""(aev) A photo Truestill could not decode is not compared for near-duplicates, and it says so.

**The finding, and how the entry that produced it had the subject backwards.** Soak two recorded
*"131 raw Pillow warnings reached the terminal"*. Measured on the format corpus while fixing it:

    image-extension files that produced NO perceptual hash ....... 478
      of those, that emitted any warning ......................... 71
      of those, SILENT today .................................... 407
    files that warned and hashed perfectly well .................. 14

So the warnings are a **lossy 15% proxy** for a gap the product never mentions at all: 478
photographs got no near-duplicate check and nobody was told. Suppressing the warnings on their own
would have made Truestill *quieter about a real gap* - §4's forty-second member, a check measuring
the cheaper proxy - and would have reported 71 of 478, which implies the other 407 were fine.

⚠ **THE REPORT IS DERIVED FROM THE DECODE OUTCOME, NEVER FROM A WARNING.** A warning is evidence
that something happened; the *consequence* is what a person needs, and the consequence is already
in the data. `FileHashes.perceptual_computed` exists because *"`perceptual=None` answers two
different questions - not an image and nobody looked"* (`models.py`). That settled two of three.
The third - **an image we tried to decode and could not** - is what this file pins.

**The three cases, and the middle one is the whole test.** A video's `None` is correct and must
stay silent; a good photo's hash is present and must stay silent; a damaged photo is the one fact
worth a line.
"""

from __future__ import annotations

import io
import shutil
import subprocess
import sys
from contextlib import redirect_stdout
from pathlib import Path

import pytest
from PIL import Image
from truestill_cli.cli import main
from truestill_core.models import UncomparedReason, uncompared_label

_EXIFTOOL = pytest.mark.skipif(shutil.which("exiftool") is None, reason="exiftool not installed")


def _photo(path: Path, colour: tuple[int, int, int]) -> None:
    """A photograph with STRUCTURE, tinted by ``colour``. Never a solid fill.

    ⚠ **THIS WAS `Image.new("RGB", (48, 48), colour)` UNTIL `(ahq)`**, and the whole file asserted
    that such a photo *"hashed perfectly well"* and was compared. A flat frame dHashes to all
    zeros, so once `dedup.carries_no_signal` shipped the fixture landed in the very group these
    tests prove it stays out of - **correctly**, which is why the fixture moved and the assertion
    did not. Same finding as `truestill-core/tests/conftest.py`'s `_gradient`, one package over:
    the repo's default synthetic photograph carries no picture in it.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    red, green, blue = colour
    image = Image.new("RGB", (48, 48))
    pixels = image.load()
    assert pixels is not None
    for x in range(48):
        for y in range(48):
            block = 90 if (x // 6 + y // 6) % 2 else 0
            pixels[x, y] = ((red + block) % 256, (green + x * 3) % 256, (blue + y * 3) % 256)
    image.save(path, "JPEG", quality=95)


def _undecodable_photo(path: Path) -> None:
    """A real TIFF truncated mid-strip: opens, then fails to decode. `(aev)`

    ⚠ **Truncated rather than filled with random bytes**, and the difference is the point.
    Random bytes are not an image at all and Pillow says so immediately with
    `UnidentifiedImageError` - the same answer it gives for a video, which this test needs to
    stay *silent* about. A truncated TIFF is a real photograph whose bytes stop early: Pillow
    identifies it, starts decoding, and cannot finish. That is the case the corpus produced 478
    of, and the only one that discriminates.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (256, 256), (200, 30, 30)).save(path, "TIFF")
    whole = path.read_bytes()
    path.write_bytes(whole[: len(whole) // 3])


def _palette_with_byte_transparency(path: Path) -> None:
    """A PNG that makes Pillow warn while decoding perfectly well. `(aev)`

    The 14-of-85 case: *"Palette images with Transparency expressed in bytes should be converted
    to RGBA images"* is advice to a programmer using Pillow, and the file itself is fine - it
    hashes, it is compared, nothing is lost. It exists here so the terminal test has a
    deterministic trigger and so the report test can prove this file is **not** listed.

    ⚠ **The pixels carry structure for the reason `_photo`'s do** - an all-zero palette image is
    a flat frame, and `(ahq)` would exclude it from comparison for that rather than for anything
    to do with transparency, which is this fixture's actual subject.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("P", (64, 64))
    pixels = image.load()
    assert pixels is not None
    for x in range(64):
        for y in range(64):
            pixels[x, y] = (x * 4 + (30 if (x // 8 + y // 8) % 2 else 0)) % 256
    image.putpalette(b"".join(bytes((i, i, i)) for i in range(256)))
    image.save(path, "PNG", transparency=bytes(range(256)))


def _not_an_image(path: Path) -> None:
    """A video, by extension. Its missing perceptual hash is CORRECT and must never be reported."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\x00\x00\x00\x20ftypisom" + b"\x00" * 512)


def _mixed_source(tmp_path: Path) -> Path:
    source = tmp_path / "src"
    _photo(source / "good.jpg", (10, 120, 200))
    _undecodable_photo(source / "damaged.tif")
    _palette_with_byte_transparency(source / "noisy.png")
    _not_an_image(source / "clip.mp4")
    return source


#: The heading the section is found by. A literal, because the test's subject is the words a
#: person reads - importing the constant would make this a tautology (§4's twenty-ninth member).
_SECTION = "Not compared for near-duplicates:"


def _section_of(report: str) -> str:
    """Just the new block, or "" when it was not printed.

    ⚠ **Everything below asserts inside this, never against the whole report**, and that is not
    tidiness. The first version of this file asserted ``"damaged.tif" in report`` and **passed
    against unfixed code**: the file is organized normally, so its name is already in the
    organized list. A test whose subject appears elsewhere in the haystack measures the haystack.
    """
    if _SECTION not in report:
        return ""
    return report.split(_SECTION, 1)[1].split("\n\n", 1)[0]


def _organize_with(root: Path, source: Path, *extra: str) -> str:
    """Run a preview and hand back everything it printed. Used for the threshold proof below."""
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        main(
            [
                "organize",
                str(source),
                str(root / "dest"),
                "--db",
                str(root / "c.sqlite"),
                *extra,
            ]
        )
    return buffer.getvalue()


def test_the_report_states_the_threshold_this_run_applied(tmp_path: Path) -> None:
    """`--phash-threshold` moves what is excluded, so it must move what is reported. `(ahq)`

    ⚠ **WRITTEN BECAUSE A MUTATION SURVIVED.** Replacing `args.phash_threshold` with
    `DEFAULT_PHASH_THRESHOLD` at the CLI's one call site passed **342 CLI tests**: not one of them
    moved the flag, so the whole suite proved the report agreed with a rule no run had applied.
    That is the declaration-shaped guard this week keeps producing, and this is the behaviour half.

    At **32** the two poles meet - `min(popcount, 64 - popcount) <= 32` is true of every possible
    hash - so every photograph in the source is excluded from comparison and the report has to say
    so. At the default, none of them is. The bound is derived from the hash's width, not picked.
    """
    for name in ("wide", "narrow"):
        source = tmp_path / name / "plain"
        _photo(source / "a.jpg", (10, 120, 200))
        _photo(source / "b.jpg", (200, 40, 60))

    wide = _organize_with(tmp_path / "wide", tmp_path / "wide" / "plain", "--phash-threshold", "32")
    assert uncompared_label(UncomparedReason.NO_SIGNAL) in wide, (
        "at a threshold of 32 every hash is within reach of a pole, so every file was excluded "
        "from comparison and the report said nothing about it"
    )
    section = _section_of(wide)
    assert "a.jpg" in section
    assert "b.jpg" in section

    narrow = _organize_with(tmp_path / "narrow", tmp_path / "narrow" / "plain")
    assert _SECTION not in narrow, (
        "at the default threshold these photographs carry signal and are compared normally"
    )


def _organize(tmp_path: Path, source: Path) -> int:
    return main(
        ["organize", str(source), str(tmp_path / "dest"), "--db", str(tmp_path / "c.sqlite")]
    )


@_EXIFTOOL
def test_a_photo_that_could_not_be_decoded_is_named(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The 478. Today the run says nothing at all about them."""
    source = _mixed_source(tmp_path)

    _organize(tmp_path, source)

    report = capsys.readouterr().out
    section = _section_of(report)
    assert section, (
        f"a photo Truestill could not decode got no near-duplicate check and the run never said "
        f"so - there is no {_SECTION!r} block at all:\n{report}"
    )
    assert "damaged.tif" in section, (
        f"the block exists but does not name the photo it is about:\n{section}"
    )
    assert "1" in section, "the block names a file without stating how many there were"


@_EXIFTOOL
def test_a_video_is_never_called_undecodable(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """⚠ The discriminating half, and the defect this whole area already produced once.

    `perceptual=None` is the *correct* answer for a video, and `models.py` records what happened
    when a report could not tell that apart from a failure: it *"told users their photographs were
    not images"*. A guard that fires on every video in a library is worse than no guard - people
    switch it off, and it takes the real signal with it.
    """
    source = _mixed_source(tmp_path)

    _organize(tmp_path, source)

    section = _section_of(capsys.readouterr().out)
    assert section, "nothing to discriminate against; the block was not printed at all"
    assert "clip.mp4" not in section, (
        f"a video was reported as a photo that could not be decoded. Its missing perceptual "
        f"hash is correct and expected:\n{section}"
    )
    assert "good.jpg" not in section, (
        "a photo that hashed perfectly well was listed as one that could not be compared"
    )
    assert "noisy.png" not in section, (
        "a file that WARNED but decoded and hashed perfectly well was listed. The report is "
        "derived from the outcome, not from whether a library said something - 14 of the 85 "
        "warning files in the corpus were entirely fine."
    )


@_EXIFTOOL
def test_an_ordinary_source_says_nothing_about_comparing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The cry-wolf half. A section that appears when nothing is wrong teaches people to skip it."""
    source = tmp_path / "plain"
    _photo(source / "a.jpg", (1, 2, 3))
    _photo(source / "b.jpg", (4, 5, 6))

    _organize(tmp_path, source)

    report = capsys.readouterr().out
    assert "Not compared for near-duplicates" not in report, (
        f"a source where every photo was compared grew a warning about comparing:\n{report}"
    )


@_EXIFTOOL
def test_no_raw_library_warning_reaches_a_real_terminal(tmp_path: Path) -> None:
    """The half the entry was named for - and it runs in a SUBPROCESS, which is the point.

    ⚠ **`capsys` CANNOT SEE THIS DEFECT, so an in-process version of this test is a tautology.**
    Two independent reasons, either one fatal:

    * pytest's own warnings plugin wraps every test in `catch_warnings`, so a Pillow warning is
      captured by the harness and never reaches `sys.stderr` at all;
    * the libtiff/libjpeg half is written by C code straight to **file descriptor 2**, which
      `capsys` does not replace - it swaps the `sys.stderr` *object*.

    The first version of this test used `capsys` and passed against unfixed code while a real
    `truestill organize` printed the warning plainly. §4's fifty-second member: prove the subject
    is there before reporting that nothing is wrong with it - which the first assertion does.
    """
    source = _mixed_source(tmp_path)

    run = subprocess.run(
        [
            sys.executable,
            "-c",
            "from truestill_cli.cli import main; raise SystemExit(main())",
            "organize",
            str(source),
            str(tmp_path / "dest"),
            "--db",
            str(tmp_path / "c.sqlite"),
        ],
        capture_output=True,
        text=True,
        timeout=300,
        check=False,  # the exit code is not the subject; the stderr is
    )

    # NON-EMPTINESS FIRST: if the run did not happen, "no warnings" means nothing.
    assert "hashing" in run.stderr or run.stdout, (
        f"the subprocess produced no recognisable run; there is nothing to check.\n"
        f"stdout={run.stdout[:400]}\nstderr={run.stderr[:400]}"
    )
    for leak in ("UserWarning", "warnings.warn", "site-packages"):
        assert leak not in run.stderr, (
            f"a raw library warning reached the user's terminal: {leak!r} is in the run's own "
            f"stderr. Pillow's words are not the product's words (§9).\n{run.stderr[:600]}"
        )
