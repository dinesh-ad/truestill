"""Does the SHIPPED artifact carry the mark in `brand/`?

**The three cheap proxies this refuses, because each is one step short of the property.**
*"`--icon` was passed"* reads the workflow, not the artifact. *"the file exists in `brand/`"*
reads the checkout. *"`dpkg-deb --contents` lists the path"* proves a name, and a path can hold
the wrong bytes or none. `ENGINEERING_STANDARD.md` §4, forty-second member: a check measuring the
cheaper proxy passes the artifact it was written for.

So both modes open the built artifact, pull the icon bytes **out of it**, and hash them against
the committed artwork. The split is `(aad)`'s own: the artifact holds bytes, the checkout decides
whether they are the right ones - the same division `compare_selfcheck.py` makes.

**Linux closes both sides.** The desktop entry is read *from the package payload* and its `Icon=`
value is what the icon paths are then built from - so an entry naming one thing while the package
stages another fails, which checking either half alone would miss.

**Windows compares resource bytes to ICO bytes, and that is exact rather than approximate.**
`PyInstaller/utils/win32/icon.py`'s `IconFile.__init__` reads each `ICONDIRENTRY` as
``file.read(e.dwBytesInRes)`` and hands those bytes straight to `UpdateResource`. The image
payloads are copied verbatim; only the directory header differs (`ICONDIR` -> `GRPICONDIR`).
Verified in the pinned 6.21.0 source, not assumed.

**WHAT THIS CANNOT SEE, and none of it is a gap to close here:**

* **What is drawn.** It proves correct bytes at the paths the specs say are consulted. Whether
  Explorer, the taskbar or GNOME Shell renders them is a claim about a desktop environment, and
  CI has none.
* **The cry-wolf half runs on Windows only.** `_pyinstaller_default_icon` needs
  ``PyInstaller/bootloader/images/``, which the **Linux wheel does not ship** (checked: the
  Linux wheel's `bootloader/` holds only `Linux-64bit-intel`). A guard that runs on one lane is
  fine; one that is silently absent on the other is not, so `--exe` says so out loud rather than
  skipping quietly.
* **Whether the icon cache was refreshed** on the user's machine. That is the `hicolor-icon-theme`
  trigger's job - see `build_deb.py`.
* **macOS.** `--icon` wants `.icns` there and `brand/` holds none. D9 builds macOS and does not
  publish it.
* **Whether the mark is any good.** That is not a question a byte comparison can hold.

**Complexity: O(entries in the artifact).** One `dpkg-deb` pipe or one resource-directory walk.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import struct
import subprocess
import sys
import tarfile
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_BRAND = _ROOT / "brand"

#: The hicolor sizes the `.deb` stages, and the only ones this asserts. Kept here rather than
#: imported from `build_deb` so the check states its own expectation: a verifier that read the
#: builder's list would agree with it by construction and prove nothing.
DEB_ICON_SIZES = (16, 24, 32, 48, 64, 128, 256, 512)

#: Where the desktop entry lives inside the package payload.
DESKTOP_ENTRY = "usr/share/applications/truestill.desktop"

#: RT_ICON and RT_GROUP_ICON, from `winuser.h`. RT_GROUP_ICON is read only to prove the directory
#: resource exists: without it Windows has an index of nothing and shows the default.
_RT_ICON = 3
_RT_GROUP_ICON = 14

#: `ICONDIR`: reserved (always 0), type (1 = icon, 2 = cursor), image count.
_ICONDIR = struct.Struct("<HHH")
_ICO_TYPE = 1

#: One `ICONDIRENTRY`: width, height, colours, reserved, planes, bit count, byte size, offset.
_ICONDIRENTRY = struct.Struct("<BBBBHHII")


class IconMismatchError(Exception):
    """The artifact does not carry the committed mark. Always fatal - never a warning."""


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# --------------------------------------------------------------------------------- the ICO


def ico_images(blob: bytes) -> list[bytes]:
    """Every image payload inside an ICO, in file order.

    The same walk PyInstaller performs, which is what makes the Windows comparison exact rather
    than a resemblance. A malformed header raises rather than returning a short list: a silently
    truncated result would compare equal to a silently truncated resource.
    """
    if len(blob) < _ICONDIR.size:
        message = "not an ICO: shorter than its own header"
        raise IconMismatchError(message)
    reserved, kind, count = _ICONDIR.unpack(blob[: _ICONDIR.size])
    if reserved != 0 or kind != _ICO_TYPE:
        message = f"not an ICO: reserved={reserved} type={kind}, expected 0 and {_ICO_TYPE}"
        raise IconMismatchError(message)

    images: list[bytes] = []
    for index in range(count):
        start = _ICONDIR.size + _ICONDIRENTRY.size * index
        entry = _ICONDIRENTRY.unpack(blob[start : start + _ICONDIRENTRY.size])
        size, offset = entry[6], entry[7]
        image = blob[offset : offset + size]
        if len(image) != size:
            message = f"ICO entry {index} claims {size} bytes and carries {len(image)}"
            raise IconMismatchError(message)
        images.append(image)
    return images


# --------------------------------------------------------------------------------- the .deb


def deb_payload(package: Path) -> dict[str, bytes]:
    """Every regular file inside the package, keyed by path with dpkg's leading `./` removed."""
    stream = subprocess.run(
        ["dpkg-deb", "--fsys-tarfile", str(package)],
        capture_output=True,
        check=True,
    )
    files: dict[str, bytes] = {}
    with tarfile.open(fileobj=io.BytesIO(stream.stdout), mode="r:*") as archive:
        for member in archive:
            if not member.isfile():
                continue
            handle = archive.extractfile(member)
            if handle is not None:
                files[member.name.lstrip("./")] = handle.read()
    return files


