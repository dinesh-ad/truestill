"""Build the Linux `.deb` around the PyInstaller one-folder output.

**Why a `.deb` and not an AppImage or a tarball** (`BACKLOG.md` `(aad)`): it is the shape a Linux
user's own tooling installs, upgrades and removes, and the only one of the three that registers
with the system at all. AppImage was declined - its viability turns on a plugin, and Briefcase's
own maintainers discourage their AppImage backend.

**Layout follows the FHS**, which is what a `.deb` is for:

* ``/usr/lib/truestill/`` - the frozen application, one folder, exactly as PyInstaller built it;
* ``/usr/bin/truestill`` - a relative symlink onto it, so the command is on PATH;
* ``/usr/share/applications/`` - a desktop entry, because this is a double-clicked app rather
  than a daemon;
* ``/usr/share/icons/hicolor/<N>x<N>/apps/truestill.png`` - the mark, at eight sizes;
* ``/usr/share/doc/truestill/copyright`` - what the bundle carries and under what terms.

**Depends: perl.** We vendor exiftool's *modules*; we do not vendor an *interpreter*. exiftool's
floor is ``require 5.004`` and every distribution ships far beyond it, but declaring it is what
makes the package honest rather than lucky - and the self-check proves it at runtime rather than
assuming, reporting a missing interpreter differently from a broken bundle.

**Depends: hicolor-icon-theme, FOR THE TRIGGER RATHER THAN FOR ITS ICONS.** We use none of its
artwork. What we need is the *file trigger* it registers on ``/usr/share/icons/hicolor``, which is
what refreshes the icon cache after our PNGs land; with the package absent, no trigger exists and
the cache is never rebuilt. Verified rather than assumed, two ways. dpkg's own specification
(``/usr/share/doc/dpkg/spec/triggers.txt``) says file triggers *"are activated automatically by
dpkg when a matching file is installed, upgraded or removed as part of a package"* and are named
by absolute path, *"activated when the specified filesystem object, or any object under the
specified subdirectory, is created, updated or deleted by dpkg during package unpack or removal"*.
So **no maintainer script of ours is needed, and none is added** - the activation is dpkg's, from
what dpkg itself unpacks, which is equally true of ``dpkg -i`` on a local file as of apt.
Observed on a real machine: ``hicolor-icon-theme`` is registered ``interest-noawait
/usr/share/icons/hicolor``, declares no triggers of its own in the *triggering* package, and went
``triggers-pending`` during the **unpack** of a package that merely ships icons - before that
package's own configure ran.

**The icon name in the desktop entry carries no extension**, and that is the specification rather
than a style: the Icon Theme Specification's lookup appends ``.png``/``.svg``/``.xpm`` itself, so
``Icon=truestill.png`` would be searched for as ``truestill.png.png``. Debian Policy §9.6 wants
*"a PNG or SVG icon with a transparent background, providing at least the 22x22 size, and
preferably up to 64x64"*; the eight sizes below clear both ends, and the transparency is asserted
on the **staged bytes** by ``verify_icon.py`` rather than trusted.

**No ``scalable/apps/truestill.svg``, deliberately.** ``brand/`` holds the mark as SVG, but as
*two* drawings: ``build_brand_assets.py`` renders the fluted variant at 128px and above and the
flute-less one below, because the hairline is sub-pixel at small sizes. A scalable entry can be
preferred over a fixed size by the lookup, so shipping one would silently override that split with
whichever variant we picked - a third drawing that can disagree with the eight PNGs. The PNGs are
the mark here.

⚠ **On vendoring, since a Debian-literate user will notice.** Debian Policy §4.13 says *"Debian
packages should not make use of these convenience copies unless the included package is explicitly
intended to be used in this way"*. It **discourages rather than forbids**, it binds packages **in
the Debian archive** - which this is not, it is served from our own site - and the exception clause
fits almost verbatim: exiftool's own README documents running the script with its `lib/` beside it
precisely so it need not be installed. Recorded here so we can say this before someone says it to
us, and so that anyone who later wants this *in* Debian knows the one conversation they will have.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]

#: Debian's own name for x86-64. Not `x86_64`, which is what everything else calls it.
_ARCH = "amd64"

#: The hicolor sizes staged, every one a standard directory. **1024 is deliberately absent**:
#: hicolor defines no `1024x1024`, and `brand/icons/truestill-1024.png` is byte-identical to
#: `brand/master-1024.png` anyway. **There is no 22x22 and none is invented** - Policy's floor is
#: cleared by 24, and a fabricated size would be a drawn asset nobody drew.
_ICON_SIZES = (16, 24, 32, 48, 64, 128, 256, 512)

_CONTROL = """Package: truestill
Version: {version}
Section: graphics
Priority: optional
Architecture: {arch}
Depends: perl, hicolor-icon-theme
Maintainer: truestill <noreply@truestill.invalid>
Homepage: https://github.com/dinesh-ad/truestill
Description: Local-first photo organizer, de-duplicator and backup pipeline
 Truestill organises a photo library by the date a picture was actually taken,
 finds duplicates, and keeps track of which drives hold which copies.
 .
 Everything runs on this machine. No photo, filename, hash or count is ever
 transmitted anywhere.
"""

_DESKTOP = """[Desktop Entry]
Type=Application
Name=Truestill
Comment=Organise, de-duplicate and back up a photo library
Exec=/usr/bin/truestill
Icon=truestill
Terminal=false
Categories=Graphics;Photography;
"""

_COPYRIGHT = """Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/
Upstream-Name: truestill
Source: https://github.com/dinesh-ad/truestill

