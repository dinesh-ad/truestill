"""Thumbnails: the content-id guard, the cache contract, and that it renders a real image.

The security-shaped assertion is `cache_path` refusing anything that is not a sha256. It is the
second of the two joins the plan named - the first is the drive-relative path, which
`destinations.check_contained` already owns - and it is the one that turns a content id into a
FILENAME, so a separator or a `..` reaching it would be a traversal.
"""

from __future__ import annotations

import io
import subprocess
import sys
from pathlib import Path

import pytest
from PIL import Image
from truestill_core import thumbnails


def _photo(path: Path, size: tuple[int, int] = (1200, 900)) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, (30, 90, 160)).save(path, "JPEG", quality=90)
    return path


SHA = "a" * 64


# ------------------------------------------------------------------ the content-id guard


@pytest.mark.parametrize(
    "bad",
    [
        pytest.param("../../etc/passwd", id="traversal"),
        pytest.param("a" * 63, id="too short"),
        pytest.param("a" * 65, id="too long"),
        pytest.param("A" * 64, id="uppercase is not the shape we store"),
        pytest.param("g" * 64, id="not hex"),
        pytest.param(f"{'a' * 64}/../../x", id="valid prefix then traversal"),
        pytest.param("", id="empty"),
        pytest.param("a" * 32 + "/" + "a" * 31, id="separator mid-string"),
    ],
)
def test_a_content_id_that_is_not_a_sha256_never_becomes_a_path(bad: str, tmp_path: Path) -> None:
    """THE TRAVERSAL GUARD. Every one of these would be a filename if the check were missing."""
    with pytest.raises(thumbnails.BadContentIdError):
        thumbnails.cache_path(tmp_path, bad)


def test_a_real_sha256_resolves_inside_the_cache_directory(tmp_path: Path) -> None:
    """The cry-wolf half: the guard must accept what it exists to let through."""
    resolved = thumbnails.cache_path(tmp_path, SHA)
    assert resolved.suffix == ".webp"
    # Containment stated as the property, not as a string comparison that a `..` could satisfy.
    assert tmp_path.resolve() in resolved.resolve().parents


def test_the_fan_out_keeps_directories_small(tmp_path: Path) -> None:
    """256 buckets on the first two hex characters - one directory of 33k entries is slow to
    list on the filesystems that manage it at all."""
    a = thumbnails.cache_path(tmp_path, "ab" + "0" * 62)
    b = thumbnails.cache_path(tmp_path, "cd" + "0" * 62)
    assert a.parent.name == "ab"
    assert b.parent.name == "cd"
    assert a.parent != b.parent


# -------------------------------------------------------------- the decoder it inherits


def test_the_decoder_setup_is_not_a_function_of_import_order(tmp_path: Path) -> None:
    """`hashing` registers the HEIF opener and raises Pillow's pixel ceiling AS AN IMPORT SIDE
    EFFECT. `thumbnails` imports it deliberately for that, so both hold in a bare interpreter that
    has imported nothing else - not merely under the app, where something else happened to.

    Run in a SUBPROCESS because this session's other tests have already imported `hashing`; in
    process the assertion would pass no matter what `thumbnails` imports. A guard that its own
    test suite guarantees green is not a guard.
    """
    probe = tmp_path / "probe.py"
    probe.write_text(
        "from truestill_core import thumbnails\n"
        "from PIL import Image\n"
        "assert Image.MAX_IMAGE_PIXELS >= 300_000_000, Image.MAX_IMAGE_PIXELS\n"
        "assert 'HEIF' in Image.OPEN or not thumbnails.HEIF_AVAILABLE, sorted(Image.OPEN)\n"
        "print('ok')\n"
    )
    done = subprocess.run([sys.executable, str(probe)], capture_output=True, text=True, check=False)
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip() == "ok"


# ------------------------------------------------------------------------ what it produces


def test_it_renders_a_real_image_at_the_declared_size(tmp_path: Path) -> None:
    source = _photo(tmp_path / "src" / "a.jpg")
    data = thumbnails.thumbnail(source, SHA, tmp_path / "cache")

    with Image.open(io.BytesIO(data)) as out:
        assert out.format == "WEBP"
        assert max(out.size) == thumbnails.THUMB_PX, f"long edge is {out.size}"
        assert out.size[0] > out.size[1], "aspect ratio was not preserved"


