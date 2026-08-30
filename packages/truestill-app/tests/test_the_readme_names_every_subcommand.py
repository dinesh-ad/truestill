"""The README's subcommand sentence names every subcommand the parser defines. `(aad)`

**The defect this closes, measured 2026-08-30**: the sentence listed 17 of the 19 subcommands
`cli.py` declares. **`backup` and `bake` were missing** - two of the operations `(ahd)` and
`(ahf)` moved into the CLI specifically so no mutating behaviour lived only in the app
(`PROJECT_STATUS.md`'s condition 4). They shipped, and the front page never learned about them.

⚠ **A hand-listed set of subcommands has gone stale here twice over** - `(agu)`'s guard, and
`check_product_name.SUBCOMMANDS`, which `CLAUDE.md` already records as one of three copies of a
list that drifted. The README is now a released product's front page, so the cost of it being
wrong is a reader concluding a capability does not exist.

**Parsed with `ast`, not run**, and the derivation is
`test_the_cli_app_parity_table_is_complete.py`'s - one way to ask *"what subcommands are there"*
rather than a second that can disagree with the first.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
_CLI = REPO / "packages" / "truestill-cli" / "src" / "truestill_cli" / "cli.py"
_README = REPO / "README.md"

#: Below the count at which the scan is obviously broken rather than the parser having shrunk.
#: The same floor `test_the_cli_app_parity_table_is_complete.py` sets, and for its stated reason.
_MINIMUM_SUBCOMMANDS = 12


def _declared_subcommands() -> set[str]:
    """Every ``sub.add_parser("name", ...)`` in the CLI, by parsing rather than matching."""
    tree = ast.parse(_CLI.read_text(encoding="utf-8"))
    return {
        node.args[0].value
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "add_parser"
        and node.args
        and isinstance(node.args[0], ast.Constant)
        and isinstance(node.args[0].value, str)
    }


def _sentence() -> str:
    """The one paragraph that claims to list them, located by its own promise."""
    text = _README.read_text(encoding="utf-8")
    start = text.find("lists every subcommand")
    assert start != -1, (
        "README.md no longer contains the phrase 'lists every subcommand'. If the sentence was "
        "reworded, point this guard at the new one; if it was removed, remove this guard and say "
        "why in the commit - a guard whose subject is gone reports green about nothing."
    )
    return text[start : text.index("\n\n", start)]


def test_the_scan_found_the_subcommands_at_all() -> None:
    """The floor, asserted before anything is asserted about what was found.

    Without it, a rename of `add_parser` makes `_declared_subcommands` return an empty set and
    the test below passes by checking nothing - `ENGINEERING_STANDARD.md` §4's silent instrument.
    """
    found = _declared_subcommands()

    assert len(found) >= _MINIMUM_SUBCOMMANDS, (
        f"only {len(found)} subcommands were read from {_CLI.name}; the scan is broken, and every "
        f"assertion about the README is vacuous until it is fixed"
    )


def test_the_readme_names_every_subcommand() -> None:
    """THE GUARD. A subcommand the parser defines and the front page omits does not exist to a
    reader - which is what happened to `backup` and `bake`."""
    named = set(re.findall(r"`([a-z][a-z-]*)`", _sentence()))
    missing = sorted(_declared_subcommands() - named)

    assert not missing, (
        "README.md's subcommand sentence claims to list every one and omits: "
        + ", ".join(missing)
        + ".\nAdd them, or reword the sentence so it stops promising completeness."
    )


def test_it_does_not_name_a_subcommand_that_does_not_exist() -> None:
    """The other direction, which the first cannot see.

    A removed or renamed subcommand left in the sentence sends a reader to a command that answers
    `invalid choice`. ⚠ **`truestill` itself is excluded**, because the sentence necessarily names
    the program - not because it is a subcommand.
    """
    named = set(re.findall(r"`([a-z][a-z-]*)`", _sentence())) - {"truestill"}
    phantom = sorted(named - _declared_subcommands())

    assert not phantom, (
        "README.md names these as subcommands and the parser defines no such thing: "
        + ", ".join(phantom)
    )
