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
        "CATALOG_BUSY_CODE": "a string constant; the terminal event's `code` for a held catalog",
        "CATALOG_BUSY_MESSAGE": "a string constant - the refusal's wording, shared with the CLI",
        "is_catalog_busy": (
            "a pure predicate over an exception's `sqlite_errorcode`; opens nothing and reads "
            "nothing. It is here rather than in `service/` because the exception is caught here "
            "- `JobManager` owns the one place a worker's failure becomes a terminal event"
        ),
    },
    "__main__.py": {
        "default_catalog_path": "resolves a path per call and returns it; opens nothing",
        "CATALOG_UNUSABLE_EXIT": (
            "an int constant - the exit code for a catalog that must not be opened. It lives in "
            "core because the CLI and the launcher must agree on it, and one meaning spread over "
            "two literals is the drift this fence is about"
        ),
        "CatalogUnusableError": (
            "an exception type the launcher turns into an exit code, exactly as `server.py` "
            "turns core's settings errors into HTTP replies. It carries a `CatalogStartupInfo` "
            "and nothing else"
        ),
        "refuse_unusable_catalog": (
            "a pure predicate that raises. It takes the ALREADY-COMPUTED inspection result, not "
            "a path - it opens nothing, reads nothing and touches no filesystem, which is why "
            "`inspect_catalog` above it needs a documented exception and this one does not"
        ),
        "format_startup_lines": "turns an inspection result into text; pure",
        "inspect_catalog": (
            "**the one documented exception (IMPLEMENTATION_STANDARDS.md §2)**: it opens a "
            "Catalog to read count() and list_drives() for the launch banner, before any route "
            "exists. Deliberate and named there rather than glossed - and pinned here so it "
            "stays the *only* one, which the prose alone could not promise."
        ),
        "is_complete": "a pure predicate over a list of findings; opens nothing",
        "binaries": (
            "the module that owns how truestill talks to external programs. Used here for "
            "`os_opener`/`popen` to hand the self-check report to the user's own viewer - a "
            "process launch, never library state. It is imported rather than duplicated so the "
            "per-platform opener has one home (§4): `service/drives.py` reveals a folder with the "
            "same call"
        ),
        "session_url_path": "resolves a path; opens nothing. Names where the report goes",
        "render": (
            "turns findings into lines; pure. It lives in core rather than here **because** §9 "
            "forbids the CLI and the app wording one outcome differently - the same reason "
            "`models.status_label` has one home"
        ),
        "write_findings": (
            "serialises findings to a path the caller names. It writes a REPORT, never library "
            "state - no catalog, no drive, nothing under a user's photos - which is the "
            "distinction this fence is about rather than the word 'write'"
        ),
    },
    "selfcheck.py": {
        "Finding": "a value type - one line of a report, passed by value",
        "Status": "an enum of outcomes; a value",
        "core_findings": (
            "runs core's own checks and returns values. It reads what this INSTALL contains - a "
            "resolved binary, an importable module, a path - and never opens the library. It is "
            "imported here rather than routed through `service/` because the direction is the "
            "other way round: core cannot import the app, so the app is what composes core's "
            "findings with the static-asset ones only it can see"
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