@pytest.mark.parametrize(
    ("source_size", "expected_scale"),
    [
        pytest.param((3200, 2368), (400, 296), id="landscape - 1/8, not the 1/4 a square gets"),
        pytest.param((2368, 3200), (296, 400), id="portrait - the other branch of _fitted"),
    ],
)
def test_it_decodes_at_the_smallest_dct_scale_that_covers_the_target(
    source_size: tuple[int, int],
    expected_scale: tuple[int, int],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """THE DECODE COST, asserted as a size rather than as a duration.

    A timing assertion would be flaky on a loaded machine and would prove nothing about *why* it
    was slow. The mechanism is exact and observable instead: by the time `thumbnail()` is called
    the image has already been drafted, so `self.size` there IS the DCT scale libjpeg handed back.

    **Both orientations, because a first attempt covered only landscape and a mutation walked
    straight through it.** Breaking `_fitted`'s portrait branch changes NOTHING about the output -
    `thumbnail()` fits the long edge regardless - so an output assertion cannot see it. The only
    thing that moves is the scale: a portrait drafts at 1/4 instead of 1/8 and silently costs four
    times the pixels. Asserting the visible result would have been asserting Pillow's behaviour,
    not ours.
    """
    source = _photo(tmp_path / "src" / "photo.jpg", size=source_size)

    drafted: list[tuple[int, int]] = []
    real = Image.Image.thumbnail

    def spy(self: Image.Image, size: tuple[int, int], *args: object, **kwargs: object) -> None:
        drafted.append(self.size)
        return real(self, size, *args, **kwargs)

    monkeypatch.setattr(Image.Image, "thumbnail", spy)
    thumbnails.render(source)

    assert drafted == [expected_scale], (
        f"a {source_size} source decoded at {drafted}, not {expected_scale} - the draft target "
        "let the SHORT edge pick the scale, which costs four times the pixels for identical output"
    )


def test_a_photo_smaller_than_a_thumbnail_is_never_enlarged(tmp_path: Path) -> None:
    """Upscaling would invent detail and cost bytes. `thumbnail` never grows an image and the
    fitted draft target must not change that."""
    source = _photo(tmp_path / "src" / "tiny.jpg", size=(100, 80))
    data = thumbnails.thumbnail(source, SHA, tmp_path / "cache")
    with Image.open(io.BytesIO(data)) as out:
        assert out.size == (100, 80), f"a 100x80 photo came back as {out.size}"


def test_a_tall_photo_keeps_its_shape(tmp_path: Path) -> None:
    """The output-shaped half: portrait in, portrait out, long edge on THUMB_PX."""
    source = _photo(tmp_path / "src" / "tall.jpg", size=(900, 1200))
    data = thumbnails.thumbnail(source, SHA, tmp_path / "cache")
    with Image.open(io.BytesIO(data)) as out:
        assert out.size == (240, thumbnails.THUMB_PX), f"a 900x1200 photo came back as {out.size}"


def test_the_original_is_never_touched(tmp_path: Path) -> None:
    """§1: the pipeline only ever copies bytes. A thumbnail is a proxy, never an edit."""
    source = _photo(tmp_path / "src" / "a.jpg")
    before = source.read_bytes()
    thumbnails.thumbnail(source, SHA, tmp_path / "cache")
    assert source.read_bytes() == before


# ------------------------------------------------------------------------- the cache contract


def test_a_second_call_is_served_from_the_cache_and_not_re_rendered(tmp_path: Path) -> None:
    """The whole point of the cache, asserted by making a re-render impossible rather than by
    timing it: the source is removed between the calls."""
    source = _photo(tmp_path / "src" / "a.jpg")
    cache = tmp_path / "cache"
    first = thumbnails.thumbnail(source, SHA, cache)

    source.unlink()
    second = thumbnails.thumbnail(source, SHA, cache)

    assert second == first, "the second call did not come from the cache"


def test_a_cache_that_cannot_be_written_still_returns_the_bytes(tmp_path: Path) -> None:
    """A cache is an optimisation. Losing it must be a slower app, never a broken one."""
    source = _photo(tmp_path / "src" / "a.jpg")
    blocked = tmp_path / "ro"
    blocked.mkdir()
    blocked.chmod(0o500)
    try:
        data = thumbnails.thumbnail(source, SHA, blocked)
        assert data, "no bytes came back when the cache was unwritable"
        with Image.open(io.BytesIO(data)) as out:
            assert out.format == "WEBP"
    finally:
        blocked.chmod(0o700)


def test_the_bytes_are_never_written_to_the_name_a_reader_would_open(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Same discipline as `safe_copy`: written to a sibling and renamed, so a concurrent reader
    cannot open a half-written entry under the real name.

    **THE FIRST VERSION OF THIS TEST WAS WORTHLESS AND A MUTATION FOUND IT.** It asserted that no
    `*.partial` remained afterwards - which is equally true of a direct `write_bytes` to the
    target, so replacing the rename with a plain write left all sixteen tests green. An assertion
    satisfied by both the implementation and its defect is not a guard.

    The property is *the target path never holds incomplete bytes*, so what has to be observed is
    **where the write goes**, not what is left over. Recording the path `write_bytes` is called
    with fails the moment somebody writes straight to the target.
    """
    source = _photo(tmp_path / "src" / "a.jpg")
    cache = tmp_path / "cache"
    target = thumbnails.cache_path(cache, SHA)

    written: list[Path] = []
    real = Path.write_bytes

    def spy(self: Path, data: bytes) -> int:
        written.append(Path(self))
        return real(self, data)

    monkeypatch.setattr(Path, "write_bytes", spy)
    thumbnails.thumbnail(source, SHA, cache)

    assert written, "nothing was written at all"
    assert target not in written, (
        f"the bytes were written directly to {target.name}, the name a reader opens - "
        "a concurrent reader can see a half-written thumbnail"
    )
    assert target.exists(), "the entry never arrived at its final name"
    assert list(cache.rglob("*.partial")) == [], "a staged file was left behind"


def test_an_unreadable_source_raises_rather_than_caching_a_broken_entry(tmp_path: Path) -> None:
    """A file that is not an image must not leave anything behind for the next call to serve."""
    broken = tmp_path / "src" / "not-an-image.jpg"
    broken.parent.mkdir(parents=True)
    broken.write_bytes(b"this is not a jpeg")
    cache = tmp_path / "cache"

    with pytest.raises(Exception, match=r"(?i)cannot identify|image"):
        thumbnails.thumbnail(broken, SHA, cache)

    assert list(cache.rglob("*.webp")) == [], "a failed render left a cache entry"
