"""`check_product_name.SUBCOMMANDS` must be every subcommand the parser actually has.

**A list that mirrors something by hand is a list nobody prunes** - the shape §4 already names
for allow-list entries, arriving here as an allow-list of words that are invocations rather than
prose. The failure is quiet in the useful direction and loud in the useless one: a subcommand
missing from the list makes the name-check flag `truestill restore ...` as lowercase prose, so a
correct line fails a gate and the fix is to edit the guard.

Found by tripping over it: `restore` shipped, `make check` failed on its own help text, and
nothing had said the list was now wrong. This test says it.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from truestill_cli.cli import _build_parser

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))

from check_product_name import SUBCOMMANDS


def parser_subcommands() -> set[str]:
    """Every subcommand argparse knows about, read from the parser rather than from a list."""
    actions = _build_parser()._actions
    subparsers = [a for a in actions if isinstance(a, argparse._SubParsersAction)]
    assert subparsers, "the CLI parser has no subparsers; this guard is reading the wrong object"
    return set(subparsers[0].choices)


def test_the_guards_subcommand_list_is_the_parsers() -> None:
    """Both directions, because they fail differently.

    A subcommand MISSING from the list makes its own help text fail the name-check - a correct
    line rejected by a stale guard. A subcommand in the list that no longer EXISTS is the
    allow-list entry nobody pruned: it silently permits lowercase prose about a word that is no
    longer a command.
    """
    missing = parser_subcommands() - set(SUBCOMMANDS)
    assert not missing, f"subcommands the name-check does not know about: {sorted(missing)}"

    retired = set(SUBCOMMANDS) - parser_subcommands()
    assert not retired, f"listed subcommands the parser no longer has: {sorted(retired)}"
