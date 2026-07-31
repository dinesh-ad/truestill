#!/usr/bin/env python3
"""Normalize em-dashes to spaced hyphens, without eating the spacing around them.

The maintainer's house style is the plain ASCII hyphen, not ``U+2014``. A repo-wide sweep that
implemented that preference on 2026-07-28 consumed the *leading* space as well as the dash,
turning ``recorded - a copy`` into ``recorded- a copy`` in 61 places -- including the backup
banner in the web UI, where a user reads it. This script is the corrected sweep.

Two rules, and the second is why the script exists at all:

1. An em-dash, with whatever whitespace surrounds it, becomes exactly ``" - "``.
2. An already-damaged ``word- word`` becomes ``word - word``.

**Suspended hyphens are not damage.** ``Camera- and app-generated names`` is correct English and
``"signal- prefix"`` names a literal filename prefix; both match a naive ``word- word`` search and
neither is touched. See :data:`ALLOWED_LITERALS`.

**User-facing surfaces are excluded, not merely handled carefully** (:data:`EXCLUDED`). UI copy,
the changelog and the readme are prose a user reads, where an em-dash is a legitimate typographic
choice and a sweep is more likely to do harm than good.

The em-dash is written as ``\\u2014`` throughout so that running this script over its own source
tree cannot corrupt it.

Usage::

    python3 scripts/normalize_dashes.py --check     # report, change nothing (CI / make check)
    python3 scripts/normalize_dashes.py --apply     # rewrite in place
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

#: Written as an escape, never as the character. This file is inside the sweep's own scope, so a
#: literal em-dash here would be rewritten by the very run that reads it.
EM_DASH = "\u2014"

#: Paths a sweep must never rewrite. Prose a user reads, where the typography is a choice.
EXCLUDED: tuple[str, ...] = (
    "packages/truestill-app/src/truestill_app/static/",
    "packages/truestill-app/src/truestill_app/templates/",
    "CHANGELOG.md",
    "README.md",
    "SECURITY.md",
)

#: Extensions worth sweeping. Anything else (media fixtures, lockfiles) is left alone.
SUFFIXES: frozenset[str] = frozenset({".md", ".py", ".toml", ".yaml", ".yml"})

#: An em-dash and any whitespace hugging it.
_EM = re.compile(rf"\s*{EM_DASH}\s*")

#: Damage: an alphanumeric, a hyphen, a single space, then a word character.
_DAMAGED = re.compile(r"(?<=[0-9A-Za-z])- (?=[0-9A-Za-z])")

#: Genuine suspended hyphens, listed **literally** rather than matched by shape.
#:
#: A suspended hyphen (``Camera- and app-generated``) and the damage (``photos- and, worse``) are
#: the same shape, and no regex over English tells them apart: the first attempt here excluded
#: ``word- and|or|to``, which protected the one real case and eleven damaged ones with it. An
#: allowlist is auditable and cannot silently grow; a heuristic silently protects whatever it
#: happens to match. Add a line here, with its file, when a real one appears.
ALLOWED_LITERALS: tuple[str, ...] = (
    "Camera- and app-generated",  # docs/metadata-chain-research.md
)


def normalize(text: str, *, repair: bool = True) -> str:
    """Apply the rules. Pure; the single definition of what the sweep does.

    ``repair`` gates rule 2 only. The damage was done by a *prose* sweep, so the repair runs on
    prose; a ``word- word`` inside source is left for a human. The one such case in this repo is
    ``"signal- prefix"`` in `categorize.py`, which names the literal filename prefix ``signal-``
    and would be actively wrong as ``signal - prefix``.
    """
    text = _EM.sub(" - ", text)
    if not repair:
        return text
    # Park each allowed literal behind a sentinel that cannot occur in source, repair everything
    # else, then put them back. NUL is not valid in any file this sweep touches.
    parked = {f"\x00{i}\x00": literal for i, literal in enumerate(ALLOWED_LITERALS)}
    for sentinel, literal in parked.items():
        text = text.replace(literal, sentinel)
    text = _DAMAGED.sub(" - ", text)
    for sentinel, literal in parked.items():
        text = text.replace(sentinel, literal)
    return text


def tracked_files() -> list[Path]:
    """Git-tracked files in scope. Uses git so untracked scratch files are never rewritten."""
    out = subprocess.run(
        ["git", "ls-files", "-z"], capture_output=True, text=True, check=True
    ).stdout
    paths = []
    for name in out.split("\0"):
        if not name or Path(name).suffix not in SUFFIXES:
            continue
        if any(name.startswith(prefix) or name == prefix for prefix in EXCLUDED):
            continue
        paths.append(Path(name))
    return paths


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true", help="report and change nothing")
    group.add_argument("--apply", action="store_true", help="rewrite in place")
    args = parser.parse_args()

    changed: list[tuple[Path, int]] = []
    for path in tracked_files():
        try:
            original = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        updated = normalize(original, repair=path.suffix == ".md")
        if updated == original:
            continue
        hits = sum(1 for _ in _EM.finditer(original))
        if path.suffix == ".md":
            stripped = original
            for literal in ALLOWED_LITERALS:
                stripped = stripped.replace(literal, "")
            hits += len(_DAMAGED.findall(stripped))
        changed.append((path, hits))
        if args.apply:
            path.write_text(updated, encoding="utf-8")

    if not changed:
        print("dash style: clean")
        return 0

    verb = "normalized" if args.apply else "would normalize"
    for path, hits in changed:
        print(f"  {verb} {path} ({hits})")
    print(f"{verb} {len(changed)} file(s)")
    return 0 if args.apply else 1


if __name__ == "__main__":
    sys.exit(main())
