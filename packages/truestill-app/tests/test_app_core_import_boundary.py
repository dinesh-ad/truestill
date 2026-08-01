"""Outside `service/`, the app may import core **values** - never core state or work.

**The rule, in words.** `service/` is where state and work cross the boundary: catalog access and
long-running jobs go through it. Every other module in `truestill_app` may still reach into core,
but only for things that hold nothing - exception types it turns into HTTP replies, value types,
pure helpers that compute a path or read a filesystem fact.

**Why this is a test and not a sentence.** `IMPLEMENTATION_STANDARDS.md` §2 has stated this rule
three different ways and been wrong twice. It said `service.py` was "the sole bridge" while
`server.py` imported four core names; that was corrected to "every catalog read and write goes
through `service/`", which was wrong because `__main__.py` opens one for the startup banner. Each
correction was a prose list kept by hand, and a prose list is exactly what audit F7 watched drift
from four symbols to fourteen without anyone noticing. **The list has to be executable or it will
rot again** - that is the whole content of this module.

**Scope: broad, deliberately.** The fence covers every `truestill_app` module outside `service/`,
not just `server.py`. The rule is a property of the boundary rather than of one file, and a guard
aimed at one file would let the same drift happen in `jobs.py` or `session_link.py` - the "a fix
reaches one copy and not its twin" failure `ENGINEERING_STANDARD.md` §4 records as this repo's
recurring one. It costs the same walk.

**Parsed, not grepped.** A regex over source text matches names inside comments and docstrings -
including §2's own allow-list if it is ever quoted into a module - and misses aliases and
multi-line imports. `ast` sees the imports and nothing else.

**Two-way, and that is a choice.** A symbol imported but not allow-listed is new drift. A symbol
allow-listed but no longer imported is the same rot in reverse: the list stops describing the
code, which is precisely what the prose did. Removing an import therefore fails here until the
entry goes too - a one-line deletion that belongs in the same commit, and the message says so.
"""

from __future__ import annotations

import ast
from pathlib import Path

import truestill_app

_APP_ROOT = Path(truestill_app.__file__).resolve().parent

#: `service/` is the unrestricted side of the boundary: it exists to hold state and work, so its
#: core imports are its job rather than a violation.
_UNFENCED = "service"

#: ``module -> {symbol: why it holds no state}``. **A new entry must carry its justification**,
#: which is the part prose could not enforce: naming a symbol is easy, arguing that it is
#: value-shaped is where a state import gets caught by the person adding it.
ALLOWED: dict[str, dict[str, str]] = {
    "__init__.py": {
        "distribution_version": "reads the installed version string; holds nothing",
    },
    "jobs.py": {
        "Progress": "a value type - one progress tick, passed by value to callers",
        "ProgressCallback": "a typing alias for the callback shape; not a runtime object",
    },
    "__main__.py": {
        "default_catalog_path": "resolves a path per call and returns it; opens nothing",
        "CatalogPresence": "an enum of startup states; a value",
        "format_startup_lines": "turns an inspection result into text; pure",
        "inspect_catalog": (
            "**the one documented exception (IMPLEMENTATION_STANDARDS.md §2)**: it opens a "
            "Catalog to read count() and list_drives() for the launch banner, before any route "
            "exists. Deliberate and named there rather than glossed - and pinned here so it "
            "stays the *only* one, which the prose alone could not promise."
        ),
    },
    "server.py": {
        "default_catalog_path": "resolves the default --db per call inside create_app",
        "InvalidEventSettingsError": "an exception turned into an HTTP reply",
        "InvalidEverydayDaySettingsError": "an exception turned into an HTTP reply",
        "ReviewCard": "a value type, carried in a review session",
    },
    "session_link.py": {
        "session_url_path": "resolves a path; opens nothing",
        "facts_for": "reads filesystem facts and returns a value",
        "stores_access_control": "answers a question about a filesystem; pure",
    },
}


def _fenced_modules() -> dict[str, Path]:
    """Every `truestill_app` module the fence applies to, keyed by its path below the package."""
    found: dict[str, Path] = {}
    for path in sorted(_APP_ROOT.rglob("*.py")):
        relative = path.relative_to(_APP_ROOT)
        if relative.parts[0] == _UNFENCED:
            continue
        found[relative.as_posix()] = path
    return found