def desktop_icon_name(entry: str) -> str:
    """The `Icon=` value, refused unless the Icon Theme Specification can resolve it.

    Two refusals, and both are failures the spec makes silent. **An extension** - the lookup
    appends `.png`/`.svg`/`.xpm` itself, so `truestill.png` is searched for as `truestill.png.png`.
    **A slash** - a value containing one is treated as a path and bypasses the theme entirely,
    which works on the build machine and nowhere a theme is involved.
    """
    values = [
        line.split("=", 1)[1].strip() for line in entry.splitlines() if line.startswith("Icon=")
    ]
    if len(values) != 1:
        message = f"the desktop entry carries {len(values)} Icon= lines, expected 1"
        raise IconMismatchError(message)
    name = values[0]
    if "/" in name:
        message = f"Icon={name!r} contains a slash, so theme lookup is bypassed"
        raise IconMismatchError(message)
    if "." in name:
        message = f"Icon={name!r} carries an extension; the lookup appends its own"
        raise IconMismatchError(message)
    return name


def refuse_opaque(name: str, blob: bytes) -> None:
    """Debian Policy §9.6 wants a transparent background, asserted on the STAGED bytes."""
    # Local, so importing this module never depends on Pillow. It is a `truestill-core` runtime
    # dependency and always present under `uv run`; the release lane is the only caller.
    from PIL import Image  # noqa: PLC0415

    with Image.open(io.BytesIO(blob)) as image:
        if "A" not in image.getbands():
            message = f"{name} has no alpha channel; Policy §9.6 wants transparency"
            raise IconMismatchError(message)
        low, _high = image.getchannel("A").getextrema()
    if low != 0:
        message = f"{name} has no fully transparent pixel (alpha floor {low})"
        raise IconMismatchError(message)


def verify_deb(package: Path) -> list[str]:
    """The package stages the committed artwork, at the paths its own desktop entry names."""
    payload = deb_payload(package)
    entry = payload.get(DESKTOP_ENTRY)
    if entry is None:
        message = f"no {DESKTOP_ENTRY} in the package"
        raise IconMismatchError(message)
    name = desktop_icon_name(entry.decode("utf-8"))

    lines = [f"desktop entry names Icon={name}"]
    for size in DEB_ICON_SIZES:
        path = f"usr/share/icons/hicolor/{size}x{size}/apps/{name}.png"
        staged = payload.get(path)
        if staged is None:
            message = f"the package stages no {path}"
            raise IconMismatchError(message)
        committed = (_BRAND / "icons" / f"truestill-{size}.png").read_bytes()
        if _sha(staged) != _sha(committed):
            message = (
                f"{path} is not brand/icons/truestill-{size}.png "
                f"({_sha(staged)[:12]} against {_sha(committed)[:12]})"
            )
            raise IconMismatchError(message)
        refuse_opaque(path, staged)
        lines.append(f"  {path}  {len(staged):,} B  {_sha(staged)[:12]}")
    return lines


