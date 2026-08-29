"""How truestill talks to external programs: where it finds them, and how it launches them.

**The defect this closes ((aad)).** Every external binary was found with `shutil.which`, which
searches PATH and nothing else. That is right for a developer install and wrong for a shipped
one: a double-clicked desktop app inherits no useful PATH, and the binary it needs was shipped
*inside* it. Searching PATH first would also mean an installed copy silently preferring whatever
version is on the user's machine over the one it was built and tested against.

**"Bundled" is a contract this module defines, not a bundler's layout.** The promise runs the
other way round from the usual: these are the places truestill looks, and a bundler is judged
partly on whether it can put a file in one of them. That shape was chosen while the bundler was
undecided, and **it is kept now that PyInstaller has been chosen (`(aad)`, 2026-08-13)** for a
better reason than the original one - `TRUESTILL_BIN_DIR` is the escape hatch for a layout nobody
anticipated, and hard-coding one tool's directory shape here would make the next bundler question
a code change in the core rather than a packaging one.

**Not every external binary belongs here, and the line is not "whichever one we touched today".**
Bundle what we *compute with*; never bundle what we *delegate to*.

* ``exiftool`` is computed with. Its output becomes catalog data, so the version matters and a
  shipped app should carry a known one. It uses this module.

  **BUNDLED ON BOTH PLATFORMS** (`BACKLOG.md` `(aad)` item 4, ruled and built 2026-08-13).
  `packaging/exiftool_source.py` fetches the **official distribution**, verifies a pinned
  SHA2-256, and stages the script or launcher **with its module tree** - which is the shape
  upstream's own README requires: move the script, move ``lib/`` with it. So a packaged truestill
  resolves the exiftool it shipped with, on Windows and on Linux alike, and the version its
  catalog data was produced by is one we chose.

  A source checkout resolves from PATH, and that is not a failed bundle lookup: `bundled_bin_dirs`
  filters to directories that **exist**, so a checkout gets ``[]`` and falls through with nothing
  skipped. The `.deb` declares ``Depends: perl`` for the same reason - we vendor exiftool's
  *modules*, never an *interpreter*.

  > ⚠ **This paragraph said the opposite until 2026-08-13, and acting on it would have been a
  > defect rather than an untidiness.** It recorded a ruling - *Linux: a DECLARED DEPENDENCY
  > (`libimage-exiftool-perl`), resolved from PATH by design* - that was **reversed the same day**
  > by `676f479`, which this file was not brought along with. `BACKLOG.md` names this module as
  > where that rule was written down, so it is what a reader consults; anyone implementing what it
  > said would have made a packaged Linux install prefer the **host's** exiftool over the vendored
  > tree, which is exactly the silent substitution `676f479` hardened `selfcheck.exiftool_finding`
  > to catch (a stripped bundle reported ``ok`` while borrowing the host's modules). It also
  > credited ``--add-binary`` with placing exiftool: that flag copies **one file** and PyInstaller
  > deliberately collects nothing from ``/lib``, so it could never have carried the modules on
  > either platform. ``--add-data`` on the tree is the mechanism.
* ``rclone`` (`destinations.rclone`) is the **user's own tool**, paired with the user's own
  remotes and credentials. A bundled copy would not know their config and would be the wrong
  binary by definition. PATH only.
* ``gio trash`` (`cleanup`) is the **desktop environment's** trash service. Its whole job is to
  put a file where *that desktop* will show it in its Trash. A bundled copy would be the wrong
  implementation of a system service. PATH only.
* The file-manager openers (`service.drives`) are the **OS's**, definitionally. Bundling
  ``explorer`` or ``xdg-open`` is not a thing anyone should be able to do. PATH only.

The three PATH-only cases are not an oversight to fix later: for each of them, using a bundled
copy would be a bug rather than an improvement.

**Finding and launching live together, and that is one concern rather than two.** They are
different jobs - a path versus a process-creation flag - and on a server they would belong
apart. Here they share a *cause*: both exist because truestill is becoming a double-clicked
desktop app. Bundled-first resolution exists because an installed app inherits no useful PATH;
the no-console-window flag exists because an installed app has no console for a child to pop a
window over. Splitting them would produce two modules that are always imported together, whose
docstrings each explain half of `(aad)`, and a reader who found one would have no reason to look
for the other.

**Complexity: O(number of PATH entries), and deliberately not cached.** `ensure_exiftool` is
called once per *batch*, outside the chunk loop. Measured: `shutil.which` is **30.6 us** on a
20-entry PATH against an exiftool process start of 50-200 ms - about 0.02% of a single
invocation, with the bundled probes adding two ``stat`` calls in front. Caching would buy nothing
measurable and would cost the ability to honour an override set after first use, which is exactly
the import-time-constant failure `(aae)` was made of.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

#: One directory a packager fills, honoured on every platform. The simplest thing a bundler can
#: be asked to do, and the escape hatch for a layout nobody anticipated.
BIN_DIR_ENV = "TRUESTILL_BIN_DIR"

#: Directory name looked for beside the running executable. This is the **zero-configuration**
#: half of the contract: a bundler that lays the binary down here satisfies it by layout alone,
#: without a launcher script that has to set an environment variable before anything starts.
BUNDLED_DIR_NAME = "bin"


def bundled_bin_dirs() -> list[Path]:
    """Directories that ship *with* truestill, most explicit first. Never touches PATH.

    Resolved on every call rather than at import, so an override set after startup is honoured
    and a test can redirect it - see the module docstring on why that is not a style preference.
    """
    directories: list[Path] = []
    configured = os.environ.get(BIN_DIR_ENV)
    if configured:
        directories.append(Path(configured))
    # Where a freezer actually unpacks what it shipped. Added after a throwaway PyInstaller
    # 6.21 build shipped exiftool and then could not find it: a one-dir build puts
    # `--add-binary` content under `_internal/` and points `_MEIPASS` there, so
    # `dirname(sys.executable)` and `_MEIPASS` are *different directories*. Predicted from the
    # 6.0 changelog, then measured - `bundled_bin_dirs()` returned `[]` inside the bundle.
    frozen_root = getattr(sys, "_MEIPASS", None)
    if frozen_root:
        directories.append(Path(frozen_root) / BUNDLED_DIR_NAME)
    # sys.executable is the interpreter when running from source and the app's own executable
    # once frozen. Kept because it is the zero-configuration rule a bundler can satisfy by
    # layout alone - PyInstaller does not, but a bundler that lays the binary beside its
    # executable needs no packaging config at all.
    if sys.executable:
        directories.append(Path(sys.executable).parent / BUNDLED_DIR_NAME)
    return [d for d in directories if d.is_dir()]


#: How each platform is asked to open a path with whatever the user has associated with it.
#: PATH-only by definition - see the module docstring: bundling ``explorer`` is not a thing anyone
#: should be able to do. One home because two surfaces need it: revealing a folder
#: (`service.drives`) and opening the self-check report on a build with no console
#: (`truestill_app.__main__`).
_OS_OPENERS = {"darwin": "open", "win32": "explorer"}


def os_opener() -> str | None:
    """The command this platform opens a path with, or ``None`` when it has none.

    ``None`` is the headless-Linux case and is a real answer rather than an error: the caller
    says so and gives the path instead of leaving a button that silently does nothing.
    """
    return shutil.which(_OS_OPENERS.get(sys.platform, "xdg-open"))


def resolve_binary(name: str, *, override_env: str | None = None) -> str | None:
    """Absolute path to ``name``, or ``None`` when it cannot be found anywhere.

    Order: the per-binary override, then the bundled directories, then PATH. Returning ``None``
    rather than raising keeps the *message* with the caller, which is the only place that knows
    what the binary was for and therefore what the user should do about it.

    An ``override_env`` that is set but does not point at a real file resolves to ``None``
    instead of falling through. Silently running a different binary than the one a user named is
    the never-silent rule's exact failure: it looks like it worked.
    """
    if override_env:
        chosen = os.environ.get(override_env)
        if chosen:
            return chosen if Path(chosen).is_file() else None

    # shutil.which does the looking in every branch, bundled included. On Windows PATHEXT means
    # the file is `exiftool.exe`, and a hand-rolled `(directory / name).exists()` would miss it
    # on the one platform where the bundled path matters most.
    searched = bundled_bin_dirs()
    if searched:
        found = shutil.which(name, path=os.pathsep.join(str(d) for d in searched))
        if found:
            return found
    return shutil.which(name)


#: Suppresses the console window Windows creates for a console application. Resolved by
#: ``getattr`` because the constant **only exists on Windows** - and this is what keeps the flag
#: out of every call site: ``creationflags=0`` is accepted on POSIX and does nothing, while any
#: *non-zero* value there raises ``ValueError: creationflags is only supported on Windows``.
#: Verified on both counts rather than assumed.
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _pin_text_decoding(kwargs: dict[str, Any]) -> None:
    """Text mode decodes as UTF-8 + surrogateescape unless the call site says otherwise.

    ``text=True`` alone means ``locale.getpreferredencoding(False)`` - **cp1252 on Windows** -
    while every text-mode consumer of this door parses machine output that is UTF-8 by its
    producer's own documentation: exiftool's external charset defaults to UTF8, and rclone's
    internal encoding is "unicode, so it can represent all characters in all languages", written
    out as UTF-8. Decoding that with the console code page mojibakes ``SourceFile``, which then
    misses the lookup keyed by the real path, and a correctly-dated photograph is filed
    `Undated/` with no warning - the measured misfile in `docs/research/backlog/aic.md`.

    ``errors="surrogateescape"`` rather than strict, ruled against the actual consumers: one
    undecodable byte under strict is a **crashed batch** - measured, a ``UnicodeDecodeError``
    out of ``communicate`` that costs all 200 files in the chunk - where surrogateescape
    degrades only the record carrying the byte, and is byte-identical to strict on the valid
    UTF-8 both producers document. It is also ``os.fsdecode``'s convention for streams that
    carry filenames. ⚠ **The stronger hope was tested and does not hold**: an ext4 file named
    with latin-1 ``0xE9`` does *not* round-trip into ``read_metadata``'s keys, because with
    ``-charset filename=utf8`` exiftool replaces the undecodable byte with ``?`` in its own
    echo before Python decodes anything (measured 2026-08-29). Such a file keys a fictitious
    name under **every** ``errors=`` policy - the input-side residual recorded in
    `docs/research/backlog/aif.md` - so this choice is about batch survival, not name rescue.

    A call site that passes ``encoding=`` has made the whole decision and is left alone,
    ``errors`` included; one that passes only ``errors=`` keeps it. Bytes-mode calls are
    untouched - forcing text on them would change what their callers receive.
    """
    wants_text = kwargs.get("text") or kwargs.get("universal_newlines")
    if wants_text and "encoding" not in kwargs:
        kwargs["encoding"] = "utf-8"
        kwargs.setdefault("errors", "surrogateescape")


def run(command: Sequence[str | Path], **kwargs: Any) -> subprocess.CompletedProcess[Any]:
    """`subprocess.run`, with the no-console-window flag and the text-decoding pin applied.

    **Hiding the window changes nothing about output or exit codes.** ``CREATE_NO_WINDOW``
    suppresses the console *window* Windows would create; it does not touch the child's handles.
    Redirected streams are redirected either way, and the return code is unaffected. Checked
    against every call site: all five pass ``capture_output=True`` or explicit ``DEVNULL``, so
    none of them relies on inheriting a console.

    The cost that *would* exist is worth naming so nobody rediscovers it as a mystery: a child
    whose output is **not** redirected has nowhere to write in a windowed build. That is not
    caused by this flag - a packaged app has no console to inherit in the first place - but it
    means any future call site must redirect rather than assume a terminal.
    """
    _pin_text_decoding(kwargs)
    return subprocess.run(command, creationflags=_NO_WINDOW, **kwargs)  # noqa: PLW1510


def popen(command: Sequence[str | Path], **kwargs: Any) -> subprocess.Popen[Any]:
    """`subprocess.Popen`, with the no-console-window flag applied. See :func:`run`."""
    _pin_text_decoding(kwargs)
    return subprocess.Popen(command, creationflags=_NO_WINDOW, **kwargs)


def is_bundled_install() -> bool:
    """Whether truestill appears to be a packaged install rather than a source checkout.

    **Deliberately NOT derived from `bundled_bin_dirs()`, and that coupling was the defect.**
    It read "a bundled directory exists", so the two failed *together*: a bundle whose exiftool
    was missing also stopped believing it was a bundle, and told its user to run
    ``sudo apt install`` - a terminal command, to someone with no terminal, about a cause that
    was not theirs. The one situation this function exists to describe was the one situation it
    got wrong. Found by a throwaway PyInstaller build, not by the suite.

    ``sys.frozen`` is the honest signal because it answers a *different* question from the
    search path: **what kind of process is this**, rather than *what could be found*. A freezer
    sets it when it builds the executable, so it stays true whether or not anything inside the
    bundle is intact - which is exactly the property a broken bundle needs.

    **Known limit, stated rather than discovered later:** freezers set ``sys.frozen``
    (PyInstaller, cx_Freeze, py2exe); an install that ships an ordinary interpreter - Briefcase's
    shape, and a distro package that installed the sources would be another - does **not**, and
    reads `False` here. **`(aad)` chose PyInstaller on 2026-08-13**, which sets it, so the limit is
    not reached by anything truestill ships today. It is kept because it describes when a second
    signal would be needed rather than which tool was in front of us: `selfcheck.install_finding`
    reports this value instead of relying on it, precisely so a bundle answering `False` shows
    that fact rather than hiding it inside another check's verdict.
    """
    return bool(getattr(sys, "frozen", False))