def _core_imports(source: Path) -> set[str]:
    """The core symbols a module imports, by name, from its syntax tree.

    Covers both forms: ``from truestill_core.x import a, b`` contributes ``a`` and ``b``;
    ``import truestill_core.x`` contributes the dotted module, since that also binds core into
    the module's namespace and could reach state through it.
    """
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module and node.module.split(".")[0] == "truestill_core":
                names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.Import):
            names.update(
                alias.name for alias in node.names if alias.name.split(".")[0] == "truestill_core"
            )
    return names


def test_no_app_module_outside_service_imports_core_state_or_work() -> None:
    """New drift: a core symbol imported without a recorded justification."""
    offenders: list[str] = []
    for module, path in _fenced_modules().items():
        permitted = ALLOWED.get(module, {})
        offenders += [
            f"{module}: {symbol}" for symbol in sorted(_core_imports(path) - set(permitted))
        ]

    assert not offenders, (
        "an app module outside `service/` imports a core symbol with no recorded reason:\n  "
        + "\n  ".join(offenders)
        + "\n\nIf it is state or work - a Catalog, a pipeline stage, anything that reads or "
        "writes the library - route it through `service/`, which exists for exactly that. If it "
        "genuinely holds nothing, add it to ALLOWED with one line saying why it is value-shaped. "
        "Naming it is easy; arguing it is where a state import gets caught."
    )


def test_the_allow_list_names_nothing_the_code_stopped_importing() -> None:
    """The reverse rot: a list that has stopped describing the code.

    §2's prose failed this way rather than the other - it kept naming a shape the code had moved
    on from. An entry granting permission nobody uses is how a list quietly becomes fiction.
    """
    modules = _fenced_modules()
    stale: list[str] = []
    for module, permitted in ALLOWED.items():
        assert module in modules, f"ALLOWED names {module}, which is not a fenced module any more"
        stale += [
            f"{module}: {symbol}"
            for symbol in sorted(set(permitted) - _core_imports(modules[module]))
        ]

    assert not stale, (
        "ALLOWED permits a core import that no longer happens:\n  "
        + "\n  ".join(stale)
        + "\n\nDrop the entry in the same commit that dropped the import - a permission nobody "
        "uses is how this list stops describing the code, which is the failure it replaced."
    )


def test_the_fence_found_modules_and_real_imports() -> None:
    """Anti-vacuity: a rename or a parse failure must not make the checks above pass on nothing."""
    modules = _fenced_modules()

    assert "server.py" in modules, "server.py is not being fenced; the package layout moved"
    assert len(modules) >= 5, f"only {len(modules)} fenced modules found - the walk is wrong"

    parsed = {symbol for path in modules.values() for symbol in _core_imports(path)}
    assert parsed, "no core imports parsed at all; the AST reader is not seeing them"

    # Anchored on the allow-list rather than on a named symbol. Pinning one - `ReviewCard`, say -
    # would make this fire the day that import legitimately goes, which is a cry-wolf failure in
    # the test whose only job is to prove the parser works (§4).
    permitted = {symbol for entries in ALLOWED.values() for symbol in entries}
    assert parsed & permitted, "the parser and the allow-list share no symbol; one of them is wrong"


def test_service_is_outside_the_fence_and_uses_core_freely() -> None:
    """Cry-wolf half: `service/` is the side of the boundary that *may* hold state.

    If the fence ever grew to cover it, the guard would fire on the package doing its job - and
    a guard that fires on correct work is one somebody switches off, taking the real coverage
    with it (§4).
    """
    assert not any(m.startswith(f"{_UNFENCED}/") for m in _fenced_modules()), (
        "service/ has been pulled inside the fence; it is the unrestricted side by design"
    )

    service_root = _APP_ROOT / _UNFENCED
    assert service_root.is_dir(), "service/ is gone; this guard now checks a boundary that moved"
    service_imports = {s for p in service_root.rglob("*.py") for s in _core_imports(p)}
    assert "Catalog" in service_imports, (
        "service/ no longer imports Catalog - either the boundary moved or this guard is "
        "asserting against a layout that no longer exists"
    )
