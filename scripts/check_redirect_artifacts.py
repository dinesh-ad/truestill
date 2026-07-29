#!/usr/bin/env python3
"""Refuse accidental shell-redirect artifacts at the repository root.

Paste a markdown table cell like ``| > 25.9 min |`` into a shell and ``> 25.9`` creates an
empty file named ``25.9``. Paste a span like ``00:00 -> 2024-03-24`` and ``->`` is parsed as
``-`` then a redirect into ``2024-03-24``. Both happened on 2026-07-28 (zsh history
``1785251197`` / ``1785251198``); the empty files were then committed with the Find paging
work. This hook fails the commit if any such name is staged or already tracked at the root.

What it catches (repo-root only, no slash):

- a bare number: ``7``, ``10.0``, ``25.9``
- an ISO date: ``2024-03-24``

What it must let through (cry-wolf half): ordinary root names (``LICENSE``, ``README.md``,
``.python-version``, ``uv.lock``, ``3.13`` would only fail if someone actually put that at
the root without an extension - versions belong in files, not as filenames). Nested paths
are ignored so a fixture named ``10.0`` under ``tests/`` is not this defect.

Usage::

    python3 scripts/check_redirect_artifacts.py            # scan tracked root files
    python3 scripts/check_redirect_artifacts.py path...    # check the given paths (pre-commit)
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

#: Bare decimal or integer, no extension, no letters.
_NUMBER = re.compile(r"^\d+(\.\d+)?$")
#: Calendar date as commonly pasted from research notes.
_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def is_redirect_artifact_name(name: str) -> bool:
    """True when *name* (a single path segment) matches a known redirect-target shape."""
    return bool(_NUMBER.fullmatch(name) or _ISO_DATE.fullmatch(name))


def _root_segment(path: str) -> str | None:
    """Return the filename if *path* is at the repo root; otherwise ``None``."""
    normalised = path.replace("\\", "/").lstrip("./")
    if not normalised or "/" in normalised:
        return None
    return normalised


def _tracked_root_files() -> list[str]:
    out = subprocess.check_output(
        ["git", "ls-files", "-z"],
        text=False,
    )
    names: list[str] = []
    for raw in out.split(b"\0"):
        if not raw:
            continue
        path = raw.decode("utf-8", "surrogateescape")
        segment = _root_segment(path)
        if segment is not None:
            names.append(segment)
    return names


def main(argv: list[str]) -> int:
    if len(argv) > 1:
        candidates = [p for p in argv[1:] if _root_segment(p) is not None]
        # pre-commit may pass only changed non-root files; still scan tracked root so a
        # previously committed artifact cannot sit unnoticed until someone touches it.
        candidates.extend(_tracked_root_files())
    else:
        candidates = _tracked_root_files()

    offenders = sorted(
        {Path(c).name for c in candidates if is_redirect_artifact_name(Path(c).name)}
    )
    if not offenders:
        return 0

    print(
        "redirect-artifact: refused -- shell-redirect filenames at the repo root:",
        file=sys.stderr,
    )
    for name in offenders:
        print(f"  {name}", file=sys.stderr)
    print(
        "These are almost always accidental: a pasted ``> 25.9`` or ``-> 2024-03-24`` "
        "wrote an empty file instead of comparing. Delete them and re-stage.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
