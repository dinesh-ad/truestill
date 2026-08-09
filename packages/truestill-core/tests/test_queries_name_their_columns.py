"""No query in the catalog selects `*`. The rule is catalog-wide, not local to one module.

**It began as a privacy guarantee in `decisions.py`:** the gather reads column by column so a
column added to `files` or `settings` later cannot arrive on a user's drive by default. That
reasoning is not specific to the drive document. A `SELECT *` hands every future column to
whatever consumes the row - a UI payload, a log line, an export - and the person who adds the
column is not the person who wrote the consumer.

**Same shape as the exclusion-by-default rule elsewhere in this codebase:** the safe behaviour is
what you get when someone forgets. Naming columns means a new one reaches a caller only when
somebody decides it should.

Scoped to `catalog.py`, which is where the queries are. A guard whose scope is "everywhere" is
one nobody can keep green.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

CATALOG = Path(__file__).resolve().parents[1] / "src" / "truestill_core" / "catalog.py"

#: `SELECT *` and `SELECT alias.*`, inside a string literal rather than in prose.
STAR = re.compile(r"SELECT\s+(?:[a-z_]+\.)?\*", re.IGNORECASE)


def _sql_literals(source: Path) -> list[tuple[int, str]]:
    """Every string constant in the module, with its line - comments and docstrings excluded.

    Parsed rather than grepped: this file's own docstrings discuss `SELECT *` by name, and a text
    search would report the sentence explaining the rule as a violation of it.
    """
    tree = ast.parse(source.read_text(encoding="utf-8"))
    docstrings = {
        id(node.body[0].value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef)
        and node.body
        and isinstance(node.body[0], ast.Expr)
        and isinstance(node.body[0].value, ast.Constant)
        and isinstance(node.body[0].value.value, str)
    }
    return [
        (node.lineno, node.value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and id(node) not in docstrings
    ]


def test_no_catalog_query_selects_star() -> None:
    offences = [f"catalog.py:{line}" for line, text in _sql_literals(CATALOG) if STAR.search(text)]

    assert not offences, (
        f"a query selects every column, so a column added later reaches its caller without "
        f"anyone deciding it should: {offences}. Name the columns, as `gather_decisions` does."
    )


def test_the_guard_can_see_a_star_at_all() -> None:
    """CRY-WOLF HALF, and this guard needs it more than most: it reads string literals through
    `ast`, so a mistake in the extraction makes it pass over everything in silence rather than
    fail. Proven against a fixture rather than against the file it guards."""
    assert STAR.search("SELECT * FROM files")
    assert STAR.search("SELECT d.* FROM drives d")
    assert not STAR.search("SELECT uuid, label FROM drives")
    assert not STAR.search("COUNT(*) FROM files"), "COUNT(*) is not a column list"
