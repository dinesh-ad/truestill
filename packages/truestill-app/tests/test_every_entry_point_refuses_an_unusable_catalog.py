"""Every surface that inspects the catalog at startup also refuses an unusable one. `(adr)`

**Why a guard rather than a convention.** `(adr)`'s ruling keeps `inspect_catalog` a *pure
describer* - it names the state and raises nothing - so the refusal lives in one shared helper
that each entry point calls. That is the right split for the value and the wrong one for
enforcement: a fourth entry point added later would inspect, get `ZERO_BYTES`, print a calm
banner and carry on, and **a missing call is invisible**. This turns it into a failing test.

**Function-level, not module-level**, because `drives.py` legitimately does both: `prepare_catalog`
is an entry point and must refuse, while `library_status` is a per-request reader that must not -
it renders the presence into the custody strip, and raising there would turn a description into
an outage. A module-level check would be satisfied by the first and blind to the second.

Follows `test_catalog_opens_go_through_the_session.py`, including the half that matters most:
**an entry that no longer inspects also fails.** A list nobody prunes becomes a list of places
the rule does not apply.
"""

from __future__ import annotations

import ast
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]

_SURFACES = (
    _REPO / "packages/truestill-cli/src/truestill_cli",
    _REPO / "packages/truestill-app/src/truestill_app",
)

#: `module::function -> why it is an entry point`. Each must call `refuse_unusable_catalog`.
_MUST_REFUSE: dict[str, str] = {
    "truestill_cli/cli.py::_dispatch": (
        "the CLI's startup banner, ahead of the dispatch table, so every subcommand is covered "
        "by one refusal instead of seventeen"
    ),
    "truestill_app/__main__.py::main": (
        "the launcher, ahead of `bind_listening_socket`, so nothing claims an address for a "
        "process that must not serve"
    ),
    "truestill_app/service/drives.py::prepare_catalog": (
        "the hazard site: its `migrate_catalog` is what builds a schema into the failed file"
    ),
}

#: `module::function -> why this one inspects WITHOUT refusing`. Every entry is a decision.
_PURE_READERS: dict[str, str] = {
    "truestill_app/service/drives.py::library_status": (
        "a per-request reader that renders presence into the custody strip. It is reachable "
        "only from a started app, and an app cannot start on an unusable catalog - so raising "
        "here would add an outage to a state that is already impossible."
    ),
}


def _calls_by_function(module: Path) -> dict[str, set[str]]:
    """`function name -> names it calls`, for every top-level and nested function in `module`.

    Parsed rather than grepped: both names appear in imports, docstrings and comments, and a
    text search would report a module that only mentions the rule as a module that follows it.
    """
    tree = ast.parse(module.read_text(encoding="utf-8"))
    found: dict[str, set[str]] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        called = {
            inner.func.id
            for inner in ast.walk(node)
            if isinstance(inner, ast.Call) and isinstance(inner.func, ast.Name)
        }
        found[node.name] = called
    return found


def _inspecting_functions() -> dict[str, set[str]]:
    """`package/path.py::function -> the names that function calls`, for every inspector.

    Keyed against each surface ROOT rather than the module's own parent: `service/drives.py`
    sits a directory deeper than `cli.py`, so keying on `parents[1]` gives two different depths
    and the two lists below could never both be right. Caught by this test on its first run.
    """
    inspectors: dict[str, set[str]] = {}
    for root in _SURFACES:
        for module in sorted(root.rglob("*.py")):
            relative = module.relative_to(root.parent).as_posix()
            for name, called in _calls_by_function(module).items():
                if "inspect_catalog" in called:
                    inspectors[f"{relative}::{name}"] = called
    return inspectors


def test_every_startup_inspector_also_refuses_an_unusable_catalog() -> None:
    inspectors = _inspecting_functions()

    unlisted = sorted(set(inspectors) - set(_MUST_REFUSE) - set(_PURE_READERS))
    assert not unlisted, (
        f"{unlisted} inspects the catalog and is in neither list. Decide which it is: an entry "
        "point calls `refuse_unusable_catalog` and joins _MUST_REFUSE, a reader joins "
        "_PURE_READERS with the reason it may proceed on a 0-byte file."
    )

    silent = sorted(
        site
        for site in _MUST_REFUSE
        if site in inspectors and "refuse_unusable_catalog" not in inspectors[site]
    )
    assert not silent, (
        f"{silent} inspects the catalog but never calls `refuse_unusable_catalog`, so a 0-byte "
        "file would be announced calmly and then opened - which builds a schema into it and "
        "destroys the only evidence that a write failed. `(adr)`."
    )


def test_the_lists_do_not_outlive_the_call_sites_they_describe() -> None:
    """A stale allow-list is a list of places the rule silently stopped applying."""
    inspectors = _inspecting_functions()
    stale = sorted(site for site in (_MUST_REFUSE | _PURE_READERS) if site not in inspectors)
    assert not stale, (
        f"{stale} no longer calls `inspect_catalog`. Remove the entry - keeping it means the "
        "next reader trusts a list that has stopped describing the code."
    )
