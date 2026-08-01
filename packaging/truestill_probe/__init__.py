"""Measurements a packaged build can take about itself, written to a file a job can read.

**Why a file.** A windowed Windows build has no console: ``sys.stdout`` and ``sys.stderr`` are
``None`` and `print` is a silent no-op. So a probe that printed its findings would report
nothing at all, which is the same constraint that produced the session URL file, and it gets the
same answer - write to a path the caller passed in, and let the caller read it.

**What is being measured, and why it needs a real Windows artifact.** Two `(aad)` questions
cannot be answered anywhere else:

* whether a *genuinely* windowed process skips the legacy-catalog probe. On Linux the branch is
  only reachable by faking ``sys.stdout = None``; here it is simply true.
* whether ``CREATE_NO_WINDOW`` actually suppresses a console window. CI runs with a console, so
  no lane has ever exercised suppression.

Plus the layout question the Linux throwaways left open: which resolution rule fires under each
bundler on the platform installers actually matter for.
"""

from __future__ import annotations

import ctypes
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

# Imported at module level, not inside the functions that use them. A bundler's dependency
# analysis walks top-level imports; a function-local one can be missed entirely, which would
# produce an artifact that fails for a reason the measurement was not about.
from truestill_core import binaries
from truestill_core.app_paths import default_catalog_path, standard_catalog_path
from truestill_core.exif import ExiftoolMissingError, ensure_exiftool

#: How long the console-attach children live. Long enough to attach to, short enough that a
#: failed run does not leave anything behind for the length of the job.
_CHILD_SECONDS = 5

#: ``DETACHED_PROCESS``. The flag that gives a child **no console at all** - which is NOT what
#: ``CREATE_NO_WINDOW`` does, and that distinction is the whole correction below.
_DETACHED_PROCESS = 0x00000008


def _layout() -> dict[str, Any]:
    """Everything about where this process and its bundled files actually are."""
    return {
        "sys.executable": sys.executable,
        "dirname(sys.executable)": str(Path(sys.executable).parent),
        "sys._MEIPASS": getattr(sys, "_MEIPASS", None),
        "sys.frozen": getattr(sys, "frozen", None),
        "sys.prefix": sys.prefix,
        "sys.base_prefix": sys.base_prefix,
        "truestill_core.__file__": binaries.__file__,
        "bundled_bin_dirs()": [str(d) for d in binaries.bundled_bin_dirs()],
        "is_bundled_install()": binaries.is_bundled_install(),
        "has_console": {"stdout": sys.stdout is not None, "stderr": sys.stderr is not None},
        "cwd": os.getcwd(),  # noqa: PTH109 - the *process* cwd is the subject here, not a path
    }


def _exiftool() -> dict[str, Any]:
    """Assertion 2: does the packaged app find the exiftool it shipped with?"""
    try:
        return {"assertion": "pass", "resolved": ensure_exiftool()}
    except ExiftoolMissingError as exc:
        return {"assertion": "fail", "message": str(exc)}


def _legacy_probe() -> dict[str, Any]:
    """Windows-only question 1: does a windowed process skip the working-directory probe?

    The caller runs this with a ``reports/catalog.sqlite`` in the working directory. A console
    build must adopt it; a windowed build must ignore it and use the data directory.
    """
    resolved = default_catalog_path()
    standard = standard_catalog_path()
    legacy_present = Path("reports/catalog.sqlite").exists()
    return {
        "legacy_file_in_cwd": legacy_present,
        "resolved": str(resolved),
        "standard": str(standard),
        "skipped_the_probe": resolved == standard,
        # Only meaningful when a legacy file was actually there to ignore.
        "assertion": "pass" if (legacy_present and resolved == standard) else "inconclusive",
    }


def _console_window() -> dict[str, Any]:
    """Windows-only question 2: does ``CREATE_NO_WINDOW`` suppress the console **window**?

    **The first version of this asked the wrong question, and the answer looked like a failure.**
    It attached to the child and treated attachability as the verdict. But ``CREATE_NO_WINDOW``
    creates an **invisible console** - the child *is* attached to a console, it simply has no
    window - and ``DETACHED_PROCESS`` is the flag that yields no console at all. So a flagged
    child being attachable is exactly what the flag should produce, and attachability cannot
    distinguish suppressed from unsuppressed. No launcher change fixes that; the observable was
    wrong.

    The right observable is the **window**. ``GetConsoleWindow`` returns ``NULL`` for a console
    that has none, so attaching becomes the *setup* and the window handle is the verdict:
    non-zero for an ordinary child, zero for a suppressed one.

    The control is still the gate. This process must be able to attach at all - if it already
    owns a console it cannot, and every reading below would be meaningless.
    """
    if sys.platform != "win32":
        return {"technique": "unavailable", "reason": "AttachConsole is Windows-only"}

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    def console_window_of(creationflags: int) -> dict[str, Any]:
        child = subprocess.Popen(
            ["cmd", "/c", "timeout", "/t", str(_CHILD_SECONDS), "/nobreak"],
            creationflags=creationflags,
        )
        try:
            time.sleep(0.7)  # let the child get far enough to own (or not own) a console
            kernel32.FreeConsole()
            attached = bool(kernel32.AttachConsole(child.pid))
            error = ctypes.get_last_error()
            window = int(kernel32.GetConsoleWindow()) if attached else 0
            if attached:
                kernel32.FreeConsole()
            return {"attached": attached, "last_error": error, "console_window": window}
        finally:
            child.kill()
            child.wait(timeout=10)

    no_window_flag = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    control = console_window_of(0)
    if not control["attached"]:
        return {
            "technique": "unsound",
            "reason": (
                "this process could not attach to the control child's console at all, so no "
                "reading below distinguishes anything"
            ),
            "control": control,
        }

    suppressed = console_window_of(no_window_flag)
    detached = console_window_of(_DETACHED_PROCESS)
    return {
        "technique": "sound",
        "flag_value": no_window_flag,
        "ordinary_child": control,
        "with_create_no_window": suppressed,
        # The third arm is the reference point: DETACHED_PROCESS is what "no console" looks
        # like, so it shows whether an unattachable child is even reachable in this harness.
        "with_detached_process": detached,
        "assertion": (
            "pass"
            if control["console_window"] != 0 and suppressed["console_window"] == 0
            else "fail"
        ),
    }


def measure() -> dict[str, Any]:
    """Every finding this artifact can produce about itself."""
    return {
        "layout": _layout(),
        "exiftool": _exiftool(),
        "legacy_probe": _legacy_probe(),
        "console_suppression": _console_window(),
    }


def write_findings(destination: Path) -> Path:
    """Write the findings **atomically**, so a partial file can never read as a pass.

    A half-written JSON file is worse than none: the job would parse what it could and report a
    result nobody measured. Written to a sibling and renamed, so no reader ever opens a partial
    file. This runs in CI on ext4/NTFS, both of which journal, so the rename is crash-safe here
    too - a claim worth keeping only because the filesystem is known, not because renames are
    crash-safe in general.
    """
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_name(destination.name + ".partial")
    partial.write_text(json.dumps(measure(), indent=2, sort_keys=True), encoding="utf-8")
    partial.replace(destination)
    return destination
