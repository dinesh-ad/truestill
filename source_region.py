"""Extract a named region of source for a test to assert against - or fail loudly.

**The failure this exists to prevent, measured.** `tests/e2e/test_find_on_the_pattern.py` read
`catalog.py` and sliced it between two markers::

    body = sql[sql.index("def _search_where") : sql.index("class Catalog")]

`_search_where` is defined at line 1251 and `class Catalog` at line 424, so the slice ran
backwards. **Python returns `''` for that rather than raising**, and the assertion below it then
failed against nothing with the message *"the terms are no longer ANDed"* - accusing a search that
was, and still is, correct. It was wrong from the commit that wrote it (`8c46c0a`, 2026-09-15) and
took three nightly runs to surface, because the browser lane is the only thing that runs it.

**Both failure directions matter, and only one of them is loud.** That test asserted a string was
`in` the region, so an empty region failed. Its neighbours assert things are `not in` a region -
`"drive_uuid = ?" not in body`, `"<table" not in find` - and `x not in ""` is **True**. An inverted
slice there does not fail; it passes vacuously and the guard is dead with nothing to show for it.

So neither function here can return an empty region: they raise `LookupError` instead.
"""

from __future__ import annotations

import ast


def function_source(source: str, name: str) -> str:
    """The source of the function or method ``name``, located by AST rather than by offset.

    Order-independent by construction - where the definition sits in the file cannot matter,
    which is the whole defect above. Methods are found as readily as module-level functions.

    Raises ``LookupError`` if ``name`` is absent, or ambiguous: two definitions sharing a name
    mean the caller is asserting against whichever one happened to come first, which is the same
    class of accident one layer along.
    """
    tree = ast.parse(source)
    found = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name == name
    ]
    if not found:
        msg = (
            f"no function or method named {name!r} in this source - "
            "the extraction is broken, not the code it was watching"
        )
        raise LookupError(msg)
    if len(found) > 1:
        lines = ", ".join(str(node.lineno) for node in found)
        msg = (
            f"{len(found)} definitions named {name!r} (lines {lines}) - say which one, "
            "because asserting against the first is an accident waiting to change"
        )
        raise LookupError(msg)
    segment = ast.get_source_segment(source, found[0])
    if not segment:
        msg = f"could not recover the source of {name!r} - the extraction is broken"
        raise LookupError(msg)
    return segment


def region_between(text: str, start: str, end: str) -> str:
    """The slice of ``text`` from ``start`` to the first ``end`` **after it**.

    Searching for ``end`` from the far side of ``start`` is what makes inversion impossible: the
    two markers are not located independently, so they cannot cross. For anything that is not
    Python - markup, JavaScript - this is the form to use; :func:`function_source` is better
    wherever the target is a Python definition.

    Raises ``LookupError`` if either marker is absent, or if nothing lies between them.
    """
    opened = text.find(start)
    if opened < 0:
        msg = f"the start marker {start!r} is not in this source; the region is blind"
        raise LookupError(msg)
    closed = text.find(end, opened + len(start))
    if closed < 0:
        msg = f"the end marker {end!r} does not appear after {start!r}; the region is blind"
        raise LookupError(msg)
    if not text[opened + len(start) : closed].strip():
        msg = (
            f"nothing lies between {start!r} and {end!r}; the region asserts against its own marker"
        )
        raise LookupError(msg)
    return text[opened:closed]