Files: *
Copyright: truestill
License: Apache-2.0

Files: usr/lib/truestill/_internal/bin/*
Copyright: Phil Harvey
Comment: The ExifTool distribution, vendored unmodified and verified against a
 pinned SHA2-256. See packaging/exiftool_source.py.
License: Artistic-1.0-Perl or GPL-1.0-or-later

Files: usr/lib/truestill/_internal/truestill_app/static/fonts/*
Copyright: 2003 Bitstream, Inc.
Comment: DejaVu Sans Mono. The notice ships beside the typefaces, which is what
 the Bitstream Vera licence binds us to.
License: Bitstream-Vera

Files: usr/share/icons/hicolor/*
Copyright: truestill
Comment: The pillar T, rendered from brand/pillar-t-geometric*.svg. Outlined
 artwork, not a font; see brand/PROVENANCE.md.
License: Apache-2.0
"""


def build(dist: Path, version: str, out: Path) -> Path:
    """Stage the tree, write the metadata, and hand it to ``dpkg-deb``.

    **``out`` receives the package and nothing else.** The staging tree is scratch, and it used
    to be built at ``out/truestill_<version>_<arch>/`` and removed only at the *start* of the
    next build - so it survived every run, in the directory `release.yml` uploads wholesale.
    ``cd out; sha256sum *`` then exits 1 on a directory under ``bash -e``, which would have
    failed the first real tag at the publish step. Reproduced 2026-08-15; pinned by
    `test_release_out_holds_only_deliverables.py`.

    The scratch directory sits **inside ``out``** rather than in ``TMPDIR``: it holds a full copy
    of the frozen application, and ``TMPDIR`` is a small root partition on more machines than it
    is not. Same filesystem as the target, so `copytree` is never a cross-device copy, and
    `TemporaryDirectory` removes it on **every** exit path - a `dpkg-deb` failure is precisely
    when someone re-runs the lane and least wants debris.
    """
    if not (dist / "truestill").is_file():
        message = f"no frozen application at {dist} - build it before packaging it"
        raise SystemExit(message)

    with tempfile.TemporaryDirectory(dir=out) as scratch:
        return _stage_and_package(dist, version, out, Path(scratch))


def _stage_and_package(dist: Path, version: str, out: Path, scratch: Path) -> Path:
    """Lay the FHS tree out under ``scratch`` and package it into ``out``."""
    # Keeps the conventional name inside the scratch directory, so anything `dpkg-deb` prints
    # still names the package it is building rather than a temporary directory.
    staging = scratch / f"truestill_{version}_{_ARCH}"

    app = staging / "usr" / "lib" / "truestill"
    app.parent.mkdir(parents=True)
    shutil.copytree(dist, app)

    # A RELATIVE symlink. An absolute one would break for anyone inspecting or relocating the
    # staged tree before install, and dpkg records it either way.
    binaries = staging / "usr" / "bin"
    binaries.mkdir(parents=True)
    (binaries / "truestill").symlink_to(Path("..") / "lib" / "truestill" / "truestill")

    desktop = staging / "usr" / "share" / "applications"
    desktop.mkdir(parents=True)
    (desktop / "truestill.desktop").write_text(_DESKTOP, encoding="utf-8")

    # The name in the desktop entry resolves through the hicolor theme, so the files have to be
    # where that lookup goes: `<theme>/<size>x<size>/<context>/<name>.png`. Copied rather than
    # rendered - `brand/` is the authored source and this is a packaging step, not an authoring
    # one. No `index.theme` is written: hicolor's belongs to hicolor-icon-theme, and a second
    # copy would conflict with the package we depend on.
    for size in _ICON_SIZES:
        source = _ROOT / "brand" / "icons" / f"truestill-{size}.png"
        if not source.is_file():
            message = f"no brand artwork at {source} - the package would name an icon it lacks"
            raise SystemExit(message)
        target = staging / "usr" / "share" / "icons" / "hicolor" / f"{size}x{size}" / "apps"
        target.mkdir(parents=True)
        shutil.copy2(source, target / "truestill.png")

    docs = staging / "usr" / "share" / "doc" / "truestill"
    docs.mkdir(parents=True)
    (docs / "copyright").write_text(_COPYRIGHT, encoding="utf-8")

    control = staging / "DEBIAN"
    control.mkdir()
    (control / "control").write_text(_CONTROL.format(version=version, arch=_ARCH), encoding="utf-8")

    package = out / f"truestill_{version}_{_ARCH}.deb"
    subprocess.run(
        ["dpkg-deb", "--build", "--root-owner-group", str(staging), str(package)],
        check=True,
    )
    return package


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="build the truestill .deb")
    parser.add_argument("--dist", type=Path, default=_ROOT / "dist" / "truestill")
    parser.add_argument(
        "--version",
        # ⚠ NOT `0.0.0`: a default that is indistinguishable from a real release is how a
        # dispatch build becomes a plausible one. `installer.iss` has defaulted to
        # `0.0.0-dev` all along; this is the same rule on the other platform. `(aex)`
        default="0.0.0-dev",
    )
    parser.add_argument("--out", type=Path, default=_ROOT / "deb-out")
    args = parser.parse_args(argv)

    args.out.mkdir(parents=True, exist_ok=True)
    package = build(args.dist, args.version.lstrip("v"), args.out)
    print(f"built {package} ({package.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
