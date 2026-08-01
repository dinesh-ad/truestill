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

#: ``ERROR_INVALID_HANDLE``. What ``AttachConsole`` reports for a process that has no console,
#: which is the outcome that would prove suppression worked.
_ERROR_INVALID_HANDLE = 6


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


def _attach_console() -> dict[str, Any]:
    """Windows-only question 2: does ``CREATE_NO_WINDOW`` really suppress the console?

    **The control is the gate, not the test.** ``AttachConsole`` can fail for reasons that have
    nothing to do with the child - most obviously if *this* process already owns a console, in
    which case it refuses before ever consulting the child, and a naive reading would score that
    as "suppression worked". So a child is first launched **without** the flag and must be
    attachable. If that control does not succeed, the technique is unsound here and the result
    is reported as such rather than as a measurement.
    """
    # `sys.platform`, not `os.name`: mypy narrows on it, so everything below is checked as the
    # Windows-only code it is instead of failing on a Linux run where `ctypes.WinDLL` does not
    # exist. Putting packaging/ in the type fence found that immediately.
    if sys.platform != "win32":
        return {"technique": "unavailable", "reason": "AttachConsole is Windows-only"}

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    def attachable(creationflags: int) -> dict[str, Any]:
        child = subprocess.Popen(
            ["cmd", "/c", "timeout", "/t", str(_CHILD_SECONDS), "/nobreak"],
            creationflags=creationflags,
        )
        try:
            time.sleep(0.7)  # let the child get far enough to own (or not own) a console
            ok = bool(kernel32.AttachConsole(child.pid))
            err = ctypes.get_last_error()
            if ok:
                kernel32.FreeConsole()
            return {"attached": ok, "last_error": err}
        finally:
            child.kill()
            child.wait(timeout=10)

    no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    control = attachable(0)
    if not control["attached"]:
        return {
            "technique": "unsound",
            "reason": (
                "the control child, launched WITHOUT CREATE_NO_WINDOW, could not be attached to "
                "either - so a failure to attach proves nothing about suppression"
            ),
            "control": control,
        }

    suppressed = attachable(no_window)
    return {
        "technique": "sound",
        "control": control,
        "with_no_window": suppressed,
        "flag_value": no_window,
        "assertion": (
            "pass"
            if not suppressed["attached"] and suppressed["last_error"] == _ERROR_INVALID_HANDLE
            else "fail"
        ),
    }


def measure() -> dict[str, Any]:
    """Every finding this artifact can produce about itself."""
    return {
        "layout": _layout(),
        "exiftool": _exiftool(),
        "legacy_probe": _legacy_probe(),
        "console_suppression": _attach_console(),
    }


def write_findings(destination: Path) -> Path:
    """Write the findings **atomically**, so a partial file can never read as a pass.

    A half-written JSON file is worse than none: the job would parse what it could and report a
    result nobody measured. Written to a sibling and renamed, which is atomic on both platforms.
    """
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_name(destination.name + ".partial")
    partial.write_text(json.dumps(measure(), indent=2, sort_keys=True), encoding="utf-8")
    partial.replace(destination)
    return destination
