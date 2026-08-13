"""Fetch the official ExifTool distribution, verify it, and unpack it for bundling.

**Why we vendor it rather than lean on a package manager** (ruled 2026-08-13, `BACKLOG.md`
`(aad)`). Chocolatey's `exiftool.exe` turned out to be a **shim** pointing at
``..\\lib\\exiftool\\tools\\...`` outside the bundle: it resolved, it was a real `.exe`, and it
did nothing. Leaning on packaging decisions we do not control is how that broke. The official
distribution is the thing exiftool's own author ships.

**Both platforms have the same shape, and it is the shape upstream's README describes:** *"if you
move the exiftool script to a different directory, you must also either move the contents of the
lib directory or install the Image::ExifTool package so the script can find the necessary
libraries."*

* **Unix**: `exiftool` (a Perl script) + `lib/` - 225 modules. Needs a perl interpreter, floor
  ``require 5.004``; distributions ship 5.36-5.40.
* **Windows**: `exiftool(-k).exe` - a **57 KB launcher**, CC0, by Oliver Betz - plus
  `exiftool_files/` at **34 MB**, which carries `perl.exe`, its DLLs and the same module tree.
  There is no self-contained single exe. The launcher is renamed to `exiftool.exe`; the ``-k``
  in the shipped name means *pause before exiting*, which is right for a double-click and wrong
  for a subprocess.

**And this is why `--add-binary` was never going to work:** PyInstaller documents that it
deliberately does not collect anything from `/lib` or `/usr/lib`, assuming those exist on every
system. The modules were excluded **by design, not by accident**, and the mechanism for a
directory tree is ``--add-data``.

**Digest policy, and what it does not protect against.** The version is pinned here and the
SHA2-256 is recorded here, so a changed artifact fails the build. Each digest below was
**corroborated at pin time against a second origin**: the bytes come from SourceForge (where
exiftool.org links them) and the digest from `exiftool.org/checksums.txt`, which publishes
SHA2-256 per file. That is stronger than trust-on-first-use, and it is **not provenance**: if both
origins were already compromised when the pin was taken, this verifies the wrong bytes forever.
exiftool publishes digests over HTTPS, not signatures - there is nothing to check against a key.
`checksums.txt` also lists only the *current* release, which is the second reason the digest lives
here rather than being fetched beside the file.
"""

from __future__ import annotations

import hashlib
import shutil
import sys
import tarfile
import urllib.request
import zipfile
from pathlib import Path

#: Pinned version. Bump this and both digests together, never one alone.
VERSION = "13.59"

#: Where exiftool.org actually links its downloads. The files are **not** served from
#: exiftool.org itself - a request there 404s (checked by HEAD, ranged GET and full GET).
_BASE = "https://sourceforge.net/projects/exiftool/files"

#: filename -> SHA2-256, from `https://exiftool.org/checksums.txt`, verified by download.
_ARTIFACTS = {
    "unix": (
        f"Image-ExifTool-{VERSION}.tar.gz",
        "668ea3acececb7235fbd0f4900e72d5f12c9b07e5c778fd36cb1e9b5828fd65a",
    ),
    "windows": (
        f"exiftool-{VERSION}_64.zip",
        "44b512b25af500724ba579d0a53c8fc5851628b692dd5e5d94ae4a15c2cba9ec",
    ),
}

_CHUNK = 1 << 20


def _download(name: str, into: Path) -> Path:
    target = into / name
    url = f"{_BASE}/{name}/download"
    print(f"fetching {url}")
    with urllib.request.urlopen(url) as response, target.open("wb") as handle:
        shutil.copyfileobj(response, handle, _CHUNK)
    return target


def _verify(path: Path, expected: str) -> None:
    """Fail loudly rather than build something unverified."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(_CHUNK), b""):
            digest.update(block)
    actual = digest.hexdigest()
    if actual != expected:
        message = (
            f"{path.name} does not match the pinned digest.\n"
            f"  expected {expected}\n  actual   {actual}\n"
            "The pinned artifact changed under its URL. Do not 'fix' this by updating the digest "
            "until the new bytes are established as legitimate."
        )
        raise SystemExit(message)
    print(f"verified {path.name} sha256={actual}")


def fetch(destination: Path) -> Path:
    """Put a ready-to-bundle exiftool in ``destination`` and return the directory to add.

    The returned directory is what goes to PyInstaller's ``--add-data`` as ``bin`` - the script or
    launcher **and** its module tree, together, which is the whole lesson of this file.
    """
    platform = "windows" if sys.platform == "win32" else "unix"
    name, expected = _ARTIFACTS[platform]
    destination.mkdir(parents=True, exist_ok=True)
    archive = _download(name, destination)
    _verify(archive, expected)

    staged = destination / "bin"
    if staged.exists():
        shutil.rmtree(staged)
    staged.mkdir()

    if platform == "windows":
        with zipfile.ZipFile(archive) as bundle:
            bundle.extractall(destination)
        root = destination / f"exiftool-{VERSION}_64"
        # `-k` means "pause before exiting", which is right for a double-click and wrong for a
        # subprocess. Upstream's own README says to rename it.
        shutil.move(str(root / "exiftool(-k).exe"), str(staged / "exiftool.exe"))
        shutil.move(str(root / "exiftool_files"), str(staged / "exiftool_files"))
    else:
        with tarfile.open(archive) as bundle:
            bundle.extractall(destination, filter="data")
        root = destination / f"Image-ExifTool-{VERSION}"
        shutil.move(str(root / "exiftool"), str(staged / "exiftool"))
        shutil.move(str(root / "lib"), str(staged / "lib"))
        (staged / "exiftool").chmod(0o755)

    print(f"staged {platform} exiftool at {staged}")
    return staged


if __name__ == "__main__":
    raise SystemExit(0 if fetch(Path(sys.argv[1] if len(sys.argv) > 1 else "exiftool-src")) else 1)
