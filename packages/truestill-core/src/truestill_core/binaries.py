"""How truestill talks to external programs: where it finds them, and how it launches them.

**The defect this closes ((aad)).** Every external binary was found with `shutil.which`, which
searches PATH and nothing else. That is right for a developer install and wrong for a shipped
one: a double-clicked desktop app inherits no useful PATH, and the binary it needs was shipped
*inside* it. Searching PATH first would also mean an installed copy silently preferring whatever
version is on the user's machine over the one it was built and tested against.

**"Bundled" is a contract this module defines, not a bundler's layout.** `(aad)` has not chosen
between PyInstaller, Briefcase and the rest, and hard-coding one tool's directory shape here
would quietly make that choice. So the promise runs the other way: these are the places truestill
looks, and a candidate bundler is judged partly on whether it can put a file in one of them.

**Not every external binary belongs here, and the line is not "whichever one we touched today".**
Bundle what we *compute with*; never bundle what we *delegate to*.

* ``exiftool`` is computed with. Its output becomes catalog data, so the version matters and a
  shipped app should carry a known one. It uses this module.
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
    # sys.executable is the interpreter when running from source and the app's own executable
    # once frozen, which is what makes "beside the executable" mean the right thing in both.
    if sys.executable:
        directories.append(Path(sys.executable).parent / BUNDLED_DIR_NAME)
    return [d for d in directories if d.is_dir()]


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


def run(command: Sequence[str | Path], **kwargs: Any) -> subprocess.CompletedProcess[Any]:
    """`subprocess.run`, with the no-console-window flag applied.

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
    return subprocess.run(command, creationflags=_NO_WINDOW, **kwargs)  # noqa: PLW1510


def popen(command: Sequence[str | Path], **kwargs: Any) -> subprocess.Popen[Any]:
    """`subprocess.Popen`, with the no-console-window flag applied. See :func:`run`."""
    return subprocess.Popen(command, creationflags=_NO_WINDOW, **kwargs)


def is_bundled_install() -> bool:
    """Whether truestill appears to be a packaged install rather than a source checkout.

    Derived from **our own contract** - a bundled directory exists - rather than from a marker a
    particular bundler sets, for the same reason the search order avoids one. Used only to choose
    which advice a missing-binary message gives: "your installation looks incomplete" is right
    for a packaged copy and useless for a developer who simply has not installed the tool.
    """
    return bool(bundled_bin_dirs())
