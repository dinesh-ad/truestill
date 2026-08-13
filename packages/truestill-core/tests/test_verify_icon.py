"""The icon verifier, aimed at itself.

**Why this exists at all.** `packaging/verify_icon.py` is the assertion that the shipped
artifacts carry the mark, and it runs in exactly one place - the release lane, on a tag. A broken
harness there makes a correct build look wrong and sends somebody reading working packaging code
(`ENGINEERING_STANDARD.md` §4, the broken-harness member). So the *parser* is exercised here, on
every lane, against inputs whose answers are known.

**What is NOT tested here, stated rather than discovered:** the two artifacts themselves. Nothing
in `make check` builds a `.deb` or freezes an executable, and a fixture that faked one would be
testing the fixture. The artifact half is the release lane's job; this half is the guarantee that
when the release lane speaks, it is saying something.
"""

from __future__ import annotations

import importlib.util
import io
import struct
import tarfile
from pathlib import Path
from typing import Any

import pytest
from PIL import Image

_ROOT = Path(__file__).resolve().parents[3]
_BRAND = _ROOT / "brand"


def _module() -> Any:
    spec = importlib.util.spec_from_file_location(
        "verify_icon", _ROOT / "packaging" / "verify_icon.py"
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


verify_icon = _module()


# ------------------------------------------------------------------------------ the ICO walk


def test_the_committed_ico_parses_into_its_seven_images() -> None:
    """The real artifact, not a synthetic one: this is what the Windows check compares against."""
    images = verify_icon.ico_images((_BRAND / "favicon.ico").read_bytes())
    assert len(images) == 7, f"brand/favicon.ico yielded {len(images)} images"
    assert all(images), "an image payload came back empty"
    assert len(set(images)) == 7, "two entries carry identical bytes"


def test_a_truncated_entry_raises_rather_than_returning_a_short_image() -> None:
    """THE CRY-WOLF HALF of the walk, and the failure it guards is silent.

    A payload cut short would compare equal to a resource cut short in the same way, so the
    comparison would pass on two identically broken artifacts. It must raise instead.
    """
    blob = bytearray((_BRAND / "favicon.ico").read_bytes())
    with pytest.raises(verify_icon.IconMismatchError, match="carries"):
        verify_icon.ico_images(bytes(blob[: len(blob) // 2]))


@pytest.mark.parametrize(
    "blob",
    [
        pytest.param(b"", id="shorter than its own header"),
        pytest.param(struct.pack("<HHH", 1, 1, 0), id="reserved is not zero"),
        pytest.param(struct.pack("<HHH", 0, 2, 0), id="type 2 is a cursor, not an icon"),
    ],
)
def test_a_file_that_is_not_an_ico_is_refused(blob: bytes) -> None:
    with pytest.raises(verify_icon.IconMismatchError):
        verify_icon.ico_images(blob)


# ------------------------------------------------------------- the desktop entry's Icon= value


def test_the_icon_name_is_read_from_the_entry() -> None:
    entry = "[Desktop Entry]\nType=Application\nName=Truestill\nIcon=truestill\n"
    assert verify_icon.desktop_icon_name(entry) == "truestill"


def test_an_extension_is_refused_because_the_lookup_appends_its_own() -> None:
    """`Icon=truestill.png` is searched for as `truestill.png.png` - a silent miss on a name that
    reads correct to everybody who checks it by eye."""
    with pytest.raises(verify_icon.IconMismatchError, match="extension"):
        verify_icon.desktop_icon_name("[Desktop Entry]\nIcon=truestill.png\n")


def test_a_path_is_refused_because_it_bypasses_the_theme() -> None:
    """An absolute path works on the build machine and skips theme lookup everywhere."""
    with pytest.raises(verify_icon.IconMismatchError, match="slash"):
        verify_icon.desktop_icon_name("[Desktop Entry]\nIcon=/usr/lib/truestill/t.png\n")


@pytest.mark.parametrize("entry", ["[Desktop Entry]\nName=Truestill\n", "Icon=a\nIcon=b\n"])
def test_zero_or_two_icon_lines_are_refused(entry: str) -> None:
    with pytest.raises(verify_icon.IconMismatchError, match="Icon= lines"):
        verify_icon.desktop_icon_name(entry)


# ------------------------------------------------------------------------ the transparency bar


def test_every_committed_png_clears_the_policy_transparency_bar() -> None:
    """Debian Policy §9.6 wants a transparent background. Asserted on the artwork here and on the
    STAGED bytes in the release lane - this half is what tells us the artwork can pass at all."""
    for size in verify_icon.DEB_ICON_SIZES:
        blob = (_BRAND / "icons" / f"truestill-{size}.png").read_bytes()
        verify_icon.refuse_opaque(f"truestill-{size}.png", blob)


def test_an_opaque_png_is_refused() -> None:
    """The cry-wolf half: the bar must be capable of failing."""
    buffer = io.BytesIO()
    Image.new("RGB", (16, 16), (12, 34, 56)).save(buffer, format="PNG")
    with pytest.raises(verify_icon.IconMismatchError, match="alpha"):
        verify_icon.refuse_opaque("opaque.png", buffer.getvalue())


# ------------------------------------------------------------------- the payload reader's shape


def test_the_payload_reader_strips_dpkgs_leading_dot_slash(tmp_path: Path) -> None:
    """`dpkg-deb --fsys-tarfile` names members `./usr/...`; every lookup here is `usr/...`.

    Aimed at the tar walk rather than at `dpkg-deb`, which is not installed on two of the three
    lanes. If this normalisation broke, every path lookup would miss and the verifier would report
    a package with no icons at all - a false failure on a correct build.
    """
    archive = tmp_path / "payload.tar"
    with tarfile.open(archive, "w") as tar:
        for name, body in (("./usr/share/applications/x.desktop", b"Icon=t\n"), ("./a/b", b"z")):
            info = tarfile.TarInfo(name)
            info.size = len(body)
            tar.addfile(info, io.BytesIO(body))

    with tarfile.open(archive) as tar:
        seen = {member.name.lstrip("./"): member for member in tar if member.isfile()}
    assert set(seen) == {"usr/share/applications/x.desktop", "a/b"}
