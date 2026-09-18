"""A test may not slice source between two independently-located markers.

**The defect, measured.** `tests/e2e/test_find_on_the_pattern.py` read `catalog.py` and sliced::

    body = sql[sql.index("def _search_where") : sql.index("class Catalog")]

`_search_where` is at line 1251, `class Catalog` at line 424. The slice ran backwards, **Python
returned `''` rather than raising**, and the assertion below failed with *"the terms are no longer
ANDed"* - accusing a search that was correct. Wrong from the commit that wrote it (`8c46c0a`,
2026-09-15), and it took **three nightly runs** to surface because `testpaths` keeps `tests/e2e`
out of `make check`.

**Why a guard rather than three fixes, which is `(ago)`'s bar.** The census found four sites of
this shape and the fix-the-instances answer leaves the shape available to the next person. More
pointedly, the three that were *not* failing are the dangerous ones: two pair a **negative**
assertion with the slice - `"drive_uuid = ?" not in body`, `"<table" not in find` - and
``x not in ""`` is **True**. An inversion there does not go red; it passes vacuously and the guard
is dead. The loud instance was the lucky one.

**Why this is guardable where `test_platform_skips_collect_everywhere.py` says its own class is
not.** That file's defect is a *missing* condition, which no AST can see. This one is a *present*
and fully-formed expression: a `Slice` whose `lower` and `upper` are both `.index()`/`.find()`
calls. Nothing has to be inferred. The narrowness is deliberate - one-sided slices (`s[a.index(x):]`,
`s[:s.index(x)]`) cannot invert and are not flagged.

**Placement.** This lives under `packages/` rather than beside the test it was written for,
because `testpaths` excludes `tests/e2e` - a guard against a defect that only the nightly caught
would itself only run at night. The helper's own refusals are asserted here too: the guard points
at `source_region` as the remedy, so a remedy that failed to refuse an empty region would make
this file a signpost to nothing.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from source_region import function_source, region_between

REPO = Path(__file__).resolve().parents[3]

#: Locating a marker. Both spellings are used in this repo.
LOCATORS: frozenset[str] = frozenset({"index", "find"})


def _test_files() -> list[Path]:
    return sorted(REPO.glob("packages/*/tests/**/*.py")) + sorted(REPO.glob("tests/**/*.py"))


def _is_locator_call(node: ast.expr | None) -> bool:
    """Whether ``node`` is a ``<something>.index(...)`` / ``.find(...)`` call."""
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in LOCATORS
    )


def two_marker_slices(source: str, filename: str = "<source>") -> list[int]:
    """Line numbers of every ``x[a.index(...) : b.index(...)]`` in ``source``."""
    tree = ast.parse(source, filename=filename)
    return [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Subscript)
        and isinstance(node.slice, ast.Slice)
        and _is_locator_call(node.slice.lower)
        and _is_locator_call(node.slice.upper)
    ]


def _offenders() -> list[str]:
    found: list[str] = []
    for path in _test_files():
        if path.resolve() == Path(__file__).resolve():
            continue
        for line in two_marker_slices(path.read_text(encoding="utf-8"), str(path)):
            found.append(f"{path.relative_to(REPO).as_posix()}:{line}")
    return found


def test_no_test_slices_between_two_independently_located_markers() -> None:
    offenders = _offenders()
    assert not offenders, (
        f"{len(offenders)} slice(s) locate both ends independently, so they invert into `''` "
        "the moment the file is reordered - silently, and vacuously true for any `not in` "
        "assertion beside them:\n  "
        + "\n  ".join(offenders)
        + "\n\nUse `source_region.function_source(src, name)` for a Python definition, or "
        "`source_region.region_between(text, start, end)` otherwise. Both raise rather than "
        "returning an empty region."
    )


# --------------------------------------------------------------- the detector actually detects


def test_the_detector_sees_the_shape_that_caused_this() -> None:
    """⚠ The exact line from `test_find_on_the_pattern.py`, so the guard is proved on the original."""
    bad = 'body = sql[sql.index("def _search_where") : sql.index("class Catalog")]\n'
    assert two_marker_slices(bad) == [1]


def test_the_detector_leaves_one_sided_slices_alone() -> None:
    """Cry-wolf check: neither of these can invert, and flagging them would train people to ignore it."""
    assert two_marker_slices('tail = s[s.index("a") :]\n') == []
    assert two_marker_slices('head = s[: s.index("a")]\n') == []
    assert two_marker_slices("chunk = s[3:9]\n") == []


# ------------------------------------------------------------------- the remedy refuses emptiness


def test_function_source_is_order_independent() -> None:
    """The defect was positional; this cannot be, which is the point of using the AST."""
    src = "class C:\n    pass\n\n\ndef after() -> int:\n    return 1\n"
    assert "return 1" in function_source(src, "after")


def test_function_source_refuses_an_absent_name() -> None:
    with pytest.raises(LookupError, match="no function or method named"):
        function_source("x = 1\n", "gone")


def test_function_source_refuses_an_ambiguous_name() -> None:
    src = "def f() -> None:\n    pass\n\n\nclass C:\n    def f(self) -> None:\n        pass\n"
    with pytest.raises(LookupError, match="2 definitions named"):
        function_source(src, "f")


def test_region_between_cannot_invert() -> None:
    """The end marker is searched from the far side of the start, so crossing is impossible."""
    assert "middle" in region_between("START middle END", "START", "END")
    with pytest.raises(LookupError, match="does not appear after"):
        region_between("END ... START", "START", "END")


def test_region_between_refuses_a_region_with_nothing_in_it() -> None:
    """⚠ The region always contains `start`, so emptiness has to be measured BETWEEN the markers.

    Checking `region.strip()` instead - as this first did - is a condition that can never fire,
    which is the dead-guard shape this whole file argues against. The test caught it.
    """
    with pytest.raises(LookupError, match="nothing lies between"):
        region_between("ab", "a", "b")


def test_region_between_refuses_a_missing_marker() -> None:
    with pytest.raises(LookupError, match="is not in this source"):
        region_between("hello", "nope", "lo")
