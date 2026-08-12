"""Every tag the categoriser reads must be a tag the reader asks exiftool for. `(aaq)`.

**THE DETECTOR FOR A WHOLE CLASS, and the one that was missing when `(aaq)` was written.**
`read_metadata` invokes exiftool with an explicit named tag list, so a key absent from
`REQUESTED_TAGS` is never present in the dict - and a rule reading it is dead code that looks
alive. Two such paths shipped and sat unreachable until an audit found them by hand.

Nothing else notices: the rule compiles, is covered by unit tests that pass a hand-built dict
containing the key, and never fires in production.
"""

from __future__ import annotations

import ast
from pathlib import Path

from truestill_core.exif import _NUMERIC_TAGS, REQUESTED_TAGS

#: Tags read by a rule that is knowingly unreachable, each with the entry that owns the decision.
#: **An exemption here is a record of an OPEN decision, not a licence.** Removing one is part of
#: closing its entry; adding one needs the same kind of reasoning.
_EXEMPT = {
    # `rule_software`: requesting this turns an open-ended folder-per-application rule on across
    # every library at once and invalidates every cached metadata row. Measured 2026-08-12: it
    # would take 159 files carrying a working camera `Model` out of the timeline and grow the
    # library from 3 folder labels to 97, including `Version` and `Binary data`. That is a product
    # decision for the maintainer - reorder-and-constrain, or delete - and it is not this test's
    # to make.
    "Software": "(aaq)",
}


def _tags_read_by_the_categoriser() -> set[str]:
    """Every metadata key `categorize.py` reads, from the **AST** rather than the text.

    Parsed, not grepped, and the difference is not fussiness: the first version of this scanned
    raw source and matched the literal inside a *comment* explaining a deleted call, so it
    reported a dead path that no longer existed. A detector that reads prose is a detector that
    can be argued with.
    """
    source = Path(__file__).parents[1].joinpath("src/truestill_core/categorize.py").read_text()
    found: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        func = node.func
        reads_metadata = (
            isinstance(func, ast.Name)
            and func.id == "_text"
            and isinstance(node.args[0], ast.Name)
            and node.args[0].id == "metadata"
        ) or (
            isinstance(func, ast.Attribute)
            and func.attr == "get"
            and isinstance(func.value, ast.Name)
            and func.value.id == "metadata"
        )
        key = node.args[-1] if reads_metadata else None
        if isinstance(key, ast.Constant) and isinstance(key.value, str):
            found.add(key.value)
    return found


def test_every_tag_the_categoriser_reads_is_actually_requested() -> None:
    requested = set(REQUESTED_TAGS) | set(_NUMERIC_TAGS)
    unreachable = _tags_read_by_the_categoriser() - requested - set(_EXEMPT)
    assert not unreachable, (
        f"{sorted(unreachable)} read by categorize.py but never requested from exiftool, so the "
        f"rule reading them cannot fire. Either add the tag to REQUESTED_TAGS (which invalidates "
        f"every cached metadata row) or delete the dead path - see `(aaq)`"
    )


def test_the_regex_actually_finds_the_reads_it_is_scanning_for() -> None:
    """ANTI-VACUITY. A pattern that matched nothing would make the test above pass forever."""
    found = _tags_read_by_the_categoriser()
    assert {"Make", "Model", "LensModel"} <= found, found


def test_every_exemption_still_names_a_tag_that_is_read() -> None:
    """An exemption for a tag nobody reads any more is stale, and would silently permit its
    re-introduction. Deleting the rule must also delete its exemption."""
    stale = set(_EXEMPT) - _tags_read_by_the_categoriser()
    assert not stale, f"{sorted(stale)} is exempted but no longer read - remove the exemption"
