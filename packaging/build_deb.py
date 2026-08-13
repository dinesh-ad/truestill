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
* ``/usr/share/doc/truestill/copyright`` - what the bundle carries and under what terms.

**Depends: perl.** We vendor exiftool's *modules*; we do not vendor an *interpreter*. exiftool's
floor is ``require 5.004`` and every distribution ships far beyond it, but declaring it is what
makes the package honest rather than lucky - and the self-check proves it at runtime rather than
assuming, reporting a missing interpreter differently from a broken bundle.

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
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]

#: Debian's own name for x86-64. Not `x86_64`, which is what everything else calls it.
_ARCH = "amd64"

_CONTROL = """Package: truestill
Version: {version}
Section: graphics
Priority: optional
Architecture: {arch}
Depends: perl
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
"""


def build(dist: Path, version: str, out: Path) -> Path:
    """Stage the tree, write the metadata, and hand it to ``dpkg-deb``."""
    if not (dist / "truestill").is_file():
        message = f"no frozen application at {dist} - build it before packaging it"
        raise SystemExit(message)

    staging = out / f"truestill_{version}_{_ARCH}"
    if staging.exists():
        shutil.rmtree(staging)

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
    parser.add_argument("--version", default="0.0.0")
    parser.add_argument("--out", type=Path, default=_ROOT / "deb-out")
    args = parser.parse_args(argv)

    args.out.mkdir(parents=True, exist_ok=True)
    package = build(args.dist, args.version.lstrip("v"), args.out)
    print(f"built {package} ({package.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
