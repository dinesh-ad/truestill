"""Version lookup, resolved from installed package metadata.

The version lives in exactly one place per package -- its ``pyproject.toml`` ``version``
field -- and is read back from the installed distribution here. Nothing hardcodes a version
string in Python, so a release bump cannot leave a stale number behind in a report or a UI
footer, which is precisely the kind of small lie that wastes a bug reporter's time.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

#: Shown when the distribution is not installed -- e.g. running straight from a source
#: checkout. Deliberately not a plausible-looking number: an honest "unknown" beats a
#: confident wrong answer in a bug report.
UNKNOWN_VERSION = "unknown (not installed)"


def distribution_version(distribution: str) -> str:
    """The installed version of ``distribution``, or :data:`UNKNOWN_VERSION`.

    Never raises: a missing version must not be able to take down a ``--version`` flag or a
    settings screen.
    """
    try:
        return version(distribution)
    except PackageNotFoundError:
        return UNKNOWN_VERSION