# --------------------------------------------------------------------------------- the .exe


def exe_icon_images(executable: Path) -> list[bytes]:
    """Every RT_ICON resource in a PE image, and proof the RT_GROUP_ICON directory exists.

    **`pefile` rather than a hand-rolled resource walk**, and the independence question was asked
    rather than waved past: PyInstaller writes icons through `win32api.UpdateResource` (pywin32)
    and `utils/win32/icon.py` does not import `pefile` at all, so this reads back what the
    **Windows resource API** wrote rather than trusting the writer's own parser.
    """
    # Local, so a Linux lane that only exercises the .deb path never pays the import.
    import pefile  # noqa: PLC0415

    image = pefile.PE(str(executable), fast_load=True)
    image.parse_data_directories(
        directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_RESOURCE"]]
    )
    resources = getattr(image, "DIRECTORY_ENTRY_RESOURCE", None)
    if resources is None:
        message = f"{executable.name} carries no resource directory at all"
        raise IconMismatchError(message)

    icons: list[bytes] = []
    groups = 0
    for kind in resources.entries:
        if kind.id == _RT_GROUP_ICON:
            groups += len(kind.directory.entries)
        if kind.id != _RT_ICON:
            continue
        for named in kind.directory.entries:
            for language in named.directory.entries:
                icons.append(
                    image.get_data(language.data.struct.OffsetToData, language.data.struct.Size)
                )
    if groups == 0:
        message = f"{executable.name} has RT_ICON images but no RT_GROUP_ICON directory"
        raise IconMismatchError(message)
    return icons


def _pyinstaller_default_icon() -> Path | None:
    """PyInstaller's own windowed icon, or `None` where the wheel does not ship it."""
    import PyInstaller  # noqa: PLC0415

    candidate = Path(PyInstaller.__file__).parent / "bootloader" / "images" / "icon-windowed.ico"
    return candidate if candidate.is_file() else None


def verify_exe(executable: Path) -> list[str]:
    """The executable's icon resources are the committed ICO's images - and not the default."""
    committed = (_BRAND / "favicon.ico").read_bytes()
    expected = {_sha(image) for image in ico_images(committed)}
    found = {_sha(image) for image in exe_icon_images(executable)}

    if found != expected:
        message = (
            f"{executable.name} carries {len(found)} icon image(s) and brand/favicon.ico has "
            f"{len(expected)}; {len(found & expected)} match"
        )
        raise IconMismatchError(message)

    lines = [f"{executable.name} carries all {len(expected)} images of brand/favicon.ico"]

    # THE CRY-WOLF HALF. Without it a comparison that matched nothing against nothing would pass.
    default = _pyinstaller_default_icon()
    if default is None:
        lines.append(
            "  NOT CHECKED: PyInstaller ships no bootloader/images/ on this platform, so "
            "'is not the default icon' is unproven here - it runs on the Windows lane"
        )
    elif {_sha(image) for image in ico_images(default.read_bytes())} == found:
        message = "the executable still carries PyInstaller's own windowed icon"
        raise IconMismatchError(message)
    else:
        lines.append("  and it is not PyInstaller's default windowed icon")
    return lines


# --------------------------------------------------------------------------------- entry point


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="verify a built artifact carries brand/'s mark")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--deb", type=Path, help="the built .deb")
    group.add_argument("--exe", type=Path, help="the built or installed truestill.exe")
    args = parser.parse_args(argv)

    target: Path = args.deb or args.exe
    if not target.is_file():
        print(f"no artifact at {target}")
        return 2
    try:
        lines = verify_deb(target) if args.deb else verify_exe(target)
    except IconMismatchError as mismatch:
        print(f"::error::THE SHIPPED ARTIFACT DOES NOT CARRY THE MARK - {mismatch}")
        return 1
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
