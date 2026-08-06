"""Human sizes. One formatter, so two surfaces cannot disagree about one number.

DECIMAL (1000-based), and the reason is what the number gets compared against: drives are sold
in decimal GB, and GNOME Files and macOS Finder both report that way. A 1024-based figure
labelled "GB" is ~7% low at gigabyte scale, which reads as truestill being wrong about the
user's disk rather than as a units convention.

This is mirrored in `static/app.js` as `fmtBytes`, the way `plural` is - the browser cannot
import Python. `test_byte_formatting_agrees_across_surfaces` fails if the two ever drift.
"""

from __future__ import annotations

_UNITS = ("B", "KB", "MB", "GB", "TB")
_STEP = 1000


def format_bytes(value: float) -> str:
    """``5_298_094_843`` -> ``'5.3 GB'``. Bytes are whole; everything above carries one decimal.

    A negative reads as ``0 B``: sizes come from ``stat`` and from ``SUM()``, so one cannot be
    negative honestly, and printing ``-1.0 GB`` would dress a defect up as a measurement.
    """
    size = float(value)
    if size <= 0:
        return "0 B"
    index = 0
    while size >= _STEP and index < len(_UNITS) - 1:
        size /= _STEP
        index += 1
    if index == 0:
        return f"{int(size)} {_UNITS[0]}"
    return f"{size:.1f} {_UNITS[index]}"
