"""Every CLI subcommand appears in the parity document, so a new one cannot ship it stale.

`docs/cli-app-parity.md` answers *"if the UI arc starts tomorrow, what is actually missing?"*. It
exists because that question was being answered from memory and **three of four expectations were
wrong, in both directions at once** - `migrate-layout`, `clean-empty` and `undo` were all assumed
missing and all three are covered, while the real gap beside `reclaim` (`catalog --move`) was on
nobody's list. `(aef)` records the same failure about the release question.

**This checks completeness, not correctness, and the difference is the whole of what it promises.**
A subcommand that exists and is absent from the table is caught here. A row whose *route* column
has since become false is **not** - that half needs a human read, and claiming otherwise would be
the guard-aimed-through-a-lens-that-cannot-resolve-it shape §4 keeps finding.

**Names come from the AST, not a regex**, for the reason `test_no_invocation_escapes_the_pin` gives
about its own first draft: prose in this file that mentions a subcommand is not a declaration of
one, and a text match cannot tell the difference.
"""

from __future__ import annotations

import ast
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
_CLI = _REPO / "packages/truestill-cli/src/truestill_cli/cli.py"
_DOC = _REPO / "docs/cli-app-parity.md"

#: Below this, the scan found too little to be asserting anything - copied from
#: `test_every_job_declares_whether_it_mutates`, whose `>= 12` floor exists because a scan that
#: finds nothing passes every downstream assertion silently. 17 subcommands on 2026-08-23; the
#: floor is deliberately under it so ordinary growth does not trip it and a broken parse does.
_MINIMUM_SUBCOMMANDS = 12


def _declared_subcommands() -> list[str]:
    """Every ``sub.add_parser("name", ...)`` in the CLI, by parsing rather than matching."""
    tree = ast.parse(_CLI.read_text(encoding="utf-8"))
    return [
        node.args[0].value
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "add_parser"
        and node.args
        and isinstance(node.args[0], ast.Constant)
        and isinstance(node.args[0].value, str)
    ]


def test_the_scan_found_the_subcommands_at_all() -> None:
    """The floor, asserted before anything is asserted about what was found.

    Without it, a rename of `add_parser` or a restructure of the parser setup makes
    `_declared_subcommands` return `[]`, and the test below then passes by checking nothing -
    reporting green about a document it never read.
    """
    found = _declared_subcommands()

    assert len(found) >= _MINIMUM_SUBCOMMANDS, (
        f"only {len(found)} subcommands were read from {_CLI.name}; the scan is broken, and "
        f"every assertion about the parity table is vacuous until it is fixed"
    )


def test_every_subcommand_is_in_the_parity_table() -> None:
    """A subcommand absent from the table is a gap nobody sized.

    ⚠ **It matches a TABLE ROW, not the document, and the first draft did the latter** - a check
    that said *"the document mentions it"* while its name and its failure message both promised
    *"the table lists it"*. §4's fifty-fourth member: the right subject through a lens that cannot
    resolve part of it. Proven by mutation - replacing a row with a sentence naming the same
    subcommand is caught now and was accepted then.

    ⚠ **And the mutation that first exposed it was itself badly chosen**, which is worth more than
    the fix. Dropping `rescan`'s row "survived" - correctly, because `rescan` has a **second** row
    in the short-answer list and the document still described it. A subcommand listed twice cannot
    demonstrate this property; the proof needs one listed once (`verify`). A surviving mutation is
    a claim about the test *and* about the mutation, and only one of those was wrong here.
    """
    rows = {
        line.split("`")[1]
        for line in _DOC.read_text(encoding="utf-8").splitlines()
        if line.startswith("| `")
    }

    missing = sorted(name for name in _declared_subcommands() if name not in rows)

    assert not missing, (
        f"{_DOC.relative_to(_REPO)} does not mention: {', '.join(missing)}. A new subcommand "
        f"leaves the parity document describing a surface that no longer exists, which is the "
        f"state it was written to end - add a row saying what the app can and cannot do."
    )
