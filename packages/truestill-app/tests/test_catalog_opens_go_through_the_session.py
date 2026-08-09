"""Every surface catalog open goes through the session wrapper, so the trigger cannot be missed.

**A missed call site is invisible**, which is why this is a guard and not a convention: the
decision saves locally, the drive copy silently does not move, and nothing anywhere says so. The
user finds out when they lose the catalog, which is the one moment this feature exists for.

Follows `test_app_core_import_boundary.py`'s shape, including the half that matters most: an
allow-list entry for a call that no longer happens **also fails**. An allow-list nobody prunes
becomes a list of places the rule does not apply.

Deliberately does NOT look at tests. Tests open `Catalog(...)` directly and must keep doing so:
that is what makes it impossible for a test run to write to a real drive, rather than merely
unlikely (`ENGINEERING_STANDARD.md` §4).
"""

from __future__ import annotations

import ast
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]

#: Surface source that must not construct a `Catalog` directly. Tests are not here, on purpose.
_SURFACES = (
    _REPO / "packages/truestill-cli/src/truestill_cli",
    _REPO / "packages/truestill-app/src/truestill_app",
)

#: `module path -> why this one is allowed`. Every entry is checked to still be true.
#:
#: **Empty, and it stayed empty on the first attempt.** An entry was written here for
#: `truestill_cli/cli.py` on the assumption its `_catalog` wrapper still constructed a `Catalog`;
#: the staleness check below refused it within a minute, because `_catalog` delegates to
#: `open_catalog` and cli.py names `Catalog` only in annotations. The check earned itself before
#: the list had a single true entry.
_ALLOWED: dict[str, str] = {}


def _catalog_calls(source: Path) -> list[int]:
    """Line numbers where this module calls `Catalog(...)`.

    Parsed rather than grepped: `Catalog` appears constantly as a type annotation, in docstrings
    and in names like `CatalogPresence`, and a text search would report all of them.
    """
    tree = ast.parse(source.read_text(encoding="utf-8"))
    return [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "Catalog"
    ]


def _surface_modules() -> list[Path]:
    return sorted(path for root in _SURFACES for path in root.rglob("*.py"))


def test_no_surface_opens_a_catalog_outside_the_session_wrapper() -> None:
    offences: list[str] = []
    for module in _surface_modules():
        relative = module.relative_to(module.parents[1]).as_posix()
        calls = _catalog_calls(module)
        if calls and relative not in _ALLOWED:
            lines = ", ".join(str(line) for line in calls)
            offences.append(f"{relative}:{lines}")

    assert not offences, (
        "a surface constructs Catalog(...) directly, so the decisions trigger never fires for "
        f"that work and nothing reports it: {offences}. Use `open_catalog` (or the CLI's "
        "`_catalog`), or record a justification in this test's allow-list."
    )


def test_the_allow_list_holds_no_entry_that_has_stopped_being_true() -> None:
    """THE HALF THAT ROTS. A justification for a call that no longer happens reads as a rule with
    an exception, and the next person adds theirs beside it."""
    modules = {m.relative_to(m.parents[1]).as_posix(): m for m in _surface_modules()}
    stale = [name for name in _ALLOWED if name not in modules or not _catalog_calls(modules[name])]

    assert not stale, f"allow-list entries for calls that no longer exist: {stale}"


def test_every_surface_module_that_opens_a_catalog_uses_the_wrapper() -> None:
    """The cry-wolf half: a guard that passed because nothing opens a catalog at all would be
    worthless, and this suite is one careless refactor away from that."""
    users = [
        module.name
        for module in _surface_modules()
        if "open_catalog(" in module.read_text(encoding="utf-8")
    ]

    assert len(users) > 10, f"only {len(users)} surface modules open a catalog; the guard is idle"
